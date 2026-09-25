# 反馈权限与蒙对识别：谁能看到什么，以及蒙对识别到底值多少分（2026-09-25）

## 先说大白话

**谁能看到参考答案。** 在我们的 WebArena 流水线里，参考答案和官方判分只进一个地方：判官（judge）。判官的输入第二行就是 `REFERENCE ANSWER (ground truth): {"must_include": ["265.69"]}`，第三行是 `OFFICIAL GRADER VERDICT: CORRECT`。写经验的 L1、L2 不拿参考答案，但它们拿判官写的那句理由——理由里常带着数字和判分口径（"omitted the item's $5 share of the $10 shipping charge; adding that yields the required $265.69"）。这就是我们叫"声明式泄漏"的那条通道，本文附了原始输入。agent 做题时什么都看不到，只有门控挑出来的一条经验，包在"这是可选提示、不合适就别用"的措辞里。

**AWM 和 ReasoningBank 不是等价反馈。** 两家论文里的学习循环都不消费 benchmark 的真值：成败由一个和 agent 同家族的 LLM 判官自己判（AWM 借 Pan et al. 2024 的评估器，看最后一页和动作序列；RB 看 query、轨迹、最后页面状态和最终回答），判官准确率 RB 自报 72.7%，AWM 没报。我们的判官看得到官方 reward 和参考答案，所以我们的学习信号比它们干净得多——这是设定级差异，论文必须写明；对 RB 公平的做法是给它同样的真值标签，或者承认设定不同。两家开源代码里都有 `--criteria gt` 开关能读 WebArena 的 `cum_reward`，RB 的 MaTTS 归纳脚本默认就是 gt（但标签没进提示词）。

**蒙对识别值多少分。** 蒙对（官方判对但轨迹不支撑）占官方判对分的 1.2–3.6 点，map 7.6–8.5 点。把蒙对当成功只会改变 14/763 道题的写入档位，按各档实测下游 Δ 折算净影响约等于 0——**蒙对识别的价值不在这 14 道题的档位上，在经验的内容上**：源任务含蒙对（已剔出对比）的经验，下游 Δ −0.4（n=21），不含的 +1.6（n=450）；蒙对占多数的"成功"题在 map 上写出 11 条 L2，下游 −6.7（n=7）；历史案例里一条从蒙对答案形态学来的 "answer N/A" 经验让 3 道兄弟题 0/8，占那次 run 7 个点。**SWE 是反面教材**：那里的判官是 label-free 的（和 RB 同设定），它判"成功"的 attempt 里 24%（93/389）实际是 harness 失败，"verified" 位挡不住（92/93 也标了 verified）；26 条"成功来源"的 L2 里 20 条（77%）来自 harness 没解出的题——2606.15017 报 RB 的"成功经验" 53–60% 来自真值失败，我们在自己的 label-free 设定里复现了同一件事。

**没测的**：真正的消融臂（判官关掉或蒙对当成功、用当前写手重跑一个站）没跑过，一个站两臂约 1 天机时。

---

## 一、Hippo：每个环节能看到什么

| 环节 | 任务意图 | 页面观察 | 官方 reward | 参考答案 | 判官理由 | 其他 rollout | 库里的经验 | 代码 |
|---|---|---|---|---|---|---|---|---|
| agent（8 条 rollout） | 是 | 是（完整 a11y 树） | 否 | 否 | 否 | 否 | 门控挑的至多 1 条 L2 | `wa/rollout.py` `run_episode` |
| 官方判分器 | 是 | 读服务器状态 / 最终答案 | 产出 | 是（fuzzy_match 用 gpt-4o 对照参考答案） | — | — | — | webarena evaluators（打了 N/A 规则和 host 归一化补丁） |
| 判官 judge | 是 | 是（compact_trace，含页面文本，上限 20 万字符） | **是** | **是** | 产出 | 否（逐条判） | 否 | `wa/brain.py:120-140` |
| L1 写手 | 是 | 是（该 rollout 的 compact_trace） | 间接（只对 failure 调） | **否** | **是**（`FAILED: {reason}`） | 否 | 否 | `brain.py:141-153` |
| L2 写手 | 是 | 真成功 rollout 的完整 trace（多数错/半半/全错档） | 间接（OK/WRONG 标签） | **否** | **是**（每条 rollout 一行 `[OK/WRONG] (reason)`） | 是（≤8 条，剔蒙对） | 失败 rollout 的 L1 | `brain.py:155-257` |
| 门控 select_lesson | 是 | 否 | 否 | 否 | 否 | 否 | 5 条候选的 title+content | `brain.py:259-272` |
| 入库/去重 | — | — | — | — | — | — | (scope, 标题) 去重 | `wa/run.py:483-507` |

