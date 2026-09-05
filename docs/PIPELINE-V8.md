# PIPELINE-V8 — 一个 Claim、三个 workflow、一条漏斗

草稿 2026-09-05。取代 docs/PIPELINE-V7.md。对象层（`.research/dag.py` 的 sha 审批、合同行账本、
put 校验）沿用 V7；workflow 从六个并成三个；H/Contract/P 三个 claim 对象并成一个 Claim。

---

## 0. 为什么重写：V7 一轮 330 分钟、产出为零

| 步骤 | 耗时 | agent | 产出 |
|---|---|---|---|
| dossier | 59 min | 18 | 一份十一栏卷宗，下游只用了 facts 和 closest_prior |
| hypothesize ×2 | 50 min | 46 | 两轮 do_not_generate，170 条 major |
| specify ×3 | 113 min | 9 | 两个 spec，一个作废 |
| experiment ×2 | 86 min | 10 | 一次 fix 后起跑，control arm 没跑 |
| adjudicate | 20 min | 7 | 一条 R/E |

三个根因，都不是"agent 太多"：

1. **对象错了。** FROZEN 已经写好了 keep rule（候选比同课程对照高 ≥MDE，两网三胜，clean cost ≤0.2）。
   这句话就是方法论文的 claim。hypothesize 却被要求再造一个带 load_bearing_variable、negative_control、
   alternative_explanations 的科学假说 H，K3 攻击它，三家投票杀它。170 条 major 全部落在这个多出来的
   对象上（AUROC 方向反了、常数场 Spearman 无定义、mIoU 不可逐位置分解），M_drafts 本身几乎没人碰。
2. **严出用了二元杀。** DeepResearch 的 3 票 2 杀是给"带引文的事实"设计的，事实非真即假。候选 idea
   没有真假只有排名。RS critique 自己是两层（机械硬底 + 软判断），ccf idea-reviewer 是致命门 + 四维分。
   V7 把二元杀用在了 idea 上，所以 0/6。
3. **同一件事判了三四次。** 数字重算三次（adjudicate Recompute、manuscript Audit、Referee sol 席）；
   证据许可四次（Judge+票、Claims、Referee claim table、Audit 四态）；novelty 三次（dossier、投票分、Scoop）；
   以及五个做脚本活的 agent（Package、Extract、Scope、Launch、Audit）。

"双轨"不是必须的。它是 H（研究轨 claim）和 P（论文轨 claim）并存的副产品。合成一个 Claim 之后，
剩下的是"一个对象在三个地方被检查"：research 产出它，experiment 检验它，paper 表达它。

---

## 1. 对象模型

### 1.1 FROZEN 改定义：目标、平台、预算、禁区，不含 claim

```
## FROZEN
Objective    一句话：要什么类型的贡献（method），投哪里（PR），解决什么现象
Platform     substrate.json 指向的网络、数据、检查点、受保护脚本；test half 只读一次；两块卡
Budget       GPU-h 上限、单候选 kill cap、research 轮数上限、paper 轮数上限
Measured     owner 已测的事实（anomalies）— 只读，never re-measured
Hard bounds  research 只能收紧不能放松的门槛：MDE 下限、clean cost 上限、基线表最小集合
Out of scope 训练无关方法作 headline、机制解释、新 benchmark、改协议
```

keep rule 和 protocol 从 FROZEN 挪出：它们是 Claim 的 contract rows，由 research 产出、由 research 第 6 相
的四家审核把关。Hard bounds 是防止 research 把 owner 实测定下的门槛改软：`dag.py put research` 比对每个
contract row 的阈值，低于 Hard bounds 即 REJECT。

### 1.2 六个对象变五个

| V7 | V8 | 说明 |
|---|---|---|
| H + H.contract + P | **Claim (C)** | claim 句、contract rows、机制候选、scoop level、四家分数、7×7 cell、strength |
| M | M | 不变：一个 Claim 行下的一个机制候选，1:N，每 Claim ≤3 |
| R | R | 不变：不可变记录，数字来自重算 |
| E | E | 不变：verdict ∈ {supports, weakens, refutes, underdetermined, method_invalid}，指向 (C, row, R) |
| — | (P) | 不再是对象。稿子里的 claim 句 = C.text 原文 + `% C-n` 注释；强度 = C.strength，由 E 派生 |
| D | (D) | 不再是对象。research 的中间产物写到 `.research/research/R-round-n/`，不进 lattice |

