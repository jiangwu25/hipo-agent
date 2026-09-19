# 题量与可学性：哪些 bench、哪些站有"先验经验"可学，哪些没有（2026-09-18）

三件事：每个 bench 理论上多少题、我们每次 run 跑了多少；哪些地方的题是连贯的（后面的题能用上前面写的经验）、哪些不是；连贯的地方给三条典型的"一串题变好"的链，带题号、题目、答案，说清为什么变好、无记忆为什么不行。数字全部从 `test.raw.json`、run 目录的 `events.jsonl` 和 `runs/retrieval_suite_wa.json` 里算出，脚本见文末。

---

## 一、题量：理论上有多少，我们跑了多少

### WebArena（812 题）

单站 764 题 + 跨站 48 题（跨站的 48 题涉及 Wikipedia 等第二个站，我们的 scope 机制不支持，没跑）。

| 站 | 官方题数 | 只读子集（readonly） | 全集（all） | 我们跑过的全集配对 run |
|---|---|---|---|---|
| shopping | 187 | 139 | 187 | 0811：187 对 |
| shopping_admin | 182 | 109 | 182 | 0816：182 对；0818：182 对 |
| gitlab | 180 | 67 | 180 | 0815：180 对 |
| reddit | 106 | 10 | 106 | 0814：105 对（1 题两臂全崩） |
| map | 109 | 109 | —（map 全是只读题） | 0812：87 对（前端超时）；0813：107 对 |
| cross-site | 48 | — | — | 未跑 |

每次 run 实际跑到的题（`wa_task` 事件；配对 = 两臂都拿到分）：

| run | nomem | withmem | 配对 |
|---|---|---|---|
| wa_fleet_shopping_readonly_0803 | 139 | 74 | 74（withmem 半程断网） |
| wa_fleet_shopping_readonly_0805 | 139 | 67 | 67（同上） |
| wa_fleet_shopping_readonly_0806 | 139 | 139 | 139 |
| wa_fleet_shopping_all_0811 | 187 | 187 | 187 |
| wa_fleet_shopping_admin_readonly_0807 / 0808 / 0809 | 109 | 109 | 109 ×3 |
| wa_fleet_shopping_admin_all_0816 / 0818 | 182 | 182 | 182 ×2 |
| wa_fleet_gitlab_readonly_0809（两次） | 67 | 67 | 67 ×2 |
| wa_fleet_gitlab_all_0815 | 180 | 180 | 180 |
| wa_fleet_reddit_all_0814 | 106 | 105 | 105 |
| wa_fleet_map_readonly_0812 / 0813 | 88 / 108 | 96 / 107 | 87 / 107 |

五站全集配对合计 761 对题（shopping 187 + admin 182 + gitlab 180 + reddit 105 + map 107）。

### SWE-bench Verified（500 题）

| 仓库 | 官方题数 | 我们跑的 |
|---|---|---|
| django | 231（229 有 arm64 镜像） | 大跑 `swe_big_django_0712`：nomem 229 题；withmem 流式跑到第 116 题停机（库 243 条）；冻结库注入的留出集 114 题；之后 4 次独立重复（`fc_django_*_s1..s3` 各 114 题，nomem / global bank / repo bank 三臂） |
| sympy | 75 | `fc_sympy_*`：35 题 × 3 臂 × 3 seed |
| sphinx | 44 | `fc_sphinx_learn` 30 题学库，`fc_sphinx_*` 14 题留出 × 3 臂 × 3 seed |
| 其余 9 仓 | 150 | 未跑 |

### Mind2Web

test_task 252 题、test_website 177、test_domain 912。我们只碰过 test_task：按站点对半留出，静态 A/B 49 道留出任务 / 334 步，流式 40 题（7 月初，gpt-4o-mini）。run 目录不在这台机器上。

---

## 二、可学 vs 不可学

记忆要起作用，前提是**后面的题能用上前面的题写出的经验**。WebArena 的题按 intent 模板成串排列（一个模板通常 5 个实例，只换商品名、日期、地名），所以同模板的后几道题有先验可学；一个模板的第一道题永远是冷启动；单例模板的题什么都学不到。

### 题集本身的结构

| 站 | 题数 | 模板数 | 单例模板（结构上不可学） | 模板大小分布 |
|---|---|---|---|---|
| shopping | 187 | 48 | 10 | 5 个实例的模板 31 个 |
| shopping_admin | 182 | 41 | 4 | 5 个实例的 25 个 |
| gitlab | 180 | 41 | 5 | 5 个实例的 27 个，最大一个 10 |
| reddit | 106 | 21 | 0 | 5 个实例的 18 个 |
| map | 109 | 29 | 4 | 5 个实例的 13 个，4 个实例的 7 个 |

