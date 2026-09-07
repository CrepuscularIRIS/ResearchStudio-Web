# V9 Brain 架构：RS 为脊柱 + 四处补线

日期：2026-09-06。状态：讨论定稿，未实现。取代本目录下 role-workflows.md 中 Brain B0–B8 的相位设计；Worker W0–W8 与 dag 实验侧不变。

## 0. 一句话

Brain = ResearchStudio idea-spark 原样（Phase 0–4）+ 仓库 intake（前）+ 一处不阻塞的 DR 引文校验（中）+ Astra 推导席（后）+ 实验契约（末）。研究侧不用 dag，宿主就是 Brain 会话，RS 自带导航器；dag 只管实验侧（GPU、租约、角色、判决）。

目标只有一个：效率最高，原创，高质量高创新的算法，刷分。不做多样性扇出，不做第二透镜，一次一个 idea，隔离到底。

## 1. 输入与输出的变化

| | RS 原版 | V9 |
|---|---|---|
| 输入 | 一句研究方向 + intake 10 字段（缺的自推） | 仓库 + 数据集 + 目标会议；问题自己找 |
| gap 来源 | 文献留下的 residue | 文献 residue **+ 仓库实测异常**，同等地位 |
| 输出 | idea 卡 | idea 卡 + 推导 + evidence_plan（B2 契约）→ Worker |
| 实现层 | 4.1.5 可实现性审计（无仓库） | 砍掉，Worker 的 spec 席带仓库做 |

RS 的核心原则保留：机制必须从文本可算；判改分席；便宜的杀先做；模式是诊断词汇不是模板；K=1；每个 LLM 相位隔离上下文，宿主 ≤30k，产物落盘。

## 2. 相位表（模型、工具、类型）

| 步 | 名称 | 类型 | 模型 | 允许工具 | 产物 |
|---|---|---|---|---|---|
| −1 | 仓库 intake | 席 | GLM | Read/Glob/Grep/Bash 只读 | intake.json、substrate.md、anomalies.md（可空） |
| 0a | 写 4–6 个查询（含 escape-mechanism） | 宿主 | Brain | — | queries.json |
| 0b | 检索 + 去重 + 角色窗口 | 脚本 | — | — | lit_results.json、lit_table.md |
| 0c | 15 模式打标（分 2–3 片并行） | 席 | GLM | Read/Write | pattern tags |
| 0d | 全文抓取（硬门 ≈15 篇） | 脚本 | — | — | fulltext/ |
| 1 | 瓶颈诊断 + method_lineage 谱系树 | 席 | **Opus** | Read；Bash 白名单仅 topup 脚本 | bottleneck.json（residue 含引文） |
| 1v | DR 校验 A：residue 引文三票（与 2.1+2.2 并行，不阻塞；结果喂 3.2） | 席 ×N 并行 | GLM | Read | 每条引文 verified/refuted |
| 2.1+2.2 | 选 gap×模式 + 生成候选（同一上下文） | 席 | **Opus** | Read/Write | candidate.json、deferred_gaps[] |
| 2g | 引用门（子模式 id 必须来自卡文件） | 脚本 | — | — | pass/fail |
| 2.3 | 连贯门：干跑执行、独立构造 naive（= 推导席：T1 形式化 / T2 执行干跑 / T4 性质定级 / T5 naive） | 席（fresh） | **Opus**（失败回退 GLM；Astra 的额度在这一席死过两次） | Read/Write/Bash 仅 python | blocking_findings.json |
| 3.1 | 碰撞双通道（signature@10mo、alias@48mo） | 脚本 ∥ 2.3 | — | — | collision_hits.json |
| 3.2 | 五项审计 | 席（fresh）×2 并行 | **K3**（裁决者）∥ **Sol**（第二审稿人，同提示词，自己的文件） | Read | verdict abandon/advance/revise（合并规则见 §10） |
| 3.2b | 反驳复核（条件） | 席（fresh） | K3 | Read | — |
| 3.3 | 补丁（只改审计点名字段） | 席 | Opus | Read/Write | candidate.json v2 |
| ~~3.5~~ | ~~推导席~~ 并入 2.3（2026-09-07 深夜：不加席，换模型） | — | — | — | — |
| 4a | 骨架 | 脚本 | — | — | card skeleton |
| 4b | 填 method 相关字段（key_equations、what_changes、feasibility）；abstract_draft、reviewer_concerns 等延后到实验后 | 席 | Opus | Read/Write | card.json |
| 4c | 组装 + method_view + 校验（derive、render 砍） | 脚本 | — | — | card.md |
| 5 | evidence_plan | 席 | Opus 或 GLM | Read/Write | B2 契约给 Worker |

计数：席 10 次（Opus 5、GLM 4–5 类、K3 1–2、Sol 1 = 3.2 第二审稿人，与 K3 并行不加跳），脚本 6 次。3.2v 已砍（改为 K3 必须引全文原句）。与额度 100:20:5:1 相符。

工具禁用原则：出品味的席不许搜不许跑（Opus）；判的席只许读（K3）；跑的席只许 python（2.3）；分类的席只许读写（0c）；Astra 只见冻结对象。Brain 主会话只跑脚本、派席、记状态，不写内容。

## 3. 四处补线（RS 之外唯一新增）

1. **Phase −1 基质**。RS 假设纯文本输入。intake 席把机制层会用到的代码事实提前抽到 substrate.md：指标与协议、模态如何进入、算子形式、张量形状、已有 baseline、算力。抽漏由 2.3 干跑暴露，回补 substrate 再跑，不让 Opus/Astra 翻代码。
2. **两根接线**。(a) anomalies.md 作为 residue 来源与文献 residue 同等进入 Phase 1；(b) 2.2 的前提账本加一条 substrate premise（机制假设的结构在这个仓库存在吗），2.3 对 substrate.md 核。
3. **DR 只做 verify 一步，一处**。1v 引文三票（全文已本地，约 10 次并行，与 2.1+2.2 并行不阻塞）。不做 DR 报告、不做综合、不做方法盘点、不做补证回路。任何拖慢脊柱的校验都不加。
4. **Astra 与契约**。3.5 输入冻结卡 + substrate.md，输出形式定义、成立条件、复杂度、失效条件、falsification_prediction 是否可从公式推出；禁改机制禁提新 idea。放在 3.3 之后的理由：额度 1，只给活过审计的 idea；拿冻结对象才不会顺手改设计。Phase 5 读 CCF experiment-designer refs 出 arms、baseline 矩阵、keep_rule、gpu_h。

## 4. 谁读代码

| 层 | 问题 | 读什么 | 谁 |
|---|---|---|---|
| 机制设计（2.2） | 改哪个算子、为什么有效 | substrate.md | Opus |
| 推导（= 2.3 干跑） | 命题、条件、失效点（T1/T4/T5） | 候选 + substrate.md | Opus 新上下文（回退 GLM） |
| 实现设计（Worker W0） | 改哪个文件、几行、跑多久 | 代码 | GLM |

## 5. ARFT / ASI-Bench / CCF 的插入方式

不作为阶段，作为参考文本进席：

| 来源 | 进哪 | 形式 |
|---|---|---|
| ASI-Bench | Phase 5 | B2 契约字段；B1 留给 Worker |
| ARFT 失败分类 | K3 3.2 检查表；Worker 判决 | 逐条失败模式核对项 |
| CCF experiment-designer | Phase 5 | baseline 矩阵、消融合同、keep_rule |
| CCF 审稿打分 | K3 3.2 | 打分口径，只判不改 |

## 6. 并发

- 同一领域共享 Phase 0（`phase0/` 目录 + 全文缓存）；0c 打标分片。
- 2.1 处按 `deferred_gaps` 分叉 K 个 run 目录，各自独立走 2.2→5；跨 run 去重由 RS 自带。
- 2.3 ∥ 3.1；1v 与 2.1+2.2 并行；3.2b 条件串行。
- 估计（2026-09-06 原文，已被实测推翻）：冷启动 Phase 0 3–10 分钟；K=3 warm 约 35–40 分钟出 3 张卡。**实测（2026-09-07，§9i）：干净一腿 k=1 ≈ 170 分钟（Opus 席 @ max effort），含一次 RS abandon→retry 周期 ≈ 305 分钟；Phase 0 冷启动 ≈ 15 分钟。**

