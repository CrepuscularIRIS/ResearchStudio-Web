#!/usr/bin/env bash
# Self-test: no model calls, no network. Needs python3 + pytest + node.
#
#   1. the committed workflow is exactly what the generator produces from the vendored upstream
#   2. every prompt it ships is byte-identical to the vendored file it came from
#   3. decide() picks the same step of the phase graph as upstream's own navigator, on 52 run-dir
#      fixtures plus 5 shard-count unit checks
#   4. the state probe is read-only and deterministic
#   5. the installer produces a usable run directory
set -euo pipefail
P="$(cd "$(dirname "$0")/.." && pwd)"
export RS_HOME="$P/vendor/researchstudio"

echo "== upstream vendored at $RS_HOME"
python3 -m pytest "$P/tests/test_ideaspark_workflow.py" -q

T="$(mktemp -d)"
python3 "$P/scripts/init_research.py" --slug selftest --dir "$T" --direction "a test direction" > /dev/null
test -f "$T/.claude/workflows/ideaspark.workflow.js"
python3 - "$T/ideaspark_run/selftest/args.json" <<'PY'
import json, sys, pathlib
a = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert a["direction"] == "a test direction", a
assert pathlib.Path(a["rs_home"], "skills/idea_spark/scripts/run.py").exists(), a["rs_home"]
assert pathlib.Path(a["root"]).name == "selftest", a["root"]
print("  install ok:", a["root"])
PY
rm -rf "$T"
echo "selftest ok"
