# V9 Worker：GLM 写、Grok 审、脚本判——实验侧一比一复刻 Methodology

2026-09-07。取代 `2026-09-06-v9-brain-worker-design.md` 的 Worker 部分（那一版是 dag 总线 + 多席，已被 owner 判死并归档）。Brain 部分见 `2026-09-06-v9-brain-rs-architecture.md` §9b（已跑通一次，两张卡）。

## 0. 一句话

一个 `claude-kimi` 会话：主窗口是 GLM，只写代码、只跑仪器；设计全部由 `brain.workflow.js` 在后台独立上下文里做；判决分两层——数值门是脚本，过程审计是 Grok（`grok:rescue` 插件 agent 调 grok cli，只读 run 目录，带锚点）。没有 dag，没有子代理，没有实验侧 workflow。人只在判断环：改 FROZEN、写"不对"、批护栏。

## 1. 与 Methodology 五层的一比一对应

| 层 | Methodology 原句 | 本设计的构件（不是比喻，是文件） |
|---|---|---|
| L0 北极星 | "目标必须能被机器判定""没达标不许停" | `GOAL.md ## FROZEN` 的 keep rule 逐字进 `spec.verdict_rule.keep_if_all`；`verdict.py` 只认这个字段；FROZEN "Exit: None for failure" 意味着 killed 只能 route，不能结题 |
| L1 标杆 | "凡异常先查标杆""三源互证""一切锚到源码行号" | 三源：`substrate.md`（Brain intake 从代码抽的事实，带 file:line）/ `instruments/README.md`（仪器契约、canary 数字）/ `experiments/X-*.json` 台账（历史实测）。spec 里每个"改哪里"必须带 file:line；Grok 的每条 finding 必须带锚点，`anchor_check.py` 核验存在性 |
| L2 裁判 | "自建验收仪，且裁判也要被验证""双绿假阳性""金标回归门" | 验收仪 = `m157/m158` + `verdict.py`（Type-A，脚本）；裁判 = Grok（Type-B，换族）；**裁判验证** = Grok 上线前先审金标语料 `tests/golden/X-*.json`（X-005…X-016 的已知结论：canary_fail / L0 bug / 真 kill / gate_passed），对已知坏样本给 survived 或对已知好样本给 killed 即裁判失效；回归门 = `.research/tests/`（mock + golden）任何共享面改动后必跑 |
| L3 军团 | "一域一会话""结构化跨会话记忆""交接仪式""撞车协调" | 一域一会话：Brain 域 = workflow（每席独立上下文），基质域 = 主窗口（长期持有仓库/trainer/当前 X）；记忆 = `memory/worker/*.md`（frontmatter：type / hook / owner）+ `INDEX.md`；交接 = 主窗口 >400k 或 X 终态时写 `handoff-<date>-<X>.md`（六节，先 `git status` 再写）然后开新会话，不 compact；撞车 = 一 X 一 worktree，禁区 `instruments/`、受保护 eval、`substrate.json` |
| L4 治理 | "每次事故一个防再犯工件""三态近似审计""一切落盘" | 事故 → `anomalies.md` 一条 + `.research/tests/` 一个测试；三态审计 = `spec.deviation_notes[]`（✅一致 / 📋登记带理由 / ❌回炉），无登记的近似 = Grok 的 C.3 blocking；落盘 = `build/X-*/`、`experiments/X-*.json`、`findings/X-*.json`、`memory/`，聊天不是档案 |

## 2. 已敲定的决策

| # | 决策 | 依据 |
|---|---|---|
| D1 | 实验侧不用 Workflow，不用子代理；主窗口 GLM 连续上下文 | owner 2026-09-07；X-016 91 min 中 45 min 是每席重付仓库冷启动 |
| D2 | dag 整体删除；只留三个纯函数脚本 | reader 盘点：`keep_if_all`、negctl→L3 在 JS 里，canary 是 `substrate.json` 的纯函数；其余是无状态 Workflow 壳的补偿 |
| D3 | 设计全在 Brain，**不加新席**：Phase 5 的 evidence_plan 已是 B1 级（arms 带 file:line、canary、seed、baseline 的 config 与 ckpt 路径、keep_rule 含绑定审计），只在同一席的提示词里加结构化字段 `spec`（edits[]/run_cmd/smoke_cmd/eval_type/keep_if_all 或 scorer），并要求对 implementability 的每个 open hole 做出选择或把依赖它的 block 标 `blocked_on` | 2026-09-07 盘点 r1 产物；ASI-Bench：B1→B2 −21.8，操作化是瓶颈；GLM B1 63.05 / B2 35.45 |
| D4 | 判决族 = Grok，经 `grok:rescue` 插件 agent 调 grok cli；不是 workflow，不是我们的子代理 | owner 2026-09-07；ARIS acceptance-gate："loop 可以 DRIVE，不能 ACQUIT"，Type-B 必须换族 |
| D5 | 数值门先于 Grok：`verdict.py` 算 exit 码三分、keep_if_all、negctl→L3、too_good；Grok 只审过程，不重算数字 | ARIS result-to-claim 的 evidence_check 预检；Methodology "裁判互证" |
| D6 | 判决由脚本从 findings 算，Grok 不自评 survived | ARIS kill-argument："Verdict is computed by the skill, not by the adjudicator" |
| D7 | launch 是脚本，0 token；换进程跑 3 条零容忍 grep | V8 D7；ARFT R3 "verification the agent does not control" |
| D8 | Brain 对 `ugra-rgbd-robust/` 只读，用 `disallowedTools` / `bashCommandClamp` 物理禁写；主窗口只在 worktree 里 Edit | 2026-09-06 提示词式禁用被席无视（席照样用了 sed/Edit） |
| D9 | killed L2–L4 不修，把失败卡作为负锚重触发 Brain；L0/L1 原地修，帽 2+1 | V8 `_route_judged`；RS retry 模式本来就吃负锚 |
| D10 | 实验侧只用 ARIS；CCF 只在 Brain Phase 5（已内联）和论文阶段 | §6 |

