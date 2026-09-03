# Acceptance — before the first real GPU run

1. `python3 -m pytest tests -q` in the plugin: green. `python3 .research/stage.py` in the project prints STAGE A (no CLAIM.md) or R.
2. Identity: dispatch each lane once through its workflow with a trivial bundle; `.research/IDENTITY-MISMATCH` must not appear.
3. Lock: a second session in the same project prints READ-ONLY and `bin/run_protected.sh x <card> 1G true` is refused.
4. Launcher: with a frozen test card whose worktree exists and a token naming its sha, `GPU=<n> bin/run_protected.sh <card> <card> 1G "echo ok"` starts a unit whose ledger stop line carries `exit`; without the token it is refused.
5. Watchdog: a fake kill_cmd that writes `progress.json` with `fraction 0.3, dev_gain -1` is killed with exit 4 and a synthetic `seed_0.json` (`early_kill: true`); one that never writes progress.json is killed with exit 5 after `stall_min`.
6. First live iteration on ONE chain only; open the second chain after the first record.
