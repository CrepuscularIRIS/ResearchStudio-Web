import json, pathlib, sys, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import gate, gapmap

GOAL = {"campaign": {"metric": "mIoU_nyu_heldout_wrong", "metric_direction": "maximize",
        "gpu_h_ceiling": 100, "caps": {"oracle_frac": 0.05, "single_run_frac": 0.25, "reserve_frac": 0.2},
        "run_name": "t", "protected_paths": ["scripts/eval.py", "local_configs/**"],
        "test_baseline_score": 50.0, "merge_margin": None}}


def base_card():
    return {
        "id": "C-0001",
        "claim": "Training against smooth-wrong depth raises held-out wrong-depth mIoU",
        "mechanism": "m", "forbids": "clean mIoU drop > 0.5",
        "prediction": {"metric": "mIoU_nyu_heldout_wrong", "band": [1.5, 3.0], "direction": "maximize"},
        "kill": {"metric": "mIoU_nyu_heldout_wrong", "threshold": 0.3, "rule": "mean below threshold"},
        "controls": ["absent-depth arm"], "seed_sd": 0.564, "n_required": 3, "mde": 1.29,
        "instrument": {"checkpoint": "ckpt.pth", "reference_number": 54.93, "canary": "entire_missing 49.95 ± 0.10"},
        "oracle": {"design": "gt mask", "cost_gpu_h": 0.5, "pass": "delta > oracle_mde"},
        "tier": "T4", "cost_gpu_h": 20, "frozen_sha": None, "arbor_node": None,
    }


def good_card():                      # schema 1 (v6, in-flight cards)
    return {**base_card(), "bridge": "bridges/2026-09-03.md#1"}


def good_card2():                     # schema 2 (minimal loop)
    return {**base_card(), "schema": 2, "parent": "ROOT", "mediator": "depth pathway gain",
            "conflicts": "none — attacks an axis the deaths left unexplored",
            "source_insights": ["2608.09381"], "cites": ["GOAL", "2608.09381"], "source_lens": "anomaly"}


INSIGHT = """---
paper: "2608.09381"
title: JEPA-WAM
year: 2026
domain: robot manipulation VLA
predecessor: {paper: "2602.10098", assumed: "the world model is a separate module beside the policy"}
old_belief: a world model predicts the next state
anomaly: predicting the endpoint difference scores below not predicting at all
gap_crossed: the transition target was the wrong object
core_insight: predict joint(current, future) on the policy backbone
hidden_hypothesis: the two-frame tubelet defines the transition geometry
fragile_assumption: visual transitions are shared across instructions
relies_on:
  - {noun: state, type: "frozen V-JEPA 2.1 latent", line: 3}
  - {noun: supervision, type: "patch-level cosine on joint target", line: 5}
changes:
  - {noun: future, old_type: "next-state latent", new_type: "joint(current, future) latent", line: 5}
sign_flips:
  - {observation: "endpoint difference target", expected: "beats no prediction", observed: "70.9 below 77.0", where: 7}
untested: ["language-conditioned target"]
reproduce: {code: yes, compute: "8 GPU-days", key_number: 79.2, where: 5}
naive_baseline: "an auxiliary next-frame loss on a separate head does not shape the policy backbone"
mechanism: joint transition target on a shared predictor
innovation_mechanism: [F, A]
critical_experiment: joint 79.2 vs future-only 77.3 vs diff 70.9
ablation_gaps: ["no leakage on/off switch"]
formulations:
  - {question: q1, hypothesis: h1, minimal_experiment: e1, kills: k1, conflicts: none}
  - {question: q2, hypothesis: h2, minimal_experiment: e2, kills: k2, conflicts: none}
  - {question: q3, hypothesis: h3, minimal_experiment: e3, kills: k3, conflicts: none}
provenance:
  stated:
    - {claim: "joint target achieves 79.2", line: 5}
  inferred: []
  abduced: ["path"]
  speculated: []
---
""" + "body " * 400

PAPER = "\n".join(["l1", "l2", "frozen V-JEPA 2.1 encoder", "l4",
                   "The joint current-future target achieves 79.2%, compared with 77.3% for future-only",
                   "l6", "Endpoint difference 70.9 vs V-JEPA only 77.0", "l8"])


def research_dir(tmp_path, with_bridge=True, with_packet=True, with_insight=True):
    r = tmp_path / ".research"
    for d in ("cards", "bridges", "lit", "records", "insight", "verdicts"): (r / d).mkdir(parents=True)
    if with_bridge: (r / "bridges" / "2026-09-03.md").write_text("## 1\n- domain_a: x\n")
    if with_packet: (r / "lit" / "2026-09-03-1.md").write_text("packet")
    if with_insight: (r / "insight" / "2608.09381.md").write_text(INSIGHT)
    (r / "ledger.jsonl").write_text("")
    return r


