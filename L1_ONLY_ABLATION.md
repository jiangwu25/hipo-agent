# L1 单独消融：数据全记录

本文把仓库里关于 L1（逐 rollout / 逐 attempt 的失败反思）单独作用的所有数据收拢到一处，按证据强度排列：先是能从 `runs/` 原始文件重算出来的数字，再是只剩文档记载、本机没有原始数据的数字（Mind2Web），最后是推断。每个数字后面都标了来源目录或文件；单次运行、pilot 规模的数字都单独标出。全文有一条贯穿的告诫：SWE 上同一配置重跑四次，nomem 在 114 题上分别解出 49、48、52、58 题，同一臂之间就能差 8 分以上（`runs/fc_django_nomem_s{1,2,3}_*`、`runs/swe_big_django_20260712_190710`），所以凡是单臂单次的比较，差距在 8 分以内的一律不能读成效应。曾经写进 README 的 SWE "+7.0" 就是这样被四次重复归零的（nomem 四次均值 45.4%，带 243 条库四次均值 46.3%，`README.md:168`）。

## 0. 成功率一览：四种消融臂各多少分

先给结论表，细节在后面各节。每格写"nomem → 该臂"的成功率；**实测**是仓库里能重算的数，**估算**是没跑过的臂按已有数据推的值，都标了出来。WebArena 有两个口径：全集均值（五站 761 对题、8 条 rollout 命中率均值）和正典只读口径（WA_SCORES.md，四站）。SWE 是 django 114 道留出题的 harness 解决率。

| 臂 | 定义 | WebArena 全集均值 | WebArena 正典口径 | SWE Verified（django 114） | Mind2Web（49 题，步级） | 能下的结论 |
|---|---|---|---|---|---|---|
| nomem | 无记忆，8 条 rollout | 65.7 | 64.3 | 43.0（四次重复 42.1–50.9，均值 45.4） | 基线 element_acc 0.353 | — |
| **完整系统** | L1 → 闸门 → L2 对比 → 去重追加 → 门控注一条 | **65.7 → 67.0（+1.3）实测** | **64.3 → 71.8（+7.6）实测** | 43.0 → 50.0 单次实测；四次重复 45.4 → 46.3（+0.9）实测 | — | WA 全集小正，只读子集正；SWE 归零 |
| **只有 L1**（只写 L1、只注 L1） | 每条失败 rollout 独立反思，不做跨 rollout 对比 | **估算 ≈ 0（−1 到 +1）** | **估算 ≈ 0** | **43.0 → 43.0（0）实测**，185 条 L1、10 得 10 失；对四次 nomem 差 0 / +1 / −3 / −9 | **+0.054 步级实测**（104 条；element +0.021） | 唯一为正的是 Mind2Web 小样本；SWE 零；WA 07-19 七个单 rollout run 359 对 17 胜 26 负（分站 Δ 0 / +2.3 / −2.3 / −1.1 / +1.1 / −14.0 / −7.0，全在 nomem 自身摆动内） |
| **跳过 L1**（不写 L1，L2 直接从轨迹对比） | 保留闸门和 L2，L2 写手不喂 L1 | **估算 +0.5 到 +1.0**（比完整系统略低：93% 的 L2 有 L1 输入，但 L1 的边际价值没测过） | **估算 +5 左右** | 切片 C（拿掉续跑期 90 条新 L1）**20/46 = 43.5% 实测** vs 保留 A 23/46 = 50.0%、B 19/46 = 41.3%（p=0.45，噪声）；冻结 L2-only 58 条 **40.4% 实测**（−2.6） | L2-only **+0.033 步级实测**（40 条） | SWE 上拿掉 L1 只挪 1 题；WA 上没跑过这臂 |
| **不维护旧经验**（只追加，不去重不整合） | 这**就是现在的在线系统**（只有标题去重，整合原型未接入） | = 完整系统 65.7 → 67.0 实测 | = 完整系统 +7.6 实测 | 续学不整合 243→469 条：流式臂 20/46 = 43.5% 实测；整合到 237 条（Bcons）21/46 = 45.7% 实测；未整合 367 条（B）19/46 = 41.3%；A 243 条 23/46 = 50.0%——全部 p>0.29 | 库 218 条时流式 +0.009，L1+L2 合并 −0.009（灌水） | 整合与否在 SWE 上分不出；WA 上 0.88 聚簇只能压 6–13%，**估算维护后 ±1 以内** |
| **独立归纳 + 直接追加**（ReasoningBank 式） | 每条轨迹独立反思、不过滑不对比、写完直接进库、cosine top-k 直接注入、无门控 | **估算 −2 到 0** | 07-19 四站 165 题修正口径 **72.1 → 70.3（−1.8）实测**，8 胜 11 负（单 rollout、k=1、每题注 1 条）；原始 reward 359 对 17 胜 26 负 | 全库 top-4 直接注入（74% 槽位是 L1）**43.0 → 50.0 单次实测**，四次重复 **45.4 → 46.3（+0.9）** | L1+L2 合并直注 **−0.009** 实测 | 三个 bench 上都是零附近或负；这是"闸门 + 门控"存在的对照 |

三点读法。第一，只有完整系统在 WebArena 上拿到过重复验证的正效应（shopping 三次 +6.4 / +10.8 / +4.2；全集 761 对 +1.3 [−0.3, +2.9]），其余四臂没有一处显著为正。第二，SWE 这一列所有差别都在 ±8 分的同臂重复噪声里（nomem 四次 49 / 48 / 52 / 58），只能读"没有可见效应"，不能读排序。第三，两格估算的依据：WA "只有 L1" 取 07-19 七个 run 的合计（17 胜 26 负，≈ −1 到 −3）向上修正到当前写手（有全称禁令纪律、答案盲），落在 0 附近；"跳过 L1" 从完整系统的 +1.3 / +7.6 往下打七到八成，因为 L2 的对比输入里 L1 是失败方的唯一摘要、但 SWE 上拿掉它只挪 1 题；"独立归纳 + 直接追加" 取 07-19 的 −1.8 与 07-18 冻结库 −2.5，按当前判官 / 写手会略好，给 −2 到 0。要把估算变实测，第 8 节列了三个臂的开关和机时（一个站三天）。

## 1. L1 是什么、现在怎么用

"L1" 在三个 bench 上是三种不同的东西，讨论"L1 单独有没有用"之前必须先分开。

| bench | L1 的触发 | 输入 | 每次产出 | 答案盲? | item 上有 layer 标签? | 现在会被检索? | 代码位置 |
|---|---|---|---|---|---|---|---|
| WebArena | judge 判 `outcome=failure` 且未报错的每个 rollout（fluke 和 genuine success 不写） | site、intent、压缩 TRACE、judge 的失败理由（`FAILED: {reason}`） | 最多 1 条，无每题上限 | 是（但 judge reason 是一条声明过的泄漏通道） | 是，`layer='L1'` | 否（`wa.inject_only_l2` 默认 on） | `src/hippo/wa/brain.py:63-74,141-153`；`src/hippo/wa/run.py:471-489` |
| SWE-bench | 非 (success 且 verified) 且非 SetupError 的每个 attempt | repo、issue[:2000]、trace[:15000]、patch[:3000]、`FAILED: <judge reason/exit_status>` 或 "plausible patch but NEVER VERIFIED" | 每次调用最多 2 条，每题上限 `l1_max_per_task=2`（上限按已写入条数在每个 attempt 前检查：第一个失败 attempt 写满 2 条时后续 attempt 不再反思；写不满时下一个失败 attempt 仍会反思，所以单题可到 3 条，13568 即此例） | 无参考答案，label-free | 否，只能靠 `swe_write_l1` 事件的标题回溯 | 是，与 L2 同池 cosine top-4 | `src/hippo/swe/brain.py:62-68,153-170`；`src/hippo/swe/run.py:75-78,142-158` |
| Mind2Web | 每个 (attempt, step)：步错，或步对但 judge 认为是蒙对 | gold 控件被解析后直接喂给模型（`CORRECT_CONTROL`） | 模板句 `When {intent}: use '{label}' ({role})[, not '{trap}'][. {cue}]`，去字面量，dedup key = `slug(role:label:intent)` | 否，看得见 gold | 否（FactItem 无 layer 字段） | 是，与 L2 同一 FactStore、cosine top-k_fact | `src/hippo/brain.py:389-448`；`src/hippo/m2w/run.py:206-283` |

注意 `run.py:473-474` 的注释仍写着 "The reference answer is passed in so the lesson targets the procedure that would have reached the correct result"，这是 07-24 改答案盲写手时没更新的旧注释；实际调用 `run.py:481`（`brain.reflect_trajectory(site, t["intent"], x["trace"], v)`）不传参考答案，`brain.py:142-146` 明确答案盲。

WebArena 是当前的主战场，L1 在这里的角色由三段代码决定。写端在 `run.py:471-489`：只在 withmem 臂、只对 judge 判 failure 且无 error 的 rollout 调 `reflect_trajectory`，`max_items=1`，写入前用一个和 L2 共享的 `seen` 集合按 (scope, 去空白小写标题) 去重，没有每题上限。喂 L2 在 `run.py:494-508` 与 `brain.py:241-252`：每个失败 rollout 写出的 L1 以 `L1 lesson: title: content` 的形式作为该 rollout 的代表进入 `contrast_rollouts` 的 prompt；写手返回空列表的失败 rollout 就只剩 judge reason 进 L2。读端在 `run.py:345-357` 与 `src/hippo/memory/store.py:41-53`：`inject_only_l2` 打开时把 `layer='L2'` 传进 `topk_scored`，在 cosine top-k 之前先按 layer 过滤，所以 L1 在结构上不可达；关掉则 `layer=None`，L1、L2 混池。运行器里没有"只取 L1"这个取值。

SWE 上 L2 不吃 L1：`contrast_attempts` 直接拿 traces[:6000] 和 patches，L1 和 L2 是并行独立产出（`src/hippo/swe/brain.py:172-201`），尽管 `_L2_SYS` 的提示词文本里写着 "a per-attempt reflection"。Mind2Web 在 `step_evolve` 协议里每个 attempt 的 L1 `reason` 会以 `why-wrong (layer1)` 进 L2 prompt（`m2w/run.py:264`、`brain.py:493-494`），但 stream 协议的 `one()` 不捕获 `reason`，stream 模式的 L2 实际上没有 L1 输入（`m2w/run.py:406-422,472-473`）。

几个开关的实际状态：`wa.layer1`、`wa.layer2` 由 `run.py:243` 读取，`_on()` 接受字符串 `off`；`wa.l1_fluke`（`config/default.yaml:102`，注释说 "L1 records failures + 蒙对 flukes"）和 `wa.divergence_signal`（`:107`）在 `src/hippo/wa/` 里没有任何读取点；l1_fluke 只由 `scripts/run_wa_evolve.sh:20` 以 `--wa.l1_fluke off` 传过（`run_wa_site.sh:18` 仅在注释里举例），divergence_signal 没有任何脚本或代码读取或传递，两者都是死配置——fluke 写 L1 在 b08f899（2026-07-20）时代确实存在，07-24 的 40d92fc 去掉了，配置注释没跟上；`wa.vote_margin` 被读取但不使用。SWE 侧 `--swe.layer2 off` 可得流式 L1-only，冻结 L1-only 靶 `--swe.arms frozenmem --swe.memory_in .../bank_l1.json`，这正是 `abl_l1only` 用的。Mind2Web 侧 `--m2w.layer2 off` 即 L1-only（`HANDOFF.md:169`），但七个 `scripts/run_m2w*.sh` 都没传过 layer 开关。

## 2. SWE 成分消融

### 2.1 库从哪来

四个库文件都在 `runs/swe_big_django_20260712_190710/`，全部来自这个 big run 的 withmem 流。这条流跑了 115 道 django Verified 题，每题 5 个 attempt，共 575 个 attempt（291 LimitsExceeded、284 Submitted），其中 303 个不是 verified success。L1 写了 185 条，来自 92 道题（91 题 ×2、1 题 ×3，那一条多出来的是上限检查在 attempt 之前导致的），23 道 5/5 全对的题什么都没写；按源题 nc/5 分：nc=0 的 32 题贡献 64 条，nc=1 贡献 28、nc=2 贡献 24、nc=3 贡献 35、nc=4 贡献 34。L2 写了 58 条，来自 29 道题，这 29 题全部也写了 L1；另有 29 题因为 close vote（|2nc−n|<2）被跳过。所有 185 条 L1 的 outcome 都是 `failure`（success-but-unverified 路径在这次 run 里一次没触发），58 条 L2 的 outcome 是 32 failure + 26 success，这里 success 的语义按 `brain.py:200` 是"少数派成功"（nc=1/5），描述的是那次成功 attempt 用的可靠流程。