三条硬边界：agent 全程看不到 reward、参考答案、判官理由；写手看不到参考答案，只看判官理由；判官不能推翻判分器（reward=0 必 failure，reward=1 只能 genuine/fluke）。

### 参考答案是怎么进判官、又怎么漏到写手的：一条真实链路（shopping t141 → t143，run `wa_fleet_shopping_all_20260811`）

**(1) 判官输入**（t143 无记忆臂 rollout 0；TRACE 是带页面文本的 compact_trace，事件里没存，这里略）：

```
system: An agent attempted a web task. The OFFICIAL grader has ALREADY scored this rollout against the reference answer — that CORRECT/INCORRECT verdict (given in the message) is GROUND TRUTH; do NOT re-judge whether the final answer matches.
Your only job is to read the trace and label HOW the outcome came about.
Respond JSON {"outcome": str, "reason": str}:
- If the grader says INCORRECT -> outcome="failure"; reason = the concrete cause it went wrong and what it would have needed to do to reach the reference answer.
- If the grader says CORRECT -> decide how the right answer was reached:
    outcome="genuine" if the trace shows the agent actually navigated to and READ the value(s) that yield the reference answer;
    outcome="fluke" if the correct answer was reached by luck — the agent dumped/listed a lot of content that merely happened to contain it, guessed, or never grounded the specific value. reason = why it is a fluke.
- When the grader says CORRECT but you are unsure how, prefer "genuine".

user:
TASK: How much I spent on home decoration shopping during 1/29/2023

REFERENCE ANSWER (ground truth): {"must_include": ["265.69"]}
OFFICIAL GRADER VERDICT: INCORRECT

AGENT FINAL ANSWER: $260.69

TRACE:
[compact_trace: 每步的思考、动作、页面文本；此处略]
```
判官输出：`{"outcome": "failure", "reason": "The agent correctly identified the $260.69 home-decoration item but reported only its merchandise subtotal. It omitted the item's $5 share of the $10 shipping charge across the two ordered items; adding that yields the required $265.69."}`

**(2) L1 写手输入**（t141 带记忆臂 rollout 0，判官理由原文进 system prompt 的 `FAILED:` 子句；写手拿不到参考答案 47.41 本身，但理由里有 "$25 shipping"、"$7.99 cake-topper" 这类判官对照参考答案后写出的细节）：

```
system: You are an expert web-navigation analyst distilling a lesson from ONE failed rollout. It FAILED: The agent undercounted the mixed March 11 order. It included only the $11.43 cornbread mix and missed the $7.99 cake-topper item as food-related, while also failing to include the applicable share of that order's $25 shipping. …
Extract lessons that would prevent this failure on future tasks on this site.
A single attempt cannot tell a bad route from a good route walked badly: do NOT write blanket prohibitions ("never use X", "page Y is unreliable") from one trajectory — state what to VERIFY on that route instead.
Respond JSON {{"items": [{{"title": str, "description": str, "content": str}}]}}.
- title: short name for the control/decision.
- description: WHEN this applies (and when not) — the retrieval condition.
- content: 1-3 sentences of actionable insight.
- Items must generalize to FUTURE tasks on this SITE. Cover BOTH: (a) navigation — where a control/report lives, what a labeled element does, the reliable sequence, the look-alike trap (e.g. a report that cannot filter by status); AND (b) answer extraction — how to read the result COMPLETELY once you reach it: copy the full displayed value (open a detail view if the grid abbreviates a name), enumerate EVERY tied/qualifying row, verify the answer is visible rather than guessed, don't confuse near-identical variants. Describe controls by visible text/role, NEVER by numeric bid. NEVER copy task-specific values (product names, search terms, dates, numbers).
- Return at most 1 item — the single most important, reusable lesson; [] only if nothing reusable was learned.

user:
SITE: shopping
TASK: How much I spent on food-related shopping during March 2023

TRACE:
[该 rollout 的 compact_trace，略]
```
写出的 L1（6 条之一）："Audit mixed orders and allocate shipping — From My Account, select 'View All' under 'Recent Orders' or open 'My Orders,' … add the qualifying share of 'Shipping & Handling' for mixed orders …"

