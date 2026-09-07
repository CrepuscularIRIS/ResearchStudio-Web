---
description: Install the V9 harness into this project (Brain workflow, the seven exp-* skills, .research/tools, tests, the verbatim prompt bank under docs/refs, GOAL.md / instruments / args.json templates)
allowed-tools: Bash(python3:*), Read
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_research.py" --slug <topic-slug> --repo <absolute path of the code repository the ideas must run in>` from the project root and show its output. Then tell the user, in this order: fill every field of `.research/GOAL.md` `## FROZEN`; paste that block into `<root>/args.json` → `goal` and fill `dataset` / `venue`; put the clean canary number into `.research/instruments/README.md`; write `.research/anomalies.md` (measured facts no paper explains; may be empty); then `/exp-auto <root>` from a session whose model ids resolve (claude-kimi).
