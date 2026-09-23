"""Build the human-audit sample for 'Is the surprise judge reliable?'.
Population: every rollout the OFFICIAL grader marked correct (reward=1) in the five full-set paired runs,
both arms. Stratified sample per site: 20 rollouts the judge called FLUKE + 20 it called GENUINE (seed 0).
Outputs (judge_audit/): sample_200.jsonl (full record incl. steps), annotation_sheet.csv (judge label HIDDEN),
answer_key.csv (judge label + reason), sampling_table.md."""
import json, csv, random, collections
META = {t['task_id']: t for t in json.load(open('.venv-wa/lib/python3.11/site-packages/webarena/test.raw.json'))}
RUNS = {'shopping': 'runs/wa_fleet_shopping_all_20260811_191401_20260811_191415', 'shopping_admin': 'runs/wa_fleet_shopping_admin_all_20260818_005633_20260818_005647',
        'gitlab': 'runs/wa_fleet_gitlab_all_20260815_172053_20260815_172110', 'reddit': 'runs/wa_fleet_reddit_all_20260814_002621_20260814_002652', 'map': 'runs/wa_fleet_map_readonly_20260813_103741_20260813_103743'}
PER = 20; rng = random.Random(0)
sample = []; table = []
for site, run in RUNS.items():
    J = {}; steps = collections.defaultdict(list); end = {}
    for l in open(run + '/events.jsonl'):
        e = json.loads(l); k = e.get('kind')
        if k == 'wa_judge': J[(e['tag'], e['task_id'], e['rollout'])] = e
        elif k == 'wa_step': steps[(e['tag'], e['task_id'], e['rollout'])].append(e)
        elif k == 'wa_episode_end': end[(e['tag'], e['task_id'], e['rollout'])] = e
    pop = {o: [k for k, v in J.items() if v['reward'] == 1 and v['outcome'] == o] for o in ('fluke', 'genuine')}
    pick = {o: rng.sample(pop[o], min(PER, len(pop[o]))) for o in pop}
    table.append((site, len(pop['genuine']), len(pop['fluke']), len(pick['genuine']), len(pick['fluke'])))
    for o in ('fluke', 'genuine'):
        for key in pick[o]:
            tag, tid, r = key; j = J[key]; en = end.get(key, {}); st = sorted(steps[key], key=lambda x: x['step'])
            sample.append(dict(sample_id=f"{site[:2]}-{tid}-{tag[0]}{r}", site=site, run=run.split('/')[1], arm=tag, task_id=tid, rollout=r, template_id=META[tid]['intent_template_id'],
                               intent=META[tid]['intent'], reference=META[tid]['eval'].get('reference_answers'), eval_types=META[tid]['eval']['eval_types'], official_reward=1,
                               final_answer=en.get('stop_answer', ''), n_steps=en.get('n_steps', len(st)),
                               steps=[dict(step=s['step'], url=s.get('url', ''), thought=s.get('thought', ''), action=s.get('action', '')) for s in st],
                               judge_outcome=j['outcome'], judge_reason=j.get('reason', '')))
rng.shuffle(sample)
with open('judge_audit/sample_200.jsonl', 'w') as f:
    for s in sample: f.write(json.dumps(s, ensure_ascii=False) + '\n')
def steps_text(s): return " || ".join(f"[{x['step']}] {x['thought']} -> {x['action']} @ {x['url'].split('//')[-1][:60]}" for x in s['steps'])
with open('judge_audit/annotation_sheet.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['sample_id', 'site', 'task', 'eval_type', 'text_answer_required', 'reference_answer', 'official_grader', 'agent_final_answer', 'n_steps', 'trajectory (step] thought -> action @ url)', 'A_label', 'A_evidence', 'B_label', 'B_evidence'])
    for s in sample: w.writerow([s['sample_id'], s['site'], s['intent'], '+'.join(s['eval_types']), 'yes' if 'string_match' in s['eval_types'] else 'no (state-changing / URL task)', json.dumps(s['reference'], ensure_ascii=False), 'CORRECT', s['final_answer'] or '(no answer given)', s['n_steps'], steps_text(s), '', '', '', ''])
with open('judge_audit/answer_key.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['sample_id', 'judge_outcome', 'judge_reason']); [w.writerow([s['sample_id'], s['judge_outcome'], s['judge_reason']]) for s in sample]
with open('judge_audit/sampling_table.md', 'w') as f:
    f.write("| 站 | 官方判对的 rollout 里 judge=genuine | judge=fluke | 抽样 genuine | 抽样 fluke |\n|---|---|---|---|---|\n")
    for r in table: f.write(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |\n")
    f.write(f"| 合计 | {sum(r[1] for r in table)} | {sum(r[2] for r in table)} | {sum(r[3] for r in table)} | {sum(r[4] for r in table)} |\n")
print(open('judge_audit/sampling_table.md').read()); print("sample size", len(sample), "; steps per sample median", sorted(len(s['steps']) for s in sample)[len(sample)//2])
