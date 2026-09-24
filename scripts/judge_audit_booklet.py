"""Plain-language grading booklet (one card per rollout) + simple score sheets. Judge labels hidden."""
import json, csv, collections, re
S = [json.loads(l) for l in open('judge_audit/sample_200.jsonl')]
SITE_CN = {'shopping': '购物网站（顾客端）', 'shopping_admin': '购物网站后台（管理员端）', 'gitlab': 'GitLab 代码托管网站', 'reddit': '论坛网站', 'map': '地图网站'}
def act_cn(a):
    a = a.strip()
    m = re.match(r"send_msg_to_user\((.*)\)$", a, re.S)
    if m: return "把答案交了上去：" + m.group(1).strip().strip('"\'')[:300]
    if a.startswith('report_infeasible'): return "宣布这个任务做不了" + (("：" + a[len('report_infeasible'):].strip('()"\' ')[:200]) if len(a) > 20 else '')
    for k, cn in (('click', '点了一下页面上的某个按钮/链接'), ('fill', '在输入框里打字'), ('goto', '直接打开一个网址'), ('select_option', '在下拉菜单里选了一项'), ('scroll', '滚动页面'), ('go_back', '点了浏览器的后退'), ('noop', '什么都没做，等了一下'), ('hover', '把鼠标移到某处'), ('press', '按了键盘')):
        if a.startswith(k): return cn + ("（" + a[:120] + "）" if k in ('fill', 'goto', 'select_option', 'press') else '')
    return a[:200]
def ref_cn(ref, need):
    if not need: return "这道题不需要写答案，要的是完成一个操作（比如改设置、发帖、建项目）。判分程序是去网站里检查操作有没有真的做成。"
    if not ref: return "（无）"
    parts = []
    for k, v in ref.items():
        vs = v if isinstance(v, list) else [v]
        if k == 'must_include': parts.append("答案里必须出现：" + "；".join(map(str, vs)))
        elif k == 'exact_match': parts.append("答案必须恰好是：" + "；".join(map(str, vs)))
        elif k == 'fuzzy_match': parts.append("答案大意要是：" + "；".join(map(str, vs)))
        else: parts.append(f"{k}：" + "；".join(map(str, vs)))
    txt = "。".join(parts)
    if 'N/A' in json.dumps(ref): txt += "。（N/A 的意思是：这道题的正确答案是\"不存在 / 找不到\"。）"
    return txt
GUIDE = """# 打分册：{site_cn}（共 {n} 张卡片）

## 这是在做什么

我们让一个 AI 在网站上做任务。每张卡片是 AI 的一次做题过程，而且**自动判分程序已经判它做对了**。

现在想知道的是：**这些"做对"里，有多少是真的做出来的，有多少只是碰巧对了？** 这一步机器也判过一遍，但机器判得准不准，需要人来核。所以请你不看机器的结论（卡片里没放），自己判一遍。

## 怎么判

每张卡片先看三样东西：**题目**、**标准答案**、**AI 最后给出的答案**。然后从头读 AI 的做题过程（一步一步列出来了：它当时在想什么、做了什么、在哪个页面）。问自己一个问题：

> **AI 是不是真的走到了能证明答案的那个页面、看到了那个东西，然后才答的？**

- 是 → 填 **真做出来的**
- 不是 → 填 **碰巧对了**，并写一句为什么（比如："一步没走就直接报答案"、"标准答案是 N/A，它只是中途放弃没答，恰好被算对"、"它把整页内容都抄进答案，正确值只是碰巧在里面"、"要求做的操作它根本没做"）
- 过程信息太少，看不出来 → 填 **看不出来**

注意：AI 的"当时在想什么"是它自己写的英文原话；"做了什么"我翻成了中文。

## 怎么填

打开 `打分表_A.csv`（第二个人用 `打分表_B.csv`），找到卡片编号那一行，在"你的判断"一栏写 **真做出来的 / 碰巧对了 / 看不出来** 三者之一，"为什么"一栏写依据（判"碰巧对了"的必须写）。两个人各自填，别商量。

---
"""
by_site = collections.defaultdict(list)
for s in S: by_site[s['site']].append(s)
for site, items in by_site.items():
    items.sort(key=lambda s: s['sample_id']); out = [GUIDE.format(site_cn=SITE_CN[site], n=len(items))]
    for s in items:
        need = 'string_match' in s['eval_types']
        ans = s['final_answer'] if s['final_answer'] else ("（AI 没有给出任何答案就停了）" if need else "（这类任务不需要文字答案）")
        out.append(f"## 卡片编号 {s['sample_id']}\n")
        out.append(f"**题目**：{s['intent']}\n")
        out.append(f"**标准答案**：{ref_cn(s['reference'], need)}\n")
        out.append(f"**AI 最后给出的答案**：{ans}\n")
        out.append(f"**自动判分结果**：对\n")
        out.append(f"**AI 的做题过程**（共 {len(s['steps'])} 步）\n")
        for st in s['steps']:
            url = re.sub(r'^https?://[^/]+', '', st['url'] or '') or '/（首页）'
            th = st['thought'].strip() or '（这一步没写想法）'
            out.append(f"- 第 {st['step']+1} 步　当时在想：{th}\n  做了什么：{act_cn(st['action'])}\n  所在页面：`{url[:120]}`")
        out.append("\n**你的判断**（填到打分表里）：真做出来的 / 碰巧对了 / 看不出来\n\n---\n")
    open(f'judge_audit/打分册_{site}.md', 'w').write("\n".join(out))
for who in ('A', 'B'):
    with open(f'judge_audit/打分表_{who}.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['卡片编号', '网站', '你的判断（真做出来的 / 碰巧对了 / 看不出来）', '为什么（判"碰巧对了"的必须写）'])
        for s in sorted(S, key=lambda s: (s['site'], s['sample_id'])): w.writerow([s['sample_id'], SITE_CN[s['site']], '', ''])
print("ok")
