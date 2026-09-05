---
description: One turn of the V8 main loop — run dag.py next and act on exactly the one line it prints (the unattended driver is /goal around this)
allowed-tools: Bash(python3:*), Bash(bash:*), Bash(git:*), Bash(systemctl:*), Read, Write, Workflow
---
1. Run `python3 .research/dag.py next`. It prints ONE line.
2. `WORKFLOW: <name> args=<path>` → Read the args file, call `Workflow({ name: "<name>", args: <the file's JSON object> })`, write the return JSON to `.research/bundles/out-<name>-<n>.json`, run `python3 .research/dag.py put <name> <that file>`. `WAIT: <unit>` → Monitor `systemctl --user is-active <unit>` (or ScheduleWakeup ≥ 20 min). `STOP:` → report the reason and stop. `RETRY:` → wait ~1 min, run `next` again. `REJECT:` → stop and report; never patch objects by hand.
3. Print `python3 .research/dag.py board` and stop. Never reason about the science, never summarise a report, never type a number.
Unattended: `/goal "python3 .research/dag.py next prints STOP; print the board every turn; or stop after 60 turns"`.
