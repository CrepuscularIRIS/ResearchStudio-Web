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
