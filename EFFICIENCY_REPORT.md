# 效率报告：记忆机制到底花了多少（2026-09-24 重写）

这份报告回答一个审稿人一定会问、我们自己也该先算清的问题：带记忆的臂（withmem）相对无记忆的臂（nomem）多花了多少 LLM 调用、多少步、多少墙钟、多少钱，库有多大、注入了多少提示词，机制里哪些是记忆本身的成本、哪些是评测协议的成本。所有数字都来自五站 WebArena 全集配对 run 的 `events.jsonl` 与启动日志、SWE-bench 各 run 的 `summary.json` / `metrics_*.csv` / `trajs/*.traj.json`，以及代码里写死的上限。凡是没记录的量（最典型的是 WebArena 的 token 数），文中直说没有，并在最后一节给补法。

五个 WebArena run 是 `runs/wa_fleet_shopping_all_20260811_191401_*`、`wa_fleet_shopping_admin_all_20260818_005633_*`、`wa_fleet_gitlab_all_20260815_172053_*`、`wa_fleet_reddit_all_20260814_002621_*`、`wa_fleet_map_readonly_20260813_103741_*`；SWE 主 run 是 `runs/swe_big_django_20260712_190710`。重算脚本在 `scripts/wa_timing_efficiency.py`（输出 `runs/wa_timing_efficiency.json`），旧的 `runs/efficiency_wa.json` 与之一致。

先说三件读表前要知道的事。第一，五个 WebArena run 里 nomem 臂也跑 8 条 rollout（`--agent.n_traj 8 --wa.eval_rollouts 8` 两臂同传），所以两臂的 rollout 数是对齐的，"记忆臂 8 倍成本"这句话是相对一个假想的单 rollout 部署 agent 说的,不是相对表里的 nomem 臂。第二，判官（judge）在两臂都跑，每条有步数的 rollout 一次（trace 为空的崩溃 rollout 直接判 failure，不调 LLM，五站共 106 条，其中 map 66 条），用来标 genuine / fluke 算口径，它是评测协议的开销，不是记忆的开销。表中的"判官调用"列括号里是 `wa_judge` 事件数 = 8 × 题数；付费判官 LLM 调用五站为 12,116 而不是 12,222。第三，WebArena 的美元数是 litellm 1.92.0 按 `gpt-5.6-sol` 表价（$4/M 输入、$20/M 输出）逐次算出来的估价，不是账单；上一版报告说"网关不计价"是错的，`summary.json` 里就有四位数的 `spent_usd`。

## 一、总表：两臂逐项对账

下表每行一个臂。墙钟给两个数：不含每臂一次 fleet 重置的臂墙钟（该臂第一到最后一个事件，扣掉臂初 221–244 s 的全量重置；含 reset 的严格口径见第三节），和再剔除 >1800 s 任务周期后的数（withmem 臂有 5 个这样的周期，都不是记忆造成的，第八节解释）。花费是启动日志里逐题累计的 `spent=$`，withmem 臂 = run 总额 − nomem 末值。

| 站 | 臂 | 题数 | 墙钟 h 不含 fleet 重置 / 再剔停摆 | agent 调用 | 判官 LLM 调用（wa_judge 事件数） | L1 写手调用（写出条数） | L2 写手调用（写出） | 门控调用 | 步/rollout 均值 | 30 步封顶 rollout | 崩溃 rollout | 花费 USD | USD/题 均值 / 中位 | 全臂 USD / agent 步（withmem 含写端与门控） |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shopping | nomem | 187 | 6.36 / 6.36 | 11,063 | 1,496 (1,496) | – | – | – | 7.39 | 72 (4.8%) | 1 | 549.56 | 2.94 / 1.85 | 0.0497 |
| shopping | withmem | 187 | 14.79 / 7.76 | 12,143 | 1,496 (1,496) | 630 (560) | 103 (99) | 186 | 8.12 | 100 (6.7%) | 4 | 734.14 | 3.93 / 2.67 | 0.0605 |
| shopping_admin | nomem | 182 | 7.91 / 7.91 | 12,998 | 1,456 (1,456) | – | – | – | 8.94 | 100 (7.0%) | 22 | 1,437.25 | 7.90 / 3.81 | 0.1106 |
| shopping_admin | withmem | 182 | 9.07 / 9.07 | 12,955 | 1,455 (1,456) | 500 (454) | 84 (79) | 179 | 8.85 | 94 (6.6%) | 26 | 1,466.04 | 8.06 / 4.52 | 0.1132 |
| gitlab | nomem | 180 | 6.78 / 6.78 | 13,180 | 1,437 (1,440) | – | – | – | 9.18 | 29 (2.0%) | 8 | 661.67 | 3.68 / 2.76 | 0.0502 |
| gitlab | withmem | 180 | 7.49 / 7.49 | 13,497 | 1,434 (1,440) | 360 (314) | 65 (61) | 178 | 9.40 | 40 (2.8%) | 10 | 747.77 | 4.15 / 3.32 | 0.0554 |
| reddit | nomem | 106 | 6.28 / 6.28 | 6,317 | 828 (848) | – | – | – | 7.79 | 8 (1.0%) | 51 | 329.15 | 3.11 / 2.18 | 0.0521 |
| reddit | withmem | 105 | 9.13 / 6.69 | 7,091 | 836 (846) | 153 (142) | 43 (42) | 104 | 8.76 | 28 (3.5%) | 55 | 364.34 | 3.47 / 2.70 | 0.0514 |
| map | nomem | 108 | 4.97 / 4.97 | 9,297 | 842 (872) | – | – | – | 11.05 | 67 (8.0%) | 31 | 243.41 | 2.25 / 1.40 | 0.0262 |
| map | withmem | 107 | 7.75 / 5.94 | 11,196 | 836 (872) | 332 (303) | 74 (68) | 108 | 13.39 | 86 (10.3%) | 36 | 297.12 | 2.78 / 2.11 | 0.0265 |
| 五站 | nomem | 763 | 32.31 / 32.31 | 52,855 | 6,059 (6,112) | – | – | – | – | 276 | 113 | 3,221.04 | 4.22 | 0.0609 |
| 五站 | withmem | 761 | 48.22 / 36.95 | 56,882 (+7.6%) | 6,057 (6,110) | 1,975 (1,773) | 369 (349) | 755 | – | 348 | 131 | 3,609.41 (+12.1%) | 4.74 | 0.0635 |

最后一列的 withmem 行分子含判官、L1/L2 写手与门控在内的全臂花费，不是 agent 单步价格；扣除第六节的写端残差后，shopping withmem 的 agent 单价 ≈ (734.14 − 130.93) / 12,143 = 0.0497，与 nomem 相同。"agent 调用"含崩溃 rollout 崩前已走的步（shopping nomem 那 1 条崩溃 rollout 走了 18 步：11,063 − 18 = 第四节的 11,045），所以与第四节只计已结束 rollout 的"步总数"逐臂略有差别。