Claim 文件：

```json
{
  "id": "C-0001",
  "text": "A per-position depth-use module trained on cheap corruptions keeps ≥4.8 mIoU over the same-curriculum per-frame control on held-out structured rungs, on two of three hosts, at clean cost ≤0.2.",
  "type": "method",
  "opportunity": "Puzzle/Contradiction", "method_paradigm": "Robustification",
  "contract": {
    "required_evidence": [
      {"row": "primary",   "spec": "candidate − control ≥ 4.8 mIoU on mirrored+smoothed rungs, paired per-frame bootstrap CI95 excludes 0, ≥2/3 hosts", "status": "open"},
      {"row": "control",   "spec": "same frozen host, same curriculum, one depth weight per frame", "status": "open"},
      {"row": "baselines", "spec": "frozen host · zero fill · per-frame gate as published · ConD if runs · GeomPrompt-Recovery if runs", "status": "open"},
      {"row": "ablation",  "spec": "per-position vs per-frame, per rung", "status": "open"},
      {"row": "clean_cost","spec": "≤ 0.2 mIoU on NYU test half", "status": "open"}
    ],
    "kill_conditions": ["clean cost > 0.2", "CI95 spans 0 on both kept hosts"]
  },
  "mechanisms": [{"name": "...", "pattern": "structural_prior_encoding", "gene": "paper_id", "sketch": "..."}],
  "scoop": {"level": 4, "closest": "...", "delta": "Unlike X, which ..., ..."},
  "scores": {"opus": {...}, "sol": {...}, "k3": {...}, "glm": {...}, "median": {...}},
  "strength": null,
  "status": "active",
  "sha": "…", "depends_on": {"GOAL": "…"}
}
```

`strength` 由 `put experiment judge` 写：primary 行 supports 且 CI 不含零 → strong；supports 但单网 → adequate；
其余 → weak/negative。paper 的 draft 模式只读它，不判它。

### 1.3 不变的机制

sha8 审批、`approvals/<id>@<sha>.<lane>.json`、合同行是唯一账本、REJECT/RETRY/STOP 三种 put 结果、
infra.jsonl 三振出局、`next` 只读一行。

---

## 2. 共同形状与三条新规则

六个文件长成一样这条不变（PIPELINE-V7 §1：meta 纯字面量、MODEL/PRESET 常量、关键词常量带出处、
每个 agent 一个 schema、确定性装配、seat 缺席永不等于通过）。加三条：

**R1 宽进严出，事实二元、idea 排名。** 带引文的事实（quote、数字、代码行）用 DeepResearch 的 3 票 2 杀。
候选 idea 用两层：脚本硬底（scoop、预算、基线、anomalies）+ 四家分数中位数排名。任何地方不再对 idea 做
2/3 refute。

**R2 脚本能做的不给 agent。** 文件拷贝、路径拼接、`systemd-run`、数字对 R、cite 对 lit、P 句在不在、
7×7 数格、阈值对 Hard bounds，全部在 `dag.py`、`launch_wrap.sh` 或装配段。V7 里五个 agent 因此消失。

**R3 家族分工（owner 2026-09-04 教义，不变）。** Opus = 品味（选题、瓶颈、判证据）；sol = 算法与数学
（spec、重算、统计）；K3 = 找茬（跨域、反例；分数偏低需校准，不做裁决）；GLM = 广度（检索、读卡、实现、
写节、补丁）；Grok CLI = 工程主审。深的部件（瓶颈、审候选、判证据）多家族并行再收敛；浅的部件单家族跑量。

---

## 3. `research.workflow.js` — FROZEN + 本地状态 → 1-3 个 Claim

DeepResearch 骨架（Scope → pipeline(Search → Read) → Verify → Synthesize），RS idea_spark 的五个阶段填进去，
ccf idea-reviewer 做严出。这是核心 workflow，其余两个围着它的产出转。

### 3.1 相位表

