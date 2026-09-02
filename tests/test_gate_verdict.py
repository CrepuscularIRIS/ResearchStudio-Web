import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import gate

def ta(pass_=True, kill=False, blockers=None):
    return {"pass": pass_, "checks": [], "band_hit": True, "kill_hit": kill, "blockers": blockers or []}

def tb(v="SUPPORTED", blocking=None):
    return {"verdict": v, "criterion_met": v == "SUPPORTED", "blocking": blocking or [], "reviewer": "codex:gpt-5.6-sol"}

def test_state_rules():
    assert gate.compute_state(ta(kill=True), tb("SUPPORTED")) == "REFUTED"
    assert gate.compute_state(ta(), tb("SUPPORTED")) == "SUPPORTED"
    assert gate.compute_state(ta(pass_=False), tb("SUPPORTED")) == "CONTESTED"
    assert gate.compute_state(ta(blockers=[{"severity": "high", "text": "x"}]), tb("SUPPORTED")) == "CONTESTED"
    assert gate.compute_state(ta(), tb("SUPPORTED", blocking=["leak"])) == "CONTESTED"
    assert gate.compute_state(ta(), tb("REFUTED")) == "CONTESTED"   # reasoning demotes, never kills

def test_packet_contains_only_card_record_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "HERE", tmp_path)
    (tmp_path / "templates").mkdir(); (tmp_path / "templates" / "role-prompt.md").write_text("ROLE")
    (tmp_path / "packets").mkdir(); (tmp_path / "records").mkdir()
    card = {"id": "C-0009", "claim": "c"}; rec = {"run": "m9", "card": "C-0009", "artifacts": [{"path": "/tmp/a.npy", "sha256": "0" * 64}]}
    (tmp_path / "records" / "m9.md").write_text("# Record m9")
    out = gate.write_packet(card, rec)
    text = out.read_text()
    assert text.startswith("ROLE") and '"id": "C-0009"' in text and "# Record m9" in text and "/tmp/a.npy" in text
    assert "interpretation" not in text.lower().replace("experimenter's interpretation", "")
