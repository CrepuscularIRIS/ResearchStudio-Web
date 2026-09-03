# WORKFLOW.md v3 — 一条 claim 的无人值守闭环（机制图 + 刷分 + 及时止损，2026-09-03）

目标不变：`CLAIM.md` 里那一条 claim，一篇论文。人出现四次：accept、机制图无开放来源时、停止规则后二选一、D 阶段读稿。
形状是 paperjury / Claude native 的：workflow 只做语义 fan-out（输入内联、schema 输出），确定性动作在 `step.py` 里跑在两次 workflow 之间，`stage.py` 只读文件、每链打印恰好一条动作。复审证据：`docs/WORKFLOW-REVIEW-2026-09-03.md`。

## 0. 一页总览

```
A  frame      Fable 写 CLAIM.md ──► 人 accept
M  mechanism  一个 workflow，每条 claim 一次（Sparking.md：A→B→M→C）
              Fable：claim + anomalies.md → 失败模式 B（必须引用测量）→ 机制 M（三层抽象，最后一层无领域词）
              K3：   每个 M → 若干来源领域 C {同构论证, 机制名, disanalogy, 检索句}
              Grok： 每个 (M,C) → 配方基因（步骤 + 关键数字引文行）+ 先例（这个机制搬进 A 过没有）
              --finish：脚本核对引文行；无配方 / 有先例的 C 标 dropped；写 mechanism-map.json
C  loop       每链 5 个 Main 动作（alpha 走机制图，beta 跑 ConD 对照，各一台 GPU，一次一个候选）
              propose  Fable 从图里挑一个 open 的 C（或当前 C 上一版刷新了最好则再改一版）→ B1 规格
              --finish gate.py spec → 卡 → 冻结 → worktree
              build    同一 workflow：GLM 实现 → Grok 审 diff（逐步 coverage + 引文行）∥ Codex 审 diff
              --finish 脚本核对引文行 ∈ 真实 diff → token → launcher
                       unit 内：SMOKE=1 先跑（canary 不过 exit 3）→ 训练；watchdog 读 progress.json，
                       25%/50% 时 dev_gain 低于线 → 杀（exit 4，算 early kill，进 record）；停滞 45 min → exit 5
              record   render → gate.py record → notebook → 机制图刷分：同一 C 两版不刷新最好 → exhausted
                       band hit → 直接再跑 SEEDS=1,2；n≥3 且 CI95>0 → KEEP
              KEEP 后  支持阶梯：其他网络 / 数据集 / 消融，一次一档，仍是普通候选（phase=support，不计搜索预算）
P  pivot      24 h 无进步 / 24 搜索 GPU-h / 图上来源全部 exhausted → K3 一次 → 人选出口
D  write      阶梯走完 → writer 按节 → Fable 抛光 → Grok 终审 → gate.py numbers → latexmk
```

模型调用：M 阶段 Fable 1 + K3 1 + Grok fan-out（每条 claim 一次）；C 每轮 Fable 1、GLM 1（+1 修复）、Grok 1、Codex 1；Main 每轮 5 个动作。

## 1. 原则（每条一句）

1. 想法只从机制图来：A→B→M→C→S，不让任何车道自由发挥（Sparking.md；ARFT B.5 词汇相似≠结构同构，所以每个 C 必须带配方和 disanalogy）。
2. B 必须接地在我们测过的反常（`.research/anomalies.md`），不接地的失败模式不写（ARFT D.1）。
3. 规格必须是 B1 完整过程（ASI-Bench：只给方法名比不给更贵更差）。
4. 一次一个候选；花钱前有人看 diff；record 只来自 launcher；band hit 补种子后才叫 KEEP。
5. 止损由脚本执行，不由 Main 看：smoke 先跑、watchdog 中途杀、同一来源两版不进步就换来源。
6. 一个模型上成立之后再泛化：支持阶梯一档一档跑，绝不并行铺开。
7. null ≠ 否决；基础设施失败单列；丢弃带原因入队列。
8. 只为事实投票（代码忠实、泄漏、记录真实），不为想法投票。
9. 先跑一条链看完第一轮，再开第二条。

## 2. 模型与车道（4 + 1）

| 车道 | 模型 | 做什么 | 工具 |
|---|---|---|---|
| Main | GLM | 跑 `stage.py`，执行它打印的那一个 `step.py` 动作 | 全部 |
| scientist | Fable 5.1 | M：B 与 M；C1：规格；A；D 抛光 | Read, Write |
| explorer | K3 | M：来源领域发散；P：审查与联想 | Read |
| researcher | Grok | M：配方与先例检索；C：diff 监视；D：终审 | Bash, Read, Grep, Glob |
| reviewer | Codex（外部 CLI） | C：diff 的正确性审查（只在实验前） | Bash(node *), Read |
| builder | GLM | C：在 worktree 实现，让 kill_cmd 满足契约 | Bash, Read, Edit, Write, Grep, Glob |
| writer | GLM | D：按节写 | Read, Write, Edit, latexmk |

## 3. Main 看到的动作（`stage.py` 每链打印其一）

