#!/usr/bin/env python
"""Timing / efficiency decomposition of the five full-set WebArena paired runs.

Event-stamping model (verified in hippo-src/hippo/wa/run.py `one_task` and `_rollout_worker`):
  * per arm, tasks run strictly sequentially; the N=8 rollouts of a task run in parallel in
    8 worker processes and their events (wa_episode_start / wa_step / wa_episode_end /
    wa_episode_error / wa_host_guard) are COLLECTED in the worker and REPLAYED into the parent
    logger after the whole batch returns -> all of them carry the parent's replay timestamp.
    So consecutive wa_step deltas and episode_start->episode_end are ~0 by construction; the
    real rollout time of a task is (replay t) - (previous boundary).
  * wa_judge for all rollouts is emitted after all verdicts are computed (one timestamp).
  * wa_write_l1 events are emitted one by one as each L1 item is written (real per-item time);
    wa_write_l2 after the contrast call; wa_task closes the task.
  * reset_done carries `seconds` (subprocess wall) and is stamped at reset END.
Phases attributed by walking each arm's events in file order with a moving cursor.
"""
import json, re, sys, collections, statistics
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = [
    "runs/wa_fleet_shopping_all_20260811_191401_20260811_191415",
    "runs/wa_fleet_shopping_admin_all_20260818_005633_20260818_005647",
    "runs/wa_fleet_gitlab_all_20260815_172053_20260815_172110",
    "runs/wa_fleet_reddit_all_20260814_002621_20260814_002652",
    "runs/wa_fleet_map_readonly_20260813_103741_20260813_103743",
]
ROLLOUT_KINDS = {"wa_episode_start", "wa_step", "wa_episode_end", "wa_episode_error", "wa_host_guard"}
WRITE_KINDS = {"wa_write_l1", "wa_write_l2"}
ARMS = ("nomem", "withmem")
MAX_STEPS = 30


def pct(xs, q):
    xs = [x for x in xs if x is not None]
    return float(np.percentile(xs, q)) if xs else float("nan")


def med(xs):
    return pct(xs, 50)


def fmt(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:.{nd}f}"


def err_class(err: str) -> str:
    e = err.strip()
    e = re.sub(r"http://\S+", "URL", e)
    e = re.sub(r"\d+(\.\d+)?", "N", e)
    # keep the exception type + first clause
    head = e.split("\n")[0]
    return head[:90]