**(3) L2 写手输入**（t141，全错档 nc=0/8，蒙对 0 条；每条 rollout 一行，括号里是判官理由，正文是该 rollout 的 L1）：

```
system: An agent made N independent PARALLEL rollouts of the SAME web task. For each rollout you see its verdict (OK/WRONG, with the judge's reason) and EITHER the lesson distilled from it (its L1) OR, for a genuine success we want to learn from, its full TRACE.
Look across ALL N outcomes and the success/failure ratio, then write ONE higher-level lesson:
[方向子句，全错档，见附录]
Respond JSON {{"items": [{{"title": str, "description": str, "content": str}}]}}.
- title: short name for the control/decision.
- description: WHEN this applies (and when not) — the retrieval condition.
- content: 1-3 sentences of actionable insight.
- Items must generalize to FUTURE tasks on this SITE. Cover BOTH: (a) navigation — where a control/report lives, what a labeled element does, the reliable sequence, the look-alike trap (e.g. a report that cannot filter by status); AND (b) answer extraction — how to read the result COMPLETELY once you reach it: copy the full displayed value (open a detail view if the grid abbreviates a name), enumerate EVERY tied/qualifying row, verify the answer is visible rather than guessed, don't confuse near-identical variants. Describe controls by visible text/role, NEVER by numeric bid. NEVER copy task-specific values (product names, search terms, dates, numbers).
- Return at most 1 item — the single most important, reusable lesson; [] only if nothing reusable was learned.

user:
SITE: shopping
TASK: How much I spent on food-related shopping during March 2023

8 rollouts, 0 succeeded:

--- rollout 1 [WRONG] (The agent undercounted the mixed March 11 order. It included only the $11.43 cornbread mix and missed the $7.99 cake-topper item as food-related, while also failing to include the applicable share of that order's $25 shipping. …)
  L1 lesson: Audit mixed orders and allocate shipping: From My Account, select "View All" …
--- rollout 2 [WRONG] (The agent undercounted by treating only the cornbread mix as food-related in the mixed order and using its $11.43 merchandise subtotal without shipping … It also needed to include the $7.99 cake topper …)
  L1 lesson: Use full order details and include attributable costs: …
--- rollout 3 [WRONG] (… omitted the $5-per-item shipping attributable to each of the three relevant products …)
  L1 lesson: Audit full order details and attributable costs: …
[其余 5 条同格式]
```
写出的 L2：**Audit complete orders and allocate related shipping** — "…then add each item's attributable share of 'Shipping & Handling' based on the visible per-item or per-unit pattern and reconcile the result with the order totals."

**(4) 门控输入**（t143，dense top-5 候选的 title+content 列成菜单，返回下标或 −1）：

```
system: Given the CURRENT web task and a numbered list of candidate past lessons, pick the ONE most APPLICABLE lesson. It must genuinely fit this task's goal and the controls/pages it needs — matching topic words is NOT enough (e.g. a task about the 'main' branch needs the branch-specific lesson, not a generic Contributors one). If NONE genuinely applies, return -1 — injecting nothing is better than a misleading lesson.
Respond JSON {"idx": int} (the 0-based index, or -1).

user:
CURRENT TASK: How much I spent on home decoration shopping during 1/29/2023

CANDIDATE LESSONS:
[0] Audit complete orders and allocate related shipping: Open "My Account" → "My Orders," review all pages …
[1] …（其余 4 条候选）
```
输出 `{"idx": 0}`（余弦 0.585）。

**(5) agent 输入**（t143 带记忆臂 8 条 rollout 共用，746 字符）：

```
Optional hints from past tasks on this site — use one ONLY if it clearly fits the current task, and prefer the cheapest sufficient evidence. Do not add steps or chase a procedure a hint describes if you can already answer directly and correctly:
[strategy] Audit complete orders and allocate related shipping: Open "My Account" → "My Orders," review all pages for the requested period, and select "View Order" on every qualifying row. In "Items Ordered," enumerate every visibly category-related product—including accessories, decorations, and supplies—using full names and displayed subtotals, then add each item's attributable share of "Shipping & Handling" based on the visible per-item or per-unit pattern and reconcile the result with the order totals. (applies when: Use for category-spend questions based on purchase history, especially when orders mix qualifying and unrelated merchandise; do not rely on the limited "Recent Orders" panel or interpret a category as consumables only.)

TASK: How much I spent on home decoration shopping during 1/29/2023

HISTORY:
…
```
结果：无记忆 8 条全部答 $260.69（漏运费），带记忆 8 条全部答 $265.69。

