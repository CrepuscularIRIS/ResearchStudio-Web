---
name: exp-spec
description: "Experiment step 1.5 — draft ONE block spec (spec/B<k>.json) on the Worker side under the Brain's Phase 6 contract, then pass spec_check.py with PLAN ⊆ SPEC binding; the Brain no longer writes specs. Use when next.py says a block has no spec yet, or the user says 写 spec / 起草 / draft spec."
---

# exp-spec — 出题人出题（evidence_plan），解题人列卷（spec/B<k>.json），第三方核卷（Grok）

硬核（≤10 行，每条有出处）
1. 合同就是 Brain 原来的 Phase 6 提示词，逐字：`.research/tools/exp/refs/spec_contract.md`；ASI 三件在 `docs/refs/papers/asi-bench/`（task.yaml 的 gates 形式、prompt_b1.md 的完备度、how-scoring-works 的"自报分数不算数"）。
2. **PLAN ⊆ SPEC**（`spec_check.py --plan`，确定性）：keep_if_all 的数字只能来自本块的 keep_rule；kill_condition 是计划里的一条；forbids 覆盖 frozen_untouched；负对照臂就是计划里的负对照。你只补工程字段（改哪个文件、run_cmd、smoke_cmd、gates、decision_points 的默认值），科学决定一个都不改——改了就是 L2（回 Brain），不是你的权限（ARFT R3：被验者不能控制验证）。
3. substrate.md 是事实源，REPOSITORY MAP 定位文件，Read 只用来确认将要点名的函数/行；不许 Glob/Grep 探索仓库（ccf 那次 94 次工具调用 53 分钟就是这么来的）。
4. 块自己要创建的文件写 `"function": "NEW file"`，且目录存在；run_cmd 用仓库现成的 launcher，永远不自己设 SMOKE；一个 outputs 一条 file_exists 门，一个 forbids 一条 forbidden_* 门，数值结果文件都有 no_nan_inf。
5. 一次只写一块（懒出块）：B1 死了 B2–B5 的合同就不用写。
6. 修复只改 spec_check 点名的项，其余字节不动（cap 2）。
7. 无法在不做科学决定的情况下写出来 → 写 `"blocked": "<why>"`，precheck 会以 exit 3 路由回 Brain。

STEP 0 读单
- `python3 .research/tools/exp/spec_packet.py <run_root> --run <r> --block <Bk> --repo <repo>` 生成 `spec/<Bk>.packet.md`——这是你唯一要读的计划/方法/可实现性视图（含 FROZEN、substrate、intake、仓库地图）。
- `.research/tools/exp/refs/spec_contract.md`（合同）；ASI 三件按需。

步骤
1. 跑 spec_packet.py，Read 打印出的 packet 路径（整份读完）。
2. 按合同写 `<run>/spec/<Bk>.json`（JSON，无其他内容）。需要确认某个函数/行时才 Read 那个文件。
3. 跑 packet 输出里 `then` 给的那条 `spec_check.py ... --block <Bk> --plan ...`；`__SPEC_BAD` → 只修点名项再跑（最多 2 次）；`__SPEC_OK` 才算完。
4. `python3 .research/tools/exp/next.py <run_root>` → 它会给 `/exp-next`（领取 + 封印），之后 `/exp-critic X spec`（Grok 跨族审）。

→ 下一步：`/exp-next <run_root> --run <r> --block <Bk>`