## 3. 三方的输入与输出

### Brain（`brain.workflow.js`，已有；Phase 5 提示词加 `spec` 字段）

| | |
|---|---|
| 输入 | `args`：root、repo（只读）、dataset、venue、FROZEN 全文、anomalies.md、K；重触发时加 `negative_anchors: [failures/X-*.md]` |
| 输出 | 每 run：`phase4/idea.detail.en.md`（+std zh/en、PDF）、`method_view.json`（S1–S12 步骤 + key_equations）、`phase4_implementability.json`（实现级细节 + open holes）、`phase5/evidence_plan.json`（blocks 内含 **`spec` 结构化字段**，见下）；根：`ranking.json` |
| 不做 | 不写仓库；唯一的代码是 2.3 的 `t2_dryrun.py`（标准库草稿，留在 run 目录） |

每个 block 的 `spec` 字段（B1 级，取自 V8 PREREG/METHOD_COMPLETE 合同 + ASI-Bench B1 范式；Worker 从 evidence_plan 直接取，不再翻译）：`block_id, claim_id, mechanism(文本), edits[{file, symbol, lines, what}], new_files[], tensors[{name, shape, dtype, where}], run_cmd, smoke_cmd, arms[{name, what_changes, eval_type}], verdict_rule{arms, keep_if_all}, negctl_arm, forbids[], seeds, gpu_h_cap, deviation_notes[], dual_reading_pins[]`。地板脚本 `spec_floor.py`：`outcome_metric` 逐字等于 FROZEN 行；候选 arm 的 `eval_type ∉ {synthetic_proxy, simulation_only}`；`keep_if_all` 非空；`forbids` 非空；每个 `edits[].file` 存在且 `lines` 范围内含 `symbol`。

### Worker（主窗口，GLM）

| | |
|---|---|
| 输入 | `ranking.json` 第一名的 `evidence_plan.json`（含每个 block 的 `spec`）+ `phase4_implementability.json` + `method_view.json` + `idea.detail.en.md`；`_shared/substrate.md`；`GOAL.md`；`instruments/README.md`；spec 点名的仓库文件。读单在 `skills/worker/build.md` STEP-0 |
| 输出 | worktree（`/tmp/wt-X-*`）diff；`build/X-*/{spec.json, progress.md, self_check.json, blockers.json, smoke/}`；systemd unit + `ledger.jsonl`；`results/`（m157/m158 产物）；`verdict.json`；`experiments/X-*.json`；killed 时 `failures/X-*.md`（失败卡） |
| 不做 | 不改 spec 的科学决定（留空即 spec 缺陷，回 Brain）；不碰 `instruments/`、受保护 eval、`substrate.json`；不读 test half；不选 seed；不自判 survived；不读 `.research/` 读单之外的东西 |

### Grok（`grok:rescue`，只读）

| | |
|---|---|
| 输入 | 只给路径：`spec.json`、`diff.patch`、`results/`、`verdict.json`、`progress.md`、`smoke.log` 尾、launch 日志、`self_check.json`、`blockers.json`。不给 Worker 的总结 |
| 输出 | `findings/X-*.json`：`[{anchor, class: <ARFT 码>, blocking: bool, note}]` + `probe_self_proof{ckpt_loaded_fraction, canary_pass}`；`anchor_check.py` 核验锚点、算 `survived|killed` 与 `failure_level L0–L4` |

## 4. Worker 内循环（每个 X）

