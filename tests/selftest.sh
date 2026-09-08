#!/usr/bin/env bash
# Self-test: no model calls, no network. Needs python3 + pytest + node.
#
#   1. the committed Claude workflow still matches its generator and vendored upstream
#   2. prompt bank + phase graph differential tests remain unchanged
#   3. the native Claude host adapter satisfies its routing/artifact contract
#   4. the OpenAI Skill preserves upstream prompts and builds a clean skill.zip
#   5. the installer still produces a usable Claude run directory
set -euo pipefail
P="$(cd "$(dirname "$0")/.." && pwd)"
export RS_HOME="$P/vendor/researchstudio"

echo "== upstream workflow"
python3 -m pytest "$P/tests/test_ideaspark_workflow.py" -q

echo "== native/OpenAI adapter contracts"
python3 -m unittest -v \
  "$P/tests/test_native_host_adapter.py" \
  "$P/tests/test_openai_skill.py"

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

echo "== OpenAI package"
python3 "$P/scripts/openai/build_skill.py" --out "$T/openai-dist" > /dev/null
test -f "$T/openai-dist/skill.zip"
python3 - "$T/openai-dist/skill.zip" <<'PY'
import sys, zipfile
p = sys.argv[1]
with zipfile.ZipFile(p) as z:
    names = z.namelist()
    assert "idea-spark/SKILL.md" in names
    assert "idea-spark/agents/openai.yaml" in names
    assert not any("__pycache__" in n or n.endswith(".pyc") or n.endswith("/.env") for n in names)
print("  openai package ok")
PY

echo "== Claude installer"
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

echo "selftest ok"
