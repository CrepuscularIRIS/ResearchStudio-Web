---
name: exp-verdict
description: "Experiment step 4 — after the unit ends: verdict.py (numeric gate, Type-A) → /exp-critic process (Grok audit) → anchor_check route → survived / fix / failure card. Use when a run finished and the user says verdict / 判 / 结果 / 审结果."
---

# exp-verdict — 数值门先于审者；结果决定去向，不由人解释

硬核（≤10 行，每条有出处）
1. 先跑脚本：exit 5 = infra、3 = canary_fail、4 = early-kill，都不是科学判决，永不 refuted（V8 P0#3 "Infra ≠ verdict"）。
2. `keep_if_all` 逐键对 m158 `verdict.json`，缺键即 fail；CI 含 0 即 fail（V9 dag_verdict）。
3. 负对照命中（`|negctrl_delta − delta| < |delta|/2`）= L3 机制归因死，不是 L0 bug（V8 P1#6）。
4. `too_good`（delta > 3× min_effect）不许 survived，先由审者分解（ARFT J2）。
5. 审者只审过程，不重算数字；`Codex is the judge, not CC. CC collects evidence and routes`（ARIS result-to-claim）。
6. `partial` 不许圆成 `yes`；一个数据集上的一个正结果不支持一般 claim（ARIS result-to-claim Rules）。
7. 数字只从 `verdict.json` 回溯；表格按 CCF result-templates 填，No-Fabrication（CCF K29）。

步骤
1. `python3 .research/tools/exp/verdict.py <X>` → `build/X/verdict.json`，读 `gate` 与 `next`。
   - infra → 同一 build 重发射（第 3 次 infra 当 build 问题）；invalid → 按 reasons 走 L0/L1 修复（`/exp-build`）。
2. survived / killed → `/exp-critic <X> process` → `anchor_check.py <X> --mode process` → `route.json`。
3. survived：更新 `progress.md`，`/exp-next` 领下一块；全部 run_order 过 → supported：`python3 .research/tools/exp/report.py <run_root>` 出 `results_table.md`（CCF result-templates 形状，数字只来自 verdict.json；`Always show raw numbers before interpretation` — ARIS monitor-experiment）；再按 `evidence_plan.ablations` 的 priority 跑消融（同一 launcher，MODE=full，GLM 零设计），每块各自 verdict。
4. killed L0/L1 → `/exp-build` fix；L2/L3/L4 → `python3 .research/tools/exp/failure_card.py <X>` → 失败卡作负锚重触发 Brain。
