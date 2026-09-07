#!/usr/bin/env bash
# Runs INSIDE the systemd unit. Usage: launch_wrap.sh <run> <card-id> -- <command...>
# Phase 1 (unless SMOKE_FIRST=0): SMOKE=1 SEED=0 RESULTS_DIR=$RESULTS_DIR/smoke (≤1% data); the canary in its seed_0.json must
#   land within tol or the unit exits 3 before any GPU-hour is spent.
# Phase 2: once per seed in $SEEDS with SMOKE=0, under a WATCHDOG (cut losses early, by script, never by Main):
#   the command writes $RESULTS_DIR/progress.json = {fraction, dev_gain, clean_dev, loss, t} at every eval checkpoint;
#   at fraction >= EARLY_AT[i] with dev_gain < EARLY_MIN[i] → the run is killed (exit 4, early kill = a scientific kill, recorded);
#   no progress update for STALL_MIN minutes, or loss NaN → exit 5 (infrastructure failure, not a verdict).
#   An early kill writes a synthetic seed file (value = last dev_gain, early_kill = true) so the record gate can render it.
set -uo pipefail
RUN="$1"; CARD="$2"; shift 2; [ "${1:-}" = "--" ] && shift
LEDGER="$(dirname "$(readlink -f "$0")")/ledger.jsonl"
T0=$(date +%s); RC=0; MAIN_DIR="${RESULTS_DIR:?RESULTS_DIR unset}"
EARLY_AT="${EARLY_AT:-0.25,0.5}"; EARLY_MIN="${EARLY_MIN:-0.0,0.25}"; STALL_MIN="${STALL_MIN:-45}"

if [ "${SMOKE_FIRST:-1}" = "1" ]; then
    mkdir -p "$MAIN_DIR/smoke"
    SMOKE=1 SEED=0 RESULTS_DIR="$MAIN_DIR/smoke" bash -c "$*"; RC=$?
    if [ "$RC" -eq 0 ]; then
        python3 - "$MAIN_DIR/smoke/seed_0.json" <<'EOF' || RC=3
import json, os, sys
try:
    d = json.load(open(sys.argv[1])); c = dict(d["canary"])
    # the bar comes from the FROZEN spec (exported by run_protected.sh), never from the run under test (paperjury: no agent echoes its own criterion)
    if os.environ.get("CANARY_EXPECTED") not in (None, "", "-"):
        c["expected"] = float(os.environ["CANARY_EXPECTED"]); c["tol"] = float(os.environ["CANARY_TOL"])
    ok = abs(float(c["observed"]) - float(c["expected"])) <= float(c["tol"])
    print(f"[smoke] canary expected {c['expected']} observed {c['observed']} tol {c['tol']} -> {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
except Exception as e:
    print(f"[smoke] canary unreadable: {e}"); sys.exit(1)
EOF
    else
        echo "[smoke] command exited $RC"
    fi
fi

watchdog() {   # $1 = pid of the training command, $2 = seed, $3 = seed start time
    local pid="$1" seed="$2" seed_t0="${3:-$(date +%s)}" last_t0 last_mtime now mtime
    last_t0=$(date +%s); last_mtime=0
    while kill -0 "$pid" 2>/dev/null; do
        # a finished-but-unreaped child is a ZOMBIE — kill -0 succeeds on zombies, which
        # used to spin this loop until STALL_MIN overwrote the real exit code with 5.
        state=$(ps -p "$pid" -o stat= 2>/dev/null || echo "")
        if [ "$state" = "Z" ] || [ -z "$state" ]; then break; fi
        sleep 60
        now=$(date +%s)
        # 2× estimated-time circuit breaker (ARIS: "don't wait forever — flag it and move on")
        if [ "${ETA_MAX_S:-0}" -gt 0 ] && [ $((now - seed_t0)) -ge "${ETA_MAX_S}" ]; then
            echo "[watchdog] ETA — run exceeded ${ETA_MAX_S}s (2× estimate); killing"; kill "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null; return 5
        fi
        if [ -f "$MAIN_DIR/progress.json" ]; then
            mtime=$(stat -c %Y "$MAIN_DIR/progress.json" 2>/dev/null || echo 0)
            [ "$mtime" != "$last_mtime" ] && { last_mtime=$mtime; last_t0=$now; cat "$MAIN_DIR/progress.json" >> "$MAIN_DIR/progress.jsonl" 2>/dev/null; echo >> "$MAIN_DIR/progress.jsonl"; }
            verdict=$(python3 - "$MAIN_DIR/progress.json" "$EARLY_AT" "$EARLY_MIN" "$MAIN_DIR/progress.jsonl" <<'EOF'
import json, math, sys
try:
    p = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
f = float(p.get("fraction") or 0); g = p.get("dev_gain"); loss = p.get("loss")
if loss is not None and (isinstance(loss, float) and math.isnan(loss)):
    print("stall:loss NaN"); sys.exit(0)
# divergence (training-check): loss rising across 3 consecutive checkpoints = clearly bad
try:
    vals = []
    for l in open(sys.argv[4]):
        l = l.strip()
        if l:
            try: vals.append(json.loads(l).get("loss"))
            except Exception: pass
    vals = [v for v in vals[-4:] if isinstance(v, (int, float)) and not math.isnan(v)][-3:]
    if len(vals) == 3 and vals[0] < vals[1] < vals[2]:
        print(f"stall:loss diverging across 3 checkpoints {vals}"); sys.exit(0)
except Exception:
    pass
if g is None:
    sys.exit(0)
for at, mn in zip(sys.argv[2].split(","), sys.argv[3].split(",")):
    if f >= float(at) and float(g) < float(mn):
        print(f"early:fraction {f:.2f} dev_gain {float(g):.3f} < {float(mn)} (at >= {at})"); sys.exit(0)
EOF
)
            case "$verdict" in
                early:*) echo "[watchdog] EARLY KILL seed $seed — ${verdict#early:}"; echo "{\"seed\": $seed, \"reason\": \"${verdict#early:}\", \"t\": \"$(date -Iseconds)\"}" > "$MAIN_DIR/early_kill.json"; kill "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null; return 4 ;;
                stall:*) echo "[watchdog] STALL — ${verdict#stall:}"; kill "$pid" 2>/dev/null; return 5 ;;
            esac
        fi
        if [ $((now - last_t0)) -ge $((STALL_MIN * 60)) ]; then
            echo "[watchdog] STALL — no progress.json update for $STALL_MIN min"; kill "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null; return 5
        fi
    done
    return 0
}