| # | 相位 | 席位 | 宽/严 | 输入 | 输出 |
|---|---|---|---|---|---|
| 0 | Scope | GLM ×1 | 宽 | FROZEN、anomalies、两篇旧稿摘要、已有 C/E 状态 | 5-6 个角度 {label, query, kind, years} |
| 1 | Search | GLM ∥ 每角度 | 宽 | 角度 | ≤6 篇/角度，text_path 必须存在 |
| 2 | Read | GLM ∥ 每篇 ≤10 | 宽 | 一篇 | 一张 gene card（quote+line） |
| 3 | Verify | GLM ×1 fresh | 严（二元） | 所有 quoted items | refuted per index；未裁决 = 丢 |
| 4 | Bottleneck | Opus ∥ sol ∥ K3 → Opus merge | 深 | 存活卡、anomalies、旧稿结论 | bottleneck + gaps[]（每 gap ≥2 paper_id + stakes） |
| 5 | Generate | Opus ×2 ∥ sol ×2 ∥ K3 ×2 | 宽 | bottleneck、gaps、15 模式卡、Hard bounds | 6 个候选 Claim |
| 6 | Floor | 脚本 + (GLM 搜索 → Opus 判) | 严（硬底） | 候选 | scoop level；预算/基线/anomalies 四条过滤 |
| 7 | Converge | Opus ∥ sol ∥ K3 ∥ GLM，每存活候选 | 严（排名） | 候选 + 存活卡核心 | 四维分 + anchored items + 致命门 |
| 8 | Select | 脚本数格 → Opus ×1 | 严 | 排名、7×7 分布 | 前 1-3 个 Claim（按 index），justification |

约 30 agent，串行深度 8。GLM 约 1 min/call、Opus 约 3 min/call 计，墙钟 20-25 min。

### 3.2 每相要点

**0 Scope。** 角度种类：`mechanism_class · discriminating_observation · analogous_domain · escape_mechanism(必含) ·
closest_prior · contrary_evidence(必含)`。contrary_evidence 的对象是本地状态：两篇旧稿的结论和 anomalies 里的
每条测量。这就是"先攻击现有 claim"。RS intent-recognition 的 ESCAPE-MECHANISM 规则原文照抄（解题者用解法命名，
问题词查不到最近的前人）。

**1-2 Search/Read。** V7 的 SEARCH_PROMPT / READ_PROMPT 不变：本地语料先 grep，再 search_papers.py，
宽窗角度做 snowball；一卡一源，AVOID 优先（2604.15097 Table 7），quote+line。读卡上限 10。FROZEN 点名的
基线（ConD、GeomPrompt、DFormerv2、CMNeXt、GeminiFusion）强制入读卡池，不占上限。

**3 Verify。** V7 的单席读者式 fuzzy 检查不变。二元在这里是对的：一条引文要么在 ±2 行找得到要么找不到。

**4 Bottleneck（多家族收敛，第一处）。** 三家各自独立跑 RS bottleneck_identify.txt 的合同：
`bottleneck_statement`（说失败不说药方，≥2 paper_id 内联）、`closest_adjacent[]`、`gaps[]`（additive/subtractive，
每条带 stakes 子句）、`state ∈ {proceed, do_not_generate}`。三份输出交给第四席 Opus 合并：

- gaps 取并集，按 (paper_id 集合, 关键词) 去重，每条标 `raised_by[]`；
- bottleneck 取三份里被 ≥2 份的 paper_id 共同支撑的那条，没有则取 Opus 那条并标 `single_family`；
- 任一家 do_not_generate 且理由是 OOD（too broad / no anchor）→ 整轮 do_not_generate；理由是"<5 篇相关"不算，
  合并后再数。

合并不是平均：gap 越多越好，瓶颈只取一条。这和 STANCE_RULE 是两件事，那条只用于审稿。

**5 Generate（并行、跨域）。** 六席，每席一个 (gap, pattern) 组合。装配段先枚举 gaps × 15 模式的结构匹配
（RS ideate_select 的 Operational-signature 判断由 Opus 一次性做完，输出 6 个组合和 lens 分配），再并行生成。
K3 两席强制 `analogous_domain` 镜头。每个候选 Claim 的字段：

```
text · type(method) · contract.required_evidence[] · contract.kill_conditions[]
mechanisms[2-3] {name, pattern, sub_pattern, gene, sketch}
naive_baseline {what, why_it_fails | suffices | field_disbelieves}      ← RS 三分支自审
differentiation_from_lit[] · signature_terms[] · alias_terms[]
budget {gpu_h, runs}                                                       ← 对 FROZEN Budget
self_cell {opportunity, method_paradigm}                                  ← 7×7 自报
falsification: type=method → {minimal_experiment, outcome_metric, naive_baseline}
               type=mechanism → 加 load_bearing_variable, negative_control_target
```

