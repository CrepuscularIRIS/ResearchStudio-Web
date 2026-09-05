# V8 Research v2 — Speculative DeepResearch × RS 转换先验(席位/提示词/判定 定稿)

2026-09-05 定稿。取代 research.workflow.js v1 的 12 相位门链。一句话:**RS 不再是管线,是搜索先验;
昂贵模型永不互相等待;杀候选只凭证据或形式论证,不凭意见。**

---

## 0. 架构图

```
                    ┌─ Opus-M(1)  deepest reframe ──────┐
FROZEN ──┬──────────┤                                     │
(+local_digest)      └─ K3-H(1)    adversarial reframe ──┤
         │                                                 │
         ├─ GLM-L: baseline 搜索 ──────────────┐          │
         ├─ GLM-L: closest 搜索                 ├─ 基础证据池
         └─ GLM-L: contrary 搜索 ──────────────┘          │
                                                           ▼
                                              Sol-H(1) 形式化路线选择
                                              (每条 reframe:formal object? naive?
                                               变换改变什么?什么能杀?可跑吗?)
                                                           │
                                              GLM-H 路线规划器 → 查询波
                                              (每查询带 {query, route_id, if_yes, if_no})
                                                           │
                                              路线状态更新(live/supported/weakened/killed)
                                              动态停止:live≤2 ∨ 预算尽 ∨ 零状态变化
                                                           │
                                              GLM-H bottleneck digest(+负知识切片抽取)
                                                           │
                                              GLM-H 一次匹配 31(仅幸存父卡;compressed index)
                                                           │
                                              GLM-L ×10 IdeaSketch(短)
                                                           │
                                              GLM-H 组合修剪(机械三则)→ top-4
                                              ┌────────────┴────────────┐
                                       GLM-H ×4 全 Claim        GLM-L ×4 碰撞
                                       (与碰撞并行!)            (signature/alias/github)
                                              └────────────┬────────────┘
                                              K3-H 攻击(带负知识) ∥ Sol-H 形式审
                                                           │
                                              JS 确定性合成(枚举,无分数)
                                              ┌──── 1 幸存 → Claim
                                              └──── >1 → 机械比较 → 平局才 Opus-M pick
```

墙钟:典型 ~50 min(最少 ~35;路线波动态 1-3 个)。

---

## 1. 模型分工表(非对称先验)

| 模型 | 角色 | 永不做 | 调用帽 |
|---|---|---|---|
| **GLM-L**(glm-5.3 低档) | 基础检索/路线查询/sketch/碰撞——**投机铺量** | 最终硬判断 | ~20-25/轮 |
| **GLM-H**(glm-5.3 高档) | 路线规划/digest/31 匹配/修剪/Claim 展开 | — | ~8/轮 |
| **Opus-M**(claude-opus-5, medium, 小 context) | ①概念先验 reframe ②top-2 品味仲裁 | 读全文池、长链执行、反复审计 | **≤2** |
| **K3-H**(k3-256k, fresh context) | ①对抗先验 reframe ②**检察官**(攻击,不裁决) | 单独 kill;评分 | **≤2** |
| **Sol-H**(gpt-5.6-sol) | ①路线级形式化选择 ②形式审(六类硬杀) | 文献广搜、品味仲裁 | ≤2(+1 条件 max 复核) |
| Grok | 不出现(工程主审属实验侧 R2) | — | 0 |

规则:**杀候选只有两条路——证据(EXACT collision / 路线证据)或形式(Sol 硬杀)。K3 的 fatal_if_true
必须转成 GLM 检索,EXACT 才杀;意见不杀。**

---

## 2. 每席位合同(输入注入 / 输出 schema / RS 提示词原文)

### S1 Opus-M · deepest reframe(无工具)

- **注入**:FROZEN + local_digest(substrate 一行式/语料 title+mechanism 清单/上轮负锚/历史 claim 一行式,~2k cap)+ 15 父卡 digest(Definition + Operational signature)。
- **输出**(≤2 条):`{pattern, trigger(四段链), reframe(一句话世界观), bottleneck_hypothesis, smallest_artifact, queries[2]}`。
- **RS 提示词(原文,触发判据)**:
  > 四段链说不清楚就不是 match:**failure → pattern operation → method artifact → keep-rule metric**。
  > 例:当前真正难的是 X → 把 X 重写成 Y 这个成熟对象 → 用 Z machinery → 产出 runnable artifact A → A 直接影响 primary metric。
- 偏置提示(Opus 的已知毛病防护):"不要把小问题扩大成 architecture;reframe 必须落在 local_digest 可执行的基质上。"

### S2 K3-H · adversarial reframe(无工具)