SWE-bench Verified 这边只有 django 大 run 有两臂对照，模型是 claude-haiku-4-5（litellm 表价 $1/M 输入、$5/M 输出），每次尝试 60 步、$0.50 上限：

| run / 臂 | 题数 | 尝试/题 | agent USD 合计 | agent USD/题 | USD/次尝试 | 每次尝试 API 调用 | 60 步封顶尝试 | 判官+写端付费调用 | 判官+写端 USD | 臂墙钟 | 吞吐 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| swe_big_django nomem | 229 | 1 | 48.87 | 0.2134 | 0.2134 | 51.6 | 109/229 (47.6%) | 120（判官） | ≈1.30 | 2.56 h（4 题并行） | 40 s/题 |
| swe_big_django withmem | 115（$180 预算打断） | 5 | 125.99 | 1.0956 (5.13×) | 0.2191 (+2.7%) | 52.7 | 291/575 (50.6%) | 284 判官 + 123 写端 | ≈4.39 | 6.35 h（题串行、5 尝试并行） | 199 s/题 |
| fc_django_repo_s1 frozenmem 对 fc_django_nomem_s1 | 114 | 1 | 24.30 vs 23.95 | 0.2132 vs 0.2101 (+1.5%) | 同 | 49.9 vs 51.5 | 48 vs 59 | 66 vs 55 | 0.73 vs 0.61 | 4,124 vs 4,158 s | 36.5 vs 36.8 s/题 |

两个数值口径在这份报告里一律固定：WebArena 记忆臂相对 nomem 臂多 12.1% 的表价花费、多 7.6% 的 agent 调用、剔除停摆后多 14% 的墙钟（36.95 / 32.31 = 1.144）；SWE 学习臂每题全包约 $1.13，是 nomem 每题约 $0.22 的 5.2 倍，其中 5 倍来自 5 次尝试，写端和判官只占 3%。折成产出：nomem 五站 493 个计分成功、$6.53/成功；withmem 510 个、$7.08/成功；记忆臂多花的 $388 对应 17 个额外成功，边际 $22.8/题，其中 gitlab 与 reddit 是多花钱不多解题（+$86 / −2 题，+$35 / 0 题）。

## 二、每题的 LLM 调用账

一题在 nomem 臂里花的调用是：8 条 rollout 各走 7–13 步、每步一次 agent 调用（五站合计每题 59–86 次），加最多 8 次判官。withmem 臂在这之上多三类调用，都在 parent 进程里、在 8 条 rollout 回来之后串行发生：门控（select_lesson，一题一次，只在库里已有 L2 时调，五站 755 次）、L1 写手（reflect_trajectory，每条判为 failure 且没崩溃的 rollout 一次，五站 1,975 次、写出 1,773 条）、L2 写手（contrast_rollouts，每题最多一次，条件是非 fluke rollout 多于 1 条且不全是 genuine，五站 369 次、写出 349 条）。

| 调用 | 谁有 | 每题次数（五站均值） | 温度 / 缓存 | 输入规模 | 输出上限 |
|---|---|---|---|---|---|
| agent 步 | 两臂 | nomem 69.3，withmem 74.7 | 0.7，不缓存 | system + 可选记忆块 + TASK + 最近 15 步历史（thought 截 200 字符）+ 完整未截断 a11y 树（页面常 20–40k+ 字符） | 8,000 token |
| 判官 | 两臂，各最多 8 次/题 | 8.0（事件数；付费调用 7.96） | 0.0，磁盘缓存 | system 1,005 字符 + compact_trace（页面观察预算 200,000 字符） | 8,000 |
| 门控 select_lesson | withmem | 0.99 | 0.0，缓存 | system 469 字符 + intent（69–94 字符）+ 最多 5 条候选菜单（每条 `[i] {title}: {content}` 均 599 字符），按库内条目长度重构估算每次约 3,100–3,700 字符 ≈ 800–950 token（菜单本身没有记录，这是估算不是实测） | 8,000（实际输出 ~12 字符 JSON） |
| L1 reflect | withmem | 2.60（1,975/761） | 0.0，缓存 | system 1,409 字符 + 该 rollout 完整 compact_trace（上限 200,000 字符） | 16,000 |
| L2 contrast | withmem | 0.48 | 0.0，缓存 | system 1,369 字符 + 方向子句 140–1,090 字符（对半 138、多数对 344、多数错 757、全错 1,085）+ 平均 7.9 条 rollout 摘要 + 平均 4.9 条 L1（每条 ≈613 字符）+ 在 98/349 次里附完整成功轨迹（共 228 条） | 16,000 |
| fuzzy_match grader | 两臂，仅 115 题 | – | 走 litellm 直连 gpt-4o，绕过 LLMClient | – | – |

折成每题：记忆臂独有的调用是 3,099 次 / 761 题 = 4.07 次/题，相对每题 82.8 次的 agent+判官调用是 +4.9%；再加上记忆臂 agent 本身多走的 5.4 次/题，总调用从约 77 次/题涨到约 87 次/题（+12%）。按站看，shopping 与 map 每题多 4.9 / 4.8 次，admin 4.2 次，gitlab 3.4 次，reddit 2.9 次，差别几乎全由失败率决定：L1 写手的次数就是未崩溃且判为 failure 的 rollout 条数（占已结束 rollout 的 shopping 42%、map 40%、gitlab 25%、reddit 19%）。

调用次数低估了写端的分量。判官、L1、L2 三类调用的输入都是带完整页面观察的 compact_trace，一条 rollout 最多 200,000 字符（约 5 万 token）；L2 一次要读 8 条 rollout 的摘要加若干完整轨迹。这些输入的实际大小没有记录（`wa_step` 事件里没有 obs 字段），所以"4.9% 的调用"换成 token 会是一个更大但未知的数。第六节用美元残差反推了一个上界。

SWE 那边写端更轻：判官只对有 Submitted 的尝试调（无 patch 的 LimitsExceeded 尝试不花钱，`swe/brain.py:136-141`），学习臂每题付费写端调用 1.07 次（swe_big_django 123 次 / 115 题），L1 每题最多 2 条、L2 需要 |2·nc−n| ≥ 2 的票差（29 题因票数接近跳过 L2）。frozenmem 臂只有判官（0.58 次/题），加 LLM 门控后再加 0.96 次/题（abl_gate 176 次 vs abl_plain 67 次，多 109 次）。

## 三、时间

先说一个测量限制。WebArena 的 rollout 事件（`wa_episode_start` / `wa_step` / `wa_episode_end`）是在 8 个 worker 进程里缓存、整批回到 parent 后再回放进日志的（`wa/run.py` 的 `_Collect` 与回放循环，`logging_utils.py:38-44` 在回放时打时间戳），所以同一 rollout 内相邻 `wa_step` 的时间差中位数是 0.0000 s、最大 0.004 s，每步延迟、每条 rollout 时长都不能从事件里读出。能读的是 parent 侧的阶段边界：上一题 `wa_task` → `wa_retrieve`（检索 + 门控）→ 第一条回放事件（8 条 rollout 并行批的墙钟）→ 第一条 `wa_judge`（判官）→ `wa_write_*` 与 `wa_task`（写端）。