证伪四问变**条件项**：RS 自己的普适性准则是"n/a 时零成本"。方法型 claim 不要求 load-bearing 变量。
`contract.required_evidence` 的每个阈值必须 ≥ FROZEN Hard bounds，装配段先查，低了直接丢该候选。

**6 Floor（脚本硬底）。** 四条，任一命中即死，死因写进 `dropped[]`：

1. scoop level ≤2：GLM 跑 signature@10mo + alias@48mo 两次搜索，Opus 按 RS 四轴判 level（min across hits）。
2. `budget.gpu_h` > FROZEN Budget 单候选上限，或机制引用了 substrate 没有的资源。
3. contract.baselines 行为空，或没有一个基线是 FROZEN 基线表里的。
4. `text` 与 anomalies 任一条矛盾（装配段把 anomalies 的数字和方向交给 Converge 的 GLM 席专查；
   GLM 报 `contradicts_anomaly=true` 且引到行号 → 死）。

**7 Converge（多家族收敛，第二处）。** 每个存活候选四席并行，同一 prompt 加各家 PRESET：

- ccf idea-reviewer 四维（novelty · soundness · feasibility · impact，1-5）+ ccf calibration.md 致命门；
- RS critique.txt 五检（paper_pointed_threat · recipe_application · anti_pattern · falsification_structure ·
  naive_baseline）；
- anchored items（≥12 字原文锚点，major/minor）。

装配：每维取四家**中位数**（抗 K3 偏低，抗任一家离群）；致命门 = 某维 ≤2 且 ≥2 家给 ≤2 → `capped`；
排名键 = (not capped, median soundness, median novelty, scoop level)。不 kill，只排。

**8 Select。** 脚本数存活候选的 `self_cell.method_paradigm` 落几格；全落一格且候选 >1 → Select prompt 里
加 2607.01233 的坍缩警告，Opus 必须写 justification 或换格。Opus 按 index 取前 1-3（默认 1，FROZEN Budget
允许才 2-3），可把落选候选的 mechanisms 嫁接到选中者（同 V7 merge[]）。返回 `{claims[], dropped[], stats}`。

### 3.3 模式

- `new`：上表全跑。
- `revise`：owner 或 paper round 的 `hypothesis_mismatch` 请求触发；跳过 0-4，Generate 只跑 2 席围绕给定
  Claim，Floor/Converge/Select 照跑。
- `add_mechanisms`：某 Claim 的 M 全 invalid 且 rows 未关；只跑 Generate 的 mechanisms 字段 + Converge。

### 3.4 关键词常量（沿用 V7，出处不变）

ANGLES_HINT / ESCAPE 规则（RS intent-recognition.md:18）、GENE_FIELDS / AVOID_FIRST（2604.15097 Table 7-8）、
QUOTE_RULE、BOTTLENECK_DISCIPLINE / GAP_RULES（RS bottleneck_identify.txt:90-101）、PATTERN_MENU / PATTERN_RULE
（RS ideation-patterns/overview.md）、NAIVE_BASELINE 三分支（RS design-notes "Why the naive-baseline audit exists"）、
SCOOP_AXES / ALIAS_RULE（RS scoop_check SKILL.md:23-30, 149-161）、CCF_FATAL（ccf calibration.md:27-34）、
DELTA_SENTENCE（RS scoop_check SKILL.md:167）、TASTE_AXES（2607.01233 App. B）。
删除：LINEAGE_RULE、RESIDUE_RULE、COHERENCE_T1_T5、H_CONTRACT_RULE、ALT_RULE、OOD_TWO 的"<5 篇"半条。

---

## 4. `experiment.workflow.js` — 一个 Claim 行 + 一个机制 → R + E

CodeReview 骨架（Scope → Find → group-by-location → Verify → Gate）。两个模式，中间隔着 GPU 等待。

### 4.1 build 模式

