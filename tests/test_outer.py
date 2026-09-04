"""The outer manuscript loop: passages and anchors, the ledger's intake / routing / gate, one round walked through the navigator."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))
import stage  # noqa: E402
import outer  # noqa: E402
import decompose  # noqa: E402
import paper_ledger as L  # noqa: E402
from test_stage import ws  # noqa: E402

Q = "Our method improves robustness across settings on every network."


def wk(summary, anchor=Q, sig="major", kind="substantive"):
    return {"summary": summary, "evidence_anchor": anchor, "section": "06_experiments.tex", "significance": sig, "kind": kind, "references": ""}


def test_decompose_locates_verbatim_anchors(tmp_path):
    w, r = ws(tmp_path)
    plist = decompose.passages(outer.sections(w))
    assert [p["id"] for p in plist] == ["05_method.tex:0", "05_method.tex:1", "06_experiments.tex:0", "06_experiments.tex:1"]
    assert decompose.locate("improves ROBUSTNESS   across settings", plist)["id"] == "06_experiments.tex:0", "whitespace and case do not matter"
    assert decompose.locate("a sentence nobody wrote in this paper", plist) is None
    assert decompose.locate("mask", plist) is None, "an anchor shorter than the floor never matches"


def test_ledger_intake_routing_and_gate():
    led = L.load(Path("/nonexistent"))
    a = L.add(led, {**wk("the robustness claim has no held-out evidence"), "passage_id": "06:0"}, "sol", 0)
    b = L.add(led, {**wk("robustness claim: no held-out evidence shown"), "passage_id": "06:0"}, "k3", 0)
    c = L.add(led, {**wk("three seeds is too few for the interval", sig="minor"), "passage_id": "06:1"}, "glm", 0)
    assert a["event"] == "new" and b["event"] == "corroborated" and b["id"] == a["id"] and c["event"] == "new"
    assert L.get(led, a["id"])["corroboration"] == 2 and L.get(led, a["id"])["significance"] == "major", "corroboration counts, never inflates significance"
    assert L.route(led) == {"in-trial": 1, "valid-fixable": 1}
    ok, bad = L.gate(led); assert not ok and bad[0].startswith(a["id"]) and len(bad) == 1, "only an active MAJOR blocks"
    L.set_status(led, a["id"], "closed", "drafted")
    assert L.gate(led)[0]
    d = L.add(led, {**wk("no held-out evidence for the robustness claim"), "passage_id": "06:0"}, "sol", 1)
    assert d["event"] == "reopened" and L.get(led, a["id"])["status"] == "raised" and L.get(led, a["id"]).get("reraised"), "a clean re-review re-raising a closed issue reopens it: the fix did not land"
    L.set_status(led, a["id"], "needs-data", "trial")
    assert L.bind_needs_data(led, "sha-1") == [a["id"]] and L.close_by_claim(led, "sha-1", ["Q-0002-alpha"], "keep") == [a["id"]]
    assert L.get(led, a["id"])["records"] == ["Q-0002-alpha"] and L.get(led, a["id"])["status"] == "closed"


def test_outer_round_walkthrough(tmp_path):
    w, r = ws(tmp_path)
    sha = stage.claim_sha(w)
    nxt = lambda done=(): outer.decide(w, r, "head", sha, list(done))
    assert nxt()["next"][0] == "python3 .research/step.py write", "no ledger: W0 writes the sections from records"
    (w / "paper" / "pr" / "main.tex").unlink()
    assert "write --merge" in nxt()["next"][0], "no manuscript at all: W0 is the merge"
    (w / "paper" / "pr" / "main.tex").write_text("x")
    led = L.load(r); L.start_round(led, 0); L.save(led, r)
    outer.intake_review(r, 0, {"verdict": "pass", "issues": ["style: em-dash budget"]})
    assert L.load(r)["issues"] == [], "style issues never become rows"
    d = nxt(); assert d["stage"] == "W" and d["next"][0] == "python3 .research/step.py read 0"
    res = outer.finish_read(w, r, 0, {"panel": {
        "sol": {"weaknesses": [wk("the robustness claim has no held-out evidence")], "per_section_coverage": [], "overall_confidence": 4},
        "k3": {"weaknesses": [wk("robustness claim without held-out evidence"), wk("an invented flaw", anchor="a quote that is not in the manuscript")], "per_section_coverage": [], "overall_confidence": 3},
        "glm": None}})
    assert res["filed"] == 2 and res["unanchored"] == 1 and res["new"] == 1 and res["corroborated"] == 1 and res["routed"]["in-trial"] == 1
    d = nxt(); assert d["next"][0] == "python3 .research/step.py trial 0"
    args = outer.cmd_trial(w, r, 0)
    assert "Our method improves" in args["charges"][0]["passage"] and "05_method.tex" in args["paper"] and len(args["jury"]) == 5
    rid = args["charges"][0]["id"]
    outer.finish_trial(r, 0, {"verdicts": [{"id": rid, "verdict": "needs-data", "close_criterion": "NetB × missing × mIoU", "tally": {"valid": 4, "invalid": 0, "context_limited": 1, "size": 5}, "rationale": "no held-out number"}]})
    d = nxt(); assert "needs-data" in d["reason"] and d["next"][0].startswith(f"human: {rid}")
    led = L.load(r); assert L.bind_needs_data(led, sha) == [rid]; L.save(led, r)
    d = nxt(done=["Q-0002-alpha"])
    assert L.get(L.load(r), rid)["status"] == "closed" and d["next"][0] == "python3 .research/step.py read 1", "the claim loop's records close the row; round 0 found something new, so round 1 reads again"
    res = outer.finish_read(w, r, 1, {"panel": {"sol": {"weaknesses": [wk("three seeds is too few for the interval", sig="minor")], "per_section_coverage": [], "overall_confidence": 4}}})
    assert res["genuinely_new"] == 1 and res["routed"]["valid-fixable"] == 1
    d = nxt(); assert d["next"][0] == "python3 .research/step.py draft 1"
    args = outer.cmd_draft(w, r, 1); rid2 = args["rows"][0]["id"]
    assert "MODE: PATCH" in args["rows"][0]["prompt"] and "06_experiments.tex" in args["rows"][0]["section"]
    bad = outer.finish_draft(w, r, 1, {"patches": [{"id": rid2, "patch": {"before": "three seeds", "after": "three seeds (73.2 mIoU)", "rationale": "x", "no_op": False}}]})
    assert bad["refused"] == 1 and L.get(L.load(r), rid2)["status"] == "author-required", "a patch that smuggles an unsourced number is refused and the section is untouched"
    assert "73.2" not in (w / "paper" / "pr" / "sections" / "06_experiments.tex").read_text()
    L.set_status(led := L.load(r), rid2, "valid-fixable", "test"); L.save(led, r)
    good = outer.finish_draft(w, r, 1, {"patches": [{"id": rid2, "patch": {"before": "three seeds", "after": "three seeds per arm", "rationale": "state the arm", "no_op": False}}]})
    assert good["closed"] == 1 and "three seeds per arm" in (w / "paper" / "pr" / "sections" / "06_experiments.tex").read_text()
    assert json.loads((r / "paper-journal.jsonl").read_text().splitlines()[-1])["after"] == "three seeds per arm"
    d = nxt(); assert "write --review" in d["next"][0], "after a draft the fact review runs again"
    time.sleep(1.1)
    outer.intake_review(r, 1, {"verdict": "pass", "issues": []})
    (r / "gates" / "write-review.json").write_text(json.dumps({"verdict": "pass", "issues": [], "t": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    d = nxt(); assert d["next"][0] == "python3 .research/step.py read 2", "round 1 found one genuinely new issue: read again"
    outer.finish_read(w, r, 2, {"panel": {"glm": {"weaknesses": [], "per_section_coverage": [], "overall_confidence": 5}}})
    outer.intake_review(r, 2, {"verdict": "pass", "issues": []})
    d = nxt(); assert "gate.py deliverables" in d["next"][0], "nothing genuinely new on a clean round: the paper is done"
