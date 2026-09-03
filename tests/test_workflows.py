"""The workflow files parse as plain JS modules, carry a literal meta, parse args defensively, and use the lane agentTypes."""
import re, shutil, subprocess
from pathlib import Path

WF = Path(__file__).resolve().parents[1] / "workflows"
EXPECTED = {"frame": "scientist", "mechanism": "scientist", "spec": "scientist", "build": "builder", "write": "writer", "pivot": "explorer"}


def test_workflow_files_present_and_wellformed():
    for name, lane in EXPECTED.items():
        p = WF / f"{name}.workflow.js"
        assert p.exists(), name
        s = p.read_text()
        assert re.search(r"^export const meta = \{", s, re.M), f"{name}: meta must be a top-level literal"
        assert f"name: '{name}'" in s
        assert "typeof args === 'string' ? JSON.parse(args) : args" in s, f"{name}: args must be parsed defensively (harness passes a JSON string)"
        assert f"agentType: '{lane}'" in s, f"{name}: must dispatch through the {lane} lane"
        if name == "build":
            assert "agentType: 'researcher'" in s and "agentType: 'reviewer'" in s and "parallel([" in s, "build carries the Grok monitor and the Codex lens after the builder"
            assert "smoke: {" not in s and "'pass', 'fail'" not in s, "the builder never self-reports a smoke verdict"
        if name == "mechanism":
            assert "agentType: 'explorer'" in s and "agentType: 'researcher'" in s, "mechanism: Fable abstracts, K3 diverges, Grok retrieves"
            assert "--start-year" in s and "--max-papers" in s, "the retrieval command uses search_papers.py's real flags"
        if name in ("spec", "build", "mechanism", "write"):
            assert "stallMs" in s, f"{name}: every long agent call carries a stall watchdog"
        assert "Structured output only" in s
        assert "require(" not in s and "import " not in s, f"{name}: no filesystem or imports inside the sandbox"


def test_workflow_files_parse_as_es_modules():
    node = shutil.which("node")
    if not node:
        import pytest; pytest.skip("node not installed")
    for p in WF.glob("*.workflow.js"):
        # wrap in an async module body the way the harness does: top-level await + the sandbox globals
        # the harness runs the body inside an async function (top-level `return`/`await` are legal there)
        src = ("const agent=async()=>null,parallel=async(t)=>Promise.all(t.map(f=>f())),pipeline=async()=>[],log=()=>{},phase=()=>{},args='{}',budget={total:null,spent:()=>0,remaining:()=>Infinity};\n"
               + "(async()=>{\n" + p.read_text().replace("export const meta", "const meta") + "\n})();\n")
        r = subprocess.run([node, "--input-type=module", "--check"], input=src, capture_output=True, text=True)
        assert r.returncode == 0, f"{p.name}: {r.stderr[:400]}"