### 一个蒙对的判官输出（gitlab t168，run `wa_gitlab_20260722_022526`，rollout 1）

参考答案 `{"fuzzy_match": "N/A"}`，agent 走了 1 步、没作答（最终答案空串），官方判分器按模糊匹配判对。判官：`{"outcome": "fluke", "reason": "The agent produced no final answer. Although it inspected the project list and noticed no displayed repository exceeded 100 stars, it explicitly concluded that the profile contribution activity still needed inspection and never completed that verification. The empty response only happened to align with the N/A reference."}`

### SWE 与 Mind2Web 的判官看什么

SWE（`swe/brain.py`）：判官 **label-free**——看 issue、轨迹、patch，输出 success 与 verified 两个位，不看 harness 真值（真值只在事后评测用）；L1 对失败/未验证的 attempt 写，L2 对比 attempts 的 traces 与 patches，不吃 L1。这和 ReasoningBank 的设定等价，第三节的数字说明它有多不可靠。Mind2Web（`hippo/brain.py` `judge_step`）：教师强制，每步都有 gold 控件，L1 写手直接拿到 gold（`CORRECT_CONTROL`），是最强的监督。

## 二、AWM 与 ReasoningBank 的反馈权限（论文与开源代码核对）

| 方法 | 学习信号 | 看官方 reward？ | 看参考答案？ | 判官模型 | 判官看什么 | 失败也提炼？ | 出处 |
|---|---|---|---|---|---|---|---|
| **Hippo（WebArena）** | 官方 reward + 参考答案 → 判官三分类；写手答案盲但拿判官理由 | **是**（判官） | **是**（判官） | gpt-5.6-sol（与 agent 同模型），T=0 | 任务、参考答案、官方判定、最终答案、完整 compact_trace | 是（L1 每条真失败；L2 四档） | 本文第一节 |
| Hippo（SWE） | label-free 判官 success/verified | 否 | 否 | gpt-4o-mini | issue、trace、patch | 是 | `swe/brain.py` |
| AWM 离线（Mind2Web） | 训练集人工标注的 gold 轨迹 | 不适用（直接用 gold 轨迹） | 是（gold 动作序列） | 无 | — | 否 | §2.3 "I(E_train) → W_offline" |
| AWM 在线（WebArena） | LM 判官二值标签，只归纳判为成功的轨迹 | 论文：否；代码有 `--criteria gt` 读 `cum_reward`，默认 autoeval | 否 | 论文未指明（"the LM-based evaluation model of Pan et al. 2024"）；代码默认 gpt-3.5-turbo 文本版，gpt-4o 走视觉 | 用户意图、动作序列、"最终页面状态"（代码里填的是 agent 最后一步的 think 文本）、最终回答 | 否 | §2.3 Online；`induce_prompt.py:170-172`；`evaluator.py:61-63` |
| ReasoningBank | LLM-as-judge 二值标签（与 agent 同骨干，T=0），成功和失败都提炼 | 论文主流程：否；§5 校准消融用真值模拟不同准确率的判官；代码 `pipeline_memory.py` 默认 autoeval，`induce_scaling.py`（MaTTS）默认 `gt`（标签未进提示词） | 否 | Gemini-2.5-flash/pro、Claude-3.7-sonnet（同 agent） | query、轨迹（think/action）、最后 5 页页面状态（≤40k 字符）、最终回答；2026-04 起提取器还拿到判官的理由 | 是 | §3.2；App. A.1–A.3；`induce_memory.py:159-162` |

判官准确率：RB 自报 72.7%（WebArena-Shopping，Gemini-2.5-flash 对真值，§5）；AWM 没报，它借的 Pan et al. 2024 评估器在 WebArena 上与 oracle 一致率 74.4–82.1%。2606.15017 的 Table 10：RB 标为"成功"的经验里来自真值失败的比例 Shopping 52.9%（Gemini 3 Flash）/ 59.5%（GPT-5.4-mini），Reddit 30.2% / 60.0%，Admin 42.6% / 48.1%；AWM 的归纳事件来自真值失败的比例 10.9–52.3%（Table 9）。