每步延迟只能用代理：8 条 rollout 批墙钟除以其中最长的步数，得到关键路径每步中位 8.3–11.1 s（nomem）与 7.9–12.1 s（withmem），p90 11.4–17.9 s。这里包含浏览器启动，是每步 LLM+浏览器时间的上界。两臂几乎一样，说明注入的 ~1k 字符记忆块没有可见的每步延迟代价。

| 站 | 臂 | 检索+门控 中位/p90 | 8-rollout 批 中位/p90 | 判官 8 次 中位/p90 | 每次判官 | 写端阶段（有写的题）中位/均值 (n) | 判官→首条 L1 | 每条 L1 间隔 中位 | 每题周期 中位/p90 |
|---|---|---|---|---|---|---|---|---|---|
| shopping | nomem | – | 49/189 | 32.1/85.7 | 4.0 | – | – | – | 93.2/230.9 |
| shopping | withmem | 2.4/4.4 | 46/185 | 29.8/85.6 | 3.7 | 53.2/51.1 (103) | 6.9 | 7.0 | 125.3/294.0 |
| shopping_admin | nomem | – | 74/272 | 30.8/64.4 | 3.9 | – | – | – | 108.1/341.7 |
| shopping_admin | withmem | 2.0/3.8 | 70/250 | 31.2/62.0 | 3.9 | 57.6/55.8 (84) | 7.5 | 7.6 | 135.5/366.5 |
| gitlab | nomem | – | 78/189 | 22.8/55.4 | 2.8 | – | – | – | 104.6/241.2 |
| gitlab | withmem | 1.4/2.9 | 74/214 | 21.6/51.5 | 2.7 | 41.9/39.5 (62) | 5.3 | 5.8 | 119.4/289.8 |
| reddit | nomem | – | 83/290 | 19.6/69.9 | 2.4 | – | – | – | 106.7/327.2 |
| reddit | withmem | 1.8/3.3 | 95/328 | 22.1/60.6 | 2.8 | 24.7/32.0 (42) | 6.7 | 7.2 | 132.8/377.5 |
| map | nomem | – | 101/269 | 26.2/43.1 | 3.3 | – | – | – | 132.4/297.9 |
| map | withmem | 2.2/3.5 | 134/256 | 25.0/41.0 | 3.1 | 36.0/36.7 (71) | 6.4 | 6.5 | 196.5/323.0 |

单位都是秒。判官每次 2.4–4.0 s、每题 20–32 s，在两臂里对称，占 nomem 臂墙钟的 22.5%（这是 8 次串行判官的协议成本，部署时不存在）。写端只在有东西可写的题上触发（34–66% 的题），触发时一题 25–58 s，其中第一条 L1 在判官结束后 5–7.5 s 落地，之后每条 L1 再花 6–8 s，L2 在 L1 之后。门控每题 1.4–2.4 s，包括本地 embedding（几毫秒）和一次 LLM 调用。

把整臂墙钟按阶段拆开（原始口径、含停摆），nomem 是 rollout 72.7%、判官 22.5%、重置 4.6%；withmem 是 rollout 68.0%、判官 15.0%、写端 9.4%、检索+门控 4.5%（这 4.5% 里 7,911 s 有 6,269 s 是 map t40 的一次停摆）、重置 3.1%。剔除停摆后按每题折算：

| 站 | 臂 | rollout s/题 | 判官 s/题 | 检索+门控 s/题 | 写端 s/题 | 重置 s/题 | 周期均值 s | 记忆独有 s/题 | 占臂墙钟 |
|---|---|---|---|---|---|---|---|---|---|
| shopping | nomem / withmem | 80.1 / 78.0 | 42.4 / 40.9 | 0 / 2.6 | 0 / 28.2 | 1.2 / 1.2 | 122.5 / 150.2 | 30.8 | 20.4% |
| shopping_admin | nomem / withmem | 118.3 / 112.1 | 38.2 / 39.3 | 0 / 2.2 | 0 / 25.7 | 1.3 / 1.3 | 156.5 / 179.4 | 27.9 | 15.5% |
| gitlab | nomem / withmem | 105.5 / 105.5 | 30.2 / 28.8 | 0 / 1.6 | 0 / 13.8 | 1.2 / 1.3 | 135.7 / 149.7 | 15.4 | 10.2% |
| reddit | nomem / withmem | 141.1 / 141.2 | 29.9 / 31.3 | 0 / 2.0 | 0 / 12.8 | 44.5 / 45.5 | 171.0 / 191.1 | 14.8 | 6.4% |
| map | nomem / withmem | 138.0 / 148.6 | 27.6 / 26.8 | 0 / 2.3 | 0 / 24.5 | 0 / 0 | 164.8 / 200.1 | 26.8 | 13.4% |
| 五站 | nomem / withmem | 111.9 / 111.3 | 34.7 / 34.3 | 0 / 2.2 | 0 / 21.6 | 7.1 / 7.2 | – | 23.7 | 13.5% |

记忆机制本身每题平均多花 23.7 s（写端 21.6 s + 门控 2.2 s），是剔停摆后 withmem 臂墙钟的 13.5%。rollout 阶段两臂几乎相等（111.9 vs 111.3 s/题），唯一例外是 map，多走的 2.3 步让 rollout 批中位从 101 s 涨到 134 s。

吞吐与并行度：8 台机器各承一条 rollout，一题内 8 条并行、题与题串行、两臂串行。nomem 五站 763 题 32.56 h（严格口径、含 reset；总表的 32.31 h 是扣掉每臂一次 fleet 重置后的数）= 23.4 题/h；withmem 原始 48.48 h = 15.7 题/h，剔除 5 个停摆周期后 37.21 h = 20.5 题/h。也就是记忆让吞吐降 12%，而不是原始数字暗示的 33%。每站 withmem/nomem 周期中位比是 1.34 / 1.25 / 1.14 / 1.25 / 1.48，按剔停摆均值是 1.23 / 1.15 / 1.10 / 1.12 / 1.21。

重置：fleet 全量重置每臂一次 221–244 s（shopping / admin / gitlab / reddit 各两次，map 不重置）；reddit 因 Postmill 发帖限流逐题重置 forum，每臂 95 次共 4,491 s（nomem）/ 4,533 s（withmem），单次 42–53 s、中位 47.5 s；加上臂初一次全量重置（225 / 244 s）后重置合计 4,716 / 4,777 s，占该臂墙钟 20.6% / 14.4%，两臂对称。脚本注释里写的"约 30 s"偏低。