1. **领取**：读 `ranking.json` → 第一名 run → `run_order[0]`；`X-<n>` 编号；`build/X-n/` + worktree（`git worktree add`，`repos/*` 符号链接照 `launcher_reference.sh`）；把该 block 的 `spec` 抄成 `build/X-n/spec.json`，`spec_floor.py` 不过门或 block 带 `blocked_on` 则回 Brain，一行代码不写。
2. **实现（GLM）**：只读 spec 点名的文件；增量 commit；`progress.md` 追加式记录"测了什么、故意没测什么、坏了什么"（ARFT F.2）；中途死亡写 `wip:` commit 标未验证部分。
3. **smoke**：`smoke_cmd`，产物只落 `smoke/` 且文件名带 `NOT_A_RESULT`；SELF_CHECK 7 条 grep（V8 原文）写 `self_check.json`；自审发现写 `blockers.json`，空列表即宣称没找到。任何 `blockers` 未清 → 不许 launch（F.4 的第一道线）。
4. **launch（脚本 `launch.sh`）**：换进程跑 3 条零容忍 grep（碰 test half / 改 eval_entry / GT 逃逸）→ `nvidia-smi` 预检（ARIS：free = used < 500 MiB）→ `launch_wrap.sh` 带 canary 旗（从 `substrate.json` 算）→ `systemd-run` → `tee` 日志 → 记 `ledger.jsonl`。
5. **等待**：Monitor 盯 unit；ETA 只封顶（`gpu_h_cap`），到顶 = early-kill exit 4；不按 ETA 等。
6. **判决一（脚本 `verdict.py`）**：exit 5 → infra，3 → canary_fail，4 → early_kill（都不是科学判决，`Infra ≠ verdict`）；m158 键逐字 → `keep_if_all`；negctl 匹配（`|negctrl_delta − delta| < |delta|/2`）→ L3；`too_good`（delta > 3× 历史最大）→ 不许 survived；写 `verdict.json`。
7. **判决二（Grok）**：`grok:rescue` 收路径清单 + `skills/critic.md`；四查：C.3 实现≠spec（逐条 `edits[]` 对 diff）、C.1 循环验证/碰 test half/选 seed、arm 隔离（三条链只差一个变量）、F.4 自审未改（`blockers.json`/`progress.md` 里写了却没改）；外加探针自证（checkpoint 加载张量比例 ≥90%、canary 复现）。`anchor_check.py`：锚点不存在 → 降 advisory；有一条 blocking 且锚点成立 → killed；崩溃/超时 → 待重判，永不 survived。
8. **路由**：L0/L1 原地修（帽 2 次 fix + 1 次重实现）；L2 → 写失败卡回 Brain 出新 spec；L3/L4 → 失败卡作负锚重触发 Brain（换 ranking 下一名或重跑 ideate）；survived → `run_order` 下一个 block；全部 block 过 → `supported`，写 E[]（数字从 `verdict.json` 回溯）。
9. **记忆**：这轮的 pitfall / finding 各一文件进 `memory/worker/`；X 终态或 >400k → 交接仪式。

## 5. 判决细则（L0–L4 闭集，V8 判决书原文）

| 级 | 含义 | 由谁判 | 去向 |
|---|---|---|---|
| infra / canary / early-kill | 跑挂、主干没复现、超预算 | `verdict.py`（exit 码） | 重试或 invalid，永不 refuted |
| L0 | 代码 bug（实现≠spec，可定位到行） | Grok C.3 | 原地修 |
| L1 | 训练配置错（seed/优化器/数据，spec 说清了但没照做） | Grok C.3 / C.1 | 原地修 |
| L2 | spec 本身缺东西（科学决定留白） | Grok + `spec_floor.py` | 回 Brain 出新 spec |
| L3 | 机制不成立：负对照命中或 keep_if_all 不过且过程无误 | `verdict.py` negctl 规则 | 负锚回 Brain，换候选 |
| L4 | 前提错：A.5 度量错配 / A.6 假设-实验错配 / D.4 方法-结论脱节（闭集） | Grok，只许这三码 | 负锚回 Brain，两次独立 L4 = refuted |

"证据缺失但假设合理"是 L2，永远不是 L4。

## 5b. Brain 产物 → Worker 需求（复用表，2026-09-07 盘点 r1）

| Worker 需要 | Brain 已有（文件.字段） | 缺什么 |
|---|---|---|
| 机制与步骤 | `method_view.method_flow.steps[S1..S12]`（what_changes / why / linked_component / linked_falsification）+ `key_equations` | 无 |
| 实现级细节（层、初始化、优化器组、精度） | `phase4_implementability.enriched_steps[].what_changes` | 无；`underspecified_points`（r1：S7 AdditiveGate 输入与位置、S10 无头站点的 A_disp）必须在 Phase 5 做出选择或标 blocked |
| 每个 block 的臂、预期方向、负对照 | `evidence_plan.blocks[].arms[] / negative_control / expected_direction` | `eval_type` 标签 |
| 改哪个文件哪个符号 | 散在 arms.what_changes 与 steps 的 prose（`DFormerv2.py:330-339` 等） | 结构化 `edits[{file,symbol,lines}]` |
| 命令 | prose 里点名 `arbor_eval.py --split dev`、`eval_robust_suite.py` | 完整 `run_cmd` / `smoke_cmd`（含环境变量、launcher） |
| 判决规则 | `blocks[].keep_rule`（含绑定审计：CI 半宽 ≥ 最大效应即无法判） | m158 块要 `keep_if_all` 的键形式；B1 这类前向分布测试要 `scorer` 规格（阈值：drop_r > spread_clean、|rho| ≥ 0.10、permuted ≤ 0.02、headroom > 0.59/2.13/10.10 + 0.5） |
| 基线与 ckpt | `blocks[].baselines`（config 名 + 路径） | 无 |
| 禁区 | `evidence_plan.frozen_untouched`（16 条，带 file:line） | 无；`launch.sh` 的 grep 从这里生成 |
| 杀条件 | `kill_conditions`（11 条）+ `falsification_prediction`（锁定） | 无 |
| 预算 | `blocks[].gpu_h` / `total_gpu_h` / `compute_budget` | 无 |
| 风险清单 | `reviewer_concerns_and_responses`、critique 的 `paper_pointed_threat`、coherence 的 `unrepaired` | 无；进 Grok 的检查表作为"已知风险" |

结论：Brain 已经是 B1 级图纸，缺的只是机器可读的一层（edits / cmd / eval_type / keep_if_all 或 scorer）——放进 Phase 5 的输出，不加席。

## 6. ARIS / CCF 放哪里

