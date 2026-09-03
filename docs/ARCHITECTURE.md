# 架构解析与逐步决策表（v3，2026-09-03）

## 1. 三层

| 层 | 是什么 | 谁写 | 例 |
|---|---|---|---|
| 真相 | 只由脚本或 launcher 写的文件 | `step.py` / `gate.py` / `render_record.py` / launcher | `CLAIM.sha`、`mechanism-map.json`、`cards/`、`monitor/`、`tokens/`、`records/`、`ledger.jsonl`、`notebook.json`、`queue.json` |
| 语义 fan-out | workflow 文件；输入全内联，输出 schema；互不调用 | 6 个 `.claude/workflows/*.js` | frame · mechanism · spec · build · write · pivot |
| 编排 | `stage.py` 读真相层、每链打印一个 `step.py` 动作；Main 只执行 | Main（GLM） | `propose` / `propose --finish` / `build` / `build --finish` / `record` |

数据流：`CLAIM.md` → `mechanism-map.json` → `bundles/spec-Q.json` → `cards/Q.json`（冻结）→ worktree diff → `monitor/Q.json` → `tokens/Q.clean` → unit → `results/Q/{smoke, progress.json, seed_k.json, blockers.json}` → `records/Q.json` → `notebook.json` + 机制图状态 → 下一候选 / 支持阶梯 / P / D。

## 2. 谁决定什么

| 决定 | 谁 | 凭什么 |
|---|---|---|
| claim | 人 | `stage.py accept` |
| 失败模式 B、机制 M | Fable | claim + `anomalies.md`；B 必须引用测量 |
| 来源领域 C | K3 | 机制列表；每个 C 带同构论证与 disanalogy |
| C 是否进图 | 脚本 | 有配方步骤、引文行核对通过、无先例 |
| 这一轮试哪个 C、怎么适配成规格 | Fable | 图上 status=open，或当前 C 上一版刷新了最好 |
| 规格是否合格 | 脚本 | B1 四项 + kill_cmd 契约 + canary |
| 代码是否忠实、是否泄漏 | Grok 报告 + Codex 报告，脚本裁决 | 引文行 ∈ 真实 diff、逐步覆盖、无 finding、无 P1、未截断 |
| 能否启动 | launcher | 冻结、门、token 绑 diff sha、锁、同 GPU |
| 要不要中途杀 | watchdog | `progress.json`：25% 时 dev_gain<0、50% 时 <0.25；停滞 45 min |
| 结果算不算 | 脚本 | exit 0/4、mtime 在 unit 窗口、blockers/progress 存在、clean_cost、metric 一致、canary |
| kill / keep | 脚本 | kill 线 max(floor, best/2)；keep = band ∧ n≥3 ∧ CI95>0 ∧ clean_cost≤0.2 ∧ 非 early |
| 换不换来源 | 脚本 | 同一来源连续 2 版不刷新最好 → exhausted |
| 什么时候泛化 | 脚本 | 一个 KEEP 之后，阶梯一档一档 |
| 什么时候停 | 脚本 | 24 h / 24 GPU-h / 来源用尽 |
| 停了往哪走 | 人（K3 给意见） | ship / 改 claim / 带联想重做机制图 |
| 论文里的数字 | 脚本 | 每个数字同行 `% src:` 且在 record 里 |

模型只在三处“决定”：Fable 决定 B/M/S，K3 决定 C 候选，人决定 claim 与出口。Grok、Codex、GLM 只报告或实现，报告由脚本核对后才生效。

## 3. 逐步决策表

