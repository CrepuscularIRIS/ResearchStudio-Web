LANE: scientist
BRIEF: .research/briefs/scientist-<cycle>.md
REQUIRED READING: .claude/skills/statistical-power/SKILL.md ; .claude/skills/ablation-planner/SKILL.md
INPUTS: GOAL.md ; .research/bridges/<cycle>.md ; .research/lit/<cycle>-*.md ; .research/records/*.json ; seed_sd=<from records or GOAL>
MODE: CARDS (1–3) | DIAGNOSIS <record path> <code paths>
BUDGET: ≤12 tool calls (CARDS) / ≤20 (DIAGNOSIS); write each card on completion; no codebase reads in CARDS
OUTPUT: .research/cards/C-<nnnn>.json ... ; report .research/reports/scientist-<cycle>.md
STATUS: DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED <report path>