| 文件 | 条数 | 筛法 | outcome | 文件字节 | title / description / content 中位字符数 | 合计字符 中位/均值/最小/最大 | 总字符数 |
|---|---|---|---|---|---|---|---|
| memory.json | 243 | withmem 流全部 reasoning 项 | failure 217, success 26 | 2,259,622 | 64 / 185 / 342 | 594 / 605 / 421 / 1092 | 147,135 |
| bank_l1.json | 185 | 标题与 185 个 `swe_write_l1` 事件完全匹配 | failure 185 | 1,719,241 | 62 / 179 / 342 | 589 / 599 / 421 / 1092 | 110,897 |
| bank_l2.json | 58 | 标题与 58 个 `swe_write_l2` 事件匹配 | failure 32, success 26 | 540,408 | 66 / 214 / 344 | 622 / 625 / 480 / 826 | 36,238 |
| bank_success.json | 26 | bank_l2 中 outcome=='success' 的子集 | success 26 | 243,054 | 70 / 226 / 346 | 642 / 655 / 504 / 826 | 17,020 |

bank_l1 ∪ bank_l2 = memory.json 且无交集；bank_success 是 bank_l2 的子集，所以"success-only"并不是第三种来源，只是 L2 的一个 outcome 切片。所有 item 的 certainty 都是 medium、scope 都是 `repo:django/django`、surprise 0.0、source_traj_ids 为空，文件体积主要是每条 384 维的 bge-small embedding。`scripts/` 和 `src/` 里找不到任何生成 bank_* 文件的脚本（grep bank_l1/bank_l2/bank_success 无命中，只有 `EXPERIMENT_SETUP.md:444`、`RETRIEVAL_INJECTION_ABLATIONS.md:55-57`、`MEMORY_SIZES.md:35` 提到它们），这三个库是手工切的，成分是靠 id 集合与事件标题重新核出来的。

库在流里的增长（`events.jsonl` 按 t 排序）：

| withmem 完成题数 | 累计 L1 | 累计 L2 | 累计总数 (= n_memory) | L2 close-vote 跳过 | 已注入题数 | 本段写 L1 | 本段写 L2 | 本段写 L1 的题数 |
|---|---|---|---|---|---|---|---|---|
| 25 | 40 | 16 | 56 | 6 | 24 | 40 | 16 | 20 |
| 50 | 76 | 26 | 102 | 12 | 49 | 36 | 10 | 18 |
| 75 | 122 | 46 | 168 | 20 | 74 | 46 | 20 | 23 |
| 100 | 165 | 52 | 217 | 25 | 99 | 43 | 6 | 21 |
| 115 | 185 | 58 | 243 | 29 | 114 | 20（15 题） | 6 | 10 |

每 25 题写约 40 条 L1，1.6 条/题，到流末没有放缓。这条流本身的 harness 真值是 withmem 51/115 对 nomem 49/115（`gt_big_withmem_gt.json` / `gt_big_nomem_gt.json`，12 胜 10 负），花了 $125.99；nomem 臂 229 题花 $48.87；整个 run 因 BudgetExceeded 在 $180.55 停下。

### 2.2 六个消融臂的配置

六臂全部在 2026-07-13 跑完，事件文件第一行 `run_start` 记录了完整配置。共同项：`swe.arms=frozenmem`，agent `anthropic/claude-haiku-4-5`，judge `openai/gpt-4o-mini`，embed `local/BAAI/bge-small-en-v1.5`，`retrieve_k_reasoning=4`，`relevance_threshold=0.0`，`token_budget=4000`（4000×4=16000 字符，从未触顶），`step_limit=60`，`attempt_cost_limit=0.5`，`skip_done` 指向 big run 的 `preds_withmem.json`，`n_instances=116`，`budget_usd=35`，seed 0。116 题里 django-10097 和 django-7530 因 "no arm64 image" 被跳过，剩 114 题；六臂的 114 题集合完全相同，它是 229 道已评 nomem 题里排除 115 道学习题后的 holdout。

一个要纠正现有文档的点：配置里 `agent.n_traj=5`，但 `src/hippo/swe/run.py:73` 是 `n_traj = max(1, cfg.agent.n_traj) if write else 1`，frozenmem 臂不写，所以每题只跑 1 个 attempt。六臂每个 `swe_task` 事件都是 `n=1`，`metrics_frozenmem.csv` 114 行 n 之和 114。`RETRIEVAL_INJECTION_ABLATIONS.md:15` 的"每题 5 次尝试"和 `:71` 的"5 次尝试里判官认为成功的次数"与数据不符（`:49-57` 表里的 n_traj=5 是配置值，实跑 1）；`EXPERIMENT_SETUP.md:363` 写的 1 attempt 是对的。

| run | memory_in | 库大小 | injection_gate | injection_style | 每题 attempt | 题数 / 跳过 / 实跑 |
|---|---|---|---|---|---|---|
| abl_plain_20260713_040638 | memory.json | 243 | none | plain | 1 | 116 / 2 / 114 |
| abl_gate_20260713_051518 | memory.json | 243 | llm（fetch_k 10） | plain | 1 | 116 / 2 / 114 |
| abl_attend_20260713_062546 | memory.json | 243 | llm | attend | 1 | 116 / 2 / 114 |
| abl_l1only_20260713_102315 | bank_l1.json | 185 | none | plain | 1 | 116 / 1 / 0（中止） |
| abl_l1only_20260713_102404 | bank_l1.json | 185 | none | plain | 1 | 116 / 2 / 114 |
| abl_l2only_20260713_113012 | bank_l2.json | 58 | none | plain | 1 | 116 / 2 / 114 |
| abl_suconly_20260713_123441 | bank_success.json | 26 | none | plain | 1 | 116 / 2 / 114 |

中止的那个 `abl_l1only_20260713_102315` 与 102404 配置完全相同，`events.jsonl` 只有 run_start 和一条 skip_instance，`trajs/` 里有 4 条半截轨迹（django-14011/14017/14034/14053，各 5–8 次 API 调用，合计约 $0.10），48 秒后重启。没有任何 launch log 或文档解释为什么中止。

### 2.3 114 题上的结果

| 臂 | 库 | resolved/114 | % | 比 nomem 多解 | 少解 | 净 | judge 判成功（attempt 0） | summary judge_sr | 平均 n_retrieved | 注入题数 | 平均 mem_chars | agent 成本 $ | 含 judge 总花费 $ | judge 调用 | Submitted / LimitsExceeded | 墙钟 min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nomem（big run） | — | 49 | 43.0 | — | — | — | — | — | 0 | 0 | 0 | （229 题共 $48.87） | — | — | — | — |
| plain | 243 | 57 | 50.0 | 16 | 8 | +8 | 66 | 0.5789 | 4.00 | 114 | 2732 | 23.50 | 24.24 | 67 | 67 / 47 | 66 |
| gate | 243 | 55 | 48.2 | 11 | 5 | +6 | 63 | 0.5526 | 1.33 | 83 | 848 | 23.00 | 24.00 | 176 | 64 / 50 | 68 |
| attend | 243 | 54 | 47.4 | 13 | 8 | +5 | 67 | 0.5877 | 1.33 | 83 | 848 | 23.76 | 24.52 | 70 | 70 / 44 | 70 |
| l1only | 185 | 49 | 43.0 | 10 | 10 | 0 | 58 | 0.5088 | 4.00 | 114 | 2702 | 23.82 | 24.50 | 60 | 60 / 54 | 64 |
| l2only | 58 | 46 | 40.4 | 9 | 12 | −3 | 57 | 0.5000 | 4.00 | 114 | 2797 | 23.46 | 24.10 | 57 | 57 / 57 | 62 |
| suconly | 26 | 50 | 43.9 | 11 | 10 | +1 | 58 | 0.5088 | 4.00 | 114 | 2861 | 23.15 | 23.81 | 60 | 60 / 54 | 62 |

来源：各臂 `gt_*_gt.json` 与 `runs/swe_big_django_20260712_190710/gt_big_nomem_gt.json` 限到同 114 题；`summary.json`（spent_usd、judge_llm_calls、judge_sr）；`metrics_frozenmem.csv`；`swe_task` 事件的 t 与 exit_statuses。30 题所有臂含 nomem 都解出，40 题所有臂都没解出。LLM judge 每臂比 harness 多认 8–13 题。每题平均步数 50.1–51.5，上限 60。

L1-only 与 nomem 恰好打平：l1only 解出而 nomem 没解出的 10 题是 django-14122、14311、14404、14580、14608、14771、15022、16082、16899、16901；nomem 解出而 l1only 没解出的 10 题是 14170、14493、14999、15278、15380、15467、15499、15814、15930、16502。丢掉的 10 题里 9 题以 LimitsExceeded 结束（60 步到顶没交 patch），1 题（14493）交了 judge 认可但 harness 拒绝的 patch。其他臂对 nomem 的翻转：plain +16（14053,14122,14311,14315,14376,14404,14580,14608,14771,14855,15022,15375,16082,16560,16899,16901）/ −8（14999,15380,15467,15499,15814,16136,16502,16612）；gate +11 / −5；attend +13 / −8；l2only +9（14017,14311,14404,14580,15022,16082,16116,16877,16899）/ −12（14999,15278,15315,15368,15499,15851,15930,16136,16139,16502,16612,16662）；suconly +11 / −10。

臂之间：l1only ∩ plain = 47，plain 独有 10（14053,14170,14315,14376,14493,14855,15278,15375,15930,16560），l1only 独有 2（16136,16612）；l1only ∩ l2only = 38，l1only 独有 11、l2only 独有 8；l1only ∩ suconly = 41。有 6 题被 plain、l1only、l2only 三臂都解出而 nomem 没解出：14311、14404、14580、15022、16082、16899。

### 2.4 每题实际注入了什么

`swe_task` 事件记了 n_retrieved、n_memory、mem_chars、ret_scores，但没记 item id；实际注入项是解析 `trajs/*.frozenmem.a0.traj.json` 里的 `<memory>` 块、按标题回配库项得到的（0 条未匹配）。渲染格式是 `[strategy] {title}: {content} (applies when: {description})`（`store.py:140-156`），整块前置在 mini-swe-agent 的 instance 模板前（`rollout.py:22-29`）。

| 臂 | n_memory | n_retrieved 分布 | 注入题数 | mem_chars 均值/中位/最小/最大 | 字符/条 | top-1 cosine 中位（范围） | 第 4 名 cosine 中位（最小） | 注入总次数 | 用到的不同项 | 从未注入 | 来自 L1 / L2（其中 success 源） | 最高复用（项） |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| plain | 243 | {4:114} | 114 | 2732/2716/2183/3524 | 683 | 0.743 (0.646–0.853) | 0.716 (0.634) | 456 | 134 | 109/243 | 338 / 118 (80) | 23 |
| gate | 243 | {0:31,1:37,2:28,3:13,4:5} | 83 | 848/664/0/2513 | 640 | 0.743 | 0.697 (0.623) | 152 | 77 | — | 133 / 19 (6) | 8 |
| attend | 243 | 与 gate 相同 | 83 | 848/664/0/2513 | 640 | 0.743 | 0.697 | 152 | 77 | — | 133 / 19 (6) | 8 |
| l1only | 185 | {4:114} | 114 | 2702/2663/2183/3431 | 676 | 0.740 (0.646–0.841) | 0.712 (0.634) | 456 | 107 | 78/185 | 456 / 0 | 21 |
| l2only | 58 | {4:114} | 114 | 2797/2808/2443/3156 | 699 | 0.721 (0.623–0.853) | 0.685 (0.600) | 456 | 51 | 7/58 | 0 / 456 (295) | 60 |
| suconly | 26 | {4:114} | 114 | 2861/2874/2523/3184 | 715 | 0.712 (0.614–0.853) | 0.671 (0.590) | 456 | 26 | 0/26 | 0 / 456 (456) | 78 |

两个值得记住的事实。第一，在全库 plain 臂里 L1 占了 456 个槽位中的 338 个（74%），也就是 SWE 上所谓"全库有效"时，四分之三的注入文本本来就是 L1。第二，库越小，4 个槽位填的匹配越弱：平均 fetched cosine plain 0.725 > l1only 0.719 > l2only 0.698 > suconly 0.688；suconly 里同一条 "Locate SQLiteNumericMixin in expressions.py..." 被注入了 78 次。l1only 的复用直方图（注入次数→项数）：1:32、2:17、3:17、4:9、5:6、6:4、7:2、8:6、9:2、10:2、11:3、12:1、13:1、15:2、19:1、21:2；最高的是 "Annotations must be propagated when creating subqueries in split_exclude()" 和 "Identify the ORM filter preparation layer early for value-type issues" 各 21 次。

