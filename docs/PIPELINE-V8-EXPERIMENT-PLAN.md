# V8 实验 TS 方案（草稿）— 一个 REVIEW 原语 × 一条实验梯

草稿 2026-09-05。配 docs/PIPELINE-V8-PLAN.md（research 侧）。本文只定骨架与去向；每级实验的具体
skill、判据文本、决策表后续逐条填入。

必读源（判据从这里抄，不自己发明）：
- CodeReview 形状：`paperjury/ClaudeNative/CodeReview.md`（Scope → Find 屏障 → 按位置分组 → Verify 阶梯 → Sweep → Synthesize）
- ARFT `kbs/paper/2608.14905v2.txt`：45 条失败模式（附录 A）、judge 证据包（Table 8）、Iron Rules 九条（C.4）、评分信号素养（Table 9）
- ASI-Bench `kbs/paper/2608.17271v1.txt`：B1→B2→B3 断崖（50.91→29.10→26.62）、B2 最贵（+59% token）、任务验证四件（sandbox 端到端、参考可复现、评分一致、泄漏与捷径）
- ccf：`ccf-experiment-designer/references/evidence-design.md`、`result-templates.md`、`ccf-humanization/references/experiment-discipline.md`、`ccf-integrity-auditor`
- ARIS `~/oss/aris/skills`：`shared-references/experiment-integrity.md`（四禁 + eval 类型声明）、`experiment-audit`（六检 A-F）、`result-to-claim`（确定性预检 + yes/partial/no 路由 + fail closed）、`reviewer-routing.md`（Type-A/Type-B）

---

## 0. 定位

research 产出一个 Claim（claim 句 + contract rows + 2-3 个机制候选）。实验 TS 的任务是：用最少的 GPU
把每个 contract row 关掉，或者证明关不掉。它不是"实现一个 spec 再跑一次"，而是一条**实验梯**：
探针 → 最小可行实验 → 能否支撑的判断 → 全程主实验 → 消融/鲁棒系列 → 复现。每一级只许可
它能许可的 claim 强度，每一级之间有一次 REVIEW。

两个原则贯穿：

1. **一个原语。** research 侧是 GATE（判断失败 → 定向检索），实验侧是 REVIEW（找 → 分组 → 验 → 扫漏 → 门 → 有界修复 → 增量重验）。形状抄 CodeReview，判据抄 ccf/ARIS/ARFT。
2. **执行者不判自己。** GLM 实现、GLM 做 Type-A（完整性、对照、smoke 通不通）；Type-B（诚实性裁决）必须外族：代码 = Grok CLI，数字 = 脚本重算（sol 兜底），claim = Opus。外族缺席 = `REVIEW_UNAVAILABLE`，fail closed，不是 PASS。

---

## 1. 实验梯（每级一行，后续每级一个 skill）

| 级 | 名 | 目的 | 典型形态（本 campaign） | 成本上限 | 能许可什么 | 出口 |
|---|---|---|---|---|---|---|
| D0 | design 设计 | **反向设计**:先画终稿论文三表再倒推梯;定义"全面"是什么样 | claim-evidence 矩阵→表格骨架→梯级映射→arm 矩阵→预算 | 0 GPU | 许可整个实验计划(过 R1 后逐级生效) | 过 R1 → T0;不过 → 有界修订(设计是 GATE 形:起草→判据→修订) |
| K | kill 杀测设计 | 为每个机制候选出**能失败的最便宜测试**序列(kill plan);定义下半段跑什么 | sol/K3/GLM 三席出测试 → Opus 按"单位 GPU-h 杀伤概率"排序 → 脚本硬底(阈值绑得住/eval-only 优先/oracle 天花板第一测/canary) | 0 GPU | 许可 T0/T2 的执行顺序;不许可任何 claim | 过硬底 → T0 按 plan 首测;不过 → 三席重出一次;仍不过 → 候选 invalid(设计不出可失败测试 = A.2 不可证伪) |
| T0 | probe 探针 | 机制是否存在、量级多大；只读，不训练 | 冻结 ckpt 上的 eval-only 干预（掩码、置零、oracle 路由）；dev half | 分钟级，无训练 | 只许可 motivation 句和 contract 行的**方向**；不进主表 | 有信号 → T2；无信号 → 该机制候选 invalid，不进 T2 |
| T1 | smoke / canary | 代码路径通、评分一致、参考可复现 | SMOKE=1 ≤1% 数据到 eval；冻结 host 复现 canary（49.11 ± 0.10） | 分钟级 | 什么都不许可（ccf：smoke 不是证据） | 过 → 起跑；不过 → 分 infra/算法（ARFT C.5） |
| T2 | MVE 最小可行 | 候选 vs 对照的**存亡**：有没有效应的迹象 | 短课程、单 seed、dev half、kill cap ≤4 GPU-h；候选与对照同预算 | FROZEN kill_cap | **只能杀，不能选**（memory: 40-ep 筛选把两 arm 顺序判反了；MVE 不做超参选择） | 效应方向对且 ≥ 噪声底 → T3；反向或平 → 候选 invalid（first-run-failure 原则：不加投入重试同一方向） |
| T3 | support 判断 | MVE 结果是否**足以支撑**花全程预算 | 脚本重算 + Opus 一句 verdict；不是 E，是放行 | 0 GPU | 只许可"进入 T4"的决定 | supports_full_run / underdetermined（可再一次 T2 换 seed）/ no |
| RR | reverse review 反向审 | 假装论文已写完,让裁判打;每条扣分变一行 contract row;定义上半段跑什么 | sol/K3/GLM 三席隔离,paper round 的 Referee prompt + 全 TBD 三表骨架 → 脚本路由 needs_* → rows(带 prevents_deduction / fills_cell)→ FIXED_RULE 裁剪,≤6 行,超出进 deferred | 0 GPU | 许可 T4/T5 的行集合与优先序 | 行集合非空且 ≤6 → T4;scope_overclaim 项直接改 claim 句 |
| T4 | main 全程主实验 | contract primary + control + clean_cost 行 | 全课程、全 arm 一个 unit、test half 读一次、配对 bootstrap CI95 | FROZEN 单候选上限 | 产生 R/E；关 primary/control/clean_cost 行 | E.verdict 五值 |
| T5 | series 消融/鲁棒系列 | baselines / ablation 行；"刷分"但每张表回答一个 reviewer 问题 | 每 arm 一行：去模块、换通用件、逐 rung、开销表 | 按行计 | 关 baselines/ablation 行；补 C.strength 到 strong | 行全关 → paper draft |
| T6 | repro 复现 | seed 方差、配置冻结、可审计包 | ≥3 seed（若预算）、pip freeze、配置 hash、数据 hash | 按 FROZEN | 许可 reproducibility 句 | 完 |

梯的规则：

- **不跳级**，但可以**降级回退**：T4 结果 underdetermined → 回 T2 换机制候选，不是重跑 T4。
- **每级的 claim 天花板**写死在 ARIS eval-type 表上：T0/T2 是 `pilot (N=…)`，只能写 "preliminary"；"robust / extensive / across settings" 只有 T5 完成后才允许出现（ARIS scope 检查）。
- **T2 不选超参**。选择在 T4 前由 spec 写死（dev half 上的规则，不看 test）。
- 每级产一个 R（不可变，带 tier 字段）；只有 T4/T5 的 R 生成 E 并关 contract 行。

### 1.5 梯分上下两段：下半段由 K 门定，上半段由 RR 定(2026-09-05 讨论定稿)

裁判问的是"证据够不够",这个问题在 GPU 花完之后才有答案;真正的杠杆在前面:一个 idea 若能被一个便宜测试杀死,
就不该活到 T4;活到 T4 的 idea,裁判的 "why not X" 已经是它 kill test 里的对照 X。所以梯分两段,由两个 0-GPU
节点分别定义,两者共用同一张对照表(替代解释 = kill test 的 control = 裁判将来的 needs_baseline)。

| 段 | 级 | 谁定 | 依据 | 回答的问题 |
|---|---|---|---|---|
| 下半段 发现 | T0 → T2 → T3 | **K 门** kill plan | 机制候选 + Claim.kill_conditions + FROZEN kill cap | 能不能便宜地证明自己错了 |
| 上半段 证据 | T4 → T5 → T6 | **RR** contract rows | ccf 七问 + 最小说服包 + 执行优先表 | 证据够不够、裁判还会问什么 |

T3 是分界:放行句成立,RR 的行才开始花 GPU。D0 的三张终稿表由 RR 的行填槽;K 门的第一测就是 D0 要求的
"判别 arm 已排进 T0/T2"的具体形态。

**K 门(kill design)——生成节点角色分工 + Opus 排序**

