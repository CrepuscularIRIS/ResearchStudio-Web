#!/usr/bin/env bash
# Protected launcher — the ONLY way a GPU run starts. Usage:
#   GPU=<n> [SEEDS=0] bin/run_protected.sh <run> <card-id> <mem>G <command...>
# run ∈ {<card>, <card>-confirm}. Refuses unless the card is frozen, gate.py card passes, the GPU has no other research
# unit, and a review token names the frozen sha. The unit (launch_wrap.sh) runs a SMOKE=1 phase first (except -confirm) and
# checks the canary before spending the GPU-hours; exports RESULTS_DIR / SEED / SMOKE, scrubs RESULTS_DIR, caps the wall
# clock at kill.gpu_h × 1.1 + 15 min, runs inside the card's worktree. Writes the ledger start line here; launch_wrap.sh writes the stop line inside the unit.
set -euo pipefail
RUN="${1:?usage: run_protected.sh <run> <card-id> <mem>G <command...>}"
CARD="${2:?card id}"; MEM="${3:?mem, e.g. 30G}"; shift 3
W="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"; R="$W/.research"
CARD_P="$R/cards/$CARD.json"; TOKEN="$R/tokens/$CARD.clean"; UNIT="research-$RUN"
GPU_ID="${GPU:-1}"

[ -f "$CARD_P" ] || { echo "REFUSED: no card $CARD_P" >&2; exit 1; }
read -r SHA WT GPUH CARD_METRIC CANARY_EXPECTED CANARY_TOL < <(python3 - "$CARD_P" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1])); can = ((c.get("spec") or {}).get("canary") or {})
print(c.get("frozen_sha") or "-", c.get("worktree") or "-", float((c.get("kill") or {}).get("gpu_h") or 4), (c.get("prediction") or {}).get("metric") or "-",
      can.get("expected", "-"), can.get("tol", "-"))
EOF
)
CSHA=$(python3 "$R/gate.py" cardsha "$CARD_P" 2>/dev/null || echo "-")
[ "$CSHA" = "$SHA" ] || { echo "REFUSED: card $CARD content sha $CSHA != frozen_sha $SHA (the card was edited after freeze)" >&2; exit 1; }
[ "$SHA" != "-" ] || { echo "REFUSED: card $CARD is not frozen (gate.py freeze)" >&2; exit 1; }
python3 "$R/gate.py" card "$CARD_P" > /dev/null || { echo "REFUSED: gate.py card failed for $CARD" >&2; exit 1; }
[ "$WT" != "-" ] && [ -d "$WT" ] || { echo "REFUSED: card $CARD names no existing worktree ($WT)" >&2; exit 1; }
MAXSEC=$(python3 -c "print(int($GPUH*3600*1.1) + 900)")
read -r EARLY_AT EARLY_MIN STALL_MIN < <(python3 - "$W/CLAIM.md" <<'EOF'
import re, sys, yaml
try:
    m = re.search(r"^```yaml\n(.*?)\n```", open(sys.argv[1], encoding="utf-8").read(), re.S | re.M)
    e = ((yaml.safe_load(m.group(1)) or {}).get("claim") or {}).get("early_stop") or {}
except Exception:
    e = {}
at = ",".join(str(x) for x in (e.get("at") or [0.25, 0.5])); mn = ",".join(str(x) for x in (e.get("min_gain") or [0.0, 0.25]))
print(at, mn, int(e.get("stall_min") or 45))
EOF
)
case "$RUN" in *-confirm) SMOKE_FIRST=0 ;; *) SMOKE_FIRST=1 ;; esac
{ [ -f "$TOKEN" ] && grep -q "$SHA" "$TOKEN"; } || { echo "REFUSED: no review token naming sha $SHA at $TOKEN" >&2; exit 1; }
DSHA=$(python3 "$R/gate.py" diffsha "$WT" 2>/dev/null || echo "-")
{ [ "$DSHA" != "-" ] && grep -q "$DSHA" "$TOKEN"; } || { echo "REFUSED: worktree diff sha $DSHA is not the one the monitor approved (token $TOKEN); code changed after review — re-run the monitor" >&2; exit 1; }
[ -f "$W/.claude/hooks/session-lock.py" ] && { python3 "$W/.claude/hooks/session-lock.py" --check "$$" || exit 1; }
if systemctl --user is-active --quiet "$UNIT.service"; then
    echo "REFUSED: $UNIT.service is already active — never relaunch a running unit" >&2; exit 1
