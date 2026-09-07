---
name: exp-auto
description: "Auto mode — the main window drives the whole pipeline (Brain workflow → experiment blocks → tables) by asking next.py what the next step is and doing exactly that, until SUPPORTED, BLOCKED or WAIT. Use with /loop for GPU waits: `/loop 10m /exp-auto <run_root>`. Use when the user says auto / 自动 / 流水线 / pipeline / 跑起来."
---

# exp-auto — 导航器说什么，做什么；没有别的裁量

硬核（≤10 行，每条有出处）
1. 下一步由 `next.py` 从盘上状态算出（纯函数：台账 + build 目录 + unit 状态），主窗口不自己判断阶段（RS `run.py next` 的做法；worker 设计 D2：只留纯函数脚本，无 dag 总线）。
2. 每个 SKILL 步在它自己的 skill 里做完并落盘；驱动环不 Read 任何产物到上下文（RS context discipline Rule 1–2）。
3. `schedule the wait, never the verdict.`（ARIS external-cadence 原句）WAIT = GPU 在跑：用 `/loop 10m /exp-auto <run_root>` 或 `Monitor systemctl --user is-active research-<X>`，不 sleep 不猜 ETA（ARIS "don't wait forever" 由 launch_wrap 的 ETA 熔断执行）。
4. BLOCKED = 需要 owner（Brain 重触发超过 `args.max_brain_rounds`（默认 2）、审者失联两次、无规则状态）：报告并停，不绕过（acceptance-gate：DRIVE 不 ACQUIT）。
4b. 失败卡之后的梯子由导航器走，不用问：ranking 的 `backup_run`（0 额度）→ 两边都死 → `retrigger.py`（新根 `<root>-n<round>`，复用 `_shared/`，`args.negative_anchors` = 本根全部失败卡）→ 超帽 BLOCKED。重触发的根带 `retrigger.json`，`/exp-auto <原根>` 自动顺着走到新根（输出里的 ROOT 行）。
5. 同一 emit 连续三次相同 = 卡死：停，报告 `experiments/<X>.json` 与 `route.json`。
6. Brain 阶段只在 claude-kimi 会话里发射 `Workflow`（官方 API 下 GLM/K3 id 会被静默替换）。
7. 已经发射过的不重做：Brain 按盘上产物续跑（完成的阶段永不重跑），同一根上在跑的 Brain 由 `brain.lock` + 45 分钟心跳挡住第二次发射（导航器给 WAIT）；已在跑的 systemd 单元由 `launch.sh` 记回台账而不重发；已过的块、已领的 X、已 gate_passed 的实现都按台账跳过。

环
1. `python3 .research/tools/exp/next.py <run_root> --json`
2. 按 `phase`：
   - `BRAIN` 且有 `skill` → 按 `run` 的三行做：`brain_lock.py <root> acquire`（exit 3 = 已在跑：不发射，当作 WAIT）→ `Workflow({scriptPath: ".claude/workflows/brain.workflow.js", args: <读 <d.root>/args.json>})`（用输出里的 `root`，重触发后它不是你传入的那个）→ 无论返回什么都 `brain_lock.py <root> release`；回到 1。
   - `BRAIN` 且只有 `run` → 执行 `retrigger.py`（建新根 + 写 negative_anchors），回到 1。
   - `EXPERIMENT` 且有 `skill` → 用 Skill 工具调 `/<skill> <skill_args>`；做完回到 1。
   - `EXPERIMENT` 且只有 `run` → 逐条执行命令（失败即停，报告输出）；回到 1。
   - `wait_s > 0` → `/loop 10m /exp-auto <run_root>`（或 Monitor），醒来回到 1。
   - `blocked` → 停，把 `state` 与 `note` 报给 owner。
   - `SUPPORTED` → 执行 `run` 里的 `report.py`，报告 `results_table.md` 路径，停；后续消融按 `evidence_plan.ablations` 的 priority 由 owner 决定是否继续。
3. 每一步后在 `<run_root>/auto.log` 追加一行：时间、phase、state、做了什么（脚本输出的第一行）。
