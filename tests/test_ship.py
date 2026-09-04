"""Exit (a): `stage.py ship` records the owner's decision and stage D proceeds with the incumbent, never a KEEP."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))
import stage  # noqa: E402
from test_stage import ws, write_map, baseline, clean_ledger  # noqa: E402


def test_ship_refusals_and_stage_d(tmp_path):
    w, r = ws(tmp_path)
    write_map(r, stage.claim_sha(w))
    claim = stage.load_claim(w)
    ok, msg = stage.ship_incumbent(w, r, "owner", "no source reached the band")
    assert not ok and "pivot verdict" in msg
    (r / "gates" / "pivot-20260904T000000.json").write_text(json.dumps({"verdict": "ship_incumbent", "reasons": ["x"]}))
    ok, msg = stage.ship_incumbent(w, r, "owner", "no source reached the band")
    assert not ok and "baseline" in msg, "the incumbent needs a valid record to ship"
    qb = "Q-0001-beta"
    baseline(r, tmp_path / "wt-Q-0001-beta", mean=50.0, qid=qb)
    assert stage.decide(w, r, idle=[])["stage"] == "C", "no ship marker: the search continues"
    ok, msg = stage.ship_incumbent(w, r, "owner", "")
    assert not ok and "--why" in msg
    ok, msg = stage.ship_incumbent(w, r, "owner", "no source reached the band")
    assert ok and (r / "SHIP-INCUMBENT").exists()
    ev = [json.loads(l) for l in (r / "ledger.jsonl").read_text().splitlines()][-1]
    assert ev["event"] == "ship_incumbent" and ev["baseline_records"] == [qb] and ev["why"] == "no source reached the band"
    d = stage.decide(w, r, idle=[])
    assert d["stage"] == "W" and "exit (a)" in d["reason"] and d["next"][0] == "python3 .research/step.py write"
    clean_ledger(r)
    assert "deliverables" in stage.decide(w, r, idle=[])["next"][0]
    (w / "CLAIM.md").write_text((w / "CLAIM.md").read_text() + "\nedited\n")
    assert stage.decide(w, r, idle=[])["stage"] == "R", "a ship marker for another claim text is stale"
