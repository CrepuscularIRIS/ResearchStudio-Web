LANE: reviewer
BRIEF: .research/briefs/reviewer-<card>.md
REQUIRED READING: .claude/skills/shared-references/reviewer-independence.md ; .claude/skills/shared-references/acceptance-gate.md
INPUTS: MODE=diff <worktree> | MODE=verdict .research/packets/<card>.md | MODE=adversarial <repo> "<focus>"
OUTPUT: .research/verdicts/<card>.codex.json | .research/reports/reviewer-diff-<card>.md
STATUS: DONE|BLOCKED <output path>