SWE 的时间账更直接，因为 trajs 里每次 API 调用有时间戳：每次尝试 147 s 均值（中位 138，p90 186），两臂一样（withmem 145 s）。nomem 4 题并行，40 s/题吞吐；withmem 题串行、5 次尝试并行，一题 198.6 s = 尝试跨度 178 s + 判官与 L1/L2 19 s + 检索与容器启动约 2 s。记忆写端加约 17 s/题（9%），5 倍成本来自 5 次尝试而不是写端。本地 ground-truth 评测（`scripts/eval_local.py`，串行）每个有 patch 的题约 20 s，不在 events 里，从 `logs/run_evaluation` 的 mtime 反推。

## 四、步数与终止方式

| 站 | 臂 | 已结束 rollout | 步均值 | 中位 | p90 | 封顶 30 步 | 步总数（仅已结束 rollout；崩溃 rollout 崩前已走的步含在第一节的 agent 调用里） | 动作错误/rollout | 有动作错误的 rollout | 动作错误占步数 |
|---|---|---|---|---|---|---|---|---|---|---|
| shopping | nomem | 1,495 | 7.39 | 5 | 16.6 | 72 (4.8%) | 11,045 | 0.086 | 104 (7.0%) | 1.2% |
| shopping | withmem | 1,492 | 8.12 | 5 | 20 | 100 (6.7%) | 12,115 | 0.093 | 115 (7.7%) | 1.1% |
| shopping_admin | nomem | 1,434 | 8.94 | 7 | 17 | 100 (7.0%) | 12,817 | 0.173 | 179 (12.5%) | 1.9% |
| shopping_admin | withmem | 1,430 | 8.85 | 7 | 17 | 94 (6.6%) | 12,659 | 0.137 | 149 (10.4%) | 1.5% |
| gitlab | nomem | 1,432 | 9.18 | 8 | 17 | 29 (2.0%) | 13,145 | 0.270 | 331 (23.1%) | 2.9% |
| gitlab | withmem | 1,430 | 9.40 | 8 | 19 | 40 (2.8%) | 13,445 | 0.281 | 348 (24.3%) | 3.0% |
| reddit | nomem | 797 | 7.79 | 7 | 13 | 8 (1.0%) | 6,205 | 0.146 | 114 (14.3%) | 1.9% |
| reddit | withmem | 791 | 8.76 | 7 | 15 | 28 (3.5%) | 6,931 | 0.432 | 281 (35.5%) | 4.9% |
| map | nomem | 841 | 11.05 | 7 | 27 | 67 (8.0%) | 9,293 | 0.101 | 57 (6.8%) | 0.9% |
| map | withmem | 836 | 13.39 | 12 | 30 | 86 (10.3%) | 11,196 | 0.214 | 92 (11.0%) | 1.6% |

记忆臂在 4/5 站多走步：shopping +0.73、gitlab +0.22、reddit +0.98、map +2.34（+21%），admin −0.09。中位步数除 map（7→12）外两臂相同，多出的步集中在长尾：封顶 rollout 从 276 条涨到 348 条，reddit 从 8 涨到 28。注入措辞里"不为照着提示走而多花步"在 shopping / admin / gitlab 大体压住了，map 的经验（核对两端点、换模式再点 Go）直接加步。步数没有像 ReasoningBank 在 SWE 上报告的那样因记忆而下降。

终止方式有四种，不是三种。除了给出 stop_answer、撞 30 步封顶、崩溃之外，browsergym 的 WebArena 任务在每步之后跑 `validate()`，url_match / program_html 类任务一旦 score>0 就 done，或者有 tab 离开授权 host 就以 reward 0 终止；这类 rollout 最后一步是点击、stop_answer 为空。

| 站 | 臂 | 给出答案 | grader 终止无答案（其中 reward=1） | 封顶 30 步无答案 | 90 s 步超时终止 | 崩溃（剔出分母） |
|---|---|---|---|---|---|---|
| shopping | nomem / withmem | 868 / 840 | 558 (549) / 562 (558) | 69 / 90 | 0 / 0 | 1 / 4 |
| shopping_admin | nomem / withmem | 861 / 844 | 475 (450) / 497 (467) | 96 / 89 | 2 / 0 | 22 / 26 |
| gitlab | nomem / withmem | 592 / 605 | 812 (753) / 786 (765) | 28 / 39 | 0 / 0 | 8 / 10 |
| reddit | nomem / withmem | 187 / 149 | 602 (599) / 614 (608) | 8 / 28 | 0 / 0 | 51 / 55 |
| map | nomem / withmem | 624 / 591 | 147 (138) / 154 (143) | 65 / 82 | 5 / 9 | 31 / 36 |

map nomem 有 1 条 rollout 既撞满 30 步又触发 90 s 步超时，表中只归入封顶列。显式回答 "N/A" 的 rollout：shopping withmem 19 条、admin withmem 3 条，其余为 0。90 s 步超时（SIGALRM 包住 `env.step`）终止的 rollout 仍被计分，只有 map 明显（5/9 条）。崩溃的 rollout 五站合计 nomem 113、withmem 131，全是浏览器或站点问题（第八节）。

SWE 的步数被封顶吃掉了：每次尝试 API 调用 51.6（nomem）与 52.7（withmem）均值，中位 59 和 60 之于 60 步上限（withmem 有 300/575 次尝试恰好用满 60 次调用）；47.6% 与 50.6% 的尝试以 LimitsExceeded 结束、没有 patch，除一次撞 $0.50 单次成本上限（$0.508，575 次里唯一一次）提前结束外，其余 LimitsExceeded 尝试都是恰好 60 次调用。

## 五、token 与提示词开销

WebArena 没有任何 token 记录。`LLMClient._charge`（`src/hippo/llm.py:91-102`）只把 `litellm.completion_cost` 累进 `spent_usd` 并给 `calls` 加 1，`response.usage` 被丢弃；对 `src` / `config` / `scripts` grep `usage|prompt_tokens|completion_tokens` 只命中 `spent_usd` 相关行。下面所有 WebArena token 数都是字符数 ÷ 4 的估算。

读端（注入）是实测字符数。门控在 764 次 `wa_retrieve` 里注入了 474 次（62.0%）；其中 3 次落在随后 8 条 rollout 全崩、不计分的题上（reddit 1、map 2），按 761 道计分题算是 471 次（`MEMORY_SIZES.md` 用的是这个数）。分站 shopping 134/187（71.7%）、admin 87/182（47.8%）、gitlab 90/180（50.0%）、reddit 67/106（63.2%）、map 96/109（88.1%）。注入的 L2 渲染成 `[strategy] {title}: {content} (applies when: {description})`，`wa_retrieve.mem_chars` 五站均值 801 / 841 / 749 / 710 / 823 字符（中位 808 / 841 / 731 / 732 / 822，最大 1,160），加固定包装 "Optional hints from past tasks on this site …" 248 字符，每步用户消息里约 1,040 字符 ≈ 260 token。记忆块每步都重发（`rollout.py:273` 的 `usr = mem_block + TASK + HISTORY`），所以一条被注入的 episode 累计携带 步数 × 1,040 字符（下表各列统一为含 248 字符包装的口径）：

