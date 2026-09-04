# WORKFLOW v4 — 定稿（2026-09-04）

这是循环的操作规范，之后不再改结构；设计理由见 `docs/WORKFLOW-V4-DESIGN.md`，提示词来源见 `docs/prompt-bank/`。Main 的操作卡是 `.claude/CLAUDE.md`。

## 0. 一句话

外层是稿件循环（读者是顶层评价者，弱点 ledger 是工作队列，停止 = 一轮干净且没有新问题 ∧ ledger 无 active major ∧ 事实门全过）；内层是 claim loop（一条 needs-data 行的处理器：机制图 → 评审团 → 规格 → 构建 → 外部审 → kill test → record）。任何模型的分数都不是门；只有 record、anchor、脚本事实是门。

## 1. 阶段（`stage.py` 从文件判定，每轮打印一个动作）

| 阶段 | 触发 | 动作 | 谁 |
|---|---|---|---|
| A | 无 CLAIM.md | `bundle.py A` → frame（可选：claim 通常来自 needs-data 行或 owner） | scientist（Opus 5） |
| R | claim 未 accept / 被改；图无开放来源 | owner `stage.py accept`（MDE、a_terms、只紧不松；绑定 needs-data 行） | 人 |
| M | 无本 claim 的图；或有 eligible 来源无 `critique` | `step.py mechanism` → Workflow(mechanism)：Opus B→M · K3 C · 每来源 searcher(GLM) → reader(GLM, 一篇一 agent) → verifier(sol) → `--finish`（脚本核每条引文行）；**Slot 1** `step.py critique sources` → Workflow(critique) → `--finish`（多数 anchored drop、rank 均值、contested） | Opus · K3 · GLM · sol · 评审团 |
| C | 图有开放来源，无 KEEP 完成阶梯，未停止 | 每链：`propose` → Workflow(spec) → `propose --finish`（gate.py spec）→ **Slot 2** `critique spec <Q>` → Workflow(critique) → `--finish`（advance / revise 一次 / abandon）→ `build` → Workflow(build)：builder(GLM) → Grok 插件审 → `build --finish`（gate.py monitor：critical/high 阻断 + 脚本覆盖）→ token → launcher（smoke、watchdog）→ `record` | Opus · 评审团 · GLM · Grok 插件 |
| P | 24 h 无进步 / 24 搜索 GPU-h / 来源耗尽 / dry runs；阶梯完成但网络数不足 | `bundle.py pivot` → Workflow(pivot) → `pivot --finish` → owner：(a) `stage.py ship --why` (b) 改 CLAIM 重 accept (c) `step.py mechanism` | K3 · 人 |
| W | 本 claim 的内层结束（KEEP + 阶梯，或 SHIP-INCUMBENT） | `outer.py`：W0 `write --merge` / `write`（节 + 事实审）→ 每轮 `read <n>` → `trial <n>` → needs-data 行等 owner → `draft <n>` → `write --review` → clerk → `gate.py deliverables` → DONE | critic-* · writer · researcher(sol) |
| STOP / DONE | IDENTITY-MISMATCH、INFRA-STOP / `.research/DONE` | 人 / 无 | — |

## 2. 车道与模型（额度：GLM ≫ K3 = sol = Opus）

| 车道 | 模型 | 模式 |
|---|---|---|
| scientist | claude-opus-5 | FRAME · SPEC（B→M 在 mechanism workflow 里也是它） |
| explorer | k3-256k | DIVERGE（C 来源）· PIVOT |
| searcher / reader | glm-5.3 | SEARCH（脚本检索 + 取正文）· REVERSE / PRECEDENT（gene card 带引文行） |
| verifier | gpt-5.6-sol | VERIFY（跨家族核卡：引文在行、步骤是过程、数字是机制自己的证据） |
| critic-sol / critic-k3 / critic-glm | sol / K3 / GLM | SOURCES · SPEC（评审团）· REFEREE · DEFENSE · JUROR · JUDGE（外层） |
| builder | glm-5.3 | 实现冻结的 spec，报告 files / deviations / blockers |
| reviewer | glm-5.3（转发） | Grok 插件 `review --json` |
| writer | glm-5.3 | MERGE · SECTION · PATCH |
| researcher | gpt-5.6-sol | REVIEW（事实终审：重算数字、`% src:`、负结果完整、四态审计、`style:`） |

grok-4.6 已不在 Claude-native workflow 中；Grok 只以插件（外部 CLI）形式审 diff。

## 3. Workflow（`.claude/workflows/`，只做语义 fan-out，输入全内联，输出 schema，互不调用）