- 同 S1 注入。输出同 schema。
- **RS 提示词(原文,假设审计的形态)**:
  > 当前结果依赖假设 A → FROZEN 的 Measured anomaly 恰好表明 A 在 regime R 失效 → relax/violate A 后重新构造 method → 它影响 keep rule。
- 角色约束:"你是检察官不是法官——你提出致命可能性(fatal_if_true),文献和形式审去裁决。"

### S3 GLM-L ×3 · 基础证据波(t=0,与 S1/S2 并行,工具)

- baseline 搜索 / closest prior / contrary evidence 三席。本地语料优先,再 search_papers/snowball。
- **RS 提示词(角度纪律)**:escape-mechanism(解法词汇而非问题词汇)+ frozen baseline 必搜。

### S4 Sol-H · 形式化路线选择(无工具,吃 reframe+基础证据 digest)

- **输出**:每条 live reframe 一份 `{formal_object, naive_solution, transformation_changes, kill_observation, runnable_route}`。
- **RS 提示词(naive 合同前移,原文意)**:
  > 先问"最 naive 的 runnable version 是什么"——若 naive 即可解,这条路线当场降级。

### S5 GLM-H · 路线规划器(无工具)

- 输入:routes(live)+ 池增量摘要。输出:下一波查询,每条强制 `{query, route_id, if_yes, if_no}`。
- **停止规则(JS)**:live≤2 ∨ 查询预算尽 ∨ 上一波零路线状态变化(= 边际增益早停的路线版)。
- **护栏**:route 转 killed/weakened 必须带 evidence_ids 或 Sol 形式杀,JS 拒绝无证据的状态迁移。

### S6 GLM-L ×n · 路线查询波(工具,并行)

- 执行 S5 的查询,回卡(卡 schema 带 residue 字段)。

### S7 GLM-H · bottleneck digest(无工具)

- 输入:幸存路线+证据+初始 reframe。输出:`{bottleneck_statement(一句), method_target, surviving_patterns[0-3], negative_knowledge_slice}`。
- **RS 提示词(原文,保留 prompt 删机器)**:
  > bottleneck = **failure,不是缺少某个 cure**:陈述什么坏了、在什么条件下、为什么现有机制产不出所需量。Litmus:若某个具名机制可"按定义关闭"它,它是 solution-shaped——重写。≥2 paper_id 锚;不是类别标签。
- negative_knowledge_slice:顺手抽幸存父卡的 Failure modes + Oral-vs-Reject gap 各 3 行(给 S10 的 K3)。

### S8 GLM-H · 31 匹配(一次调用,无工具)

- 离线压缩的 31 卡三行索引(tactical signature / when-to-pick / failure mode)仅幸存父卡的子集注入。
- 输出:每父卡 ≤1 子卡或 none("没有合适的子就停在父卡——31 是提分辨率的,不是必填 ontology")。
- **companion-combos 真条件**:仅当主模式 deliverable 不是 runnable method 而 FROZEN 要 method 时读。

### S9 GLM-L ×10 · IdeaSketch(无工具,短)

```
{statement_stub, mechanism, pattern, subpattern, naive_baseline,
 why_not_naive, target_row, signature_terms[3], alias_terms[2-3]}
```
- 生成偏置(**刷分型**):"不要宏大 research program;找满足 keep rule 的**最小 runnable mechanism**:一个算子替换/一个条件变量/一个分解/一个估计器/一个表示变更/一个信号。"
- **alias 提示词(原文)**:alias = 其他社区会怎么命名同一机制(参数化知识,不用本域词汇)。

### S10 GLM-H · 组合修剪(无工具,只做机械)

- 三则:dedup(机制重复)/ 无 keep-row 挂链 / 同模式超量保留多样。**禁品味判断**。→ top-4。

### S11 GLM-H ×4 ∥ GLM-L ×4 · Claim 展开 ∥ 碰撞(并行)

- **Claim 展开**:注入 sketch + digest + (若定了子卡)完整 C## 卡 + 31 卡的 Step-by-Step。产出完整 Claim(见 §3 契约)。
- **碰撞**:每 sketch 的 signature_terms(近窗)+ alias_terms(多年窗)+ github。输出 `NONE/ADJACENT/EXACT + 证据`。
- **碰撞提示词(RS 原则)**:alias 命中不因年代折价——改名祖先同样致命。

### S12 K3-H ∥ Sol-H · 攻击 ∥ 形式审(无工具,并行)

