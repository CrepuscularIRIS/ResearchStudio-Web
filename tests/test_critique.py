"""The critique panel's script aggregation: anchored findings only, majority drop, worst spec verdict, and the navigator states."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))
import critique as cq  # noqa: E402
import stage  # noqa: E402
from test_stage import ws, write_map  # noqa: E402

TEXT = "## bundle\n{\"sources\": [{\"id\": \"S1\", \"recipe_steps\": [\"reweight samples by a robust scale estimate before the mean\"]}], \"graveyard\": [{\"id\": \"S9\", \"name\": \"dropout on the depth branch\"}]}"


def src(sid, verdict, rank, fails=(), anchor="reweight samples by a robust scale estimate"):
    return {"id": sid, "verdict": verdict, "rank": rank, "checks": [{"name": f, "result": "fail", "anchor": anchor, "why": "x"} for f in fails]}


def test_sources_majority_drop_needs_two_anchored_fails():
    panel = {"sol": {"sources": [src("S1", "drop", 2, ["naive_baseline"])]},
             "k3": {"sources": [src("S1", "drop", 1, ["naive_baseline"], anchor="an invented line nobody wrote here")]},
             "glm": {"sources": [src("S1", "keep", 2)]}}
    a = cq.aggregate_sources(panel, TEXT, ["S1"])["S1"]
    assert a["decision"] == "uncertain", "one anchored fail + one unanchored drop is not a majority"
    assert a["panel"]["k3"]["unanchored"] == ["naive_baseline"] and a["panel"]["k3"]["fails"] == []
    panel["k3"]["sources"][0]["checks"][0]["anchor"] = "dropout on the depth branch"
    a = cq.aggregate_sources(panel, TEXT, ["S1"])["S1"]
    assert a["decision"] == "drop" and a["rank_mean"] == 1.67 and not a["contested"]
    mp = {"sources": [{"id": "S1", "status": "open"}, {"id": "S2", "status": "open"}]}
    counts = cq.apply_sources(mp, cq.aggregate_sources(panel, TEXT, ["S1"]))
    assert counts["drop"] == 1 and mp["sources"][0]["status"] == "dropped" and "naive_baseline" in mp["sources"][0]["drop_reason"] and "sol" in mp["sources"][0]["drop_reason"]
    assert mp["sources"][1].get("critique") is None, "a source the panel did not judge is untouched"


def test_sources_rank_mean_and_contested_never_change_status():
    ids = ["S1", "S2", "S3", "S4"]
    panel = {"sol": {"sources": [src("S1", "keep", 1), src("S2", "keep", 4)]}, "k3": {"sources": [src("S1", "keep", 4), src("S2", "keep", 3)]}, "glm": None}
    a = cq.aggregate_sources(panel, TEXT, ids)
    assert a["S1"]["contested"] and a["S1"]["rank_mean"] == 2.5, "a spread of half the list is contested"
    assert not a["S2"]["contested"] and a["S2"]["rank_mean"] == 3.5
    assert a["S3"]["decision"] == "unjudged"
    mp = {"sources": [{"id": "S1", "status": "tried", "no_improve": 1}]}
    cq.apply_sources(mp, a)
    assert mp["sources"][0]["status"] == "tried" and mp["sources"][0]["critique"]["contested"]


def test_spec_worst_verdict_after_anchor_cap():
    text = "spec: {\"kill_cmd\": \"python train.py --out $RESULTS_DIR\", \"steps\": [{\"change\": \"scale the depth mask by a uniform factor in [0.05, 1]\"}]}"
    f = lambda sev, q="scale the depth mask by a uniform factor": {"check": "naive_equivalence", "severity": sev, "quote": q, "text": "t"}
    panel = {"sol": {"verdict": "abandon", "findings": [f("blocking", "a quote that is not in the spec at all")], "revision_target": ""},
             "k3": {"verdict": "advance", "findings": [], "revision_target": ""}, "glm": None}
    a = cq.aggregate_spec(panel, text)
    assert a["per_model"]["sol"]["effective"] == "advance" and a["verdict"] == "advance", "an abandon with no anchored blocking finding is capped to advance"
    panel["sol"]["findings"] = [f("major")]; panel["sol"]["revision_target"] = "drop the uniform factor"
    a = cq.aggregate_spec(panel, text)
    assert a["per_model"]["sol"]["effective"] == "revise" and a["verdict"] == "revise" and a["revision_target"] == ["sol: drop the uniform factor"]
    panel["glm"] = {"verdict": "abandon", "findings": [f("blocking")], "revision_target": ""}
    assert cq.aggregate_spec(panel, text)["verdict"] == "abandon", "the worst anchored verdict wins (fail-closed)"
    assert cq.aggregate_spec({"sol": None, "k3": None}, text) is None, "no family answered = infrastructure, not a verdict"


def test_penalize_source_counts_toward_patience(tmp_path):
    r = tmp_path; (r / "mechanism-map.json").write_text(json.dumps({"sources": [{"id": "S1", "status": "open", "no_improve": 0}]}))
    assert cq.penalize_source("S1", "Q-0001-alpha: naive", rdir=r)["status"] == "tried"
    assert cq.penalize_source("S1", "Q-0002-alpha: naive", rdir=r)["status"] == "exhausted"
    mp = json.loads((r / "mechanism-map.json").read_text())
    assert mp["sources"][0]["no_improve"] == 2 and len(mp["sources"][0]["critique_abandons"]) == 2 and "best" not in mp["sources"][0]


def test_navigator_slot1_and_slot2_states(tmp_path):
    w, r = ws(tmp_path)
    write_map(r, stage.claim_sha(w), sources=[{"id": "S1", "mechanism": "M1", "domain": "d", "name": "n", "status": "open", "best": None, "no_improve": 0, "tried": [], "critique": None}])
    mp = json.loads((r / "mechanism-map.json").read_text()); mp["sources"][0].pop("critique"); (r / "mechanism-map.json").write_text(json.dumps(mp))
    d = stage.decide(w, r, idle=[])
    assert d["stage"] == "M" and "critique sources" in d["next"][0], "an eligible source without a critique blocks every spec (Slot 1)"
    time.sleep(0.02); (r / "bundles" / "critique-sources-out.json").write_text("{}")
    assert "critique --finish sources" in stage.decide(w, r, idle=[])["next"][0]
    write_map(r, stage.claim_sha(w))
    assert stage.decide(w, r, idle=[])["stage"] == "C"
    claim = stage.load_claim(w); cfg = claim["chains"]["alpha"]
    nxt = lambda: stage.chain_next("alpha", cfg, claim, r, [0, 1], lambda run: False)
    q = "Q-0001-alpha"
    (r / "bundles" / f"spec-{q}.json").write_text("{}"); (r / "gates" / f"{q}.spec.ok").write_text("t\n")
    assert nxt()["state"] == "critique_pending" and nxt()["lines"][0] == f"python3 .research/step.py critique spec {q}"
    out = r / "bundles" / f"critique-out-{q}.json"; out.write_text("{}")
    assert nxt()["state"] == "critique_out" and f"critique --finish spec {q} {out}" in nxt()["lines"][0]
    time.sleep(0.02); (r / "critique" / f"{q}.json").write_text(json.dumps({"verdict": "revise"}))
    assert nxt()["state"] == "spec_retry" and "--retry" in nxt()["lines"][0]
    (r / "gates" / f"{q}.spec.retries").write_text("1\n")
    assert nxt()["state"] == "critique_revise_twice" and "queue" in nxt()["lines"][0]
    (r / "critique" / f"{q}.json").write_text(json.dumps({"verdict": "abandon"}))
    assert nxt()["state"] == "critique_abandon"
    (r / "critique" / f"{q}.json").write_text(json.dumps({"verdict": "advance"}))
    assert nxt()["state"] == "spec_written" and "propose --finish" in nxt()["lines"][0]
    beta = claim["chains"]["beta"]
    (r / "bundles" / "spec-Q-0001-beta.json").write_text("{}"); (r / "gates" / "Q-0001-beta.spec.ok").write_text("t\n")
    assert stage.chain_next("beta", beta, claim, r, [0, 1], lambda run: False)["state"] == "spec_written", "the baseline chain skips the panel"
