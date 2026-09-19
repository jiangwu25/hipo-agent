# 先验能解决多少题，我们的经验又真的解决了多少：逐站账目与更多案例（2026-09-18）

接着 COVERAGE_AND_LEARNABILITY.md 往下算。上一份说了"有先验可学的题占 21%"；这一份把这批题的题号、我们的经验在上面翻对了多少道、比例是多少全部列出来，再补六条清楚的案例。数据来自五站全集配对 run 与 `runs/retrieval_suite_wa.json` 的标签，脚本 `scripts/prior_solvable.py`、`scripts/wa_lesson_chains.py`。

## 一、WebArena：先验可解的题有多少，我们解决了多少

口径。**有先验可用** = 这道题检索那一刻，库里已经有一条来自同模板、且来源题至少一次真成功的 L2（GT-B，实测唯一稳定有益的那类经验）。**门控注入了先验** = 那次 run 里 `select_lesson` 真的把这样一条注进去了。**翻好** = 无记忆多数错（命中 <4/8）、带记忆多数对（≥4/8）；**翻坏**反之。Δ 按 8 条 rollout 的命中数算。

| 站 | 配对题 | 有先验可用 | 门控注入了先验 | 翻好 | 翻坏 | Δ>0 / =0 / <0 | 多出的正确 rollout | 翻好率 |
|---|---|---|---|---|---|---|---|---|
| shopping | 187 | 54 | 31 | 3 | 2 | 11 / 14 / 6 | +20 | 3/31 = 10% |
| shopping_admin | 182 | 59 | 42 | 6 | 0 | 10 / 28 / 4 | +23 | 6/42 = 14% |
| gitlab | 180 | 52 | 42 | 4 | 1 | 10 / 25 / 7 | +21 | 4/42 = 10% |
| reddit | 105 | 36 | 29 | 0 | 0 | 3 / 24 / 2 | +2 | 0/29 = 0% |
| map | 107 | 39 | 19 | 4 | 2 | 5 / 9 / 5 | -1 | 4/19 = 21% |
| **合计** | 761 | 240 | 163 | 17 | 5 | 39 / 100 / 24 | +65 | 17/163 = 10% |

读法。761 道题里 240 道（32%）检索时库里有可用先验，门控在其中 163 道上真的注了进去（其余 77 道它选了别的或弃权）。这 163 道里 39 道变好、100 道不变、24 道变坏，按多数对错的口径翻好 17 道、翻坏 5 道，净多出 65 条正确 rollout。**翻好率 10%**——先验可用不等于会翻盘，因为 163 道里大多数无记忆臂本来就是多数对（不变的 100 道多是 8/8 → 8/8），真正有翻盘空间的是无记忆多数错的那部分。分站看，shopping_admin 最干净（翻好 6、翻坏 0），reddit 完全不动（先验注了 29 次，翻好翻坏都是 0，基线太高），map 翻好 4 翻坏 2、rollout 净值 −1。

### 题号

**shopping** — 有先验可用的题（54）：50, 51, 148, 149, 150, 159, 160, 161, 162, 165, 166, 167, 235, 241, 242, 270, 271, 272, 273, 286, 301, 302, 325, 326, 327, 328, 330, 331, 332, 333, 336, 337, 338, 440, 507, 508, 517, 518, 519, 520, 529, 530, 531, 532, 573, 574, 575, 586, 587, 588, 589, 792, 793, 798
翻好：160, 161, 273；翻坏：336, 586

**shopping_admin** — 有先验可用的题（59）：6, 63, 64, 65, 108, 109, 110, 111, 115, 116, 121, 122, 123, 186, 187, 204, 214, 215, 216, 217, 245, 246, 247, 290, 291, 292, 346, 347, 348, 471, 472, 473, 474, 492, 493, 494, 495, 502, 503, 504, 505, 539, 540, 541, 542, 548, 549, 550, 551, 679, 680, 706, 707, 708, 770, 779, 780, 781, 782
翻好：215, 247, 492, 502, 504, 550；翻坏：—

**gitlab** — 有先验可用的题（52）：104, 105, 106, 136, 171, 172, 182, 350, 390, 391, 392, 393, 412, 413, 414, 416, 417, 420, 421, 422, 442, 443, 444, 445, 482, 483, 484, 485, 522, 525, 526, 527, 670, 736, 743, 744, 745, 746, 752, 753, 754, 755, 756, 785, 786, 787, 788, 800, 801, 802, 803, 811
翻好：743, 744, 745, 746；翻坏：445

**reddit** — 有先验可用的题（36）：30, 31, 68, 69, 405, 406, 407, 408, 581, 582, 583, 584, 601, 602, 603, 604, 632, 633, 634, 641, 642, 643, 644, 648, 649, 650, 651, 652, 717, 718, 721, 722, 723, 724, 729, 730
翻好：—；翻坏：—

**map** — 有先验可用的题（39）：9, 10, 17, 18, 19, 20, 37, 38, 39, 40, 56, 60, 61, 72, 73, 75, 76, 81, 82, 83, 86, 87, 88, 90, 91, 92, 100, 101, 138, 139, 140, 152, 153, 154, 155, 250, 251, 252, 758
翻好：18, 40, 82, 251；翻坏：19, 92