- **K3 检察官**(注入候选+S7 负知识切片+anti-patterns 三组比率):逐候选输出 `{CLEAR | CHALLENGE(+理由) | SEARCH_REQUIRED(+query)}`,并逐条对照负知识:
  > 这几张卡的 Reject 失败模式哪几条适用于本候选?(如"增益与共同引入组件混杂""真瓶颈没动留下静默天花板""保留性是证明还是断言")
  > 组件组合是否落入高拒率组合(n_O/n_R 为先验)?
  > 候选真执行了卡的战术动作,还是只占名字?
- **Sol 形式审**(注入全部候选):逐候选 `PASS | FORMAL_RISK | HARD_KILL`。六类硬杀:
  `equivalent_to_naive / 形式矛盾 / 算法产不出声称的 estimand / 证伪 tautological / 负控制不动下游指标 / 算力不可能`。
  仅 top 候选存在 load-bearing 形式歧义时升 max 复核一次。

### S13 JS · 确定性合成 + 选择

```
Sol HARD_KILL            → kill(形式杀,无需投票)
Collision EXACT          → kill(证据杀)
K3 CHALLENGE 且无外部证据 → survives_with_flag
K3 SEARCH_REQUIRED       → GLM 检索一轮 → EXACT 才杀,否则 flag 落地
其余                      → survivor
幸存者>1:机械比较(方法尺寸↓ / clean_cost 余量↑ / untested premises 数↓ / Sol 档位)
仍平局 → Opus-M pairwise pick(第 2 次 Opus 调用)
```
- **无跨模型 0-4 分**(无校准意义);无 leaderboard。

---

## 3. Claim 契约(出生即可被实验侧消费)

```ts
Claim {
  statement        // 要解决的问题(一句话,问题级,不提解)
  strategy         // 刷分策略/模块设计(输入什么、动哪里、怎么算,可计算级)
  target_metric    // 哪个 benchmark 的哪个数,方向
  margin_rule      // 击败谁、多大幅度、怎么算显著(CI 规则)
  contract_rows[]  // primary / control / clean_cost(metric 逐字+阈值+方向)
  advantages[]     // 每条标 evidence_id 或 bet
  premises[]       // 含 observation-model 前提;bet 标 untested
  naive_baseline   // {version, branch: false_premise|incremental|minimalism}
  steps[]          // 可跑级步骤
  falsification_prediction  // 最小实验+主指标+承重变量+非tautology负控制
  signature_terms / alias_terms
  compute_budget
}
```

**RS 提示词原文(证伪最小四件套,保留)**:
> 负控制的预测效应必须是**下游结果指标回到基线**——"干预 X → X 变 0"是 tautological 且无效。
> naive ≈ candidate → 直接杀,不写论文故事。

---

## 4. RS 资产 → 工位映射(全部在岗)

| RS 资产 | 工位 |
|---|---|
| 15 父卡 Definition/Operational signature | S1/S2 reframe 词汇表 |
| 四段链触发测试 | S1/S2 判据 |
| bottleneck failure-not-cure 合同 | S7 digest prompt |
| 31 子卡(压缩三行索引;全卡 lazy) | S8 匹配 / S11 展开 |
| companion-combos(真条件) | S8 |
| **负知识**:父卡 Failure modes + Oral-vs-Reject gap + anti-patterns 比率 | S7 抽切片 → S12 K3 |
| 证伪合同 + naive 三分支 + premises/estimand | S4(路线级前移)+ S11(候选级) |
| residue 必须来自方法节 | S6 读卡合同 |
| alias 多年窗防改名祖先 | S11 碰撞 |
| 已丢弃:组合引擎(CHAIN/removal test/alternates/composition_note)、L 谱系全树、B/S/T/A/I/F 相位机器、expand/derive、三席条件修订 | — |

## 5. 基础设施不变量

无工具注入(全部昂贵席+GLM-H 规划/修剪;工具只在 GLM 检索席);席位缺席=infra error 非裁决;
查询账本(每查询带 route_id,可回放);local_digest 每轮一次构建缓存;策略先验入口(输入带刷分策略
→ 作为第 4 条 route 直接入场,不跳过验证)。


---

## 6. 实现状态(2026-09-05)

`research.workflow.js` v2 已写(611 行,v1 门链版归档 `.research/archive/research-v1-gatechain.workflow.js`);
语法/UTF-8/NUL 检查通过;mock 冒烟(`.research/tests/mock_runtime_research2.mjs`)19 席全绿:
Reframe(opus+k3 ∥ foundation)→ Routes(sol 形式化杀 R2 + planner 波 1 + route query)→ Digest →
Factory(sketch×4 → prune 3 → claim×3 ∥ coll×3)→ Verdict(prosecute ∥ formal → JS 合成 → pick)。
待真模型测试(取代 v1 的测试①)。