| # | 相位 | 席位 | 输出 |
|---|---|---|---|
| 1 | Draft | sol ×1 | B1 级 TestSpec：steps 到函数、run_cmd（所有 arm 顺序跑）、smoke_cmd、eval_entry、result_contract、forbids ⊇ gene.avoid ∪ kill_conditions |
| 2 | Implement | GLM ×1 | 在 `ugra-rgbd-robust` 的 worktree 实现，SMOKE=1 跑到 eval 写 seed_0.json，diff 到 build/<M>/diff.patch；返回 files、summary、deviations、smoke_passed |
| 3 | Find | Grok CLI ∥ GLM 三镜头 | 候选 findings {file, line, summary, failure_scenario, severity} |
| 4 | Verify | GLM 每 (file,line) 组 | CONFIRMED / PLAUSIBLE / REFUTED（native 阶梯 + RECALL 规则 + ARFT Iron Rules） |
| 5 | Gate | 脚本 | CONFIRMED critical/high → blocked；否则 `{gate_passed, worktree, diff_path}` |

改动对 V7：

- **Draft 吃 ccf-experiment-designer 的 evidence-design.md**：spec 必须为 contract 的每一行给出一个 arm 或
  一个读数，`arms[]` 与 rows 一一映射，装配段查。这是"ccf 对实验的补充"的位置。
- **T1-T5 干跑删除。** T2 的"执行"由 Implement 的 SMOKE=1 承担；"实现偏离 spec"由 spec-drift 镜头承担；
  T5 naive baseline 已在 research 第 5 相自审 + 第 7 相审核。
- **Opus 设计审删除。** 它问的四条里三条是字段（T5 verdict、unrepaired、eval_entry），第四条
  （机制是否真的检验该行）在 Converge 已判。sol 设计、GLM 实现、Grok 审：owner 教义"工程一律 GLM+Grok"。
- **Scope agent 删除**：Implement 返回 files + summary，SCOPE_BLOCK 由装配段拼。
- **Launch agent 删除**：`dag.py put experiment build` 收到 `gate_passed` 后自己跑 launch_checks，再
  `systemd-run --user --unit=research-<M> ... launch_wrap.sh`，写 launch marker。`NO_LAUNCH` 只是 put 不起跑；
  `launch_error` 类消失；"M1 在跑时 next 派 M2、agent 起跑、put 才拒"的孤儿 unit 不可能发生。
- **所有 arm 一个 unit。** `run_cmd` 是 `run_all_arms.sh`，顺序跑 candidate / control / baselines，或按
  substrate 的卡数并行两路；每 arm 写 `results/<arm>/seed_*.json`。上一轮 control 没跑就是因为一 M 一 arm。
- fix 模式沿用（一轮，第二次 blocked → invalid），worktree 复用的 `[ -d WT ] ||` 守卫沿用。

### 4.2 judge 模式

| # | 相位 | 席位 | 输出 |
|---|---|---|---|
| 0 | (index) | launch_wrap.sh 退出时写 | `build/<M>/evidence/index.json`：每个原件的 path、bytes、sha8、what；exit code；journal 尾 200 行 |
| 1 | Recompute | sol ×1 + Bash | 从 seed 文件重算每个 headline、配对 bootstrap CI95、clean_cost；executed=true 必须；与 spec.outcome_metric 不符即 mismatch |
| 2 | Judge | Opus ×1 fresh | verdict、一句 statement、transitions[]（close_row / add_row / set_c / invalidate_m）；H_RULE 改为 C_RULE（方法失败 ≠ claim 被驳，除非 primary 行的 spec 被完整执行） |
| 3 | Verify | sol ∥ K3 ∥ GLM | 对 Judge 的 3 票 2 杀（这里是事实层：verdict 是否与重算数字矛盾、是否忽略 HIGH blocker、SELF_AWARE） |

Package 和 Extract 两个 agent 删除：所有路径确定，launcher 自己写 index；metrics 由 Recompute 给出，exit/smoke
在 index 里。7 agent 变 5，串行 5 跳变 3。ARFT 的 artifact-aware 原则不变：judge 读原件，不读摘要。

`put experiment judge` 落 R、E，执行 transitions，写 C.strength；`add_row` 触发 research `add_mechanisms`
（若 M 预算未满）。

---

## 5. `paper.workflow.js` — E[] → 稿 → 一轮审

PaperJury 子集（ledger、exact-once 补丁、journal、裁判隔离）。V7 manuscript 减去 Audit agent、减去裁判对
证据的重判。

### 5.1 draft 模式