frame · mechanism（Abstract → Diverge → Search → Reverse → Verify）· critique（三家并行）· spec · build（Build → Review）· write（Sections → Review；mode merge/sections/review）· pivot · read（三 referee）· trial（Defense → Jury → Judge，quorum 在 JS 里确定性计算）· draft（writer PATCH 并行）。

## 4. 脚本与模块（`.research/`）

| 模块 | 职责 |
|---|---|
| `stage.py` | 读文件状态，打印阶段与动作；`accept` / `ship` / `board` / `map` |
| `step.py` | Main 的动作：打印 Workflow 行，或 `--finish` 消费结果并过门 |
| `bundle.py` | 上下文 bundle 与提示词（spec / card / build / token / notebook / queue / waive）；`_ns()` 把自身命名空间交给部件 |
| `mechanism.py` | `cmd_M`、`cmd_mechanism_finish`（`_quote_at` 引文行核验、接地、领域词、先例） |
| `writing.py` | `cmd_write`（merge / sections / review）、`cmd_pivot` |
| `critique.py` | 评审团 bundle 与聚合（Slot 1 多数 anchored drop；Slot 2 取最差且按 anchor 封顶） |
| `outer.py` | 外层循环：read / trial / draft 的 bundle 与 finish、`apply_patch`、`decide` |
| `paper_ledger.py` | 弱点 ledger：intake（去重、再提即重开）、路由、gate、needs-data 绑定/关闭；CLI `gate | docket | summary | set` |
| `decompose.py` | 稿件切段、anchor 定位（不能引用 = 不立案） |
| `gate.py` | 确定性门：spec · card · freeze · cardsha · monitor · diffsha · record · numbers · deliverables |
| `gate_legacy.py` | 最小循环遗留（screen、schema-1/2、verdict/packet/merge、views），claim loop 不用 |
| `render_record.py` · `launch_wrap.sh` · `bin/run_protected.sh` | record 只由 launcher 产生；smoke → watchdog → seed 文件 |
| `fetch_text.py` · `paper-search` skill | 检索与取正文（全是脚本，无 WebSearch） |

## 5. 状态文件（脚本写；write-guard 拒绝车道写入）

`CLAIM.sha` · `mechanism-map.json`（来源 status / best / no_improve / critique）· `bundles/`（args 与 out）· `gates/`（spec.ok / critique.fail / write-review / pivot-*）· `critique/<Q>.json` · `cards/` · `monitor/` · `tokens/` · `records/` · `notebook.json` · `queue.json` · `ledger.jsonl`（accept / ship / stop / waive 事件）· `SHIP-INCUMBENT` · `paper-ledger.json` · `paper-journal.jsonl` · `DONE`。

## 6. 门与聚合规则（一览）

- record：launcher 窗口、canary（冻结规格的 bar）、blockers.json（high 需 waive）、metric = claim metric、fraction ≥ 0.95；拒绝的 record 不计 best / kill line / map / KEEP。
- KEEP：n ≥ seeds_for_keep、CI95 > 0、≥ keep_gain 高于同网络 baseline 链；阶梯 R1 = 全 schedule = headline。
- monitor：Grok 插件 critical/high 阻断；每个 step 的 file 在 intent-to-add diff 中；无 gitlink/symlink；eval_entry 未动；token 绑 card sha + diff sha。
- Slot 1：fail 只在 anchor 是 bundle 原文子串时算；≥2 家 anchored drop → dropped；rank 均值只做 tie-break；contested 回落 hill-climb。
- Slot 2：每家裁定先按自己的 anchored finding 封顶，再取三家最差；abandon → patience + 1，永不进 best。
- 外层：weakness 必须 anchor 到段落；同段落相似即再提（corroboration 计数，不抬 significance；已关闭者重开）；major & substantive → trial；quorum ≥ 0.8·n 且一方 > 60%；judge 只路由；patch 精确一次替换 + numbers gate，失败回滚并转 author-required；needs-data 行由 accept 绑定、由 record 关闭；停止 = 干净轮次 genuinely_new == 0 ∧ 0 active major ∧ 事实审 pass ∧ deliverables。

## 7. 人的触点

accept（预注册）· 图无开放来源 · P 的出口（ship / revise / new sources）· waive 高 blocker · needs-data 行（写 CLAIM 或 author-required）· max_rounds 用尽 · STOP。

## 8. 测试与命令

`python3 -m pytest .research/tests -q`（97 项，含 outer / critique / M waves / ship）· `bash .research/tests/test_launcher.sh`（需 LOCK）· 插件副本 `~/cli/research-harness`（scripts/ hooks/ agents/ workflows/ tests/）同步。