| 席 | 镜头 | 产出 |
|---|---|---|
| sol | 统计与形式:哪个读数有 power、MDE 多大、阈值绑不绑、oracle 上界怎么算 | 带数字的测试:metric、阈值、n、若 idea 错读数落在哪 |
| K3 | 对抗:什么替代解释也能产生同样效应;**输入 ccf harsh reviewer lens + Claim.reviewer_attack_surface** | 每测的 control arm 与 prediction_if_alternative |
| GLM | 工程:substrate 上 eval-only 几分钟能做什么、哪些 hook 已存在 | 每测的可执行性、成本、脚本入口、canary |
| Opus 聚合 | **排序不是平均**:按单位 GPU-h 的杀伤概率排,把 K3 的对照补进 sol 的测试 | 有序 kill_plan(≤4 测,其余 deferred) |

kill_plan 每测字段:`{tier, question, intervention, control, metric, threshold, max_effect_available,
prediction_if_true, prediction_if_false, cost_gpu_h, eval_only, canary, decisive}`。

脚本硬底(任一不过 → 三席重出一次,仍不过 → 候选 invalid):
1. **能失败**:`threshold ≤ max_effect_available`(memory: prereg threshold must bind),且 prediction_if_false 非空;
2. **首测 ≤ kill cap**,且至少一测 `eval_only=true`;
3. **oracle 天花板第一测**:先测机制杠杆的上界(anomalies 范例:oracle 逐帧路由只救 0.59/2.13/10.10,一次 eval 杀掉整族逐帧方法;逐位置的对应物是 oracle 逐位置 mask 的天花板);
4. **只用 dev half**;
5. **探针自证**:每测带 canary(先复现一个已知数再读内部,memory: probes must prove themselves),否则假杀。

执行:T0/T2 按 plan 顺序跑,首杀即停(候选 invalid,plan 其余测试进 M 的记录供 research add_mechanisms 读);
全活 → T3。K3 的 control 直接成为 D0 arm 矩阵的判别 arm。

**RR(reverse review)——裁判反向出行**

1. 时点:T3 放行之后、T4 spec 之前;输入 = idea card + D0 的全 TBD 三表骨架 + FROZEN + anomalies + dossier closest_prior
   (没有这三样裁判只会要 "more baselines, more seeds")。
2. 席位:sol/K3/GLM 三席隔离,prompt 与 paper round 的 Referee 同一份(八维 + claim table + STANCE_RULE);
   request_type 只允许 needs_evidence / needs_baseline / needs_ablation / scope_overclaim。
3. 脚本路由:needs_* → contract row,字段照 ccf claim-evidence matrix(claim、reviewer question 七选一、evidence needed、
   dataset、baselines、metric、result placeholder、status)+ `prevents_deduction`(防哪条扣分)+ `fills_cell`(填哪表哪格);
   scope_overclaim 不生成行,直接改 claim 句与 C.strength 上限。
4. 裁剪:FIXED_RULE 反用——跑完不会改任何一维分数的行不跑;上限 6 行;默认底座 = ccf 最小说服包四件
   (主对比、机制消融、鲁棒/泛化、可复现);超出进 `deferred[]` 给 paper round。
5. 排序:ccf Execution Priority Table(P0-P2、claim defended、cost、dependency、stop condition)即 T5 顺序;
   答不出七问之一的表不上——这是"刷分"的边界。
6. 回收:paper round 裁判再提 needs_* 时先查行是否已关;关了带 row id 判 invalid,没关才开 Q。RR 与 paper round
   共用 Referee prompt 与路由代码,只是一个跑在 GPU 前、一个跑在 GPU 后。

两个风险:裁判是通用八维、攻击面是领域的(靠输入 anomalies/closest_prior 缓解);行会膨胀(三裁判各 12 条 → 36 行,
靠 ≤6 + FIXED_RULE 硬裁)。

插件已填(2026-09-05,来源:ARIS kill-argument/experiment-plan/ablation-planner/training-check/result-to-claim + ccf experiment-designer/paper-reviewer):

**K 门判据(17 条,出处标注)**:
A 起草:①每条 kill_condition 按最强审稿人拒稿备忘录写(~200 词≤250,单论点不列清单,引 file:line/公式号,不对冲不认缓解)[kill-argument Step2];②六轴测候选但**绑死最狠一轴**(定理有效性/假设-声明错配/缺证明义务/极限序歧义/声明-证据缺口/scope 超称)[同];③**anti-claim 是一等击杀目标**("增益只来自参数量/搜索空间变大/新组件是装饰")[experiment-plan Phase1];④每条件成对带"成功判据+失败解读",缺一不可运行[experiment-plan Phase3];⑤预期方向预先承诺(name/what_it_tests/expected_if_component_matters/priority 1-5),禁"试试看"[ablation-planner];⑥sol 席:阈值绑 MDE,"单数据集单正结果不支撑一般声明"[result-to-claim];⑦GLM 席:每条件过 STOP/CONTINUE/WAIT 三分——到不了 STOP 的条件是设计错误,改道更便宜更早的探针[training-check]。
B 裁决(计算式,永不自评):⑧击杀攻击分解 3-7 原子点,各标 answered/partially/still_unresolved("fixed 暗示修补史,偏乐观")[kill-argument];⑨精确映射:FAIL=≥1 critical 仍悬;WARN=major/minor 悬或 critical/major 半答;PASS=全 resolved 且 partial 仅 minor;**PASS 需 still_unresolved==0**[kill-argument Step4 裁决表];⑩verdict 由计数映射产出,防御席不得直接给顶层裁决(防自评)[同];⑪headline_unstable 守卫:Claim 的 rows 自 D0 后动过 → K 重跑再买 GPU[同]。
C 排序与帽:⑫suggested_order="最大化早期信息";estimated_compute 逐项[ablation-planner];⑬组件消融>超参扫描;config-only>改代码 → **eval-only/冻结 ckpt 探针同信息量下排最前**[同];⑭kill cap 超支=重排谈判,禁静默砍[同];⑮禁 no-op 消融与远程防御性用例[同+experiment-designer]。
D "最狠审稿人驳不倒"形态:⑯平衡严重度清单会埋掉致命攻击——每条条件写成 AC 会直接行动的一句话拒稿(阈值+工件引用);审稿人能称"又一个 major/需要更多实验"而说不出"哪个实验/基线/指标/数据/分析会改分"的条件=无效[kill-argument Why This Exists + paper-reviewer Review Tone];⑰severity 保持诚实:驳不倒不许降级;作者有意选择≠自动 answered[kill-argument Step3]。

**RR 裁剪规则(候选行→≤6 FIXED_RULE)**:
留行双路由(同时满足):K1 prevents_deduction——缺该行会喂致命分诊("主声明无证据/最强基线缺失")或一条 live 扣分(claim-evidence 审计 Strength=weak/absent + Reviewer deduction);K2 fills_cell——行映射到 (claim×block×cell) 槽,"不改 reviewer 信念的实验砍掉"[paper-reviewer + experiment-plan]。
砍/降六由:D1 unnecessary("看似有用不会增见"显式跳过表);D2 no-op(与已跑基线同构);D3 防御性填充(禁枚举远程防御用例);D4 **改写声明可退役**(suggested_claim_revision 收窄后该行不再承重——改声明不买 GPU)[result-to-claim];D5 已有负结果在案不重跑(去组件无效应=重要发现);D6 占位绑定(该格只能由简化跑填→禁,TBD 保持 TBD 或砍行)[experiment-designer Workflow6]。
排序四则:O1 priority 1-5;O2 组件>超参、config-only>改码;O3 **最大早期信息序**(能杀/能锁 headline 的行第一,不是最便宜的);O4 每行带 stop/go 门+成本,smoke 行只留变更关键路径去重后且不进发表证据[ablation-planner + experiment-plan]。
合成纪律:S1 **最终立场必须与最强未决关切一致,绝不用平均抹掉致命伤**——最强关切要的行不许被席位投票投掉;S2 每行理由必须具名"哪个实验/基线/指标/数据/分析会改分",裸"需要更多实验"无效;S3 每行带 score-change 表(改什么→哪些维度→+几分);"需新结果才能改"的行=Appendix 级不进 FIXED_RULE;S4 ≤6 帽继承紧凑教义(MAX_CORE_BLOCKS=5/MAX_BASELINE_FAMILIES=3,"宁少强基线不多弱基线")。
映射注意:kill-argument 裁决表键在攻击裁定(answered/partially/unresolved),K 复用时需一步解释性映射(阈值击穿=still_unresolved@critical→FAIL→候选死)——此步不在源文,是我们自己的桥,实现时写明。

## 2. REVIEW 原语与四个用点

```
REVIEW(target, angles[], floor[], ladder):
  0 hard-floor   脚本先判可机械化判据 → 不过直接 blocked，不进模型
  1 find         每角度一个 GLM finder + ONE 外族 finder（Grok）；候选 = {file, line, summary, failure_scenario, severity}
  2 group        按 (file,line) 分组（合并键）
  3 verify       每组一个 GLM verifier；CONFIRMED / PLAUSIBLE / REFUTED，默认 PLAUSIBLE（RECALL 规则）；缺席 → 该组丢
  4 sweep        一个 fresh finder 只找清单之外（ARFT F.2）
  5 gate         脚本：CONFIRMED critical/high → blocked
  6 remediate    有界修复（GLM）→ 只重验受影响组
```

