"""Human-friendly grading booklet from judge_audit/sample_200.jsonl:
  judge_audit/打分册_<site>.md  — one card per rollout, five files (40 cards each), judge label hidden
  judge_audit/打分表_A.csv / 打分表_B.csv — one row per card, three columns to fill
"""
import json, csv, collections, re
S = [json.loads(l) for l in open('judge_audit/sample_200.jsonl')]
SITE_CN = {'shopping': '购物网站（顾客端）', 'shopping_admin': '购物后台（管理端）', 'gitlab': 'GitLab', 'reddit': '论坛（Reddit 克隆）', 'map': '地图'}
def act_cn(a):
    a = a.strip()
    m = re.match(r"send_msg_to_user\((.*)\)$", a, re.S)
    if m: return f"【作答】{m.group(1)[:300]}"
    if a.startswith('report_infeasible'): return "【声明任务无法完成】" + a[len('report_infeasible'):][:200]
    if a.startswith('click'): return "点击 " + a
    if a.startswith('fill'): return "输入 " + a
    if a.startswith('goto'): return "打开网址 " + a
    if a.startswith('select_option'): return "选择选项 " + a
    if a.startswith('scroll'): return "滚动 " + a
    if a.startswith('go_back'): return "返回上一页"
    if a.startswith('noop'): return "等待"
    return a
GUIDE = """# 打分册 · 判官可靠性审计（{site_cn}，{n} 条）

## 你要做的事

每张卡片是一次 **已经被官方判分器判"对"** 的做题过程。你不用管答案对不对（官方已经判对了），只判一件事：**这个"对"是真做出来的，还是蒙对的？**

三步判法：

1. 看"需要文字答案吗"。需要的，看 agent 最终答案；不需要的（改状态/跳转类任务），看它有没有真的做了那个操作。
2. 顺着步骤往下看：agent 有没有走到能证明答案的页面、读到那个值（或真的执行了要求的操作）？**有** → 填 `正常`。
3. **没有** → 填 `蒙对`，并在"依据"写清哪一步缺了什么。典型的蒙对：没作答就停了而参考答案恰好是 N/A；把一大段页面内容倒进答案里恰好包含正确值；没到相关页面就凭印象/默认值答对；要求的操作根本没做但状态碰巧符合。
4. 步骤信息不够、两种解释都说得通 → 填 `不确定`。

规则：不要和另一位标注者讨论；每张卡片必填；蒙对必须写依据。填在 `打分表_A.csv`（或 B）对应编号那一行的"判断"和"依据"两列，只写 `正常` / `蒙对` / `不确定` 三个词之一。

---
"""
by_site = collections.defaultdict(list)
for s in S: by_site[s['site']].append(s)
order = []
for site, items in by_site.items():
    items.sort(key=lambda s: s['sample_id']); out = [GUIDE.format(site_cn=SITE_CN[site], n=len(items))]
    for i, s in enumerate(items, 1):
        need = 'string_match' in s['eval_types']
        ref = s['reference']; ref_txt = json.dumps(ref, ensure_ascii=False) if ref else '（无文字答案；判分看网站状态或页面 URL）'
        ans = s['final_answer'] or '（没有作答）'
        out.append(f"## 卡片 {s['sample_id']}\n")
        out.append(f"**任务**：{s['intent']}\n")
        out.append(f"**需要文字答案吗**：{'需要' if need else '不需要（改状态或跳转类任务）'}　　**参考答案**：{ref_txt}\n")
        out.append(f"**官方判分**：对　　**agent 最终答案**：{ans}　　**步数**：{s['n_steps']}\n")
        out.append("**做题过程**（每步：它在想什么 → 它做了什么 → 所在页面）\n")
        for st in s['steps']:
            url = re.sub(r'^https?://[^/]+', '', st['url'] or '') or '/'
            out.append(f"{st['step']+1}. {st['thought'].strip() or '（无）'}\n   → {act_cn(st['action'])}\n   → 页面 `{url[:120]}`")
        out.append("\n**你的判断**：☐ 正常　☐ 蒙对　☐ 不确定　　**依据**：______________________\n\n---\n")
        order.append(s['sample_id'])
    open(f'judge_audit/打分册_{site}.md', 'w').write("\n".join(out))
for who in ('A', 'B'):
    with open(f'judge_audit/打分表_{who}.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['编号', '站点', '判断（正常/蒙对/不确定）', '依据（蒙对必填：哪一步缺了什么）'])
        for s in sorted(S, key=lambda s: (s['site'], s['sample_id'])): w.writerow([s['sample_id'], SITE_CN[s['site']], '', ''])
print("booklets:", sorted(f'打分册_{k}.md ({len(v)} 张)' for k, v in by_site.items()))
