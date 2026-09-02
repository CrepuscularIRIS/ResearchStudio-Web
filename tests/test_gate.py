import json, pathlib, sys, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import gate

GOAL = {"campaign": {"metric": "mIoU_nyu_heldout_wrong", "metric_direction": "maximize",
        "gpu_h_ceiling": 100, "caps": {"oracle_frac": 0.05, "single_run_frac": 0.25, "reserve_frac": 0.2},
        "run_name": "t"}}

def good_card():
    return {
        "id": "C-0001", "bridge": "bridges/2026-09-03.md#1",
        "claim": "Training against smooth-wrong depth raises held-out wrong-depth mIoU",
        "mechanism": "m", "forbids": "clean mIoU drop > 0.5",
        "prediction": {"metric": "mIoU_nyu_heldout_wrong", "band": [1.5, 3.0], "direction": "maximize"},
        "kill": {"metric": "mIoU_nyu_heldout_wrong", "threshold": 0.3, "rule": "mean below threshold"},
        "controls": ["absent-depth arm"], "seed_sd": 0.564, "n_required": 3, "mde": 1.29,
        "instrument": {"checkpoint": "ckpt.pth", "reference_number": 54.93, "canary": "entire_missing 49.95 ± 0.10"},
        "oracle": {"design": "gt mask", "cost_gpu_h": 0.5, "pass": "delta > oracle_mde"},
        "tier": "T4", "cost_gpu_h": 20, "frozen_sha": None, "arbor_node": None,
    }

def research_dir(tmp_path, with_bridge=True, with_packet=True):
    r = tmp_path / ".research"
    for d in ("cards", "bridges", "lit", "records"): (r / d).mkdir(parents=True)
    if with_bridge: (r / "bridges" / "2026-09-03.md").write_text("## 1\n- domain_a: x\n")
    if with_packet: (r / "lit" / "2026-09-03-1.md").write_text("packet")
    (r / "ledger.jsonl").write_text("")
    return r

def test_mde_lehr():
    assert math.isclose(gate.mde_lehr(0.564, 3), 2.8 * 0.564 * math.sqrt(2 / 3))

def test_good_card_passes(tmp_path):
    assert gate.check_card(good_card(), GOAL, research_dir(tmp_path)) == []

def test_card_fails_on_n_and_mde(tmp_path):
    c = good_card(); c["n_required"] = 2; c["mde"] = 0.1
    fails = gate.check_card(c, GOAL, research_dir(tmp_path))
    assert any("n_required" in f for f in fails) and any("mde" in f for f in fails)

def test_card_fails_when_band_below_mde(tmp_path):
    c = good_card(); c["prediction"]["band"] = [0.5, 1.0]
    assert any("band" in f for f in gate.check_card(c, GOAL, research_dir(tmp_path)))

def test_card_fails_without_packet(tmp_path):
    fails = gate.check_card(good_card(), GOAL, research_dir(tmp_path, with_packet=False))
    assert any("packet" in f for f in fails)

def test_card_fails_on_duplicate_claim(tmp_path):
    r = research_dir(tmp_path)
    (r / "cards" / "C-0000.json").write_text(json.dumps({**good_card(), "id": "C-0000"}))
    assert any("duplicate" in f for f in gate.check_card(good_card(), GOAL, r))

def test_card_fails_over_budget(tmp_path):
    c = good_card(); c["cost_gpu_h"] = 90
    assert any("budget" in f for f in gate.check_card(c, GOAL, research_dir(tmp_path)))

def test_sha_ignores_mutable_fields():
    a = good_card(); b = good_card(); b["frozen_sha"] = "x"; b["arbor_node"] = "n1"
    assert gate.card_sha(a) == gate.card_sha(b)

def test_freeze_refuses_after_critique_change(tmp_path):
    r = research_dir(tmp_path); p = r / "cards" / "C-0001.json"
    p.write_text(json.dumps(good_card()))
    crit = tmp_path / "crit.md"; crit.write_text("fine")
    assert gate.record_critique(p, crit) == 0
    c = json.loads(p.read_text()); c["claim"] += " (edited)"; p.write_text(json.dumps(c))
    assert gate.freeze_card(p) == 1
    c = json.loads(p.read_text()); c["claim"] = good_card()["claim"]; p.write_text(json.dumps(c))
    assert gate.freeze_card(p) == 0
    assert json.loads(p.read_text())["frozen_sha"]
