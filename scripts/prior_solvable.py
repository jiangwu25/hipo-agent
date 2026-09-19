"""Per site: which tasks had a usable prior (a same-template lesson from a source with >=1 genuine success,
GT-B) in the bank at retrieval time, which of them the gate actually injected, and what happened
(flip to majority-correct, flip to majority-wrong, rollout-level gain). Writes runs/prior_solvable.json."""
import json, collections, numpy as np
RUNS = {'shopping': 'runs/wa_fleet_shopping_all_20260811_191401_20260811_191415', 'shopping_admin': 'runs/wa_fleet_shopping_admin_all_20260818_005633_20260818_005647',
        'gitlab': 'runs/wa_fleet_gitlab_all_20260815_172053_20260815_172110', 'reddit': 'runs/wa_fleet_reddit_all_20260814_002621_20260814_002652', 'map': 'runs/wa_fleet_map_readonly_20260813_103741_20260813_103743'}
suite = {(r['site'], r['task']): r for r in json.load(open('runs/retrieval_suite_wa.json'))}
OUT = {}
print("| 站 | 配对题 | 有先验可用（GT-B） | 其中门控注入了先验 | 翻好（多数错→多数对） | 翻坏 | Δ>0 / =0 / <0 | 多出的正确 rollout | 翻好率 |\n|---|---|---|---|---|---|---|---|---|")
for s, run in RUNS.items():
    T = {}
    for l in open(run + '/events.jsonl'):
        e = json.loads(l)
        if e.get('kind') == 'wa_task': T[(e['tag'], e['task_id'])] = e
    rows = []
    for (tag, tid), e in T.items():
        if tag != 'withmem' or ('nomem', tid) not in T: continue
        nm = T[('nomem', tid)]
        if not e['n'] or not nm['n']: continue
        r = suite.get((s, tid)); relB = set(r['relB']) if r else set(); relA = set(r['relA']) if r else set()
        sel = (e.get('ret_titles') or [None])[0]
        rows.append(dict(task=tid, tpl=e['template_id'], nomem=nm['nc'] / nm['n'], withmem=e['nc'] / e['n'], nc_nm=nm['nc'], nc_wm=e['nc'], n_nm=nm['n'], n_wm=e['n'],
                         priorB=bool(relB), priorA=bool(relA), injected=sel is not None, injB=bool(sel and sel in relB), injA=bool(sel and sel in relA), lesson=sel))
    pri = [x for x in rows if x['priorB']]; inj = [x for x in pri if x['injB']]
    good = [x for x in inj if x['nomem'] < 0.5 <= x['withmem']]; bad = [x for x in inj if x['withmem'] < 0.5 <= x['nomem']]
    up = sum(1 for x in inj if x['withmem'] > x['nomem']); same = sum(1 for x in inj if x['withmem'] == x['nomem']); down = sum(1 for x in inj if x['withmem'] < x['nomem'])
    gain = sum(round(8 * (x['withmem'] - x['nomem'])) for x in inj)
    OUT[s] = dict(n=len(rows), prior_ids=sorted(x['task'] for x in pri), injected_ids=sorted(x['task'] for x in inj), good_ids=sorted(x['task'] for x in good), bad_ids=sorted(x['task'] for x in bad),
                  up=up, same=same, down=down, rollout_gain=int(gain), rows=rows)
    print(f"| {s} | {len(rows)} | {len(pri)} | {len(inj)} | {len(good)} | {len(bad)} | {up} / {same} / {down} | {gain:+d} | {len(good)}/{len(inj)} = {len(good)/max(len(inj),1):.0%} |")
tot = lambda k: sum(len(OUT[s][k]) for s in OUT)
print(f"| 合计 | {sum(OUT[s]['n'] for s in OUT)} | {tot('prior_ids')} | {tot('injected_ids')} | {tot('good_ids')} | {tot('bad_ids')} | {sum(OUT[s]['up'] for s in OUT)} / {sum(OUT[s]['same'] for s in OUT)} / {sum(OUT[s]['down'] for s in OUT)} | {sum(OUT[s]['rollout_gain'] for s in OUT):+d} | {tot('good_ids')}/{tot('injected_ids')} = {tot('good_ids')/tot('injected_ids'):.0%} |")
print("\n## 题号")
for s in OUT:
    print(f"\n**{s}** 有先验可用（{len(OUT[s]['prior_ids'])}）：", ", ".join(map(str, OUT[s]['prior_ids'])))
    print(f"其中翻好（{len(OUT[s]['good_ids'])}）：", ", ".join(map(str, OUT[s]['good_ids'])) or "—", f"；翻坏（{len(OUT[s]['bad_ids'])}）：", ", ".join(map(str, OUT[s]['bad_ids'])) or "—")
json.dump(OUT, open('runs/prior_solvable.json', 'w'), ensure_ascii=False, default=float)