**等价性判断。** 不等价。两家的学习循环在论文里都不消费 benchmark 的 reward 或参考答案；我们的判官两者都看，而且判官理由把参考答案的口径带进了写手。所以我们测出来的效应是"在标签无噪声条件下文字经验记忆能买到多少"，是 RB/AWM 这类自判方法在同一 actor 上的上界；要和它们直接比，要么给它们同样的真值标签（它们的代码都有这个开关），要么在论文里把这一条写成设定差异。MaTTS 的 Best-of-N 是 LLM 选最优不是 oracle 选，这一点它们是干净的。

## 三、蒙对识别是否有用：能找到的全部数

### 3.1 蒙对是什么、有多少

判官标 fluke 的条件：官方判对，但轨迹显示答案是碰上的——没作答（参考答案恰好是 N/A）、把大段页面倒进答案、瞎猜命中、没读到支撑的值。五站全集 run（两臂）官方判对的 7,937 条 rollout 里 412 条（5.2%）被标 fluke；其中 84% 是 agent 没作答，47% 的题参考答案含 N/A。

| 站 | judge=fluke | 参考答案含 N/A | agent 没作答 |
|---|---|---|---|
| shopping | 99 | 83 | 99 |
| shopping_admin | 44 | 0 | 32 |
| gitlab | 103 | 31 | 100 |
| reddit | 26 | 23 | 26 |
| map | 140 | 56 | 88 |
| 合计 | 412 | 193 (47%) | 345 (84%) |

### 3.2 分数里有多少是蒙对

8 条 rollout 均值口径，reward SR 与"蒙对算错"的 genuine SR 之差：

| 站 | nomem reward → genuine | withmem reward → genuine | 蒙对贡献的分 |
|---|---|---|---|
| shopping | 55.9 → 52.8 | 57.6 → 54.1 | 3.1 / 3.5 |
| shopping_admin | 63.8 → 62.6 | 63.9 → 62.1 | 1.2 / 1.8 |
| gitlab | 71.7 → 68.1 | 74.3 → 70.8 | 3.6 / 3.5 |
| reddit | 75.2 → 73.9 | 76.1 → 74.3 | 1.3 / 1.8 |
| map | 56.8 → 48.3 | 57.8 → 50.2 | 8.5 / 7.6 |

两臂的蒙对份额几乎一样，所以蒙对不影响配对 Δ；它影响的是绝对分和写端的学习信号。

### 3.3 若不识别蒙对，写入决策会怎么变

把 fluke 全部当 genuine（RB 式"判对就是成功"）重算闸门和四档：763 道题里 53 道含蒙对，**14 道**的档位会变——全错→多数对 3、全错→多数错 4、全错→半半 1、多数错→半半 4、多数错→多数对 1、半半→多数对 1；没有一道从"不写"变"写"或反之。按 PAPER_DIRECTION_REVIEW 里各档实测的下游 Δ（全错 +0.2、多数错 +2.7、半半 −2.9、多数对 +5.7）机械折算，这 14 道的档位变化合计 +12.6 点·题，摊到 763 题约 +0.02 点——**按档位账算，蒙对识别几乎不值分**。但这套折算假设"档位决定经验质量"，而蒙对的害处正是它让写手把运气当成功流程学进内容里，这一层档位账看不见，要看下面三条。

### 3.4 内容层面的证据

**(a) 源任务含蒙对的经验，下游更差。** 五站 471 次实跑注入里，注入的 L2 来自含蒙对源任务（蒙对已剔出对比）的 21 次，下游 Δ 均值 −0.4；来自不含蒙对源任务的 450 次，+1.6。即便剔了蒙对，含蒙对的题本身就是难写好经验的题。

**(b) 蒙对占多数的"成功"题。** 若不识别蒙对，这些题会被当成"多数成功"去学成功流程：

| 站 | 含蒙对的题 | 蒙对 ≥ 真成功的题 | 我们实际写了 L2 | 这些 L2 下游 Δ（n） | 参考答案为 N/A 的比例 |
|---|---|---|---|---|---|
| shopping | 13 | 8 | 2 | +15.6 (4) | 7/8 |
| shopping_admin | 6 | 3 | 0 | — | 0/3 |
| gitlab | 9 | 7 | 0 | — | 3/7 |
| reddit | 4 | 2 | 0 | — | 2/2 |
| map | 21 | 14 | 11 | −6.7 (7) | 4/14 |