l1only 翻转的 20 题各自注入了什么、cosine 多少：

| instance | 方向 | exit | judge | ret_scores | 注入的 4 条 L1 标题 |
|---|---|---|---|---|---|
| 14122 | 得 | Submitted | 1 | 0.820,0.801,0.759,0.757 | GROUP BY queries ignore default_ordering in SQL generation; Filter non-groupable expressions from ORDER BY in GROUP BY logic; Test aggregation queries with various order_by() variants early; Test coverage gap for QuerySet.ordered with aggregations |
| 14311 | 得 | Submitted | 1 | 0.733,0.725,0.713,0.712 | Prioritize direct file edits over exploratory searches in large codebases; Identify the ORM filter preparation layer early for value-type issues; Use __qualname__ for nested class serialization in migrations; Identify and fix the core logic before test validation |
| 14404 | 得 | Submitted | 1 | 0.695,0.685,0.680,0.678 | Identify the exact file and method containing the bug before exploration; Save and restore handler state on MiddlewareNotUsed; Locate and understand the target function before exploring history; Always inspect generated patches for duplication and syntax errors before submission |
| 14580 | 得 | Submitted | 1 | 0.744,0.731,0.720,0.717 | Use __qualname__ for nested class serialization in migrations; Prioritize direct file edits over exploratory searches in large codebases; Start with test-driven understanding for migration-related issues; Use quote_name() for all SQL identifiers in backend-specific code |
| 14608 | 得 | Submitted | 1 | 0.686,0.679,0.653,0.652 | Test at the form field level, not just widget level; Use existing test patterns to verify form field rendering; Test assertion updates needed when changing error message format; Locate field rendering logic via widget_attrs() method |
| 14771 | 得 | Submitted | 1 | 0.684,0.682,0.680,0.677 | Locate the primary implementation file first, then implement incrementally; Distinguish explicit pk assignment from default-generated pk in save(); Prioritize direct file paths for admin field display issues; Identify the settings file early and make targeted changes |
| 15022 | 得 | Submitted | 1 | 0.741,0.730,0.725,0.724 | Queryset deduplication needed for limit_choices_to with joins; Composed Query State Isolation in Django ORM; Efficient Reproduction Strategy for JSON/Admin Issues; Prioritize direct file paths for admin field display issues |
| 16082 | 得 | Submitted | 1 | 0.841,0.754,0.731,0.728 | Locate expression type resolution logic early; Test field.to_python() with edge-case input types before fixing conversion logic; Identify the ORM filter preparation layer early for value-type issues; Composed Query State Isolation in Django ORM |
| 16899 | 得 | Submitted | 1 | 0.749,0.739,0.735,0.720 | Prioritize direct file paths for admin field display issues; Model instances should bypass filterable checks; App label case sensitivity in field deconstruction; ModelChoiceField error message parameter passing pattern |
| 16901 | 得 | Submitted | 1 | 0.731,0.727,0.724,0.723 | Model instances should bypass filterable checks; Locate expression type resolution logic early; Identify the ORM filter preparation layer early for value-type issues; Distinguish explicit pk assignment from default-generated pk in save() |
| 14170 | 失 | LimitsExceeded | 0 | 0.735,0.722,0.716,0.712 | Annotations must be propagated when creating subqueries in split_exclude(); Use SQL generation debugging to compare working vs broken queries; Identify the ORM filter preparation layer early for value-type issues; Composed Query State Isolation in Django ORM |
| 14493 | 失 | Submitted | 1 | 0.685,0.681,0.677,0.676 | Always inspect generated patches for duplication and syntax errors before submission; Identify the exact file and method containing the bug before exploration; Prioritize targeted grep searches over sequential file reading; Identify the ORM filter preparation layer early for value-type issues |
| 14999 | 失 | LimitsExceeded | 0 | 0.745,0.737,0.725,0.719 | ForeignKey assignment with non-auto primary keys requires deferred update logic; ForeignKey attname vs field name distinction in query resolution; Multi-table inheritance primary key reset requires parent-child synchronization; Use quote_name() for all SQL identifiers in backend-specific code |
| 15278 | 失 | LimitsExceeded | 0 | 0.704,0.698,0.688,0.687 | ModelChoiceField blank option logic is field-level, not widget-level; Converters not applied to RETURNING clause results in insert/bulk_create; Use quote_name() for all SQL identifiers in backend-specific code; App label case sensitivity in field deconstruction |
| 15380 | 失 | LimitsExceeded | 0 | 0.757,0.733,0.728,0.724 | Write minimal reproduction tests early, using existing test patterns; Prioritize direct file edits over exploratory searches in large codebases; Start with test-driven understanding for migration-related issues; Use __qualname__ for nested class serialization in migrations |
| 15467 | 失 | LimitsExceeded | 0 | 0.783,0.723,0.718,0.709 | ModelChoiceField blank option logic is field-level, not widget-level; ForeignKey validation should use _base_manager, not _default_manager; Use __qualname__ for nested class serialization in migrations; Field comparison must handle uninitialized model attribute |
| 15499 | 失 | LimitsExceeded | 0 | 0.653,0.642,0.635,0.634 | Test CheckConstraint SQL generation with mixed OR/AND operators before migration; Use existing test infrastructure for migration operations; Leverage existing test infrastructure before building custom tests; Efficient root cause isolation for field behavior issues |
| 15814 | 失 | LimitsExceeded | 0 | 0.746,0.741,0.726,0.719 | Efficient Diagnosis Strategy for Query State Bugs in Django; Deletion operations should use .only() to fetch minimal fields; Annotations must be propagated when creating subqueries in split_exclude(); Composed Query State Isolation in Django ORM |
| 15930 | 失 | LimitsExceeded | 0 | 0.743,0.736,0.736,0.735 | Investigate query state isolation in combinator operations; Test aggregation queries with various order_by() variants early; Use SQL generation debugging to compare working vs broken queries; Filter non-groupable expressions from ORDER BY in GROUP BY logic |
| 16502 | 失 | LimitsExceeded | 0 | 0.731,0.684,0.681,0.678 | Always inspect generated patches for duplication and syntax errors before submission; Complete the full test-verify-confirm cycle before declaring success; Use Django's test runner (runtests.py) instead of standalone scripts for validation; Locate the implementation first, then understand the issue |

得失两边的 cosine 分布看不出差别（得的 top-1 中位约 0.74，失的也约 0.74），也看不出某类标题偏向哪一边。

### 2.5 L1 库的冗余

SWE 的 L1 冗余很低，与 WebArena 形成对照。在存储的 bge-small embedding 上算成对 cosine：

| 库 | n | 对数 | 中位 | p90 | p97 | 最大 | ≥0.88 | ≥0.85 | ≥0.80 | ≥0.75 | 贪心聚类 @0.88 | @0.80 | 标题/内容精确重复 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bank_l1 | 185 | 17,020 | 0.622 | 0.696 | 0.736 | 0.904 | 2 | 23 | 81 | 319 | 183 | 135 | 0 / 0 |
| bank_l2 | 58 | 1,653 | 0.614 | 0.682 | 0.728 | 0.901 | 1 | 4 | 17 | 35 | 57 | 42 | 0 / 0 |
| bank_success | 26 | 325 | 0.632 | 0.714 | 0.786 | 0.901 | 1 | 3 | 8 | 18 | 25 | 18 | 0 / 0 |
| memory.json | 243 | 29,403 | 0.617 | 0.690 | 0.730 | 0.965 | 13 | 50 | 150 | 495 | 232 | 157 | 0 / 0 |
| L1 × L2 交叉 | 185×58 | 10,730 | — | — | — | 0.965 | 10 | — | 52 | — | 9 条 L2 有 ≥0.88 的 L1 邻居 | — | — |

同一源题的 L1 对（94 对）平均 cosine 0.732，跨题 0.622，同题对里只有 1.1% 到 0.88。最近的两对是 0.904 的 "Window functions with DecimalField bypass SQLiteNumericMixin casting" 对 "Test window functions with DecimalField on SQLite before submission"，和 0.885 的两条 runtests.py 建议。交叉层最高 0.965 是 L1 "Annotations must be propagated..." 对 L2 "Annotations must be copied..."。

### 2.6 bank@116 / @180 / @180 去新 L1 切片

这组切片是 SWE 上唯一一次直接"拿掉 L1"的实验。库快照都在 `runs/swe_tail_20260713_135958/`，swe_tail 是从 243 条库继续学 110 道 django 题的续跑（自己的 idx 从 1 重数，对应总体第 116–225 题），写了 158 条 L1（79 题 ×2）和 68 条 L2，14 次 close-vote 跳过，最终库 469 条，$120.65 时 BudgetExceeded 停下。`n_memory` 第一次到 367 是在 tail idx 64（django-15629），所以 "@180" 是名义值，实际是 115+64=179 道 withmem 题之后的快照。切片题 = tail idx 65–110 的 46 题，`skip_for_slice.json` 里 183 条 = 115 big 预测 + 64 tail 题 + 4 道从未跑过的题（17029、9296、17084、17087）。

| 库 | 条数 | L1 | L2 | 合并改写项 | outcome fail/succ/unverified | 来历 |
|---|---|---|---|---|---|---|
| bank_A_116.json | 243 | 185 | 58 | 0 | 217/26/0 | 与 swe_big memory.json id 集相同 |
| bank_B_180.json | 367 | 275 | 92 | 0 | 319/46/2 | A + tail 写的 90 L1（45 题 ×2）+ 34 L2（17 题） |
| bank_C_180noL1.json | 277 | 185 | 92 | 0 | 231/46/0 | B 减去 tail 期写的 90 条 L1（88 failure + 2 unverified），原 185 条 L1 保留；= A ∪ 34 新 L2 |
| bank_B_cons_085.json | 313 | 212 | 60 | 41 | 282/29/2 | `scripts/consolidate_bank.py` 对 B，阈值 0.85，未评测 |
| bank_B_cons_080.json | 237 | 125 | 35 | 77 | 218/17/2 | 阈值 0.80，slice_Bcons 用的这个 |
| bank_B_consolidated.json | 69 | 15 | 5 | 49 | 63/6/0 | 默认阈值 0.7，未评测 |
| memory.json（tail 末） | 469 | 343 | 126 | 0 | 401/64/4 | 全部 110 题之后 |

四个切片臂协议相同：frozenmem，每题 1 attempt，k=4 每题注 4 条，gate none，plain，claude-haiku-4-5 温度 0.7，step_limit 60，judge gpt-4o-mini，seed 0，并发 8，每臂花 $9.6–9.9。

| 臂（run） | 库 | resolved/46 | judge_sr | 注入槽 L1/L2/合并项 | 用到的不同项 | 新 L1 槽（题数） | 对 nomem 21/46 | 对 A |
|---|---|---|---|---|---|---|---|---|
| A（slice_A116_20260713_213036） | 243 | 23（50.0%） | 0.609 | 132/52/0 | 87 | 0 | +4 −2 | — |
| B（slice_B180_20260713_215708） | 367 | 19（41.3%） | 0.500 | 126/56/0（+2 未匹配） | 103 | 35（26） | +2 −4 | −6 +2 |
| C（slice_C180noL1_20260713_222308） | 277 | 20（43.5%） | 0.478 | 116/66/0（+2 未匹配） | 93 | 0 | +2 −3 | −5 +2 |
| Bcons（slice_Bcons_20260714_072730） | 237 | 21（45.7%） | 0.522 | 64/36/84（合并项按'标题不匹配任何 swe_write 事件'认定，库文件无合并标记） | 78 | 19（16） | +3 −3 | −5 +3 |
| nomem（gt_big_nomem 同题） | — | 21（45.7%） | — | — | — | — | — | −4 +2 |
| 流式续学臂（gt_tail 同题） | 243→469 | 20（43.5%） | — | — | — | — | +3 −4 | −6 +3 |