| 动作 | 里面发生什么 |
|---|---|
| `step.py mechanism` → Workflow(mechanism) → `--finish` | 上表 M；写 `mechanism-map.json` |
| `step.py propose <chain> [--rung R]` → Workflow(spec) → `propose --finish <Q>` | Fable 写规格；脚本：spec 门（步骤指向 trunk 上存在的文件、held-out 不进训练、network 白名单、kill_cmd 走 $RESULTS_DIR/$SEED、canary）→ 卡（worktree 先定）→ CLAIM.sha/FROZEN.sha 门 → 冻结 → worktree。门失败 → `--retry` 一次 → 再失败入队 |
| `step.py build <Q> [--fix]` → Workflow(build) → `build --finish <Q> <out>` | GLM 实现 → Grok ∥ Codex；脚本：每条引文行 ∈ 真实 diff、每个 step 有 coverage=implemented、无 finding、无 Codex P1、diff 未截断 → token（绑当前 diff sha）→ launcher。拒绝 → `--fix` 一次 → 再拒入队 |
| （等待） | `stage.py` 打印 `fraction · dev_gain · loss`；Monitor / ScheduleWakeup |
| `step.py record <Q>` | render → record 门（exit 0/4、mtime 在 unit 窗口、blockers.json、progress.json、clean_cost、metric 一致）→ notebook → 机制图刷分 → band hit 则启动 SEEDS=1,2 → 再次 `record` 重渲染 |
| `bundle.py queue <Q> "<why>"` | 丢弃带原因，链跳到下一候选 |

## 4. 每步 context bundle（字段 · 扣留）

| 步 | 给 | 扣留 |
|---|---|---|
| M / Fable | claim 核心、anomalies.md、AVOID、held_out、networks | 任何方法、任何论文、网络 |
| M / K3 | 机制列表、claim 句 | 我们的方法史、论文 |
| M / Grok | 一个 (M,C) 与其检索句、A 的领域词、本地库路径、`search_papers.py` 真实参数 | 其它来源、CLAIM 正文 |
| spec / Fable | claim 核心、机制图视图（每个 C 的 status/配方步骤/disanalogy/best/no_improve/tried）、本链最近 3 条或 `NO PRIOR RUNS`、parent{上版规格、record、monitor 理由、blockers}、榜单、numbers、AVOID ≤900 字符、trunk 文件清单 ≤80、结果契约；支持阶梯时另带 kept 规格与 rung | 他链规格、notebook error、文档、网络；对照链看不到机制图 |
| build / GLM | 规格、qid、worktree、kill_cmd、protected_paths、结果契约（含 progress.json 契约）、实现类 AVOID；`--fix` 带 monitor 理由/findings + unit 日志尾 | CLAIM、榜单、他链、`.research/`、网络 |
| build / Grok | steps、files、conditions、held_out、protected_paths、契约、硬规则；自己跑 `git diff` | builder 的报告、链历史、CLAIM 正文 |
| build / Codex | worktree 路径 + 固定命令 | 一切 |
| write | 节路径、keep records、其规格、机制图的 B/M、榜单、禁写清单 | — |
| pivot / K3 | claim 核心、榜单、notebook 最近 30 条、机制图视图 | — |

通用：JSON；ISOLATION 行；代码/日志/论文前 UNTRUSTED 行；`bundle.py` 断言字节上限，超限报错。

## 5. 门（脚本）

`gate.py spec` · `gate.py card`（含 CLAIM.sha、networks、worktree）· `gate.py monitor`（引文行、覆盖、截断、Codex P1）· `bundle.py token`（monitor 通过 ∧ diff sha 未变）· `run_protected.sh`（冻结、gate card、worktree、token、锁、同名 unit、同 GPU unit；清空 RESULTS_DIR；RuntimeMax；导出 EARLY_AT/EARLY_MIN/STALL_MIN）· `launch_wrap.sh`（smoke → canary；watchdog）· `gate.py record`（exit 0/4、mtime 窗口、blockers/progress 存在、clean_cost、metric、种子连续）· `stage.py` keep（valid ∧ band ∧ n≥3 ∧ CI95>0 ∧ 非 early）· `bundle.update_map`（patience 2）· `gate.py numbers` · `write-guard.py`（agent 不能写 CLAIM/GOAL/records/ledger/notebook/map/tokens/monitor/gates/queue/原稿/protected）。

## 6. 止损（全部脚本）

| 层 | 触发 | 结果 |
|---|---|---|
| smoke | canary 不在 tol 内 | unit exit 3，无 record，`build --fix` 一次 |
| watchdog | fraction ≥ 0.25 且 dev_gain < 0.0；≥ 0.5 且 < 0.25（CLAIM `early_stop` 可改） | exit 4，合成 seed 文件，record 标 early_kill，算 kill，机制图计一次 |
| watchdog | progress.json 45 min 不更新 / loss NaN | exit 5，基础设施失败，不计 |
| 刷分 | 同一来源连续 2 版不刷新最好成绩 | 来源 exhausted，下一候选必须换来源 |
| 全局 | 来源全部 exhausted/dropped，或 24 h / 24 GPU-h | P |

## 7. 失败语义

workflow 返回 null → 队列 + notebook `error`；重试上限各 1 次（spec 门、monitor、smoke）；计数在磁盘；Codex 缺席 skipped；Grok 缺席不放行；`queue.json` 只增不删。

## 8. 人的触点

accept；机制图无开放来源时读 `mechanism-map.json`；P 二选一（或带着 K3 的联想重跑 `step.py mechanism`）；D 读稿并清队列。

## 9. 待 owner 定

- `keep_networks`/阶梯：默认阶梯 = 其余网络各一档 + 一档消融；`CLAIM.md` 可写 `support_ladder` 覆盖。
- `keep_gain 1.0` 与 3 种子 MDE（clean sd 0.564 → 1.71）；confirm 用 CI 排除 0，可能要 5 种子。
- beta 链的 `mode: baseline` 建议写进 CLAIM.md（现在靠 seed_method 里含 “baseline” 判断）。

## 10. 不做的

陪审团、关键词文献循环、候选清单、K3 在 C 环内、Main 推理、外部 Python 驱动、并发顶层 workflow、为想法投票的排名器、并行铺开泛化实验。