### 实跑里到底有多少题吃到了可用的先验

五站全集配对 run 的 withmem 流，逐题看：

| 站 | 配对题 | 模板首次出现（冷启动） | 检索时库里已有同模板 L2 | 门控注入了 | 注入的是同模板 | 同模板且来源题有真成功 | Δ 注入同模板+来源成功 | Δ 其他注入 | Δ 未注入 |
|---|---|---|---|---|---|---|---|---|---|
| shopping | 187 | 48 | 87 | 134 | 73 | 31 | **+7.9** (n=31) | +1.3 (n=103) | −0.7 (n=53) |
| shopping_admin | 182 | 41 | 89 | 87 | 67 | 42 | **+6.8** (n=42) | −5.8 (n=45) | +0.1 (n=95) |
| gitlab | 180 | 41 | 78 | 90 | 63 | 42 | **+6.3** (n=42) | +1.2 (n=48) | +1.7 (n=90) |
| reddit | 105 | 21 | 48 | 66 | 40 | 29 | +0.9 (n=29) | +1.0 (n=37) | +0.5 (n=39) |
| map | 107 | 29 | 61 | 94 | 30 | 19 | −1.3 (n=19) | −0.7 (n=75) | +8.7 (n=13) |
| 合计 | 761 | 180 | 363 | 471 | 273 | 163 | **+4.9** (n=163) | −0.3 (n=308) | +0.9 (n=290) |

Δ = withmem − nomem 的 8 条命中率，百分点。

读法。761 道题里 180 道是模板首次出现，结构上没有先验；到检索那一刻库里已经有同模板经验的只有 363 道（48%）；门控注了 471 次，其中注的是同模板经验的 273 次，而同模板且来源题至少一次真成功（我们测出来唯一稳定有益的那一类）的只有 163 次，占全部题的 21%。**记忆的全部增益就压在这 21% 的题上（+4.9 点），另外 79% 的题要么没先验、要么注进去的经验不对路（−0.3）。** 这就是全集均值只有 +1.3 的算术。

按站分：

- **可学**：shopping、shopping_admin、gitlab。同模板且来源成功的注入分别 +7.9 / +6.8 / +6.3，未注入的题基本不动（−0.7 / +0.1 / +1.7），剂量对照干净。三站共 115 次这样的注入，是论文里能站住的部分。
- **弱可学**：reddit。结构上最连贯（没有单例模板），但同模板好经验注进去只有 +0.9。原因是 reddit 的题基线已经很高（全集 nomem 75.5%），且错法多是发帖措辞、论坛选择这类判分口径问题，经验能教的东西少。
- **不可学（用现在的检索）**：map。同一模板的题只差地名，文本几乎一样，检索分不出哪条经验对应哪道题；同模板注入 −1.3，未注入的 13 道反而 +8.7（那 13 道是门控弃权的，说明门控知道自己拿不准）。map 的问题在读端而不是写端。
- **结构上不可学**：跨站 48 题（没跑）、各站的单例模板题（23 道）、每个模板的第一题（180 道）。

SWE-bench Verified：没有模板结构。7 月的取证（HANDOFF.md）是失败题需要的知识 10/11 在其他题的轨迹里根本没出现过；这次用"来源题与目标题 gold patch 碰同一文件"做代理，114 道留出题里 56 道库里有这样的条目，但按此定义所有检索方法的 precision 都只有 0.1 左右（RETRIEVAL_METHODS_EVAL.md）。这个 bench 的题目之间知识几乎不回访，跨任务记忆在结构上没有着力点，这也是 +7.0 经 4 次重复归零的底层原因。

Mind2Web：每个网站平均 3.7 道题（HANDOFF.md），复用机会比 WebArena 还少；当时测到 REUSED 11% 对 MISLED 8%，净效应小。

---

## 三、连贯的地方长什么样：三条典型的链

链 = 同一个模板里前面的题写出经验、后面的题吃到它翻盘。三条都是全集 run 的实录（`CASE_STUDIES.md` 有更长的版本）。

### 链 1 · GitLab 模板 332：建项目并加成员（t742 → t743、t744、t745、t746）