| 相位 | 席位 | 说明 |
|---|---|---|
| Claims | 脚本 | 不再有 Opus Claims 席：稿子的 claim 句 = C.text 原文，强度 = C.strength；负结果 = E.verdict≠supports 的 statement，每条必须出现（脚本查） |
| Write | GLM ∥ 每节 | WRITE_RULE 不变：数字只来自 R 且带 `% src: R-n`，cite 只来自 lit 表，C.text 原文带 `% C-n`，无记录处 TBD |

prewrite 模式保留（Intro / Related / Method / Setup 可在 GPU 前写），但 draft 的触发条件改为"无 `% C-n` 行"
而不是"无 ms.tex"（V7 的 prewrite/draft 互斥 bug）。表格骨架从 spec.arms 生成，不写死方法名。

### 5.2 round 模式

| # | 相位 | 席位 | 说明 |
|---|---|---|---|
| 1 | Referee | sol ∥ K3 ∥ GLM，隔离 | ccf 八维 + STANCE_RULE + **claim table 改问三件事**：这句话是否比它挂的 C.strength 强；有没有断言没挂 C；缺哪个对照。items 的 request_type ∈ {text_only, scope_overclaim, needs_evidence, needs_baseline, needs_ablation, hypothesis_mismatch}。`novelty_collision`、`method_validity` 删除：裁判无搜索、无 artifact，不重判研究轨 |
| 2 | Merge | 脚本 | passage_id 由锚点段落位置派生（V7 P1-1 修法不变）；(passage_id, request_type) 合并；lone-GLM major 降 minor |
| 3 | Contest | GLM 每单家 major | 不变 |
| 4 | Route | 脚本 | text_only / scope_overclaim → 补丁行；needs_* → add_row 请求；hypothesis_mismatch → research revise 请求 |
| 5 | Patch | GLM 每行 | exact-once、无新数字无 `% src:`、不碰 `% C-n` 行、段落数不变；装配段查 |
| 6 | Audit | **脚本** | 数字对 R 字段；cite ∈ lit；每个 C.text 原文仍在（四态退化为在/不在，因为补丁不许碰 C 行）；每条负结果 statement 仍在。任一不过 → 本轮不落 |

收敛：`genuinely_new == 0 && open_requests == 0 && audit_pass`，连续两轮 → DONE。轮数上限从 FROZEN Budget 读。

---

## 6. `dag.py` 改动清单

`next` 的一行输出和优先级队列保留；以下改动：

| 处 | V7 | V8 |
|---|---|---|
| 对象扫描 | dossier/D、hypotheses/H+contract、paper/claims/P | claims/C（含 contract） |
| 起点 | 无 D → dossier；D 无 H → hypothesize | 无 active C → research new |
| C 的 rows 开着且无 M 在飞 | hypothesize revise + add_m_for_rows | research add_mechanisms（M 预算内）否则 deadend |
| M specced 无 launch | experiment new → agent 起跑 | experiment build → `put` 起跑（cap 由 substrate 卡数定，默认 1；有 RUNNING 时不派 build） |
| launch 完成无 R | adjudicate judge | experiment judge |
| Hard bounds | 无 | `put research`：每个 contract row 的阈值 ≥ FROZEN Hard bounds，否则 REJECT |
| C.strength | 无 | `put experiment judge` 写 |
| 稿子审计 | 模型 | `put paper round`：数字/cite/C 行/负结果 四项脚本检查，任一失败 → 不落 |
| prewrite/draft | 互斥 bug | draft 条件 = 稿中无 `% C-n` |
| 请求类型 | 8 种 | 6 种（去 novelty_collision、method_validity） |
| SPEED 旗子 | 三个文件顶部的 TDZ 分支 | 删除；减法写进正式路径 |

`launch_wrap.sh` 增加退出钩子：写 `evidence/index.json`（path、bytes、sha8、what、exit、phase、early_kill）
和 `journal.tail`。

---

## 7. 预算

| workflow | agent | 串行深度 | 墙钟估计 | V7 对应 |
|---|---|---|---|---|
| research new | ~30 | 8 | 20-25 min | dossier+hypothesize 41 agent / 109 min / 零产出 |
| experiment build | 3 + Grok + k verifier | 4 | ~20 min | specify+experiment 8 / 38+43 min |
| experiment judge | 5 | 3 | ~10 min | adjudicate 7 / 20 min |
| paper draft | 5 | 1 | ~5 min | 6 |
| paper round | 3 + k + n | 4 | ~10 min | 4 + k + n + 1 |