34 道这样的题里，我们的闸门只在 13 道写了 L2（其余因为剔蒙对后不足 2 条或清一色真成功而没写）；map 那 11 条下游 −6.7，是当前系统里最接近"蒙对污染"的一组。shopping 的 2 条是正的（n=4，噪声）。

**(c) 历史案例（唯一一次蒙对答案形态进了写手）。** run `wa_gitlab_20260721_220729`：t168 8 条里 6 条蒙对（没作答，参考答案 N/A），判官全部识别并剔出对比；但那一版写手能看到参考答案，L2 写成 "…if none visibly exceed the threshold, answer N/A rather than guessing"，被 t169/170/171 检索到（余弦 0.70–0.72），三道题 0/8——那次 run 43 道题，这一条经验吃掉 3 道题、24 条 rollout，7.0 个点。第二天写手改答案盲（`wa_gitlab_20260722_022526`），同一道 t168 4 条蒙对剔出、从 2 真成功 2 失败里写出 "Verify contributed projects by actual star count"，t169–172 全 8/8。案例图在 `paper/figures/C1_fluke_poison_case.png`。

### 3.5 SWE：没有真值的判官会怎样（RB 设定的实证）

SWE 的判官 label-free（和 ReasoningBank 同设定）。`swe_big_django` 两臂全部 attempt 里判官判 success 的 389 次，按 instance 的 harness 真值分：296 次 harness 也解出，**93 次（23.9%）harness 没解出**——这就是蒙对的 SWE 版，而且判官的 verified 位没有帮助（93 次假成功里 92 次也被标 verified）。往写端看：26 条"成功来源"的 L2（写的是"少数派成功的可靠流程"）里，**20 条（77%）的源题 harness 没解出**，只有 6 条来自真解出的题。2606.15017 报 ReasoningBank 的成功经验里 53–60% 来自真值失败，我们在自己的 label-free 通道里量到 77%。这一列的意义是：没有真值的判官不是"稍微不准"，是把大多数"成功流程"写成了失败流程；WebArena 上我们的判官看得到 reward 和参考答案，这一类污染在结构上不会发生——代价是 oracle 设定。

### 3.6 结论与没测的

能说的：蒙对在分数里占 1–4 点（map 8 点），两臂对称；蒙对识别对写入档位几乎没影响（14/763 题、净 ≈ 0），它的价值在于不让"运气"进写手——含蒙对源题的经验下游更差、蒙对占多数的题写出的经验 map 上 −6.7、历史上一次泄漏就吃掉 7 个点；在没有真值的 SWE 通道里，"成功经验" 77% 来自失败，说明 RB 式判官的问题是结构性的。

没测的：真正的消融臂——用当前写手、把判官关掉（所有 reward=1 当 genuine）跑一个站两臂各 8 rollout，直接量 Δ 差；估一个站一天机时。判官自身的 precision/recall 由 JUDGE_RELIABILITY_STUDY.md 的人工审计给出（200 条盲标样本已备好）。

## 附录 A · 全部提示词原文（`src/hippo/wa/brain.py`）

**判官 `_JUDGE_SYS`**

```
An agent attempted a web task. The OFFICIAL grader has ALREADY scored this rollout against the reference answer — that CORRECT/INCORRECT verdict (given in the message) is GROUND TRUTH; do NOT re-judge whether the final answer matches.
Your only job is to read the trace and label HOW the outcome came about.
Respond JSON {"outcome": str, "reason": str}:
- If the grader says INCORRECT -> outcome="failure"; reason = the concrete cause it went wrong and what it would have needed to do to reach the reference answer.
- If the grader says CORRECT -> decide how the right answer was reached:
    outcome="genuine" if the trace shows the agent actually navigated to and READ the value(s) that yield the reference answer;
    outcome="fluke" if the correct answer was reached by luck — the agent dumped/listed a lot of content that merely happened to contain it, guessed, or never grounded the specific value. reason = why it is a fluke.
- When the grader says CORRECT but you are unsure how, prefer "genuine".
```
用户消息格式：`TASK: …` / `REFERENCE ANSWER (ground truth): <json>` / `OFFICIAL GRADER VERDICT: CORRECT|INCORRECT` / `AGENT FINAL ANSWER: …` / `TRACE: <compact_trace>`；T=0；代码硬保证 reward=0→failure，reward=1→genuine|fluke，解析失败→genuine。