| 来源 | 内容 | 去处 | 形态 |
|---|---|---|---|
| ARIS experiment-plan | claim map / blocks / run order / anti-claim | Brain Phase 5（已内联） | 提示词 |
| ARIS run-experiment | nvidia-smi 预检、一实验一 unit、tee、后台跑、报告 GPU/命令/ETA、依赖分阶段钉版本、"import 成功不算就绪，跑种子见证" | `launch.sh` + `skills/worker/build.md` | 脚本 + 规则 |
| ARIS experiment-audit | 六检查 A–F：GT 来源、归一化、结果文件存在、死代码、范围、eval_type；"执行者只递路径" | `skills/critic.md`（Grok 的检查表） | 提示词 |
| ARIS result-to-claim | evidence 预检 → 换族判 supported yes/partial/no；REVIEW_UNAVAILABLE 即 fail closed | `verdict.py`（预检）+ Grok（判） | 脚本 + 提示词 |
| ARIS ablation-planner | supported 之后由换族模型设计消融，执行者只评可行性 | supported → 同一 Grok 通道出消融清单 | 后续 |
| ARIS analyze-results | 均值±std、对 baseline 的 delta、趋势 | `verdict.py` 输出 + E[] 模板 | 脚本 |
| ARIS shared: acceptance-gate / experiment-integrity / reviewer-independence | Type-A/B 分类、执行者不递总结、fresh 上下文 | `skills/critic.md` 头部铁律 | 规则 |
| ARIS kill-argument / paper-claim-audit | 攻防两线程、数字逐条回溯 | 论文阶段 | 后续 |
| CCF experiment-designer refs | baseline 矩阵、消融合同、最小说服包、result-templates | Brain Phase 5（已内联）；E[] 表格式 | 已在 |
| CCF experiment-discipline | "只有内部确认的完整方法版本能进表；smoke 永不作证据" | = 我们的 NOT_A_RESULT 规则 | 已在 |
| CCF idea-reviewer rubric | 打分口径 | Brain 3.2（原计划给 K3，未接） | 可选，后续 |
| CCF paper-reviewer / integrity-auditor / submission-checker | 终审、数字一致、投稿检查 | 论文阶段 | 后续 |
| ARFT | 45 码闭集、九条铁律（尤其 9："识别了机制≠解决了"） | `skills/critic.md` 的 class 闭集 + 铁律 | 规则 |
| ASI-Bench | B1 规格形态；自报分数不算数；硬门（禁库、缺文件、NaN）先于打分 | `spec/B*.json` 形态；`spec_floor.py`；`launch.sh` 的 grep | 已吸收 |

结论：**实验侧只需要 ARIS**（run-experiment、experiment-audit、result-to-claim 三个的规则逐字搬进两份 skill 和两个脚本）；CCF 的实验部分已经在 Brain Phase 5 里，其余 CCF 属于论文阶段。

## 7. 文件清单

新写：
- `.claude/skills/worker/build.md`（STEP-0 读单、实现/smoke/SELF_CHECK/blockers/wip 规则；V8 prompt-bank §1–§3 逐字）
- `.claude/skills/worker/critic.md`（给 Grok 的检查表：ARIS audit A–F + 四查 + 探针自证 + ARFT 闭集 + 铁律；路径清单模板）
- `.research/tools/spec_floor.py`、`launch.sh`（包 `launch_wrap.sh`）、`verdict.py`（从 `experiment.workflow.js:411-472` 抽出）、`anchor_check.py`、`canary.py`
- `.research/tests/golden/X-*.json`（金标语料）+ `test_worker_tools.py`
- Brain：Phase 5 提示词加 `spec` 字段与 open-hole 处置规则（同一席，零新席）；`spec_floor.py` 在 workflow 内对每个 block 跑一次，不过门的 block 标 `blocked_on`

保留：`instruments/*`、`launch_wrap.sh`、`ledger.jsonl`、`GOAL.md`、`substrate.json`、`anomalies.md`、`experiments/X-*.json` 格式。

删除：`experiment.workflow.js`、`dag.py` 实验侧、`bundles/`、旧 agents。

## 8. 两张卡的核对（2026-09-07）

r1 RADG 的基质锚点逐条对过代码：`GeoPriorGen.decay = log(1 − 2^{−(init − range·h/H)})`，stage 2 取 `init_values[2]=2, heads_ranges[2]=6, num_heads[2]=8`，与卡片的 δ_h 公式逐字一致；分解 h/w 路径 `mask_h = w0·mask_pos + (λ·w_d)·mask_d_h` 就是卡片 eq.2 的两个操作数、相加前各自存在；`_depth_lambda()`、`_pos_weight()` 存在；`depth_flip`、`depth_smooth_random`、`entire_missing` 在 `depth_corruptions.py:150/171/15`；`SEED=20260721` 在 `eval_robust_suite.py:150`；`rs_cond.py` 开头就是卡片引用的"raw RGB+depth 条件化对腐蚀无响应"的实测；`m78b_perframe_*.npz` 存在；69 键支持 = 40 行 + 30 列 − 1。**卡片的事实层站得住**。两处仍是假设、要 B1 先测：λ·w_d 训练后为正（卡片自己列为 S1 canary）、A 对结构性腐蚀有响应（B1 的 drop_r > spread_clean）。r2 OSDA 的算子位置同源，未逐条核。

## 9. 验收指标

