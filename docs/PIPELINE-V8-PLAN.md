# V8 实施方案 — 3 个 workflow、~50 agent、昂贵模型用在刀刃上

## 0. 昂贵模型分配原则

> **按节点性质分派(§1.1b 三家 MoA):判断 = Opus+K3+sol 三家并行同题 → Opus 合并+反思;
> 生成 = 角色分工并行不合并(测量出的强项);执行/检索 = GLM + 脚本。**

| 模型 | 测量出的强项 | 每回合调用数 |
|---|---|---|
| **Opus** | 研究方向/品味/**审查与合并收敛**(合并席专属) | ~10 |
| **GPT/sol** | 数学与算法(formal 型模式、Draft、Recompute、判断席) | ~6 |
| **K3** | 批判性思维/找茬(判断席、跨域生成镜头) | ~5 |
| **Grok** | 工程主审(experiment Find 主席) | 1 |
| **GLM** | 广度+工程+量:检索/读卡/干跑/实现/写节 + 生成广度席 | ~30 |

**总额定**:~55 agent/回合,昂贵(Opus/sol/K3/Grok)~22 次,GLM ~30 次。

---

## 1. `research.workflow.js` — DeepResearch 骨架 + RS 灵魂 (~30 agent)

### 1.1 相位表与模型分配

| # | 相位 | 席位 | 模型 | 节点性质 | agent 数 | 耗时 |
|---|---|---|---|---|---|---|
| 0 | Scope | 1 | GLM | 检索 | 1 | ~1 min |
| 1-3 | **广度 Search/Read/Verify**(一遍 + 硬洞补查 ≤1 轮) | ∥ | GLM | 检索/执行 | 12-18 | ~5 min |
| 4a | Bottleneck 独立 | **Opus+K3+sol** ∥3 | 三家同题 | **判断** | 3 | ~3 min |
| 4b | Bottleneck 合并 + **反思** | 1 | **Opus** | 合并 | 1 | ~3 min |
| 4R | 定向再搜索(反思触发,≤2 次) | ∥ ≤3 | GLM | 检索 | 0-6 | 0-4 min |
| 5 | Generate(模式组合 + 角色镜头 + 软负锚,不合并) | 6 ∥ | **Opus+sol+K3** + GLM×3 | **生成** | 6 | ~4 min |
| 5C | 执行式干跑(数值真跑 + 退化探针 + 独立 naive 对比) | ∥ 每候选 | GLM | 执行 | ≤3 | ~2 min |
| 6a | Floor: scoop 搜索(signature@10mo + alias@48mo + github) | 1 | GLM | 检索 | 1 | ~1 min |
| 6b | Floor: 硬底 | 脚本 | — | 执行 | 0 | 0 |
| 7a | Audit/Converge 独立(五检 + 四维,锚定发现) | **Opus+K3+sol** ∥3 | 三家同题 | **判断** | 3 | ~3 min |
| 7b | 合并 + 排名 | 1 | **Opus** | 合并 | 1 | ~2 min |
| 8 | Select(含 scoop 四轴判) | 1 | **Opus** | 合并 | 1 | ~2 min |

**墙钟估计**:~30 min(最深串行路径 8 跳 + 循环 2 轮)

### 1.1b 三家 MoA 架构(判断=trio+Opus 合并;生成=角色分工;执行=GLM)

7×7 全删(测量对象是 Sonnet-4.6 级模型,对在用模型不可迁移;测量装置不产出 idea)。
多家族组织方式按**节点性质**分派,RS design-notes 的三条证据裁决:

| 节点性质 | 架构 | 理由 |
|---|---|---|
| **判断/审查**(Bottleneck、Audit、Judge 等决策门) | **级联三席:K3 攻击 → sol 复核(形式子集独立判+复核攻击)→ Opus 仲裁三分类+反思** | 座次=测量强项(K3 批判/sol 数学/Opus 审查收敛);每席只读上一席的锚定输出+判据切片,不重读全工件——比并行同题省,且后席看见前席之锚、分歧留 Opus,错误去相关保留 |
| **生成**(5 Generate 各席) | **角色分工并行,不合并不投票** | RS 证据:K=3/K=2 退回 K=1(无下游选择的冗余无价值);refine-to-blandness(合并磨平棱角);质量来自下游 gauntlet 不来自生成端共识。镜头按测量分:sol→formal 型(reframe_as_solvable/algebraic_equivalence/characterize_limit/relax_discrete)、K3→跨域型(adapt_via_conditioning/decompose_and_delegate/unify/heterogeneous_decomposition)、Opus→pivot 型(assumption_audit_and_pivot/generative_process_redesign/structural_prior_encoding)、GLM→其余+广度。镜头分配不是 RS 警告的生成约束(那是强制内容);席内仍按 2.1 判断层选型、2.2 按子模式卡生成 |
| **执行/检索**(搜索、读卡、干跑、实现、写节) | **GLM + 脚本** | 干跑是执行不是判断(脚本真跑);RS 2.3 的执行式验证 GLM 足够 |

**级联四规则**(防级联变和稀泥):
1. 锚定才进下一席:每席 findings 必须带锚(paper_id+行号 / 候选字段原文);无锚项脚本先丢。
2. 硬底归脚本:可机械化的 kill 条件(计数/关键词 membership/执行痕)→ 脚本判,永不进模型。
3. Opus 仲裁输出三件:裁决陈述(分歧+理由)、三分类(searchable {query,why} / regenerable 指令 /
   unresolvable 下传)、反思与落选嫁接。
4. 盲区保持:审计门只见 blocking_findings 切片,不见干跑报告全文(RS anti-anchoring 原样)。

### 1.1c GATE 原语:RS 全功能 = DR 的 assess→continue 判据(一层循环,统一原语)

重读两边的结论:CC 官方 DR workflow-script.js **本身没有外层循环**——Scope→Search→Fetch→Verify→Synthesize
单遍走完,迭代只藏在两处(agent 内部可改写查询、vote quorum 裁决);Perplexity 的
"assess → continue until resolved" 才是轮回的形状。RS 恰好就是那套 assess 的**内容**:11 个
system-prompt 每一个都是"逐条判据 + 路由"的合同。统一原语因此成立:**DR 出循环的形状,
RS 出判据的内容;检索是门内函数,不是上游层。**

```
GATE(name, criteria[], artifact):
  0 hard-floor   脚本先判可机械化判据(计数/schema/kill-switch 字节同一/引文一致/
                 grounding 哨兵)——不过直接路由,永不进模型
  1 cascade      级联三席(决策节点的多模型 MoA,座次=测量强项):
                 K3  攻击席  对每条非机械判据 {met|unmet|uncertain}+锚;无锚项脚本先丢
                 sol 复核席  形式判据子集独立判(estimand 匹配/算术/控制 tautology/
                             claim 分级,能算的算)+ 逐条复核 K3 的攻击
                 Opus 仲裁席 裁决分歧;每个 unmet/uncertain 三分类;反思:
                   (a) searchable   → emit {query, why} 入查询账本
                   (b) regenerable  → revision 指令(回生成 / patch 词表,RS revise 原样)
                   (c) unresolvable → 标记下传或路由(abandon/retry/STOP)
  2 remediate    (a)→GLM 定向检索(节点预算)新卡入池;(b)→生成/patch 执行器(有界);(c)→路由
  3 re-judge     增量复判:只重判受影响判据
  4 advance      全 met,或预算尽带 unresolved 前进
```

一层不变量:**一个池**(所有卡对所有门可见)、**一本查询账本**(去重+预算;每个 unmet→query 对
落在 bundles 可审计)、**一条工件链**。非门节点只有两类:GENERATE(执行 (b) 指令,角色镜头分工)、
EXECUTE(脚本/GLM 抓取)。级联比并行同题便宜:sol/Opus 只读上一席的锚定攻击清单+判据切片,
不重读全工件;串行代价换来错误去相关(后席看见前席的锚,分歧留给 Opus)。

**门链(research)**:P0 池门 → L 谱系门 → B 瓶颈门 → S 选择门 → G 生成(执行器)→
T 追踪门 → C 碰撞(纯检索,被候选自身字段拉动)→ A 审计门(内嵌 X 驳斥复核;revise→R patch
执行器→FA 再审计门)→ I 可实现性门 → F 可行性+卡片门 → Select 终审。
dag 轮间环 = BOTTLENECK-RETRY 负锚(两次 subsumption 死→换失败轴)+ 跨轮软负锚(S 门)。

**RS 全功能 → 判据清单**(每行就是一条 assess;三分类示例 = unmet 时怎么办):

| 门 | 判据(源自 RS 原文) | 判法 | unmet 三分类示例 |
|---|---|---|---|
| P0 池门 | 真相关论文 ≥5(稀疏 → do_not_generate);多源在场 | 脚本计数 + K3 判真相关 vs 关键词噪声 | 稀疏→(a) 换措辞/换源再广;OOD→(c) STOP+remedial_steps(RS one-shot:不问用户,直接路由) |
| P0 | anchor/closest 候选的全文(intro+method)在场——residue 推理在摘要上不可靠 | 脚本查 fulltext 缓存 | 全文缺→(a) top-up 检索(RS phase1_fulltext_topup 原样,确定性调用) |
| L 谱系门 | 谱系树到该线根动作;age_band 全标;2-4y 带标低置信 | 脚本(schema) | 缺带/断根→(b) 重构谱系 |
| L | 4-6 机制家族枚举 + collateral 代表**或声明缺席**(反编造);REGRESSION FLAG 必须具名具体方法否则删(反过保守) | Opus 判 / K3 攻击含糊旗 | 家族有无老代表不确定→(a) 家族名+经典 venue 查询 |
| B 瓶颈门 | bottleneck ≥2 paper_id 内联;closest_adjacent ≥2 且 is_anchor 恰一;anchor residue 出自全文非摘要 | 脚本 | 摘要级 residue→(a) top-up,重写 residue |
| B | 问题级不说药方(单一具名机制即可关 = 走私,改写);gaps 落 frontier-leaf residual(落内部节点=回归);共享祖先存在时 ≥1 subtractive;每 gap stakes 双成本具象(mattering test:写不出=负空间非 gap) | K3 攻击走私/落点 / Opus 仲裁 | stakes 写不出→(b) 丢该 gap;"该 residual 可能已被关"→(a) 定向查那篇/该 venue |
| S 选择门 | anchor 类型绑死 contribution_type(读 gap 的动词);组合 ≥2 模式或 composition_note 非空;CHAIN 必须具名中间对象 O;siblings ≤2 + removal test + 相干线程非 shared_question-only | 脚本 / K3 攻击装饰链 / Opus 判 | 装饰链→(b) 换 RE-PICK/PAIR(attested 集内) |
| S | regression check:所选模式的落点不落已占节点;companion ∈ attested 集(companion-combos.md membership);saturation 记录(只透明不过滤) | sol 追落点 / 脚本 membership | 落点占位不确定→(a) 经典家族查询 |
| G 生成(执行器,合同非判据) | 子模式卡(when_to_pick+thin-corpus 声明);hook 三形准入测试;premises ledger(observation-model 前提+estimand 声明);naive 三分支+standard-tool 追问;中心对象可从文本计算;steps 带传播;证伪结构(承重变量+非 tautology 负控制+正控制);signature 3-5 + alias 2-4;substantive>methodological 差异化;只用已存在资源;claim 按强度分级 | 生成(三镜头) | 数字 grounding 不确定→(a) 查同设定 closest 的全文对数(RS 硬规:不许跨 regime 贴指数) |
| T 追踪门 | T2 真执行(mode=executed,不许手算);T3 退化探针(空集/k=0/全同/平局)全 halt;T4 每条 claim 映射到步+分级,统计 claim MC 仲裁带实测数;T5 naive **独立构造**(不用候选自述版)+ 分支一致;obstacle holes 不许 patch | 脚本查执行痕 / sol 算 / K3 攻击 T1 双读 | 手算→(b) 重跑带工具;可修 findings→(b) patch(词表);obstacle holes→(c) blocking 切片下传 A,merger 拒修 |
| C 碰撞 | 纯检索三通道:signature(近窗,抢发风险)+ alias(多年窗,改名祖先)+ github(未发表实现);BM25 脚本,截断命中 | 脚本 | —(卡入池供 A 门判) |
| A 审计门 | 五检逐条(reject lessons 逐条引 / 战术签名是否真实例示 / 反模式缓解是否实质交付 / paper-pointed 威胁 / 证伪结构);硬底三条→abandon:reject lesson 触发、缓解未交付、exact-mechanism 威胁;blocking findings 逐条处置(upheld 压住 advance;驳斥须具体 flaw 类) | 脚本硬底 + K3 攻击 + sol 复核 + Opus 裁 | threat addressable→(b) R patch;**parametric_family_concern→(a) 当场 scoop 检索**(RS 单遍才留旗子,我们有循环);证伪缺损→(b) scope=falsification 重写+FA 强制再审 |
| X(A 内嵌) | 驳斥只认三类具体 flaw:形式化与原文不符/算术错/非法实例;算术类 sol 带脚本重算;不对称:执行证据优先,存疑时 finding 站立 | sol | 无具体 flaw→驳斥无效 |
| FA 再审计门 | 单检重跑;strengthen-only(实验/指标/claim 逐字保留,只增不减);每 run 至多一次重写 | sol + 脚本 diff | 再 deficient→(c) abandon |
| I 可实现性门 | 每步具体对象(输入表示/具名估计器/输出 schema/默认超参+一句理由);无对方程符号的前向引用;open 洞内联【作者需决定】不编造 | sol(实现工程师人格,算力无关)+ 脚本 validator | 可自信填→(b) enriched_steps;真开放→(c) 诚实标注下传 |
| F 可行性+卡片门 | 五项 verdict(data/theory/engineering/falsification/compute——compute 由脚本对 intake 包络分桶);kill-switch 字节同一;expansion 完整性 | 脚本 + Opus | compute 超包络→(c) 标注下传(绝不缩水方法,I 门算力无关) |
| Select | 幸存者间终审 + 落选嫁接建议 | Opus | — |

**grill / 深度 / 广度 / 方法论的统一**:
- **广度** = P0 门的入口循环 Loop-R(r1 角度扇出 + r2 默认补洞/角度变异,§1.1d);入口但不止一遍。
- **深度** = 后续门被 unmet 判据**拉动**的发射器:fulltext top-up(B)、follow_up 引文追踪
  (transport 层路由,读卡时零新增 agent)、alias 多年窗(C)、谱系带查询(L)、家族 scoop(A)。
  深度不在入口设计,在判断失败处产生——**这就是回溯式检索**:原五条回溯边塌缩成
  "某门的 (a) 类出口"(= Loop-N)加"检查点的开放问题"(= Loop-P,§1.1d)。
- **grill** = T/A/FA/X 四门的判据集 + 盲区布线(A 只见 blocking_findings 切片,不见干跑报告全文,
  RS anti-anchoring 原样)+ 执行证据不对称(驳斥须具体 flaw;executed > reasoned)。
- **方法论** = S/G 的内容合同(15 模式+31 子模式卡、CHAIN+attested companion、premises/estimand、
  naive 三分支、证伪结构、substantive 差异化)——方法论不是相位,是判据与生成合同里的内容。

成本(级联+循环版,§1.1d 总账):Opus ≈10 / sol ≈7 / K3 ≈7 ≈ 24 次昂贵调用 + GLM ~40-55;
墙钟 ~120-150 min。

### 1.1d 循环搜索设计(三层循环 Loop-R / Loop-N / Loop-P,全部同构 GATE)

GATE 原语给了"按需拉取",但一问一答不等于迭代深搜。真实 DR 的深度来自**检索轮本身会循环**:
Gemini DR 的 plan 被读到的东西改写(Plan→Search→Read→Iterate,~80 查询);OpenAI DR 用边际增益停机
(新查询不再带来新信息即停);Perplexity "assess → continue until resolved";web-research.md 泄漏
原话 "Stop only when new queries stop surfacing new information"。V8 把这些收进三层显式循环,
**全部同构 GATE**(循环不是新原语,是 GATE 在不同尺度上的实例):

```
dag 轮(≤3,负锚重跑 = 最外层)
└ research 一轮
  ├ Loop-R  入口池循环(r1 恒定 → r2 默认开;硬上限 3 轮)      = P0 门自己的轮
  ├ 门链 P0→L→B→S→G→T→C→A→I→F→Select
  │    └ Loop-N  门内补救循环(B/L/S/A 各 ≤2 轮,可升级 3)     = 门内 (a) 出口的轮
  └ Loop-P  池级反思检查点(B 后、A 后,各一次)                = 检查点门(判据="不存在其答案
                                                                会改变相邻判断的未答问题")
```

#### Loop-R 入口池循环(广度 + 计划改写)

```
r1(恒定):
  Scope → 角度表(5-6 个,含 escape_mechanism / contrary_evidence / FROZEN 基线)
  搜索席 GLM ∥ 5-6,每席 ≤3 查询变体(hedge 首措辞);链路:本地语料 grep →
    search_papers.py → search_github.py → snowball(宽窗角度)
  dedup(URL/repo)→ 读波 ≤8 新卡(FROZEN 基线强制入池不占上限)→ follow_up 入队
  覆盖评估(全脚本):每角度 on-topic 卡数、必含槽(基线/方法近邻/对立证据)计数、follow_up 队长

r2(默认开——不是有洞才开;除非 r1 已饱和:槽全满 且 ≥20 on-topic 卡 且 follow_up 空):
  ① 洞补:必含槽 0 卡的槽 → query(槽名+benchmark/venue 变体)          ≤4 查询
  ② follow_up 波:队列去重(已在池内丢)→ 读                           ≤4
  ③ 角度变异(= Gemini 计划改写):r2 可加 ≤2 新角/删 0 产出角;
     新角度必须由 r1 卡的机制词/社区词派生(引发现卡 card_id)——查询从证据长出来 ≤2 席×2
  ④ 池矛盾裁决:两卡同量冲突 → 找裁决源                                ≤2
  读波 ≤6 新卡 → 重估覆盖

r3(仅条件触发:B 门入口判据又拉洞时,见 Loop-N 升级规则):≤4 查询 + 读 ≤4

出口(任一,脚本判):必含槽全满 / 边际增益=0(本轮新 on-topic 卡 <2 且翻转判据数=0)/ 轮数上限
```

#### Loop-N 门内补救循环(判断失败 → 定向检索 → 增量复判)

每门自带预算与轮上限;每轮 = 搜(≤3 查询)+ 读(≤2 卡)+ **只重判受影响判据**:

| 门 | 触发判据(示例) | 查询派生 | 预算 | 轮上限 |
|---|---|---|---|---|
| B | gap 支撑 <2 paper_id;卡间矛盾;承重数字单源;anchor residue 摘要级 | gap 陈述关键词 + venue 变体;矛盾量名 + "benchmark/ablation";top-up = paper_id 直取 | ≤6 查询 | 2(可升 3) |
| L | 家族占位不确定(2-4y 带) | 家族名 + 经典 venue(DBLP/journal 限定) | ≤4 | 2 |
| S | 模式落点占位不确定 | 经典机制名 + 领域词 | ≤2 | 1 |
| A | parametric_family_concern;alias 命中需第二源;威胁论文全文缺 | 家族名+其词汇短语;alias 词 + 年窗放宽;paper_id 直取 | ≤4 | 2 |

**升级规则**:某门两轮边际增益均 >0(仍有新 on-topic 卡或判据翻转)且预算未尽 → 允许第 3 轮,
写入 bundles(升级可见,可审计);否则带 unresolved 前进(B 门 = single_family 标记,Generate
自己决定接不接)。

#### Loop-P 池级反思检查点(生成式——这是"研究本身变深"的机制)

与 Loop-N 的区别:Loop-N 填**已列出**的判据之洞;Loop-P 问**没列出的问题**。
检查点门判据:"不存在一个其答案会改变相邻判断的未答问题"——met 当且仅当反思席找不到这样的问题。

```
Loop-P①(B 门 advance 后):
  Opus 反思席(1 席,读整池摘要+B 工件):
    "池里还有什么系统性盲区?哪个未答问题的答案会改变 bottleneck/gaps 的成立?"
    典型产出:社区盲区("池全是 RL 群体——该 failure 在 bandit/OPE/生存分析文献里有已解实例吗?")
  → ≤4 query(GLM)→ 新卡入池
  新卡若与 B 工件矛盾 → B 门增量复判一次(仅一次)

Loop-P②(A 门 advance 后):
  同构,对象 = 幸存候选 + 审计结论
  典型产出:家族 scoop 追深(alias 二源)、竞争实现追踪(github 第二 repo)、
           威胁论文的后续工作(citing 窗)
  新卡若推翻存活裁决 → 回 A 门增量复判一次(仅一次)
```

#### 公共机制(三层共用,防循环失控)

1. **查询账本**(bundles 落盘,可审计):
   `{qid, q, why, source: {gate, criterion | card_id | checkpoint}, round, results: [card_ids],
     gain: {new_on_topic, criteria_flipped}}` —— 每条查询的出处与增益全部可回放。
2. **账本去重**:规范化查询(小写/去停用词/词序折叠)不得二次发出,脚本拒绝;follow_up 按 paper_id 去重。
3. **查询必须带出处**:r2/Loop-N/Loop-P 的每条 query 须引用触发它的卡或判据——"查询从证据长出来,
   不从想象长出来"(4R 纪律推广到所有循环层)。
4. **边际增益脚本判,不问模型**(防"再搜一次"偏置):本轮 gain.new_on_topic <2 且
   gain.criteria_flipped =0 → 该层循环立即出口,即使预算未尽。
5. **读波纪律**:只读新 URL;FROZEN 基线强制入池不占上限;引文验证二元(`_quote_at` ±2 行)。
6. **每层轮数硬上限**(Loop-R 3 / Loop-N 2+升级 / Loop-P 1);检查点复判仅一次。
7. **检索渠道不变**:本地语料 → search_papers.py → search_github.py → snowball(宽窗);
   Loop-P 的 citing 窗查询走 snowball。

#### 预算与墙钟(循环版总账)

| 层 | 查询 | GLM 席 | 昂贵 |
|---|---|---|---|
| Loop-R r1 | 12-18 | 搜索 5-6 + 读 ≤8 | P0 覆盖判 K3 1 |
| Loop-R r2 | 6-10 | 搜索 ≤4 + 读 ≤6 | — |
| Loop-R r3(条件) | ≤4 | ≤2 | — |
| Loop-N(B/L/S/A) | 8-16 | 搜索+读 6-12 | —(门级联已计) |
| Loop-P ×2 | ≤8 | 读 ≤6 | Opus 2(反思席) |
| 合计 | 34-56 | ~40-55 GLM | Opus ≈10 / sol ≈7 / K3 ≈7 ≈ 24 |

墙钟 ~120-150 min(比无循环版 +20-30:每轮检索波 ~8-10 min,边际增益早停平均省回一轮)。

#### 示例走查(三层各一)

- **Loop-N(B 门)**:判据"gap G1 支撑 ≥2 paper_id"unmet(仅 card_17)→ K3 锚定 → Opus (a) 类
  → query = G1 陈述关键词"verification schedule self-censoring" + venue 变体 → GLM 搜 →
  card_31/32 入池(on-topic)→ 增量复判仅 G1 → met → advance。
- **Loop-R r2**:r1 后必含槽"FROZEN 基线"0 卡(脚本洞)→ query = 基线名 + benchmark 词;
  同时 card_8 的 follow_up 指出"真正机制在其引文 [14]"→ 读 [14] → card_33;角度变异:card_31
  的机制词派生新角"off-policy correction 家族"→ r2 第 5 席。
- **Loop-P①**:B advance 后反思席:"池全是 RL 群体"→ query = "adaptive verification acceptance
  censoring bandit OPE" → 命中 2 篇 OPE 卡 → 不矛盾 B,但谱系加 collateral 节点 → L 增量更新一次
  (该家族的历史代表进入回归防护)。

### 1.1a 两层循环:广度一遍 + 分析驱动的定向再搜索

出处:~/oss/system_prompts_leaks 四份 DR 泄漏 + 真实 DR 观察(Gemini Plan→Search→Read→Iterate,
plan 被读到的东西改写;OpenAI 边际增益;Perplexity "assess → continue until resolved")。
**深度的来源不是检索自己查覆盖,而是分析发现自己不知道什么**——覆盖循环只保证"读过",
保证不了"够用"。具体形态即 §1.1c 的 GATE(所有门;检索=门内函数),下面是数据流:

```
0 Scope → 角度(含 escape_mechanism/contrary_evidence)
1 广度 Search(GLM ∥ 5-6 席,每席 ≤3 查询变体 hedge 首措辞)
   链路:本地语料 grep → search_papers.py → search_github.py → snowball(宽窗角度)
   硬洞补查:必含角度/FROZEN 基线 0 张卡 → 脚本判 → 补查 ≤1 轮(≤3 席),不算循环
2 Read(GLM ∥ ≤8,仅新 URL,FROZEN 基线强制入池不占上限)
3 Verify(引文二元,一遍跑全部卡)

4 Bottleneck 独立(3 席 ∥) → 4b Opus 合并 = **反思席**,触发集三件:
   ① gap 支撑 <2 paper_id → 不丢 gap,输出 needs_search[]{query 从 gap 陈述派生, why}
   ② 卡间矛盾:两张卡对同一量方向/数字冲突 → 找裁决源
   ③ 单源承重数字:下游要用的关键数字只有一张卡 → 定向找第二源
   4R 定向再搜索:GLM ≤3 席搜 + 读卡(≤3) → 卡入池 → 重新合并(轻量确认)
   ≤2 次;第 2 次后仍 <2 → 该 gap 标 single_family 进 Generate(Generate 自己决定接不接)

5 Generate(gaps × RS 15 模式) → 6 Floor(scoop 三路 + 硬底) → 7 Converge → 8 Select
```

**read 阶段引文追踪(回溯最内层,真实 DR 的核心)**:Read 卡加可选 `follow_up[]`:
{target: paper_id|query, why}——读者发现"真正的贡献在它引的那篇"时标记。装配段脚本收集全部
follow_up → 去重(已在池内丢) → 预算 ≤4 排进读卡队列,由普通读者席读。零新增 agent,只加路由。

**回溯地图(与真实 DR 的对照)**:真实 DR 的回溯在检索器内部(agent loop,每查询自适应,~80 次);
我们的回溯是相位间的**有界边**——读时(follow_up,新增)、分析时(4R 三触发)、产出后(scoop 三路)、
失败后(revise 归因路由)、轮间(dag revise)。一轮实际检索 ≈30-40 次查询,全部对准 FROZEN;
每条边的预算是常量,可按需放宽。

- **RS ≥2 paper_id 纪律从过滤器变成再搜索触发器**:证据不足先搜再判,不是先丢。
- 查询质量:4R 的查询从 gap 陈述长出来,不是 Scope 预想的——这是"研究本身变深"的机制。
- 预算(§1.1d 定稿):Loop-R 18-32 + Loop-N 8-16 + Loop-P ≤8 ≈ 34-56 查询;边际增益脚本早停。
- 泄漏机制照抄:空路径返回 stats 不 throw;弃权感知法定票(≥2 有效且 <2 refute 才活);
  pipeline 无屏障(角度完成即 dedup→read);排序锚 FROZEN 原问题不锚角度词。

### 1.2 昂贵调用明细(research ≈23 次,级联版)

| 调用 | 模型 | 节点性质 |
|---|---|---|
| P0 覆盖判定 | K3 1 | 判断:真相关 vs 关键词噪声 |
| L 谱系重构 | Opus 1 | 生成:age-band 祖先重构(parametric)+ K3 攻击含糊旗 |
| B 瓶颈门级联 | K3→sol→Opus 串3 | 判断:RS bottleneck_identify 判据合同,锚定 |
| S 选择门级联 | Opus→K3→sol 串3 | 判断:2.1 合同(锚型/组合/回归落点) |
| Generate ×3 席 | Opus+sol+K3 ∥ | 生成:角色镜头(pivot/formal/跨域),不合并 |
| T 追踪门级联 | sol(执行)→K3→Opus 串3 | 执行+判断:T2-T5 stdlib 真跑,T1 双读/分级 |
| A 审计门级联 | K3→sol→Opus 串3 | 判断:五检+处置,盲于干跑报告 |
| FA 再审计 / X 驳斥复核(条件) | sol 1 / sol 1 | 有界单检 / 算术重算 |
| I 可实现性 | sol 1 | 执行:实现工程师人格,算力无关 |
| F 可行性 + Select 终审 | Opus 2 | 判断:包络分桶(脚本)+ 终审嫁接 |

### 1.2a 决策权分割(DR js 原型:编排决策全在脚本,agent 只产内容)

Anthropic 自家 DR workflow-script.js 里没有任何 agent 决定"下一步做什么"——读哪个 URL(排序+去重+预算)、
验证哪 25 条(importance×quality 切片)、谁活(计票),全是代码。V8 同构:

| 判断 | 归属 | 规则 |
|---|---|---|
| 读哪篇 | 脚本 | relevance 排序、URL/repo 去重 Map、广度预算 ≤8 |
| 引文真伪 | 脚本 | `_quote_at` ±2 行 fuzzy,找不到即丢(二元) |
| 广度是否够 | 脚本 | 必含角度/FROZEN 基线 0 张卡 → 补查 ≤1 轮 |
| gap 去重并集 | 脚本 | gaps 并集按 (paper_id 集, 关键词) 去重,标 raised_by[] |
| **哪些 gap 证据不足** | **Opus 合并席** | <2 paper_id → needs_search,不丢 gap |
| Floor 四条 | 脚本 | 预算/基线表/矛盾检查/阈值≥Hard bounds |
| 排名输入 | 脚本 | 三家分数中位数 + (not capped, soundness, novelty, scoop)——作为 Opus 合并的输入,不替代仲裁 |
| 无锚 findings | 脚本 | 合并前直接丢(三家的发现必须带 paper_id+行号或候选字段原文) |
| 硬底 kill | 脚本 | ≥2 家以相同锚断言同一 kill 条件 → 判死,不问 Opus |
| bottleneck 是什么 / 选哪个候选 | **Opus** | 品味,错误会级联到下游一切 |

### 1.2b 提示词对齐(DR 模式 → V8 席位)

| DR 模式 | 原文要点 | V8 去向 |
|---|---|---|
| 精炼许可 | "with the query above (or a refined version)" | Search 席允许改写查询 |
| 排序锚原问题 | "Rank by relevance to the ORIGINAL question, not just the search query" | Search 席按 FROZEN 现象排序,不按角度词 |
| 可证伪+引文锚 | "FALSIFIABLE...direct quote...central/supporting/tangential" | Read 卡(扩 RS 字段,见 §1.2c) |
| 验证五问+默认杀 | checklist + "Default to refuted=true if uncertain" | Verify 席;硬底已脚本化 |
| 失败行为显式 | "If the fetch fails...return claims: [] and unreliable" | 每席 schema 带失败分支,空返回不 throw |

### 1.2c RS 嫁接点(卡片 schema = DR 与 RS 的契约)

DR 循环管"证据从哪来",RS 管"证据变成什么 idea"。交接只在 Read 卡 schema:**卡片带 RS 字段,
循环结构不用为 RS 改任何东西**。Read 卡字段 = V7 GENE_FIELDS/AVOID_FIRST(2604.15097 Table 7-8)
+ mechanism_class + discriminating_observation + 带行号数字 + kind(paper/repo)。
下游:卡 → Bottleneck(失败不说药方,gaps ≥2 paper_id,不足触发 4R 再搜索)
→ Generate(gaps × 模式组合,naive_baseline 三分支)→ 5C(执行式干跑)
→ Floor(scoop 四轴)→ Audit(五检 + 四维,trio)。

### 1.2e RS 深读补遗(V8 原计划漏掉的六项)

| # | RS 机制 | V8 去向 |
|---|---|---|
| 1 | 模式组合(2.1):候选默认 CHAIN——锚模式+attested 次模式(companion-combos)+命名中间对象;anchor-only 要 composition_note 辩护 | Generate 装配段给每席分"模式组合"不是单模式;companion-combos.md 进关键词常量 |
| 2 | 跨轮软负锚:兄弟 run 的候选 title+signature terms 作负约束,防重复发明 | research 第 2 轮起装配段自动附前轮候选签名词 |
| 3 | premises ledger(2.2):承重前提+领域依据;observation-model 前提;estimand 声明 | Candidate 加 `premises[]`;experiment Draft 直接吃 |
| 4 | 执行式干跑(2.3):"逻辑 bug 读起来很顺,只有算才露馅"——stdlib 脚本真跑+退化探针+claim→step 分级 | 新相 5C:GLM 每候选干跑,杀逻辑破损候选于实验之前 |
| 5 | 独立构造 naive baseline(绝不用候选自述版),跑同实例判 confronts/equivalent/n_a | 5C 内做 |
| 6 | 失败归因路由:两次死于 exact-mechanism subsumption → 归罪 bottleneck 框架,重跑 Bottleneck(do_not_generate 是合法出口) | research revise 模式:Floor 连续 scoop 杀死 → 回 4a,不是再摇 Generate |

另:parametric_family_concern(未检索到的机制家族名+查询词)→ A 审计门 (a) 类出口,当场 scoop 检索(§1.1c;RS 单遍才留旗子)。

### 1.2f 额度纪律(trio 版)

- **判断节点 = trio + Opus 合并**(4a/4b、7a/7b、Judge):每处 4 次昂贵调用,换取三家族错误去相关。
- **生成节点 = 角色分工不合并**(5、Draft):sol→formal 型模式、K3→跨域型、Opus→pivot 型、GLM→广度。
- **执行/检索 = GLM + 脚本**:数字只算一次,审过不再算。
- 多样性靠结构(角色镜头/模式组合/软负锚),不靠 extended thinking。
- 可调档位(若 Opus 8/回合太重):7b 与 8 合一(-1)、Generate 的 Opus 席换 GLM(-1,丢 pivot 镜头)。

### 1.2d 检索通道(第 4 通道:GitHub)

链路:`本地语料 grep → search_papers.py → search_github.py → snowball.py(宽窗角度)`。
`search_github.py`(新,~60 行,GitHub Search API,gh token)输出与 search_papers.py 同构:
`{items: [{url, name, desc, stars, pushed_at, language}]}`,去重 key = repo URL。

- Search 相:方法论文的 closest_prior 常在代码不在 arxiv(实现先于论文);Read 卡 kind=repo,
  引 README 行号,同池去重。
- Floor 相:signature terms 搜 GitHub,抓"论文里看不见的 scoop"(未发表的实现在跑)——
  补 RS scoop_check 只搜文献的盲区。

### 1.3 RS 技巧去向

已逐一并入 §1.1c 的判据清单与 G/G 合同(每条 RS 功能一行,含 unmet 三分类)。
旧表更正:T1-T5 不删(= T 追踪门,执行式干跑);五检不简化(= A 审计门逐条);
method lineage 独立为 L 门;parametric_family_concern 从 Converge 席旗子改为 A 门 (a) 类当场检索。

---

## 2. `experiment.workflow.js` — CodeReview 骨架 (~12 agent)

### 2.1 build 模式(5 agent + k verifier)

| # | 相位 | 模型 | agent | 说明 |
|---|---|---|---|---|
| 1 | Draft | **sol** | 1 | B1 spec: steps 到函数、arms↔rows 映射、forbids ⊇ gene.avoid |
| 2 | Implement | GLM | 1 | worktree 里写代码 + SMOKE + diff |
| 3 | Find | **Grok** + GLM | 2 | Grok 主审 + GLM 域镜头(spec-drift/leakage/integrity 三合一) |
| 4 | Verify | GLM | k | 每 (file,line) 组一验证者 ← **CR 的 group-by-location** |
| 5 | Gate | 脚本 | 0 | CONFIRMED critical/high → blocked |

**Grok 缺席回退**:GLM 三镜头(spec-drift / leakage / integrity 独立各一)+ GLM 分组验证。

### 2.2 judge 模式(5 agent)

| # | 相位 | 模型 | agent | 说明 |
|---|---|---|---|---|
| 0 | Index | launch_wrap 钩子 | 0 | 脚本写 evidence/index.json |
| 1 | Recompute | **sol** | 1 | 重算每个数字 + CI95;executed=true 必须 |
| 2 | Judge 独立 | **Opus+K3+sol** ∥3 | 3 | **trio 同题**(判断节点):各出 verdict + statement + transitions,锚定(数字引 R 行) |
| 3 | Judge 合并 | **Opus** | 1 | 合并四规则:无锚丢、≥2 家同锚 kill 条件→脚本判死、分歧仲裁、反思 |

### 2.3 昂贵调用明细(每回合 6 次)

| 调用 | 模型 | 为什么 |
|---|---|---|
| Draft | sol | 算法设计 + 数学(生成节点,角色分工) |
| Recompute | sol | 独立重算数字(执行,数字只算一次) |
| Judge trio | Opus+K3+sol | 判断节点:三家族错误去相关 |
| Judge 合并 | Opus | 测量强项=审查收敛 |

---

## 3. `paper.workflow.js` — PaperJury 骨架 (~10 agent)

### 3.1 draft 模式(5 agent)

| 相位 | 模型 | agent | 说明 |
|---|---|---|---|
| Claims | **脚本** | 0 | C.text 直接进稿(零 agent) |
| Write | GLM | 5 | 每节一个(∥):数字带 %src:R-n、cite 从 lit 表、C.text 逐字 |

### 3.2 round 模式(3 + k agent)

| # | 相位 | 模型 | agent | 说明 |
|---|---|---|---|---|
| 1 | Referee | **sol + K3** + GLM | 3 | 隔离;八维 + claim 表;无搜索无 artifact |
| 2 | Merge | 脚本 | 0 | passage_id 派生 + (passage, type) 合并 |
| 3 | Contest | GLM | 0-k | 每单家 major 一席 |
| 4 | Route | 脚本 | 0 | text_only → patch;needs_* → add_row;hypothesis_mismatch → revise |
| 5 | Patch | GLM | 0-k | exact-once + 无新数字 + 不碰 C 行 |
| 6 | Audit | **脚本** | 0 | 四项字符串比对(零 agent) |

### 3.3 昂贵调用明细(每回合 2 次)

| 调用 | 模型 | 为什么 |
|---|---|---|
| Referee sol 席 | sol | 数字/统计审查 |
| Referee K3 席 | K3 | 跨域遗漏检测 |

---

## 4. 每回合昂贵调用总账

| workflow | Opus | sol | K3 | Grok | GLM | 总 |
|---|---|---|---|---|---|---|
| research | 6 | 3 | 3 | 0 | ~28 | ~40 |
| experiment build | 0 | 1 | 0 | 1 | 2+k | ~5+k |
| experiment judge | 2 | 2 | 1 | 0 | 1 | ~6 |
| paper draft | 0 | 0 | 0 | 0 | 5 | ~5 |
| paper round | 0 | 1 | 1 | 0 | 2+k | ~4+k |
| **总计** | **8** | **7** | **5** | **1** | **~38** | **~57** |

> research Opus 6 = 4b 合并 + 5 pivot 席 + 7b 合并 + 8 Select(4a/7a trio 各含 1)。judge Opus 2 = trio + 合并。
> **昂贵 ~21 次/回合**,比单席版(15)多 6,换来每个判断节点三家族错误去相关;可调档位见 §1.2f。

---

## 5. V7 → V8 删除清单

| 部件 | 理由 |
|---|---|
| H + H.contract + P 三对象 | 合成 Claim |
| dossier 十一栏 / 40 facts / lineage 年代带 | 下游只用 facts + closest_prior |
| hypothesize 3 lens + Contrarian + 3 票二元杀 | 换成 Generate 6 席 + Floor 硬底 + Converge 中位数排名 |
| FALSIFICATION_FOUR 硬要求 | 方法型改条件项 |
| 7×7 双 Profile agent | Select 前脚本数格 |
| specify DryRun T1-T5 + Opus 设计审 | SMOKE + spec-drift 承担 |
| experiment Scope + Launch agent | 装配段 + put 承担 |
| adjudicate Package + Extract | launcher 写 index,Recompute 给 metrics |
| manuscript Opus Claims 席 + Audit agent | C.text 直接进稿;审计变脚本 |
| Referee 的 novelty_collision + method_validity | 裁判无搜索无 artifact |
| SPEED 旗子 | 减法写进正式路径 |

---

## 6. dag.py 改动

| 处 | 改动 |
|---|---|
| 对象 | dossier/ → claims/C(含 contract);删 hypotheses/、paper/claims/ |
| 起点 | 无 active C → research new |
| C rows 开 + 无 M 在飞 | research add_mechanisms |
| M specced 无 launch | experiment build → put 起跑(不是 agent) |
| launch 完成 | experiment judge |
| Hard bounds 校验 | put research:每个 contract row 阈值 ≥ FROZEN |
| C.strength | put experiment judge 写 |
| prewrite/draft | draft 条件 = 稿中无 %C-n 行 |
| 请求类型 | 6 种(去 novelty_collision、method_validity) |
| 并发调度 | 已实现(collect all ready → priority → WAIT only when empty) |

---

## 7. 墙钟预算

| workflow | 串行深度 | 昂贵调用 | GLM 调用 | 墙钟 |
|---|---|---|---|---|
| research new | 8 + 反思环 | 12 | ~28 | ~30 min |
| experiment build | 4 | 2 | 2+k | ~15 min |
| experiment judge | 3 | 6 | 1 | ~10 min |
| paper draft | 1 | 0 | 5 | ~5 min |
| paper round | 4 | 2 | 2+k | ~10 min |
| **全回合** | | **~21** | **~38** | **~70 min + GPU** |

V7 是 330 min。V8 是 70 min。**4.7 倍加速。**

---

## 8. 实施顺序

**冻结令 2026-09-05**:paper.workflow.js、dag 的 paper 分支与 T4+ 真跑全部 freeze,直到 DR 与 code review 两轮真模型测试通过。测试阶梯:①research 降档跑(loops r2-only,~20 昂贵+~30 GLM)→②产物复盘→③experiment design+build@T0 no_launch(0 GPU,验 R2/GLM+Grok)→④修复+回归。

**状态 2026-09-05**:① research.workflow.js 已实现(1325 行,`.claude/workflows/research.workflow.js`)——
三层循环 + 全门链 + 级联 + 查询账本 + 脚本硬底,`loops:{r2,p1,p2}` 可关;mock 运行时全流程两场景
(友好/敌意:含 Loop-N 补救、B patch、A revise→patch→FA、kill-switch 守卫)跑通,友好 42 调用 /
敌意 54 调用,byModel 与本表吻合(Opus 10-11 / sol 6-8 / K3 6-7 / GLM 19-28)。
② search_github.py 已实现(第 4 通道,真 token 实测 3/3 命中)。
③ mock 回归工具入库:`.research/tests/mock_runtime_research{,_hostile}.mjs`(在 `.research/tests/` 下 `node mock_runtime_research.mjs`)。
未做:dag.py 接线(args 从 GOAL.md 构造 + put 校验 selected 形状)、experiment/paper 两个 workflow、真实 dry-run。

**评审修复轮 2026-09-05(外部全读 1398 行后的 16 项发现,全修)**:
P0:#1 T:merge 缺席/漏判 → 覆盖检查 error(mock MERGE_MODE=null/partial 双验);#2 未审计候选静默蒸发 →
K3/仲裁双覆盖检查;#4 kill-switch 拆分——compute_budget 永无门(篡改实测回滚),falsification 仅授权门
(mock 实测放行);#3 补救卡进 prompt(liveCards,标 [unverified])。
P1:#5 A/P2 补救卡一次 a4 增量复判(反思可选、复判不可选);#6 有 patch 必再攻一轮;#7 席位缺席全统一
为 error(L/S/T attack + 四处 verify);#8 revise 空 targets → error;#9 single_family 改为末尾派生(patch 不再抹掉)。
P2:#10 r2 洞补按槽 kind 入池(slots 可见);#11 Verify 后复检下限;#12 Verify 分块 ≤40 项并行;
#13 五检 result 全 enum + 硬底精确匹配(reject_lesson=triggered / anti_pattern=matched_undelivered /
paper_threat=unaddressable);#14 Select 失效 → 脚本回退(feasibility→最少 open 洞),不 RETRY 整轮;
#15 mock 守卫修活;#16 search_github.py 去 sort=best-match、非 JSON 输出可读。
另:collisionHits var→let 提块外。回归:friendly/hostile selected、MERGE_MODE=null→"T merge seat absent"、
partial→"did not disposition cand-2, cand-3"。**v7 六 workflow 已归档 `.research/archive/v7-workflows/`**
(.claude/CLAUDE.md 的 v7 主循环描述待 V8 dag 接线时一并重写)。GitHub App MCP 已装:主会话 PR/issue 用 MCP,
workflow 检索仍走 Bash 脚本(交互式认证 MCP 在 headless 运行可能缺席 = infra 风险)。

1. `dag.py`:对象模型(C 替代 H+contract+P)、Hard bounds 校验、put research/build/judge
2. `research.workflow.js`:全相位(核心，~350 行)
3. `experiment.workflow.js`:build + judge 两个模式(~250 行)
4. `paper.workflow.js`:draft + prewrite + round(~200 行)
5. `launch_wrap.sh`:退出钩子写 evidence/index.json;`search_github.py`(~60 行)
6. 测试:fixture + node 装配夹具

**workflow js 抄 CC 官方 deep-research script 的七条惯例**(~/oss/system_prompts_leaks/Anthropic/
Claude Code/bundled-skills/deep-research/scripts/workflow-script.js):
①schema 全部顶部 const;②prompt 是纯函数(angle/source 参数化);③`pipeline()` 无屏障——
角度完成即去重即读;④去重 Map + 预算计数器是循环携带态;⑤弃权感知计票(`valid≥2 && refuted<2`,
全弃权≠活);⑥任何空路径返回带 stats 的结构化对象,绝不 throw;⑦返回值带 agentCalls 统计。

---

## 9. 剩余工作与对齐清单(2026-09-05,research + experiment 两核心已成)

跑通一轮(0 GPU)还差五件,按依赖顺序;出稿再差两件。终点不是 draft,是 paper round 连续两轮收敛 → `STOP: DONE`。

| # | 件 | 内容 | 阻塞 | 量 |
|---|---|---|---|---|
| 1 | args 口径统一 | research 的 `frozen` 是 FROZEN 原文字符串,experiment 当对象读 `kill_cap_gpu_h`/`total_gpu_h`。定:`frozen` 永远是原文;dag 另解析 `budget{kill_cap_gpu_h,total_gpu_h,rounds}` 与 `platform`(=substrate)对象随 args 传;两个 workflow 都改读 `A.budget` | dag、experiment | 小,先做 |
| 2 | GOAL.md 改 V8 形状 | Objective / Platform / Budget / Measured / Hard bounds / Out of scope;keep rule 挪进 Claim.contract,由 research 产出、put 对 Hard bounds 校验只许收紧 | dag 解析 | owner 写 |
| 3 | dag.py 重接线 | 对象:`claims/C`(含 contract rows、strength)取代 H+contract+P;M 加 `tier`、`arms[]`,同候选不同级不同 M;R 加 tier;E 枚举映射(experiment 的 supports/partial/refutes/inconclusive ↔ supports/weakens/refutes/underdetermined/method_invalid)。tier 状态机:design→K→T0→T2→T3(support)→RR→T4→T5→T6,只许降级回退。put 校验:Hard bounds、越级 REJECT、T2 不产 E、statement 用词天花板、arms↔rows 双射。**launch 挪进 put**(agent 不再 systemd-run;RUNNING 存在时 next 不派 build)。research 三种出口(do_not_generate / all_blocked / all_abandoned)的 negative_anchors 回写为下轮 `redo`。`.claude/CLAUDE.md` Main 卡按新 mode 集合重写 | 一切 | 最大件 |
| 4 | launch_wrap.sh 补两件 | 退出时写 `evidence/index.json`(path/bytes/sha8/what/exit/phase/early_kill,journal 尾 200 行);test-half 读取计数写入 index(judge probe 的 `test_half_reads` 现在靠 GLM 从日志猜) | judge | 小 |
| 5 | tools/recompute.py | 固定 result_contract 下确定性重算:均值、配对 per-frame bootstrap CI95(10k,固定 seed)、clean_cost、numeric-token 比对(73.2≈73.20,73≠73.5);metric 不在注册表才落 sol。T3 预检与 E:recheck 的"数字在不在表里"同用此脚本 | judge、support | 中 |
| 6 | paper.workflow.js | 见 §10 | 出稿 | 中 |
| 7 | paper mock + dag put paper | 收敛 `genuinely_new==0 && open_requests==0 && audit_pass` 连续两轮 → DONE;轮数上限读 Budget | 出稿 | 小 |

真跑分三级:Stage 1 = research 一轮 + design + build 到 gate(NO_LAUNCH,0 GPU,验对象链与状态机);
Stage 2 = 一个 T0 eval-only 探针真起跑(分钟级,验 launch_wrap→index→judge→put);Stage 3 = T2。第一次不放 T4。

**待定(定了省事):** rr 与 paper round 是否同一 REVIEW 实例。现在 experiment 的 rr 是 Opus 单席出行,
EXPERIMENT-PLAN §1.5 写的是三裁判隔离 + 脚本路由。建议:Referee prompt + 合并 + 路由抽成 paper.workflow.js
的常量与函数,experiment rr 只做"读 E → 调同一段路由",两处一份代码。这决定 paper.workflow.js 从哪起手。

DONE 之后的交付物:ms.tex、ledger + journal(每条改动可回放)、每个数字的重算表文档、evidence index、
D0 三表与 RR 行集合(审稿人问 "why not X" 时能指到行)、T6 复现包。submission check / humanization / 图表排版
归 owner,不进流水线(§10 之前已划出)。

---

## 10. 写作 workflow 备忘(paper.workflow.js;只记来源与抄法,后续细定)

**原则不变:** 写作是实验的投影,不是独立创作。C.text 原文进稿(`% C-n`),数字只从重算表文档(`% src: R-n`),
cite 只从 lit 表,负结果句必在;审计四项全脚本(数字对 R、cite ∈ lit、C 行在、负结果在)。裁判隔离、
passage_id 派生合并、exact-once 补丁、journal 回放照 V7 manuscript 保留。

**实验期间写作(prewrite)是硬需求,不是可选:** D0 一过,Intro / Related Work / Method / Experimental Setup
就能写——它们只依赖 Claim、dossier、D0 设计与 spec,不依赖结果;表骨架从 D0 `final_tables` 生成(全 TBD,不写死
方法名)。触发:dag 在 `experiment build` 首次 gate_passed 后、GPU 空档派 `paper prewrite`(pri 低于一切实验)。
prewrite 禁写任何结果性动词("improves / achieves / confirms");V7 的 prewrite/draft 互斥 bug 修法:draft 触发条件 =
稿中无 `% C-n` 行,不是无 ms.tex。T4 E 落地 → draft 只写 Results/Discussion/Abstract 并回填 TBD 槽。

**三个来源,各抄什么(先记,后续逐条读):**

| 来源 | 位置 | 抄什么 | 不抄什么 |
|---|---|---|---|
| ccf | `~/autoresearch/CCFA-Skills/ccf-paper-writer`(storyline-blueprint、citation-workflow、WRITE_RULE)、`ccf-humanization`(warning-only、无注入、去 AI 腔、confirmed 方法门)、`ccf-integrity-auditor`(claim-evidence 四态)、`ccf-paper-reviewer`(八维 + claim table,已在 Referee 里) | storyline 骨架作 section_order;WRITE_RULE 原文;humanization 作补丁后一遍 GLM 润色(只改措辞不改数字,装配段 diff 数字集合为空才落);四态审计口径 | ccf-submission-checker / visual-composer / latex-templates(owner 侧) |
| nature-skills | `~/autoresearch/nature-skills/skills/`:nature-writing、nature-polishing、nature-ref-verifier、nature-statistics、nature-figure、nature-response、nature-reviewer | nature-writing 的段落角色(每段一个功能句)与 Results 写法(数字带 CI 与 n);nature-ref-verifier 作 cite 存在性的第二道(脚本 lit 表之外,DOI/arXiv 元数据核);nature-statistics 的报告清单(效应量、CI、配对、多重比较)进 Results 的 R4 检查;nature-response 留给 rebuttal(流水线外) | nature-paper2ppt、paper-to-patent、proposal-writer、downloader(已有 fetch_text) |
| PaperJury | `~/autoresearch/paperjury/`(ledger.js / journal.js / apply-patch.js / spine.md / review-panel.workflow.js / methodology.md) | 已抄:ledger 行、exact-once 补丁、journal、四态锚、裁判隔离、clerk 收敛。再抄:review-panel 的裁判"每轮都是第一次读稿"措辞;spine 的锚句回滚规则原文 | defense / jury-of-12 / recall-audit / 段落 hash(§8 已排除) |

另两处可参考但不作主源:`~/autoresearch/Composite-writing/skills/`(agent-research-skills 的 paper-writing-section /
related-work-writing / table-generation / self-review 四个;ARIS 的 paper-write / paper-claim-audit 已在 R4 消费)。

**paper.workflow.js 三模式的形状(与 V7 manuscript 的差别):**
- prewrite:5 节 GLM 并行,输入 Claim + dossier core + D0 + spec;表骨架脚本生成;零 claim 句。
- draft:无 Opus Claims 席(C.text 直接进稿);Results 每个数字从重算表文档带 `% src`;Discussion 必含每条
  E.limitations 与 credit_due(honest null 作 strength 写,ARFT Iron Rule 3);Abstract 最后写,只许引已在正文的句。
- round:Referee(sol/K3/GLM 隔离,与 rr 同一份 prompt)→ 派生 passage_id 合并 → lone-GLM 降级 → GLM contest →
  脚本路由(text_only/scope_overclaim → 补丁;needs_* → 先查 RR 行:已关带 row id 判 invalid,未关开 Q)→
  GLM exact-once 补丁(不碰 `% C-n` 行、无新数字无 `% src`、段落数不变)→ **脚本审计**(替代 V7 的 Audit agent)→
  humanization 一遍(可选,数字集合不变才落)。裁判 request_type 去掉 novelty_collision / method_validity。
