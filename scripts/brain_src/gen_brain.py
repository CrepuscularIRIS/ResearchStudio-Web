"""Generator (source of truth lives here, never edit the generated file): brain.logic.js + verbatim prompt/reference files → .claude/workflows/brain.workflow.js."""
from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[3]   # brain_src → tools → .research → the harness root (works in any copy of the harness)
REFS = WS / "docs" / "refs"
RS = REFS / "rs"
SP = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else WS / ".claude" / "workflows" / "brain.workflow.js"   # optional out path (tests)

# key, path shown to the seat (relative to SKILL_DIR for RS files), source file
FILES = [
    ("bottleneck_identify", "references/system-prompts/bottleneck_identify.txt", RS / "references/system-prompts/bottleneck_identify.txt"),
    ("ideate_select", "references/system-prompts/ideate_select.txt", RS / "references/system-prompts/ideate_select.txt"),
    ("ideate_generate", "references/system-prompts/ideate_generate.txt", RS / "references/system-prompts/ideate_generate.txt"),
    ("coherence_trace", "references/system-prompts/coherence_trace.txt", RS / "references/system-prompts/coherence_trace.txt"),
    ("critique", "references/system-prompts/critique.txt", RS / "references/system-prompts/critique.txt"),
    ("refutation_recheck", "references/system-prompts/refutation_recheck.txt", RS / "references/system-prompts/refutation_recheck.txt"),
    ("revise", "references/system-prompts/revise.txt", RS / "references/system-prompts/revise.txt"),
    ("falsification_reaudit", "references/system-prompts/falsification_reaudit.txt", RS / "references/system-prompts/falsification_reaudit.txt"),
    ("expand", "references/system-prompts/expand.txt", RS / "references/system-prompts/expand.txt"),
    ("derive_plain", "references/system-prompts/derive_plain.txt", RS / "references/system-prompts/derive_plain.txt"),
    ("implementability_audit", "references/system-prompts/implementability_audit.txt", RS / "references/system-prompts/implementability_audit.txt"),
    ("patterns_overview", "references/ideation-patterns/overview.md", RS / "references/ideation-patterns/overview.md"),
    ("companion_combos", "references/ideation-patterns/companion-combos.md", RS / "references/ideation-patterns/companion-combos.md"),
    ("subpatterns_overview", "references/ideation-sub-patterns/overview.md", RS / "references/ideation-sub-patterns/overview.md"),
    ("anti_patterns", "references/anti-patterns.md", RS / "references/anti-patterns.md"),
    ("rubric", "references/pattern-summary-rubric.md", RS / "references/pattern-summary-rubric.md"),
    ("intent_recognition", "references/intent-recognition.md", RS / "references/intent-recognition.md"),
    ("intake_routing", "references/intake-routing.md", RS / "references/intake-routing.md"),
    ("ccf_evidence_design", "docs/refs/ccf/ccf-experiment-designer/references/evidence-design.md", REFS / "ccf/ccf-experiment-designer/references/evidence-design.md"),
    ("ccf_result_templates", "docs/refs/ccf/ccf-experiment-designer/references/result-templates.md", REFS / "ccf/ccf-experiment-designer/references/result-templates.md"),
    ("aris_experiment_plan", "docs/refs/aris/experiment-plan/SKILL.md", REFS / "aris/experiment-plan/SKILL.md"),
    ("aris_ablation_planner", "docs/refs/aris/ablation-planner/SKILL.md", REFS / "aris/ablation-planner/SKILL.md"),
    ("aris_formula_derivation", "docs/refs/aris/formula-derivation/SKILL.md", REFS / "aris/formula-derivation/SKILL.md"),
    ("aris_compute_env", "docs/refs/aris/shared-references/compute-env-contract.md", REFS / "aris/shared-references/compute-env-contract.md"),
    ("aris_evidence_precheck", "docs/refs/aris/shared-references/evidence-precheck.md", REFS / "aris/shared-references/evidence-precheck.md"),
    ("ccf_idea_intake", "docs/refs/ccf/ccf-idea-optimizer/references/idea-intake.md", REFS / "ccf/ccf-idea-optimizer/references/idea-intake.md"),
    ("ccf_blueprint", "docs/refs/ccf/ccf-idea-optimizer/references/problem-method-blueprint.md", REFS / "ccf/ccf-idea-optimizer/references/problem-method-blueprint.md"),
    ("ccf_idea_rubric", "docs/refs/ccf/ccf-idea-reviewer/references/rubric.md", REFS / "ccf/ccf-idea-reviewer/references/rubric.md"),
    ("ccf_idea_calibration", "docs/refs/ccf/ccf-idea-reviewer/references/calibration.md", REFS / "ccf/ccf-idea-reviewer/references/calibration.md"),
    ("ccf_strict_review", "docs/refs/ccf/ccf-idea-reviewer/references/strict-idea-review.md", REFS / "ccf/ccf-idea-reviewer/references/strict-idea-review.md"),
    ("ccf_lit_evolution", "docs/refs/ccf/ccf-idea-optimizer/references/literature-grounded-evolution.md", REFS / "ccf/ccf-idea-optimizer/references/literature-grounded-evolution.md"),
    ("ccf_expert_panel", "docs/refs/ccf/ccf-idea-reviewer/references/expert-panel.md", REFS / "ccf/ccf-idea-reviewer/references/expert-panel.md"),
    ("ccf_review_output_standards", "docs/refs/ccf/ccf-common/references/review-output-standards.md", REFS / "ccf/ccf-common/references/review-output-standards.md"),
    ("ccf_venue_adapters", "docs/refs/ccf/ccf-idea-optimizer/references/venue-idea-adapters.md", REFS / "ccf/ccf-idea-optimizer/references/venue-idea-adapters.md"),
    ("arft_guide", "docs/refs/papers/arft_guide.md", REFS / "papers/arft_guide.md"),
    ("asi_task_yaml", "docs/refs/papers/asi-bench/task-exemplar/task.yaml", REFS / "papers/asi-bench/task-exemplar/task.yaml"),
    ("asi_prompt_b1", "docs/refs/papers/asi-bench/task-exemplar/prompt_b1.md", REFS / "papers/asi-bench/task-exemplar/prompt_b1.md"),
    ("asi_how_scoring", "docs/refs/papers/asi-bench/guide/how-scoring-works.md", REFS / "papers/asi-bench/guide/how-scoring-works.md"),
    ("intake", "brain/intake.md", SP / "prompts" / "intake.md"),
    ("tagging_shard", "brain/tagging_shard.md", SP / "prompts" / "tagging_shard.md"),
    ("evidence_plan", "brain/evidence_plan.md", SP / "prompts" / "evidence_plan.md"),
]


def esc(text: str) -> str:
    """Escape for a JS template literal: backslash, backtick, ${."""
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def main() -> int:
    lines = ["const BANK = {"]
    total = 0
    for key, shown, src in FILES:
        text = src.read_text(encoding="utf-8")
        total += len(text)
        lines.append(f"  {key}: {{ path: {json.dumps(shown)}, text: `{esc(text)}` }},")
    lines.append("}")
    bank = "\n".join(lines)
    logic = (SP / "brain.logic.js").read_text(encoding="utf-8")
    if "/*__BANK__*/" not in logic:
        print("marker missing", file=sys.stderr)
        return 1
    final = logic.replace("/*__BANK__*/", bank)
    OUT.write_text(final, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(final.encode('utf-8'))} bank_chars={total} files={len(FILES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
