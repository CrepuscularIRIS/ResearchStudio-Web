---
name: exp-critic
description: "Experiment review — the cross-family reviewer (Grok CLI, read-only) in one of three modes: spec (before code), code (before launch), process (after the run); then anchor_check.py validates anchors and routes with zero discretion. Use when the user says review / 审 / critic / 审查."
---

# exp-critic — 换族审查 + 锚点核验 + 路由（GLM 只递路径，不判）

硬核（≤10 行，每条有出处）
1. `The executor collects file paths. The external reviewer backend reads code and judges integrity. The executor does NOT participate in integrity judgment.`（ARIS experiment-audit）
2. 不递总结、不递解读、不递上一轮反馈（ARIS reviewer-independence "What CANNOT be passed"）。
3. 审者失联 = blocked，不是跳过（ARIS result-to-claim "Fail closed if the reviewer is unavailable"；acceptance-gate）。
4. 判决由脚本从 findings 算，审者不自评 survived（ARIS kill-argument；worker §2 D6）。
5. 缺锚点的 finding 降 advisory；L4 只许 A.5 / A.6 / D.4 且需第二票（V8 判决书）。
6. 三个模式同一合同文件 `.research/tools/exp/critic.md`（全部由原文切片拼成，`build_critic_md.py` 可重生成）。

步骤
1. `python3 .research/tools/exp/critic.py <X> --mode spec|code|process [--worktree /tmp/wt-X]`
   - 写 `build/X/findings/<mode>.request.json`（路径清单）、`<mode>.prompt.md`，调 `grok --prompt-file … --output-format json --json-schema … --permission-mode plan`（只读，和 grok 插件同参数），落 `findings/<mode>.json`；失败 → `{"status":"critic_failed"}`。
   - 第二票（仅 L4）：`--second` 走 `moa.sh review`（Kimi-K3）。
2. `python3 .research/tools/exp/anchor_check.py <X> --mode <mode>` → `build/X/route.json`，读它的 `next`：
   - spec：pass → `/exp-build`；L2 → `failure_card.py <X>` 回 Brain。
   - code：pass → `/exp-launch`；blocked → `/exp-build` fix（帽 2+1，超帽 → 回 Brain）。
   - process：survived → `/exp-next`；L0/L1 → `/exp-build` fix；L2–L4 → `failure_card.py`；critic_failed → 重跑本步，永不 survived。
3. 不与 finding 争论：blocking 只能在代码里解决或写进 `blockers.json` 的 resolution；解决后重跑同一模式。