一个完整回合（research → build → GPU → judge → draft → round）约 70 min 加 GPU 时间，V7 是 330 min 加 GPU。

---

## 8. 验收清单

1. `dag.py next` 从空状态起走：research → experiment build → (NO_LAUNCH) STOP，全程 Main 不读论文不判结果。
2. research 在一轮内产出 ≥1 个 Claim，`dropped[]` 里每个死因可追到 Floor 四条或 Converge 致命门之一；
   没有任何候选死于 2/3 refute。
3. Claim 的每个 contract row 阈值 ≥ FROZEN Hard bounds（构造一个低于阈值的返回，put 必 REJECT）。
4. Bottleneck 合并输出带 `raised_by[]`；单家瓶颈标 `single_family`。
5. Generate 六席的 (gap, pattern) 各不相同；K3 两席 lens = analogous_domain。
6. Converge 四家分数取中位数（构造一家全 1 的票，排名不变）。
7. 7×7 全落一格时 Select 无 justification → put REJECT。
8. experiment build：Implement 返回 summary；无 Scope、无 Launch agent；`put` 在 RUNNING 存在时 REJECT
   而 `next` 在 RUNNING 存在时不派 build。
9. launch_wrap 退出后 `evidence/index.json` 存在且 sha8 与文件一致；judge 无 Package/Extract。
10. paper round：Referee 不得产出 novelty_collision / method_validity；Audit 为脚本；构造一个改动 `% C-n` 行
    的补丁，装配段拒。
11. prewrite 后 draft 仍会触发。
12. node 装配夹具覆盖：research Floor 四条、Converge 中位数、Select 坍缩；experiment gate_passed 不含 unit；
    paper 脚本 Audit 四项。
13. 三个文件顶部无使用后声明的 `const`（`node --check` 之外加一个 TDZ 扫描：`grep -n "^if (" ` 之前不得引用
    之后 `^const` 的名字）。

---

## 9. 从 V7 删除的部件及理由

| 部件 | 理由 |
|---|---|
| H / H.contract / P 三对象 | 合成 Claim；双轨随之消失 |
| dossier 十一栏、40 facts、lineage 年代带、residue 规则 | 下游只用 facts 与 closest_prior；lineage 的用途（回归检测）由 Converge 的 paper_pointed_threat 承担 |
| hypothesize 三 lens + Contrarian + 三票 2/3 | 二元杀 idea 是 0/6 的原因；换成 Generate 六席 + Floor + Converge 排名 |
| FALSIFICATION_FOUR 作硬要求 | 方法型 claim 改条件项；170 条 major 的来源 |
| 两个 7×7 Profile agent | 只在 Select 前脚本数一次格 |
| specify DryRun T1-T5 + Opus 设计审 | SMOKE=1 和 spec-drift 镜头承担；owner 教义工程归 GLM+Grok |
| experiment Scope、Launch agent | 装配段和 put 承担 |
| adjudicate Package、Extract | launcher 写 index，Recompute 给 metrics |
| manuscript Opus Claims 席、Audit agent | C.text 直接进稿；审计四项全是字符串比对 |
| Referee 的 novelty_collision、method_validity | 无搜索无 artifact 的裁判不得推翻研究轨结论 |
| SPEED 旗子 | TDZ 崩溃；且它砍的是门不是重复 |
| 单独的 review workflow | idea 审在 research 第 7 相，paper 审在 paper round；两处用的是不同仪器（排名 vs 定位项） |

---

## 10. 待 owner 定

1. **7×7 是否进 experiment。** 本稿把它只放在 research Select 前的数格。若"experiment 用 7×7 建模"指别的
   意思（例如 method_paradigm 轴决定 spec 模板），Draft 相加一个查表。
2. **review 独立还是并入。** 本稿三个文件；要四个就把 paper round 拆成 review.workflow.js，接口不变。
3. **Select 默认取几个。** 本稿默认 1，Budget 允许才 2-3。取 2-3 意味着 experiment 交错跑、paper 同时挂两个 claim。
4. **Hard bounds 的内容。** 至少：MDE ≥ 4.8（Lehr，seed sd 1.19）、clean cost ≤ 0.2、基线表最小集合、
   test half 只读一次。是否加"两网三胜"。