# ── card, both schemas ───────────────────────────────────────────────────────

def test_mde_lehr():
    assert math.isclose(gate.mde_lehr(0.564, 3), 2.8 * 0.564 * math.sqrt(2 / 3))

def test_good_card_passes(tmp_path):
    assert gate.check_card(good_card(), GOAL, research_dir(tmp_path)) == []

def test_good_card2_passes(tmp_path):
    assert gate.check_card(good_card2(), GOAL, research_dir(tmp_path)) == []

def test_card_fails_on_n_and_mde(tmp_path):
    c = good_card(); c["n_required"] = 2; c["mde"] = 0.1
    fails = gate.check_card(c, GOAL, research_dir(tmp_path))
    assert any("n_required" in f for f in fails) and any("mde" in f for f in fails)

def test_card_fails_when_band_below_mde(tmp_path):
    c = good_card2(); c["prediction"]["band"] = [0.5, 1.0]
    assert any("band" in f for f in gate.check_card(c, GOAL, research_dir(tmp_path)))

def test_schema1_fails_without_packet(tmp_path):
    fails = gate.check_card(good_card(), GOAL, research_dir(tmp_path, with_packet=False))
    assert any("packet" in f for f in fails)

def test_schema2_needs_no_bridge(tmp_path):
    assert gate.check_card(good_card2(), GOAL, research_dir(tmp_path, with_bridge=False, with_packet=False)) == []

def test_schema2_fails_without_source_insight(tmp_path):
    fails = gate.check_card(good_card2(), GOAL, research_dir(tmp_path, with_insight=False))
    assert any("source insight" in f for f in fails)

def test_schema2_fails_on_bad_parent_and_empty_cites(tmp_path):
    c = good_card2(); c["parent"] = "C-9999"; c["cites"] = []
    fails = gate.check_card(c, GOAL, research_dir(tmp_path))
    assert any("parent" in f for f in fails) and any("cites" in f for f in fails)

def test_schema2_cites_must_resolve(tmp_path):
    c = good_card2(); c["cites"] = ["no-such-thing"]
    assert any("resolves to nothing" in f for f in gate.check_card(c, GOAL, research_dir(tmp_path)))

def test_schema2_lens_must_be_known(tmp_path):
    c = good_card2(); c["source_lens"] = "vibes"
    assert any("source_lens" in f for f in gate.check_card(c, GOAL, research_dir(tmp_path)))

def test_card_fails_on_duplicate_claim(tmp_path):
    r = research_dir(tmp_path)
    (r / "cards" / "C-0000.json").write_text(json.dumps({**good_card2(), "id": "C-0000"}))
    assert any("duplicate" in f for f in gate.check_card(good_card2(), GOAL, r))

def test_card_own_records_are_not_duplicates(tmp_path):
    """v6 defect: after the oracle landed, the card's own record made gate.py card refuse the full launch."""
    r = research_dir(tmp_path); c = good_card2()
    (r / "records" / "C-0001-oracle.json").write_text(json.dumps({"card": "C-0001", "claim_norm": gate._norm(c["claim"])}))
    assert gate.check_card(c, GOAL, r) == []
    (r / "records" / "C-0000-full.json").write_text(json.dumps({"card": "C-0000", "claim_norm": gate._norm(c["claim"])}))
    assert any("already measured" in f for f in gate.check_card(c, GOAL, r))

def test_card_fails_over_budget(tmp_path):
    c = good_card2(); c["cost_gpu_h"] = 90
    assert any("budget" in f for f in gate.check_card(c, GOAL, research_dir(tmp_path)))

def test_sha_ignores_mutable_fields():
    a = good_card2(); b = good_card2(); b["frozen_sha"] = "x"; b["arbor_node"] = "n1"
    assert gate.card_sha(a) == gate.card_sha(b)

def test_freeze_without_critique_is_fine(tmp_path):
    r = research_dir(tmp_path); p = r / "cards" / "C-0001.json"
    p.write_text(json.dumps(good_card2()))
    assert gate.freeze_card(p) == 0 and json.loads(p.read_text())["frozen_sha"]

def test_freeze_refuses_after_critique_change(tmp_path):
    r = research_dir(tmp_path); p = r / "cards" / "C-0001.json"
    p.write_text(json.dumps(good_card()))
    crit = tmp_path / "crit.md"; crit.write_text("fine")
    assert gate.record_critique(p, crit) == 0
    c = json.loads(p.read_text()); c["claim"] += " (edited)"; p.write_text(json.dumps(c))
    assert gate.freeze_card(p) == 1


