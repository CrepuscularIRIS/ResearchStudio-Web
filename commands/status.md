---
description: Render and show the campaign views (hypotheses, results, decisions, budget)
allowed-tools: Bash(python3:*), Read
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" views && python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" budget`, then read `.research/views/HYPOTHESES.md`, `RESULTS.md`, `DECISIONS.md` and summarise the state in at most ten lines. Do not interpret results; state them.
