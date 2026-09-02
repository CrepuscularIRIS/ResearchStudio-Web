#!/usr/bin/env bash
# Protected launcher — the ONLY way a GPU run starts. Usage:
#   GPU=<n> ${CLAUDE_PLUGIN_ROOT}/scripts/run_protected.sh <run> <card-id> <mem>G <command...>
# Refuses unless the card is frozen, gate.py card passes, and a review token names the frozen sha.
# Writes the ledger start line here; launch_wrap.sh writes the stop line inside the unit.
set -euo pipefail
RUN="${1:?usage: run_protected.sh <run> <card-id> <mem>G <command...>}"
CARD="${2:?card id}"; MEM="${3:?mem, e.g. 30G}"; shift 3
PLUGIN="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
W="${CLAUDE_PROJECT_DIR:-$(pwd)}"; R="${RESEARCH_DIR:-$W/.research}"
CARD_P="$R/cards/$CARD.json"; TOKEN="$R/tokens/$CARD.clean"; UNIT="research-$RUN"

[ -f "$CARD_P" ] || { echo "REFUSED: no card $CARD_P" >&2; exit 1; }
SHA=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('frozen_sha') or '')" "$CARD_P")
[ -n "$SHA" ] || { echo "REFUSED: card $CARD is not frozen (gate.py freeze)" >&2; exit 1; }
RESEARCH_DIR="$R" python3 "$PLUGIN/scripts/gate.py" card "$CARD_P" > /dev/null || { echo "REFUSED: gate.py card failed for $CARD" >&2; exit 1; }
{ [ -f "$TOKEN" ] && grep -q "$SHA" "$TOKEN"; } || { echo "REFUSED: no review token naming sha $SHA at $TOKEN" >&2; exit 1; }
CLAUDE_PROJECT_DIR="$W" python3 "$PLUGIN/hooks/session-lock.py" --check "$$" || exit 1
if systemctl --user is-active --quiet "$UNIT.service"; then
    echo "REFUSED: $UNIT.service is already active — never relaunch a running unit" >&2; exit 1
fi
printf '{"event": "start", "run": "%s", "card": "%s", "gpu": "%s", "mem": "%s", "t": "%s"}\n' \
  "$RUN" "$CARD" "${GPU:-1}" "$MEM" "$(date -Iseconds)" >> "$R/ledger.jsonl"
exec systemd-run --user --unit="$UNIT" --collect \
    -p "MemoryMax=$MEM" -p "WorkingDirectory=$(pwd)" \
    -E "CUDA_VISIBLE_DEVICES=${GPU:-1}" \
    bash "$PLUGIN/scripts/launch_wrap.sh" "$R/ledger.jsonl" "$RUN" "$CARD" -- "$@"