双侧精确 sign test 没有一对显著：A vs B +6 −2（p=0.29），A vs C +5 −2（p=0.45），A vs Bcons +5 −3（p=0.73），A vs nomem +4 −2（p=0.69）；B vs C 是 B 独有 2 题（16502、16819）、C 独有 3 题（15987、16136、16901），拿掉 90 条新 L1 只挪了 1 题。更关键的是新 L1 落到了哪些题上：B 臂里 26 道题收到了新 L1，这 26 题 B 解出 12 题，同 26 题在 A 臂（无新 L1）解出 11 题——B 的亏损并不在有新 L1 的题上。按轨迹里的 `<memory>` 块逐字节比对，A 与 B 注入完全相同的 14 题 A 胜 4、B 胜 0，注入不同的 32 题 2:2（平均 4 条里 1.75 条不同）；A 与 C 相同的 29 题 4:0，不同的 17 题 1:2；B 与 C 相同的 20 题 0:2，不同的 26 题 2:1。"库越大越差"的差额全部落在提示词完全一致的题上，所以不可能是内容效应。HANDOFF.md:103 在 2026-07-16 把它归因为前一臂的 harness 评测容器与下一臂并跑造成的机器负载不对称加单样本方差（A、B、C 在 07-13 21:30 到 22:50 背靠背跑完，间隔 3–4 秒；没有评测时间戳文件可以验证这个解释）。`scripts/consolidate_bank.py:3-5` 的 docstring 仍然保留着被撤回的读法（"243 items helped (+4.3), 277+ hurt, and the damage is layer-agnostic"），`README.md:164` 也还写着切片"正在跑"；HANDOFF.md:123 提到的"判读表"在仓库和 git 历史里都不存在。

### 2.7 四次重复：global vs repo bank

2026-07-17 的 fc_* 战役给出了 SWE 上唯一的重复度量。三个 repo，每个 3 个 seed，三臂：nomem；repo（各 repo 自己的库，scope 过滤）；global（`runs/fc_global_bank.json`，393 条 = django 243 + sympy 82 + sphinx 68，按层 295 L1 + 98 L2，`memory_scope=global` 全池检索）。测试集 django 114（同上 holdout）、sympy 35（75 减 40 学习题）、sphinx 14。

| repo (n) | 臂 | 库 | s1 | s2 | s3 | 均值 % |
|---|---|---|---|---|---|---|
| django (114) | nomem | — | 48 (42.1) | 52 (45.6) | 58 (50.9) | 46.2 |
| django (114) | repo | django 243（185 L1 + 58 L2） | 53 (46.5) | 52 (45.6) | 49 (43.0) | 45.0 |
| django (114) | global | 393（295 L1 + 98 L2），跨 repo 槽位 5% | 45 (39.5) | 50 (43.9) | 54 (47.4) | 43.6 |
| sympy (35) | nomem | — | 16 (45.7) | 18 (51.4) | 17 (48.6) | 48.6 |
| sympy (35) | repo | sym_stream 82（58 L1 + 24 L2） | 18 (51.4) | 17 (48.6) | 15 (42.9) | 47.6 |
| sympy (35) | global | 393，跨 repo 槽位 19% | 18 (51.4) | 20 (57.1) | 15 (42.9) | 50.5 |
| sphinx (14) | nomem | — | 5 (35.7) | 7 (50.0) | 4 (28.6) | 38.1 |
| sphinx (14) | repo | sphinx_learn 68（52 L1 + 16 L2） | 6 (42.9) | 6 (42.9) | 3 (21.4) | 35.7 |
| sphinx (14) | global | 393，跨 repo 槽位 16% | 5 (35.7) | 5 (35.7) | 5 (35.7) | 35.7 |

合并 163 题同 seed 配对：repo vs nomem +38 −44（p=0.58），global vs nomem +33 −41（p=0.42），global vs repo +36 −38（p=0.91）。同臂不同 seed 的差距才是这里的主角：django nomem s1 vs s3 是 +4 −14，一次配置没动的 8.8 分摆动。global 臂的注入在 seed 间是确定的（`memory_scope=global` 检索无随机），django global 注入 335 L1 / 116 L2，repo 337 L1 / 118 L2。

回到 L1-only 的 49/114：对四次 nomem（49、48、52、58），它的差是 0、+1、−3、−9；它对原 nomem 的 10 胜里 9 题在四次 nomem 之间本来就翻来翻去，10 负里也有 9 题是翻转题；114 题里 44 题四次 nomem 都没解出、32 题四次都解出。P2 的"冻结 243 vs 续学 243→469"在两者都做过的 110 题上是 54 对 45（nomem 46），+17 −8，双侧精确 sign test p=0.108（HANDOFF.md:101 记的是 0.054，即同一检验的单侧值）。在官方步数预算下（`runs/align_default_20260713_225859`），nomem 82/114 对冻结 243 库 83/114。

## 3. Mind2Web

先说清来源：本机上没有任何 Mind2Web 的 run 目录、库文件、events.jsonl 或 data/ 目录（`runs/*/summary.json` 中无 `test_split`，`events.jsonl` 中无 `step_write_l1`/`stream_step`/`test_episode`，无 `runs/stream_*` 或 `runs/m2w_*`）。m2w 代码在 42b072b（2026-07-03）一次落地后未改过；下面所有数字都是 `HANDOFF.md`（db05b24、a78e62f，同日）的转录，无法重算。

### 3.1 静态 held-out A/B（49 题 / 334 步）

协议是按站点 50% 留出（每站 `max(1, int(n*0.5))` 题进 learn，单题站只进 test），共用 nomem 基线，element_acc 0.353（`HANDOFF.md:197-198`）。用的模型、脚本、k_fact、阈值都没有记录——49 题不匹配任何脚本默认的 TLIM（40/60/30），后来的文档（`SCORES_VS_COMPETITORS.md:36`）断言是 gpt-4o-mini。

| 臂 | 库 | Δ element_acc | Δ step_success | 规模 | 来源 |
|---|---|---|---|---|---|
| nomem | — | 0.353（绝对值） | 未记录 | 49 题 / 334 步 | HANDOFF.md:198 |
| L1-only（`--m2w.layer2 off`） | 104 条 L1 | +0.021 | +0.054 | 49 题 | HANDOFF.md:199 |
| L2-only（`--m2w.layer1 off`） | 40 条 L2 | +0.024 | +0.033 | 49 题 | HANDOFF.md:200 |
| L1+L2 合并 | 未记录（现有文档写 144 = 104+40 是假设；FactStore 按 (scope,key) upsert，真值 ≤144） | −0.009 | 未记录 | 49 题 | HANDOFF.md:201 |
| L1-only（pilot） | 未记录 | +0.036 | 未记录 | 14 题 pilot | HANDOFF.md:202 |
| L2-only（pilot） | 未记录 | +0.062 | 未记录 | 14 题 pilot | HANDOFF.md:202 |
| test-on-learn 正向对照（泄漏） | learn 库 | — | +15（单位未写） | 40 题 | HANDOFF.md:204；`scripts/run_m2w_poscontrol.sh` |

这是整个项目里 L1 单独为正的唯一记录，但有两个附注。其一，Mind2Web 的 L1 由 `judge_step` 产生，gold 控件是解析后直接给模型的，所以它不是 WA/SWE 意义上的答案盲 L1。其二，从 14 题 pilot 到 49 题，L1 的 +0.036 缩到 +0.021（−42%），L2 的 +0.062 缩到 +0.024（−61%），HANDOFF 自己的读法是"之前的大数有方差成分"。按条效率算，element_acc 上 L2 每条 0.00060 对 L1 每条 0.00020（3 倍），step_success 上 0.00083 对 0.00052（1.6 倍）；L1 总量 step_success 赢，L2 总量 element_acc 赢，比较结果随指标翻转。README.md:187 由此写下 "实测 40 条 L2 ≈ 104 条 L1 的效果"。

L1-only 库在 334 步上的逐步分桶（`HANDOFF.md:176-184`；步数是按比例算的）：40%（≈134 步）两臂都错且库里没有相关 fact；26%（≈87）两臂都对；14%（≈47）两臂都错但相关 fact 在库里（注了没转化）；11%（≈37）REUSED（nomem 错→withmem 对）；8%（≈27）MISLED（nomem 对→withmem 错）；净 +10 步。注入 fact 命中当前 gold 控件的步只有 31%，69% 离题；按 top-4 每步 ≤1 条有用倒推，有用项占比 ≤7.8%，与 HANDOFF 的"~89% 没用"一致。MISLED 几乎全是"注入了与当前子目标不匹配的 fact"——FactItem 存了 `condition`（intent）字段但检索从未用它过滤（`store.py:93-104` 只按 scope 和 cosine），这是后来 SWE/WA 加 LLM 注入门控的直接源头。

### 3.2 流式自进化（40 题、n_traj=5、两层都开、新 L1 抽取器）

| 量 | 值 | 来源 |
|---|---|---|
| 相对配对 nomem 流的总 step_success Δ | +0.009 | HANDOFF.md:203 |
| 前半程 gap | −0.013 | HANDOFF.md:203 |
| 后半程 gap | +0.028 | HANDOFF.md:203 |
| 40 题后库大小 | 218 条（L1/L2 拆分未记录；≈5.45 条/题） | HANDOFF.md:203 |
| 旧抽取器（旧 L1+旧 L2）流 | step_success 0.35 → 0.32，净负 | HANDOFF.md:205；db05b24 HANDOFF.md:15 |
| stream_L1 / stream_L2 / stream_L1L2（各 40 题） | 2026-07-03 排队，结果从未记录 | HANDOFF.md:243-244 |

抽取器重写前的 L1 病症（`HANDOFF.md:186`）：反 gold（gold=Category 却写 "click Size"）、93% 否定句、92% 来自错步、带任务原话、同站矛盾。重写后 L1 触发频率仍是每 (attempt, step) 一次，n_traj=5 时一个分叉步最多写 5 条（只靠 key 碰撞去重），L2 每步最多一次且只在 0<n_correct<n 时；提示词要求至多 3 条但代码不切片（`brain.py:498-506` 只过 `_is_abstract_site_fact`），不像 SWE/WA 那样按 max_items 硬切（`m2w/run.py:206-283`、`brain.py:484`）——这就是"L1 洪水"的机械来源（104 对 40）。流式 L1-only 的数据点（stream_L1）丢失了。

### 3.3 其他

`SCORES_REPORT.md:7` 的 "65.4% → 74.6% (+9.2)"、`PAPER_MAIN_TABLE*.md` 的 "+9.8 另机" 和 "+5.4 本机" 都没有对应工件；+5.4 可能就是 L1-only 的 step_success +0.054，这是推断。七个 `run_m2w*.sh`（ab / channels / perstep / abc 等）的臂结果没有任何记录。唯一残存的 Mind2Web 原始 item 是 README.md:45-68 贴的 8 条 L1 与 7 条 L2 示例。

## 4. WebArena：L1 被注入的时代（2026-07-18 → 07-21）

### 4.1 时间线与当时的代码

`wa.inject_only_l2` 第一次出现在 `runs/wa_gitlab_20260721_133636_20260721_133638` 的 run_start（07-21 13:36，0 题完成即中止）；之前 07-18 到 `wa_gitlab_20260721_101118` 的所有 run 配置里没有 inject_only_l2 也没有 inject_gate，检索是按 scope 过滤后对整个 reasoning 池做 cosine top-k，L1、L2 混池（b08f899 的 `run.py:153` `topk_scored(intent, retrieve_k, thr, scope=scope)` 无 layer 参数）。第一个带该 flag 完整跑完的是 `wa_gitlab_20260721_134130`（withmem 0.5581）；`inject_gate=llm`（fetch_k 5）从 `wa_gitlab_20260721_184102` 开始，第一个完整 gate run 是 `wa_gitlab_20260721_220729`（0.4884）；07-22 `wa_gitlab_20260722_022526` 加了答案盲写手得 0.7907。

那个时代的写手和今天不同。07-19 的代码不在 git 里（第一个提交 b08f899 是 07-20 21:22），从配置 `l1_max_per_task=2` 和观测到的写入量（七个 n_traj=1 run 的 L1/失败 rollout = 2.00、2.00、1.87、1.87、1.83、1.93、1.67）推断当时每个失败 rollout 写 2 条 L1。b08f899 起 `reflect_trajectory` 改为 `max_items=1`，且 `wa.l1_fluke=on`（默认）时 fluke rollout（reward=1 但 judge 未 verified）也写 L1，所以 07-20/07-21 的 n_traj=8 库里含 fluke 来源的 L1（181038：55 条 outcome=success；223735：25 条 unverified；101118：32；134130：26）。当时的 `_L1_SYS` 是 "Reflect on WHY, then extract lessons that prevent this failure (or turn luck into a reliable procedure)"，judge 是 label-free（无参考答案），没有禁令守卫也没有 LLM 门控。所以这批 run 只能当背景，不是当前机制的 L1-only 消融。

### 4.2 主要 run 一览