## 二、SWE-bench Verified

冻结 243 条 django 库，留出集 115 道配对题（114 道 + 1 道只在一臂有分）。无记忆解决 49 道，带记忆 51 道；**带记忆对、无记忆错 12 道，反过来 10 道**，净 +2。按"来源题与目标题 gold patch 碰同一文件"这个代理，115 道里 56 道库里有可用先验，但所有检索方法在这个代理上 precision 都只有 0.1 左右——先验存在但检索送不到（RETRIEVAL_METHODS_EVAL.md）。口径提醒：这次跑无记忆每题 1 次尝试、带记忆 5 次，同配置独立重复 4 次后主效应归零，下面的题号只说明翻转发生在哪里，不构成效应量。

- 带记忆对、无记忆错（12）：django-10880, 11239, 11749, 11848, 11964, 11999, 12039, 12209, 12713, 13012, 13401, 13568
- 无记忆对、带记忆错（10）：django-10914, 11206, 11276, 11299, 11333, 12774, 13028, 13512, 13821, 13837

## 三、Mind2Web

没有本机数据，算不出。HANDOFF 记录：49 道留出任务 / 334 步，REUSED（本错→修对）11% 的步，MISLED（本对→带错）8%。

## 四、再来六条清楚的案例

每条：题号、题目、答案、两臂 8 条里对几条、注入了哪条经验、它从哪道题写出来、经验里起作用的话、无记忆为什么错。全部是全集 run 实录（shopping 0811、shopping_admin 0818、map 0813）。

### 案例 A · Shopping 模板 171：找能装下 N 张 Switch 卡带的最佳收纳盒（t158 → t160 → t161）

| 题号 | 题目 | nomem | withmem | 注入 |
|---|---|---|---|---|
| 158 | …best storage option to fit all 11 cards | 5/8 | 3/8 | （写出 L2 "Search broadly, then verify every qualifying product"） |
| 160 | …best storage option to fit all 6 cards | 3/8 | **6/8** | t158 的 L2；t160 自己又写出 "Build the full candidate set before ranking" |
| 161 | …best storage option to fit all 23 cards | 2/8 | **7/8** | t160 的 L2 |

无记忆为什么错：搜 "game card" 只出 5 条结果就当成全部候选，或者把 "24 Game Card Slots" 当精确条件，把容量更大的收纳盒全排掉了，然后用"评分最高"这种题目没说的标准挑。为什么变好：t158 的 L2 说"别把 Advanced Search 的精确结果当完整候选集，兼容产品可能归在别的类目，把每个可能的盒子都点开核对容量、库存、价格、评分"；t160 吃到它以后翻到 6/8，自己再写出一条更精炼的版本——"Navigate through Shop By → Category, increase Show, page through all results… apply the task's stated ranking criterion without inventing a highest-rating rule"，t161 吃到这条 7/8：把 51 个 Switch 商品全看了一遍，锁定 24 格的 HEIYING 盒（够装 23 张）。这是经验在一条链上**被迭代改写**的例子。

### 案例 B · Shopping 模板 139：某类目下价格低于 X 的商品（t272 → t273）

| 题号 | 题目 | nomem | withmem | 注入 |
|---|---|---|---|---|
| 272 | Show me products under $78 in "children dental care" category | 2/8 | 2/8 | （写出 L2） |
| 273 | Show me products under $199 in "furtiture with accent" category | 1/8 | **8/8** | Preserve the category and apply an exact price ceiling |

无记忆为什么错：站内 Shop By 只给 $100–$199.99 这种预设价格段，agent 点了这一段就交卷，把 $100 以下的商品全漏了。为什么变好：t272 的 L2 写明"通过部门菜单进类目、保留类目 URL，然后在 URL 上加精确的 `price=lower-upper` 区间，核对 'Now Shopping by' 显示的是严格上限"。t273 八条全部走 Home & Kitchen → Furniture → Accent Furniture 再加 `price=0-199`，页面显示 "Price $0.00 – $198.99"、571 件商品。

### 案例 C · Shopping Admin 模板 249：客户对某商品不满意的关键点（t213 → t215）

| 题号 | 题目 | 答案 | nomem | withmem | 注入 |
|---|---|---|---|---|---|
| 213 | …don't like about Antonia Racer Tank | Not suitable for high-impact workouts | 8/8 | 5/8 | （写出 L2，多数对少数错档） |
| 215 | …don't like about Circe ice fleece | Material quality, fit, insufficient warmth, color | 3/8 | **6/8** | Verify all reviews, then consolidate key aspects |

无记忆为什么错：两条评论都读对了、四个参考要点都找到了，但把"帽子太大""不值这个价"这种从属抱怨也单列成要点，答案被判分器判为过度展开。为什么变好：t213 的少数派错在同一处，L2 写成告诫"report every distinct, visibly supported key aspect, but avoid turning subordinate or overlapping phrases into extra standalone aspects"。t215 注入后把要点收成四条。这是"多数对少数错"档的典型：经验只管收口，不改流程。