**L1 写手 `_L1_SYS`**（`{outcome_clause}` = `FAILED: <判官理由>`；末尾拼接条目格式 `_ITEM_FORMAT`）
```
You are an expert web-navigation analyst distilling a lesson from ONE failed rollout. It {outcome_clause}
Extract lessons that would prevent this failure on future tasks on this site.
A single attempt cannot tell a bad route from a good route walked badly: do NOT write blanket prohibitions ("never use X", "page Y is unreliable") from one trajectory — state what to VERIFY on that route instead.
Respond JSON {{"items": [{{"title": str, "description": str, "content": str}}]}}.
- title: short name for the control/decision.
- description: WHEN this applies (and when not) — the retrieval condition.
- content: 1-3 sentences of actionable insight.
- Items must generalize to FUTURE tasks on this SITE. Cover BOTH: (a) navigation — where a control/report lives, what a labeled element does, the reliable sequence, the look-alike trap (e.g. a report that cannot filter by status); AND (b) answer extraction — how to read the result COMPLETELY once you reach it: copy the full displayed value (open a detail view if the grid abbreviates a name), enumerate EVERY tied/qualifying row, verify the answer is visible rather than guessed, don't confuse near-identical variants. Describe controls by visible text/role, NEVER by numeric bid. NEVER copy task-specific values (product names, search terms, dates, numbers).
- Return at most {max_items} item — the single most important, reusable lesson; [] only if nothing reusable was learned.
```
用户消息：`SITE: … / TASK: … / TRACE: <该 rollout 的 compact_trace>`。

**L2 写手 `_L2_SYS`**（`{direction}` 按成败比例换四段之一）
```
An agent made N independent PARALLEL rollouts of the SAME web task. For each rollout you see its verdict (OK/WRONG, with the judge's reason) and EITHER the lesson distilled from it (its L1) OR, for a genuine success we want to learn from, its full TRACE.
Look across ALL N outcomes and the success/failure ratio, then write ONE higher-level lesson:
{direction}
Respond JSON {{"items": [{{"title": str, "description": str, "content": str}}]}}.
- title: short name for the control/decision.
- description: WHEN this applies (and when not) — the retrieval condition.
- content: 1-3 sentences of actionable insight.
- Items must generalize to FUTURE tasks on this SITE. Cover BOTH: (a) navigation — where a control/report lives, what a labeled element does, the reliable sequence, the look-alike trap (e.g. a report that cannot filter by status); AND (b) answer extraction — how to read the result COMPLETELY once you reach it: copy the full displayed value (open a detail view if the grid abbreviates a name), enumerate EVERY tied/qualifying row, verify the answer is visible rather than guessed, don't confuse near-identical variants. Describe controls by visible text/role, NEVER by numeric bid. NEVER copy task-specific values (product names, search terms, dates, numbers).
- Return at most {max_items} item — the single most important, reusable lesson; [] only if nothing reusable was learned.
```
**全错（nc=0）**：
```
ALL rollouts FAILED. Summarize the common cause of failure. Read the verdicts: if they ran out of the step budget or never produced a final answer, say the approach is too long to finish in budget and advise a cheaper route or giving a best-effort partial answer — do NOT advise being more exhaustive. If they took a wrong path, name it so it is avoided. If every rollout read the same on-page value and it was judged wrong, do NOT conclude the site or its results are untrustworthy, and never advise overriding a displayed value with outside knowledge — describe where the correct value lives ON the site and how to read it. Recommend only actions some rollout actually performed: a reading convention diagnosed by the verdicts may be stated directly, and scope controls that only change what is displayed (tabs, filters, sorting, page size) are safe to include; but a UI mechanism no rollout ever completed must NOT become the substance of the lesson — start the content with an executable instruction, and mention an untried idea only in a final clause explicitly marked as untried.
```

**半对半错**：
```
Half succeeded, half failed. State BOTH: the reliable thing the successful rollouts did, AND the specific trap the failing ones fell into.
```

