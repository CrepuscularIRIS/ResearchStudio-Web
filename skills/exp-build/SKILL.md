---
name: exp-build
description: "Experiment step 2 — implement ONE block exactly as spec/B<k>.json says, in the worktree, up to gate_passed (smoke + SELF_CHECK + blockers). Also the fix / reimplement re-entry after a blocked review. Use when the user says build / implement / 实现 / 修复."
---

# exp-build — 实现到 gate_passed（不按发射钮）

硬核（≤10 行，每条有出处）
1. NEVER：`Redesign the experiment. Touch protected paths (eval_entry). Run nohup, systemd-run, or any GPU python beyond the smoke stage. Read .research/ beyond the paths in the brief. Choose among seeds.`（V8 §2.1，ccf builder.md:27）
2. `Follow the plan. Do not invent experiments not in the plan. If you think something is missing, note it but don't add it.`（ARIS experiment-bridge Key Rules）
3. `CRITICAL — Evaluation must use dataset ground truth … NEVER use another model's output as ground truth.`（同上）
4. 每处偏离进 `deviation_notes.json`，静默重设计 = blocked（refs/prereg.md）；操作词多义 = finding，钉死读法（F20）。
5. 修复预算：同一失败 2 次 patch，再 1 次干净重写；干净重写只删本次的脚手架，计划/数据/结果永不删（ARIS bridge Phase 3；V8 帽）。
6. 续跑：`build/X/spec.json` 与 worktree 已存在即从 `progress.md` 继续，不重来（V8 RESUME-aware）。
7. 止于 gate_passed：`blockers.json`（空 = 宣称没找到）、`self_check.json`（7 条 grep 逐字输出）、`diff.patch`；launch 是另一个脚本。

ARIS experiment-bridge Key Rules（逐字，`docs/prompt-bank/raw/aris/experiment-bridge.md`；Vast.ai / Modal 两条对本机无效）

## Key Rules

- **CRITICAL — Evaluation must use dataset ground truth.** When writing evaluation scripts, ALWAYS compare model predictions against the dataset's actual ground truth labels/targets — NEVER use another model's output as ground truth. Double-check: (1) ground truth comes from the dataset split, not from a baseline/backbone model, (2) evaluation metrics are computed against the same ground truth for all methods, (3) if the task has official eval scripts, use those.
- **Follow the plan.** Do not invent experiments not in EXPERIMENT_PLAN.md. If you think something is missing, note it but don't add it.
- **Sanity first.** Never deploy a full suite without verifying the sanity stage passes.
- **Reuse existing code.** Scan the project before writing new scripts. Extend, don't duplicate.
- **Save everything as JSON/CSV.** The auto-review-loop needs parseable results, not just terminal output.
- **Update the tracker.** `EXPERIMENT_TRACKER.md` should reflect real status after each run completes.
- **Don't wait forever.** If an experiment exceeds 2x its estimated time, flag it and move on to the next milestone.
- **Budget awareness.** Track GPU-hours against the plan's budget. Warn if approaching the limit.
- **Vast.ai lifecycle.** If using vast.ai instances, destroy them after all experiments complete and results are downloaded. Running instances cost money every second — don't leave them idle. Use `/vast-gpu destroy` or `/vast-gpu destroy-all` when done.
- **Modal lifecycle.** If using `gpu: modal`, no cleanup is needed — Modal auto-scales to zero after each run. But always show cost estimates before running and verify the spending limit is set at https://modal.com/settings (NEVER through CLI).

STEP 0 读单：`build/X/spec.json`（changes / run_cmd / smoke_cmd / arms / negctl_arm / verdict_rule / forbids / gates / decision_points / open_holes）· 该 run 的 `phase4/method_view.json`（key_equations、method_flow）· `phase4/phase4_implementability.json`（enriched_steps）· `_shared/substrate.md` · `.research/instruments/README.md` · `.research/GOAL.md` FROZEN · 五段规则原文：`.research/tools/exp/refs/{prereg,method-complete,self-check,known-pitfalls,obstacle}.md` · ARIS 原文按需：`~/oss/aris/skills/experiment-bridge/SKILL.md`（Phase 2–3、Key Rules）。

步骤
1. 只读 spec 点名的仓库文件；只在 worktree 里 Edit；增量 commit（`git -C /tmp/wt-X add -A && git -C /tmp/wt-X commit -m wip-<step>`），每步在 `progress.md` 追加"测了什么、故意没测什么、坏了什么"。
2. 写机制 delta + 薄 launcher（`NETWORK=` / `MODE={mve,full}` 旗；负对照臂在内；`run_cmd` 不自带 `SMOKE=`）。
3. smoke：`smoke_cmd`，产物只落 `smoke/`、带 NOT_A_RESULT；不到 eval 不算过。
4. SELF_CHECK 7 条 grep（refs/self-check.md 原文）→ `build/X/self_check.json`：`[{"check","result","pass"}]`，result 为 grep 输出逐字；自审发现 → `blockers.json`：`[{"text","resolution"}]`。
5. 落 diff：`git -C /tmp/wt-X add -A && git -C /tmp/wt-X diff --cached > .research/build/X/diff.patch`；`deviation_notes.json` 每条带理由；最后 `touch .research/build/X/gate_passed`（导航器靠它知道 build 完成；任何 review 打回都会删掉它）。
6. 修复再入（review 给了 blocking）：只改 finding 锚点指向的地方；回避式补丁 = abandon 不是 fix（refs/obstacle.md）；重写模式从干净树开始、带教训不带文件。

→ 下一步：`/exp-critic <X> code`。
