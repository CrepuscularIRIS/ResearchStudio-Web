LANE: builder
BRIEF: .research/briefs/builder-<card>.md
REQUIRED READING: .claude/skills/experiment-bridge/SKILL.md
INPUTS: .research/cards/<card>.json ; worktree=<path> ; eval_cmd=<from GOAL.md> ; protected=<from GOAL.md>
MODE: ORACLE | FULL | GRID
OUTPUT: results/<run>/seed_<k>.json + blockers.json ; report .research/reports/builder-<card>.md
STATUS: DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED <report path>