## 7. 砍掉的东西

15 席 reframe 扇出、tension 卡、DeerFlow planner、双轨、渐进 DR-lite/full、第二透镜、ChatGPT 出 idea、Grok 插件、RS 的 derive/render/4.1.5、Claude 原生 DR 的 ~97 次调用、研究侧 dag。

## 8. 资产搬运清单

已逐字整目录搬到 `docs/refs/`（`docs/refs/INDEX.md` 有相位→文件对照；`skills/` 被 .gitignore 排除，故放 docs）。原清单：

- 提示词：bottleneck_identify、ideate_select、ideate_generate、coherence_trace、critique、revise、expand、refutation_recheck、falsification_reaudit
- 卡：ideation-patterns 15 张 + overview、sub-patterns C00–C30 + overview、anti-patterns、companion-combos、pattern-summary-rubric、design-notes
- 脚本：run.py/next_step.py 导航器、search_*.py 连接器、phase0、phase0_fulltext、phase4_skeleton、validators/*、schemas.md
- 新写：intake.md（Phase −1）、verify_quote.md（1v）、derive_astra.md（3.5）、evidence_plan.md（Phase 5）

## 9. 交接点

Brain → Worker 只交一个对象：card.json + derivation.md + evidence_plan.json，经 `dag.py deliver` 进实验侧。Worker 的 W0 spec 席替代 RS 4.1.5，带仓库做可实现性。

## 9b. 实现（2026-09-06 晚，第二版：一整套 TS）

入口是一个自包含的 Workflow：`.claude/workflows/brain.workflow.js`（约 275 KB，其中 230 KB 是逐字内联的 RS 提示词与参考文件）。Brain 会话直接触发：

```
Workflow({scriptPath: '.claude/workflows/brain.workflow.js',
          args: {root, repo, dataset, venue, goal, anomalies, k}})
```

没有 agent md、没有 python tick/bundle 层：所有逻辑（相位图驱动、路由、并发、提示词拼装）都在这一个 JS 文件里，和 reframe/experiment 等 V8 workflow 同一种写法。

**三种调用。** (1) runner：GLM、effort low、只跑一条 shell 命令并原样返回 `{rc, out}`——RS 的脚本步骤（phase0、lit_table_merge、phase0_fulltext、phase2_prepare、phase3_collision、merge、skeleton、assemble、validate、render）和导航器 `run.py next` 都经它执行；长任务（检索、全文、碰撞）`setsid` 后台化，pid 落在 `ROOT/.jobs/`，runner 轮询（每次 ≤8.5 分钟，可把 `next` 折叠进最后一次轮询）。(2) 席：`agent(prompt, {model, schema})`，提示词 = 静态块（席框架 + 工具纪律 + RS 系统提示词逐字 + 该席要读的参考文件逐字）+ 动态块（SKILL_DIR/RUN_DIR、导航器给的 INPUT/OUTPUT/NOTES、Brain 额外上下文）；静态块按席种类构建一次，跨 run 前缀相同，命中 prompt cache。(3) 导航：TS 解析 `next` 的 emit（STATE/STEP/TYPE/PROMPT/INPUT/OUTPUT/RUN/NOTES），按 PROMPT 文件名路由到席种类并钉模型。

| 席 | 模型 | 工具纪律 | 内联的 RS 文本 |
|---|---|---|---|
| Phase −1 intake | GLM | Read/Glob/Grep + Write | intake.md、intake-routing、intent-recognition |
| 0c 打标分片（≤3 片） | GLM low | Read/Write | tagging_shard.md、rubric、patterns overview |
| Phase 1 | Opus | Read/Write | bottleneck_identify.txt |
| 2.1+2.2（一席） | Opus | Read/Write | ideate_select + ideate_generate、patterns overview、companion-combos、sub-patterns overview |
| 引用门修复 | Opus | Read/Write | sub-patterns overview |
| 2.3 干跑 | GLM | Read/Write + Bash 仅 python3 脚本（WORKDIR=phase2_coherence） | coherence_trace.txt |
| 3.2 / 反驳复核 / falsification 再审 | K3 | Read/Write | critique.txt（+anti-patterns）/ refutation_recheck / falsification_reaudit |
| 3.3 | Opus | Read/Write | revise.txt |
| 4.fill | Opus | Read/Write | expand.txt |
| 4.derive / 4.1.5 | GLM | Read/Write | derive_plain / implementability_audit |
| signature_terms 补齐、do_not_generate/phase_3_failed 写文 | GLM | Read/Write | intent-recognition（Collision mode）/ 无 |
| Phase 5 evidence_plan | Opus | Read/Write | evidence_plan.md、CCF evidence-design + result-templates、ARIS experiment-plan |
| Rank（K≥2） | Opus | Read/Write | rank.md |

15 张模式卡和 31 张子模式卡不内联（超 512 KB 上限），席按提示词指示自己去 `docs/refs/rs/references/` 读。

**Brain 加进 RS 的上下文（动态块里的几行）：** Phase 1 收到 direction、intake.json、substrate.md、anomalies.md（与文献 residue 同等地位）、FROZEN goal；2.1+2.2 收到 substrate.md 并被要求在前提账本写一条 `substrate:` 前提；2.3 对 substrate 核这条前提；4.fill 的可行性对 substrate 的算力信封判；Phase 5 与 Rank 拿 FROZEN goal。

**并发（全在 JS 里）：** `_shared/` 做一次 intake 与 Phase 0，`cp -r` 到 r1..rK；`parallel()` 同时驱动 K 个 run；r2..rK 在导航器要 Phase 1 时 `await` r1 的 Phase 1 完成后拷贝（bottleneck-retry 模式除外，各自重做）；2.1+2.2 按 run 序号轮流（r(i) 等 r(i−1) 落地候选后再取一次 `next`，RS 自带的 CROSS-RUN DEDUP 行因此确定地看到前面的候选）；2.3 席跑时 3.1 碰撞在后台跑；各 run 之间其余步骤互不等待。席失败重试一次，再失败该 run 标 failed，不影响其他 run。

**终点：** RS 的 DONE（三张卡渲染完，含 validate）→ Phase 5 → K≥2 时 Rank 写 `ROOT/ranking.json`。返回值列出每个 run 的状态、步数、卡路径、evidence_plan、validate rc。

**环境与模型（2026-09-07 复盘后）。** 模型 id 是 claude-kimi（LiteLLM :4001）的路由名：`claude-opus-5` / `glm-5.3[1m]` / `k3-256k`。Brain 必须从 `claude-kimi` 起的会话触发；在官方 API 会话里这些 id 不存在，harness 会静默换成会话模型并沿用会话 effort（第一次跑成 3.6 h 的原因：所有 GLM/K3 席实为 Fable 5.1 @max，2.3 与 4.1.5 各空转约 50 分钟）。改法已落地：每席显式 `effort`（品味席 high，审计 high，4.1.5/intake medium，打标/derive/runner low）；`args.models`/`args.runner_model` 可按环境覆盖；`args.stagger` 默认关（2.1+2.2 并行；开则按 run 序轮流以启用 RS 的 CROSS-RUN DEDUP 行）；每席 RUN 段带 `REPOSITORY:`，substrate.md 的相对路径以它为根；RS 的 dblp 连接器超时 1200 s → 180 s（`docs/refs/rs/scripts/run.py:252`）。跑完后用 agent-*.jsonl 的 `message.model` 核对实际服务模型。

**工具纪律改为机械强制（2026-09-07，Codex 审计后）。** 提示词里的"只许 Read/Write"不被执行环境理解——第一次跑里 2.3 席用 Bash 翻仓库、4.1.5 席用 Edit 拼了 10 次。现在每次 `agent()` 都带 `disallowedTools`（品味/审计席禁 Bash/Glob/Grep/web；runner 禁 Read/Write/Edit/Glob/Grep；intake 禁 Bash/Edit），2.3 席带 `bashCommandClamp: ['Bash(python3:*)']`（只能 `python3 /绝对路径/脚本 > 输出 2>&1`，`args.no_clamp` 可关）。其他修正：bash 步骤链任一命令失败即停在 `next` 之前（validate 例外）；后台任务 `JOB_DONE` 以进程退出为准，不再以文件出现为准；打标合并失败真的会重来第二轮；导航器 NOTES 里"先跑 RUN 命令"的句子由 workflow 改写为"已执行/已后台启动"。

**测试：** `.research/tests/mock_runtime_brain.mjs`（脚本化的 RS 状态机代替 runner，席只标记输出文件；断言 intake→Phase 0→spawn→Phase 1 只在 r1→2.1+2.2 有序且 r2 看到 dedup 行→碰撞先起后等→Phase 4 链→DONE→Phase 5→Rank，以及每席模型）+ `test_brain_workflow.py`（语法、512 KB、11 个 RS 提示词逐字相等、mock 通过）。run 根目录约定 `.research/research/ideaspark/<slug>/`（已 gitignore）。

## 9c. ARFT / ASI-Bench 对照与待加的五样（2026-09-07）

来源：`docs/refs/papers/arft-2608.14905v2.txt`（45 式失败分类，附录 A 定义；四根因 R1 grounding / R2 depth / R3 integrity / R4 engineering；核心论断"评审是同一个模型写的更多文本，除非系统强制，诊断不会改变结论"）、`docs/refs/papers/asibench-2608.17271v1.txt` + `docs/refs/papers/asi-bench/`（B1–B4 引导梯度、task.yaml 结构、评分合同、oracle 校准阈值）。对照对象：第一次 live run（wf_00a3a165-dcd）的两张卡与两份 evidence_plan，用脚本核过引文可解析性、claim↔block 映射、负对照、keep_rule 数值化、基线覆盖。

### ARFT 45 式 × Brain（只列 idea 阶段相关）

| ARFT | Brain 现状 | 判定 | 补法 |
|---|---|---|---|
| A.1 框锁 | 15×31 模式卡 + deferred_gaps + K 个 run；但 r1/r2 仍撞进同一族（rank agreement / operator-site admission） | 半暴露 | r(i>1) 的 anchor gap 必须与兄弟不同：由动态块硬约束，不再只靠 RS 的软 dedup 行 |
| A.2 不可证伪 | falsification_prediction 锁字段、审计第 5 检、再审、kill-switch 校验；plan 有 11/9 条 kill 条件 | 防住 | — |
| A.3 重复发明 | 双通道碰撞 + paper_pointed_threat + reject lessons | 防住；连接器 4/6（openreview 无凭据） | .env 补 OPENREVIEW_USER/PASS |
| A.4 可行性误判 | compute_budget 对 substrate 算力信封；gpu_h 36.8 / 51.5 | 半防 | plan_check：keep_rule 阈值 ≥ substrate 里的 MDE（ranking 已点名 r2 的 B2 低于 1.71） |
| A.5 指标错位 / X.2 目标漂移 | FROZEN 只注入 Phase 1、2.2、fill、P5、Rank；3.2 审计与 3.3 补丁看不到 FROZEN | **暴露** | FROZEN 进 3.2/3.3 动态块 + scope check：contribution type、禁区（training-free、mechanism paper、新 benchmark、改协议）命中 = 硬地板 abandon |
| A.6 假设-实验错配 | claim_map↔blocks 一一对应（核：r1 5/5、r2 6/6），每块有负对照 | 半防 | plan_check：负对照必须点名 falsification_prediction 的 load-bearing 变量 |
| B.1 幻觉引文 | 连接器真检索；三个文件里的 paper_id 全部可解析 | 防住 | — |
| B.5 引文去相关 | 15 篇有全文（10 成功），其余 residue 为摘要级改写 | **暴露** | 1v-lite：Phase 1 后确定性脚本，closest_adjacent 的引句须在全文/摘要逐字命中，否则该条降为 abstract-level（RS 自带 `fulltext_degraded` 语义） |
| B.4 检索浅 | 130 篇；dblp 超时、openreview 跳过 | 半暴露 | dblp 已改 180 s；补凭据 |
| D.5 基线缺失 | FROZEN 规定每张表六条基线；脚本核到 r2 的 B4/B5 疑缺 same-curriculum control | **暴露** | plan_check：headline block 的 baselines ⊇ FROZEN 列表 |
| F.1–F.4 自审 | 3.2 独立席（不同模型）、导航器强制处置 blocking findings、反驳复核 | 防住（RS 最强一段） | 保证审计席真是 K3（见 §9b 环境说明） |
| X.5 目的论 | evidence_plan 由出 idea 的同一模型家族写 | 半暴露 | keep_rule 来自 FROZEN（外部）、负对照 + attribution 必填、Worker 阶段由 Grok 外审 |
| X.6 错因得分 | r1 有无参数归因对照 | 半防 | plan_check：`attribution` block 必填 |

### ASI-Bench 的四条规则（Brain → Worker 交接）

1. B1 = 背景 + 方法公式 + 完整程序 + 输出文件 schema + 评分合同。Phase 6 的 `spec/B*.json` 按 `task.yaml` 结构写：`input.files`、`output.files`（形状/列名）、`evaluation.gates`（硬门：必需文件、no_nan、forbidden 正则 = forbids：读 test half、改受保护 eval、训练里出现 held-out rung）、`scoring`（权重、容差 = keep_rule）、`generation.seed`。
2. 分数永远不自报：`verdict.py` + Grok `anchor_check.py` 即"website scoring"。
3. B1 的提示不能漏进 B3：Worker 看不到 test half、看不到 held-out rung 样本。
4. 阈值用 oracle 校准而非 GT 自相似：keep_rule 带宽锚在实测 seed sd（MDE 1.71）。

### Phase 6 归属：Brain（Opus，仓库只读，只许写 `spec/`）

理由：ASI 的 B1 由出题人写、不是解题人写；ARFT R3 的结论是验证必须不受被验者控制。让 GLM 自己把 evidence_plan 操作化 = C.3/C.1 没有独立参照。代价一个 Opus 席约 10 分钟。

`spec/B<k>.json` 字段（2026-09-07 第二版，对齐 V8 prompt-bank 与 experiment.workflow.js 的机器形式）：`block_id`、`claim_id`、`goal`、`tests_premise`、`anti_claim`、`method`（公式 + method_view step id）、`changes[]`（`file`、`function`、`what`、`tensor_shapes`）、`run_cmd`（完整命令，不许自设 SMOKE）、`smoke_cmd`（NOT_A_RESULT）、`arms[]`、`baselines[]`、`negctl_arm`（必须是 arms 里的名字）、`attribution`、`verdict_rule`（`outcome_metric` 逐字 FROZEN、`arms{candidate,control,negative_control}`、`keep_if_all[{key,op,value}]` 只用 m158 键 + gt/gte/lt/lte/eq + 数值/布尔、`split`、`seeds[]`、`mde_source`）、`kill_condition`、`decision_points[{name,default,why_engineering}]`（留给实现席的工程决定，必须带默认值）、`open_holes[{step_id,hole,resolution|blocked}]`（implementability 里每个 severity=open 的点都要出现）、`forbids[]`、`outputs[]`、`gpu_h`。`spec_check` 逐条核：文件/脚本存在、SMOKE 未自设、forbids 非空、run_cmd/smoke_cmd/arms 不含 test-half 模式、三个角色臂与 negctl_arm 都在 arms 里、keep_if_all 机器可读、seeds 非空、decision_points 带默认、open holes 全覆盖。这就是 Experiment 侧（GLM 主窗口 + Grok 判决）的输入合同：Brain 定科学决定，Experiment 只做工程决定，spec 留白的科学决定 = Brain 的缺陷（L2 回 Brain）。

### 要加进 workflow 的五样（按收益）

1. FROZEN + scope check 进 3.2/3.3 的动态块（`brainContext('audit'|'revise')`，0 次额外调用）。
2. `plan_check`：Phase 5 后一个确定性 python（runner 执行）——claim↔block、负对照点名变量、headline 基线 ⊇ FROZEN、keep_rule ≥ MDE、attribution 必填、forbids 必填；不过则一轮 Opus 修（上限 1）。
3. Phase 6 spec 席（Opus，`disallowedTools` 禁 Bash/Edit，Write 限 `spec/`）+ `spec_check`（changes 里的文件/函数存在、run_cmd 指向真实脚本、forbids 路径真实、arms 不含 test half）。
4. 1v-lite 引句核对（确定性，秒级）。
5. 跨 run anchor gap 硬去重。

预计加时：Phase 6 约 10 分钟，其余秒级。实施等 Codex 最终审计到齐后一并做（见 §9e 占位）。

## 9d. 实验侧（owner 2026-09-07 已定，Brain 稳定后再做）

不做 workflow、不用 dag。Worker = `claude-kimi` 主窗口（GLM）：输入 ranking 第一名的 `spec/B1.json` + evidence_plan + idea.detail.en.md + substrate.md + GOAL.md FROZEN + instruments/README.md + spec 点名的仓库文件；开 worktree → 照 spec 实现 → smoke（只落 smoke/，NOT_A_RESULT）→ launch.sh（nvidia-smi 预检、零容忍 grep、canary 旗、systemd-run、tee）→ 等 unit → verdict.py；不改 spec 的科学决定、不碰 instruments/ 与受保护 eval、不读 test half、不选 seed、不自己判 survived。判决 = Grok（`grok:rescue` 插件 agent 调 grok cli，只读）：只给路径（spec.json、diff.patch、results/、verdict.json、progress.md、smoke.log 尾、launch 日志），查 C.3 实现≠spec、C.1 循环验证/碰 test half、arm 隔离、F.4 自审未改、探针自证（checkpoint 加载率、canary）；输出 findings/X-*.json 带锚点，`anchor_check.py` 核锚点算 survived/killed + L0–L4。接线：Brain →ranking + spec/B* + evidence_plan→ Worker →run 目录→ Grok →findings→ anchor_check；survived → 下一个 block；killed L0/L1 → Worker 原地修（帽 2+1）；killed L2–L4 → 失败卡作负锚重触发 Brain。

## 9e. Codex 独立审计（2026-09-07 到齐）

原文：`2026-09-07-brain-run1-codex-audit.md`（17 条 findings + 53 次 runner 逐条核对 + 关键路径预算；它的全修估计 75–95 min，与 §9b 一致；它特别指出只修模型不修 dblp 的话碰撞的 43 min 会立刻成为关键路径）。分诊：

| # | Codex 发现 | 状态 |
|---|---|---|
| 1 | 模型 id 不存在时静默回退到会话模型 + max effort | 已修（显式 effort、args.models）；剩：脚本内无法做 served-model 自检，靠 §9b 的启动规则 + 跑后核对 |
| 2 | 2.3 席逃出工具纪律、翻仓库、100 KB 报告、额外写校验脚本 | 工具纪律已机械化；剩：报告体积上限、`written` 与命名输出的核对 |
| 3 | 4.1.5 用 Edit 当输出流拼 10 次（输出超单次 Write 上限） | Edit 未禁（禁了会直接失败）；待做：按 method step 分片输出 + 确定性合并，或压缩每步字段 |
| 4 | 多个席只读了输入的一部分（Phase 1 的 lit_results、fill 的骨架中段、derive/evidence 只读到前 256/639 行） | 待做：给 fill/derive/evidence 出精简视图（RS 已有 `phase4_method_view` 的做法），INPUT 附行数 |
| 5 | 重试只看 `ok`，从不对产物校验 | 待做：席后校验命名路径、JSON 可解析、体积、mtime，失败才重试 |
| 6 | NOTES 里"先跑 RUN 命令"传给席 | 已修（改写为已执行/已后台启动） |
| 7 | 没给仓库根 | 已修（`REPOSITORY:`） |
| 8 | 命令失败仍跑 `next`；validate 失败无"修 2 次"回路 | 前者已修；后者待做 |
| 9 | **r2 的两个 xelatex 编译失败被 `phase4_render` 吞掉，仍返回 0，run 被判 DONE** | 新发现；待做：DONE 前核对三张 md 卡存在（PDF 可选），或让 render 在缺卡时返回非零 |
| 10 | runner 自己给命令加 `echo RC=$?` 再删掉；rc 由模型自报 | 待做：`sh()` 自带哨兵并本地解析 rc |
| 11 | `launch()`/`nextEmit()` 只看输出文本不看 rc | 待做（与 10 一起） |
| 12 | 轮询以文件出现为准；超时丢弃日志尾 | 前者已修（进程退出为准）；后者待做 |
| 13 | 2.1+2.2 串行 + r1 多跑一次 `next` | 已修（默认并行；串行时 turn 0 不再重取） |
| 14 | 续跑时 rN/phase0 可能是陈旧快照 | 待做：`_shared/phase0` 写 manifest，spawn 前核对 |
| 15 | 打标第二轮永远跑不到 | 已修 |
| 16 | 零散违约（读未列文件、写后 Edit、审计多读两段空 offset） | 工具纪律已收；精简视图见 4 |
| 17 | dblp 超时：phase0 全额 20 min，碰撞 2×20 min 被 2.3 遮住 | 超时已改 180 s；待做：会话内首次超时后跳过该连接器 |

**2026-09-07 落地情况（brain.workflow.js 第三版，mock 69 次调用全过）：** 哨兵 rc（10/11：每条命令包在 `{ … }` 里由 workflow 自己打 `__SH_RC`，`launch()` 要求 rc=0）；席后产物校验（5：席写的 JSON 在下一次 `next` 的同一个 runner 调用里先 `json.load`，坏了就换新上下文重跑该席一次）；轮询超时保留日志尾（12）；phase0 manifest（14：`_shared/phase0/.manifest`，spawn 前 `cmp`，不一致就重拷）；DONE（9）由导航器保证三张 md 卡存在，PDF 可选不再另查；4.1.5（3）不禁 Edit，等真模型再看体积；精简视图（4）先用提示词硬约束"读到最后一行"，不改 RS 脚本；validate 修 2 次（8）未做，记 rc。ARFT 五样：FROZEN + SCOPE CHECK 进 3.2、FROZEN 进 3.3（动态块）；`plan_check`（Phase 5 后确定性 python，坏则同一席带 findings 重写一次）；Phase 6 spec 席（Opus，只读仓库，Write 限 spec/）+ `spec_check`（文件/脚本存在、forbids 非空、run_cmd/arms 不含 test-half 模式、keep_if 数值化；坏则重写一次）；1v-lite（Phase 1 要求 `evidence_quote`，随后的确定性脚本在全文/摘要里逐字核对并写 `quote_verified`）；跨 run anchor gap 硬去重改为"run i 取第 i 名 gap"（并行安全，不再串行）。新 args：`required_baselines`、`forbidden_patterns`（已写进 ugra-rgbd-t1/args.json）。

**原清单（供对照）：** 哨兵 rc（10/11）→ DONE 核卡（9）→ 席后产物校验（5）→ 精简视图（4）→ 4.1.5 分片（3）→ phase0 manifest（14）→ dblp 熔断（17）→ FROZEN 进 3.2/3.3、plan_check、Phase 6 spec 席 + spec_check、1v-lite、anchor gap 硬去重。

## 9f. 提示词覆盖审计（2026-09-07）：RS 榨干了吗？CCF / ARIS 的评分规则用了多少？

审计依据：`docs/refs/rs/` 117 文件逐个对 `brain.workflow.js` 的引用计数 + SEATS/INLINED/ROUTES 三张表；评分规则以 `docs/prompt-bank/dims-{researchstudio,ccf-aris,paperjury}.md` 的编号为索引。

### 一、RS → Brain

| 类别 | 文件 | Brain 状态 |
|---|---|---|
| 11 个 system prompt | bottleneck_identify / ideate_select / ideate_generate / coherence_trace / critique / refutation_recheck / revise / falsification_reaudit / expand / derive_plain / implementability_audit | 全部逐字内联，各一席（SEATS）；`test_prompts_inlined_verbatim` 做 byte-diff |
| 7 个 reference | ideation-patterns/overview、companion-combos、sub-patterns/overview、anti-patterns、pattern-summary-rubric、intent-recognition、intake-routing | 逐字内联（INLINED） |
| 15 父卡 + 31 子卡 | ideation-patterns/*.md、C00–C30 | 按 RS 设计留盘；席位用 Read 打开导航器 INPUT 点名的那几张（readwrite 席只禁 Bash/Glob/Grep，不禁 Read） |
| 导航器 + 脚本 | run.py、next_step.py、search_*、dedup_merge、pattern_summary、fetch_sections、phase4_skeleton、merge_revisions、extract_user_refs、_time_guard | 由 `run.py next` 的 RUN 行驱动，Brain 原样执行；`.retry_used` / `.bottleneck_retry_used` 两级重试阶梯在 next_step.py 里，Brain 继承 |
| 5 个 validator | subpattern_citation_consistency（2g，next 内联调用）、kill_switch_integrity、expansion_completeness、implementability_completeness、implementability_readability | 经 `run.py validate` 跑；**RS 规定 fail 后只修点名 contract、cap=2，Brain 只记 `validate_rc` 就 render as-is**（§9e 未做项） |
| 未用 · 应该用 | `scripts/regression_check.py`（run_dir 结构回归，exit 0/1；run.py 不调用，RS 自己只在改 prompt 后手动跑） | DONE 后一行 runner 命令；等于免费的第 6 个 validator |
| 未用 · 正确不用 | design-notes.md、regression-directions.md、schemas.md、setup.md、source-routing.md、render_pdf.py（砍）、gen_pipeline / selftest_routing / intent.py | 非运行时输入；RS 的 next_step.py 也不把它们交给任何席 |
| 不在 refs 里的 RS 兄弟 skill | `evaluation/idea_quality`（A 问题位置 / B 方法 / C 问题契合，各 1–5，overall = 100·(A+B+C−3)/12，strong ≥ 67；A ≤ 2 或 C ≤ 2 封顶 borderline；pairwise 盲判、provenance-blind）、`skills/scoop_check`（四轴重叠 → Level 1–5，取最差）、`paper_search` | **RS 自己的两套评分规则，Brain 没有**。idea_quality 的消费者是 rank 席；scoop_check 与 3.1 碰撞 + 3.2 paper_pointed_threat 重叠，不加 |
| RS SKILL.md 主 agent 规则 | 上下文纪律三条（隔离上下文 / 直接 Write 落盘 / 相间 compact）、Phase 3 路由 | 结构性满足：每席独立 agent、只传路径、返回 ≤ 250 词 |

结论：RS 运行时资产已全部接线。缺的是一条 `regression_check.py` 命令和 validate 修复环；RS 自己的评分规则（idea_quality）没进 Brain。

### 二、CCF / ARIS 评分规则 → Brain

| 编号 | 规则 | Brain 现状 | 消费席 | 处置 |
|---|---|---|---|---|
| K1 | idea-reviewer 10 维加权（novelty 14 / soundness 14 / importance 12 …，1–5 分，≤ 3 必带 deduction 块） | 无 | rank | **换入**：rank 席现为自写 3 条权重 |
| K2 | calibration：推荐带 5 档、8 条致命门、multi-idea tournament 6 条、公平规则 7 条 | 无 | rank | **换入**；tournament 第 5 条 = ranking.json 加 backup |
| K5 | 推荐枚举 accept-to-develop / revise / pivot-with-rescue-route / abandon / needs-literature-search | 无 | rank | 换入；与"rank, never kill"一致 |
| K7 | idea-optimizer 六问 + overlap / evidence 两个挑战 | 无 | rank | 六问作 `why` 骨架；两个挑战 3.2 已等价 |
| K4 | strict-idea-review：No-Filler 五字段锚点块、5 条 Score Guardrails | 无 | audit 3.2 | 可选，Brain 附加段（同 SCOPE CHECK 形态） |
| K6 | Coherence Filter 6 布尔 + Fatal Idea Risks 6 布尔 | 部分（SCOPE CHECK 覆盖 contribution type ↔ evidence type） | audit 3.2 | 可选，附加输出字段 |
| K3 | 五角色专家团，独立后综合、不平均致命风险 | 无 | — | **不进 Brain**：五席即新角色；论文阶段 |
| K8 | 发展标签 | 无 | — | 不需要（Brain 不杀） |
| K27–K29 | experiment-designer 三模式、Evidence Principle 七问、venue-family 清单、Minimum Convincing Package、result templates | **已在 P5**（两份逐字内联） | evidence | ✓ |
| K30 | review-output-standards：Output Quality Gate 8 条、两张 scorecard 不得融合 | 无 | 全部席的输出核验 | **第 7 条可脚本化**：TBD / TODO / [fill] / 空标题扫描并入 verifyCmd |
| ccf 硬 H4 | 引用行必须存在；claim 里的数字必须出现在 ±2 行内 | 部分（1v quote check 只查 phase1） | audit 3.2 | **扩到 3.2**：paper_pointed_threat 引句必须命中 fulltext_cache |
| ccf 硬 H2 | card gate：n ≥ 3、mde ≥ 2.8·sd·√(2/n)、band > mde、controls 可失败 | 部分（plan_check：keep_rule 数值化 + 负对照 + baseline 覆盖，无 Lehr 行） | evidence / spec | 可选，plan_check 加 Lehr 行 |
| ARIS ablation-planner | 每条 ablation 带 what_it_tests + expected_if_component_matters；禁 no-op；组件消融优先 | 部分（ablations[{name, removes, predicts}]） | evidence | 可选，evidence_plan.md 加两行 |
| ARIS R2 | 审计判决六枚举，never silent skip | 结构性满足（__PLAN_OK/BAD、__SPEC_OK/BAD、sentinel rc） | — | ✓ |
| ARIS R5 | taste-calibration：评分器先在已知好/坏样本上校准，分不开就修 rubric | 无 | rank | 后续：r1 / r2 / 下次 k=1 的真实结果作校准集 |
| ARIS kill-argument、paperjury 12 陪审、ccf-paper-reviewer | 需要独立席位 | 无 | — | 论文阶段；不进 Brain |

### 三、盯准清单（不加席，按价值 / 成本）

1. rank 席换 CCF 原文：FILES 加 `rubric.md`、`calibration.md`；BANK.rank = K1 + K2 + K5 逐字 + 我们的 ranking.json 形状（加 score_table、backup、recommendation），保留 first_block_to_run 与 never-kill。
2. DONE 后跑 `scripts/regression_check.py <run_dir>`，rc 记入 `runs[].regression_rc`；verifyCmd 加占位符扫描。
3. validate fail 修复环：RS 原规则 cap = 2，只修点名 contract，kill-switch 字段不许"修"。
4. QUOTE_CHECK 扩到 3.2 的 paper_pointed_threat 引句。
5. 3.2 附加段：K4 No-Filler 五字段 + K6 六布尔，注入方式同 SCOPE CHECK。

### 四、落地情况（2026-09-07 晚，GLM 复核后一次做完；mock 4 变体 + pytest 7 项全绿）

零新席。源码搬进仓库：`.research/tools/brain_src/{gen_brain.py, brain.logic.js, prompts/}` 是唯一真源，`test_generator_roundtrip` 保证提交的 workflow 与生成结果逐字节相同。生成文件 372 KB（bank 33 份逐字文件，283 K 字符）。

| 项 | 做法 | 机检 |
|---|---|---|
| 盯准 1 rank 席 | `rubric.md` + `calibration.md` + `strict-idea-review.md` 逐字内联；ranking.json 带 10 维 scores（分/置信/引证）、weighted_score、fatal_gates_triggered、deductions、recommendation（无 abandon）、backup_run；rs-eval/idea_quality 的 provenance-blind 规则一句 | `RANK_CHECK_PY`：复算加权分（权重 12/14/12/14/8/8/10/8/6/8）、≤3 必带 deduction 块、致命门（novelty≤2 高置信 / soundness≤2 封顶 pivot）、推荐带、每 run 一次；BAD → 一次修复 |
| 盯准 2 | DONE 后跑 RS `scripts/regression_check.py <run_dir>`（真实 r1 110 项 / r2 93 项全绿）；`VERIFY_PY` 在 JSON 可读之外扫 TBD / [fill] / [TODO] / PLACEHOLDER（跳过 skeleton / fill_map / derive_map），记为 warn（真实 r1/r2 产物零误报） | `runs[].regression_rc`、`runs[].placeholders` |
| 盯准 3 | validate 单独跑；fail → 按 ✗ 行的 validator 名路由：expansion_completeness / kill_switch_integrity → fill 席修 phase4_expansion.json，implementability_* → impl 席修 phase4_implementability.json，citation 门不修；cap 2；kill-switch 字段只许回源值 | `runs[].validate_repairs / validate_note`；mock `MOCK_VALIDATE_FAIL` 走通 |
| 盯准 4 | 3.2 输出 `paper_pointed_threat.evidence_quote` + `quote_source`（title-only 命中可引标题）；`QUOTE_CHECK_PY` 双模式，在 verify 与 next 同一 runner 调用里跑，命中 abstract / fulltext / lit_table / collision_hits 即 `quote_verified` | `runs[].quote_check3`（真实 r1 威胁论文标题 → 1/1） |
| 盯准 5 | 3.2 加 REVIEW DISCIPLINE：No-Filler 五字段进 verdict_rationale / revision_targets；输出加 `ccf_coherence_filter`（六布尔）与 `fatal_idea_risks`；`strict-idea-review.md` + `problem-method-blueprint.md` 逐字内联 | 提示词级（RS 校验器不管额外字段） |
| B · Lehr | evidence_plan 块加 `seed_sd` / `min_effect`；`plan_check` 检 min_effect ≥ 2.8·sd·√(2/seeds) | 旧 r1/r2 计划按新规则 BAD（预期） |
| B · ablation | ablations 改 ARIS 字段（what_it_tests / expected_if_component_matters / priority / config_only）+ 禁 no-op、组件先于超参；`ablation-planner/SKILL.md` 逐字进 P5 | `plan_check` 检字段 |
| B · storyline（GLM 二审补） | evidence_plan 按 ARIS experiment-plan 原文：claim_map[].primary（MAX_PRIMARY_CLAIMS=2）、blocks[].role 五选一（anchor / novelty_isolation / simplicity / frontier_necessity / failure_analysis）+ placement + failure_interpretation、skipped_roles 显式说明、minimum_convincing_package ≤ 5（MAX_CORE_BLOCKS）、基线族过多告警（MAX_BASELINE_FAMILIES=3） | `plan_check` 机检；旧 r2 计划按新规则报 18 条（预期） |
| 测试 | `test_prompts_inlined_verbatim` 改为对 bank 全部 33 条逐字节比对源文件（RS 11 提示词 + 7 reference + CCF/ARIS 12 份 + Brain 3 份），refs 一改即失败 | pytest 7 项 |
| C-1 Astra | 不建独立席：`aris/formula-derivation/SKILL.md` 逐字进 4b fill 席 + KEY EQUATIONS DISCIPLINE（不变量对象 / 假设 / 四类步骤标签 / 失效条件 → Phase 6 tests_premise 取材） | — |
| C-2 intake | `idea-intake.md`、`compute-env-contract.md`、`evidence-precheck.md` 逐字进 intake 席；substrate.md 算力信封按 env-spec、seed_sd 带来源行、数字必带 file:line、limitation 遵守 idea-intake 硬规则 | — |
| C-3 | 不做：`aris/specification-writing` 是专利说明书 skill，INDEX 第 48 行取材有误，已改 | — |
| C-4 | idea_quality 整目录搬进 `docs/refs/rs-eval/`（MANIFEST 已补）；只取其盲判规则，评分表用 CCF K1（两套评分 = 噪声） | — |
| D · dblp | run.py `check_connector` 认 `IDEASPARK_SKIP_SOURCES`；Brain 在 Phase 0 日志里查到 `[dblp…] timed out` 即给后续所有检索加 `IDEASPARK_SKIP_SOURCES=dblp` | mock `MOCK_DBLP_TIMEOUT` 走通 |
| D · OpenReview 凭据 | 未做：需要 owner 的账号进 `.env` | — |

仍未做（§9e 尾巴）：compact input views（fill / derive / evidence 大输入）、4.1.5 输出分片。

### 五、最后一滴（2026-09-07 深夜，按四个正交面各挤一次；零新席、模型不动；生成 429 KB，bank 41 份）

| 面 | 进哪 | 逐字引用 | 提示词行 | 机检 |
|---|---|---|---|---|
| CCF（关系图，ARFT B.5） | Phase 1 | `literature-grounded-evolution.md` | closest_adjacent 每条加 `relation`（supports / conflicts-with / leaves-open / depends-on / evaluated-by）+ `relation_evidence`；只有 leaves-open 的残差是缺席声明不是证据 | `QUOTE_CHECK` p1 报 `relations n/m valid` |
| ARFT（失败码表） | 3.2 | `papers/arft_guide.md`（agent-as-a-judge 原文，17 KB，已入 refs + MANIFEST） | 每条 blocking finding / revision_target 带 `arft_code`（A.1–A.6、X.2 / X.5 / X.6；§3 判别簇、§4 Do-NOT-label） | 码随失败卡进 Worker |
| CCF（评审会） | rank | `expert-panel.md`、`review-output-standards.md`、`venue-idea-adapters.md`、`literature-grounded-evolution.md` | 打分前先写五角色 per-reviewer 块 + Panel synthesis（不平均掉致命风险）；venue_fit 按 venue family；`why` 答六问；写前跑 Output Quality Gate | `rank_check`：panel < 5 条 → BAD |
| ASI（交接契约） | Phase 6 | `task-exemplar/task.yaml`、`prompt_b1.md`、`guide/how-scoring-works.md` | spec 加 `gates[]`（file_exists / no_nan_inf / forbidden_import / forbidden_pattern / key_present，硬、结构、脚本可查，永不是科学检查）；B1 完整度以范例为准；"self-reported scores are never trusted" | `spec_check`：gates 枚举、forbids 必有对应门、每个 output 缺 file_exists 门告警 |
| RS / ARIS | — | 无新增：RS 运行时资产已全接；ARIS 在 Brain 内的 2.5 样（experiment-plan / ablation-planner / formula-derivation）已在第四节 | kill-argument 留 paper 阶段 |

静态块最大 ideate 75 KB、audit 54 KB、rank 40 KB，均一次构建、跨调用同前缀（prompt cache）。

## 9g. Brain 最终席位配置表（由 workflow 的 SEATS 表生成，2026-09-07）

模型路由：Opus = 作者 + 2.3 干跑（新上下文，回退 GLM），GLM = 工程，K3 = 对抗审计，Sol（gpt-5.6-sol）= 3.2 的并行第二审稿人（K3 裁决；Sol 可迫使 revise 并追加 revision_targets，单独不能 abandon，`args.second_auditor_kills` 可改）；Phase 5 / Phase 6 = Opus（回退 GLM）；`args.seat_models` 可临时把任一席挪到别的模型（额度是当天的事实，不是设计）；claude-kimi 会话启动（官方 API 下 GLM/K3/Sol id 会被静默替换成会话模型）。runner = GLM / low。

| 席位 | 步 | 模型 / effort | 工具类 | 逐字提示词 | 逐字引用 | 静态块 KB |
|---|---|---|---|---|---|---|
| phase1 | Phase 1 瓶颈 | Opus / high | readwrite | bottleneck_identify.txt | literature-grounded-evolution.md | 34 |
| ideate | 2.1+2.2 选 gap + 生成 | Opus / high | readwrite | ideate_select.txt, ideate_generate.txt | overview.md, companion-combos.md, overview.md | 75 |
| generate | 2.2 重生成 | Opus / high | readwrite | ideate_generate.txt | overview.md | 32 |
| cite_fix | 2g 引用修正 | Opus / medium | readwrite | — | overview.md | 5 |
| coherence | 2.3 连贯干跑 = 推导 | Opus / high（回退 GLM） | exec | coherence_trace.txt | — | 17 |
| audit | 3.2 审计 | K3 / high ∥ Sol gpt-5.6-sol / high（第二审稿人，AUDIT_MERGE_PY 合并） | readwrite | critique.txt | anti-patterns.md, strict-idea-review.md, problem-method-blueprint.md, arft_guide.md | 54 |
| recheck | 3.2b 复核 | K3 / medium | readwrite | refutation_recheck.txt | — | 5 |
| revise | 3.3 补丁 | Opus / high | readwrite | revise.txt | — | 14 |
| reaudit | 3.3b 证伪复审 | K3 / medium | readwrite | falsification_reaudit.txt | — | 6 |
| fill | 4b 填充 | Opus / high | readwrite | expand.txt | SKILL.md | 25 |
| derive | 4.derive 通俗推导 | GLM / low | readwrite | derive_plain.txt | — | 7 |
| impl | 4.1.5 可实现性 | GLM / medium | readwrite | implementability_audit.txt | — | 14 |
| terms | signature terms | GLM / low | readwrite | — | intent-recognition.md | 8 |
| writeup | do_not_generate / failed 写单 | GLM / low | readwrite | — | — | 2 |
| tagging | Phase 0 打标 | GLM / low | readwrite | tagging_shard.md | pattern-summary-rubric.md, overview.md | 24 |
| intake | Phase −1 仓库 intake | GLM / medium | repo | intake.md | intake-routing.md, intent-recognition.md, idea-intake.md, compute-env-contract.md, evidence-precheck.md | 31 |
| evidence | Phase 5 证据合同 | Opus / high（回退 GLM） | readwrite | evidence_plan.md | evidence-design.md, result-templates.md, SKILL.md, SKILL.md | 28 |
| rank | Rank | Opus / high | readwrite | rank.md | rubric.md, calibration.md, strict-idea-review.md, expert-panel.md, review-output-standards.md, venue-idea-adapters.md, literature-grounded-evolution.md | 40 |
| spec | Phase 6 B1 spec | Opus / high（回退 GLM） | spec | spec.md | task.yaml, prompt_b1.md, how-scoring-works.md | 22 |

## 10. 未决

- Phase 5 用 Opus 还是 GLM（先 GLM，K3 对契约再审一次可选）。
- Astra 通过 playwright 自动还是 owner 手工贴（先手工）。**2026-09-07 晚：推导纪律已按 ARIS formula-derivation 进 4b fill 席（同族）；跨族 Astra 推导席仍未建，建与不建是 owner 的决定。** **2026-09-07 深夜已决：不建独立席（再加一席 = 再加一跳）。Astra 以换模型的方式进 2.3——2.3 本就是推导席（T1 形式化 / T2 执行干跑 / T4 定级 / T5 naive），且在 3.2/3.3 修复环之前；gpt-6-astra 经 LiteLLM :4001，失败时同一席回退 Opus（`SEATS.coherence.fallback`，mock 变体 MOCK_ASTRA_FAIL）。每 run 串行 LLM 席仍为 12（intake → tagging → phase1 → ideate → coherence → audit → fill → derive → impl → evidence → spec → rank；revise 路径 +3），CCF/ARIS 两轮加的是引用与脚本检查，0 席。**
- Phase −1 对无 anomalies 的新仓库是否补一轮诊断探针（先不做，退化为原版 RS）。
- **失败卡回流（2026-09-07 深夜已接线）**：`args.negative_anchors`（实验侧 `failures/X-*.json`）只作为三席的上下文行进 Brain——Phase 1（实测事实，failure_interpretation 进 residue）、2.1+2.2（硬否决）、3.2（硬底线 abandon）；零新席、零新提示词文件。实验侧 `retrigger.py` 建 `<root>-n<round>` 并填此参数（worker 设计 §13.3）。
- **Astra 额度（2026-09-07 更晚，owner）**：t1 第二次跑在 2.3 上三次 Astra 尝试各 20–26 分钟后额度耗尽；额度耗尽表现为 API 层无限重试，agent() 不返回，席位的 fallback 永远轮不到。决定：2.3 回 Opus（新上下文 ≠ 2.2 作者上下文；回退 GLM）；Sol（gpt-5.6-sol，同一 Codex OAuth 池）只放两个一次调用的形式席——Phase 5 证据合同、Phase 6 B1 spec（V8 就把 falsifier 和 spec 给 Sol），回退 Opus；新增 `args.seat_models` 覆盖，额度变化不用重生成。
- **再改（2026-09-07 更晚，owner）**：Phase 5 / 6 回 Opus（回退 GLM）。Sol 放到 3.2 当**并行第二审稿人**：同一 critique 提示词、同一输入、自己的上下文，写 `phase3_critique/second_opinion.json`；`AUDIT_MERGE_PY`（确定性）合并进 K3 的文件——K3 abandon 即 abandon；K3 advance + Sol revise/abandon → revise 并追加 Sol 的 revision_targets（按 scope+field 去重，标 source=second_auditor）；两票都 advance 才 advance；Sol 单独不能杀（"a challenge flags, never kills"），`args.second_auditor_kills=true` 才允许。并行，不加串行跳；Sol 每 run 1 次。owner 原话："sol 实在不行就审查吧"。

## 11. 下一步

1. 写 Phase −1 intake 提示词：RS 10 个 intake 字段逐个对应到仓库可读之物 + substrate 事实清单。
2. 用当前仓库跑原版 RS 到 Phase 1，对照 anomalies.md 看 gap 是否命中。
3. 搬资产（§8），写 `skills/brain/` 的导航循环。

## 9h. 代码复审修的七处（2026-09-07 深夜；30 项测试全绿）

| # | 问题 | 修法 |
|---|---|---|
| 1 | 长任务（phase0 / fulltext / collision）在席位重试或续跑时会被第二次 launch 到同一个输出文件 | `launchCmd`：pid 仍活着就复用（echo LAUNCHED），不重发 |
| 2 | r2..rK 复制 r1 的 Phase 1 用 `cp -r r1/phase1 rd/`——目标目录已存在时会嵌套成 `rd/phase1/phase1`，导航器看不到产物 → 循环到 MAX_STEPS | `rm -rf rd/phase1 && cp -r r1/phase1 rd/phase1` |
| 3 | Phase 1 在席位返回的瞬间就对 r2..rK 开放，此时产物还没过可读性校验；r1 若重试，r2 已复制了坏文件 | `phase1Ok` 挂在 lastSeat 上，verify 通过后才 `markPhase1(true)` |
| 4 | 2.3 上一次未完成的尝试留下的 `blocking_findings.json` / `refined_candidate.json` 会被新一次 2.3 之后的 3.2 当成本次证据（t1 根上就有 Astra 留下的） | 跑 2.3 前 `rm -f` 这两个副产物 |
| 5 | Phase 5 / 6 / rank / validate-repair 席不记 model 与 fallback | 统一 `rec()`，`result.runs[].fallbacks` 覆盖全部席 |
| 6 | 续跑时 Phase 5 / 6 / rank 无条件重跑，覆盖已通过检查的好文件（与"已经发射过的不重做"矛盾） | 先跑 plan_check / spec_check / rank_check：通过 → 保留并跳过席；有 findings → 作为修复席的输入；文件不存在 → 新写。mock 变体 `MOCK_KEEP_PLAN` |
| 7 | meta.phases 文案仍写 2.3=GLM、Phase 5/6=Opus 无回退 | 改为现状 |

复审确认无误的：runner 退出哨兵、emit 解析取最后一块、validate 修复帽 2、collision 与 2.3 并行、STAGGER 轮转、ideateTurn 在失败路径也释放、AUDIT_MERGE 只改 verdict/revision_targets、quote 检查在合并之后运行。

## 9i. ccf 第一次全程（phyagentos，2026-09-07）的轨迹审计与修复

轨迹（wf_e3fb64，53 个 agent，席位合计 329 分钟）逐条核对 `agent-*.jsonl` 后的事实：

| 事实 | 数据 | 修法 |
|---|---|---|
| **每个 agent 都以 effort=max 运行**——席位表写的 high/low 没有生效（jsonl 每条记录 `effort: max`；runner 也是 max） | 2.1+2.2 45 min / 34 万思考 token；2.3 两次各 20–24 min；Phase 6 53 min + 修复 50 min（27 万思考 token） | 根因是启动器：`~/bin/claude-kimi` 默认 `CLAUDE_CODE_EFFORT_LEVEL=max`、settings.json 同。改为 high（要 max 时 `CLAUDE_CODE_EFFORT_LEVEL=max claude-kimi`）。Workflow 的 per-agent effort 在 2.1.258 下不生效，已记入记忆 |
| Sol 第二审稿人 7 次串行崩溃，每次 4 min，`<synthetic>: Prompt is too long`——它把 phase0 的 lit_table / 全文都读进上下文 | 28 min，最后 K3 单独裁决 | 第二审稿人只给紧凑输入（不含 phase0 语料文件，上下文行保留），且不重试（`{retry:false}`） |
| Phase 6 席用 Glob 18 + Grep 21 + Read 35 自己爬仓库；spec_check 因引用尚不存在的网关文件而 BAD；修复提示词写的是"整文件重写"→ 又爬一遍 | 53 + 50 min | 运行前由 runner 生成 `spec/repo_map.txt` 作为输入；块自己创建的文件写 `function: NEW file`（spec_check 放行）；所有修复提示词改为 PATCH（只改点名项） |
| 2.3 跑了两次 | 44 min | 不是 bug：两次都是 owner 中断（`[Request interrupted by user]`）后重发 |
| 第一腿死于 2.3 的 merge 形状错误（patch 的 append_items 是 str），导航器重发同一条死命令 | 1h50m | 通用自愈：消费席位产物的确定性步骤失败一次 → 把失败原文喂回该席修一次 → 同一步骤再跑（cap 1；mock 变体 `MOCK_BASH_FAIL`） |
| `brain_done(k=1)` 只看 spec/index.json，Brain 还在修复时导航器就切进 EXPERIMENT | 作废 1 次 precheck | Brain 结束写 `brain.done.json`；导航器先看新鲜锁：锁在、无 done 标记 → WAIT |
| Grok 1.0.13 `--output-format json` 的 text 里是 5 份拼接的 JSON（前 4 份 findings 空，最后一份完整） | critic 两连败 → BLOCKED | `parse_findings` 拆分拼接文档，取最后一份有 findings 的；用那份原始输出做金标测试 |

未变的：K3 审计 10–12 min、GLM 4.1.5 21 min（9.3 万 token 输出，无思考）属于模型侧成本。

## 9j. 第二审稿人精简视图 + Phase 6 三刀（2026-09-07 深夜；32 项测试全绿）

**Sol 第二审稿人**（`SEATS.audit_second`，与 K3 并行，不加跳）：
- 唯一输入 = 确定性脚本 `SECOND_PACKET_PY` 生成的 `phase3_critique/second_auditor_packet.md`：候选（2.3 精炼版优先，≤60 KB）、2.1 选择（gaps + composition）、2.3 执行过的 blocking findings、碰撞命中按 relevance_score 取 top-20（摘要截 600 字）。不给 lit_table / lit_results / 全文。
- 静态块只留 RS critique.txt + anti-patterns（砍掉 strict_review / blueprint / ARFT 三份，54 KB → 约 25 KB）；上下文行保留 SCOPE CHECK / THREAT QUOTE（引句只能来自包里的碰撞摘要）/ NEGATIVE ANCHORS / FROZEN。
- 工具只剩 Read（那一个包）+ Write（那一个输出）；不重试（失败即 K3 单独裁决）。
- 融合旋钮不变：K3 裁决，Sol 可迫使 revise 并追加 targets，`args.second_auditor_kills` 才能杀。

**Phase 6 三刀**（结构不动）：substrate 是事实源、REPOSITORY MAP 定位、Read 只用来确认将要点名的函数/行，禁止 Glob/Grep 探索；修复 = 只改点名项（PATCH）；effort medium。第四刀（只写 B1 + index，后续块按需补写）留待 Brain 重入机制设计后再做。

**位置戳**：每个席位提示词带 `SEAT #n of this run`——`resumeFromRunId` 的缓存按 prompt 回放，RS 重试周期复用同一批路径，没有它会回放已归档的裁决（ccf 19:05 那次）。

## 9k. Phase 6 下放 + 审计席读取上限（2026-09-07 深夜；33 项测试全绿）

owner 判决："Phase 6 做了太多不该做的事；RS + ARIS 足够，CCF 顶多是提示词加强；下放。"

- **Brain 到 Phase 5 为止**（cards + evidence_plan + plan_check）。spec 席、SPEC_CHECK_PY、ASI 三份引用、BANK.spec 全部离开 Brain；Opus 每 idea 省 50–105 分钟；Brain 的完成标记 = `brain.done.json`，k=1 的 brain_done 看 `phase5/evidence_plan.json`。
- **实验侧新步 `exp-spec`**（Worker = GLM 主窗口）：`spec_packet.py` 生成单块起草包（计划的本块条目 + 映射的 claims + kill_conditions/frozen_untouched + method_view + 可实现性点 + substrate + intake + FROZEN + 仓库地图），按 **原 Phase 6 提示词逐字**（`.research/tools/exp/refs/spec_contract.md`）写 `spec/B<k>.json`，`spec_check.py --plan` 把关。一次一块（懒出块自然成立）。
- **PLAN ⊆ SPEC**（`spec_check.py` 新增，确定性）：keep_if_all 的数字只能来自本块 keep_rule；kill_condition 是计划里的一条；forbids 覆盖 frozen_untouched；负对照臂对应计划的负对照。Worker 只补工程，科学决定动不了（ARFT R3）。之后照旧 `/exp-next` 封印 + `/exp-critic spec`（Grok 跨族审）。
- **审计席读取上限**：K3 的输入 = 原 emit 输入去掉 phase0 语料 + `lit_table_slice.md`（碰撞命中论文的行）+ 紧凑包；READ BUDGET 行禁止读列表之外的文件、禁止重复读。Sol 只有包（见 §9j）。
- CCF 引用保留（rank / P5 / 3.2 的 strict_review 等），实测它们不花墙钟；砍不砍是内容判断，不是时间判断。

## 9l. Codex 轨迹审计的结论与三处补修（2026-09-07 深夜；35 项测试全绿）

Codex 逐条读了两腿 89 个 agent 的记录（全文：`2026-09-07-brain-ccf-trajectory-audit-codex.md`）。与 §9i 一致的部分不重复；它多抓到的三条及修法：

| Codex 发现 | 修法 |
|---|---|
| **19:05 的 resume 不只回放了 K3 的裁决，连 `run.py next` 的 runner 结果也被回放**（同一条命令文本），于是 3.2 在一个 2.3 从未完成的候选上跑了——最终那张卡从未过连贯门 | runner 提示词加 `CALL #n`（与席位的 `SEAT #n` 同理）；3.2 前加**门不变量**：`phase2_coherence_output.json` 不存在就抛错，永不从原始 2.2 审计 |
| Phase 6 两席 169 次工具调用、写了 77 万字符（B3–B6 各写三遍）；spec_check 拒的是"块自己要创建的文件不存在" | Phase 6 已整体下放（§9k）；`function: NEW file` 规则进 spec_check |
| RS 的 abandon → 整个 Phase 2 重来，而那次审计只否定了机制，没否定 gap；建议给裁决加 `retry_scope`（mechanism_only 只重跑 2.2） | 未做（改 RS 的 next_step.py 策略，需 owner 决定）；记为后续第 1 项 |
| runner 开销 10 分钟/腿（3%），不是主因 | 不动 |
| 不该动的：2.3 独立上下文、确定性校验、K3 主判 | 保持 |

**L2 回流环（同时补上）**：ccf 的 X-001 spec 审出 L2（4×A.6 + A.2：spec 留了科学决定），旧梯子把它当"idea 死了"去重触发新根——错。现在 L2 的正确回路：`failure_card.py` 写 `phase5/plan_findings.json` 并把起草的 spec 退役（`B1.L2-<X>.json`）→ 导航器给 **plan repair**（同根重发 Brain，只有 Phase 5 的 plan_check 看到 findings 比计划新而进修复席）→ 计划比卡新之后该块重新可领 → `/exp-spec` 按修好的计划重写 spec。只有非 L2 的死亡才走 backup → retrigger。