| 站 | 被注入的 episode / 全部 | 每步记忆块字符 | 每 episode 累计字符 均值 / 中位 / p90 | 全臂累计字符 | ≈ token |
|---|---|---|---|---|---|
| shopping | 1,072 / 1,496 (72%) | ~1,049 | 9,553 / 5,946 / 27,450 | 10.24M | ~2.56M |
| shopping_admin | 696 / 1,455 (48%) | ~1,090 | 11,904 / 8,736 / 31,089 | 8.29M | ~2.07M |
| gitlab | 720 / 1,438 (50%) | ~997 | 10,081 / 8,464 / 20,016 | 7.23M | ~1.81M |
| reddit | 530 / 839 (63%) | ~958 | 9,180 / 8,080 / 15,189 | 4.87M | ~1.22M |
| map | 732 / 836 (88%) | ~1,071 | 15,447 / 13,127 / 33,660 | 11.31M | ~2.83M |
| 五站 | 3,750 | ~1,038 (≈260 tok) | 11,190 (≈2.8k tok) | 41.9M | ~10.5M |

按 $4/M 输入表价，五站 ~10.5M token 的注入约 $42，摊到 474 个被注入的题不到 $0.1/题，相对每题 $2–8 可以忽略。渲染上限 `memory.token_budget` 4000 token（16,000 字符）从未触及，因为 WA 每题最多注 1 条、最大 1,160 字符。

门控菜单：system 469 字符 + intent（69–94 字符）+ 最多 5 条候选菜单（每条 `[i] {title}: {content}` 均 599 字符），按库内条目长度重构估算每次约 3,100–3,700 字符 ≈ 800–950 token（菜单本身没有记录，这是估算不是实测），五站 755 次共约 2.64M 字符 ≈ 660k token，输出是 ~12 字符的 JSON。755 次里 713 次候选池满 5 条。

写端输入没有实测，只有上限。L1 读单条 rollout 的 compact_trace，页面观察预算 200,000 字符（≈50k token）；L2 读平均 7.9 条 rollout 的摘要、平均 4.9 条 L1（每条 ≈613 字符）、在 98 次调用里附共 228 条完整成功轨迹；判官每次读一条完整 trace。输出上限：agent / 判官 / 门控共用 `wa.max_tokens` 8,000，写手 16,000（`wa/brain.py:27` 的 `_WRITE_KW`，通过 `chat(**kw)` 覆盖客户端默认的 8,000；早先与判官共用 8,000 时截断过一条 L2、污染了 gitlab t483–485）。gpt-5.6-sol 的隐藏推理 token 按输出计费但不可见，所以美元的输入/输出拆分也做不到。

输出侧的代理是 agent 回复文本（`wa_step.raw`，含 Thought+Action）：每步 192–239 字符 ≈ 50–60 可见 token，withmem 每步长 1–12%（reddit 191.8 → 214.2）；每臂 raw 合计 1.21M–2.83M 字符。

embedding 全是本地 fastembed bge-small-en-v1.5（384 维），API 成本为零。只 embed `title. description`（`store.py:36`），每写一条 embed 一次；每题检索对 intent 调两次 embed（`topk_scored` 先经 `topk` 再自己算一次相似度，store.py:56 与 :70），第二次命中磁盘 embed 缓存，所以实际计算的向量五站是 2,122 + 764 = 2,886 条；本机实测单条 3.9 ms、百条批 4.2–4.7 ms/条、模型加载 607 ms，整个战役 embedding 约 12 s。

SWE 的 token 有记录，在 `trajs/*.traj.json` 的每次调用 usage 里。每次尝试 prompt token 约 98.8 万（nomem）与 102.7 万（withmem），其中 95% 是 Anthropic prompt cache 读（942,060 / 981,764），cache 写 3.4 万、未缓存 1.1 万；completion 13,042 与 13,442。注入的记忆块 2,672 字符均值（3.95 条，k=4），首条用户消息从 5,821 涨到 8,662 字符（+2,841 ≈ +700 token），每次尝试只发一次。LLM 门控把注入压到 848 字符、1.33 条（abl_gate），31/114 题一条不注。

## 六、钱

WebArena 五站两臂合计 $6,830.45（`summary.json` 与日志 DONE 行一致），nomem $3,221.04、withmem $3,609.41，记忆臂多 $388.37（+12.1%）。这个数是 litellm 表价估算：`litellm.model_cost['gpt-5.6-sol']` 为 $4/M 输入、$20/M 输出（超过 272k 输入 token 的调用按 $8/M、$30/M 的高档计价，本战役的单次调用远低于此），`completion_cost` 对 `openai/gpt-5.6-sol` 可解析（100k 入 + 10k 出 = $0.60）。四个已知偏差：cache 命中不计入 `calls` 也不计入 `spent_usd`（但第七节会说明五个 run 内命中率接近 0）；fuzzy_match grader 用 gpt-4o、走 litellm 直连、不记账，涉及 115 题（shopping 34、admin 26、gitlab 8、reddit 2、map 45）；shopping 与 map 的 run 里 litellm 远程价目表拉取失败 6 次和 1 次，用了本地备份表；第四，worker 只有正常返回时才把该 rollout 的 agent 花费和 `wa_step` 事件带回 parent，撞 900 s episode 期限自毁（`os._exit(70)`）的 worker 两者都丢，reddit 的 15 条这类 rollout（2 nomem、13 withmem）的 agent 调用既不在 `spent_usd` 也不在调用/步数统计里，方向是略低估 withmem 臂。走的是内部 ZGAI 网关，实际结算不按这个价。

| 站 | Δ花费 USD | 其中"多走的 agent 步"（Δ调用 × nomem 单价） | 残差 = 写手 + 门控 + 注入提示词 | 残差/题 | 配对 Δ$/题 中位 / 均值 | 记忆臂更贵的题 | 单题最高 nomem |
|---|---|---|---|---|---|---|---|
| shopping | +184.58 (+33.6%) | +53.65 | +130.93 | 0.70 | +0.49 / +0.99 | 138/187 | 15.71 (t271) |
| shopping_admin | +28.79 (+2.0%) | −4.75 | +33.54 | 0.18 | +0.07 / +0.16 | 113/182 | 102.77 (t183) |
| gitlab | +86.10 (+13.0%) | +15.91 | +70.19 | 0.39 | +0.10 / +0.48 | 120/180 | 33.58 (t307) |
| reddit | +35.19 (+10.7%) | +40.33 | −5.14 | −0.05 | +0.12 / +0.35 | 62/105 | 12.28 (t410) |
| map | +53.71 (+22.1%) | +49.72 | +3.99 | 0.04 | +0.42 / +0.52 | 83/107 | 18.47 (t367) |

这个拆分是推断不是测量（写端调用没有单独的 cost 字段）。它说的是：reddit 和 map 多花的钱几乎全是多走的步；shopping 和 gitlab 多花的钱主要是写端。把残差除以该站写手+门控调用数，每次调用在 −$0.02 到 +$0.14 之间，与"写端读整条轨迹、每次几万输入 token"的量级相符（$4/M × 30k token ≈ $0.12）。shopping 残差最大，因为它失败率高、L1 调用多（630 次）。

