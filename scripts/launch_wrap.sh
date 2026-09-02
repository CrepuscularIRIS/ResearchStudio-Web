#!/usr/bin/env bash
# Runs INSIDE the systemd unit. Usage: launch_wrap.sh <ledger> <run> <card-id> -- <command...>
set -uo pipefail
LEDGER="$1"; RUN="$2"; CARD="$3"; shift 3; [ "${1:-}" = "--" ] && shift
T0=$(date +%s)
"$@"; RC=$?
T1=$(date +%s)
printf '{"event": "stop", "run": "%s", "card": "%s", "wall_s": %d, "exit": %d, "t": "%s"}\n' \
  "$RUN" "$CARD" "$((T1 - T0))" "$RC" "$(date -Iseconds)" >> "$LEDGER"
exit $RC