**原生对照校准（CodeReview.md = CC v2.1.221 bughunter 逐字节提取版，已全文读过）**，实现时照抄的细节:
- 每角度 finder 带 perAngle cap（6/8），候选必须带 {file, line, summary, failure_scenario}；
  **failure_scenario 必须是用户可见后果，不是中间状态**；"半信候选也必须放行，下游 verifier 裁决"（召回规则）。
- 分组是**合并键不是去重**：每个候选保留自己的 verdict，语义去重留给 Synthesize。
- Verify 阶梯原文：CONFIRMED=能说出触发输入/状态+错误输出并引用行；PLAUSIBLE=机制真实但触发不确定；
  REFUTED=必须能从代码构造（引反证行）。**缺席/未裁决的候选丢弃，绝不伪造 PLAUSIBLE**（组装器不变量）。
- Synthesize 排序：correctness > cleanup，CONFIRMED > PLAUSIBLE；cap 有余量则回填；合并成员 CONFIRMED 可升级主条目。
- 用户 target 随每个 finder/verifier 传递，framed as scope-only data（防注入执行）。
- 文件路径规范化：suffix-match 对 scope.files，最长匹配胜（防绝对/相对路径混用破坏分组键）。
- 外族 finder 是第 N+1 个角度（open-code-review 阿里版补充）：**锚定或丢弃**——finding 必须带 diff 中
  逐字节匹配的 existing_code 片段，匹配失败机械丢弃；盲删过滤器只见 diff、只删"仅凭 diff 即可证实错误"者
  （不对称删除，与 PLAUSIBLE-by-default 同构）。
- Sweep 焦点清单照抄其原生形态：被移动/提取代码丢失守卫、二线坑、setup/teardown 不对称、配置翻转。

| 用点 | target | 角度集来源 | 硬底（脚本） | Type-B | 在梯上的位置 |
|---|---|---|---|---|---|
| R1 spec 审 | sol 写的 B1 TestSpec | ccf evidence-design（arms↔rows、基线矩阵 can_run、消融各测一机制、最小说服包）；experiment-discipline（confirmed 全版基线，禁 toy/proxy）；ARFT A.4/A.5/A.6 | arms 数 = open rows；eval_entry ∉ steps；run_cmd 可解析；预算 ≤ FROZEN；tier 合法 | Grok（待验 CLI 能否读 JSON） | 每级起跑前 |
| R2 diff 审 | worktree diff | CodeReview 角 A-D + 领域镜头 spec-drift（C.3）、leakage（C.1/C.2 + Iron Rule 6 答案污染）、integrity（ARIS 四禁） | launch_checks：eval_entry 无 hunk、steps 全有 hunk、测试集 token；smoke 产出 seed_0.json | Grok | T1 之后、起跑之前 |
| R3 artifacts 审 | evidence/index.json 原件 | ARIS 六检 A-F；ARFT C.4 数值失稳、D.1 bug 当发现、Iron Rule 2 量级/单位；Table 9 exit≠质量 | sha8 一致；每 arm 有 seed 文件；metric key 存在；canary 在 tol 内；test half 读取次数 = 1 | Grok（读 eval 代码 + 结果） | 每级跑完 |
| R4 claim 审 | Judge 写的 E / T3 的放行句 | ARFT D.3/D.4/D.5/D.7/E.2/F.4；ARIS scope 用词对 N；ccf integrity-auditor 四态 | ARIS 预检：statement 每个数在重算表；CI 不含零才 supports；row spec 字面满足；tier 天花板未越 | Grok 复核 Opus | T3、T4、T5 之后 |

R1 是 ASI-Bench 直接给的：B2（只给方法名）比 B1 贵 59% 且分数减半，所以给 GLM 的必须是 B1 级 spec，且 spec 先审再实现。R3 里不设 Package/Extract agent：ARIS 的规矩是"执行者只收集路径不摘要"，launch_wrap 退出时写 index 即是。

---

### D0 设计级(2026-09-05 补——原方案最大 gap:判设计的判据全有,生成设计的方法没有)

核心:**反向设计**(ccf storyline 证据阶梯倒用)——不是"设计实验",是**先画出终稿论文的三张表,再倒推梯子**。
席位:sol 起草(结构/矩阵/预算)1 次 + Opus 反向完整性仲裁 1 次(设计=品味);R1 照常审(Grok+脚本硬底)。
流程:claim-evidence 矩阵(每 row→具名 reviewer 问题→证据类型→终稿表格槽,result-templates 骨架全 TBD
不写死方法名)→ 终稿三表(主/消融/鲁棒)→ 梯级映射(哪级关哪行)→ arm 矩阵(baseline can_run 三值、
reproduced/reported 分开、每主声明 anti-claim+判别性 arm)→ unnecessary_ablations 跳过表 →
eval_type=real_gt 声明 → 预算分配(kill cap/tier 成本/总包络)。
设计判据(并入 R1):①反向完整——三表骨架装下全部 open rows,每个 TBD 槽有梯级与 arm 负责,
答不出七问之一的实验不进设计;②每主声明必有 anti-claim 与判别 arm(且判别 arm 已排进 T0/T2);
③缺基线不许静默替换;④预算 ≤ FROZEN;⑤硬底(脚本):矩阵行数=open rows、表格槽↔row 双射、
eval_type 声明存在。paper workflow 将来直接吃 D0 的表格骨架与 R4 矩阵——表先于实验存在。
形状澄清:D0=GATE 形(起草→判据→修订),R1-R3=REVIEW 形(找→验→门),R4/T3=裁决形(证据→yes/partial/no);
"claim 是否足够支撑一篇论文" = D0 反向定义"全面" + R4 逐 row 判支撑 + C.strength 取最弱 row。

### 快杀边界与消融产出时点(2026-09-05 写码前钉死)

**快杀分层**:DR 自带三层纸面快杀(T 门 equivalent_to_naive 脚本击杀 / A 门硬底 exact-mechanism+reject lesson+反模式 / P2 复判翻案),杀的是"作为 idea 不成立"——0 GPU;K/T2 杀"跑了不成立"(机制逻辑对但冻结 host 上信号不在/方向反)——只有跑才知道,且需要平台状态。一句话:**DR 杀"不值得跑的",K/T2 杀"跑了不成立的";falsification_prediction 是接口——research 定义"什么会证伪我",K 给证伪器定价排序。K 不是 DR 的重复,是 DR 证伪承诺的执行定价器。**

**全量 ablation 三段产出**:D0=设计态(三表骨架全 TBD+arm 矩阵+判别 arm+unnecessary_ablations,只有形状);
K/T0/T2=判别 arm 提前跑(唯一提前执行的消融,只许可方向,不进主表);**RR=定稿时点**(拿 T4 后矩阵 live
状态——已关行/仍 TBD 格/存活 anti-claim/未消除扣分——裁出 ≤6 FIXED_RULE+执行序);T5=逐 arm 执行回填骨架
(负结果同格记录);T6=≥3 seed。为什么定稿在 RR:消融行集取决于主效应长什么样,哪些替代解释活着决定了
哪些组件消融是 must-run(ccf ablation-planner 触发条件原文="主结果过 result-to-claim 之后";ARIS bridge
"auto-ablation only after M2 positive")。"全量"=最小说服包的完整(≤6 行+显式跳过表+≤3 基线族紧凑教义),
由 D0 反向定义、RR 裁剪保证,不是"什么都跑"。

### 边界:设计种子在 DeepResearch,完成在实验侧;R2 不产生设计(2026-09-05 定稿)

不是二选一,是接力。research 侧已实现(RS 合同字段)→ 实验侧入口的映射:
falsification_prediction(最小实验+指标方向+承重变量+负控制)→ **K 门第一测的种子**(承重变量=T0 探针对象,
负控制=T4 control arm);naive_baseline{version,branch,standard_tool_structure}→ 对照 arm 种子;
premises(observation_model)+estimand → R1 的 arms↔rows 与 metric 对齐输入;steps+I 门 impl(输入表示/
具名估计器/默认超参)→ **B1 spec 函数级步骤起点**(实验侧展开到平台,不重新发明);compute_budget+F 门
feasibility → 预算包络起点(R1 硬底对 FROZEN 校验);Claim 的 contract rows → D0 矩阵的行(接口本体)。
教义依据:RS Phase 4(expand.txt)scope contract 原文把 experiment matrix/ablation plan/baseline table/
calendar 明确排除在 idea card 外("The user designs experiments with their own dataset/compute context")——
理由:research 时刻没有 FROZEN 平台状态(冻结 host/canary/数据 split/预算),完整设计缺这些无法做。
三段分工:research 许可"idea 成立且值得做"(种子=可证伪结构);D0/K/RR 生产"完整证据计划"(需平台状态);
R2 只审"实现忠于 spec"(spec-drift 镜头),不产生设计。链条:planner(D0/K/RR)→ 写代码(GLM)→
code review(R2)→ 跑 → R3 → R4。

