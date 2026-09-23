"""Judge stability: re-judge the SAME input 5x per judge model and report label agreement.
Uses the original judge prompt/config (WaBrain.judge_trajectory, temperature 0). Picks 10 samples per site from
judge_audit/sample_200.jsonl (5 judge-fluke + 5 judge-genuine). LIMITATION: fleet runs did not persist the full
compact_trace (page text); the trace is rebuilt from the logged steps (thought/action/url) + final answer, so this
measures stability of the judge on a REDUCED trace. Needs the LLM gateway (VPN).
  python scripts/judge_stability_test.py --models gpt-5.6-sol,gpt-4o-mini --repeats 5"""
import json, sys, argparse, collections, random
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv('.env')
from hippo.llm import LLMClient; from hippo.wa.brain import WaBrain
ap = argparse.ArgumentParser(); ap.add_argument('--models', default='gpt-5.6-sol'); ap.add_argument('--repeats', type=int, default=5); ap.add_argument('--per_site', type=int, default=10); a = ap.parse_args()
S = [json.loads(l) for l in open('judge_audit/sample_200.jsonl')]; rng = random.Random(1); pick = []
for site in sorted({s['site'] for s in S}):
    for o in ('fluke', 'genuine'):
        pool = [s for s in S if s['site'] == site and s['judge_outcome'] == o]; pick += rng.sample(pool, min(a.per_site // 2, len(pool)))
def trace(s): return "\n".join(f"step {x['step']}: {x['thought']}\n  action: {x['action']}\n  url: {x['url']}" for x in s['steps'])
out = {}
for m in a.models.split(','):
    brain = WaBrain(LLMClient(model=m, embed_model='local/BAAI/bge-small-en-v1.5', cache=False)); res = []
    for s in pick:
        labels = [brain.judge_trajectory(s['intent'], trace(s), s['final_answer'], 1, s['reference'])['outcome'] for _ in range(a.repeats)]
        maj = collections.Counter(labels).most_common(1)[0]; res.append(dict(sample_id=s['sample_id'], site=s['site'], original=s['judge_outcome'], labels=labels, unanimous=len(set(labels)) == 1, majority=maj[0], majority_share=maj[1] / a.repeats, matches_original=maj[0] == s['judge_outcome']))
    out[m] = res
    print(f"\n{m}: n={len(res)} 五次全一致 {sum(r['unanimous'] for r in res)}/{len(res)}; 多数票与原标签一致 {sum(r['matches_original'] for r in res)}/{len(res)}; 平均多数票占比 {sum(r['majority_share'] for r in res)/len(res):.2f}")
    for site in sorted({r['site'] for r in res}):
        rs = [r for r in res if r['site'] == site]; print(f"  {site}: 全一致 {sum(r['unanimous'] for r in rs)}/{len(rs)}, 与原标签一致 {sum(r['matches_original'] for r in rs)}/{len(rs)}")
json.dump(out, open('judge_audit/stability_results.json', 'w'), ensure_ascii=False, indent=1)
