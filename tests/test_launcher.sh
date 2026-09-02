#!/usr/bin/env bash
# Smoke test in a temporary project: refuses unfrozen card, refuses without token, then runs a real systemd unit.
set -euo pipefail
PLUGIN="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); cd "$T"; export CLAUDE_PROJECT_DIR="$T"
python3 "$PLUGIN/scripts/init_research.py" > /dev/null
R=$T/.research; CID=C-TEST; RUN=launchtest-$$
python3 - "$CID" "$PLUGIN" <<'PY'
import json, sys, pathlib
sys.path.insert(0, sys.argv[2] + "/tests"); from test_gate import good_card
c = good_card(); c["id"] = sys.argv[1]; c["bridge"] = "bridges/test.md#1"
pathlib.Path(".research/bridges/test.md").write_text("## 1\n"); pathlib.Path(".research/lit/test-1.md").write_text("packet")
pathlib.Path(f".research/cards/{sys.argv[1]}.json").write_text(json.dumps(c, indent=2))
PY
set +e; "$PLUGIN/scripts/run_protected.sh" "$RUN" "$CID" 1G sleep 1 2>/dev/null; rc=$?; set -e
[ $rc -ne 0 ] || { echo "FAIL: launched an unfrozen card"; exit 1; }
python3 "$PLUGIN/scripts/gate.py" freeze "$R/cards/$CID.json" > /dev/null
set +e; "$PLUGIN/scripts/run_protected.sh" "$RUN" "$CID" 1G sleep 1 2>/dev/null; rc=$?; set -e
[ $rc -ne 0 ] || { echo "FAIL: launched without a review token"; exit 1; }
python3 -c "import json;print(json.load(open('$R/cards/$CID.json'))['frozen_sha'])" > "$R/tokens/$CID.clean"
"$PLUGIN/scripts/run_protected.sh" "$RUN" "$CID" 1G sleep 2 > /dev/null
for i in $(seq 1 15); do systemctl --user is-active --quiet "research-$RUN.service" || break; sleep 1; done
grep -c "\"run\": \"$RUN\"" "$R/ledger.jsonl" | grep -q "^2$" || { echo "FAIL: expected start+stop ledger lines"; cat "$R/ledger.jsonl"; exit 1; }
grep '"event": "stop"' "$R/ledger.jsonl" | grep -q '"exit": 0' || { echo "FAIL: stop line lacks exit 0"; exit 1; }
rm -rf "$T"; echo "LAUNCHER OK"
