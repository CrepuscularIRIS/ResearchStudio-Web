#!/usr/bin/env python3
"""Pack the ResearchStudio idea_spark prompt bank into one self-contained workflow.

Source of truth for the LOGIC is ideaspark.logic.js in this directory; source of truth
for every PROMPT is the upstream ResearchStudio checkout. This script only substitutes
the bank: it never rewrites logic. Every banked file is reproduced byte-for-byte (the
only transformation is JS template-literal escaping, which test_ideaspark_workflow.py
reverses and compares against the source file).

  python3 gen.py [out.js] [--rs <upstream ResearchStudio-Idea dir>]

Default out: <workspace>/.claude/workflows/ideaspark.workflow.js
Default rs:  /home/lingxufeng/autoresearch/ResearchStudio/ResearchStudio-Idea
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Two layouts, one generator: inside the plugin the upstream checkout is vendored next to the
# workflows dir; in a working repo it lives wherever RS_HOME points.
PLUGIN = HERE.parents[1]
VENDORED = PLUGIN / "vendor" / "researchstudio"
IN_PLUGIN = VENDORED.exists()
WS = HERE.parents[2]
DEFAULT_OUT = (PLUGIN / "workflows" / "ideaspark.workflow.js") if IN_PLUGIN else (WS / ".claude" / "workflows" / "ideaspark.workflow.js")
DEFAULT_RS = VENDORED if IN_PLUGIN else Path(
    os.environ.get("RS_HOME", "/home/lingxufeng/autoresearch/ResearchStudio/ResearchStudio-Idea"))

# bank key -> path relative to the ResearchStudio-Idea root.
# Sub-pattern cards (references/ideation-sub-patterns/C##.md, 283 KB) are deliberately NOT
# banked: upstream's contract is "open the ONE card you picked", so the seat Reads it from disk.
BANK = {
    # ---- the 11 system prompts (one per LLM-driven phase) ----
    "bottleneck_identify":  "skills/idea_spark/references/system-prompts/bottleneck_identify.txt",
    "ideate_select":        "skills/idea_spark/references/system-prompts/ideate_select.txt",
    "ideate_generate":      "skills/idea_spark/references/system-prompts/ideate_generate.txt",
    "coherence_trace":      "skills/idea_spark/references/system-prompts/coherence_trace.txt",
    "critique":             "skills/idea_spark/references/system-prompts/critique.txt",
    "refutation_recheck":   "skills/idea_spark/references/system-prompts/refutation_recheck.txt",
    "revise":               "skills/idea_spark/references/system-prompts/revise.txt",
    "falsification_reaudit": "skills/idea_spark/references/system-prompts/falsification_reaudit.txt",
    "expand":               "skills/idea_spark/references/system-prompts/expand.txt",
    "derive_plain":         "skills/idea_spark/references/system-prompts/derive_plain.txt",
    "implementability_audit": "skills/idea_spark/references/system-prompts/implementability_audit.txt",
    # ---- references a seat reads as its rubric or as inline context ----
    "relevance_partition":  "skills/idea_spark/references/relevance-partition-rubric.md",
    "pattern_rubric":       "skills/idea_spark/references/pattern-summary-rubric.md",
    "intent_recognition":   "skills/idea_spark/references/intent-recognition.md",
    "intake_routing":       "skills/idea_spark/references/intake-routing.md",
    "anti_patterns":        "skills/idea_spark/references/anti-patterns.md",
    "patterns_overview":    "skills/idea_spark/references/ideation-patterns/overview.md",
    "companion_combos":     "skills/idea_spark/references/ideation-patterns/companion-combos.md",
    "subpatterns_overview": "skills/idea_spark/references/ideation-sub-patterns/overview.md",
    # ---- the suite's 4th skill: idea scoring (absolute + blind pairwise) ----
    "idea_quality":         "evaluation/idea_quality/SKILL.md",
}

MARKER = "// __BANK__"


def esc(text: str) -> str:
    """Escape for a JS template literal: backslash, backtick, and ${ only."""
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else DEFAULT_OUT
    rs = DEFAULT_RS
    if "--rs" in argv:
        rs = Path(argv[argv.index("--rs") + 1]).resolve()

    logic = (HERE / "ideaspark.logic.js").read_text(encoding="utf-8")
    if MARKER not in logic:
        raise SystemExit(f"{MARKER} not found in ideaspark.logic.js")

    lines = []
    for key, rel in BANK.items():
        src = rs / rel
        if not src.exists():
            raise SystemExit(f"missing upstream file for bank key {key}: {src}")
        lines.append(f'  {key}: {{ path: "{rel}", text: `{esc(src.read_text(encoding="utf-8"))}` }},')
    bank = "const BANK = {\n" + "\n".join(lines) + "\n}"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(logic.replace(MARKER, bank), encoding="utf-8")
    size = out.stat().st_size
    print(f"wrote {out} ({size} bytes, {len(BANK)} bank entries, upstream {rs})")
    if size > 512 * 1024:
        raise SystemExit("over the 512 KB Workflow script cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
