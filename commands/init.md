---
description: Install the claim loop into this project (.research/ scripts, launcher, paper-search skill, templates, GOAL.md block, CLAUDE.md, Workflow allow rules)
allowed-tools: Bash(python3:*), Read
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_research.py"` from the project root and show its output. Then tell the user which GOAL.md fields to fill, that `.research/anomalies.md` must list the project's measured findings before the mechanism stage, and that the first command afterwards is `python3 .research/stage.py`.
