import importlib.util, json, pathlib, sys
H = pathlib.Path(__file__).resolve().parents[1] / "hooks"

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), H / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_launch_gate_decisions():
    g = load("launch-gate")
    assert g.decide("nohup python train.py &") is not None
    assert g.decide("systemd-run --user python x.py") is not None
    assert g.decide("CUDA_VISIBLE_DEVICES=0 python train.py") is not None
    assert g.decide("bin/run_protected.sh m1 C-0001 30G python train.py --gpu 0") is None
    assert g.decide("python3 .research/gate.py card x.json") is None
    assert g.decide("echo 'nohup is banned'") is None

def test_identity_probe(tmp_path):
    p = load("identity-probe")
    agents = tmp_path / "agents"; agents.mkdir()
    (agents / "scientist.md").write_text("---\nname: scientist\nmodel: claude-fable-5-1\n---\n## REQUIRED READING\n- x\n")
    ok = '{"type":"assistant","message":{"model":"claude-fable-5-1"}}\n'
    bad = '{"type":"assistant","message":{"model":"claude-opus-5"}}\n'
    assert p.probe("scientist", ok, "METHOD: x\nDONE reports/a.md", agents) is None
    assert "model" in p.probe("scientist", bad, "METHOD: x\nDONE", agents)
    assert "METHOD" in p.probe("scientist", ok, "DONE reports/a.md", agents)

def test_session_lock_roundtrip(tmp_path):
    s = load("session-lock")
    lock = tmp_path / "LOCK"
    assert s.acquire(lock, "sess-1", 999999999) == "acquired"      # dead pid → fresh lock
    assert s.acquire(lock, "sess-2", 999999999) == "acquired"      # previous holder dead → takeover
    import os
    assert s.acquire(lock, "sess-3", os.getpid()) == "acquired"
    assert s.acquire(lock, "sess-4", os.getpid() + 1) == "read-only"


def test_dispatch_guard_decisions():
    g = load("dispatch-guard")
    prompt = "LANE: scientist\nBRIEF: .research/briefs/scientist-0001.md\nINPUTS: GOAL.md ; .research/views/TREE.md ; .research/QUEUE.md"
    named = g.named_paths(prompt)
    assert ".research/views/TREE.md" in named and ".research/QUEUE.md" in named
    assert "BUDGET" in g.decide("Read", {"file_path": "/x"}, prompt, 15, "scientist", named)
    assert g.decide("Read", {"file_path": str(g.W / ".research/QUEUE.md")}, prompt, 3, "scientist", named) is None
    assert "BUDGET" in g.decide("Bash", {"command": "ls"}, prompt, 40, None, named)
    assert "OUT OF BRIEF" in g.decide("Read", {"file_path": str(g.W / ".research/views/GAPMAP.md")}, prompt, 3, "scientist", named)
    assert "OUT OF BRIEF" in g.decide("Bash", {"command": "cat .research/views/GAPMAP.md"}, prompt, 3, "scientist", named)
    assert g.decide("Read", {"file_path": str(g.W / "ugra-rgbd-robust/scripts/eval_robust_suite.py")}, prompt, 3, "builder", named) is None
    assert "SEARCH DENIED" in g.decide("Bash", {"command": "python3 x/search_papers.py --queries a"}, prompt, 3, "scientist", named)
    assert "SEARCH DENIED" in g.decide("WebSearch", {"query": "q"}, prompt, 3, "scientist", named)
    sp = "LANE: researcher\nMODE: SEARCH\n"
    assert g.decide("Bash", {"command": "python3 x/search_papers.py --queries a"}, sp, 3, "researcher", g.named_paths(sp)) is None
    assert g.lane_of("briefs/builder-C-1.md ...") == "builder" and g.lane_of("nothing") is None and g.lane_of("x", "writer") == "writer"


def test_write_guard_decisions(tmp_path):
    g = load("write-guard")
    prot = ["scripts/eval.py", "local_configs/"]
    assert g.decide("Write", {"file_path": str(tmp_path / "CLAIM.md")}, prot, tmp_path)
    assert g.decide("Edit", {"file_path": str(tmp_path / ".research/records/Q-1.json")}, prot, tmp_path)
    assert g.decide("Write", {"file_path": str(tmp_path / ".research/notebook.json")}, prot, tmp_path)
    assert g.decide("Write", {"file_path": str(tmp_path / "paper/icassp/main.tex")}, prot, tmp_path)
    assert g.decide("Write", {"file_path": "/tmp/wt-Q-0001-alpha/scripts/eval.py"}, prot, tmp_path), "protected paths inside any worktree"
    assert g.decide("Write", {"file_path": "/tmp/wt-Q-0001-alpha/models/net.py"}, prot, tmp_path) is None
    assert g.decide("Write", {"file_path": str(tmp_path / ".research/reports/builder-Q-1.md")}, prot, tmp_path) is None
    assert g.decide("Bash", {"command": "python3 .research/stage.py accept"}, prot, tmp_path)
    assert g.decide("Bash", {"command": "python3 .research/gate.py frozen --accept"}, prot, tmp_path)
    assert g.decide("Bash", {"command": f"echo x >> {tmp_path}/.research/ledger.jsonl"}, prot, tmp_path)
    assert g.decide("Bash", {"command": f"cp a.json {tmp_path}/.research/records/Q-1.json"}, prot, tmp_path)
    assert g.decide("Bash", {"command": "python3 .research/stage.py board"}, prot, tmp_path) is None
    assert g.decide("Bash", {"command": "git diff research-trunk > /tmp/d.txt"}, prot, tmp_path) is None
