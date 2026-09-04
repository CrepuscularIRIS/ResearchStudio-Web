# 架构解析（v4 定稿，2026-09-04）

规范见 `docs/WORKFLOW-V4.md`，理由见 `docs/WORKFLOW-V4-DESIGN.md`。

## 1. 三层

| 层 | 是什么 | 谁写 | 例 |
|---|---|---|---|
| 真相 | 只由脚本或 launcher 写的文件 | `step.py` / `gate.py` / `outer.py` / `paper_ledger.py` / `render_record.py` / launcher | `CLAIM.sha`、`mechanism-map.json`、`cards/`、`monitor/`、`tokens/`、`records/`、`ledger.jsonl`、`notebook.json`、`queue.json`、`critique/`、`paper-ledger.json`、`paper-journal.jsonl` |
| 语义 fan-out | workflow 文件；输入全内联，输出 schema；互不调用 | 10 个 `.claude/workflows/*.js` | frame · mechanism · critique · spec · build · write · pivot · read · trial · draft |
| 编排 | `stage.py` 读真相层、打印一个动作；Main 只执行 | Main | `step.py …` / `bundle.py queue` / `human: …` |

数据流（内层）：`CLAIM.md` → `mechanism-map.json`（+ critique）→ `bundles/spec-Q.json` → `critique/Q.json` → `cards/Q.json`（冻结）→ worktree diff → `monitor/Q.json` → `tokens/Q.clean` → unit → `results/Q/{smoke, progress.json, seed_k.json, blockers.json}` → `records/Q.json` → `notebook.json` + 机制图状态 → 下一候选 / 支持阶梯 / P。
数据流（外层）：`paper/pr/sections/*.tex` → referees → `paper-ledger.json`（raised → in-trial → valid-fixable / needs-data → closed）→ `draft` 补丁（`paper-journal.jsonl`）→ 事实审 → clerk → `DONE`。needs-data 行 → owner 写 CLAIM → 内层 → record → 行关闭。

## 2. 谁决定什么

| 决定 | 谁 | 凭什么 |
|---|---|---|
| claim | 人 | `stage.py accept`（MDE、a_terms、只紧不松） |
| 失败模式 B、机制 M | scientist（Opus） | claim + `anomalies.md`；B 必须引用测量并带 stakes；problem-level 而非 solution-level |
| 来源领域 C | explorer（K3） | 机制列表；同构论证、disanalogy、alias_terms；way_of_thinking 不入图 |
| 论文与 gene card | searcher / reader（GLM）→ verifier（sol） | 引文行；步骤是过程；先例引文可核 |
| C 是否进图、顺序 | 脚本 + 评审团（Slot 1） | 引文行核对、无先例；≥2 家 anchored drop 才丢；rank 只做 tie-break |
| 规格是否合格 | 脚本 + 评审团（Slot 2） | B1 门；三家最差裁定且按 anchor 封顶 |
| 代码是否忠实、是否泄漏 | Grok 插件 + 脚本 | critical/high 阻断；每 step 的文件在 diff；无 gitlink；eval_entry 未动 |
| 能否启动 | launcher | 冻结、门、token 绑 card sha + diff sha、锁、同 GPU |
| 要不要中途杀 | watchdog | `progress.json` |
| 什么算数 | record | `gate.py record`；只有 record 反驳；分数从不进 KEEP / best / DONE |
| 稿件哪里错 | 三家 referee → 陪审 → judge | anchor 在正文；quorum；judge 只路由 |
| 哪一格需要数据 | judge → owner | needs-data 行 = 主表一格；owner 写 CLAIM |
| 论文完成 | clerk + 脚本门 | 干净轮次无新问题 ∧ 0 active major ∧ 事实审 pass ∧ deliverables |

## 3. 失败语义

null / error 的 workflow 输出 = 基础设施失败：`--finish` 拒绝过门、计数、打印重试；三次连续 2 h 内 → INFRA-STOP。一家评审/referee/juror 返回 null 不是裁定（缺席不计票）。unit exit 3 → 一次 fix；exit 5 → 一次重启；再次 → queue。

## 4. 不再改的

阶段表、车道/模型表、门与聚合规则、状态文件清单（§5）。提示词内容可以调（`docs/prompt-bank/` 是来源），结构不动。