fi
# same-GPU collision: any active research-* unit whose CUDA_VISIBLE_DEVICES equals ours
for u in $(systemctl --user list-units --state=active --plain --no-legend 'research-*.service' 2>/dev/null | awk '{print $1}'); do
    env_line=$(systemctl --user show -p Environment "$u" 2>/dev/null || true)
    case "$env_line" in *"CUDA_VISIBLE_DEVICES=$GPU_ID"*) echo "REFUSED: $u already runs on GPU $GPU_ID" >&2; exit 1 ;; esac
done
# what runs must be what was reviewed: no populated gitlink dirs, no symlinks escaping the worktree, no ignored code files
for gl in $(git -C "$WT" ls-files -s 2>/dev/null | awk '$1=="160000"{print $4}'); do
    [ -d "$WT/$gl" ] && [ -n "$(ls -A "$WT/$gl" 2>/dev/null)" ] && { echo "REFUSED: $gl is a gitlink (nested repo) with content in the worktree: that code is invisible to review — track it as files on research-trunk" >&2; exit 1; }
done
while IFS= read -r lnk; do
    [ -z "$lnk" ] && continue
    tgt=$(readlink -f "$WT/$lnk" 2>/dev/null || true)
    case "$tgt" in "$WT"/*) ;; *) echo "REFUSED: symlink $lnk resolves outside the worktree ($tgt)" >&2; exit 1 ;; esac
done < <(git -C "$WT" ls-files -s 2>/dev/null | awk '$1=="120000"{print $4}'; find "$WT" -maxdepth 3 -type l -not -path '*/results/*' -not -path '*/.git/*' -printf '%P\n' 2>/dev/null)
IGN=$(git -C "$WT" status --ignored --porcelain 2>/dev/null | awk '$1=="!!"{print $2}' | grep -Ev '^(results/|logs/|__pycache__/|.*/__pycache__/|.*\.(pth|pt|log)$)' | grep -E '\.(py|yaml|yml|json|sh)$' || true)
[ -z "$IGN" ] || { echo "REFUSED: ignored code files present in the worktree (they would run but were never in the reviewed diff): $(echo "$IGN" | head -5 | tr '\n' ' ')" >&2; exit 1; }
RESULTS_DIR="$WT/results/$RUN"
case "$RUN" in *-confirm) mkdir -p "$RESULTS_DIR" ;; *) rm -rf "$RESULTS_DIR"; mkdir -p "$RESULTS_DIR" ;; esac
printf '{"event": "start", "run": "%s", "card": "%s", "gpu": "%s", "mem": "%s", "seeds": "%s", "smoke_first": %s, "t": "%s"}\n' \
  "$RUN" "$CARD" "$GPU_ID" "$MEM" "${SEEDS:-0}" "$SMOKE_FIRST" "$(date -Iseconds)" >> "$R/ledger.jsonl"
exec systemd-run --user --unit="$UNIT" --collect \
    -p "MemoryMax=$MEM" -p "WorkingDirectory=$WT" -p "RuntimeMaxSec=$MAXSEC" \
    -E "CUDA_VISIBLE_DEVICES=$GPU_ID" -E "RESULTS_DIR=$RESULTS_DIR" -E "SMOKE_FIRST=$SMOKE_FIRST" -E "SEEDS=${SEEDS:-0}" \
    -E "EARLY_AT=$EARLY_AT" -E "EARLY_MIN=$EARLY_MIN" -E "STALL_MIN=$STALL_MIN" -E "CARD_METRIC=$CARD_METRIC" \
    -E "CANARY_EXPECTED=$CANARY_EXPECTED" -E "CANARY_TOL=$CANARY_TOL" \
    bash "$R/launch_wrap.sh" "$RUN" "$CARD" -- "$@"