| # | 步 | 谁 | 输入 | 规则 | 输出 | 失败 |
|---|---|---|---|---|---|---|
| A | frame | Fable | 三份稿件、records、本地库、模板 | 一条 claim + yaml 数字块 | `CLAIM.md` | 人改 |
| R | accept | 人 | `CLAIM.md` | 读过即接受 | `CLAIM.sha` | — |
| M1 | abstract | Fable | claim 核心、`anomalies.md`、AVOID | 2–4 个 B，每个引用测量；每个 B 三层抽象到无领域词的 M；不提方法/论文 | `{failure_modes, mechanisms}` | null → 整个 M 阶段重跑 |
| M2 | diverge | K3 | M 列表、claim 句 | 每个 M ≤3 个 C，≥2 个领域；同构一句、disanalogy 一句、检索句一条；不凭记忆引论文 | `sources[]` | null → 重跑 |
| M3 | retrieve | Grok ×N | 一个 (M,C)、检索句、A 的领域词、本地库 | 跑 `search_papers.py`；选给出过程的论文；本地库优先；配方 ≤4 步 + 关键数字引文行；先例检索 | `{recipe, precedent}` | null → 该 C 标 error（不进图） |
| M4 | finish | 脚本 | M3 输出 | 无步骤 / 无 disanalogy / 引文行不符 / 有先例 → dropped | `mechanism-map.json` | 无 open → R 给人 |
| C1 | propose | Fable | 图视图、本链历史或 `NO PRIOR RUNS`、parent、榜单、numbers、AVOID、trunk 文件表、契约 | 选 open 的 C 或延续刚进步的 C；B1 规格；`source` 填 C | `bundles/spec-Q.json` | null → 队列 |
| C1' | spec 门 | 脚本 | 规格 | ≥3 步且每步指向 trunk 上存在的文件；条件不含 held-out 词；network 白名单；gpu_h ≤ cap；kill_cmd 含 `$RESULTS_DIR`/`$SEED`；canary 数值 | `gates/Q.spec.ok` | 带清单重试 1 次 → 队列 |
| C2 | card/freeze | 脚本 | 规格 + CLAIM 数字 | kill 线动态、band [keep_gain, 99]、worktree 先定、CLAIM.sha/FROZEN.sha | 冻结卡、worktree | 门拒 → 队列 |
| C3 | build | GLM | 规格、契约、protected、实现类 AVOID（修复轮附 monitor 理由 + 日志尾） | 按步实现；不判 smoke | `{files_changed, deviations, blockers}` | null → 队列 |
| C4 | monitor | Grok ∥ Codex | Grok：steps/files/held_out/protected/契约，自己 `git diff`；Codex：worktree | Grok：每步 coverage + 引文行；findings；Codex：正确性缺陷 | `{grok, codex}` | Grok null → 不放行；Codex null → skipped |
| C4' | monitor 门 | 脚本 | C4 输出 + 真实 diff | 引文行逐行存在；每步 implemented；无 finding；无 P1；未截断 | `monitor/Q.json{approved, diff_sha}` | `--fix` 1 次 → 队列 |
| C5 | token + launch | 脚本 + launcher | monitor、卡、worktree | approved ∧ diff sha 未变 → token；launcher 六拒 + 同 GPU 拒 | `research-Q.service` | 拒 → 打印原因 |
| C5' | unit 内 | launch_wrap | kill_cmd | SMOKE 先跑 canary（exit 3）；watchdog 25%/50% 线（exit 4）、停滞/NaN（exit 5） | `results/Q/` | 3/5 → 无 record，日志尾进下一轮 fix；4 → early kill record |
| C6 | record | 脚本 | `results/Q/`、ledger | render；门；notebook；机制图 patience；band hit → SEEDS=1,2 | `records/Q.json`、图状态 | 门拒 → 不进榜 |
| C7 | keep | 脚本 | record | n≥3 ∧ CI95>0 ∧ clean_cost ≤ 0.2 ∧ 非 early | KEEP | — |
| S | support | 脚本 + Fable + C3–C6 | kept 规格 + 阶梯下一档 | 一档一档；phase=support 不计预算 | 阶梯 done | 档失败 → 队列，继续下一档 |
| P | pivot | K3 → 人 | 榜单、notebook、图 | 每个死掉的 C 为什么；还有什么 M/C；claim 该不该改 | verdict | 人选 |
| D | write | writer / Fable / Grok / 脚本 | keep records、规格、图的 B/M、禁写清单 | 数字只从 records；`% src:`；黑名单 | 节 + pdf | 终审 block → 人 |

## 4. 每轮成本

Main 动作 5 个（≈5 分钟编排）；模型调用 Fable 1、GLM 1（+1）、Grok 1、Codex 1；GPU 一次 unit（smoke ≤15 min + kill test ≤ 4 GPU-h，中途可杀）；band hit 再一次 unit（2 种子）。

## 5. agents / skills 的现状（2026-09-03）

另一个会话在 07:03 把 `.claude/` 整目录挪成了 `.claude.bakcup0903/`，hooks、settings、agents、skills 全没了，测试与 hook 引用全部失效；我用 `cp -rn` 复制回来（备份未动）。git 视角：agents 五个文件本来就在仓库里（现在是 M），`reader.md`、`writer.md` 来自备份（未跟踪），两个 hook 是新写的；skills 与 skills-dormant 在仓库里本来就有，复制回来后与 git 一致。

v3 实际用到的：agents `scientist / explorer / researcher / reviewer / builder / writer`（六个，都在 workflow 的 `agentType` 里）；skills 只有 `paper-search`（机制阶段的检索脚本）。已做的收纳：`reader.md` → `.claude/agents-dormant/`；`imitate`、`reverse-engineer`、`scoop-check` → `.claude/skills-dormant/`（它们的活现在由机制图做）；inventory 测试改为只认 `paper-search`。`skills-dormant/` 里 21 个目录仍不被任何 workflow 加载，留作论文侧备用。
