"""brain.workflow.js: one self-contained TS workflow (RS prompts inlined verbatim, logic in JS)."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]
WORKFLOW = WORKSPACE / ".claude" / "workflows" / "brain.workflow.js"
MOCK = Path(__file__).resolve().parent / "mock_runtime_brain.mjs"
GEN = WORKSPACE / ".research" / "tools" / "brain_src" / "gen_brain.py"
RS = WORKSPACE / "docs" / "refs" / "rs" / "references"
LIMIT = 512 * 1024  # Workflow tool script cap


def test_workflow_parses_and_fits() -> None:
    src = WORKFLOW.read_text(encoding="utf-8")
    assert src.startswith("export const meta = {")
    assert len(src.encode("utf-8")) < LIMIT
    wrapped = "(async () => {\n" + src.replace("export const meta", "const meta") + "\n})()"
    proc = subprocess.run(["node", "--check", "-"], input=wrapped, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]
    for token in ("agentType", "brain.py", ".research/brain"):
        assert token not in src  # no custom agent types, no python layer
    seats = src[src.index("const SEATS = {"):src.index("// Route a navigator emit")]
    assert seats.count("effort: '") == 20  # every seat pins its effort (18 RS/Brain seats + Phase 6 spec + the parallel second auditor); no new serial seats


def test_generator_roundtrip(tmp_path: Path) -> None:
    """The committed workflow is exactly what the in-repo generator produces (source of truth = brain_src/)."""
    out = tmp_path / "brain.workflow.js"
    proc = subprocess.run(["python3", str(GEN), str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert out.read_bytes() == WORKFLOW.read_bytes()


def test_prompts_inlined_verbatim() -> None:
    """Every bank entry (RS system prompts + references, CCF/ARIS references, Brain prompts) is byte-identical to its source file."""
    src = WORKFLOW.read_text(encoding="utf-8")
    # generated entries are `  key: { path: "...", text: `...` },` lines; texts are backslash-escaped template literals
    entries = re.findall(r'^  ([a-z_0-9]+): \{ path: "([^"]+)", text: `((?:[^`\\]|\\.)*)` \},$', src, re.M | re.S)
    assert len(entries) >= 41, len(entries)
    keys = {k for k, _, _ in entries}
    for name in ("bottleneck_identify", "ideate_select", "ideate_generate", "coherence_trace", "critique",
                 "refutation_recheck", "revise", "falsification_reaudit", "expand", "derive_plain",
                 "implementability_audit", "ccf_idea_rubric", "ccf_idea_calibration", "ccf_strict_review",
                 "ccf_blueprint", "aris_formula_derivation", "aris_ablation_planner", "aris_compute_env",
                 "aris_evidence_precheck", "ccf_idea_intake", "aris_experiment_plan", "ccf_evidence_design"):
        assert name in keys, name
    for key, path, text in entries:
        if path.startswith("references/"):
            source = WORKSPACE / "docs" / "refs" / "rs" / path
        elif path.startswith("docs/refs/"):
            source = WORKSPACE / path
        elif path.startswith("brain/"):
            source = WORKSPACE / ".research" / "tools" / "brain_src" / "prompts" / path.split("/", 1)[1]
        else:
            raise AssertionError(f"{key}: unknown path family {path}")
        unescaped = text.replace("\\${", "${").replace("\\`", "`").replace("\\\\", "\\")
        assert unescaped == source.read_text(encoding="utf-8"), f"{key} drifted from {source}"


def _run_mock(env: dict[str, str]) -> None:
    proc = subprocess.run(["node", str(MOCK)], capture_output=True, text=True, timeout=120, env={**os.environ, **env})
    assert proc.returncode == 0, (proc.stdout[-1500:] + proc.stderr[-1500:])
    assert "OK —" in proc.stdout


def test_mock_runtime_happy_path() -> None:
    _run_mock({})


@pytest.mark.parametrize("env", [{"MOCK_VALIDATE_FAIL": "1"}, {"MOCK_DBLP_TIMEOUT": "1"}, {"MOCK_PLACEHOLDER": "1"}, {"MOCK_SEAT_FAIL": "1"}, {"MOCK_NEG_ANCHORS": "1"}, {"MOCK_TAG_MISSING": "1"}, {"MOCK_SEAT_MODELS": "1"}, {"MOCK_SECOND_KILL": "1"}, {"MOCK_KEEP_PLAN": "1"}, {"MOCK_BASH_FAIL": "1"}])
def test_mock_runtime_variants(env: dict[str, str]) -> None:
    """validate-fail repair loop, dblp circuit breaker, placeholder warning, Opus→GLM fallback on the 2.3 seat, args.seat_models override (spec → sol), second auditor's abandon → revise, resume keeps an existing plan / ranking that passes its check, a deterministic step rejecting a seat's output sends the seat back once, failure cards as negative anchors (Phase 1 / ideate / 3.2 only), tagging repair seat for missing rows."""
    _run_mock(env)


@pytest.mark.parametrize("k3,second,kills,expect", [("advance", "advance", "0", "advance"), ("advance", "abandon", "0", "revise"), ("advance", "abandon", "1", "abandon"),
                                                    ("revise", "advance", "0", "revise"), ("abandon", "advance", "0", "abandon"), ("advance", "revise", "0", "revise")])
def test_audit_merge_rule(tmp_path: Path, k3: str, second: str, kills: str, expect: str) -> None:
    """AUDIT_MERGE_PY (extracted from the logic, never duplicated): K3 owns the verdict; the second auditor can force revise and add targets; abandon alone only with args.second_auditor_kills."""
    import json
    logic = (WORKSPACE / ".research" / "tools" / "brain_src" / "brain.logic.js").read_text(encoding="utf-8")
    py = re.search(r"const AUDIT_MERGE_PY = `(.*?)`\n", logic, re.S).group(1)
    a, b = tmp_path / "k3.json", tmp_path / "second.json"
    a.write_text(json.dumps({"verdict": k3, "verdict_rationale": "k3 says", "revision_targets": [{"scope": "tactical", "field": "core_mechanism", "what": "x"}] if k3 == "revise" else []}))
    b.write_text(json.dumps({"verdict": second, "verdict_rationale": "second says", "revision_targets": [{"scope": "tactical", "field": "core_mechanism", "what": "dup"}, {"scope": "falsification", "field": "falsification_prediction", "what": "new"}] if second != "advance" else []}))
    proc = subprocess.run(["python3", "-", str(a), str(b), "gpt-5.6-sol", kills], input=py, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-500:]
    out = json.loads(a.read_text())
    assert out["verdict"] == expect and out["second_opinion"]["verdict"] == second, proc.stdout
    if second != "advance": assert any(t.get("source") == "second_auditor" for t in out["revision_targets"]) and len({(t["scope"], t["field"]) for t in out["revision_targets"]}) == len(out["revision_targets"])
    if expect != k3: assert "second auditor" in out["verdict_rationale"]
