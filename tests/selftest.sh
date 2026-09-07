#!/usr/bin/env bash
# Self-test: install the harness into a scratch project and run its own test suite there (no model calls; needs python3 + pytest + node).
set -euo pipefail
P="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; cd "$T"
python3 "$P/scripts/init_research.py" --slug selftest --repo "$T" > /dev/null
python3 -m pytest .research/tests/test_exp_tools.py .research/tests/test_brain_workflow.py -q
python3 .research/tools/exp/next.py .research/research/ideaspark/selftest | head -4
echo "selftest ok in $T"
