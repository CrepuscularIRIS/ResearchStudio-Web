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

echo "== web track"
mkdir -p "$T/r/phase1" "$T/r/web/answers"
python3 - "$T/r" <<'PY'
import json, pathlib, sys
r = pathlib.Path(sys.argv[1])
(r / "phase1/phase1_output.json").write_text(json.dumps({
    "intake": {"domain": "embodied agents", "contribution_type": "method", "compute": "8xH100"},
    "bottleneck_statement": "retrieval is scored by similarity, not by effect on the next tool call",
    "what_phase_0_did_not_address": ["no method conditions retrieval on downstream tool success.",
                                     "no benchmark isolates retrieval error from planning error."]}))
PY
python3 "$P/scripts/web/web.py" seed --root "$T/r" --from-run --n 2 > /dev/null
grep -q '^@ResearchStudio IdeaSpark Use IdeaSpark\.$' "$T/r/web/prompts/01.txt"
grep -q 'End your answer with the single line <<END OF IDEA CARD>>' "$T/r/web/prompts/01.txt"
printf 'cut off mid-sen' > "$T/r/web/answers/01.md"
printf 'whole card\n\n<<END OF IDEA CARD>>\n' > "$T/r/web/answers/02.md"
if python3 "$P/scripts/web/web.py" collect --root "$T/r" > /dev/null; then
  echo "  FAIL: collect accepted a capture with no end marker"; exit 1
fi
python3 - "$T/r/web/index.json" <<'PY'
import json, sys, pathlib
d = json.loads(pathlib.Path(sys.argv[1]).read_text())
a = {x["id"]: x for x in d["answers"]}
assert a["01"]["complete"] is False and a["02"]["complete"] is True, d
print("  web ok: truncated capture rejected, complete one accepted")
PY
rm -rf "$T"
echo "selftest ok"