# ── screen · insight · graph ─────────────────────────────────────────────────

def test_screen_selects_text_and_score_and_skips_done(tmp_path):
    r = research_dir(tmp_path)
    man = [{"id": "a", "status": "text", "relevance_score": 3, "citation_count": 5},
           {"id": "b", "status": "text", "relevance_score": 1},
           {"id": "c", "status": "no_text", "relevance_score": 9},
           {"id": "2608.09381", "status": "text", "relevance_score": 9}]   # already reverse-engineered
    got = gate.screen(man, r / "insight", min_score=2, max_n=10)
    assert [p["id"] for p in got] == ["a"]

def test_insight_form_checks():
    assert gapmap.check_insight(INSIGHT) == []
    short = INSIGHT.replace("body " * 400, "stub")
    assert any("body" in f for f in gapmap.check_insight(short))
    two = INSIGHT.replace("  - {question: q3, hypothesis: h3, minimal_experiment: e3, kills: k3, conflicts: none}\n", "")
    assert any("formulations" in f for f in gapmap.check_insight(two))
    nostated = INSIGHT.replace('    - {claim: "joint target achieves 79.2", line: 5}\n', "")
    assert any("provenance.stated" in f for f in gapmap.check_insight(nostated))
    nopred = INSIGHT.replace('predecessor: {paper: "2602.10098", assumed: "the world model is a separate module beside the policy"}',
                             "predecessor: {paper: '', assumed: ''}")
    assert any("predecessor" in f for f in gapmap.check_insight(nopred))
    assert gapmap.check_insight("no front matter") == ["no YAML front-matter block (--- ... ---) at the top of the file"]

def test_insight_line_refs_verified_against_paper():
    assert gapmap.check_insight(INSIGHT, PAPER) == []
    wrong_num = INSIGHT.replace('claim: "joint target achieves 79.2", line: 5', 'claim: "joint target achieves 81.2", line: 5')
    assert any("81.2" in f for f in gapmap.check_insight(wrong_num, PAPER))
    out_of_range = INSIGHT.replace('line: 3}', 'line: 99}')
    assert any("outside" in f for f in gapmap.check_insight(out_of_range, PAPER))

def _card(paper, dom, relies, changes=(), flips=()):
    return {"paper": paper, "domain": dom, "_file": f"{paper}.md", "formulations": [], "ablation_gaps": [],
            "relies_on": [{"noun": n, "type": t} for n, t in relies],
            "changes": [{"noun": n, "old_type": o, "new_type": w} for n, o, w in changes],
            "sign_flips": [dict(observation=o, expected="up", observed="down", where=1) for o in flips]}

def test_graph_bridges_unchallenged_flips():
    cards = [
        _card("p1", "A", [("future", "next-state latent")]),
        _card("p2", "A", [("future", "Next State Latent")]),                      # same type, different casing
        _card("p3", "B", [("future", "joint latent")], changes=[("future", "next-state latent", "joint latent")]),
        _card("p4", "A", [("state", "frozen encoder latent")]),
        _card("p5", "B", [("state", "frozen encoder latent")]),
        _card("p6", "C", [("state", "frozen encoder latent")], flips=["history adds nothing"]),
    ]
    g = gapmap.build(cards)
    assert g["bridges"] and g["bridges"][0]["noun"] == "future" and g["bridges"][0]["domain"] == "A"
    assert g["bridges"][0]["changed_by"][0]["paper"] == "p3"
    assert [u["noun"] for u in g["unchallenged"]] == ["state"]
    fl = [(f["noun"], f["to"]) for f in g["flips"]]
    assert ("future", "joint latent") in fl and all(f["noun"] != "state" for f in g["flips"])
    assert g["sign_flips"][0]["paper"] == "p6"
    md = gapmap.render(g, cards, ["C-0000: dead"])
    assert "| B1 | future |" in md and "| U1 | state |" in md and "| F1 | future |" in md and "C-0000: dead" in md
    cand = gapmap.candidates(g)
    assert set(cand) == {"flips", "sign_flips", "bridges", "unchallenged", "dropped"} and cand["dropped"] == []
    k = cand["flips"][0]["key"]
    cand2 = gapmap.candidates(g, {k: {"check": 2, "cycle": "0001", "reason": "label only"}})
    assert all(f["key"] != k for f in cand2["flips"]) and cand2["dropped"][0]["key"] == k


# ── merge guard · tree ───────────────────────────────────────────────────────