- 从 spec 到 gate_passed ≤ 35 min（X-016：91）；主窗口一次 build 增长 ≤ 15 万 token。
- launch 0 模型 token；Grok 一次 ≤ 10 min。
- Grok 对金标语料一致率 100% 才启用。
- 每条 killed 有 ≥1 条带锚点 finding；每个 supported 的 E[] 数字可回溯到 `verdict.json`。
- 12 h 无人值守：无 REJECT、无空转、无传输断裂。

## 10. 未决

- Grok 用哪个模型档（`grok-4.6` 默认；金标校验时对比 `grok-4.5-max`）。
- K3 是否在 Grok 之前做一遍便宜预审（先不做）。
- Rank 席是否改用 CCF idea-reviewer 的十维加权 rubric + 分数护栏（现为自写 rank.md）；3.2 是否在 RS critique 之外加 CCF 打分（先不加）。

## 11. v2 复核（2026-09-07 深夜，Brain 定稿后）：还剩什么、怎么优化

Brain 现在交出的契约比 §3 设想的更完整：`spec/B<k>.json`（changes[file,function,what,tensor_shapes]、run_cmd / smoke_cmd、arms、negctl_arm、attribution、verdict_rule{outcome_metric, arms, keep_if_all, split, seeds, mde_source}、kill_condition、decision_points 带默认、open_holes、forbids、outputs、**gates[]（ASI evaluation.gates 形式）**、tests_premise、anti_claim）+ `evidence_plan.json`（role / failure_interpretation / min_effect / ablations 带 priority / skipped_roles）+ `ranking.json`（10 维分、五角色 panel、backup_run）+ 3.2 的 `arft_code` findings。§3 里"Phase 5 加 spec 字段"已由 Phase 6 席实现，§5b 的"缺什么"列已清零，只差一项：**arms[] 没有 `eval_type`**（V8 地板 R13：候选臂 ∉ {synthetic_proxy, simulation_only}）——Brain 侧一行字段 + spec_check 一行，跑 t1 前补。

### 11.1 已有、不用写（复用清单）

| 件 | 在哪 | 用法 |
|---|---|---|
| 启动包装：smoke 先行 + canary（CANARY_EXPECTED/TOL 由外部给）+ 看门狗（progress.json 停更 / NaN / 三点发散）+ ETA 2× 熔断 + early-kill + exit 3/4/5 | `.research/tools/launch_wrap.sh` | 原样；`launch.sh` 只是它外面的一层 |
| 仪器：m157 准入门、m158 配对 bootstrap 判决（键：delta / ci_lo / ci_hi / both_rungs_exclude_zero / per_rung.* / candidate_clean_cost / negctrl_*）、m159、launcher_reference、README（canary 49.11±0.1、受保护路径） | `.research/instruments/` | 原样；`m158_keys.py`（归档 v9）用 ast 抽真实键集，spec_check 的 keep_if_all 键可对它校 |
| Worker 硬规则五段：PREREG（含 F20 dual-reading）/ METHOD-COMPLETE / SELF_CHECK 七 grep / KNOWN_PITFALLS / OBSTACLE，逐字切自 experiment.workflow.js，带 sha | `.research/archive/v9-build-20260906/skills/worker/refs/*.md` | 复活到 `.research/tools/worker/refs/`，build.md 读单指向 |
| 判官指南 + 45 码闭集 | `docs/refs/papers/arft_guide.md`、归档 `skills/critic/refs/arft-codes.txt` | critic.md 引用；anchor_check 的 class 校验 |
| findings 合同 + 校验器：schema（anchor / class / blocking / note / failure_level / credit_due / anomalies；critic_failed 状态）、锚点存在性（file:line / log: / number:）、缺锚降 advisory、失败即 critic_failed（fail-closed） | 归档 `templates/findings.schema.json`、`tools/findings_check.py` | 复活即 `anchor_check.py` 的 80%；补 L0–L4 路由表（§5）和 survived/killed/pending_rejudge |
| 跨族代码评审：Grok + K3 盲审并集、交叉核验、`failure_scenario` 必填、CONFIRMED/PLAUSIBLE、`apply --outcome fixed|skipped|no_change_needed` | `~/cli/grilling-science/scripts/review.py` | launch 前的 code-review 直接用它（packet = diff.patch + spec + claim）；exit 1 = 有 CONFIRMED blocking |
| 单一族 refute 审 / K3 第二意见 / 生存概率 + 锚点引用 | `moa.sh verify` / `moa.sh review` | L4 的"两次独立 kill 票"第二票 |
| 数字来源预检（每个引用数字必须在结果文件里） | `~/oss/aris/tools/evidence_check.py` | verdict.py 调 |
| GPU 保护启动（MemoryMax、GPU 钉死、systemd 瞬时单元） | `~/cli/grilling-science/scripts/run_protected.sh` | 合并进 launch.sh 的 systemd-run 行 |
| Lehr MDE / band > mde / 预注册漂移 | grilling-science `gate.py chk_power/chk_margin`、`freeze.py` | 已由 Brain 的 plan_check 做；漂移改为 precheck 对 spec 决策字段做 sha |
| 金标语料 | 归档 `tests/golden/X-011/014/015/016.json`（全是 invalid；X-011 = L0） | 缺 survived 与真 kill 两个样本，要合成（见 11.3） |
| ARIS 原文读单：experiment-bridge（Key Rules、修复预算 2 patch + 2 rewrite）、experiment-audit A–F、result-to-claim（demote 不 kill）、training-check 三分表、acceptance-gate / experiment-integrity / reviewer-independence | `~/oss/aris/skills/*`、`docs/refs/aris/*` | build.md / critic.md 只放路径与 ≤10 行硬核 |
| Grok 无头调用：`grok -p --prompt-file … --tools <只读集> --output-format json --json-schema …`；`~/.grok/config.toml` 默认已是 grok-4.6 / xhigh | grok CLI；`grok:grok-rescue` 有 `--read-only` | 三次评审都用只读模式；沙箱 profile 未定义则用 `--tools` 白名单 |

