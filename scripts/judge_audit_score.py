"""Score the human audit against the judge. Reads judge_audit/打分表_A.csv and 打分表_B.csv (判断 = 正常/蒙对/不确定)
and judge_audit/answer_key.csv. Reports per site and pooled: n, judge-flagged flukes,
human flukes, precision/recall of judge fluke detection (human = ground truth), A/B agreement, Cohen's kappa.
Human label = A when A==B; disagreements and 'unsure' are excluded from precision/recall and counted separately."""
import csv, json, collections
key = {r['sample_id']: r for r in csv.DictReader(open('judge_audit/answer_key.csv'))}
site_of = {json.loads(l)['sample_id']: json.loads(l)['site'] for l in open('judge_audit/sample_200.jsonl')}
A = {r['编号']: r for r in csv.DictReader(open('judge_audit/打分表_A.csv'))}; B = {r['编号']: r for r in csv.DictReader(open('judge_audit/打分表_B.csv'))}
rows = [dict(sample_id=k, site=site_of[k], A_label=A[k]['判断（正常/蒙对/不确定）'], B_label=B.get(k, {}).get('判断（正常/蒙对/不确定）', '')) for k in A]
def norm(x): x = (x or '').strip().lower(); return {'正常': 'genuine', '正常成功': 'genuine', '蒙对': 'fluke', '不确定': 'unsure', '无法判断': 'unsure'}.get(x, x)
def kappa(a, b):
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n; ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n / n; return (po - pe) / (1 - pe) if pe < 1 else 1.0
print("| 站 | 标注样本 | A/B 一致 | κ | 无法判断/分歧（剔除） | judge 判蒙对 | 人判蒙对 | 都判蒙对 | precision | recall |\n|---|---|---|---|---|---|---|---|---|---|")
groups = collections.defaultdict(list); [groups[r['site']].append(r) for r in rows]; groups['合计'] = rows
for site, rs in groups.items():
    lab = [(norm(r['A_label']), norm(r['B_label']), key[r['sample_id']]['judge_outcome']) for r in rs if r['A_label'] and r['B_label']]
    if not lab: print(f"| {site} | 0 | — | — | — | — | — | — | — | — |"); continue
    agree = sum(a == b for a, b, _ in lab); k = kappa([a for a, _, _ in lab], [b for _, b, _ in lab])
    valid = [(a, j) for a, b, j in lab if a == b and a in ('genuine', 'fluke')]; excl = len(lab) - len(valid)
    jf = sum(j == 'fluke' for _, j in valid); hf = sum(a == 'fluke' for a, _ in valid); both = sum(a == 'fluke' and j == 'fluke' for a, j in valid)
    prec = both / jf if jf else float('nan'); rec = both / hf if hf else float('nan')
    print(f"| {site} | {len(lab)} | {agree}/{len(lab)} | {k:.2f} | {excl} | {jf} | {hf} | {both} | {prec:.2f} | {rec:.2f} |")