### 横切守卫(所有 REVIEW 环共用,五源合流)

1. **反环双阈值 + 停滞阶梯**:同一 finding 两次战术修补失败→改结构;当前 REVIEW 周期内 3 个高危未决→升级 owner(ccf render-qa);连续 2 轮零新发现→换结构,4 轮→人(ARIS external-cadence)。
2. **禁环条款**:remediate 只许针对 finding 本身;删除带锚跨度/改措辞不是修复,finding 仍 OPEN(ARIS integrity-forensics)。
3. **票据重验**:每次后续 REVIEW 重验前次证据文件存在且 hash 一致;证据被改=对应裁决重开(同上)。
4. **偏置守卫**:跨轮 REVIEW 一律 fresh context,禁"since last round/已修复"措辞;复核记忆 append-only 且调用前记 hash,分数回归时 diff 两轮 trace(ARIS auto-review-loop,3/10→8/10 实证)。
5. **verdict 六值 + provisional/accepted**:PASS/WARN/FAIL/NOT_APPLICABLE/BLOCKED/ERROR;查过没有也落工件(NOT_APPLICABLE≠SKIP);同族裁决封 provisional,E 最高 adequate(ARIS assurance-contract)。
6. **done/accepted 分离**:执行完成可自报 done;accepted 只由跨族/确定性 accept() 写入(ARIS resumable)。
7. **REVIEW_UNAVAILABLE fail-closed**:外族缺席不是 PASS,是 BLOCK(该级降 provisional)。
8. **停机双条件**:score≥6 且 verdict∈{ready,almost};不可解析→fail-closed(ARIS)。
9. **shards 只抽取不裁决**:并行 finder/分片永不排名/宣称最佳/判完成;jury 前机械去重;分片只读(ARIS fan-out)。
10. **数值的承载是文档**(两篇论文的教训:ARFT D.6 结果幻觉/C.1 硬编码、dse-loop 解析漂移):结果数字只进 evidence 记录文档(每个数带 file:line 锚或重算表锚)与原始结果文件;实现代码禁 hardcode 任何实验数值(R2 镜头判死);recompute 脚本只校验不改写,产物是重算表文档;R4 审文档+原件,不审代码字面量。

### REVIEW 的输入输出单位(2026-09-05 讨论定稿)

两层单位,不要混:
- **WORK 单元** = 机制候选 M @ 某级 T 的 arm-set(spec.arms[],臂数=open rows)。R1/R2/R3 审这个:
  输入=该级 spec / worktree diff / evidence 原件,输出=pass/blocked + 带锚 findings——**不是 claim 裁决**。
- **OUTCOME 单元** = Claim 的一条 contract row。T3/R4 审这个:输入=row+重算表+审计,输出=**yes/partial/no**
  (partial→收窄句,是常态出口);Claim 级=claim-evidence 矩阵聚合,C.strength 由最弱 row 决定,不许平均。

禁止"全部实验+全部消融一把 MVE":①死候选的消融是纯浪费(auto-ablation only after M2 positive,
ARIS bridge;AI-S2 stage-4 只对最佳节点);②单 seed 消融=用噪声签因果声明——消融行是 causality claim,
归 T5(与主效应同 footing:配对/同 unit/bootstrap);③多 seed 是许可制度:T2 单 seed(kill-only),
T3 的 underdetermined 允许再跑一次 T2 换 seed,T4 ≥3 独立跑先差后聚合,T6 ≥3 seed。
但**判别性消融提前**:ccf 双链的 discriminating test 那一个 arm 以 T0/T2 身份早跑(单 seed 合法,只许可方向);
消融的**设计**(全 arm 矩阵+行映射+unnecessary_ablations)在 R1 一次定死(B1 粒度),执行按梯分批。
即:消融设计∈R1,判别消融执行∈T0/T2,消融套件执行∈T5。

## 3. ARFT 45 条 → 我们的哪一级哪一检

只列实验相关的（A/B 属 research 侧，E 属 paper 侧，这里不重复）。百分比是 ARFT 800 份分析中的出现率。

| 模式 | 率 | 我们在哪里抓 |
|---|---|---|
| A.4 可行性误判 | — | R1 预算硬底；T2 kill cap |
| A.5 指标错位 68.1% | R1：spec.outcome_metric == contract row 的 metric（字面）；R3：重算的就是这个 metric |
| A.6 假设-实验错配 52.5% | R1 arms↔rows 映射；T3 放行句必须引 row |
| C.1 循环验证 / 捷径 69.0% | R2 leakage 镜头（目标可从输入解析推出？）；R3 ARIS 检 A（GT 来源） |
| C.2 grader-fitting / 泄漏 | R2：选模统计读 test？；R3 硬底：test half 读取次数 = 1；Iron Rule 6 |
| C.3 实现偏离 72.1% | R2 spec-drift 镜头 + launch_checks steps 全有 hunk |
| C.4 数值失稳 / 未固定种子 | R3：量级/单位 sanity；launcher 固定 seed，spec 不许选 |
| C.5 基础设施误诊 | T1 分叉：exit 5 / canary fail 先判 infra；infra 不耗 fix 轮 |
| C.6 局部超参微调 | T2 不选超参；T4 前由 spec 写死 |
| C.7 过早放弃 | build 环允许一次 fix；infra 重起一次 |
| D.1 把 artifact 当发现 52.4% | R3 ARFT 角度；T0 探针只许可方向 |
| D.2 确认偏误 | R4：failed sanity check 必须出现在 statement 或 limitations |
| D.3 统计误用 | R4 预检：CI 不含零才 supports；配对 bootstrap 固定 seed 10k |
| D.4 结论与输出脱节 77.5% | R4：statement 每个数可回溯 R 字段 |
| D.5 基线/消融缺 | T5 是专门一级；contract 行不关 → paper 不能写 strong |
| D.6 结果幻觉 | R3 ARIS 检 C：文件存在、key 存在、数字相符 |
| D.7 反证未处理 60.8% | R4：blockers.json 的 HIGH 项必须被 verdict 回应 |
| F.4 未修正的自知 82.5% | R4 SELF_AWARE：reasoning 点出致命问题而 verdict 不反映 → verdict 无效 |
| F.6 幻觉审稿（实为 0.4%，近乎不存在） | ARFT 全语料结论：**评审错误几乎全是漏报（F.1-F.4），从不是误报**——REFUTED 档保留用于噪声控制但不重仓；真正要防的是橡皮图章，故 Verify 必须外族 + Sweep 必跑 |
| F.4 未修正的自知 82.5%（#1 模式） | R4 SELF_AWARE + ARFT 论文自荐：①交付前**报告 vs run 目录强制比对**（确定性）；②**已知致命自诊断的报告拒收**（"agent 自己写了 uninterpretable，系统拒收直到结果或声明改变"） |
| C.7 过早放弃 16.1% | build 环允许一次 fix；ARFT 案例：4 轮就 end_turn 决策为空 = 交付失败非科学失败，与质量分开记账 |
| X.3 怀疑推理缺失 39.4% | R4 证据表必填"替代解释+为何排除+置信依据"（ARFT App F.2 的生成侧脚手架，判据与生成同构） |
| X.6 对而无因 43.8% | R2 leakage + R3 GT 来源合看：指标达标但路径不干净 → method_invalid，不是 supports |

Iron Rules **九条**进 R3/R4 的 prompt 原文（ARFT App C.4，已逐条核对）：①看最终交付版不看废弃版；
②量级/单位 sanity 优先、选择性重跑（判据：蛋白-DNA 界面 47 Å² 该 >1000 = nm²/Å² 单位错；重跑仅限"可疑+看不出来+便宜复现"）；
③honest null 记为 strength（credit where due）；④法官误判要回撤记录；⑤逐轨迹判不套模板；
⑥答案污染（读过 test/原文的任何统计不能算独立发现，与原文的分歧才算独立性）；⑦**检索充分性也要判**
（没搜该搜的数据然后"没数据"退回合成替代，是伪装成 ideation 缺陷的检索失败）；⑧逐引用核对（grep 每个 DOI/arXiv id
是否真出现在检索日志，没出现过却进了报告=幻觉引用）；⑨**不被 eloquent 自诊断缴械**（"识别了机制"≠"处理了它"，
review 阶段的信用只给独立发现并实际修改的项——F.4 的操作定义）。池适配追加：完美/极端分数必须拆解，
查是否被特权信息（评估器默认值、泄漏初值）撑起。

---

## 4. ASI-Bench 给实验的四条要求