| run（runs/） | 模型 | site | 臂 | n_traj | k | inject_only_l2 | gate | memory_in | summary（n, reward_sr, l1w, l2w） | memory.json（总; L1/L2） | wa_retrieve 非空/总 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| wa_smoke_20260718_013619 | haiku-4-5 | reddit | nomem | 1 | 2 | 无 | 无 | — | (1, 0.0) | 无 | 0/0 | smoke |
| wa_calib_reddit_20260718_015125 | haiku-4-5 | reddit | nomem | 1 | 2 | 无 | 无 | — | (25, 0.0) | 无 | 0/0 | 25 个 episode error |
| wa_calib2_reddit / wa_calib2_shopping / wa_calib3_shopping / wa_calib3_reddit（07-18） | gpt-5-mini | — | nomem | 1 | 2 | 无 | 无 | — | 0.44 / 0.04 / 0.20 / 0.68（各 25） | 无 | 0/0 | 校准 |
| wa_reddit_ab_20260718_030719 / 031900 / 043329 | gpt-5-mini | reddit | nomem,withmem | 5 | 2 | 无 | 无 | — | 无 summary | 无 | — | 中止 |
| wa_reddit_ab_20260718_050736 | gpt-5-mini | reddit | nomem,withmem | 5 | 2 | 无 | 无 | — | nomem (25, 0.48); withmem (25, 0.44, 50, 18) | 68; 50/18 | 24/25 | 注入 39 L1 + 9 L2 |
| wa_shopping_gpt5_6sol_20260718_103827 / 105813 / 131645 | gpt-5.6-sol | shopping | nomem,withmem | 5 | 2 | 无 | 无 | — | 无 | 无 | — | 中止 |
| wa_shopping_gpt5_6sol_20260718_110832 | sol | shopping | nomem,withmem | 5 | 2 | 无 | 无 | — | nomem (25, 0.44); withmem (25, 0.40, 54, 1) | 55; 54/1 | 24/25 | 注入 48 L1 |
| wa_shopping_admin_gpt5_6sol_20260718_162602 | sol | shopping_admin | nomem,withmem | 5 | 2 | 无 | 无 | — | nomem (40, 0.525); withmem (40, 0.55, 46, 16) | 62; 46/16 | 38/40 | 注入 44 L1 + 32 L2；$48.7 |
| wa_sa_ablation_20260718_205705 | sol | shopping_admin | nomem,frozenmem | 5 | 2 | 无 | 无 | ..._162602/memory.json | nomem (40, 0.675); frozenmem (40, 0.650) | 冻结 62 | 40/40 | 注入 38 L1 + 42 L2；$74.6 |
| wa_sa_abl10_20260719_025955 | sol | shopping_admin | nomem,frozenmem | 10 | 2 | 无 | 无 | 同上 | 无 summary（30 对：0.5667 vs 0.6333） | 冻结 62 | 31/31 | 注入 36 L1 + 24 L2；未跑完 |
| wa_reddit_20260719_151957 | sol | reddit | nomem,withmem | 1 | 1 | 无 | 无 | — | 0.6364 vs 0.6364 (11, 8, 0) | 8; 8/0 | 9/11 | 全 L1 |
| wa_shopping_admin_20260719_154107 | sol | shopping_admin | nomem,withmem | 1 | 1 | 无 | 无 | — | nomem (88, 0.2159); withmem (88, 0.0, 0, 0) | 0 | 0/88 | 147 个 episode error，坏 run |
| wa_gitlab_20260719_161748 | sol | gitlab | nomem,withmem | 1 | 1 | 无 | 无 | — | 0.6047 vs 0.6279 (43, 32, 0) | 32; 32/0 | 39/43 | $23.5 |
| wa_gitlab_20260719_161841 | sol | gitlab | nomem,withmem | 1 | 1 | 无 | 无 | — | 0.6744 vs 0.6512 (43, 28, 0) | 28; 28/0 | 39/43 | $26.2；与 161748 相隔 53 秒同配置 |
| wa_shopping_20260719_161803 | sol | shopping | nomem,withmem | 1 | 1 | 无 | 无 | — | 0.5682 vs 0.5568 (88, 73, 0) | 73; 73/0 | 87/88 | $42.6 |
| wa_shopping_admin_20260719_182647 | sol | shopping_admin | nomem,withmem | 1 | 1 | 无 | 无 | — | 0.6591 vs 0.6705 (88, 53, 0) | 53; 53/0 | 85/88 | $64.4 |
| wa_gitlab_20260719_202833 | sol | gitlab | nomem,withmem | 1 | 1 | 无 | 无 | — | 0.7907 vs 0.6512 (43, 29, 0) | 29; 29/0 | 39/43 | "checks-not-procedures" 写手；$28.0 |
| wa_gitlab_20260720_020100 | sol | gitlab | nomem,withmem | 1 | 1 | 无 | 无 | — | 0.7907 vs 0.7209 (43, 20, 0) | 20; 20/0 | 38/43（门控只在 8/43 题用了记忆） | confidence_gate=on；$33.8 |
| wa_rep_shopping_admin / wa_rep_gitlab（07-20 1529） | sol | — | nomem,frozenmem | 5 | 1 | 无 | 无 | 182647 / 161841 库 | 无（1 / 5 题） | — | 0 | 中止 |
| wa_gitlab_20260720_162237 / 192310 / 193118 / 210249 / 223318 | sol | gitlab | withmem | 8 | 1 | 无 | 无 | — | 无 summary（8 / 38 / 41 / 24 / 1 题） | — | — | 中止；193118 41 题 nc/n 均值 0.689（rollout[0] 0.756），注入 28 L1 / 9 L2 |
| wa_gitlab_20260720_181038 | sol | gitlab | withmem | 8 | 1 | 无 | 无 | — | (43, 0.7209, 225, 27) | 252; 225（55 fluke）/27 | 39/43 | 注入 33 L1 + 6 L2；$246.2 |
| wa_gitlab_20260720_223735 | sol | gitlab | withmem | 8 | 1 | 无 | 无 | — | (43, 0.5814, 148, 14) | 162; 148（25 unverified）/14 | 39/43 | 注入 28 L1 + 11 L2；$314.6 |
| wa_gitlab_20260721_101118 | sol | gitlab | withmem | 8 | 1 | 无 | 无 | — | (43, 0.6047, 150, 16) | 166; 150（32 unverified）/16 | 39/43 | 注入 24 L1 + 15 L2；$198.9；最后一个混池 run |
| wa_gitlab_20260721_133636 | sol | gitlab | nomem,withmem | 8 | 1 | True | 无 | — | 无（0 题） | 无 | 0 | 第一个带 flag，中止 |
| wa_gitlab_20260721_134130 | sol | gitlab | withmem | 8 | 1 | True | 无 | — | (43, 0.5581, 155, 26) | 181; layer 字段 155/26 | 39/43 | 注入 39 L2 + 0 L1；$251.9 |
| wa_gitlab_20260721_184102 / 201502 / 213418 | sol | gitlab | withmem | 8 | 1 | True | llm | — | 无（18 / 34 / 3 题） | 201502: 146（133/13） | — | 中止 |
| wa_gitlab_20260721_220729 | sol | gitlab | withmem | 8 | 1 | True | llm | — | (43, 0.4884, 115, 25) | 140; 115/25 | 31/43 | 注入 31 L2；$192.1 |
| wa_gitlab_20260722_022526 | sol | gitlab | withmem | 8 | 1 | True | llm | — | (43, 0.7907, 63, 11) | 74; 63/11 | 21/43 | 注入 21 L2；$292.2；答案盲写手 |

表里未列的同时期 run（都带 run_start）：wa_gitlab_20260719_154107（32 个 wa_task，n_traj=1 批的中止同胞）、wa_gitlab_20260719_161510（4 题）、wa_shopping_20260719_154107（50 题，中止）、wa_sa_v2stream_20260719_135816（n_traj=5 withmem，6 题，写 4 L1）、wa_sa_smoke2_20260718_162245（2 题）、wa_shopping_admin_gpt5_6sol_20260718_133050_STALE_fmtbug 与 _150035_STALE_barebug（41/42 题，有 L1/L2 写入，带 bug）、wa_vfy_175021（n_traj=8，4 题，37 L1 + 2 L2）、wa_partest_172956（6 题，6 L1 + 8 L2）。

07-21 之前的 memory.json 没有 layer 字段，表里的 L1/L2 是把 item 标题与同 run 的 `wa_write_l1`/`wa_write_l2` 事件匹配得到的（0 条未匹配）；冻结库消融用源 run 的事件。

### 4.3 事实上的 L1-only 臂：七个 n_traj=1 配对 run

n_traj=1 时 L2 永远不会被写（需要 >1 个 rollout 才有 contrast），所以 07-19/07-20 的七个两臂 run 的 withmem 库是 100% L1，每次注入（k=1，无门控）也都是 L1，每个检索到的标题都能配到一个 `wa_write_l1` 事件。这是 WebArena 上唯一 L1 被单独注入的数据。

| run | site | n | nomem | withmem | Δ | withmem 赢（task） | withmem 输（task） | 平 | 注入题数 | 注入题上 SR nomem/withmem | 库（L1） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| wa_reddit_20260719_151957 | reddit | 11 | 0.6364 | 0.6364 | 0 | — | — | 11 | 9 | 0.667 / 0.667 | 8 |
| wa_gitlab_20260719_161748 | gitlab | 43 | 0.6047 | 0.6279 | +0.023 | 170, 172, 783 | 168, 788 | 38 | 39 | 0.590 / 0.615 | 32 |
| wa_gitlab_20260719_161841 | gitlab | 43 | 0.6744 | 0.6512 | −0.023 | 136, 309 | 304, 784, 787（787 是 withmem 报错） | 38 | 39 | 0.667 / 0.641 | 28 |
| wa_shopping_20260719_161803 | shopping | 88 | 0.5682 | 0.5568 | −0.011 | 191, 313 | 126, 166, 385 | 83 | 87 | 0.575 / 0.563 | 73 |
| wa_shopping_admin_20260719_182647 | shopping_admin | 88（4 题 nomem 报错） | 0.6591 | 0.6705 | +0.011（剔报错 84 题：0.690 / 0.667，−0.024） | 6, 120, 131, 213, 246（另 123, 212, 288 是 nomem 报错） | 65, 116, 185, 195, 196, 197, 217 | 73 | 85 | 0.659 / 0.671 | 53 |
| wa_gitlab_20260719_202833（守卫写手） | gitlab | 43 | 0.7907 | 0.6512 | −0.140 | 305 | 135, 136, 303, 312, 315, 785, 787 | 35 | 39 | 0.769 / 0.641 | 29 |
| wa_gitlab_20260720_020100（confidence gate） | gitlab | 43 | 0.7907 | 0.7209 | −0.070 | 135 | 168, 309, 349, 785 | 38 | 检索 38/43，门控只在 8 题用了记忆 | 0.816 / 0.711 | 20 |

七个 run 相加是 359 个任务对，原始 reward 下 withmem 赢 17、输 26（双侧 sign test p=0.22；剔除 4 个报错 episode 后是 355 对、赢 14、输 25，p=0.11）。WA_FINDINGS.md:341-352 的账本用的是剔报错口径，所以 admin 一行在那里是 −2.4 而不是 +1.1。注入每题一条，mem_chars 431–855 字符；除 reddit（9 次注入 3 个标题）外每个 run 用到的不同标题只有 11–25 个（shopping 87 次注入 25 个标题，admin 85 次 24 个，gitlab 39 次 11–12 个），早写的几条 L1 被反复注入。

confidence gate 那个 run 需要单独解释：`wa_gate` 事件显示 35 题模型自信、没用记忆，用了记忆的 8 题（t168、306、307、309、783、785、786、789）solo_reward 与 scored_reward 全部相同（2 对 6 错）——记忆没有改变任何一题的结果，那 −7.0 分是两次独立抽样的噪声，不是 L1 的效应。守卫写手 run（202833，写手被改成"写检查而不是流程"）的 −14.0 是这批里唯一超出 nomem 自身摆动的：四个零错误同配置 gitlab nomem run（161748、161841、202833、020100）分别对 26、29、34、34 题，25 题四次都对，6 题四次都错（296、297、306、307、317、786），12 题翻来翻去；161748 与 161841 相隔 53 秒启动、配置完全一样，nomem 在 43 题里有 3 题不一致。所以单次臂差 ±2 到 ±7 题都在噪声里。

07-19 的"165 题修正后 pass@1"是这样得来的：`scripts/analyze_corrected4.py runs/regrade_output.json runs/regrade_admin_output.json` 对 reddit 151957（主指标题 9）、gitlab 161841（40）、shopping 161803（54）、shopping_admin 182647（62）共 165 道 exact+must_include 题做严格重判，nomem 原始 106/165=64.2% 修正后 119/165=72.1%，withmem 102/165=61.8% 修正后 116/165=70.3%，Δ −1.8；8 胜 11 负。19 道翻转题每题恰好注了 1 条 L1：