单题成本重尾：中位 $1.40–3.81，admin 的 t183 一题 $102.77（8 条 rollout、rollout0 撞 30 步封顶、0/8）。admin 每次 agent 调用 $0.1106，是 shopping 的 2.2 倍，因为 Magento 后台表格把未截断的 a11y 树撑大了。

SWE 的钱有 agent 侧逐次的 `completion_cost`（mini-swe-agent 的 LitellmModel）和 LLMClient 侧的判官/写手合计。学习期与评测期分开看：

| 类别 | run | 题数 | agent USD/题 | 写端+判官 USD/题 | 全包 USD/题 | run 总额 |
|---|---|---|---|---|---|---|
| 学习臂 N=5 | swe_big_django withmem | 115 | 1.0956 | 0.038 | 1.134 | 180.55（含 nomem，$180 预算打断） |
| 学习臂 N=5 | swe_tail | 110 | 1.0578 | 0.039 | 1.097 | 120.65（$120 预算打断） |
| 学习臂 N=5 | sym_stream | 40 | 1.0228 | 0.044 | 1.067 | 42.68 |
| 学习臂 N=5 | fc_sphinx_learn | 30 | 1.1283 | 0.030 | 1.159 | 34.76 |
| 评测臂 nomem | swe_big_django nomem | 229 | 0.2134 | 0.0057 | 0.219 | 48.87（agent 部分） |
| 评测臂 nomem / frozenmem | 九个 fc_django、六个 abl_* | 114 | 0.2018–0.2145 | 0.005–0.009 | 0.209–0.220 | 23.78–25.12 |
| 评测臂 | 九个 fc_sympy | 35 | 0.196–0.211 | – | 0.203–0.218 | 7.12–7.64 |
| 评测臂 | 九个 fc_sphinx | 14 | 0.195–0.225 | – | 0.200–0.229 | 2.80–3.21 |

学习臂每题 $1.07–1.16，评测臂每题 $0.20–0.22，比值 5.2 倍；`HANDOFF.md:130` 写的"学习臂约 $0.9/题"低了约 20%。冻结库注入对 agent 成本几乎无影响（+1.5% 到 +2.7%/次尝试），LLM 门控多的 109 次调用共约 $0.26（abl_gate 非 agent 侧 $1.00 vs abl_plain $0.74）。SWE 全部 in-scope 42 个 run 合计 $850.35、44.0 h 墙钟；所有非 WebArena run 82 个 $1,068.14（比 `EXPERIMENT_SETUP.md:463` 的 80 个 / $1,066.78 多计了 `smoke_gitlab_20260719_143336` 与 `smoke_reddit_20260719_143336` 两个不带 `wa_` 前缀的 WA smoke run，合计 $1.36）；WebArena 全部 run 约 $20,310（`EXPERIMENT_SETUP.md:463`）。Anthropic prompt cache 折扣已体现在 `completion_cost` 里：按 usage 重算，nomem 每次尝试不打折应为 $1.05，按 cache 读 $0.1/M、写 $1.25/M 算为 $0.213，与实际 $0.2134 一致。因此 SWE 的 $0.21/题 是打了约 5 倍缓存折扣的数，不能与 WebArena 的无缓存表价直接比较。SWE 是否走网关仍无记录。

机器费。fleet 是 8 台 m6i.xlarge（4 vCPU、16 GB）合计约 $1.54/h，8 块 1000 GiB gp3 约 $640/月 ≈ $21/天，全开约 $58/天（`AWS_FLEET.md:163-165`）。按 $2.43/h（算力 + 折算存储）乘两臂墙钟：shopping $51.4（21.2 h）、admin $41.2（17.0 h）、gitlab $34.7（14.3 h）、reddit $37.4（15.4 h）；map 跑在另一台 t3a.xlarge + 1 TB gp3 上（`EXPERIMENT_SETUP.md:84`），单价没记，套 fleet 价约 $30.9。五个 run 81.1 h 约 $196 机器费，是 $6,830 模型表价的 2.9%。这是按 run 墙钟算的，run 之间的空转和 7 月 18 日以来的磁盘月费不在内。记忆臂不需要额外机器；8 台是两臂都跑 8 条 rollout 的设计要求，不是记忆的要求。SWE 全在本地 M4 Max 上跑，没有云费。

## 七、库与存储

五站过一遍写出 L1 1,773 条 + L2 349 条 = 2,122 条（`MEMORY_SIZES.md`）：shopping 560/99、admin 454/79、gitlab 314/61、reddit 142/42、map 303/68，即每题 1.35–2.99 条 L1、0.34–0.64 条 L2。写入速率平坦，每 50 题 20–30 条 L2，没有饱和迹象；349 条 L2 里 161 条（46%）从未被检索到，按 0.88 cosine 聚类只能合并 32 条（9%）。

| 层 | 条数 | title 均值 | description 均值 | content 均值 | 渲染行均值 | embed 文本均值 | 每条在 memory.json 里 |
|---|---|---|---|---|---|---|---|
| L1 | 1,773 | 48.3 字符 | 186.9 | 558.9 | 824.2 (≈206 tok) | 237.2 | ~9.5 KB |
| L2 | 349 | 46.2 | 180.5 | 547.2 | 803.9 (≈201 tok) | 228.7 | ~9.5 KB |

L2 和 L1 一样大，L2 不做压缩。每条 9.5 KB 里 8.4 KB 是 384 维 float 的 JSON 向量，文本只占约 0.8 KB。memory.json：shopping 6.29 MB（659 条）、admin 5.10（533）、gitlab 3.57（375）、reddit 1.75（184）、map 3.54（371）。SWE 库：django 243 条 2.26 MB（title+description+content 共 147,135 字符，均值 605、中位 594 字符/条；不含 description 时 100,007 字符、412 字符/条）、swe_tail 469 条 4.37 MB、global 393 条 3.66 MB、sympy 82 条、sphinx 68 条，每题写 2.1 条、不随库大小放缓。检索是内存 cosine，候选池最多几百条，时间可忽略。

run 产物：每个 WA run 的 events.jsonl 12.4–24.6 MB、启动日志 0.5–2.9 MB、metrics/rewards 不到 10 KB。`runs/` 共 29 GB、185 个 run 目录（连同 70 余个启动日志等散文件共 295 个条目），大头是 SWE 轨迹：swe_big_django 327 MB（804 个 traj）、swe_tail 234 MB，而 sphinx 的 traj 存了无上限的 raw_output，单个 `fc_sphinx_global_s2_20260717_130959/trajs/sphinx-doc__sphinx-9320.frozenmem.a0.traj.json` 就有 5.55 GB，六个 sphinx 臂各 2.5–5.2 GB。git 只跟踪 1,177 个文件约 450 MB（HEAD 7ac6c86），traj 被 gitignore。

