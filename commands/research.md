---
description: One turn of the claim loop — run stage.py and execute exactly the step.py action it prints for each chain (the unattended driver is /goal around this)
allowed-tools: Bash(python3:*), Bash(bash:*), Bash(git:*), Bash(systemctl:*), Read, Write, Workflow
---
1. Run `python3 .research/stage.py`.
2. For each chain, execute exactly the line it prints: a `step.py` action, a `Workflow(name=..., args=<contents of the args file>)` call followed by saving the returned JSON where the line says and running the `--finish` it names, a `bundle.py queue`, or a wait (use Monitor on `systemctl --user is-active research-<run>.service` or ScheduleWakeup ≥ 20 min).
3. Print `python3 .research/stage.py board` and stop. Never reason about the science, never summarise a report, never type a number.
Unattended: `/goal "python3 .research/stage.py prints STAGE D or STAGE P; print the board every turn; or stop after 60 turns"`.