def analyze_run(run_dir: Path):
    ev = [json.loads(l) for l in open(run_dir / "events.jsonl")]
    ts = [e["t"] for e in ev]
    monotonic = all(b >= a for a, b in zip(ts, ts[1:]))
    cfg = ev[0]["config"]
    site = cfg["wa"]["site"]
    run_start_t = ev[0]["t"]
    summary = json.load(open(run_dir / "summary.json"))

    # assign untagged events (wa_write_l1/l2) to the arm of the last tagged event seen
    cur_tag = None
    for e in ev:
        if e.get("tag") in ARMS:
            cur_tag = e["tag"]
        e["_arm"] = e.get("tag") if e.get("tag") in ARMS else cur_tag

    out = {"site": site, "run": run_dir.name, "monotonic": monotonic,
           "run_wall_h": (ev[-1]["t"] - run_start_t) / 3600, "arms": {}}
    prev_arm_end = run_start_t
    for arm in ARMS:
        aev = [e for e in ev if e["_arm"] == arm]
        if not aev:
            continue
        first = aev[0]
        arm_first = first["t"] - first["seconds"] if first["kind"] == "reset_done" else first["t"]
        arm_last = aev[-1]["t"]
        A = {
            "phase": collections.Counter(),  # rollout / judge / write / reset / other
            "tasks": [], "reset_secs": [], "n_reset": 0,
            "step_deltas_literal": [], "episode_dur_literal": [],
            "n_rollouts": 0, "n_steps_list": [], "n_max_steps": 0, "n_ge_max": 0, "max_steps_seen": 0,
            "n_action_errors": 0, "rollouts_with_action_err": 0, "steps_with_action_err": 0,
            "n_steps_total": 0,
            "n_episode_error": 0, "err_reasons": collections.Counter(), "err_steps": [],
            "n_dropped_events": 0, "n_dropped_rollouts": 0, "n_all_failed": 0, "n_host_guard": 0,
            "n_task_error": 0,
            "retrieve_n": 0, "retrieve_hit": 0, "mem_chars": [],
            "l1_gaps": [], "n_l1": 0, "n_l2": 0,
        }
        # "other" before the arm's first event (pool spin-up / previous-arm teardown)
        A["phase"]["other_setup"] += arm_first - prev_arm_end
        cursor = arm_first
        task = None  # current task record
        step_prev = {}  # (task_id, rollout) -> last step t
        ep_start = {}

        def close_task(tk, t_end, kind):
            tk["end_kind"] = kind
            tk["t_end"] = t_end
            tk["cycle"] = t_end - tk["t_begin"]  # excludes reset
            A["tasks"].append(tk)

        for e in aev:
            k, t = e["kind"], e["t"]
            if k == "reset_done":
                s = float(e["seconds"])
                gap = (t - s) - cursor
                if gap > 0:
                    A["phase"]["other"] += gap
                A["phase"]["reset"] += s
                A["reset_secs"].append(s); A["n_reset"] += 1
                cursor = t
                continue
            if k == "task_error":
                A["n_task_error"] += 1
                A["phase"]["other"] += t - cursor; cursor = t
                if task is not None:
                    close_task(task, t, "task_error"); task = None
                continue
            tid = e.get("task_id")
            if task is None or (tid is not None and tid != task["task_id"]):
                if task is not None:  # task never closed (should not happen)
                    close_task(task, cursor, "unclosed")
                task = {"task_id": tid, "t_begin": cursor, "t_retrieve": None, "t_roll": None,
                        "t_judge": None, "t_l1": [], "t_l2": None, "t_task": None,
                        "n_steps": [], "n_err": 0, "first_ep_start": None, "last_ep_end": None,
                        "n_judge": 0}
            if k == "wa_retrieve":
                A["phase"]["retrieve"] += t - cursor
                task["t_retrieve"] = t; task["retrieve_secs"] = t - cursor
                A["retrieve_n"] += 1
                if e.get("n_retrieved", 0) > 0:
                    A["retrieve_hit"] += 1
                A["mem_chars"].append(e.get("mem_chars", 0))
                cursor = t
            elif k in ROLLOUT_KINDS:
                if task["t_roll"] is None:
                    task["t_roll"] = t
                    task["rollout_secs"] = t - cursor
                A["phase"]["rollout"] += t - cursor
                cursor = t
                r = e.get("rollout")
                if k == "wa_episode_start":
                    if task["first_ep_start"] is None:
                        task["first_ep_start"] = t
                    ep_start[(tid, r)] = t
                elif k == "wa_step":
                    key = (tid, r)
                    if key in step_prev:
                        A["step_deltas_literal"].append(t - step_prev[key])
                    step_prev[key] = t
                    A["n_steps_total"] += 1
                    if e.get("action_error"):
                        A["steps_with_action_err"] += 1
                elif k == "wa_episode_end":
                    task["last_ep_end"] = t
                    A["n_rollouts"] += 1
                    ns = int(e.get("n_steps", 0))
                    task["n_steps"].append(ns)
                    A["n_steps_list"].append(ns)
                    A["max_steps_seen"] = max(A["max_steps_seen"], ns)
                    if ns == MAX_STEPS:
                        A["n_max_steps"] += 1
                    if ns >= MAX_STEPS:
                        A["n_ge_max"] += 1
                    nae = int(e.get("n_action_errors", 0))
                    A["n_action_errors"] += nae
                    if nae > 0:
                        A["rollouts_with_action_err"] += 1
                    if (tid, r) in ep_start:
                        A["episode_dur_literal"].append(t - ep_start[(tid, r)])
                elif k == "wa_episode_error":
                    A["n_episode_error"] += 1
                    task["n_err"] += 1
                    A["err_reasons"][err_class(e.get("err", ""))] += 1
                    A["err_steps"].append(int(e.get("n_steps", 0)))
                elif k == "wa_host_guard":
                    A["n_host_guard"] += 1
            elif k == "wa_judge":
                if task["t_judge"] is None:
                    task["t_judge"] = t
                    task["judge_secs"] = t - cursor
                A["phase"]["judge"] += t - cursor
                task["n_judge"] += 1
                cursor = t
            elif k in ("wa_rollouts_dropped",):
                A["n_dropped_events"] += 1
                A["n_dropped_rollouts"] += int(e.get("n_err", 0))
                A["phase"]["judge"] += t - cursor; cursor = t
            elif k == "wa_task_all_failed":
                A["n_all_failed"] += 1
                A["phase"]["judge"] += t - cursor; cursor = t
                close_task(task, t, "all_failed"); task = None
            elif k == "wa_write_l1":
                A["phase"]["write"] += t - cursor
                if task["t_l1"]:
                    A["l1_gaps"].append(t - task["t_l1"][-1])
                task["t_l1"].append(t)
                A["n_l1"] += 1
                cursor = t
            elif k == "wa_write_l2":
                A["phase"]["write"] += t - cursor
                task["t_l2"] = t; A["n_l2"] += 1
                cursor = t
            elif k == "wa_task":
                tail = t - cursor
                # withmem: the tail after the last judge/write is reflect/contrast work that
                # produced no NEW item (dedup) -> still writing cost. nomem: should be ~0.
                if arm == "withmem" and task["t_judge"] is not None:
                    A["phase"]["write"] += tail
                else:
                    A["phase"]["other"] += tail
                task["t_task"] = t
                task["tail_secs"] = tail
                cursor = t
                close_task(task, t, "wa_task"); task = None
            else:
                A["phase"]["other"] += t - cursor; cursor = t
        if task is not None:
            close_task(task, cursor, "unclosed")
        prev_arm_end = arm_last

        T = A["tasks"]
        done = [tk for tk in T if tk["end_kind"] == "wa_task"]
        strict_h = (arm_last - arm_first) / 3600
        incl_h = (arm_last - (arm_first - A["phase"]["other_setup"])) / 3600
        ph = A["phase"]
        phase_total = sum(ph.values())
        res = {
            "n_tasks": len(done), "n_task_records": len(T),
            "arm_first": arm_first, "arm_last": arm_last,
            "arm_wall_strict_h": strict_h, "arm_wall_incl_setup_h": incl_h,
            "tasks_per_hour_strict": len(done) / strict_h if strict_h else float("nan"),
            "tasks_per_hour_incl": len(done) / incl_h if incl_h else float("nan"),
            "phase_secs": dict(ph), "phase_total_secs": phase_total,
            "phase_share": {k: v / (arm_last - (arm_first - ph["other_setup"])) for k, v in ph.items()},
            "reset_total_s": sum(A["reset_secs"]), "n_reset": A["n_reset"],
            "reset_med_s": med(A["reset_secs"]) if A["reset_secs"] else None,
            # real (boundary-based) latencies
            "cycle_med": med([tk["cycle"] for tk in done]), "cycle_p90": pct([tk["cycle"] for tk in done], 90),
            "cycle_mean": float(np.mean([tk["cycle"] for tk in done])) if done else None,
            "cycle_max": max([tk["cycle"] for tk in done]) if done else None,
            "retrieve_med": med([tk.get("retrieve_secs") for tk in done if tk.get("retrieve_secs") is not None]),
            "retrieve_p90": pct([tk.get("retrieve_secs") for tk in done if tk.get("retrieve_secs") is not None], 90),
            "rollout_med": med([tk.get("rollout_secs") for tk in done if tk.get("rollout_secs") is not None]),
            "rollout_p90": pct([tk.get("rollout_secs") for tk in done if tk.get("rollout_secs") is not None], 90),
            "rollout_max": max([tk.get("rollout_secs", 0) for tk in T] or [0]),
            "rollout_ge_1800": sum(1 for tk in T if tk.get("rollout_secs", 0) >= 1800),
            "rollout_ge_900": sum(1 for tk in T if tk.get("rollout_secs", 0) >= 900),
            "judge_med": med([tk.get("judge_secs") for tk in done if tk.get("judge_secs") is not None]),
            "judge_p90": pct([tk.get("judge_secs") for tk in done if tk.get("judge_secs") is not None], 90),
            "judge_per_rollout_med": med([tk["judge_secs"] / tk["n_judge"] for tk in done if tk.get("judge_secs") is not None and tk["n_judge"]]),
            # sec/step proxies: rollout batch wall / max n_steps (critical path) and / mean n_steps
            "sec_per_step_crit_med": med([tk["rollout_secs"] / max(tk["n_steps"]) for tk in done if tk.get("rollout_secs") and tk["n_steps"] and max(tk["n_steps"]) > 0]),
            "sec_per_step_crit_p90": pct([tk["rollout_secs"] / max(tk["n_steps"]) for tk in done if tk.get("rollout_secs") and tk["n_steps"] and max(tk["n_steps"]) > 0], 90),
            "sec_per_step_mean_med": med([tk["rollout_secs"] / statistics.mean(tk["n_steps"]) for tk in done if tk.get("rollout_secs") and tk["n_steps"] and statistics.mean(tk["n_steps"]) > 0]),
            "max_nsteps_per_task_med": med([max(tk["n_steps"]) for tk in done if tk["n_steps"]]),
            "mean_nsteps_per_rollout": float(np.mean(A["n_steps_list"])) if A["n_steps_list"] else None,
            "steps_per_task_mean": float(np.mean([sum(tk["n_steps"]) for tk in done])) if done else None,
            # write latencies (withmem)
            "judge_to_first_l1_med": med([tk["t_l1"][0] - tk["t_judge"] for tk in done if tk["t_l1"] and tk["t_judge"]]),
            "judge_to_last_l1_med": med([tk["t_l1"][-1] - tk["t_judge"] for tk in done if tk["t_l1"] and tk["t_judge"]]),
            "judge_to_l2_med": med([tk["t_l2"] - tk["t_judge"] for tk in done if tk["t_l2"] and tk["t_judge"]]),
            "judge_to_l2_p90": pct([tk["t_l2"] - tk["t_judge"] for tk in done if tk["t_l2"] and tk["t_judge"]], 90),
            "judge_to_task_med": med([tk["t_task"] - tk["t_judge"] for tk in done if tk["t_judge"]]),
            "judge_to_task_p90": pct([tk["t_task"] - tk["t_judge"] for tk in done if tk["t_judge"]], 90),
            "judge_to_task_mean": float(np.mean([tk["t_task"] - tk["t_judge"] for tk in done if tk["t_judge"]])) if done else None,
            "l1_item_gap_med": med(A["l1_gaps"]), "l1_item_gap_p90": pct(A["l1_gaps"], 90),
            "l1_per_task_when_any_med": med([len(tk["t_l1"]) for tk in done if tk["t_l1"]]),
            "tasks_with_l1": sum(1 for tk in done if tk["t_l1"]), "tasks_with_l2": sum(1 for tk in done if tk["t_l2"]),
            "tasks_with_write_tail_gt5s": sum(1 for tk in done if tk.get("tail_secs", 0) > 5),
            "n_l1": A["n_l1"], "n_l2": A["n_l2"],
            # literal (as-asked) event deltas, showing the replay artifact
            "lit_step_delta_med": med(A["step_deltas_literal"]), "lit_step_delta_p90": pct(A["step_deltas_literal"], 90),
            "lit_step_delta_max": max(A["step_deltas_literal"]) if A["step_deltas_literal"] else None,
            "lit_episode_dur_med": med(A["episode_dur_literal"]), "lit_episode_dur_p90": pct(A["episode_dur_literal"], 90),
            "lit_episode_dur_max": max(A["episode_dur_literal"]) if A["episode_dur_literal"] else None,
            "lit_epstart_to_task_med": med([tk["t_task"] - tk["first_ep_start"] for tk in done if tk["first_ep_start"]]),
            "lit_epstart_to_task_p90": pct([tk["t_task"] - tk["first_ep_start"] for tk in done if tk["first_ep_start"]], 90),
            "lit_epend_to_judge_med": med([tk["t_judge"] - tk["last_ep_end"] for tk in done if tk["last_ep_end"] and tk["t_judge"]]),
            "lit_retrieve_to_epstart_med": med([tk["first_ep_start"] - tk["t_retrieve"] for tk in done if tk["t_retrieve"] and tk["first_ep_start"]]),
            "lit_retrieve_to_epstart_p90": pct([tk["first_ep_start"] - tk["t_retrieve"] for tk in done if tk["t_retrieve"] and tk["first_ep_start"]], 90),
            # reliability
            "n_rollouts": A["n_rollouts"], "n_steps_total": A["n_steps_total"],
            "n_max_steps": A["n_max_steps"], "n_ge_max": A["n_ge_max"], "max_steps_seen": A["max_steps_seen"],
            "n_action_errors": A["n_action_errors"], "rollouts_with_action_err": A["rollouts_with_action_err"],
            "steps_with_action_err": A["steps_with_action_err"],
            "n_episode_error": A["n_episode_error"], "err_reasons": dict(A["err_reasons"].most_common()),
            "err_steps_mean": float(np.mean(A["err_steps"])) if A["err_steps"] else None,
            "n_dropped_events": A["n_dropped_events"], "n_dropped_rollouts": A["n_dropped_rollouts"],
            "n_all_failed": A["n_all_failed"], "n_host_guard": A["n_host_guard"], "n_task_error": A["n_task_error"],
            "retrieve_n": A["retrieve_n"], "retrieve_hit": A["retrieve_hit"],
            "mem_chars_mean_when_hit": float(np.mean([c for c in A["mem_chars"] if c > 0])) if any(c > 0 for c in A["mem_chars"]) else None,
        }
        # write-pipeline latency restricted to tasks that actually wrote something
        wrote = [tk for tk in done if tk["t_judge"] and (tk["t_l1"] or tk["t_l2"])]
        res["judge_to_task_med_when_write"] = med([tk["t_task"] - tk["t_judge"] for tk in wrote])
        res["judge_to_task_p90_when_write"] = pct([tk["t_task"] - tk["t_judge"] for tk in wrote], 90)
        res["judge_to_task_mean_when_write"] = float(np.mean([tk["t_task"] - tk["t_judge"] for tk in wrote])) if wrote else None
        res["n_tasks_wrote"] = len(wrote)
        # outliers: any single phase > 1800 s (rollout_timeout) or cycle > 1800 s
        res["outliers"] = [
            {"task_id": tk["task_id"], "cycle": tk["cycle"], "retrieve": tk.get("retrieve_secs"),
             "rollout": tk.get("rollout_secs"), "judge": tk.get("judge_secs"), "tail": tk.get("tail_secs"),
             "n_l1": len(tk["t_l1"]), "l2": bool(tk["t_l2"]), "max_steps": max(tk["n_steps"]) if tk["n_steps"] else None,
             "n_err": tk["n_err"], "end": tk["end_kind"]}
            for tk in T if tk["cycle"] > 1800]
        # robust variants with cycles > 1800 s removed (stalls / hung batches)
        ok_t = [tk for tk in done if tk["cycle"] <= 1800]
        excl = sum(tk["cycle"] for tk in done if tk["cycle"] > 1800)
        res["cycle_mean_ex1800"] = float(np.mean([tk["cycle"] for tk in ok_t])) if ok_t else None
        res["arm_wall_strict_h_ex_outliers"] = strict_h - excl / 3600
        res["tasks_per_hour_ex_outliers"] = len(done) / (strict_h - excl / 3600)
        res["outlier_excluded_s"] = excl
        res["task_records"] = [
            {"task_id": tk["task_id"], "cycle": round(tk["cycle"], 3), "retrieve": tk.get("retrieve_secs"),
             "rollout": tk.get("rollout_secs"), "judge": tk.get("judge_secs"), "tail": tk.get("tail_secs"),
             "n_l1": len(tk["t_l1"]), "l2": bool(tk["t_l2"]), "n_steps": tk["n_steps"], "n_err": tk["n_err"],
             "end": tk["end_kind"], "t_begin": tk["t_begin"], "t_end": tk["t_end"]}
            for tk in T]
        out["arms"][arm] = res
    out["summary"] = summary
    # launch log: cumulative spend per arm + reliability warnings
    log = ROOT / "runs" / (cfg["run"]["name"] + ".log")
    L = {"exists": log.exists()}
    if log.exists():
        txt = log.read_text(errors="replace")
        spent = {}
        for arm in ARMS:
            m = re.findall(rf"\[info\] \[{arm}\] (\d+)/(\d+) t\d+ .*?spent=\$([\d.]+)", txt)
            if m:
                spent[arm] = {"last_spent_cum": float(m[-1][2]), "n_lines": len(m), "last_idx": int(m[-1][0])}
        L["spent"] = spent
        if "nomem" in spent and "withmem" in spent:
            L["arm_spend_usd"] = {"nomem": spent["nomem"]["last_spent_cum"],
                                  "withmem": spent["withmem"]["last_spent_cum"] - spent["nomem"]["last_spent_cum"]}
        L["warn_lines"] = len(re.findall(r"^\[warn\]", txt, re.M))
        L["stall_lines"] = len(re.findall(r"^\[stall\]", txt, re.M))
        L["worker_deadline_lines"] = len(re.findall(r"^\[worker\] episode deadline", txt, re.M))
        for arm in ARMS:
            L[f"{arm}_hung"] = len(re.findall(rf"^\[warn\] \[{arm}\] pool \d+ .* HUNG", txt, re.M))
            L[f"{arm}_broke"] = len(re.findall(rf"^\[warn\] \[{arm}\] pool \d+ .* broke on", txt, re.M))
            L[f"{arm}_failed_twice"] = len(re.findall(rf"^\[warn\] \[{arm}\] pool \d+ failed twice", txt, re.M))
    out["log"] = L
    return out