LLM 磁盘缓存 `.cache`（`llm.cache=true`，键是完整 payload 的 sha256）：chat 53,886 个文件、apparent 27 MB、占盘 211 MB；embed 10,456 个、每个 8,456 B、占盘 123 MB；合计 333 MB。只有 temperature 0.0 的调用（判官、L1、L2、门控）可缓存，agent 步（0.7）永不缓存，命中不写日志也不计数。五个 run 时间窗内新写的 chat 缓存文件 15,142 个，与预期的可缓存调用数 15,215（判官实际 LLM 调用 12,116 + L1 1,975 + L2 369 + 门控 755；wa_judge 事件 12,222 里有 106 条零步崩溃 rollout 走 "empty trace" 分支不调 LLM）只差 0.5%，说明 run 内命中率接近 0（约 0.5%，或略有失败调用），缓存没有省钱。fleet 磁盘：四个站点镜像 424 GB（gitlab 156、shopping 141、forum 107、shopping_admin 19.9），每台约 651 GB 用了 968 GB 的盘。

## 八、可靠性开销

崩溃（`wa_episode_error`，剔出分母）五站 nomem 113 条 / withmem 131 条，全是浏览器或站点，没有 LLM 或 host-guard 引起的。分类：admin 22/25 条 Frame.evaluate Target crashed；reddit 33/50 条 Page.goto 10 s 超时加 18/4 条登录点击超时；map 23/32 条 "Selectors.set_test_id_attribute: no running event loop"（Playwright 事件循环卡死，全部发生在 setup 阶段、n_steps=0）加 7/4 条 60 s goto 超时；shopping withmem 4 条 ERR_ADDRESS_INVALID 全在 t572。整题全崩、不产生行的：reddit withmem 1 题，map nomem 1、withmem 2，这就是 105 与 108/107 的来历。两臂崩溃数不对称（reddit 51 vs 47 剔除、admin 22 vs 26），有效 N 不恒定，runner 自 92e1afb 起把它们剔出分母而不是记 0。

看门狗与超时（值来自 `config/default.yaml`、`scripts/run_wa_fleet.sh`、`wa/run.py`、`wa/rollout.py`）：

