import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import render_record, gate
from test_gate import good_card

def seeds(dirpath, values, canary_ok=True, loaded=0.98):
    dirpath.mkdir(parents=True, exist_ok=True)
    for i, v in enumerate(values):
        art = dirpath / f"pred_{i}.npy"; art.write_bytes(b"x" * (i + 1))
        (dirpath / f"seed_{i}.json").write_text(json.dumps({
            "seed": i, "metric": "mIoU_nyu_heldout_wrong", "value": v,
            "canary": {"expected": 49.95, "observed": 49.95 if canary_ok else 51.0, "tol": 0.10},
            "checkpoint_loaded_frac": loaded, "artifacts": [str(art)]}))

def ledger(path, run, secs):
    path.write_text(json.dumps({"event": "start", "run": run, "t": 0}) + "\n" +
                    json.dumps({"event": "stop", "run": run, "wall_s": secs, "exit": 0}) + "\n")

def test_render_aggregates(tmp_path):
    r = tmp_path / ".research"; (r / "records").mkdir(parents=True)
    seeds(tmp_path / "res", [2.0, 2.4, 2.2]); ledger(r / "ledger.jsonl", "m1", 7200)
    rec = render_record.render("m1", good_card(), tmp_path / "res", r / "ledger.jsonl", r)
    assert rec["n_realized"] == 3 and abs(rec["mean"] - 2.2) < 1e-9
    assert rec["ci95"][0] < 2.2 < rec["ci95"][1]
    assert rec["canary"]["pass"] is True and rec["cost_gpu_h"] == 2.0
    assert rec["band_hit"] is True and rec["kill_hit"] is False
    assert len(rec["artifacts"]) == 3 and all(len(a["sha256"]) == 64 for a in rec["artifacts"])
    assert (r / "records" / "m1.json").exists() and (r / "records" / "m1.md").exists()

def test_kill_hit_and_canary_fail(tmp_path):
    r = tmp_path / ".research"; (r / "records").mkdir(parents=True)
    seeds(tmp_path / "res", [0.1, 0.2, 0.0], canary_ok=False); ledger(r / "ledger.jsonl", "m2", 60)
    rec = render_record.render("m2", good_card(), tmp_path / "res", r / "ledger.jsonl", r)
    assert rec["kill_hit"] is True and rec["canary"]["pass"] is False

def test_check_record_rules(tmp_path):
    r = tmp_path / ".research"; (r / "records").mkdir(parents=True); (r / "verdicts").mkdir()
    seeds(tmp_path / "res", [2.0, 2.4], loaded=0.5); ledger(r / "ledger.jsonl", "m3", 60)
    rec = render_record.render("m3", good_card(), tmp_path / "res", r / "ledger.jsonl", r)
    fails = gate.check_record(rec, good_card())
    assert any("n_realized" in f for f in fails) and any("checkpoint" in f for f in fails)