def main():
    results = [analyze_run(ROOT / r) for r in RUNS]
    json.dump(results, open(ROOT / "runs" / "wa_timing_efficiency.json", "w"), indent=1, default=str)

    rows = []
    def R(*cells):
        rows.append("| " + " | ".join(str(c) for c in cells) + " |")

    print("\n### T1. Arm wall clock, throughput, spend\n")
    R("site", "arm", "tasks", "arm wall strict (h)", "arm wall incl. setup gap (h)", "tasks/h (strict)", "arm wall ex. stalls>1800s (h)", "tasks/h ex. stalls", "task cycle median (s)", "task cycle p90 (s)", "task cycle mean (s)", "task cycle mean ex. stalls (s)", "task cycle max (s)", "resets (n, total s)", "arm spend from log ($)")
    R(*["---"] * 15)
    for r in results:
        for arm, a in r["arms"].items():
            sp = r["log"].get("arm_spend_usd", {}).get(arm)
            R(r["site"], arm, a["n_tasks"], fmt(a["arm_wall_strict_h"], 2), fmt(a["arm_wall_incl_setup_h"], 2), fmt(a["tasks_per_hour_strict"], 1),
              fmt(a["arm_wall_strict_h_ex_outliers"], 2), fmt(a["tasks_per_hour_ex_outliers"], 1),
              fmt(a["cycle_med"]), fmt(a["cycle_p90"]), fmt(a["cycle_mean"]), fmt(a["cycle_mean_ex1800"]), fmt(a["cycle_max"], 0),
              f"{a['n_reset']}, {a['reset_total_s']:.0f}", fmt(sp, 2) if sp is not None else "n/a")
    print("\n".join(rows)); rows.clear()

    print("\n### T2. Share of arm wall clock by phase (seconds and % of arm wall incl. setup gap)\n")
    R("site", "arm", "rollouts", "judging", "writing (L1+L2 incl. no-op tail)", "retrieve+gate", "resets", "other (setup gap + misc)", "sum (h)")
    R(*["---"] * 9)
    for r in results:
        for arm, a in r["arms"].items():
            ph, sh = a["phase_secs"], a["phase_share"]
            def cell(k):
                return f"{ph.get(k, 0):.0f} s ({100 * sh.get(k, 0):.1f}%)"
            other = ph.get("other", 0) + ph.get("other_setup", 0)
            other_sh = sh.get("other", 0) + sh.get("other_setup", 0)
            R(r["site"], arm, cell("rollout"), cell("judge"), cell("write"), cell("retrieve"), cell("reset"), f"{other:.0f} s ({100 * other_sh:.1f}%)", fmt(a["phase_total_secs"] / 3600, 2))
    print("\n".join(rows)); rows.clear()

    print("\n### T3. Real per-task phase latencies (boundary-based, seconds)\n")
    R("site", "arm", "retrieve+gate med/p90", "rollout batch (8 parallel) med/p90", "rollout batch max", "judge (8 verdicts) med/p90", "judge per verdict med", "judge->wa_task med/p90 all tasks (write pipeline)", "judge->wa_task med/p90/mean, tasks that wrote (n)", "judge->first L1 med", "judge->L2 med/p90", "L1 item gap med/p90", "sec/step critical-path med/p90", "sec/step (batch/mean steps) med")
    R(*["---"] * 14)
    for r in results:
        for arm, a in r["arms"].items():
            R(r["site"], arm,
              f"{fmt(a['retrieve_med'])}/{fmt(a['retrieve_p90'])}" if arm == "withmem" else "-",
              f"{fmt(a['rollout_med'], 0)}/{fmt(a['rollout_p90'], 0)}", fmt(a["rollout_max"], 0),
              f"{fmt(a['judge_med'])}/{fmt(a['judge_p90'])}", fmt(a["judge_per_rollout_med"]),
              f"{fmt(a['judge_to_task_med'])}/{fmt(a['judge_to_task_p90'])}",
              f"{fmt(a['judge_to_task_med_when_write'])}/{fmt(a['judge_to_task_p90_when_write'])}/{fmt(a['judge_to_task_mean_when_write'])} ({a['n_tasks_wrote']})" if arm == "withmem" else "-",
              fmt(a["judge_to_first_l1_med"]), f"{fmt(a['judge_to_l2_med'])}/{fmt(a['judge_to_l2_p90'])}",
              f"{fmt(a['l1_item_gap_med'])}/{fmt(a['l1_item_gap_p90'])}",
              f"{fmt(a['sec_per_step_crit_med'])}/{fmt(a['sec_per_step_crit_p90'])}", fmt(a["sec_per_step_mean_med"]))
    print("\n".join(rows)); rows.clear()

    print("\n### T4. Literal event-delta metrics as requested (show the replay-stamping artifact)\n")
    R("site", "arm", "wa_step consecutive delta med/p90/max (s)", "episode_start->episode_end med/p90/max (s)", "first episode_start->wa_task med/p90 (s)", "last episode_end->first wa_judge med (s)", "wa_retrieve->first episode_start med/p90 (s)")
    R(*["---"] * 7)
    for r in results:
        for arm, a in r["arms"].items():
            R(r["site"], arm, f"{fmt(a['lit_step_delta_med'], 4)}/{fmt(a['lit_step_delta_p90'], 4)}/{fmt(a['lit_step_delta_max'], 3)}",
              f"{fmt(a['lit_episode_dur_med'], 4)}/{fmt(a['lit_episode_dur_p90'], 4)}/{fmt(a['lit_episode_dur_max'], 3)}",
              f"{fmt(a['lit_epstart_to_task_med'])}/{fmt(a['lit_epstart_to_task_p90'])}", fmt(a["lit_epend_to_judge_med"]),
              f"{fmt(a['lit_retrieve_to_epstart_med'])}/{fmt(a['lit_retrieve_to_epstart_p90'])}" if arm == "withmem" else "-")
    print("\n".join(rows)); rows.clear()

    print("\n### T5. Steps and reliability counters\n")
    R("site", "arm", "rollouts (episode_end)", "steps total", "mean steps/rollout", "steps/task (sum of 8) mean", "rollouts n_steps==30", "max n_steps seen", "n_action_errors sum", "rollouts w/ >=1 action err", "wa_episode_error", "rollouts dropped (n_err)", "tasks all-failed", "host_guard", "rollout batches >=900 s / >=1800 s", "L1 / L2 writes", "retrieve hits / n")
    R(*["---"] * 17)
    for r in results:
        for arm, a in r["arms"].items():
            R(r["site"], arm, a["n_rollouts"], a["n_steps_total"], fmt(a["mean_nsteps_per_rollout"], 2), fmt(a["steps_per_task_mean"], 1), a["n_max_steps"], a["max_steps_seen"],
              a["n_action_errors"], a["rollouts_with_action_err"], a["n_episode_error"], a["n_dropped_rollouts"], a["n_all_failed"], a["n_host_guard"],
              f"{a['rollout_ge_900']} / {a['rollout_ge_1800']}", f"{a['n_l1']} / {a['n_l2']}", f"{a['retrieve_hit']} / {a['retrieve_n']}" if arm == "withmem" else "-")
    print("\n".join(rows)); rows.clear()

    print("\n### T6. wa_episode_error reasons (normalized; numbers->N, urls->URL)\n")
    R("site", "arm", "count", "reason class")
    R(*["---"] * 4)
    for r in results:
        for arm, a in r["arms"].items():
            for reason, n in a["err_reasons"].items():
                R(r["site"], arm, n, reason.replace("|", "/"))
    print("\n".join(rows)); rows.clear()

    print("\n### T7. Launch-log reliability lines and run-level facts\n")
    R("site", "run wall (h)", "events monotonic", "log warn lines", "stall lines", "worker deadline kills", "nomem hung/broke/failed-twice", "withmem hung/broke/failed-twice", "summary spent_usd", "log spend nomem / withmem")
    R(*["---"] * 10)
    for r in results:
        L = r["log"]
        sp = L.get("arm_spend_usd", {})
        R(r["site"], fmt(r["run_wall_h"], 2), r["monotonic"], L.get("warn_lines"), L.get("stall_lines"), L.get("worker_deadline_lines"),
          f"{L.get('nomem_hung')}/{L.get('nomem_broke')}/{L.get('nomem_failed_twice')}", f"{L.get('withmem_hung')}/{L.get('withmem_broke')}/{L.get('withmem_failed_twice')}",
          r["summary"].get("spent_usd"), f"{fmt(sp.get('nomem'), 2)} / {fmt(sp.get('withmem'), 2)}")
    print("\n".join(rows)); rows.clear()

    print("\n### T9. Outlier tasks (cycle > 1800 s = rollout_timeout), seconds\n")
    R("site", "arm", "task_id", "cycle", "retrieve+gate", "rollout batch", "judge", "tail after last judge/write", "n_l1", "l2", "max n_steps", "n episode_error", "end")
    R(*["---"] * 13)
    for r in results:
        for arm, a in r["arms"].items():
            for o in a["outliers"]:
                R(r["site"], arm, o["task_id"], fmt(o["cycle"], 0), fmt(o["retrieve"]), fmt(o["rollout"], 0), fmt(o["judge"]), fmt(o["tail"]), o["n_l1"], o["l2"], o["max_steps"], o["n_err"], o["end"])
    print("\n".join(rows)); rows.clear()

    # pooled across sites
    print("\n### T8. Pooled over the five sites (task-weighted)\n")
    R("arm", "tasks", "arm wall strict sum (h)", "tasks/h pooled", "rollouts (s, %)", "judging (s, %)", "writing (s, %)", "retrieve (s, %)", "resets (s, %)", "other (s, %)")
    R(*["---"] * 10)
    for arm in ARMS:
        tot = collections.Counter(); n = 0; wall = 0.0; incl = 0.0
        for r in results:
            a = r["arms"][arm]; n += a["n_tasks"]; wall += a["arm_wall_strict_h"]; incl += a["arm_wall_incl_setup_h"]
            for k, v in a["phase_secs"].items():
                tot[k] += v
        base = incl * 3600
        def c(k):
            return f"{tot[k]:.0f} ({100 * tot[k] / base:.1f}%)"
        R(arm, n, fmt(wall, 2), fmt(n / wall, 1), c("rollout"), c("judge"), c("write"), c("retrieve"), c("reset"), f"{tot['other'] + tot['other_setup']:.0f} ({100 * (tot['other'] + tot['other_setup']) / base:.1f}%)")
    print("\n".join(rows)); rows.clear()


if __name__ == "__main__":
    main()