### 11.2 要写的（全部是脚本或一页读单，零新席）

| # | 件 | 行数 | 读什么 | 产什么 |
|---|---|---|---|---|
| 1 | `precheck.py` | ~80 | spec/B<k>.json、evidence_plan、instruments/README、experiments/*.json | 本地重跑 spec_check；预算（gpu_h ≤ total_gpu_h − 已花）；决策字段 sha → `build/B<k>/spec.sha`；canary 环境行；worktree 引导命令（打印，不执行） |
| 2 | `launch.sh` | ~60 | diff.patch、spec.gates、spec.forbids | V8 三条零容忍 grep + gates 的 forbidden_* 扫 diff → nvidia-smi 空闲 → systemd-run（MemoryMax、GPU、CANARY_*、ETA_MAX_S = 2×gpu_h、EARLY_* 由 min_effect 推）→ launch_wrap → ledger 行。0 token |
| 3 | `verdict.py` | ~120 | exit code、results/、m158 verdict.json、spec | exit 3/4/5 → invalid（永不 refuted）；gates 的 file_exists / no_nan_inf / key_present；evidence_check；keep_if_all 逐条（V8 JS 搬）；negctl 命中 → L3；too_good（delta > 3× min_effect）→ 不许 survived；spec.sha 一致；封印 `verdict.json` |
| 4 | `critic.md` | 1 页 | — | 三个模式同一文件：spec-review（build 前：科学决定留白 → L2 回 Brain；对 open_holes / decision_points 逐条）、code-review（launch 前：bridge 2.5 六问 + V8 §3.5 锚点标准；或直接 review.py）、process-audit（跑完：audit A–F + Iron Rules 1/2/7/9 + D.7 anomalies + credit_due 先写 + ASI Dimension 3 异常 + 第五问"reviewer_concerns 哪条被回应"）；只给路径；输出按 findings.schema |
| 5 | `anchor_check.py` | +40 | findings/B<k>.json | 复活 findings_check + §5 路由表 + `pending_rejudge` |
| 6 | `build.md` | 1 页 | — | 硬核 ≤10 行（V8 NEVER 五条 + ARIS "follow the plan / 不发明实验"+ 修复预算 + 续跑规则 + blockers 非空即不许 launch）+ 读单（spec、plan、method_view、implementability、substrate、README、FROZEN、worker refs 五段、ARIS 三份原文） |
| 7 | `failure_card.py` | ~40 | verdict.json、findings、evidence_plan.failure_interpretation | `failures/B<k>.md`：level、arft_code、锚点、计划自己写的负结果解释 → Brain 重触发的负锚 |
| 8 | 金标 + 测试 | ~150 | X-011 smoke verdict.json、X-014 diff.patch、合成 survived / negctl-kill 两个 fixture | `test_worker_tools.py`：verdict.py 三态、launch.sh grep 抓 X-014 类泄漏、anchor_check 降级与 critic_failed、critic 在金标上一致率 100% 才启用 |

### 11.3 优化杠杆（省的是什么）

1. **GPU**：precheck → smoke（NOT_A_RESULT）→ canary → 才有第一颗种子；ETA 2× 与 early-kill 由 launch_wrap 执行；预算从 evidence_plan.total_gpu_h 扣，超即停（X.8）。
2. **Token**：GLM 只读 spec 点名的文件，不读 idea.detail（Grok 读）；一 block 一目录 + progress.md 追加，续跑不重来；>400k 交接不 compact。
3. **评审次数**：spec-review 每 idea 一次、code-review 每 block 一次（+≤2 次复审）、process-audit 每 run 一次；K3 只在 L4 第二票。REVIEW_UNAVAILABLE = blocked，critic_failed = pending_rejudge，永不 survived。
4. **零自由裁量**：GLM 不和 finding 争，blocking 只能在代码里解决或写 blocked；L2–L4 不修，失败卡回 Brain。
5. **刷分 / 消融**：同一 launcher MODE=full，按 run_order 和 ablations.priority 跑，每块各自 verdict.py；表格按 CCF result-templates 填，数字只能回溯到 verdict.json（numbers_gate 论文阶段再用）。

### 11.4 待 owner 定

- K3 第二族：每次 code-review 都用 review.py 的交叉核验，还是只在 L4 投票。
- Grok 档位：config 默认 grok-4.6 / xhigh；金标校验时对比 grok-4.5-max。
- Experiment 与 Brain 同一 claude-kimi 会话（Brain workflow 在后台）还是分会话。

## 12. 落地：主窗口 skill 链（2026-09-07 深夜；15 项测试全绿）

不是 workflow。六个项目级 skill 在 `.claude/skills/exp-*/SKILL.md`，每个 = 硬核 ≤10 行（每行带出处）+ 读单 + 命令；脚本在 `.research/tools/exp/`；审者合同 `critic.md` 由 `build_critic_md.py` 从原文切片拼成（测试比对字节，漂移即红）。

| 步 | skill | 脚本 / 原文 | 产物 |
|---|---|---|---|
| 1 领取 + 预检 | `/exp-next` | `precheck.py`：ranking → run_order 首个未过块；本地重跑 Brain 的 SPEC_CHECK（从 brain.workflow.js 抽，一处真源）；eval_type 地板（缺则 warn = Brain 待补）；预算；决策字段 sha；canary 从 README | `build/X/{spec.json, spec.sha, canary.env, progress.md}`、`experiments/X.json` |
| 2 审图纸 | `/exp-critic X spec` | `critic.py`（grok 无头只读：`--prompt-file --output-format json --json-schema --permission-mode plan`，与 grok 插件同参）+ `anchor_check.py` | `findings/spec.json`、`route.json`（pass / L2） |
| 3 实现 | `/exp-build` | V8 五段 refs 逐字（`refs/*.md`，归档 v9 切片带 sha）+ ARIS bridge Key Rules / 修复预算 | worktree diff、`self_check.json`、`blockers.json`、`deviation_notes.json` |
| 4 审代码 | `/exp-critic X code` | 同上；bridge 2.5 六问 + SELF_CHECK + ASI Dimension 3 + ARFT C.5 锚点标准 | pass / blocked（帽 2 patch + 1 重写，超帽回 Brain） |
| 5 发射 | `/exp-launch` | `launch.sh`：V8 三 grep + spec.gates forbidden_* + forbids 字面 → blockers/self_check → nvidia-smi → systemd-run（MemoryMax、GPU、CANARY_*、SEEDS、ETA_MAX_S=2×gpu_h）→ `launch_wrap.sh` | unit、台账 launched |
| 6 判决 | `/exp-verdict` | `verdict.py`：exit 三态 → sha 封印 → gates（file_exists / no_nan_inf / key_present）→ verdict 文件（排除 smoke/quarantine）→ keep_if_all → CI 含 0 → too_good（3×min_effect）→ negctl→L3；再 `/exp-critic X process`（audit A–F 原文 + 九条铁律 + 码表）→ `anchor_check.py` 路由 | `verdict.json`（封印）、`route.json`、survived / killed / pending_rejudge |
| 7 回 Brain | `failure_card.py` | L2–L4：level、arft_codes、锚点、计划自带的 failure_interpretation、verdict 数字 | `failures/X.{md,json}` |
| 8 交接 | `/exp-handoff` | 六节交接 + 记忆 | `build/X/handoff-*.md` |

测试 `.research/tests/test_exp_tools.py`（8 项，沙箱 `EXP_SANDBOX`，永不碰真台账）：precheck 领取/封印/预算/blocked；launch 干跑与 test_half / 未清 blocker 拦截；verdict 六态（含真实 X-011 的 negctl 命中 → L3、too_good、gate_failed）；anchor_check 六条路由（锚点缺失降级、L4 二票、critic_failed、修复帽阶梯）；critic 干跑与失败卡；critic.md 与源逐字节一致；skill 文件指向脚本。

未做 / 待真跑：Grok 真调用（`critic.py` 只干跑过；金标校验 = 对 X-011 的 process 审应给 verdict_agree=true + L3）；Brain 的 `spec.arms[].eval_type`（precheck 现在只 warn）；`--second`（K3 第二票）只在 L4 用，未跑过。

## 13. 自动模式与榨干审计（2026-09-07 深夜；17 项测试全绿）

### 13.1 自动模式 = 导航器 + 驱动 skill + /loop（无 workflow、无总线、无 hook）

`.research/tools/exp/next.py <run_root> --json` 是盘上状态的纯函数（台账 `experiments/X.json` + `build/X/` 标记 + `systemctl is-active`），吐出下一步；`/exp-auto <run_root>` 只做它说的，做完再问；GPU 在跑时 `/loop 10m /exp-auto <run_root>`。和 Brain 里 RS 的 `run.py next` 同构，与被 owner 判死的 dag 的区别：不登记会话、不做写门、不装 hook、自己不执行任何东西。

| 盘上状态 | 导航器给出 |
|---|---|
| 没有 `ranking.json`（k≥2）/ `r1/spec/index.json`（k=1） | `BRAIN`：`Workflow(brain.workflow.js, <run_root>/args.json)`（claude-kimi 会话） |
| 无当前 X | `/exp-next <root> --run --block <run_order 首个未过块>`；全过 → `SUPPORTED` + `report.py` |
| status=precheck，无 spec_review | `/exp-critic X spec` |
| spec_review=pass，无 `build/X/gate_passed` | `/exp-build X fresh` / `fix`（code_review=blocked 时） |
| gate_passed 存在，code_review≠pass | `/exp-critic X code` |
| code_review=pass | `/exp-launch X <worktree>` |
| launched | 有 `exit_code` → `/exp-verdict X`；unit active → `WAIT 600`；否则 verdict（记 no_exit_code） |
| infra | <3 次重发射，≥3 次当 build 问题 → `/exp-build X fix` |
| judged | `/exp-critic X process` |
| pending_rejudge | <2 次重审；≥2 次 `BLOCKED`（审者通道坏） |
| pending_second_vote | `/exp-critic X process --second` |
| fix_needed / killed L0–L1 / invalid | `/exp-build X fix`（帽 2+1，超帽 → 失败卡） |
| killed L2–L4 无卡 | `failure_card.py X` |
| 有失败卡（该 run 在此块死亡） | 梯子（2026-09-07 深夜接线）：ranking `backup_run` 未死 → `/exp-next --run <backup>`；两边都死 → `retrigger.py <root>`（新根 `<root>-n<round>`，`_shared/` 复用，`args.negative_anchors` = 本根全部失败卡，`brain_round+1`）→ `brain_round ≥ max_brain_rounds`（默认 2）→ `BLOCKED` |
| spec_review=L2 / code_review=escalate | `failure_card.py X` |

台账一致性由脚本维护：review 打回删 `gate_passed` 并置 `fix_needed`；verdict invalid 同；failure_card 置 `carded`；critic 失败计 `rejudge_count`。

### 13.2 榨干审计（源 → 落点）

| 源 | 落点 | 状态 |
|---|---|---|
| ARIS experiment-bridge：Phase 1 解析计划 / Phase 2 实现 + Key Rules / 2.5 六问 / Phase 3 修复预算 / Phase 5 收集 / 5.6 消融 / Phase 6 交接 | precheck.py / exp-build（Key Rules 逐字）/ critic code（逐字）/ exp-build 硬核 + anchor_check 帽（2+1，比 ARIS 2+2 紧）/ report.py + 台账 / Brain P5 / exp-handoff | ✓ |
| ARIS run-experiment：pre-flight / deploy / verify / Key Rules | launch.sh（free = used < 500 MiB；systemd-run + is-active 替代 screen；打印 GPU、命令、ETA）；vast/modal 不进 | ✓ |
| ARIS training-check：判读表 / STOP-CONTINUE-WAIT / act / Cron | exp-launch（表逐字）/ grok 一次 / launch_wrap exit 5 / `/loop` | ✓ |
| ARIS monitor-experiment："raw numbers before interpretation"、"check training logs before concluding" | exp-verdict、report.py / verdict.py 落 `unit.log` 给 critic；screen/wandb/feishu 不进 | ✓ |
| ARIS result-to-claim：1.5 证据预检 / Step 2 七字段 / 3.5 integrity / Step 4 路由 / fail-closed | verdict.py 直接读结果文件 / critic process（逐字）/ anchor_check critic_failed / survived-killed + `claim_supported` 随行（partial 不圆成 yes）/ pending_rejudge | ✓ |
| ARIS experiment-audit：完整审计提示 A–F / 报告格式 / "never block" | critic.md 逐字 / findings JSON 替代 / **有意更严**：锚定的 blocking 即 killed（V8 决定） | ✓ / 有意偏离 |
| ARIS ablation-planner / analyze-results | 设计半在 Brain；执行半 exp-verdict 步骤 3 / report.py（raw、delta、mean ± std） | ✓ |
| ARIS shared refs：acceptance-gate / integrity / independence / review-tracing / external-cadence / evidence-precheck | critic.md 逐字（含"判决意外先读原始记录"）/ exp-auto（"schedule the wait, never the verdict"）/ verdict.py | ✓ |
| ARIS kill-argument / paper-claim-audit / research-review / paper-*；reviewer-routing（codex/oracle） | 论文阶段；审者换成 grok | 不进（有意） |
| ASI-Bench：B1 阶梯 / gates / 自报分数 / reviewer Dimension 3、5 | critic spec / spec + launch.sh + verdict.py / critic.md / critic code + process | ✓ |
| ARFT：九条铁律 / C.5 锚点标准 / 码表 / 判官 Rule 1–2 / F.2 F.4 / D.7 / X.1 X.2 X.5 X.6 X.8 / R4 | critic.md / anchor_check 码集 / blockers 规则 / anomalies schema / 帽·封印·预注册·negctl→L3·预算 / infra≠verdict | ✓ |
| V8：五段 refs / launch 三 grep / judge JS / L0–L4 表 | refs/ 逐字（带 sha）/ launch.sh / verdict.py / anchor_check | ✓ |
| CCF：result-templates / experiment-discipline（smoke 永不作证据） | report.py / NOT_A_RESULT | ✓ |

结论：实验侧能榨的都进了（逐字优先，脚本次之）；剩下的三类是论文阶段技能、云 GPU/通知类基础设施、以及一条有意更严的偏离。

### 13.3 失败卡回 Brain 已接线（2026-09-07 深夜；测试 20 项全绿）

- Brain 侧：`args.negative_anchors`（失败卡 json 路径列表）只进三席的上下文行，零新席：Phase 1（与 anomalies 同等地位的实测事实，failure_interpretation 进 residue）、2.1+2.2（硬否决：卡上机制或未回应失败原因的变体在选择前出局，composition_note 记核对了哪些卡）、3.2（硬底线：重提卡上机制 = abandon，理由 `negative_anchor:<card>`）。卡不进 4b / Phase 5 / Phase 6 / rank。mock 变体 `MOCK_NEG_ANCHORS`。
- 导航侧：`next.py` 的 `dead(X)`（有卡即死）、`run_candidates`（rank-1 → backup_run）、`after_all_dead`（重触发或 BLOCKED）、`retrigger.json` 血统指针（`navigate` 顺着走，输出 `root` + `lineage`）；`retrigger.py` 幂等、超帽退出 3、无卡退出 3。
- 仍未跑过：Grok 真调用；Brain 的 `spec.arms[].eval_type` 仍是 warn；K3 第二票。