if [ "$RC" -eq 0 ]; then
    IFS=',' read -r -a SEED_LIST <<< "${SEEDS:-0}"
    for s in "${SEED_LIST[@]}"; do
        export SEED="$s"; export SMOKE=0; export RESULTS_DIR="$MAIN_DIR"
        rm -f "$MAIN_DIR/progress.json" "$MAIN_DIR/progress.jsonl"
        SEED_T0=$(date +%s)
        bash -c "$*" & CMD_PID=$!
        watchdog "$CMD_PID" "$s" "$SEED_T0"; WRC=$?
        wait "$CMD_PID"; CRC=$?
        if [ "$WRC" -eq 4 ]; then
            python3 - "$MAIN_DIR" "$s" <<'EOF'
import json, os, sys, pathlib
d = pathlib.Path(sys.argv[1]); s = int(sys.argv[2])
p = json.load(open(d / "progress.json")) if (d / "progress.json").exists() else {}
smoke = d / "smoke" / "seed_0.json"
can = json.load(open(smoke)).get("canary") if smoke.exists() else {"expected": 0, "observed": 0, "tol": 0}
seed = {"seed": s, "metric": os.environ.get("CARD_METRIC") or p.get("metric", "dev_gain"), "value": float(p.get("dev_gain") or 0.0), "clean_cost": float(p.get("clean_dev_cost") or 0.0),
        "canary": can, "checkpoint_loaded_frac": float(p.get("checkpoint_loaded_frac") or 1.0), "artifacts": [str(d / "progress.json")],
        "early_kill": True, "fraction": p.get("fraction")}
(d / f"seed_{s}.json").write_text(json.dumps(seed, indent=1))
if not (d / "blockers.json").exists():
    (d / "blockers.json").write_text("[]")
EOF
            RC=4; break
        fi
        RC=$([ "$WRC" -eq 5 ] && echo 5 || echo "$CRC")
        [ "$RC" -eq 0 ] || break
    done
fi
T1=$(date +%s)
printf '{"event": "stop", "run": "%s", "card": "%s", "wall_s": %d, "exit": %d, "seeds": "%s", "t": "%s"}\n' \
  "$RUN" "$CARD" "$((T1 - T0))" "$RC" "${SEEDS:-0}" "$(date -Iseconds)" >> "$LEDGER"
# per-experiment copies where the judge reads them (build/<X>/): exit_code first, ledger as fallback.
# P0#1: without these the judge's GLM seat finds neither file and invents an exit code.
mkdir -p "$MAIN_DIR/.."
echo "$RC" > "$MAIN_DIR/../exit_code"
printf '{"event": "stop", "run": "%s", "card": "%s", "wall_s": %d, "exit": %d, "seeds": "%s", "t": "%s"}\n' \
  "$RUN" "$CARD" "$((T1 - T0))" "$RC" "${SEEDS:-0}" "$(date -Iseconds)" >> "$MAIN_DIR/../ledger.jsonl" 2>/dev/null || true
exit $RC
