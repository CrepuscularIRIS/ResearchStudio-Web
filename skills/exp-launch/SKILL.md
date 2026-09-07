---
name: exp-launch
description: "Experiment step 3 — launch the block by script only (launch.sh): zero-tolerance greps, spec gates over the diff, GPU pre-flight, systemd-run + launch_wrap (smoke canary, watchdog, ETA 2×, early-kill). Use when the code review passed and the user says launch / 发射 / 跑."
---

# exp-launch — 发射是脚本，0 token

硬核（≤10 行，每条有出处）
1. 另一进程跑三条零容忍 grep（test_half / eval_entry_diff / gt_escape），builder 的话不算数（V8 launch 席；ARFT R3）。
2. `ALWAYS check GPU availability first — never blindly assign GPUs`；free = memory.used < 500 MiB（ARIS run-experiment）。
3. 每个实验自己的 unit，`tee`/journal 留日志；报告 GPU、命令、ETA（ARIS run-experiment Key Rules）。
4. smoke 先于任何 GPU 小时：canary 不在容差内 exit 3（launch_wrap）；ETA 2× 熔断 exit 5；early-kill exit 4（ARIS training-check "don't wait forever"）。
5. `blockers.json` 未清或 `self_check.json` 有 fail → 不发射（F.4 第一道线）。

步骤
1. 确认 `build/X/route.json` 的 code 模式为 pass。
2. `bash .research/tools/exp/launch.sh <X> /tmp/wt-<X> [GPU]`（`DRY_RUN=1` 只打印 systemd-run 行）；exit 2 = BLOCKED，按打印的计数回 `/exp-build`，绝不改 grep。
3. 记录：`systemctl --user is-active research-<X>`；日志 `journalctl --user -u research-<X> -f`。
4. 等待用 `Monitor`/`systemctl --user is-active` 轮询，不 sleep 不猜 ETA。训练中途只按 ARIS training-check 的判读表行事（`~/oss/aris/skills/training-check/SKILL.md` Step 2，逐字）：

| Signal | Judgment | Action |
|--------|----------|--------|
| NaN/Inf in loss | **Clearly bad** | Stop training, investigate |
| Loss diverging (increasing for >N steps) | **Clearly bad** | Stop training, investigate |
| Eval metrics significantly worse than baseline | **Clearly bad** | Stop training, investigate |
| Loss decreasing, metrics improving | **Clearly fine** | Continue, increase check interval |
| Loss flat but not diverging | **Unsure** | → Step 3 (Codex judgment) |
| Metrics noisy, can't tell trend | **Unsure** | → Step 3 (Codex judgment) |
| Slightly worse than baseline but still early | **Unsure** | → Step 3 (Codex judgment) |

   "Unsure" 走外部：`grok -p` 一次，回答只许 STOP / CONTINUE / WAIT（training-check Step 3 的合同）；`Do not stop training on first sign of noise — some loss spikes are normal. Look at trends over multiple checkpoints.` NaN / 发散 / 停更由 launch_wrap 自己杀（exit 5），不必人盯。

→ unit 结束后：`/exp-verdict <X>`。