| site（run） | n | nomem 原始→修正 | withmem 原始→修正 | Δ | 胜：注入的 L1 标题 | 负：注入的 L1 标题 |
|---|---|---|---|---|---|---|
| reddit（151957） | 9 | 5→5 (56%) | 5→6 (67%) | +11 | t66 'Navigate from newest forum post to full comment history'（541 字） | — |
| gitlab（161841） | 40 | 26→32 (80%) | 25→31 (78%) | −2 | t136 'Open the repository's commit history'（552）；t309 'Use the instance's commit history and valid filters'（760） | t304 'Count every visibly matching commit'（610）；t784 & t787 'Use the dedicated Contributors report'（518） |
| shopping（161803） | 54 | 27→33 (61%) | 25→31 (57%) | −4 | — | t126 'Verify both visible price endpoints'（675）；t385 'Open the product's Reviews tab'（500） |
| shopping_admin（182647） | 62 | 48→49 (79%) | 47→48 (77%) | −2 | t6 'Use the filterable Bestsellers report'（551）；t131 'Use the status-filterable Orders Report'（532）；t212 & t288 'Audit every page and reconcile customer groups'（613）；t246 'Inspect the complete review set before summarizing dislikes'（620） | t65 'Choose the report that matches the constraint'（574）；t116 'Use the actionable reviews grid'（481）；t185 'Use the Products grid and apply an exact Quantity range'（570）；t195 'Read and sum visible Total Paid values'（592）；t196 & t197 'Verify Total Paid in each order detail'（528） |
| 合计 | 165 | 106→119 (64.2→72.1) | 102→116 (61.8→70.3) | −1.8 | 8 | 11 |

"11 REGRESSIONS (misapplication)"、"GUARDRAIL FAILED" 这些原话不在仓库文档里，只在 `~/.claude/.../memory/hipo-agent-webarena-first-result.md:28-32`；仓库里的对应记载是 `RETRIEVAL_INJECTION_ABLATIONS.md:31` 的"8 道真救活 vs 11 道误用回退"。现有 L1_ONLY_ABLATION.md 第 47 行说"那 11 道回退里多数注的是 L1"，低估了：n_traj=1 下库里没有一条 L2，100% 注入的是 L1。`WA_FINDINGS.md:341-352` 的账本用原始 reward 把这批 run 列为独立行，并把整个时代归为噪声（1 rollout/臂时 ±14 分摆动）。

### 4.4 混池时代与 flag 前后

07-18 的两个冻结库消融混了两层，不能隔离 L1：`wa_sa_ablation_20260718_205705` 用 162602 的 62 条库（46 L1 + 16 L2），40 题 ×5 rollout，k=2，rollout[0] pass@1 nomem 0.675 对 frozenmem 0.650（逐题 frozenmem 好 2 题 t6、t120，差 3 题 t1、t5、t107）；按 5 个 rollout 的均值则是 0.620 对 0.645，frozenmem nc 更高 8 题（t3、5、62、63、108、113、120、122）、更低 5 题（t1、65、107、116、119），80 次注入是 38 L1 + 42 L2；`wa_sa_abl10_20260719_025955`（n_traj=10，30 对未跑完）rollout[0] 0.5667 对 0.6333；均值@10 0.5867 对 0.6267，好 4（t5、6、62、63）差 0，60 次注入 36 L1 + 24 L2。源流 run 162602 本身 nomem 0.525 对 withmem rollout[0] 0.55（均值@5 0.525），76 次注入 44 L1 + 32 L2。

07-20/07-21 的 gitlab n_traj=8 单臂 run 里 L1 占了注入的 62–85%。那个时代没有 nomem@8 基线，唯一的 nomem 参照是 n_traj=1 的 0.7907（202833/020100），协议不同，现有文档第 42 行把 withmem@8 均分与它并列比较是不对的。

| run | 注入 | nc/n 均值 | 8/8 题 | 0/8 题 | 混合 | t135 | t168 | t169 | t170 | t171 | t172 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| wa_gitlab_20260720_181038 | L1+L2 混（33 L1 + 6 L2） | 0.7035 | 23 | 5 | 15 | 4/8 | 3/8 | 8/8 | 1/8 | 8/8 | 8/8 |
| wa_gitlab_20260720_223735 | 混（28 + 11） | 0.5959 | 19 | 9 | 15 | 1/8 | 2/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| wa_gitlab_20260721_101118 | 混（24 + 15） | 0.5988 | 17 | 10 | 16 | 2/8 | 1/8 | 1/8 | 0/8 | 0/8 | 0/8 |
| wa_gitlab_20260721_134130 | 只 L2（39） | 0.6017 | 17 | 9 | 17 | 2/8 | 4/8 | 1/8 | 0/8 | 0/8 | 0/8 |
| wa_gitlab_20260721_220729 | 只 L2 经 LLM 门控（31） | 0.5029 | 4 | 12 | 27 | 1/8 | 6/8 | 0/8 | 0/8 | 0/8 | 5/8 |
| wa_gitlab_20260722_022526 | 只 L2 + 门控 + 答案盲写手（21） | 0.7907 | 31 | 6 | 6 | 0/8 | 6/8 | 8/8 | 8/8 | 8/8 | 8/8 |

最接近 inject_only_l2 关/开对照的是 0721_101118（0.6047，混池）对 0721_134130（0.5581，只 L2），同站、同模型、n_traj=8、k=1，但 L2 写手在同一次改动里被重写成 4 档 contrast，不是干净隔离。t169–172 在 0720–0722 各 run 的 withmem nc/8：181038 8,1,8,8；192310 0,0,0,1；193118 0,8,8,8；210249 0,0,0,0；223735 0,0,0,0；101118 1,0,0,0；134130 1,0,0,0；184102 0,0,0,0；201502 1,0,0,0；220729 0,0,0,5；022526 8,8,8,8。

### 4.5 那个时代的 L1 库

| run | n_traj | L1（outcome） | L2 | L1/失败 rollout | 有 L1 的题（每题条数分布） | L1 cos≥0.88 对 / ≥0.80 对 / 聚类@0.88 | L1 平均成对 cos | L1 平均字数 | l1_total @25/50/75/100% 题 |
|---|---|---|---|---|---|---|---|---|---|
| wa_shopping_gpt5_6sol_20260718_110832 | 5 | 54（全 failure） | 1 | 0.72（75 失败） | 25（{2:21,3:4}） | 23 / 124 / 39 | 0.666 | 455 | 12/27/39/54 |
| wa_shopping_admin_gpt5_6sol_20260718_162602 | 5 | 46 | 16（12 success, 4 failure） | 0.48（95） | 22（{2:20,3:2}） | 16 / 48 / 37 | 0.660 | 473 | 10/16/29/46（L2 4/4/6/16） |
| wa_reddit_ab_20260718_050736 | 5 | 50（48 failure, 2 unverified） | 18 | 0.72（69） | 25（{2:25}） | 11 / 56 / 43 | 0.629 | 671 | 无 l1_total 字段 |
| wa_reddit_20260719_151957 | 1 | 8 | 0 | 2.00（4） | 4（{2:4}） | 0 / 2 / 8 | 0.664 | 557 | 2/4/8/8 |
| wa_gitlab_20260719_161748 | 1 | 32 | 0 | 2.00（16） | 16（{2:16}） | 7 / 23 / 26 | 0.648 | 552 | 6/18/24/32 |
| wa_gitlab_20260719_161841 | 1 | 28 | 0 | 1.87（15） | 14（{2:14}） | 4 / 30 / 25 | 0.657 | 562 | 2/16/20/28 |
| wa_shopping_20260719_161803 | 1 | 73 | 0 | 1.87（39） | 39（{2:34,1:5}） | 30 / 137 / 59 | 0.664 | 553 | 26/40/60/73 |
| wa_shopping_admin_20260719_182647 | 1 | 53 | 0 | 1.83（29） | 29（{2:24,1:5}） | 11 / 67 / 44 | 0.665 | 559 | 10/25/44/53 |
| wa_gitlab_20260719_202833 | 1 | 29 | 0 | 1.93（15） | 15（{2:14,1:1}） | 3 / 32 / 26 | 0.676 | 473 | 4/10/19/29 |
| wa_gitlab_20260720_020100 | 1 | 20 | 0 | 1.67（12） | 12（{2:8,1:4}） | 2 / 10 / 18 | 0.635 | 671 | 3/8/13/20 |
| wa_gitlab_20260720_181038 | 8 | 225（170 failure, 55 fluke 'success'） | 27 | 2.21（102） | 22（{2:4,4:1,8:3,10:1,11:2,12:1,13:3,14:3,16:4}） | 188 / 1016 / 148 | 0.647 | 595 | 46/91/129/225（L2 6/12/18/27） |
| wa_gitlab_20260720_223735 | 8 | 148（123 failure, 25 unverified） | 14 | 1.06（139） | 26（{8:10,7:3,6:3,5:4,2:3,1:3}） | 431 / 2562 / 57 | 0.756 | 803 | 53/79/96/148 |
| wa_gitlab_20260721_101118 | 8 | 150（118 failure, 32 unverified） | 16 | 1.09（138） | 29 | 421 / 2357 / 58 | 0.747 | 787 | 42/70/96/150 |
| wa_gitlab_20260721_134130 | 8 | 155（129 failure, 26 unverified） | 26 | 1.13（137） | 28 | 440 / 3153 / 61 | 0.759 | 840 | 51/79/105/155 |
| wa_gitlab_20260721_220729 | 8 | 115（全 failure） | 25 | 0.67（171） | 35 | 190 / 1518 / 64 | 0.742 | 777 | 29/53/83/115 |
| wa_gitlab_20260722_022526 | 8 | 63（全 failure） | 11 | 0.88（72） | 12（{8:5,5:2,4:2,2:2,1:1}） | 102 / 440 / 28 | 0.746 | 762 | 14/30/38/63 |

07-20 之后大约六成 L1 在 0.88 处塌成近重复簇（一题 8 个 rollout 各写一次同一个坑），n_traj=8 库里 L1:L2 为 5.7–10.6 倍。

### 4.6 这个时代能不能隔离 L1 的效应

结构上只有三种可用性。七个 n_traj=1 配对 run 的库可证明是纯 L1（layer2_writes=0），给出 359 对、原始 reward 下 17 胜 26 负（剔除 4 个报错 episode 后 355 对、14 胜 25 负），但它们是流式（边写边从自己的库里检索）、每臂单次抽样、写手与今天不同，且 gitlab 上 nomem 对 nomem 的摆动就有 26 到 34 题。0721_101118 对 0721_134130 是混池对只 L2，但 L2 写手同时改了。07-18 的冻结库消融混两层，分不开。整个时期没有一个 run 的 `wa.layer1=off`（该时期 52 个带 run_start 的 wa_* 目录（含 smoke/partest/vfy）全是 layer1=True, layer2=True），也没有代码不变、只切 inject_only_l2 的配对。

## 5. WebArena 现在的 L1 统计（五个全集配对 run，2026-08）

五个 run 配置一致：gpt-5.6-sol，bge-small 嵌入，`wa.layer1=true`，`inject_only_l2=true`，`inject_gate=llm`，`retrieve_fetch_k=5`，`retrieve_k_reasoning=1`，`eval_rollouts=8`，`max_steps=30`，臂 nomem,withmem；map 用 `task_filter=readonly`，其余 all。这些 run 里 L1 只写不读：所有注入标题都能配到 `wa_write_l2`（shopping 134/134、admin 87/87、gitlab 90/90、reddit 67/67、map 96/96），0 条 L1 进过提示词。因此这五个 run 的配对分数（主口径每题 nc/n 均值：shopping 0.5591→0.5775、admin 0.6489→0.6508、gitlab 0.7221→0.7484、reddit 0.7995→0.8071、map 0.5922→0.5952；summary.json 的 reward_sr 只是 rollout[0] pass@1）是 L2 注入条件下的分数，不是 L1 消融。

### 5.1 写入率与库大小

