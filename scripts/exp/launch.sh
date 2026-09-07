#!/usr/bin/env bash
# launch.sh <X> <worktree> [GPU]  — the launch step is a SCRIPT (0 model tokens; V8 D7 / ARFT R3: verification the agent does not control).
#   1 zero-tolerance greps over diff.patch (V8 launch seat, verbatim patterns) + spec.gates forbidden_* + spec.forbids literals
#   2 blockers.json empty or every blocker resolved; self_check.json every check pass (F.4: a named flaw that shipped = blocked)
#   3 nvidia-smi pre-flight (ARIS run-experiment: free GPU = memory.used < 500 MiB)
#   4 systemd-run (run_protected: MemoryMax, GPU pinned) → launch_wrap.sh (smoke canary → seeds under watchdog, ETA 2×, early-kill)
# DRY_RUN=1 prints the systemd-run line instead of running it. Exit 2 = blocked (counts printed), 0 = launched.
set -uo pipefail
X="${1:?usage: launch.sh <X> <worktree> [GPU]}"; WT="${2:?worktree}"; GPU="${3:-${GPU:-1}}"; MEM="${MEM:-30G}"
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"; RESEARCH="$(cd "$HERE/../.." && pwd)"
SB="${EXP_SANDBOX:-$RESEARCH}"; BD="$SB/build/$X"; SPEC="$BD/spec.json"; DIFF="$BD/diff.patch"; LEDGER_DIR="$SB/experiments"
[ -f "$SPEC" ] || { echo "BLOCKED: $SPEC missing (run precheck first)"; exit 2; }
[ -f "$DIFF" ] || { echo "BLOCKED: $DIFF missing — stage the diff first: git -C $WT add -A && git -C $WT diff --cached > $DIFF"; exit 2; }
# ---- 1. greps (scope = diff.patch, the seat's own delta; the worktree carries the frozen instrument library — X-014 false-positive lesson)
a=$(grep -c 'cal_test\|test_half' "$DIFF" 2>/dev/null || echo 0)
b=$(grep -c '^+++ .*m152_eval_rungs.py' "$DIFF" 2>/dev/null || echo 0)
c=$(grep -cE '(\.\./)+(labels?|gt|ground_truth)' "$DIFF" 2>/dev/null || echo 0)
echo "grep test_half=$a eval_entry_diff=$b gt_escape=$c"
blocked=0; [ "$a" -gt 0 ] && blocked=1; [ "$b" -gt 0 ] && blocked=1; [ "$c" -gt 0 ] && blocked=1
while IFS= read -r line; do
  kind="${line%%|*}"; pat="${line#*|}"; [ -z "$pat" ] && continue
  if [ "$kind" = re ]; then n=$(grep -cE -- "$pat" "$DIFF" 2>/dev/null || echo 0); else n=$(grep -cF -- "$pat" "$DIFF" 2>/dev/null || echo 0); fi
  echo "gate $kind '$pat' = $n"; [ "$n" -gt 0 ] && blocked=1
done < <(python3 - "$SPEC" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for g in d.get("gates") or []:
    if not isinstance(g, dict): continue
    cfg = g.get("config") or {}
    if g.get("check") == "forbidden_pattern" and cfg.get("pattern"): print("re|" + cfg["pattern"])
    if g.get("check") == "forbidden_import":
        for imp in cfg.get("imports") or []: print("re|^\\+.*(import|from)\\s+" + imp)
for f in d.get("forbids") or []:
    if isinstance(f, str) and f.strip(): print("lit|" + f.strip())
PY
)
# ---- 2. blockers / self_check
python3 - "$BD" <<'PY' || blocked=1
import json, sys, pathlib
bd = pathlib.Path(sys.argv[1]); ok = True
bl = json.loads((bd / "blockers.json").read_text()) if (bd / "blockers.json").exists() else None
if bl is None: print("BLOCKED: blockers.json missing (an empty list is a claim that you found none)"); ok = False
else:
    un = [b for b in bl if isinstance(b, dict) and not b.get("resolution")]
    if un: print("BLOCKED: unresolved blockers: " + "; ".join(str(b.get("text"))[:80] for b in un)); ok = False
sc = json.loads((bd / "self_check.json").read_text()) if (bd / "self_check.json").exists() else None
if not sc: print("BLOCKED: self_check.json missing or empty (SELF_CHECK 7 greps)"); ok = False
else:
    bad = [c for c in sc if isinstance(c, dict) and c.get("pass") is not True]
    if bad: print("BLOCKED: self_check failed: " + "; ".join(str(c.get("check"))[:60] for c in bad)); ok = False
sys.exit(0 if ok else 1)
PY
[ "$blocked" -eq 1 ] && { echo "BLOCKED — resolve in code, never by editing the greps"; exit 2; }
# ---- 2b. already running? (a crash between systemd-run and the ledger write leaves the unit alive and the ledger behind — record, never relaunch)
mark_launched() {
python3 - "$RESEARCH" "$X" "$WT" "$DIFF" <<'PY'
import json, sys, hashlib, pathlib, datetime, os
research, x, wt, diff = sys.argv[1:5]
p = pathlib.Path(os.environ.get("EXP_SANDBOX") or research) / "experiments" / f"{x}.json"; d = json.loads(p.read_text()) if p.exists() else {"id": x}
d.update({"status": "launched", "unit": f"research-{x}", "worktree": wt, "launched_at": d.get("launched_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
          "diff_sha": hashlib.sha256(pathlib.Path(diff).read_bytes()).hexdigest()})
p.write_text(json.dumps(d, indent=1))
PY
}
if [ "${DRY_RUN:-0}" != 1 ] && systemctl --user is-active --quiet "research-$X" 2>/dev/null; then
  mark_launched; echo "research-$X is already active — ledger set to launched, nothing relaunched; wait for the unit, then: /exp-verdict $X"; exit 0
fi
# ---- 3. GPU pre-flight
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU" 2>/dev/null | head -1 | tr -d ' ')
if [ -n "${used:-}" ] && [ "${DRY_RUN:-0}" != 1 ] && [ "$used" -ge 500 ]; then echo "BLOCKED: GPU $GPU busy (memory.used=${used} MiB ≥ 500)"; exit 2; fi
# ---- 4. launch
RUN_CMD=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['run_cmd'])" "$SPEC")
SEEDS=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(','.join(str(s) for s in (d.get('verdict_rule') or {}).get('seeds') or [0]))" "$SPEC")
ETA=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(int(float(d.get('gpu_h') or 0)*3600*2))" "$SPEC")
CAN=""; [ -f "$BD/canary.env" ] && while IFS='=' read -r k v; do [ -n "$k" ] && CAN="$CAN --setenv=$k=$v"; done < "$BD/canary.env"
mkdir -p "$BD/results"
CMD="systemd-run --user --unit=research-$X --working-directory='$WT' -p MemoryMax=$MEM --setenv=RESULTS_DIR='$BD/results' --setenv=SEEDS='$SEEDS' --setenv=ETA_MAX_S=$ETA --setenv=GPU=$GPU --setenv=CUDA_VISIBLE_DEVICES=$GPU$CAN bash '$RESEARCH/tools/launch_wrap.sh' $X $X -- 'cd $WT && $RUN_CMD'"
echo "$CMD"
if [ "${DRY_RUN:-0}" = 1 ]; then echo "DRY_RUN: not launched"; exit 0; fi
eval "$CMD" || { echo "systemd-run failed"; exit 1; }
mark_launched
sleep 2; systemctl --user is-active "research-$X" || true
echo "launched research-$X — wait for the unit to end, then: /exp-verdict $X"
