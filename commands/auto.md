---
description: One turn of the V9 loop — ask next.py what the single next step is and do exactly that (Brain workflow · exp-* skill · wait · report BLOCKED)
allowed-tools: Bash(python3:*), Bash(bash:*), Bash(git:*), Bash(systemctl:*), Read, Write, Workflow, Skill
---
This is the project-local `/exp-auto <run_root>` skill (installed by init); use it directly: `/exp-auto <run_root>`. If the skill is missing, run `python3 .research/tools/exp/next.py <run_root> --json` and act on its `phase` exactly as `.claude/skills/exp-auto/SKILL.md` says; never reason about the science, never type a number.