| site | run | withmem/nomem 题数 | judge（genuine / failure / fluke / 报错 failure） | 非报错失败 rollout | 有失败的题 | L1 写入 | 有 L1 的题 | L1/非报错失败 | 最终库 L1 / L2 / 总 | L1 占比 | USD | 墙钟 h |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shopping | runs/wa_fleet_shopping_all_20260811_191401_20260811_191415 | 187/187 | 809 / 630 / 53 / 4 | 630 | 103 | 560 | 103 | 0.889 | 560 / 99 / 659 | 85.0% | 1283.70 | 21.3 |
| shopping_admin | runs/wa_fleet_shopping_admin_all_20260818_005633_20260818_005647 | 182/182 | 904 / 500 / 26 / 26 | 500 | 80 | 454 | 80 | 0.908 | 454 / 79 / 533 | 85.2% | 2903.29 | 17.1 |
| gitlab | runs/wa_fleet_gitlab_all_20260815_172053_20260815_172110 | 180/180 | 1019 / 360 / 51 / 10 | 360 | 60 | 314 | 58 | 0.872 | 314 / 61 / 375 | 83.7% | 1409.44 | 14.4 |
| reddit | runs/wa_fleet_reddit_all_20260814_002621_20260814_002652 | 105/106 | 625 / 153 / 15 / 53 | 153 | 29 | 142 | 27 | 0.928 | 142 / 42 / 184 | 77.2% | 693.49 | 15.5 |
| map（readonly） | runs/wa_fleet_map_readonly_20260813_103741_20260813_103743 | 107/108 | 438 / 332 / 66 / 36 | 332 | 71 | 303 | 69 | 0.913 | 303 / 68 / 371 | 81.7% | 540.53 | 12.8 |
| 合计 | | 761/763 | 3795 / 1975 / 211 / 129 | 1975（含报错 2104） | 343 | 1773 | 337 | 0.898 | 1773 / 349 / 2122 | 83.6% | 6830.45 | 81.1 |

若把报错的失败 rollout 也算进分母（2104），L1 覆盖率是 84%（shopping 88%、admin 86%、gitlab 85%、reddit 69%、map 82%）；把报错题算进"有失败的题"则是 admin 84→80、gitlab 65→58、reddit 43→27、map 74→69。约 10% 非报错失败没产出 L1，原因是写手返回空列表还是 (scope, 标题) 去重挡掉，事件里没有记录，分不开。所有 L1 的 certainty=medium、outcome=failure、scope=site:<site>，标题精确重复 0。同配置的 admin 重跑 0816（`wa_fleet_shopping_admin_all_20260816_202148`）写了 450 L1 / 76 L2。

每题 L1 条数是双峰的：

| site | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 有 L1 题的均值 |
|---|---|---|---|---|---|---|---|---|---|---|
| shopping | 84 | 11 | 8 | 8 | 5 | 12 | 10 | 23 | 26 | 5.44 |
| shopping_admin | 102 | 4 | 4 | 8 | 4 | 13 | 11 | 17 | 19 | 5.67 |
| gitlab | 122 | 5 | 3 | 8 | 6 | 4 | 2 | 17 | 13 | 5.41 |
| reddit | 78 | 4 | 2 | 3 | 0 | 2 | 4 | 5 | 7 | 5.26 |
| map | 38 | 11 | 12 | 6 | 8 | 8 | 5 | 4 | 15 | 4.39 |

全错题一题写 7–8 条 L1；这也意味着"每题配对结果 vs L1 条数"是同义反复（L1 条数由 withmem 失败数定义），不能拿来做效应分析。

### 5.2 增长

| site | @50 题 | @100 | @150 | 末 |
|---|---|---|---|---|
| shopping | L1 148, L2 26, 累计失败 156, L1/失败 0.949 | 315, 56, 340, 0.926 | 430, 78, 472, 0.911 | @187: 560, 99, 630, 0.889 |
| shopping_admin | 169, 26, 182, 0.929 | 230, 39, 244, 0.943 | 353, 64, 387, 0.912 | @182: 454, 79, 500, 0.908 |
| gitlab | 98, 15, 101, 0.970 | 174, 32, 190, 0.916 | 269, 51, 307, 0.876 | @180: 314, 61, 360, 0.872 |
| reddit | 87, 19, 95, 0.916 | 137, 41, 148, 0.926 | — | @105: 142, 42, 153, 0.928 |
| map | 172, 39, 189, 0.910 | 293, 66, 322, 0.910 | — | @107: 303, 68, 332, 0.913 |

近似线性，每题 1.35–2.99 条 L1，没有饱和；L1/累计失败随流略降（shopping 0.949→0.889，gitlab 0.97→0.872），与标题去重碰撞增多一致。来源 `runs/memory_growth.json`、`MEMORY_SIZES.md:67-108`。

### 5.3 长度

| site | n L1 | title 均值（范围） | description 均值（范围） | content 均值（范围） | 合计均值 / 中位 | 最大 | 全部 L1 字数 | L2 title/desc/content 均值 |
|---|---|---|---|---|---|---|---|---|
| shopping | 560 | 48.8 (23–83) | 194.5 (101–347) | 541.7 (300–841) | 785.0 / 781.5 | 1098 | 439,601 | — |
| shopping_admin | 454 | 48.9 (25–80) | 181.0 (78–370) | 594.9 (323–1020) | 824.8 / 811 | 1262 | 374,477 | 44.8 / 174.2 / 594.3 |
| gitlab | 314 | 48.0 (27–75) | 183.2 (85–297) | 545.5 (345–780) | 776.6 / 770 | 1074 | 243,861 | 42.3 / 169.7 / 528.9 |
| reddit | 142 | 46.6 (23–74) | 177.3 (86–284) | 529.9 (363–745) | 753.7 / 740 | 938 | 107,029 | 46.3 / 174.9 / 469.9 |
| map | 303 | 47.7 (26–70) | 190.2 (103–292) | 564.5 (338–855) | 802.4 / 797 | 1167 | 243,121 | 47.2 / 187.2 / 545.8 |

L1 与 L2 同一量级，SWE 的 L1 中位 589 字符比这里短三成。

### 5.4 冗余

在 memory.json 存的 bge-small 384 维向量上算成对 cosine（题归属靠 `wa_write_l1` 标题匹配，0 未匹配；同模板靠 `wa_task` 的 template_id）：

| site | n L1 | ≥0.85 对 | ≥0.88 对 | ≥0.90 | ≥0.95 | ≥0.88 对里 同题 / 同模板异题 / 跨模板 | 有 ≥0.88 邻居的项 | 贪心聚类 @0.85 / 0.88 / 0.90 / 0.95 | @0.88 压缩 | 最近邻 cos 均值 / 中位 / p90 | 同题对 cos 中位 vs 全部 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| shopping | 560 | 1573 | 636 | 315 | 19 | 355 / 269 / 12 | 371 (66%) | 238 / 347 / 413 / 546 | −38% | 0.894 / 0.900 / 0.942 | 0.836 vs 0.665 |
| shopping_admin | 454 | 1312 | 576 | 270 | 19 | 266 / 292 / 18 | 310 (68%) | 181 / 262 / 339 / 437 | −42% | 0.896 / 0.898 / 0.945 | 0.838 vs 0.641 |
| gitlab | 314 | 838 | 417 | 244 | 28 | 249 / 102 / 66 | 240 (76%) | 123 / 162 / 202 / 293 | −48% | 0.905 / 0.912 / 0.955 | 0.839 vs 0.681 |
| reddit | 142 | 390 | 204 | 118 | 11 | 95 / 89 / 20 | 99 (70%) | 57 / 82 / 98 / 134 | −42% | 0.895 / 0.903 / 0.948 | 0.830 vs 0.694 |
| map | 303 | 968 | 303 | 126 | 4 | 122 / 84 / 97 | 200 (66%) | 121 / 190 / 237 / 299 | −37% | 0.891 / 0.894 / 0.933 | 0.824 vs 0.716 |
| 合计 | 1773 | 5081 | 2136 | 1073 | 81 | 1087 / — / — | 1220 (69%) | 720 / 1043 / 1289 / 1709 | −41% | | |

近一半的近重复对是跨题的。同库的 L2 在 0.88 处只有 13 / 7 / 11 / 7 / 9 对。旧库同口径：shopping 0724（271 L1 / 42 L2）377 对、149 簇；shopping readonly 0806（442 L1 / 74 L2）503 对、276 簇。

### 5.5 作为 L2 原料的覆盖率

| site | L2 写入 | 源题有 ≥1 L1 的 L2 | 每个 L2 源题的 L1 均值 / 中位 | 全错（n L2，有 L1 数，L1 均值） | 少数对 | 半对 | 多数对 | L2 到任一 L1 最大 cos ≥0.88 | 到本题 L1 ≥0.88 |
|---|---|---|---|---|---|---|---|---|---|
| shopping | 99 | 99 (100%) | 5.52 / 6 | 56 (56, 7.02) | 24 (24, 5.12) | — | 19 (19, 1.58) | 74/99（均值 0.893） | 64/99（0.885） |
| shopping_admin | 79 | 75 (95%) | 5.38 / 6 | 43 (43, 6.93) | 16 (16, 5.25) | 7 (5, 2.43) | 13 (11, 2.00) | 43/79 (0.876) | 31/75 (0.867) |
| gitlab | 61 | 57 (93%) | 5.10 / 6 | 28 (28, 7.21) | 16 (16, 5.06) | 6 (6, 3.00) | 11 (7, 0.91) | 41/61 (0.896) | 33/57 (0.890) |
| reddit | 42 | 27 (64%) | 3.38 / 2.5 | 15 (15, 6.73) | 9 (5, 3.33) | — | 18 (7, 0.61) | 13/42 (0.856) | 11/27 (0.865) |
| map | 68 | 66 (97%) | 4.37 / 4 | 28 (27, 6.36) | 16 (16, 4.75) | 4 (4, 3.25) | 20 (19, 1.50) | 37/68 (0.881) | 24/66 (0.867) |
| 合计 | 349 | 324 (92.8%) | | 170 | 81 | 17 | 81 | | |

349 条 L2 里 324 条有 L1 输入；25 条没有 L1 的 L2 分布在四个站（reddit 15、admin 4：t470/538/678/778、gitlab 4：t357/389/392/799、map 2：t137/382），几乎都出自 nc=7/8 只有一次失败且那次没写出 L1 的题——现有文档说"只有 reddit 有 15 条"是错的。很多 L2 就是它某条 L1 的近义改写：shopping 0811 的 L2 到源 L1 的平均 cos 0.841，最大值的均值 0.885。

### 5.6 措辞与成本

L1 content 里的强禁令词（never / do not use / avoid / unreliable / is not proof）占比：shopping 0811 22%、admin 0818 5%、gitlab 0815 9%、reddit 0814 33%、map 0813 18%、shopping 0724 20%、gitlab ro 0809a 37%；同库 L2 是 28–42%。description 字段里出现 "do not"（"何时不用"约定）：shopping 0811 83%、reddit 0814 77%、gitlab ro 0809a 80%、gitlab 0815 12%、admin 0818 11%、map 0813 6%。run 之间起伏很大，读不成禁令守卫的前后对照。

写手调用次数就是非报错失败 rollout 数（shopping 630、admin 500、gitlab 360、reddit 153、map 332，`EFFICIENCY_REPORT.md:14-24`；报错的失败 rollout 不进写手），每题 1.4–3.4 次，对比每题 60–105 次 agent 步调用（`EFFICIENCY_REPORT.md:9-24`）；输入是整条 trace，输出上限 16000 token，token 级成本从未测量。

readonly 时代的库供参考：shopping ro 0806 442 L1 / 74 L2（`WA_FINDINGS.md:223`：442 条 L1 全部结构性不可达，516 条里只有 41 条进过提示词），0803（74 题未完）200/39，0805 185/35（memory.json 在第 945931 字节处损坏）；admin ro 0807 273/50、0808 270/51、0809 266/49；gitlab ro 0808 142/23、0809a 164/26、0809b 130/27；map ro 0812 252/70（183 个 episode error）；shopping 0724（88 题）271/42；admin 0724 182/39。`runs/wa_fleet_gitlab_all_20260814_222525` 的 events.jsonl 截断（1 个 wa_task），没有可用库。

## 6. L1 进检索会怎样（读端）

WebArena 上没有跑过把 L1 放回检索池的在线臂，只有离线回放。用 `runs/retrieval_suite_wa.json` 的 GT-A（同模板即相关）标签，在五站 363 道有相关 L2 的题上重放 dense bge-small top-5：