### 案例 D · Shopping Admin 模板 287：把某商品全部变体设为缺货（t501 → t502、t504）

| 题号 | 题目 | nomem | withmem | 注入 |
|---|---|---|---|---|
| 501 | Make all Taurus Elements Shell as out of stock | 0/8 | 1/8 | （写出 L2） |
| 502 | Make all Gobi HeatTec Tee as out of stock | 0/8 | **4/8** | Select all, update Stock Availability, and respect the queue |
| 504 | Make all Selene yoga hoodie as out of stock | 2/8 | **6/8** | 同上 |

无记忆为什么错：找到了 16 个变体，但逐个点复选框被页面拦截超时，没选中任何一行就报 "Done"；有的把"Change status"（启用/停用）当成了库存开关。为什么变好：t501 唯一做对的那条 rollout 走的是 Options → Select All → Actions → Update attributes → Advanced Inventory → 勾 Stock Availability → Out of Stock → Save，L2 把这条路写下来，并且加了一句"看到 'Message is added to queue' 要等操作完成的提示再去核对，别从数量推断库存"。t502、t504 吃到后按这条路走通。

### 案例 E · Shopping Admin 模板 252：给可配置商品加一个新尺码/颜色变体（t548 → t550）

| 题号 | 题目 | nomem | withmem | 注入 |
|---|---|---|---|---|
| 548 | Add a new color blue to size S and M of Frankie Sweatshirt | 2/2 | 3/4 | （写出 L2） |
| 550 | Add a new size XXS to blue and purple Nona Fitness Tank | 0/5 | **3/4** | Preserve, generate, then prune variants |

（这两题 rollout 数不足 8，是那次 run 里部署机器崩了几条。）无记忆为什么错：卡在配置向导第 3 步，加了全局 XXS 属性、看到两个候选变体，却没走到 Summary、没生成变体、没保存父商品。为什么变好：L2 写的是完整闭环——"keep every existing attribute value selected, add the new value, generate products, then remove each unwanted new row and Save; verify the Current Variations grid retains all originals and contains every requested combination"。t550 生成 XXS 变体后删掉多出来的 XXS-Red，保存，网格里留下 XXS-Blue、XXS-Purple。

### 案例 F · Map 模板 72：先步行再驾车的两段行程总时长（t81 → t82）

| 题号 | 题目 | 答案 | nomem | withmem | 注入 |
|---|---|---|---|---|---|
| 81 | …walk from Univ of Pittsburgh to starbucks on Craig Street, and then drive to Pittsburgh International Airport | 49 min | 8/8 | 3/8 | （写出 L2，多数错少数对档） |
| 82 | …walk from MIT to Harvard University, and then drive to Boston Logan International Airport | 63 min | 2/8 | **6/8** | Recalculate Each Leg, Then Total the Trip |

无记忆为什么错：第二段的 "Harvard" 被解析成 Allston 一条路上的另一个 Harvard 地名，两段时长对不上；有的改了出发地或模式后没重新点 Go，读到的是上一段的旧时长。为什么变好：L2 写"每一段都重新设 From/To、选模式、按 Go，核对 Directions 下刷新后的 Time，再换成同一单位相加"。t82 六条都读到步行 45 分 + 驾车 19 分 = 64 分，判分器对 63 分的参考做模糊匹配通过。诚实地说：答案差 1 分钟是路网数据的差，不是经验的功。

### 案例 G · Map 模板 46：某地标附近某设施的坐标（t250 → t251）

| 题号 | 题目 | 答案 | nomem | withmem | 注入 |
|---|---|---|---|---|---|
| 250 | Tell me the coordinates of Apple Store near Pitt in DD format | 40.451, −79.933 | 8/8 | 7/8 | （写出 L2） |
| 251 | Tell me the coordinates of bus stop on the Carnegie art museum side of the street near CMU in DD format | 40.444, −79.948 | 3/8 | **6/8** | Resolve the landmark, then verify the POI's Location |

无记忆为什么错：在 Nominatim 搜索、Map Data 图层、Export/Overpass 之间打转，始终没打开那个公交站节点，没有给出答案。为什么变好：L2 说"先确定地标所在城市，用搜索框找到附近的目标 POI，打开名字/地址能确认位置的那条结果，从 POI 详情页的 Location 字段读完整经纬度——不要用地图中心、URL 里的值或 'Where is this?' 的点"。t251 找到两个候选站，选出 Carnegie 博物馆一侧的 "Forbes Ave opposite Craig St"，打开节点读到 40.4443029, −79.9488859。

---

## 五、这批案例说明什么

七条链全部是同模板兄弟题（A、B、D、E 是"多数错少数对"或"全错"档写出的路线；C、F、G 是"多数对少数错"档写出的告诫）。共同点是无记忆臂的错法在同一模板里高度重复——同一个页面陷阱（README 文档链接、预设价格段、复选框被拦、Harvard 同名地）每道兄弟题都会踩一次——所以一条写对了的经验能沿着模板传下去。反过来，第一节的账目也说明了上限在哪：先验可用的 240 道里只有 163 道被注入、17 道翻盘，其余大多数无记忆已经做对，经验没有发挥空间。