**多数对少数错**：
```
Most rollouts SUCCEEDED; a few failed. NOTE the specific mistake the failing minority made — phrase it as a caution to avoid. The caution may steer navigation or verification, but must NEVER narrow the final answer: keep every element, label and unit the task asks for — most rollouts answered correctly, do not overcorrect their answer format.
```

**多数错少数对**：
```
Most rollouts FAILED; a few succeeded. Explain WHY the successful minority was right where the majority went wrong — the decision or check that separated them — NOT a transcript of the minority's steps, and NOT incidental page states they happened to see. The remedy must fit a tight step budget: state the CHEAP default way first, and make any expensive verification CONDITIONAL on the specific symptom that requires it — put that symptom condition in the content, and keep the description written in the task family's own vocabulary (the description is the retrieval key; do not dilute it with symptom clauses). When the task itself asks to enumerate or list everything, complete enumeration is NOT expensive verification and must not be made conditional.
```

用户消息：`SITE / TASK / N rollouts, nc succeeded:` 然后每条 rollout 一行 `--- rollout i [OK|WRONG] (判官理由)`，正文是该 rollout 的 L1 lesson，或（向成功学习时）真成功 rollout 的完整 TRACE，或 `(genuine success)` / `(no usable trajectory)`。蒙对的 rollout 在进入这一步之前已被剔除。

**条目格式 `_ITEM_FORMAT`**
```
Respond JSON {{"items": [{{"title": str, "description": str, "content": str}}]}}.
- title: short name for the control/decision.
- description: WHEN this applies (and when not) — the retrieval condition.
- content: 1-3 sentences of actionable insight.
- Items must generalize to FUTURE tasks on this SITE. Cover BOTH: (a) navigation — where a control/report lives, what a labeled element does, the reliable sequence, the look-alike trap (e.g. a report that cannot filter by status); AND (b) answer extraction — how to read the result COMPLETELY once you reach it: copy the full displayed value (open a detail view if the grid abbreviates a name), enumerate EVERY tied/qualifying row, verify the answer is visible rather than guessed, don't confuse near-identical variants. Describe controls by visible text/role, NEVER by numeric bid. NEVER copy task-specific values (product names, search terms, dates, numbers).
- Return at most {max_items} item — the single most important, reusable lesson; [] only if nothing reusable was learned.
```

**门控 `_L2_SELECT_SYS`**
```
Given the CURRENT web task and a numbered list of candidate past lessons, pick the ONE most APPLICABLE lesson. It must genuinely fit this task's goal and the controls/pages it needs — matching topic words is NOT enough (e.g. a task about the 'main' branch needs the branch-specific lesson, not a generic Contributors one). If NONE genuinely applies, return -1 — injecting nothing is better than a misleading lesson.
Respond JSON {"idx": int} (the 0-based index, or -1).
```
用户消息：`CURRENT TASK: … / CANDIDATE LESSONS: [i] title: content`（dense top-5）。

**注入包装**（`wa/rollout.py`）
```
Optional hints from past tasks on this site — use one ONLY if it clearly fits the current task, and prefer the cheapest sufficient evidence. Do not add steps or chase a procedure a hint describes if you can already answer directly and correctly:
{memory_text}
```
其中 `{memory_text}` = `[strategy] title: content (applies when: description)`。

## 附录 B · 数据来源

五站全集 run：`runs/wa_fleet_shopping_all_20260811_191401_*`、`wa_fleet_shopping_admin_all_20260818_005633_*`、`wa_fleet_gitlab_all_20260815_172053_*`、`wa_fleet_reddit_all_20260814_002621_*`、`wa_fleet_map_readonly_20260813_103741_*`（事件 `wa_judge` 的 reward/outcome/reason，`wa_write_l2` 的 nc/n/n_fluke，`wa_retrieve`）；历史案例 `runs/wa_gitlab_20260721_220729_*`、`wa_gitlab_20260722_022526_*`；SWE `runs/swe_big_django_20260712_190710/`（`swe_task` 事件的 judge 字段、`gt_big_*_gt.json`、`memory.json` 的 outcome 与 `swe_write_l2` 事件）。AWM / ReasoningBank / Pan et al. / 2606.15017 的引文与代码行号来自 arXiv 2409.07429、2509.25140、2404.06474、2606.15017 与 GitHub zorazrw/agent-workflow-memory、google-research/reasoning-bank 的核对（2026-09-25）。