| ASI-Bench 做法 | 我们的对应 | 状态 |
|---|---|---|
| B1 全流程指导最便宜最准 | sol 写 B1 级 spec（步骤到函数、run_cmd、参数）给 GLM；绝不只给方法名 | 已有，加 R1 |
| sandbox 端到端执行验证 | T1 SMOKE=1 到 eval | 已有 |
| 参考结果可复现 | canary：冻结 host 49.11 ± 0.10 | 已有 |
| 评分一致性 | eval_entry 受保护 + 脚本重算同一 metric | 已有 |
| 泄漏与捷径检查 | launch_checks token 扫描 + R2 leakage + R3 GT 来源 | 部分：缺 test-half 读取计数 |
| 五轮评审 + 2000 次修订才留 60 题 | 我们的对应是 R1：spec 不过审不实现 | 新加 |

ASI 数字已逐条核实（2608.17271v1）：断崖 50.91→29.10→26.62 在 **B1→B2（去掉步骤，−21.82）**，B2→B3 只 −2.48
→ **spec 的价值在过程不在方法名**；B2 最贵（6.91M token/题，+59%/+32%）→ 半吊子 spec 比没有更贵；
B4 干扰项几乎免费（+0.36）→ 不必防 distractor。**B1 级的判定标准**（App D ETDRK4 范例）：方程全文+系数值+
离散化逐行（2/3-rule dealiasing）+具名积分器及参数（Kassam–Trefethen 系数公式）+更新递推——sol 写的 spec
必须到这个粒度，R1 的判据"步骤到函数、run_cmd、参数"以此为准。验证四柱：1500+ 沙盒端到端、确定性参考生成
（= canary/recompute 的学理出处）、gates+加权 scorer 且 **≥3 独立跑、先差后聚合、±1 std**、泄漏/捷径审查
覆盖 prompt **和轨迹**（= test-half 读取计数）。附带：harness 效应同一模型换 harness 差 4-7 分
（MiMo 16.17→23.25）——管线本身是能力的一部分。

---

## 4b. ARFT 判据机器（App C）→ R3/R4 的席位纪律

ARFT 的 judge 机器是一套可直接抄的 R3/R4 合同：

| 机器 | 内容 | 去向 |
|---|---|---|
| 证据包（Table 8） | problem_readme↔spec+row；harness.jsonl↔journal+progress；result.json=**仅执行状态，明文"不是质量信号"**；submissions↔test-half 读取记录；evaluator/=**评分器源码逐字副本**（判方法对不对，不只看名字）；verification.md=人写说明；agent_code/=**最终容器文件系统**（≤60 文件/1MB/文件）；密封 GT 按主机路径只读挂载 | evidence/index.json 的字段表；R3 直接读 |
| 每条 finding 的写作标准 | ≥1 可验证锚（数字/日志行号/文件名/代码标识符）；`[stage|root-cause]` 尾标；≥200 字符；禁模板复用语 | R2/R3 finder 的 schema 约束 |
| 确定性 checker 六类 | 总量下限；分节下限；分节广度（C≥10）；条目厚度分布（>28% 短于 200 字符即拒）；密度反 padding（≥85% 带锚、60 字符 shingle 近重复 ≤8%、照抄跨度 ≤20%）；标签合法 | R3/R4 的 hard-floor 脚本（不达标=REVIEW 不完整，不是 PASS） |
| 句句清单 | 终稿每条关键声明标 pass/partial/fail | R4 预检的扩展（逐声明而非逐数字） |
| Credit Due 必填 | honest null/自抓 bug 与失败同格度记录 | R4 输出 schema（E.verdict 的 strength 位） |
| 回撤日志 | 法官自己改判也要记录 | R 的不可变性 + dag 审计 |
| 再生环 | checker 失败报告逐字注入重试 prompt，新尝试必须 ≥前次+5 条且不丢已对项；熔断 | R3 的 remediate 有界修复 |
| 生成侧脚手架（App F.2） | A 阶段强制具名证伪判据+替代框架；B 每源"确立了什么/支撑哪条声明"；D 强制替代解释+为何排除+置信依据；F 第三人称 Peer Review（weakest_point + what_would_change_your_mind）镜像进 decision.json | spec 与 Judge 的 prompt 合同（生成侧先把字段写出来，R4 才有可审的靶） |
| Table 9 理由码 | reward=0 先看 reason：judge_unavailable/no_decision=**非质量信号**；soft[observable]=真分；另查 observable mismatch（算得对但算的不是被评的量） | T1/T3 的 exit-code 分诊；R3 判分规则 |

ARFT 论文自己的三条系统级建议（§8，直接采纳）：①**交付前报告 vs run 目录强制比对**——"不需要任何 agent 缺的能力，
缺的只是把两样都出自同一 agent 的产物比一比的要求"；②**已知致命自诊断的报告拒收**（F.4 反制）；
③R3 无法靠加分数修复（"那只是造一个新靶子"）——需要 agent 控制之外的验证。

## 4c. ~/autoresearch 六系统普查：可偷模式（全部有出处）

