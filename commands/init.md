---
description: Install the V8 pipeline into this project (.research/dag.py + tools, the three workflows, paper-search skill, harness.json, GOAL.md skeleton, substrate.json, CLAUDE.md, Workflow allow rules)
allowed-tools: Bash(python3:*), Read
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_research.py"` from the project root and show its output. Then tell the user: fill every field of `.research/GOAL.md` `## FROZEN`; put absolute paths and the canary number in `.research/substrate.json`; set `exp_repo` and `rs_ref` in `.research/harness.json`; the first command afterwards is `python3 .research/dag.py next`.
