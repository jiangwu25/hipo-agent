"""Task counts and learnability statistics behind COVERAGE_AND_LEARNABILITY.md.
Template structure from webarena test.raw.json; per-site cold-start / sibling-availability / injection
outcomes from the five full-set paired runs plus runs/retrieval_suite_wa.json (GT-A/GT-B labels)."""
import json, collections, glob, os, numpy as np
META = json.load(open('.venv-wa/lib/python3.11/site-packages/webarena/test.raw.json'))
by_site = collections.defaultdict(list)
for t in META: by_site[t['sites'][0] if len(t['sites']) == 1 else 'cross-site'].append(t)
print("| 站 | 题数 | 模板数 | 单例模板 | 模板大小分布 |\n|---|---|---|---|---|")
for s, ts in by_site.items():
    c = collections.Counter(t['intent_template_id'] for t in ts)
    print(f"| {s} | {len(ts)} | {len(c)} | {sum(1 for v in c.values() if v == 1)} | {dict(sorted(collections.Counter(c.values()).items()))} |")
RUNS = {'shopping': 'runs/wa_fleet_shopping_all_20260811_191401_20260811_191415', 'shopping_admin': 'runs/wa_fleet_shopping_admin_all_20260818_005633_20260818_005647',
        'gitlab': 'runs/wa_fleet_gitlab_all_20260815_172053_20260815_172110', 'reddit': 'runs/wa_fleet_reddit_all_20260814_002621_20260814_002652', 'map': 'runs/wa_fleet_map_readonly_20260813_103741_20260813_103743'}
suite = {(r['site'], r['task']): r for r in json.load(open('runs/retrieval_suite_wa.json'))}
print("\n| 站 | 配对题 | 冷启动 | 库里已有同模板L2 | 注入 | 注入同模板 | 同模板+来源成功 | Δ 同模板+来源成功 | Δ 其他注入 | Δ 未注入 |\n|---|---|---|---|---|---|---|---|---|---|")
for s, run in RUNS.items():
    T = {}; order = []
    for l in open(run + '/events.jsonl'):
        e = json.loads(l)
        if e.get('kind') == 'wa_task':
            T[(e['tag'], e['task_id'])] = e
            if e['tag'] == 'withmem': order.append(e)
    order.sort(key=lambda e: e['t']); seen = set(); c = collections.Counter(); d = {'B': [], 'other': [], 'none': []}
    for e in order:
        nm = T.get(('nomem', e['task_id']))
        if not nm or not e['n'] or not nm['n']: continue
        c['n'] += 1
        if e['template_id'] not in seen: c['first'] += 1; seen.add(e['template_id'])
        r = suite.get((s, e['task_id'])); delta = 100 * (e['nc'] / e['n'] - nm['nc'] / nm['n'])
        if r and r['relA']: c['avail'] += 1
        sel = r['sel']['ours(as-run)'] if r else (e.get('ret_titles') or [None])[0]
        if sel:
            c['inj'] += 1
            if r and sel in r['relA']: c['injA'] += 1
            if r and sel in r['relB']: c['injB'] += 1; d['B'].append(delta)
            else: d['other'].append(delta)
        else: d['none'].append(delta)
    m = lambda x: f"{np.mean(x):+.1f} (n={len(x)})" if x else "—"
    print(f"| {s} | {c['n']} | {c['first']} | {c['avail']} | {c['inj']} | {c['injA']} | {c['injB']} | {m(d['B'])} | {m(d['other'])} | {m(d['none'])} |")
print("\n| run | nomem | withmem | 配对 |\n|---|---|---|---|")
for run in sorted(glob.glob('runs/wa_fleet_*_2026*')):
    if not os.path.isdir(run): continue
    c = collections.Counter(); ids = collections.defaultdict(set)
    for l in open(run + '/events.jsonl'):
        if '"wa_task"' in l:
            e = json.loads(l); c[e['tag']] += 1; ids[e['tag']].add(e['task_id'])
    print(f"| {os.path.basename(run)} | {c['nomem']} | {c['withmem']} | {len(ids['nomem'] & ids['withmem'])} |")