| 题号 | 题目 | 答案 | nomem | withmem | 注入的经验 |
|---|---|---|---|---|---|
| 742 | Create a new private project "planner" and add Abishek, Vinta as members | 改状态题，判分看服务器状态 | 0/8 | 1/8 | （写出 L2） |
| 743 | Create a new public project "web_arena" and add Abishek, Vinta as members | 同上 | 0/8 | **8/8** | Use the project Members interface |
| 744 | Create a new public project "AutoAGI" and add primer as members | 同上 | 0/8 | **8/8** | 同上 |
| 745 | Create a new public project "awesome-llms" and add primer, convexegg, abishek as members | 同上 | 0/8 | **8/8** | 同上 |
| 746 | Create a new private project "llm_bulk_inference" and add primer, convexegg, abishek as members | 同上 | 0/8 | **8/8** | 同上 |

无记忆为什么全错：新建项目的 README 页上有条醒目链接 "Invite team members and collaborators"，点进去是 GitLab 官方文档站，不是这个项目的成员页；40 条无记忆 rollout 全部点了它、看到文档就当任务完成。为什么变好：t742 有一条 rollout 走对了侧栏 Project information → Members → Invite members，L2 按"多数错少数对"档解释它为什么对，写下 "the README's 'Invite team members and collaborators' is a documentation link, not the membership control"。后四题的 description "Creating a GitLab project and adding users as members" 和任务意图精确对上，门控四次都选中它，32 条 rollout 全对。一条经验救活四道题，是这套机制最干净的样本。

### 链 2 · Shopping 模板 162：按类别算某段时间花了多少钱（t141 → t143）

| 题号 | 题目 | 答案 | nomem | withmem | 注入的经验 |
|---|---|---|---|---|---|
| 141 | How much I spent on food-related shopping during March 2023 | 47.41 | 0/8 | 0/8 | （写出 L2） |
| 143 | How much I spent on home decoration shopping during 1/29/2023 | 265.69 | 0/8 | **8/8** | Audit complete orders and allocate related shipping |

无记忆为什么错：8 条 rollout 全部找对了那件 260.69 的装饰品，但只报了商品小计；判分口径要求把这单 10 元运费按两件商品各摊 5 元，正确答案 265.69。为什么变好：t141 两臂全错，但判官（看得到参考答案）在 8 条失败诊断里都写了"该把运费摊进去"，写手（看不到答案）从诊断里学到这条口径，全错档的 L2 写成 "add each item's attributable share of Shipping & Handling"。t143 注入后 8 条全部把 5 元运费加进去。这条链在三次独立 run（0805、0806、0811）里都复现，是"来源题自己没做对也能教会下一题"的例子。

### 链 3 · Shopping 模板 370：某品牌的价格区间（t126 → t226、t228）

| 题号 | 题目 | 答案 | nomem | withmem | 注入的经验 |
|---|---|---|---|---|---|
| 126（模板 159） | What is the price range of Canon photo printer in the One Stop Market? | 2.56–649.99 | 8/8 | 7/8 | （写出 L2） |
| 226 | What is the price range for products from Amazon basic? | 5.49–375.19 | 0/8 | **8/8** | Verify the complete product range, then answer |
| 228 | What is the price range for products from sephora? | 18.18–94.99 | 1/8 | **8/8** | 同上 |

无记忆为什么错：把关键词搜索当成了品牌筛选。搜 "Amazon basic" 出来 7,332 条结果，连衣服家具都在里面，排序后报了全站极值 0.01 和 28,942.99；搜 "sephora" 把 10.99 的指甲蜡当成了 Sephora 商品。为什么变好：t126 是多数对少数错档，L2 只把那一条错的写成告诫 "exclude accessories, parts, supplies, and products that merely mention the brand"，并且不许收窄答案形态。t226 注入后 8 条都按 Product Name 搜、38 条结果里升序读到 5.49、降序读到 375.19，还主动排掉了一个只是附带 Amazon Basics 线材的 508.37 音箱套装。这条链是**跨模板**的（126 是模板 159，226/228 是模板 370），是跨模板也能起作用的少数例子——因为两个模板的坑是同一个。

---

脚本：题集结构与可学性统计见本次会话生成的临时脚本逻辑，等价于 `scripts/eval_retrieval_suite.py` 的 GT-A/GT-B 标签加 `runs/*/events.jsonl` 的 wa_task 事件；链条数据来自 `scripts/wa_chain.py` 同款的事件抽取（CASE_STUDIES.md）。