| 旋钮 | 值 | 管什么 | 单次最坏 | 五个 run 里触发 |
|---|---|---|---|---|
| wa.timeout | 10,000 ms（map 60,000） | 单个 Playwright 动作 / goto | 浪费 10 s（60 s）一步；在 make/reset 里超时则整条 rollout 崩 | reddit 33+50、gitlab 4+6、map 7+4 次 goto 超时 |
| step_timeout | 90 s SIGALRM | env.step | 90 s 后 terminated，仍计分 | admin 2、map 5/9 |
| reset_timeout | 120 s | gym.make 与 env.reset 各一次 | 240 s 后 setup 崩 | 0 显式 |
| env.close | 60 s | 浏览器关闭 | 60 s | 未记录 |
| episode_timeout | 900 s（worker 内 Timer → os._exit(70)） | 整条 rollout | 900 s + BrokenProcessPool + 重建池 + 重试一次（最多再 1,800 s） | 15 次，全在 reddit t721/t724/t730（2 nomem、13 withmem） |
| rollout_timeout | 1,800 s（parent） | 一题 8 条 rollout 的首轮收集 | fleet 路径：超时的 rollout 丢弃不重试；但 BrokenProcessPool 的重试各自另起 1,800 s 上限且按 rollout 串行，所以一批可达 1,800 + k×900 s（reddit t724 的 3,964 s 就是这样来的，不算 HUNG）；共享池（map）杀池重建整批重试一次，最多 3,600 s | 0 次 HUNG |
| worker_recycle | 10 → fleet 上 max(1, 10//8) = 1 | worker 进程存活 | 每条 rollout 一次新进程 + 新浏览器 | 每臂 1,440–1,496 次 spawn，未计时 |
| rollout_stagger | 4 s（仅 map） | 错开启动 | 第 7 条 rollout 空等 28 s，每臂 ≥51 min 地板 | map |
| LLM_TIMEOUT + tenacity | 180 s/次；每次 tenacity 尝试依次试主模型 + 2 个兄弟模型（`.env` 的 LLM_FALLBACK_MODELS=gpt-5.6-terra,gpt-5.6-luna），共 8 次尝试，退避 2–60 s | 一次 LLM 调用 | ≈ 75 min（无兄弟模型时 ≈ 27 min），远长于 900 s 的 episode 期限 | 日志里 0 条 RetryError / APIError / 429 |
| fleet_reset | 每臂一次 | 恢复纯净镜像 | 45 min 子进程上限 | 实测 221–244 s |
| reset_per_task | reddit | 逐题重置 forum | ~50 s × 题 | 95/臂（另加臂初全量重置 1 次），合计 1.31 h / 1.33 h |
| stall reporter | 每 300 s 查，静默 >1,800 s 打栈 | 诊断，不杀 | 0 | reddit 3 次、map 1 次 |

withmem 臂原始墙钟比 nomem 多 15.9 h，其中 11.3 h 是 5 个 >1800 s 的任务周期：shopping t572 的 rollout 批 25,252 s（7.0 h），reddit t721/t724/t730 批 2,703 / 3,964 / 1,986 s，map t40 在 `wa_task(39)` 与 `wa_retrieve(40)` 之间空了 6,269 s。nomem 臂没有任何一题超过 1,800 s（最长 1,590 s，reddit）。shopping t572 期间日志只有 LiteLLM "[Errno 8] nodename nor servname provided" 警告（08:18 与 15:14，隔 6 h 56 min）和 4 条 ERR_ADDRESS_INVALID，1,800 s 看门狗没响，只能是驱动机（笔记本）自身断网或休眠；reddit 三题是 "Like/DisLike all submissions" 类任务确定性卡死，每次撞 900 s 期限后池重建、重试再撞一次，13 次重试、2 次 "failed twice" 丢弃；map t40 的 105 min 停摆在检索/门控这一步：select_lesson 走 LLMClient，有 180 s × 8 次（含 2 个兄弟模型 ≈ 75 min）的上限，本地 fastembed embedding 则没有任何超时；6,269 s 比 LLM 侧的理论上限还长，所以不能只归到 LLM 调用，具体卡在哪个组件日志看不出。这些停摆落在记忆臂纯属调度顺序（withmem 总是第二个、过夜跑），不是机制成本，但它们确实没有被现有看门狗兜住。

## 九、门控与纪律省了多少

门控（cosine top-5 → 一次 LLM select_lesson 选 0 或 1 条）让 WebArena 每题至多注 1 条 L2，且只在 62% 的题上注；相对"每题必注 top-k"，它把读端提示词从 k 条压到平均 0.62 条，代价是每题一次 800–950 token 的短调用（五站 755 次、约 660k token，表价约 $3）。离线检索评测里（`RETRIEVAL_METHODS_EVAL.md`）门控的 recall@1 0.75、precision 0.58、注入率 0.63，纯 ranker 是 0.60–0.66 / ~0.3 / ~1.0，所以门控省的是注错的那一半。

SWE 上门控把注入从每题 4.00 条 2,732 字符压到 1.33 条 848 字符（−67%，`RETRIEVAL_INJECTION_ABLATIONS.md:17-24`），31/114 题一条不注，resolve 从 50.0% 到 48.2%（统计上打平，不是"一点不丢"）；每题多 0.96 次门控调用，成本约 +$0.002/题，agent 成本反而最低（$0.2018/题）。但在 SWE 上注入本身就几乎不花钱（Anthropic prompt cache 让 95% 输入是 cache 读，记忆块每次尝试只发一次），所以 −67% 省下的是上下文位置而不是美元。

写端的纪律：L1 每题最多 2 条（SWE）；L2 需要票差（SWE 29 题跳过，WA 由"非 fluke >1 且不全 genuine"过滤，只有 34–66% 的题触发写手）；WA 只把 L2 注给 agent，L1 只喂 L2 写手。这些规则决定了写端调用是每题 3–4.5 次而不是每条 rollout 一次。

## 十、与竞品的效率对比

能比的和不能比的要分开写。仓库文档里记录的竞品效率数：

| 方法 | 报告的效率量 | 值 | 我们对应的数 | 能否对比 |
|---|---|---|---|---|
| ReasoningBank (2509.25140) | SWE-V 每题步数 | flash 30.3→27.5、pro 21.1→19.8，记忆减步 | WA 每 rollout 步 +0 到 +2.3；SWE 51.6 vs 52.7 但被 60 步封顶饱和（中位 59/60） | 方向可比（我们 WA 上反号），SWE 不可比 |
| RB + MaTTS | 写时 k=5 并行 rollout | Shopping+flash k1 49.7 / k5 55.1；无 token 或美元 | 两臂各 8 条 rollout | rollout 数可比：我们是 RB 部署的 8 倍、MaTTS 的 1.6 倍 |
| 2606.15017 | 等预算协议、每题 token | 裸 agent 15 步 + 树剪枝 vs 模块 10 步；73.6K vs 82.6–107.3K token/题；3 seed | 两臂同 30 步封顶；token 未记 | 不可比，需要 token 记账和等预算臂 |
| MemGuard (2608.21867) | 比 RB 少 3–8k token | +14 vs 无记忆、+8 vs RB；5 seed；单 rollout | token 未记 | 不可比 |
| Agent KB (2507.06229) | 每题预算 | 50 iter、$3.0 / $4.5（GPT-4.1，Lite） | SWE haiku：nomem $0.21、学习臂 $1.10、冻结 $0.21/题 | 只能作为预算量级参照，模型与集合不同 |
| Compliance Trap (2607.10608) | 注入策略 | 始终注 +1.3，先试后注 +10.4（77 题） | 我们始终注（门控通过即注） | 策略层面可比，值得跑 |
| AWM / ASI / SWE-Exp / ExpeRepair | – | 文档里没有自报 token/步/美元 | – | 无 |

我们能报而竞品文档里没有的：记忆臂每题额外 LLM 调用 4.07 次（+4.9%）、每题 23.7 s 写端与门控延迟（13.5% 臂墙钟）、每题最多 1 条 ≈260 token 的注入、表价 +12.1% 的花费、库 9.5 KB/条。我们不能报的：每题 token（2606.15017 和 MemGuard 的比较口径）、等步数或等 token 的裸 agent 臂、best-of-8 裸 agent。`PAPER_DIRECTION_REVIEW.md:99` 估的"等价于 36–40 步无记忆臂"和上一版报告的"32–36 步"都不是从数据推出来的：按表价，记忆臂多花的 $388 除以 nomem 每次 agent 调用 $0.0609 约等于每题多 8.4 次 agent 调用，即每条 rollout 多约 1 步，而多数 rollout 5–8 步就结束，把封顶从 30 抬到 36 对它们没有影响；等钱基线更接近 best-of-9 而不是抬封顶。这句是推断，写进论文前要用第十一节的 token 记账重算。

## 十一、缺口与补法

token 记账。WebArena 事件里没有 usage 字段，输入/输出/隐藏推理都无法拆，2606.15017 式的等 token 对比做不了。补法是一行：在 `src/hippo/llm.py` 的 `_charge` 里把 `response.usage`（prompt_tokens、completion_tokens、reasoning_tokens）连同调用类别（agent / judge / l1 / l2 / gate）写进 events，两臂对称记；worker 里的 agent 调用要随 `_Collect` 一起带回 parent。同时给 `wa_step` 加一个 `obs_chars` 字段，让判官和写手的输入规模也可算。缓存命中也应打一条事件，否则判官/写手的付费调用数只是上界。

等步数、等 token 基线。目前没有任何 bench 跑过等预算的裸 agent。有了 token 记账之后先算出记忆臂每题实际多的 token，再决定裸臂是抬封顶还是加 rollout；在 token 记账落地前，最便宜的对照是 nomem 的 best-of-9（多一条 rollout 与多 8.4 次 agent 调用/题同量级）。`PAPER_MAIN_TABLE.md` 的 token-matched 行应保持空白，`PAPER_MAIN_TABLE_PREDICTED.md` 的 +1.0 是预测，不能当测量引用。

写端 token 实测。L1/L2/判官读的 compact_trace 上限 200,000 字符，实际大小未知，第六节的美元残差只能给出"每次 −$0.02 到 +$0.14"的间接量。补法同上；另外在 `wa_write_l1` / `wa_write_l2` 事件里直接记 prompt 字符数即可。

每步延迟。worker 事件回放时重打时间戳，每步和每条 rollout 的时长不可恢复。补法：`_Collect.event` 在 worker 里记 `time.time()`，回放时保留原时间戳。

每臂、每类调用的花费。`summary.json` 只存一个 `spent_usd`；每臂靠日志差分，每类靠推断。补法：`_charge` 带上调用类别累加到独立计数器，worker 返回时按类别汇总。

fuzzy_match grader。gpt-4o 直连不记账、不计数，browsergym 可能每步调 validate()，次数未知。补法：让 `_fix_webarena_grader` 走 LLMClient 或至少记一条事件。

机器费。AWS 账单没读，map 那台 t3a.xlarge 的单价和运行时长没记，run 之间的空转没算。补法：从 AWS Cost Explorer 拉 7 月 18 日以来的实际账单对一次。

Mind2Web。本机没有任何 m2w run 目录，`HANDOFF.md:244` 的"每题约 147 s"是唯一的数；没有可复算的调用、步数或花费。

SWE 侧的小缺口：`swe_big_django` 与 `swe_tail` 的 `summary.json` 因预算打断没有 withmem 块，成本是从 `metrics_withmem.csv` 重算的；写端 $5.69 在两臂间的分配按付费调用数推断；每次尝试的容器启动与镜像拉取时间没记。
