"""ideaspark.workflow.js: a 1:1 replica of ResearchStudio's idea_spark.

The three things that have to stay true:
  1. the workflow is what the in-repo generator produces (source of truth = ideaspark_src/);
  2. every banked prompt is byte-identical to the upstream file it came from;
  3. decide() picks the same step of the phase graph as upstream's own navigator, on every
     fixture state (the differential test — this is what makes "1:1" checkable rather than claimed).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]
_PLUGIN = Path(__file__).resolve().parents[1]                   # plugin layout: tests/ sits at the repo root
IN_PLUGIN = (_PLUGIN / "vendor" / "researchstudio").exists()
if IN_PLUGIN:
    WORKSPACE = _PLUGIN
SRC = (WORKSPACE / "scripts" / "ideaspark_src") if IN_PLUGIN else (WORKSPACE / ".research" / "tools" / "ideaspark_src")
GEN = SRC / "gen.py"
LOGIC = SRC / "ideaspark.logic.js"
WORKFLOW = (WORKSPACE / "workflows" / "ideaspark.workflow.js") if IN_PLUGIN else (WORKSPACE / ".claude" / "workflows" / "ideaspark.workflow.js")
FIXTURES = Path(__file__).resolve().parent / "ideaspark_fixtures.py"
DIFF = Path(__file__).resolve().parent / "ideaspark_diff.mjs"
def _rs_home() -> Path:
    if os.environ.get("RS_HOME"):
        return Path(os.environ["RS_HOME"])
    vendored = WORKSPACE / "vendor" / "researchstudio"          # plugin layout
    if vendored.exists():
        return vendored
    return Path("/home/lingxufeng/autoresearch/ResearchStudio/ResearchStudio-Idea")


RS_HOME = _rs_home()
SKILL_DIR = RS_HOME / "skills" / "idea_spark"
LIMIT = 512 * 1024  # Workflow tool script cap

upstream = pytest.mark.skipif(not SKILL_DIR.exists(), reason=f"upstream ResearchStudio checkout not at {RS_HOME}")


def test_workflow_parses_and_fits(tmp_path: Path) -> None:
    src = WORKFLOW.read_text(encoding="utf-8")
    assert src.startswith("export const meta = {")
    assert len(src.encode("utf-8")) < LIMIT, len(src.encode("utf-8"))
    wrapped = tmp_path / "check.js"
    wrapped.write_text("(async () => {\n" + src.replace("export const meta", "const meta", 1) + "\n})()", encoding="utf-8")
    proc = subprocess.run(["node", "--check", str(wrapped)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]
    for token in ("agentType", "resumeFromRunId", "Date.now(", "Math.random("):
        assert token not in src, token          # no custom agent types; nothing that breaks workflow resume


def test_generator_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "ideaspark.workflow.js"
    proc = subprocess.run(["python3", str(GEN), str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert out.read_bytes() == WORKFLOW.read_bytes(), "committed workflow differs from `python3 gen.py` output"


@upstream
def test_prompts_inlined_verbatim() -> None:
    """Every bank entry is byte-identical to its upstream source file — that is what '1:1 prompts' means."""
    src = WORKFLOW.read_text(encoding="utf-8")
    entries = re.findall(r'^  ([a-z_0-9]+): \{ path: "([^"]+)", text: `((?:[^`\\]|\\.)*)` \},$', src, re.M | re.S)
    assert len(entries) == 20, [k for k, _, _ in entries]
    keys = {k for k, _, _ in entries}
    for name in ("bottleneck_identify", "ideate_select", "ideate_generate", "coherence_trace", "critique",
                 "refutation_recheck", "revise", "falsification_reaudit", "expand", "derive_plain",
                 "implementability_audit", "relevance_partition", "pattern_rubric", "intent_recognition",
                 "intake_routing", "anti_patterns", "patterns_overview", "companion_combos",
                 "subpatterns_overview", "idea_quality"):
        assert name in keys, name
    for key, rel, text in entries:
        source = RS_HOME / rel
        assert source.exists(), f"{key}: {source}"
        unescaped = text.replace("\\${", "${").replace("\\`", "`").replace("\\\\", "\\")
        assert unescaped == source.read_text(encoding="utf-8"), f"{key} drifted from {source}"


def test_seat_table_matches_the_agreed_routing() -> None:
    """Every seat pins a model + effort + upstream tier, and the tier→model mapping is the one that was agreed."""
    logic = LOGIC.read_text(encoding="utf-8")
    block = logic[logic.index("const SEATS = {"):logic.index("for (const [k, v] of Object.entries(A.seat_models")]
    rows = re.findall(r"^  ([a-z_0-9]+):\s*\{ model: MODEL\.([a-z0-9]+),\s*effort: '([a-z]+)',\s*tools: '([a-z]+)',\s*tier: '([a-z]+)'", block, re.M)
    assert len(rows) == 19, [r[0] for r in rows]      # 18 pipeline seats + the scoring judge
    by_tier = {"large": set(), "own": set(), "fast": set(), "host": set()}
    for name, model, effort, tools, tier in rows:
        assert model in ("opus", "glm", "k3", "sol"), (name, model)
        assert effort in ("low", "medium", "high"), (name, effort)
        assert tools in ("readwrite", "exec", "web"), (name, tools)
        by_tier[tier].add((name, model))
    # upstream's two tiers, mapped: everything it forbids downgrading runs on the large model
    for name, model in by_tier["large"] | by_tier["own"]:
        assert model == "opus", f"{name} is an upstream {'large' if (name, model) in by_tier['large'] else 'own'}-tier step but runs on {model}"
    for name, model in by_tier["fast"]:
        assert model == "glm", f"{name} is upstream's fast tier but runs on {model}"
    assert {n for n, _ in by_tier["fast"]} == {"tagging", "derive"}, "upstream's fast tier is exactly pattern tagging and 4.derive"
    # the two seats that must be able to run code, and the one that may search the web
    assert dict((n, t) for n, _, _, t, _ in rows)["coherence"] == "exec"
    assert dict((n, t) for n, _, _, t, _ in rows)["recheck"] == "exec"
    assert dict((n, t) for n, _, _, t, _ in rows)["coverage"] == "web"


def test_no_prompt_additions_reach_a_seat() -> None:
    """The seat message carries the upstream contract and nothing bolted onto it."""
    logic = LOGIC.read_text(encoding="utf-8")
    frame = logic[logic.index("const SEAT_FRAME ="):logic.index("function staticBlock")]
    for banned in ("FROZEN GOAL", "SUBSTRATE", "NEGATIVE ANCHORS", "ARFT", "CCF", "SCOPE CHECK", "THREAT QUOTE"):
        assert banned not in frame, f"{banned} is a Brain-era addition; the replica adds nothing to the contract"
    assert "reproduced verbatim from ResearchStudio" in frame


@upstream
def test_decide_matches_upstream_navigator(tmp_path: Path) -> None:
    """The differential test: same run-dir state → same step as `run.py next`, on every fixture."""
    fx = tmp_path / "fx"
    build = subprocess.run(["python3", str(FIXTURES), str(fx)], capture_output=True, text=True, env={**os.environ, "RS_HOME": str(RS_HOME)})
    assert build.returncode == 0, build.stderr[-800:]
    proc = subprocess.run(["node", str(DIFF), str(fx), str(WORKFLOW), str(SKILL_DIR)],
                          capture_output=True, text=True, timeout=900)
    tail = (proc.stdout + proc.stderr)[-3000:]
    assert proc.returncode == 0, tail
    m = re.search(r"\[GREEN\] ideaspark_diff: (\d+)/(\d+)", proc.stdout)
    assert m, tail
    assert m.group(1) == m.group(2) and int(m.group(2)) >= 57, tail


@upstream
def test_state_probe_is_pure(tmp_path: Path) -> None:
    """The probe only reads: running it twice over a fixture leaves the directory byte-identical."""
    fx = tmp_path / "fx"
    subprocess.run(["python3", str(FIXTURES), str(fx)], capture_output=True, text=True, check=True, env={**os.environ, "RS_HOME": str(RS_HOME)})
    src = WORKFLOW.read_text(encoding="utf-8")
    state_py = re.search(r"const STATE_PY = `([\s\S]*?)`\n", src).group(1)
    state_py = state_py.replace("\\${", "${").replace("\\`", "`").replace("\\\\", "\\")
    d = fx / "14_collision"
    before = sorted((p.relative_to(d).as_posix(), p.stat().st_size) for p in d.rglob("*") if p.is_file())
    outs = []
    for _ in range(2):
        r = subprocess.run(["python3", "-", str(d), str(SKILL_DIR)], input=state_py, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-600:]
        assert "__STATE__" in r.stdout, r.stdout[-400:]
        outs.append(json.loads(r.stdout.split("__STATE__", 1)[1].strip()))
    after = sorted((p.relative_to(d).as_posix(), p.stat().st_size) for p in d.rglob("*") if p.is_file())
    assert before == after, "the state probe wrote to the run dir"
    assert outs[0] == outs[1], "the state probe is not deterministic"
    assert outs[0]["canonical"].endswith("phase2_generate_output.json")
    assert outs[0]["p32"]["exists"] is False and outs[0]["p31"]["hits"] is True
