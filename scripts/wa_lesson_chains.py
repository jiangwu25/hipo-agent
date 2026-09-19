"""Print the full provenance chain for target tasks: injected lesson -> source task (and its L1/L2), intents,
reference answers, both arms' nc/n, and judge reasons (nomem failures, withmem genuine). Usage:
  python scripts/wa_lesson_chains.py shopping 160 161 273"""
import json, sys, collections, glob
META = {t['task_id']: t for t in json.load(open('.venv-wa/lib/python3.11/site-packages/webarena/test.raw.json'))}
RUNS = {'shopping': 'runs/wa_fleet_shopping_all_20260811_191401_20260811_191415', 'shopping_admin': 'runs/wa_fleet_shopping_admin_all_20260818_005633_20260818_005647',
        'gitlab': 'runs/wa_fleet_gitlab_all_20260815_172053_20260815_172110', 'reddit': 'runs/wa_fleet_reddit_all_20260814_002621_20260814_002652', 'map': 'runs/wa_fleet_map_readonly_20260813_103741_20260813_103743'}
def chain(site, targets, nreasons=1, maxlen=320):
    run = RUNS[site]; T = {}; W = {}; J = collections.defaultdict(list); L1 = collections.defaultdict(list)
    for l in open(run + '/events.jsonl'):
        e = json.loads(l); k = e.get('kind')
        if k == 'wa_task': T[(e['tag'], e['task_id'])] = e
        elif k == 'wa_write_l2': W[e['item']['title']] = (e['task'], e.get('nc'), e.get('n'))
        elif k == 'wa_write_l1': L1[e['task']].append(e['item']['title'])
        elif k == 'wa_judge': J[(e['tag'], e['task_id'])].append(e)
    mem = {it['title']: it for it in json.load(open(run + '/memory.json'))['reasoning']}
    ref = lambda t: str(META[t]['eval'].get('reference_answers'))[:90]
    for tg in targets:
        wm = T.get(('withmem', tg)); nm = T.get(('nomem', tg))
        title = (wm.get('ret_titles') or [None])[0]
        src, nc, n = W.get(title, (None, None, None))
        print(f"\n### {site} t{tg} (tpl {META[tg]['intent_template_id']}): {META[tg]['intent']}  | ref: {ref(tg)}")
        print(f"nomem {nm['nc']}/{nm['n']}  withmem {wm['nc']}/{wm['n']}  injected: {title!r}")
        if src is not None:
            it = mem.get(title, {}); s = T.get(('withmem', src)); sn = T.get(('nomem', src))
            print(f"SOURCE t{src} (tpl {META[src]['intent_template_id']}, L2 regime nc={nc}/{n}, L1 written={len(L1[src])}): {META[src]['intent']} | ref: {ref(src)} | nomem {sn['nc']}/{sn['n']} withmem {s['nc']}/{s['n']}")
            print(f"  L2.description: {it.get('description','')}\n  L2.content: {it.get('content','')}")
        for tag, want in (('nomem', 'failure'), ('withmem', 'genuine')):
            rs = [j['reason'] for j in J[(tag, tg)] if j['outcome'] == want][:nreasons]
            for r in rs: print(f"  [{tag} {want}] {r[:maxlen]}")
if __name__ == '__main__':
    site = sys.argv[1]; chain(site, [int(x) for x in sys.argv[2:]])