| site | 有相关 L2 的题 | 相关 L2 进 top-5：只 L2 池 | L1+L2 混池 | 混池 top-5 里 L1 占比 | top-1 是 L1 | 五个全是 L1 | GT-B：只 L2 → 混池（n） |
|---|---|---|---|---|---|---|---|
| shopping | 87 | 0.851 | 0.552 | 0.784 | 0.667 | 0.207 | 0.815 → 0.519 (54) |
| shopping_admin | 89 | 0.854 | 0.640 | 0.748 | 0.573 | 0.112 | 0.881 → 0.576 (59) |
| gitlab | 78 | 0.859 | 0.628 | 0.736 | 0.590 | 0.192 | 0.923 → 0.769 (52) |
| reddit | 48 | 0.938 | 0.708 | 0.683 | 0.521 | 0.125 | 0.972 → 0.722 (36) |
| map | 61 | 0.623 | 0.311 | 0.784 | 0.705 | 0.361 | 0.667 → 0.385 (39) |
| 全部 | 363 | 0.826 | 0.570 | 0.752 | 0.614 | 0.196 | 0.854 → 0.596 (240) |

`runs/retrieval_suite_summary.json` 的 ablation_layer 给出 0.8264 / 0.5702 / 0.7515，`RETRIEVAL_METHODS_EVAL.md:123` 与 `MEMORY_SIZES.md:58` 引用的就是这组。这测的是 L1 把一条可用的 L2 挤出 top-5 的概率，不是 L1 本身有害的证据；且 GT-A/GT-B 是同模板代理标签。在线的对应观测是 07-20/21 的混池 run 里 L1 占注入的 62–85%（第 4.4 节）。

SWE 上 L1 一直在检索池里，plain 臂 456 个槽位里 338 个是 L1，去掉 L1 只留 L2（l2only）反而少解 3 题、只留 L1（l1only）持平，四臂都在噪声带内。唯一一条被记入功劳的 L1 注入是 `CASE_STUDIES.md:88` 的 django-10880 L1 "Locate SQL template issues via grep" 与一条 L2 一起注进 django-12039（4/5 解出对 nomem 0）——那是流式 run，单例。

## 7. L1 写手纪律与事故

### 7.1 禁令守卫

`_L1_SYS` 现在有一句经回放验证的规则："A single attempt cannot tell a bad route from a good route walked badly: do NOT write blanket prohibitions ('never use X', 'page Y is unreliable') from one trajectory — state what to VERIFY on that route instead."（`src/hippo/wa/brain.py:67-73`）。代码注释记录了回放：没有这句时 4/4 条抽样 L1 从一次失败写出了全称禁令（"do not use the Yours tab" 一类），加上后 1/4。n=4，采样非确定，没有回放工件文件，只有注释和 `WA_FINDINGS.md:280` 一句；`scripts/replay_l2_writer.py` 只回放 L2（它内嵌了 OLD_L1 提示词但没有回放 `reflect_trajectory` 的入口）。这句话在 git 里只作为 4ef2376（2026-08-31）的一部分出现，`WA_FINDINGS.md`（gitlab 08-09 段）说它"尚未进代码"，`WA_DESIGN.md:15`（08-13）说已生效，所以 0811–0818 五个 fleet run 跑的时候它是否在位无法从历史确定。

### 7.2 gitlab t168 → t169–172 中毒

事故 run 是 `runs/wa_fleet_gitlab_readonly_20260809_031539_20260809_031549`（inject_only_l2 on，gate llm）。

| 事件 | 细节 |
|---|---|
| t168 withmem judge | r0 genuine，r1–r3 failure，r4–r6 fluke，r7 failure（reward 1,0,0,0,1,1,1,0） |
| t168 写的 4 条 L1 | 'Cross-check contributions and stars'；'Verify contribution evidence and every threshold'（description：do not treat Dashboard 'Yours' … as proof of authored contributions）；'Verify contribution projects and stars in project details'；'Cross-check contributions and repository stars' |
| t168 写的 L2 | 'Verify contributions before applying star thresholds'，nc=1 n=5 n_fluke=3，即"多数错/少数对"档 |
| 注入到 | t169、t170、t171、t172（ret_titles 每次都是这条 L2） |
| withmem nc/8 | t168 4，t169 0，t170 0，t171 0，t172 0 |
| nomem nc/8 | t168 2，t169 6，t170 3，t171 5，t172 3（t169–172 共 −17 个 rollout） |
| t169–172 自己写的全错 L2 | 'Use the dashboard's role-labeled project list'；'Fallback from empty Contributed projects to Dashboard Yours'；'Use Dashboard → Projects → Yours, not an empty contribution tab'；'Use "Yours" for complete contribution results'——与 t168 的条目互相矛盾，同存于 memory.json |
| 同配置第二次 0809_115734 | t168 写 1 条 L1，L2 'Use contribution project lists, then verify stars'（nc=2 n=3 n_fluke=5）；t169–172 withmem 7,2,0,6 对 nomem 8,4,3,6 |
| 更早的 0808_132155（只 withmem 臂） | t168–172 8,7,8,8,8；t170–172 注入的是 'Find every tied most-starred contributed project' |

两处需要改文档：现有 L1_ONLY_ABLATION.md 第 69 行说 t169–172 "被一条'别用 Yours 标签'的 L1 归零"，注进去的其实是那条由 4 条 L1 蒸出来的 L2，inject_only_l2 开着，L1 不可能被注入；`PAPER_DIRECTION_REVIEW.md:37` 说这批毒条目"全部来自全错档"，事件里 t168 的 L2 是 nc=1/n=5。`runs/gitlab_16task_dossier.md:212-226` 还显示 LLM 门控跳过了 cosine 最高的候选（0.752，t169 自己写的、方向正确）选了 0.716 的毒条目。守卫针对的是喂进那条 L2 的 L1 输入，这是它与事故的真实关系。

### 7.3 "四病"在 L1 上的对应

`WA_FINDINGS.md:102-112,218-226` 在 shopping 0724 库（271 L1 / 42 L2）上诊断的四种写端病全部举的是 L2 例子（7 条同义的 review-scan L2、23/42 L2 从未被检索、三条互相矛盾的花费规则、点击路径内容）。对 L1 数据的对应是：重复远比 L2 严重（同库 L1 在 0.88 处 377 对，L2 0 对）；死条目在 inject_only_l2 下按定义是 100%；矛盾在 gitlab 0809a 里具体可见（"do not treat Yours as proof" 与 "Prefer the sorted Yours list" 并存）；内容是点击路径（shopping 0811 第一条 L1："Open the product page's Reviews tab, read every review body on every page…"）。没有文档明写这层对应。

### 7.4 其他

Mind2Web 旧抽取器的病症（反 gold、93% 否定句、92% 来自错步、带任务原话、同站矛盾）见第 3.2 节。README.md:184-187 的"少读 L1 / 少写 L1（更严的 surprise 门控、按 key 去重合并、每站封顶）/ 甚至只写 L2"里，只有最后一项以 inject_only_l2 的形式落地；WA 代码里没有更严的 L1 门控、没有相似度合并（只有 (scope, 标题) 精确去重）、没有每站上限；SWE 有每题 2 条上限。`config/default.yaml:102` 与 `scripts/run_wa_evolve.sh:11-20` 声称 L1 也记 fluke，与代码不符。喂 reference 写经验导致 t168 答案 N/A 被写成 "answer N/A" 毒经验的那次事故（07-21/22 时代）导出了答案盲写手，是 L2 事故，这里不重复。

## 8. 结论能说什么、不能说什么

能说的。第一，在能重算的每一处，L1 单独注入都没有显示出效应：SWE 冻结 185 条 L1 在 114 题上 49 对 nomem 49（10 得 10 失，且 9/10 的得失题在四次 nomem 重跑里本来就在翻），WA 07-19 七个纯 L1 库配对 run 359 对里原始 reward 下 17 胜 26 负（剔除 4 个报错 episode 后 355 对 14 胜 25 负，sign test p≈0.11）、单臂差 0 到 −14 分，而同站 nomem 自身摆动 26–34 题。第二，L1 作为 L2 原料的覆盖是事实：五站 349 条 L2 里 324 条（92.8%）有 L1 输入，全错题的 L2 平均吃 6.4–7.2 条 L1，很多 L2 与其某条 L1 cos ≥0.88。第三，L1 数量是 L2 的 3.4–5.7 倍（五站合计 1773 对 349），近七成 L1 有 ≥0.88 邻居，贪心聚类能压 41%；离线回放显示混池时 L1 占 top-5 的 75%，可用 L2 留在 top-5 的比例从 0.83 掉到 0.57。第四，SWE 上 L1 从未被排除出检索，全库 plain 臂 74% 的注入槽是 L1，所以 SWE 上任何"记忆有效"的说法里 L1 都占了大头，而那个有效本身已被四次重复归零。

不能说的。不能说 L1 有害：唯一超出噪声带的 −14 分（gitlab 202833）来自一个写手被临时改动的单次 run，confidence-gate run 的 −7 分经 wa_gate 事件证明记忆没改变任何一题。不能说 L1 对 L2 有因果价值：没有"L2 不喂 L1"的臂，覆盖率和 cosine 都只是相关性。不能说 Mind2Web 的 +0.054 是答案盲 L1 的正效应：那里的 L1 看得见 gold，且从 14 题 pilot 到 49 题缩了 42%，本机没有工件。不能说去掉 L1 会怎样：slice C 拿掉 90 条新 L1 挪了 1 题，差额落在提示词逐字节相同的题上，已被归因为机器负载。

缺的实验和所需开关（机时按本节以上 run 的实测墙钟与花费估）：

| 臂 | bench | 开关 / 改动 | 机时与花费估 | 备注 |
|---|---|---|---|---|
| 干净的流式 L1-only | WebArena | `--wa.layer1 on --wa.layer2 off --wa.inject_only_l2 off --wa.inject_gate llm --wa.retrieve_fetch_k 5 --agent.n_traj 8 --wa.eval_rollouts 8 --wa.arms nomem,withmem`，不用改代码（新库只有 L1，layer=None 就能检索到） | 单站配对：gitlab 约 14 h / $1400，shopping 约 21 h / $1300，admin 约 17 h / $2900，reddit 约 16 h / $700，map 约 13 h / $540；五站约 81 h / $6800 | 与现有五站 L2 注入 run 直接可比 |
| 冻结 L1-only | WebArena | 把现有 memory.json 按 layer=='L1' 离线过滤（几行 json 过滤即可，如 `[it for it in bank['reasoning'] if it.get('layer')=='L1']`；`scripts/consolidate_wa_bank.py` 虽有 --layer 参数，但它只是其 LLM 合并流程的输入选择，会接着按 0.88 合并、改写和删条目，产出的是巩固后的 L1 库，不能当过滤器用），`--wa.arms nomem,frozenmem --wa.memory_in <l1_bank> --wa.inject_only_l2 off`；若不想预过滤则改一行 `run.py:347` 加 `wa.inject_layer` 字串开关 | 与上同量级（两臂都要跑） | 库来自哪个 run 会决定同模板泄漏 |
| L2 不喂 L1 | WebArena | `run.py:498-502` 传 `l1_items=None` 只会让失败 rollout 在 L2 prompt 里变成 "(no usable trajectory)"（与 `--wa.layer1 off` 给 L2 的输入完全一样）；要测"L2 吃压缩 trace 而非 L1"需在 `brain.py:246-251` 的 else 分支为 WRONG rollout 也拼入 `r['trace']`，这是一处新代码，不是现成开关 | 单站配对 13–21 h | 这是"L1 作为原料"唯一能量化的办法 |
| layer1 off | WebArena | `--wa.layer1 off`（存在于 `run.py:243`，从未跑过） | 单站配对 13–21 h | 等价于"L2 只有 judge reason / success trace" |
| L1-only 重复 | SWE | `--swe.arms frozenmem --swe.memory_in runs/swe_big_django_20260712_190710/bank_l1.json`，换 seed 跑 3 次 | 每次约 65 min / $24（haiku） | 现有 49/114 是单次 |
| 流式 L1-only | SWE | `--swe.layer2 off` | 与 big run 同量级：115 题约 $126 | 未跑过 |
| stream_L1 | Mind2Web | `--m2w.layer2 off` | 需重建数据与环境 | 07-03 排队过，结果丢失 |

同时应订正的文档：`RETRIEVAL_INJECTION_ABLATIONS.md:15,71` 的"每题 5 次尝试"（实为 1）；`README.md:164` 切片"正在跑"（07-16 已撤回）；`scripts/consolidate_bank.py:3-5` docstring 的撤回前读法；`PAPER_DIRECTION_REVIEW.md:37` 的 t169–172 全错档归属；本文旧版第 47、69 行关于 L1 注入比例与毒条目层级的说法；`config/default.yaml:102` 的 l1_fluke 注释；`src/hippo/wa/run.py:473-474` 仍说参考答案传入写手的旧注释；L1_L2_SURPRISE.md:18 "用处有两个"只列了一个。
