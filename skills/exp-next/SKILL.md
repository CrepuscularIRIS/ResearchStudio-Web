---
name: exp-next
description: "Experiment step 1 — claim the next block of the top-ranked Brain idea and run every free check before a line of code (precheck.py). Use when starting an experiment, after a block survived, or when the user says 领取 / next block / 开始实验."
---

# exp-next — 领取 + 预检（脚本判，零裁量）

硬核（≤10 行，每条有出处）
1. 设计全在 Brain：`spec/B<k>.json` 是图纸，Worker 不做任何科学决定；留白 = spec 缺陷，回 Brain（Brain spec 合同；ASI B1→B2 −21.8）。
2. 一个 block 一个 X、一个 worktree、一个 `build/X/`；禁区 `instruments/`、受保护 eval、test half（worker 设计 §2 D8）。
3. 预算从 `evidence_plan.total_gpu_h` 扣，超即停（ARFT X.8）。
4. canary 数字来自 `instruments/README.md`，不由模型记忆（V8 P1#8）。
5. spec 的决策字段在这里封印（sha）；之后任何改动 = rule_changed = invalid。

STEP 0 读单：`ranking.json`（rank 1、first_block_to_run、backup_run）· `r?/spec/index.json` · `r?/phase5/evidence_plan.json`（run_order、min_effect、role、failure_interpretation）· `.research/instruments/README.md`。

步骤
1. `python3 .research/tools/exp/precheck.py <run_root> [--run rN] [--block Bk] --repo <repo>`
   - exit 3 = Brain 标了 blocked → 直接 `failure_card.py` 回 Brain，不写代码。
   - exit 1 = `__PRECHECK_BAD …`（spec_check / eval_type / 预算）→ 回 Brain 修 spec，不写代码。
   - exit 0 = 打印 `x_id`、`spec_sha`、canary、worktree 引导命令。
2. 按打印的引导建 worktree：`git worktree add /tmp/wt-<X> -b exp/<X>`，`repos/*` 符号链接与 `.git/info/exclude` 照 `instruments/launcher_reference.sh` STEP 0；复制 `instruments/m15*.py` 到 worktree（m152 保持 byte-identical）。
3. 把 worktree 路径写进台账：`python3 -c "import json,sys;p='.research/experiments/<X>.json';d=json.load(open(p));d['worktree']='/tmp/wt-<X>';json.dump(d,open(p,'w'),indent=1)"`

→ 下一步：`/exp-critic <X> spec`（先审图纸，再动手）。
