#!/usr/bin/env python3
"""init_research.py — scaffold .research/ in the current project and prepend the GOAL.md campaign block."""
import shutil, sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
W = Path.cwd()
R = W / ".research"
DIRS = ["cards", "records", "packets", "verdicts", "bridges", "lit", "briefs", "reports", "views", "tokens", "templates", "tests"]

for d in DIRS:
    (R / d).mkdir(parents=True, exist_ok=True)
for t in (PLUGIN / "templates").glob("*.md"):
    dst = R / "templates" / t.name
    if not dst.exists():
        shutil.copy(t, dst)
ledger = R / "lit" / "LIT-LEDGER.md"
if not ledger.exists():
    ledger.write_text("# LIT ledger — every retrieval query, verbatim, hit or miss\n\n| date | bridge | source | query | hits |\n|---|---|---|---|---|\n")
goal = W / "GOAL.md"
block = "```yaml\n" + (PLUGIN / "templates" / "GOAL-block.yaml").read_text() + "```\n\n"
if not goal.exists():
    goal.write_text(block + "# GOAL\n\nState the one objective, the three bars a method must clear, and what is out of scope.\n")
    print("wrote GOAL.md with a campaign block — edit every field")
elif not goal.read_text().startswith("```yaml"):
    goal.write_text(block + goal.read_text()); print("prepended the campaign block to GOAL.md — edit every field")
card = W / "CLAUDE.md"
if not card.exists():
    shutil.copy(PLUGIN / "templates" / "CLAUDE.md.tmpl", card); print("wrote CLAUDE.md from the template")
print(f"ok: {R} ready. Next: edit GOAL.md, register `arbor mcp`, then read {PLUGIN / 'docs' / 'ACCEPTANCE.md'}")