| 系统 | 偷什么 | 出处 |
|---|---|---|
| AI-Scientist-v2 | stage-1 零 good 节点=整树杀；**晋级必须击败继承基线**；每主阶段收口=多种子复评；**跑太快=可疑**（exec-time floor） | treesearch/agent_manager.py:410-520 |
| Curie | **对照组先跑**（实验组排队等 control done）；反 mock 清单（硬编码数据/未替换占位/**声明的变量必须真被用到**）；**verifier 重跑一遍并比对**（不是读代码） | curie/scheduler.py:190-249, prompts/llm-verifier.txt, nodes/exec_validator.py |
| open-code-review（阿里） | **锚定或丢弃**（existing_code 逐字节匹配）；**盲删过滤器**（只见 diff，只删 diff 即可证伪者）；plan 带 tool_guidance；diff 外文件禁报 | internal/config/template/prompts/*, model/review.go |
| MLEvolve | **极端指标自动触发泄漏审计**（恰 1.0/0.0）；停滞检测/分支耐心/同分支 top-k 上限 | agents/triggers.py, engine/conditions.py |
| CORAL | **grader 与被评者结构隔离**（grader 在私有 venv 以 root 跑，被评 agent 读不到评分器与答案）——eval_entry 受保护的一般化 | coral/grader/loader.py:34 |
| AgentLaboratory | 反面教材：LLM-reward 无 GT 无盲区=处处最弱，不采用；可取 evict-lowest+种群反思 | mlesolver.py:141-148 |

横切结论：成熟形状两种（进化型 vs 阶梯型），V8=阶梯+REVIEW 门，晋级规则借"必须击败继承基线"；
**finder/verifier 分离 + 机械/对抗式 verifier 最强**（精确串锚、重跑比对、变量使用审计、极端指标审计），
LLM 整体打分最弱；可疑信号三件套（太快/恰好边界值/mock 占位）编进 T1/R3 硬底。


## 4d. CCFA 18 个 skill 深读收获(全部有出处,按可偷价值排序)

| # | 偷什么 | 出处 | V8 去向 |
|---|---|---|---|
| 1 | **claim-evidence 矩阵 = 单一脊柱**:Claim/Where stated/Evidence source/Evidence strength(strong-adequate-weak-absent)/Reviewer risk/Status(supported-needs evidence-overclaim-unclear)/Revision action——writer、reviewer、integrity 三个 skill 共用同一 schema | ccf-paper-writer references/storyline-blueprint.md | V8 的 Claim C 对象直接采此字段;R1 生成 spec 时每行 claim 预登记,R4 回填 status |
| 2 | **确定性 gate 脚本两件,直接移植**:check_prose_quality.py(破折号 3/篇 0/节、17 开场填充 regex、27 精度词表、均匀句长检测、分号密度,--strict 退出码);validate_version_comparison.py(权重和=1、每 delta=current−historical、**分数下降必须有 origin∈{revision_regression,newly_revealed}+负 score_effect+非空证据** 的逐条脚本校验) | ccf-paper-writer/scripts;ccf-paper-reviewer | R4/paper 的 hard-floor;版本对比校验器给 dag 的 revise 轮 |
| 3 | **"绝不用平均抹掉致命伤"** + 致命分诊清单(中心贡献不清/novelty 塌缩/主声明无证据/最强基线缺失/方法无效/不可复现/venue 错) + 每分≤3 必带扣分与修复条件 + **分数改变条件表** | ccf-paper-reviewer universal-review-rubric.md, calibration-and-rank.md | R4 Judge 的合成规则;E.verdict 的裁决纪律 |
| 4 | **reviewer 问题分类法**:每个实验/表/图/面板必须具名回答一个 reviewer 问题;三大顶层问题 effectiveness/causality/generalization-and-limits;**一表一信息,两信息拆表**;caption 三件(what+setting+takeaway) | table-style-guide.md, section-modules.md | T5 的表界(§8.5 的裁决);R1 的行定义 |
| 5 | **基线出处纪律**:reproduced 与 reported 数字分开;比数字要同时引方法论文+数字来源;toy/proxy/reduced 版禁入发表比较 | citation-workflow.md, idea-optimizer experiment-design.md | spec.arms[] 字段;R1 硬底 |
| 6 | **方法声明双链**:每条方法 claim 必带 closest protocol anchor + **discriminating test**(什么结果能把本机制与最近替代分开) | ccf-idea-optimizer experiment-design.md | R1 判据;T0 探针的设计合同 |
| 7 | **证据阶梯顺序**:现象/失败模式→主效应 vs 强基线→机制(消融/证明/诊断)→泛化/鲁棒/尺度→边界/失败案例;每件证据四问(支撑哪条声明/失败会削弱什么) | storyline-blueprint.md | T4→T5 的排序;E 的组表逻辑 |
| 8 | **不发明清单 + 四向出处**:文献/基线/实验/结果/评审共识/显著线/录用率一概不发明;known-from-user/public/inferred/unknown 四分;未填槽标 [UNFILLED] 不造 | ccf-common privacy-and-evidence.md | R3/R4 prompt 原文;卡与 E 的字段纪律 |
| 9 | **反环/升级阈值**:两次战术修补失败→改结构;三个高危未决→升级到 owner(按类型路由) | ccf-visual-composer render-qa.md | 所有 REVIEW remediate 环的通用守卫(加进 §2 原语) |
| 10 | **未检索 novelty 封顶**:closest work 没搜过→novelty ≤3 且推荐封 needs-literature-search(脚本可判:查检索日志状态) | ccf-idea-reviewer | research 侧已有 scoop;experiment 侧 T0 前置同规则 |
| 11 | 12 条 storyline 失败信号(方法先于起源/gap 无根因/insight=组件名/多主线/卖模块验管线/证据清单非信念阶梯/摘要宽实验窄/藏最强对手/结论加新声明/图无问题/声明强于证据) | storyline-blueprint.md | paper 侧;R4 的 claim 审角度 |
| 12 | 修订台账 done 需 artifact("没落盘不算 done");接受为 accepted_limit 的诚实位 | ccf-rebuttal-writer | R 的 patch 完成判据 |
| 13 | artifact 单件制:一交付一正本,覆盖式,禁 v2/final-final | ccf-common artifact-contracts.md | .research 对象纪律(已有) |
| 14 | gate 形状五元组:required input/output artifact/pass condition/blocker/handoff + "What Not To Do Yet"次序(声明未稳不设计实验;证据未对齐不写散文) | ccf-pipeline-orchestrator routing.md | dag 的 next 逻辑表述 |
| 15 | 覆盖声明必有 rescue route(new problem/mechanism/evidence/venue/stop 五路) | ccf-literature-searcher | research 侧 scoop 命中后的路由(已有 retry,补齐五路) |

另有:ccf-experiment-designer 的"最小充分包"原则与缺值显式标记(T 级诚实);humanization 的警告不注入合同(advisory/blocking + "File changes: none");idea-reviewer 的推荐带分档(accept-to-develop/revise/pivot-with-rescue-route/high-risk/abandon-only-after-rescue——与 hypothesize 教训的 proceed-with-caveats 同构)。

## 4e. ARIS 全 skill 深读收获(全部有出处)

宪章三件(实现时原文进 prompt):
- **acceptance-gate.md**:"A goal/loop can DRIVE; it cannot ACQUIT." 门只有两型:Type-A(哑脚本可答:exit code/stat/计数器/解析器——**优先用外检,不信 LLM 的"我认为完成了"**)可自判;Type-B(质量/正确性/接受)永不自判,跨族裁决。复合门**拆开不许平均**。判别问句:"**一个没有品味的哑脚本能答这扇门吗?**" 反模式:"我们复审到过为止"(谁说过了?)、"收敛即正确"、"分≥6 就停"(除非打分的是外族)。
- **integrity-forensics.md**:append-only 义务台账;消失的 finding 仍是 OPEN(改措辞≠修复);**回据是重验的不是记住的**(每次后续 gate 重验证据文件存在且 hash 一致,改证据=重开 BLOCK);**禁环条款:"edit→re-sweep→repeat until CLEAN 教会编辑器击败检测器"**——修复只许针对 finding 本身,删带锚跨度不是修复;REVIEW_UNAVAILABLE→BLOCK("不完整的扫描不能放行")。
- **fan-out-pattern.md**:分片只许枚举/起草/检索/攻击,**永不许排名/宣称最佳/判新/判完**("五次同分布抽样是带误差棒的一个意见");jury 前机械去重省预算;分片只读共享工件;**给 jury 上游承重工件的路径让它查依赖**(防级联幻觉)。

席位/对象纪律:
- assurance-contract:verdict 六值 PASS/WARN/FAIL/NOT_APPLICABLE/BLOCKED/ERROR;**NOT_APPLICABLE≠SKIP**(查过没有也要落工件,区别"查了没有"与"忘了");BLOCKED>NOT_APPLICABLE(无原始结果可验=阻断);工件带 audited_input_hashes,**verifier 重算 hash 不符=STALE**;聚合器拒绝给语义审计贴 deterministic 标;provisional(同族)/accepted(跨族或确定性)。
- resumable-runs:**done(执行完成,可自报)与 accepted(跨族或确定性验证通过,只有 accept() 能写,需 verdict_id)分离**;resume 走到第一个非终态相位,自报 done 但没过审的要重验不许静默跳。
- evidence-precheck:两级——确定性 stage1 抓**幻觉**(numeric-token 相等:73.2≈73.20 但 73≠73.5;非数字按规范化子串),跨族 stage2 抓**真而错**;"verified 只意味着证据存在,绝不意味着声明成立"。
- effort-contract:**effort(深度旋钮)与 assurance(门严格度)正交**——lite 也不许放松门;数字档:seeds 1/3/5/5、review 轮 2/3-4/6-8、ablation 2-3/4-5/6-8/10+。
- external-cadence:**停滞=计数不凭感觉**(连续零新发现迭代入 sidecar;≥2 换结构非战术;≥4 升级人);净重写与补丁是平级动作,两次净重写同样失败=契约/环境错=人的事;watchdog 只检测不重启。
- reviewer-independence:**只传文件路径**,禁执行者摘要/推荐/上轮反馈;injection-hygiene 两层(正则 block-on-hit + jury),锚定攻击词表不锚"命令式英语"。
- auto-review-loop:停机=score≥6 **且** verdict∈{ready,almost} 双条件(高分+not ready 不停);**REVIEWER_MEMORY append-only + 每次调用前记 SHA-256**,分数回归时 diff 两轮原始 trace 找翻转判据;**偏置守卫:禁"since last round/我们修了"措辞 + 每轮 fresh thread——实证同线程灌分 3/10→8/10**;debate 协议(执行者逐条 Accept/Partially/Reject,审者裁 SUSTAINED/OVERRULED)。
- paper-claim-audit:**零上下文**(只给 .tex + 原始结果文件,不给日志/摘要/历史);七失败模式:数字膨胀(只许显示精度内的标准舍入:84.7→84.7/85% 可,84.7→85.3 不可)/best-seed 摘桃(必须写明 avg/best/median)/config 不匹配/聚合数数(实跑数 vs 声称数)/delta 算术/caption-表不符/scope 超称("consistently"但只 2 数据集);无原始结果可验→BLOCKED no_raw_evidence。
- kill-argument:T1 fresh 写**最强单条拒稿备忘录**(~200 词,不许对冲不许列清单);T2 独立分解 3-7 原子点,各标 answered/partially/still_unresolved+severity;**裁决由映射表计算不由裁决者给**(≥1 critical 仍悬→FAIL;PASS 需全 resolved 且 partial 仅 minor)。
- experiment-plan:**≤2 primary claims/5 blocks/3 baseline families/默认 3 seeds**;每 claim 带 **anti-claim**(要排除的替代解释:"增益只来自参数量")与最小说服证据;每 block **成功判据与失败解读成对** + Main/Appendix/Cut 路由;"每个实验必须护一条声明,不改 reviewer 信念的砍掉"。
- experiment-bridge:**代码先跨族审再上 GPU**;自动修预算 **2 补丁 + 2 净重写**;**>2× 估时→标记并继续**;eval GT 三查(用数据集真 GT 不是模型输出)。
- experiment-queue:状态机 pending/running/completed/failed_oom(延迟重试≤3)/failed_other→stuck;**完成=期望输出文件存在,不信 screen 状态**;波次发射四条件(进程全退/无僵尸屏/GPU<500MiB/前置满足);依赖的终态=completed **或 stuck**。
- ablation-planner:组件消融>超参扫描;config-only>改代码;输出含 **unnecessary_ablations**(看似有用不会增见的显式跳过表)+ 最优信息序;负结果也记录(去模块无效应=重要发现)。
- training-check:自适应间隔,异常即重置;三分明确判(clearly bad 停/clearly fine 续)与 unsure→跨族单次 STOP/CONTINUE/WAIT 强制枚举;两层分离(watchdog=进程健康,training-check=训练质量)。
- dse-loop:TIMEOUT 2h/MAX_ITER 50/PATIENCE 10;**绝不重跑同一配置**;指标编程解析不目测;**换解析器后必须重解析一个已完成迭代的原始输出并复现该行,不一致则修复或全量重析+标记**("一个日志里不混两种解析语义")。
- compute-env:spec 内容 hash=机械陈旧判定;三级验证(import→**种子化 kernel witness 打印哨兵 + expect 正则**→fresh agent 只拿文档逐字执行不许即兴,"卡住点即文档的谎言")。
- auto-paper-improvement:MAX_ROUNDS=2(边际递减);编辑白名单(禁 new_cite/new_theorem/新数值声明,正则探测新增行);**复述回归测试**(归一化比较主文与附录定理陈述,假设/情形拆分/量词序变化=漂移即阻断)。

## 5. ccf / ARIS 部件去向（后续逐个填成 skill）

| 部件 | 去向 | 填什么 |
|---|---|---|
| ccf evidence-design 最小说服包四件 | R1 判据 + T4/T5 的行定义 | 每件对应哪个 contract row |
| ccf 基线矩阵（can_run yes/no/unknown，缺则理由） | spec.arms[] 字段 | 缺基线不许静默替换（experiment-discipline） |
| ccf 消融逻辑模板（组件/替换/影响指标/失败解读） | T5 每 arm 的 schema | |
| ccf result-templates 主表/消融表/鲁棒表 | paper draft 的表骨架从 spec.arms 生成 | 不写死方法名 |
| ccf experiment-discipline：smoke 五条件、confirmed 全版门 | T1 范围；R1 硬底 | |
| ccf integrity-auditor 四态 | R4 | |
| ARIS experiment-integrity 四禁 + eval 类型声明 | R2 integrity 镜头；R3 检 F | spec 必须声明 eval_type=real_gt |
| ARIS experiment-audit 六检 A-F | R3 角度集原文 | |
| ARIS result-to-claim：确定性预检 → 裁决 → yes/partial/no 路由 → fail closed | R4 + T3 | partial → 收窄 statement 与 C.strength |
| ARIS Type-A/Type-B | 席位规则 §0 | |
| ARIS "verdict-bearing 不许进循环自我放行" | REVIEW 的 remediate 有界（1 次）；重验只增量 | |
| ARFT Table 8 证据包 | evidence/index.json 的字段表 | problem_readme↔spec+row；harness.jsonl↔journal+progress；submissions↔test-half 读取记录；evaluator/↔eval_entry 源码原文 |
| ARFT Table 9 评分信号 | T1/T3：exit code、canary、reward 都不是质量 | |

memory 里的 campaign 教训也进判据：screens invert arm ordering（T2 不选）；first-run failure（T2 失败换方向不加码）；prereg threshold must bind（阈值对该 cell 的最大可得效应检查）；score against operative margin（用 max(declared, realized MDE)）；probes must prove themselves（T0 探针先复现一个已知数再读内部）；measure before interpreting（读 gating 前量每个系数）。

---

## 6. 对象与 dag 接口（改动最小）

- M 加 `tier ∈ {T0,T1,T2,T4,T5,T6}` 和 `arms[]`；同一机制候选在不同级是不同 M（M-0003@T2、M-0004@T4），`depends_on.prev_tier` 指向上一级的 R。
- R 加 `tier`；T3 不产 R，产 `methods/<M>.support.json`（放行句 + 重算表）。
- E 只从 T4/T5 的 R 产生；T0/T2 的 R 只挂在 M 上供 research `add_mechanisms` 读。
- `next` 的梯逻辑：候选有 T0 R 且方向对 → 派 T2 spec；T2 R 存在无 support → 派 T3；support = supports_full_run → 派 T4 spec；T4 E 落地且 baselines/ablation 行开 → 派 T5。
- `put` 校验：tier 越级 REJECT；T2 的 R 试图产 E → REJECT；statement 含 "robust/extensive" 而 T5 未完 → REJECT。
- launch 在 put 里（不是 agent）；`launch_wrap.sh` 退出写 `evidence/index.json` 和 test-half 读取计数。

---

## 7. 席位（GLM + Grok 为主）

| 步 | 席 | 每 M 次数 |
|---|---|---|
| D0 设计起草 + Opus 反向仲裁 | sol + Opus | 1+1 |
| K 门 kill plan(sol/K3/GLM 出测试 + Opus 排序) | sol + K3 + GLM + Opus | 1+1+1+1(每候选) |
| RR 反向审(三席隔离 + 脚本路由) | sol + K3 + GLM | 1+1+1(每 Claim) |
| Draft spec（每级,从 D0 设计展开） | sol | 1 |
| R1 / R3 finders + verifiers + sweep | GLM | ~6 + k |
| R2 code review(finders+verifiers+sweep) | **GLM + Grok**(Grok=外族 finder,锚定或丢弃) | ~8+2k |
| R1/R3 外族 finder、R4 复核 | Grok CLI | 4 |
| Implement / fix | GLM | 1-2 |
| Recompute | 脚本 `tools/recompute.py`（result_contract 固定）；metric 不在注册表才 sol | 0-1 |
| T3 放行 / T4 Judge | Opus | 1 |

昂贵调用每 M：sol 1、Opus 1、Grok 4。Grok 缺席回退 GLM 三镜头 + 分组 verifier，并标 `type_b_absent`，该 M 的 E 最高 adequate。

---

## 8. 待定项裁决(2026-09-05,五源读毕)

**实现状态 2026-09-05**:`.claude/workflows/experiment.workflow.js` 已实现(974 行,5 模式:
design/build/judge/support/rr;REVIEW 引擎 find→group→verify→sweep + 脚本硬底 + 有界修复 1 轮;
席位缺席=infra error,Grok 缺席=degraded;E 裁决=kill-argument 计算式映射表强制覆盖;exit 3/5 走
infra 路线不耗修复轮)。mock 回归：`.research/tests/mock_runtime_experiment.mjs`——5 模式快乐路径全过 + 6 条敌意路径全命中。

**评审修复轮（外部全读 976 行后 20 项发现）**：P0 全修——#1 R1 error 守卫；#2 T2 存亡并入 beats_inherited_base；
#3 修复轮后重跑 probe:diff 重算泄漏硬底（不再清空）；#4 Grok 缺席=degraded（gate_passed/launched 带 provisional、
E.strength 封 adequate）；#5 Grok findings 进同一分组 verifier（锚定或丢弃：文件不匹配 scope 即丢），不再免费 CONFIRMED；
#6 K 门重构：Opus 按 index 合并去重+排序→截 4→硬底（补 canary 必有/至少一测 eval_only/阈值≤max_effect_available），
命中→重排一次→仍命中 k_floor_failed。P1 全修——#7 E/t3 recheck 改 Type-A（Bash 数值 grep 贴输出）+critical 让步→refutes；
#8 exit 4=early_kill（T2 即击杀）、exit 读不到=infra error；#9 行从 ladder_map[tier] 取、指标字面查全部 tier 行，
T3 行可选（row_id）；#10 rr 硬底消费（rr_blocked）+answers_points 对照未决点；#11 预检 Type-A 化（prompt 级）；
#12 FROZEN 字符串/对象归一；#13 臂-行改为"≥行数+臂必须∈D0 设计 arms"（配对行合法双臂，严格相等对配对语义错误，
未授权臂仍拦）。P2：#14 动词感知的 eval_entry 步骤检查；#15 spec 文件名带 M id 防并发覆盖；#17 sweep verifier 带
severity/failure_scenario。未修（记录）：#16 A.spec 缺省时 recompute 显示"？"（可降级）；#18 E 枚举与 v7 dag 的
{supports,ined,method_invalid}映射留给 dag 接线；#19 probe:diff 第 3 步为提示性，权威在 dag 的确定性 launch_checks。未做：dag.py 的
tier 状态机与 put 校验、launch_wrap.sh 补 evidence/index.json 与 test-half 读取计数、真实 dry-run。
全过 + 4 条敌意路径(双射破/指标字面不符/canary exit3/E 裁决覆盖)行为全部正确。未做:dag.py 的
tier 状态机与 put 校验、launch_wrap.sh 补 evidence/index.json 与 test-half 读取计数、真实 dry-run。

1. **T0 探针=正式一级。** 三源合流:ccf discriminating test 是方法声明的强制双链之一(什么结果能把本机制与最近替代分开——这就是探针);ARIS compute-env 的种子化 kernel witness 就是 T0 的形态;memory "probes must prove themselves"(先复现一个已知数再读内部)。T0 只许可方向,产出挂 M 供 research add_mechanisms 读。
2. **Recompute 脚本化=接受。** ARIS evidence-precheck stage-1 模式照抄:numeric-token 相等(73.2≈73.20,73≠73.5)、非数字规范化子串、批量 exit 码;metric 不在注册表才 sol。前提(result_contract 固定在 FROZEN Platform)成立即写 tools/recompute.py。
3. **Grok CLI 审 JSON=可行**(binary 在 ~/.grok/bin/grok)。R1-R4 的 Type-B 席=Grok 读工件原文;缺席→REVIEW_UNAVAILABLE fail-closed,该级 provisional、E 封 adequate(§7 已有)。
4. **Judge=Opus 单席 + Grok 复核,不是 trio。** ARIS acceptance-gate 明言 fan-out≠jury("同族五票=带误差棒的一意见"),Type-B 的价值在跨族不在票数;ARFT F.4(82.5%)说明敌人是橡皮图章不是分歧——一个跨族复核比三个同族并行更对症。sol 只管 recompute 兜底。R4 的 kill-argument 形态(T1 最强拒稿备忘录→T2 计算式裁决)作为 E.verdict 的结构。
5. **T5 表界=reviewer 问题具名制。** 每张表必须具名回答 ccf 七问之一且落入三大顶层问题(effectiveness/causality/generalization-and-limits)之一;一表一信息,两信息拆表;答不出的表不跑进 T5(ccf experiment-plan:"不改 reviewer 信念的砍掉");消融优先级=组件>超参、config-only>改代码;unnecessary_ablations 显式列出(ARIS ablation-planner)。
6. **skill 全部写进 experiment.workflow.js 常量**(与 research.workflow.js 同构,单一 workflow 即 skill;判据文本取自本文各表,出处行号已注)。

## 9. 槽位填充(判据全部有出处;实现时抄进 workflow 常量)

| 槽 | 判据合同(来源见 §3/§4b-e) | 状态 |
|---|---|---|
| exp-kill (K) | 三席出测试 + Opus 排序;硬底五条(阈值绑得住/首测≤kill cap/oracle 天花板第一测/dev half/canary);≤4 测;首杀即停;K3 席吃 harsh reviewer lens + reviewer_attack_surface | 已填(§1.5 判据块) |
| exp-rr (RR) | paper round Referee prompt 复用;needs_* → contract row(prevents_deduction/fills_cell);FIXED_RULE 裁剪 ≤6;Execution Priority Table 定 T5 顺序;回收规则 | 已填(§1.5 判据块) |
| exp-probe (T0) | 只读不训练;**探针先自证**(复现一个已知数再读内部);每候选必须回答 discriminating test("什么结果能把本机制与最近替代分开");种子化干预 + 期望正则(compute-env witness 形态);只许可 contract 行方向,声明天花板 preliminary;有信号→T2,无→候选 invalid | 已填 |
| exp-smoke (T1) | ccf smoke 五条件全过才保留;完成=**期望输出文件存在**(不信 screen/exit 状态);exit 码分诊表:3=canary 败→infra 路径,4=early kill,5=infrastructure(ARFT Table 9:执行状态≠质量信号,judge_unavailable/no_decision 非质量);canary 49.11±0.10;eval_entry 受保护(CORAL 式结构隔离) | 已填 |
| exp-mve (T2) | kill cap FROZEN;候选与对照同预算;**只杀不选**(禁超参选择);first-run failure 不加码换方向;修预算 **2 补丁+2 净重写**(两次净重写同样失败=契约/环境错→升级);>2× 估时→标记继续;晋级判据=**效应方向对且击败继承基线**;exec-time floor(太快=可疑) | 已填 |
| exp-support (T3) | 0 GPU 放行门,非实验:确定性预检(numeric-token 相等)→ 只喂预检过者 → Opus verdict+Grok 复核 → yes/partial/no 路由;partial→收窄 statement 或再一次 T2 换 seed;no→postmortem 约束回 research;fail-closed | 已填 |
| exp-main (T4) | **对照组先跑**(实验组等 control 完成);全 arm 一个 unit;test half 读一次(硬底计数);配对 bootstrap CI95 固定 seed 10k;**≥3 独立跑、先差后聚合、±1 std**;每 arm 有 seed 文件、sha8 一致;关 primary/control/clean_cost 行;E.verdict 用 kill-argument 结构(最强拒稿备忘录→计算式裁决) | 已填 |
| exp-series (T5) | 每表具名 reviewer 问题(七问∩三大顶层);一表一信息;消融四件套(组件/替换/影响指标/失败解读);组件>超参、config-only>改代码;unnecessary_ablations 显式跳过表;负结果同格记录;证据阶梯顺序:现象→主效应→机制→泛化→边界;行全关→paper | 已填 |
| exp-repro (T6) | ≥3 seed(预算内);pip freeze/配置 hash/数据 hash(内容 hash=机械陈旧判定);done/accepted 分离记录;许可 reproducibility 句 | 已填 |
| review-spec (R1) | 硬底(脚本):arms 数=open rows、eval_entry∉steps、run_cmd 可解析、预算≤FROZEN、tier 合法、outcome_metric 与 contract row 字面相等。模型判据:七问映射、基线矩阵(can_run 三值+缺则理由,reproduced/reported 分开)、最小说服包五件、≤2 primary claims、每 claim 带 anti-claim + 成功判据/失败解读对、方法声明双链(protocol anchor + discriminating test)、**B1 粒度**(方程+方法+步骤到函数+参数,ASI ETDRK4 范例;禁止只给方法名)。Type-B=Grok 读 spec 原文 | 已填 |
| review-diff (R2) | 硬底:eval_entry 无 hunk、steps 全有 hunk、测试集 token 扫描、smoke 产 seed_0.json。Finder:CodeReview 角 A-E + 三镜头(spec-drift ARFT C.3 / leakage C.1-C.2+Iron Rule 6 / integrity ARIS 四禁);**锚定或丢弃**(existing_code 逐字节匹配);外族 finder=Grok。Verifier:分组独立,PLAUSIBLE-by-default,REFUTED 须可从代码构造,未裁决=丢弃;盲删过滤器(只见 diff 只删可证伪者);Sweep 只找清单外 | 已填 |
| review-artifacts (R3) | 硬底:sha8 一致、每 arm seed 文件、metric key 存在、canary 在 tol、test half 读取=1、checker 六类总量/分节/厚度/密度(≥85% 带锚、shingle≤8%、照抄≤20%)。角度:ARIS 六检 A-F + ARFT C/D + Iron Rules 九条 + Table 9 理由码 + observable mismatch;每 finding ≥1 锚+[stage\|root-cause] 尾标 ≥200 字符;**极端指标(恰 1.0/0.0)自动触发泄漏审计**;可便宜重算的数字 verifier 亲手重跑比对;Type-B=Grok 读 eval 代码+结果 | 已填 |
| review-claim (R4) | 确定性预检:statement 每个数在重算表(numeric-token 相等)、CI 不含零才 supports、row 字面满足、tier 天花板未越、七失败模式(paper-claim-audit:数字膨胀只许显示精度舍入/best-seed 声明/config/聚合数数/delta 算术/caption-表/scope 超称)。模型判据:ARFT D.3/D.4/D.7/E.2/F.4(证据表必填替代解释+为何排除)、**SELF_AWARE=Iron Rule 9**(reasoning 点出致命而 verdict 不反映→verdict 无效)、已知致命自诊断的报告拒收;**绝不用平均抹掉致命伤**;failed sanity check 必须进 statement 或 limitations;claim-evidence status 四态回填;修正台账 done 需 artifact。Grok 复核 Opus | 已填 |


---

## V2 重写(2026-09-05,按 WORKFLOW.md 自适应实验设计)

`experiment.workflow.js` v2 已重写(703 行,v1 梯式归档 `.research/archive/experiment-v1-ladder.workflow.js`);
3 mode(plan/build/judge)自适应循环替代 5-mode D0→T0-T6 梯。mock 3-mode 全绿(`mock_runtime_experiment2.mjs`)。
关键结构变化:
- PLAN: Sol∥K3∥GLM 三路并发(无 GLM router barrier);JS normalize + hard floors + chooseTest(eval_only > cost↓ > rows↑);
  K3 未覆盖的 fatal objection 由一个短 GLM 转 TestSketch。
- BUILD: Sol B1 编译→GLM 实现→**probe∥spec-drift∥integrity∥runtime 四路并行**(probe 为 Bash 非 LLM)→Sol verify→
  fix 轮后**targeted re-verify**(只查修过的 findings + floors 重检,不跑全量 review)→launch(canary)。
- JUDGE: 确定性 manifest(Bash)→**Sol recompute∥GLM integrity∥GLM grounding 三路并行**(互不依赖)→
  GLM analysis + **conditional K3**(六 trigger 全 JS 判:unexpected_sign/effect_huge/tiny_margin/control_also_moves/
  sanity_warning/contradicts_prior)→Sol evidence-edge verifier→E。
- **Invalid ≠ refuted**(JS 状态机:NaN/test-half>1/seed 缺/exit≠0→E.valid=false,Claim 不动)——infra 全 JS 非LLM prior。
- **claim_strength 为 derived**(row_evidence 推出,非独立 truth source;收敛到 untested/active/supported/refuted 四值)。
- TestKind 只留 mve|claim_evidence;publication logic 全移出。