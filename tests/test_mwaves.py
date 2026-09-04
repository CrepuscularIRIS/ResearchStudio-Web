"""Stage M waves (v4): the finish script re-checks every quoted step line and keeps the gene/verify bookkeeping."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))
import bundle  # noqa: E402
import stage  # noqa: E402
from test_stage import ws  # noqa: E402

PAPER = "intro\nwe reweight every sample by a robust scale estimate before the mean\nthe estimator reaches 0.93 AUROC on the held-out set\nlimitations: the scale estimate breaks under heavy ties\n"


def test_quote_at_tolerates_pdftotext_breaks():
    assert bundle._quote_at(PAPER, "reweight every sample by a robust scale estimate", 2)
    assert bundle._quote_at(PAPER, "reweight every sample by a robust scale", 4), "±3 lines"
    assert not bundle._quote_at(PAPER, "reweight every sample by a robust scale", 9), "outside the file"
    assert not bundle._quote_at(PAPER, "an invented sentence that nobody wrote here", 2)


def test_mechanism_finish_checks_step_quotes(tmp_path, monkeypatch):
    w, r = ws(tmp_path)
    monkeypatch.setattr(bundle, "HERE", r); monkeypatch.setattr(bundle, "W", w); monkeypatch.setattr(stage, "HERE", r); monkeypatch.setattr(stage, "W", w)
    (r / "anomalies.md").write_text("measured: the gap is 6.61 mIoU on NYU\n")
    paper = tmp_path / "p.txt"; paper.write_text(PAPER)
    good = {"paper": "p", "title": "t", "text_path": str(paper),
            "steps": [{"text": "reweight samples by a robust scale estimate", "quote": "reweight every sample by a robust scale estimate before the mean", "line": 2}],
            "key_number": {"value": "0.93", "quote": "reaches 0.93 AUROC", "line": 3}, "avoid": "breaks under heavy ties",
            "avoid_quote": {"text": "breaks under heavy ties", "quote": "the scale estimate breaks under heavy ties", "line": 4}}
    bad = json.loads(json.dumps(good)); bad["steps"][0]["line"] = 30
    out = {"failure_modes": [{"id": "B1", "text": "x", "grounded_in": ["the gap is 6.61 mIoU"]}],
           "mechanisms": [{"id": "M1", "from": "B1", "levels": ["a", "b", "estimate a scale before aggregating"], "text": "scale before aggregating"}],
           "sources": [{"mechanism": "M1", "domain": "robust statistics", "name": "scale-normalised aggregation", "isomorphism": "i", "disanalogy": "d", "query": "robust scale estimate before aggregation",
                        "recipe": good, "precedent": {"found": False}, "genes": [{"paper": "p", "is_procedure": True, "n_steps": 1}], "verify": [{"paper": "p", "verdict": "accept"}]},
                       {"mechanism": "M1", "domain": "control", "name": "gain scheduling", "isomorphism": "i", "disanalogy": "d", "query": "gain scheduling under parameter drift",
                        "recipe": bad, "precedent": {"found": False}},
                       {"mechanism": "M1", "domain": "economics", "name": "winsorised mean", "isomorphism": "i", "disanalogy": "d", "query": "winsorised mean estimator",
                        "recipe": good, "precedent": {"found": True, "paper": "q", "quote": "we apply the winsorised mean to RGB-D segmentation under sensor failure", "line": 2, "text_path": str(paper)}}]}
    p = r / "bundles" / "mechanism-out.json"; p.write_text(json.dumps(out))
    res = bundle.cmd_mechanism_finish(str(p))
    mp = json.loads((r / "mechanism-map.json").read_text())
    by = {s["domain"]: s for s in mp["sources"]}
    assert by["robust statistics"]["status"] == "open" and by["robust statistics"]["recipe"]["steps"] == ["reweight samples by a robust scale estimate"]
    assert by["robust statistics"]["recipe"]["step_quotes"][0]["line"] == 2 and by["robust statistics"]["genes"][0]["paper"] == "p" and by["robust statistics"]["verify"][0]["verdict"] == "accept"
    assert by["control"]["status"] == "dropped" and "step 1 quote is not at line 30" in by["control"]["drop_reason"], "an invented step line costs the source"
    assert by["economics"]["status"] == "open", "a precedent quote that is not at its line is unverified, never a drop"
    assert by["economics"]["precedent"]["unverified"] is True
    assert res["open"] == 2