def test_merge_decision_rules():
    card = good_card2(); ok = {"state": "SUPPORTED"}
    rec = {"card": "C-0001", "mean": 52.0}
    assert gate.merge_decision(card, ok, rec, GOAL, ["scripts/model.py"]) == []
    assert any("SUPPORTED" in f for f in gate.merge_decision(card, {"state": "CONTESTED"}, rec, GOAL, []))
    assert any("margin" in f for f in gate.merge_decision(card, ok, {"card": "C-0001", "mean": 50.5}, GOAL, []))
    assert any("protected" in f for f in gate.merge_decision(card, ok, rec, GOAL, ["local_configs/nyu.py"]))
    g = json.loads(json.dumps(GOAL)); g["campaign"]["test_baseline_score"] = None
    assert any("baseline" in f for f in gate.merge_decision(card, ok, rec, g, []))

def test_render_tree_walks_parents():
    cards = {"C-1": {**good_card2(), "id": "C-1", "frozen_sha": "x"},
             "C-2": {**good_card2(), "id": "C-2", "parent": "C-1", "claim": "child"}}
    verdicts = {"C-1": {"state": "REFUTED"}}
    md = gate.render_tree(cards, verdicts)
    assert "- C-1 [REFUTED]" in md and "  - C-2 [DRAFT] child" in md and "C-1:" in md.split("## Graveyard")[1]


# ── schema 3 candidates · FROZEN ─────────────────────────────────────────────

def good_card3():
    return {"schema": 3, "id": "Q-0001", "parent": "ROOT",
            "claim": "A severity readout from the frozen activation gates removal at least as well as the monocular rank statistic",
            "method": "activation-readout gate", "family": "gate",
            "ceiling": {"value": 2.13, "source": "oracle-routed saving, CMNeXt, paper/.claude/CLAUDE.md"},
            "prediction": {"metric": "mIoU_test_half_structured", "band": [1.0, 99.0], "direction": "maximize"},
            "kill": {"metric": "mIoU_test_half_structured", "threshold": 0.3, "rule": "gated gain below 0.3 on the kill rung", "gpu_h": 0.5,
                     "cmd": "python scripts/eval_robust_suite.py --gate readout"},
            "keep": {"rule": "gain >= 1.0 on 2 of 3 networks, clean cost <= 0.2"},
            "cost_gpu_h": 1.0, "cites": ["GOAL"], "frozen_sha": None}

def test_schema3_candidate_passes(tmp_path):
    assert gate.check_card(good_card3(), GOAL, research_dir(tmp_path)) == []

def test_schema3_refuses_bad_family_cap_and_empty_keep(tmp_path):
    c = good_card3(); c["family"] = "vibes"; c["kill"]["gpu_h"] = 40; c["keep"]["rule"] = ""
    f = gate.check_card(c, GOAL, research_dir(tmp_path))
    assert any("family" in x for x in f) and any("kill_cap" in x for x in f) and any("keep.rule" in x for x in f)

def test_schema3_duplicate_method(tmp_path):
    r = research_dir(tmp_path)
    (r / "cards" / "Q-0000.json").write_text(json.dumps({**good_card3(), "id": "Q-0000"}))
    assert any("duplicate" in x for x in gate.check_card(good_card3(), GOAL, r))

def test_record_check_defaults_n_required_to_one_for_candidates():
    rec = {"n_realized": 1, "canary": {"pass": True}, "checkpoint_loaded_frac": 1.0, "card": "Q-0001", "artifacts": []}
    assert gate.check_record(rec, good_card3()) == []

def test_frozen_block_gate(tmp_path):
    ws = tmp_path; r = ws / ".research"; r.mkdir()
    (ws / "GOAL.md").write_text("```yaml\ncampaign: {run_name: t}\n```\n## FROZEN\nthe problem\n## Other\nx\n")
    assert gate.frozen_text(ws).startswith("## FROZEN") and "Other" not in gate.frozen_text(ws)
    assert any("nobody accepted" in f for f in gate.frozen_check(ws, r))
    (r / "FROZEN.sha").write_text(gate.frozen_sha(ws) + "\n")
    assert gate.frozen_check(ws, r) == []
    (ws / "GOAL.md").write_text("```yaml\ncampaign: {run_name: t}\n```\n## FROZEN\nthe problem, edited\n## Other\nx\n")
    assert any("changed" in f for f in gate.frozen_check(ws, r))
    (ws / "GOAL.md").write_text("```yaml\ncampaign: {run_name: t}\n```\n## Other\nx\n")
    assert gate.frozen_check(ws, r) == []          # no block, no gate
