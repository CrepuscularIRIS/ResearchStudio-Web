#!/usr/bin/env python3
"""Build layered run-dir fixtures for the ideaspark differential test.

Each fixture is the previous one plus exactly one more artifact, so the pair
(upstream `run.py next`, the workflow's decide()) is compared at every node of the
phase graph. Written under <out>/NN_<name>/.

  python3 ideaspark_fixtures.py <out_dir>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ideaspark_fixtures").resolve()
_VENDOR = Path(__file__).resolve().parents[1] / "vendor/researchstudio"
RS_REF = Path(os.environ.get("RS_HOME") or (_VENDOR if _VENDOR.exists() else
              "/home/lingxufeng/autoresearch/ResearchStudio/ResearchStudio-Idea")) / "skills/idea_spark/references"

# a real (cluster, parent slug, parent display name) triple from references/ideation-sub-patterns/overview.md
SUB = "C12 (Substitute the Operator or Representation)"
PARENT = "architectural_operator_substitution"

CANDIDATE = {
    "title": "Operator-substituted routing for long-horizon control",
    "hook": "one line",
    "core_mechanism": "Replace the softmax router with a monotone gate.",
    "core_mechanism_reasoning": "PREMISES ledger ... NAIVE-BASELINE AUDIT ... design rationale.",
    "core_mechanism_steps": ["step one", "step two"],
    "gap_closure": [{"gap": "the anchor gap", "main_pattern": PARENT, "sub_pattern": SUB, "how_closed": "by substituting the operator"}],
    "falsification_prediction": "Minimal experiment: A vs B on the same split; the gate norm is the load-bearing variable; permuting it returns the downstream metric to baseline.",
    "compute_budget": "about 4 GPU-days on 80GB-class hardware.",
    "differentiation_from_lit": [{"paper_id": "arxiv:2501.00001", "delta": "different operator"}],
    "almost_prior_paper_id": "arxiv:2501.00001",
    "what_step_was_missed": "they never substituted the operator",
    "signature_terms": ["monotone routing gate", "operator substituted router"],
    "alias_terms": ["gated mixture routing"],
    "composition_note": "anchor-only, defended.",
}
PHASE1 = {
    "intake": {"domain": "control", "task": "long-horizon control", "contribution_type": "method"},
    "_inferred_fields": ["venue"],
    "bottleneck_statement": "Routing saturates (arxiv:2501.00001, arxiv:2501.00002).",
    "closest_adjacent": [{"paper_id": "arxiv:2501.00001", "summary_and_residue": "residue"},
                         {"paper_id": "arxiv:2501.00002", "summary_and_residue": "residue"},
                         {"paper_id": "arxiv:2501.00003", "summary_and_residue": "residue"}],
    "what_phase_0_did_not_address": ["gap one, at a stated cost", "gap two, at a stated cost"],
    "state": "proceed",
}
SELECT = {"selected_gaps": [{"gap": "the anchor gap", "chosen_pattern_id": PARENT}],
          "coherence_thread_type": "n_a", "composition_note": "anchor-only, defended.",
          "pattern_saturation": "medium", "deferred_gaps": []}
COHERENCE_PASS = {"verdict": "pass", "unrepaired": [], "trace": {"t1": "ok"}}
COHERENCE_BLOCKING = {"verdict": "pass", "unrepaired": [
    {"severity": "blocking", "finding": "the acceptance probability is 4**-24, so the loop never terminates",
     "reading_dependence": "reading_robust", "structural_requirement": "an identifying condition is needed"}]}
CRITIQUE_ADVANCE = {"verdict": "advance", "verdict_rationale": "no threat found; all five checks clean.",
                    "paper_pointed_threat": {"threat_paper_id": "no_threat_found", "addressable_via": "n_a"},
                    "gap_closure_reject_check": {"entries": []}, "recipe_application_check": {"verdict": "applied", "entries": []},
                    "anti_pattern_check": {"matched_pattern_id": "none"}, "revision_targets": []}


def w(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1) if not isinstance(obj, str) else obj, encoding="utf-8")


def lit_results(n: int = 8) -> dict:
    return {"query": "operator substitution for long-horizon control", "queries_run": ["q1"], "n_papers": n,
            "lit_grounding_mode": "real",
            "papers": [{"paper_id": f"arxiv:250100{i:03d}", "title": f"Paper {i}", "abstract": "abstract",
                        "year": 2025, "year_month": "2025-06", "venue": "arXiv", "authors": ["A"],
                        "citations": 0, "source": "arxiv", "retrieved_via": "arxiv", "relevance": "core"} for i in range(n)]}


def lit_table(n: int = 8, extra_ids: list[str] | None = None) -> str:
    head = ("| paper_id | year_month | venue | title | ideation pattern tags | bottleneck this paper targets | "
            "open issue / unresolved gap | resolves_problem | retrieved_via |\n|---|---|---|---|---|---|---|---|---|\n")
    rows = [f"| arxiv:250100{i:03d} | 2025-06 | arXiv | Paper {i} | {{{PARENT}}} | routing saturation | open | | arxiv |" for i in range(n)]
    for pid in (extra_ids or []):
        rows.append(f"| {pid} | 2025-07 | arXiv | Host paper | {{{PARENT}}} | routing saturation | open | | host_recall |")
    return head + "\n".join(rows) + "\n"


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    stage = OUT / "_stage"
    stage.mkdir()
    order = []

    def snap(name: str) -> None:
        order.append(name)
        shutil.copytree(stage, OUT / f"{len(order):02d}_{name}")

    snap("fresh")

    p0 = stage / "phase0"
    w(p0 / "lit_results.json", lit_results())
    (p0 / ".lit_grounding_mode").write_text("real")
    (p0 / "user_query.txt").write_text("operator substitution for long-horizon control\n")
    w(p0 / "user_refs.json", [])
    snap("retrieved")

    w(p0 / "relevance_partition.json", [{"paper_id": f"arxiv:250100{i:03d}", "relevance": "core", "reason": "on topic"} for i in range(8)])
    snap("partition_written")

    (p0 / ".partition_applied").touch()
    snap("partition_applied")

    (p0 / "lit_table.md").write_text(lit_table())
    snap("tagged")

    w(p0 / "host_refs_nominations.json", [])
    snap("nominations")

    w(p0 / "host_refs.json", [])
    snap("host_refs_empty")

    # a second branch: one admitted host ref that still needs a row
    shutil.copytree(stage, OUT / "07b_host_refs_admitted")
    w(OUT / "07b_host_refs_admitted" / "phase0" / "host_refs.json",
      [{"paper_id": "arxiv:2507rec01", "title": "Host paper", "retrieved_via": "host_recall"}])

    (p0 / ".coverage_check_done").touch()
    snap("coverage_done")

    w(p0 / "fulltext_cache.json", {f"arxiv:250100{i:03d}": {"tier": "T3", "intro": "intro", "method": "method text", "source_used": "html"} for i in range(3)})
    snap("fulltext")

    # do_not_generate branch
    dng = OUT / "10b_phase1_dng"
    shutil.copytree(stage, dng)
    w(dng / "phase1" / "phase1_output.json", dict(PHASE1, state="do_not_generate", ood_reasons=["too_broad"], remedial_steps=["narrow it"]))

    w(stage / "phase1" / "phase1_output.json", PHASE1)
    snap("phase1")

    w(stage / "phase2_select" / "phase2_select_output.json", SELECT)
    snap("select")

    # citation-gate failure branch: a sub_pattern citation whose parent does not match
    bad = OUT / "12b_citation_fail"
    shutil.copytree(stage, bad)
    w(bad / "phase2_generate" / "phase2_generate_output.json",
      dict(CANDIDATE, gap_closure=[dict(CANDIDATE["gap_closure"][0], sub_pattern="C02 (Substitute the Operator or Representation)")]))

    w(stage / "phase2_generate" / "phase2_generate_output.json", CANDIDATE)
    snap("generated")

    # coherence: invalid verdict branch
    badv = OUT / "13b_coherence_invalid"
    shutil.copytree(stage, badv)
    w(badv / "phase2_coherence" / "phase2_coherence_output.json", {"verdict": "unclear"})

    w(stage / "phase2_coherence" / "phase2_coherence_output.json", COHERENCE_PASS)
    snap("coherence_pass")

    w(stage / "phase3_collision" / "collision_hits.json", {"hits": [], "n_hits": 0})
    w(stage / "phase3_collision" / ".collision_terms.json",
      {"signature_terms": CANDIDATE["signature_terms"], "alias_terms": CANDIDATE["alias_terms"]})
    snap("collision")

    # audit branches built off the collision state
    for name, doc in (("advance", CRITIQUE_ADVANCE),
                      ("abandon", dict(CRITIQUE_ADVANCE, verdict="abandon",
                                       paper_pointed_threat={"threat_paper_id": "arxiv:2501.00001", "addressable_via": "unaddressable",
                                                             "subsumption_argument": "same mechanism"})),
                      ("revise", dict(CRITIQUE_ADVANCE, verdict="revise",
                                      revision_targets=[{"scope": "tactical", "field": "core_mechanism", "what": "state the premise"}]))):
        b = OUT / f"16b_audit_{name}"
        shutil.copytree(stage, b)
        w(b / "phase3_critique" / "phase3_critique_output.json", doc)

    # blocking-evidence guard: 2.3 produced a blocking finding, the audit advanced without dispositioning it
    g = OUT / "16c_blocking_undispositioned"
    shutil.copytree(stage, g)
    w(g / "phase2_coherence" / "phase2_coherence_output.json", COHERENCE_BLOCKING)
    w(g / "phase2_coherence" / "blocking_findings.json", [{"finding": "acceptance probability 4**-24", "verbatim_step_quote": "resample R=16 times"}])
    w(g / "phase3_critique" / "phase3_critique_output.json", CRITIQUE_ADVANCE)

    # …and the same audit WITH a refuted disposition (routes to the bounded re-check)
    g2 = OUT / "16d_blocking_refuted"
    shutil.copytree(g, g2)
    w(g2 / "phase3_critique" / "phase3_critique_output.json",
      dict(CRITIQUE_ADVANCE, blocking_findings_disposition=[{"finding_ref": "acceptance probability 4**-24", "status": "refuted", "basis": "arithmetic error in the gate script"}]))

    w(stage / "phase3_critique" / "phase3_critique_output.json", CRITIQUE_ADVANCE)
    snap("audit_advance")

    p4 = stage / "phase4"
    w(p4 / "phase4_skeleton.json", {"title": "<TODO[title]: hint>", "falsification_prediction": CANDIDATE["falsification_prediction"]})
    snap("skeleton")

    w(p4 / "fill_map.json", {"title": "Operator-substituted routing"})
    snap("fill_map")

    w(p4 / "phase4_expansion.json", {"title": "Operator-substituted routing", "title_zh": "<TODO[title_zh]: hint>",
                                     "plain_motivation_en": "<TODO[plain_motivation_en]: hint>"})
    snap("expansion_partial")

    w(p4 / "derive_map.json", {"title_zh": "算子替换路由", "plain_motivation_en": "plain english"})
    snap("derive_map")

    w(p4 / "phase4_expansion.json", {"title": "Operator-substituted routing", "title_zh": "算子替换路由",
                                     "plain_motivation_en": "plain english", "method_flow": {"steps": [{"step_id": "S1"}]}})
    snap("expansion_full")

    w(p4 / "method_view.json", {"method_flow": {"steps": [{"step_id": "S1"}]}})
    snap("method_view")

    w(p4 / "phase4_implementability.json", {"enriched_steps": [{"step_id": "S1", "what_changes": "x", "what_to_do_en": "y", "what_to_do_zh": "z"}],
                                            "underspecified_points": []})
    snap("impl")

    for c in ("idea.std.zh.md", "idea.std.en.md", "idea.detail.en.md"):
        (p4 / c).write_text("# Title\n\n## Motivation\n\nm\n\n## Method\n\n1. step\n")
    snap("cards")

    # ---- branches that only appear after a verdict, built off earlier snapshots ----
    coll = OUT / "14_collision"

    def fork(name: str, src: Path) -> Path:
        dst = OUT / name
        shutil.copytree(src, dst)
        return dst

    # 2.3 patched, merger not yet run
    f = fork("24_coherence_patched", OUT / "12_generated")
    w(f / "phase2_coherence" / "phase2_coherence_output.json",
      {"verdict": "patched", "unrepaired": [], "repairs": [{"field_path": "core_mechanism", "op": "replace", "value": "repaired mechanism"}]})

    # collision hits retrieved with terms a 2.3 patch has since changed
    f = fork("25_collision_stale", coll)
    w(f / "phase3_collision" / ".collision_terms.json", {"signature_terms": ["stale term"], "alias_terms": ["stale alias"]})

    # 3.1 stalled: the candidate carries no signature_terms
    f = fork("26_terms_pending", OUT / "13_coherence_pass")
    (f / "phase3_collision").mkdir(parents=True, exist_ok=True)
    (f / "phase3_collision" / ".signature_extraction_pending").write_text("{}")
    w(f / "phase2_generate" / "phase2_generate_output.json", {k: v for k, v in CANDIDATE.items() if k != "signature_terms"})

    # audit advanced while upholding a blocking finding (inconsistent report)
    f = fork("27_audit_upheld_advance", coll)
    w(f / "phase2_coherence" / "phase2_coherence_output.json", COHERENCE_BLOCKING)
    w(f / "phase2_coherence" / "blocking_findings.json", [{"finding": "acceptance probability 4**-24"}])
    w(f / "phase3_critique" / "phase3_critique_output.json",
      dict(CRITIQUE_ADVANCE, blocking_findings_disposition=[{"finding_ref": "acceptance probability 4**-24", "status": "upheld"}]))

    # the refutation re-check judged the refutation invalid
    f = fork("28_refutation_invalid", OUT / "16d_blocking_refuted")
    w(f / "phase3_critique" / "refutation_recheck.json",
      {"rechecks": [{"finding_ref": "acceptance probability 4**-24", "refutation_valid": False, "reason": "re-reasons, does not touch the numbers"}]})

    THREAT = {"threat_paper_id": "arxiv:2501.00001", "addressable_via": "unaddressable", "subsumption_argument": "same mechanism"}
    ABANDON_THREAT = dict(CRITIQUE_ADVANCE, verdict="abandon", paper_pointed_threat=THREAT)
    ABANDON_RECIPE = dict(CRITIQUE_ADVANCE, verdict="abandon",
                          recipe_application_check={"verdict": "bypassed", "entries": [{"sub_pattern": SUB, "verdict": "bypassed"}]})

    def with_attempt(dst: Path, archived: dict) -> None:
        a = dst / "attempt_1"
        a.mkdir(parents=True, exist_ok=True)
        for sub in ("phase2_select", "phase2_generate", "phase2_coherence", "phase3_collision", "phase3_critique"):
            if (dst / sub).exists():
                shutil.copytree(dst / sub, a / sub)
        w(a / "phase3_critique" / "phase3_critique_output.json", archived)
        (dst / ".retry_used").touch()

    # abandon #2 carrying a NEW lesson the first attempt did not have → directed retry
    f = fork("29_abandon_fresh_lesson", coll)
    w(f / "phase3_critique" / "phase3_critique_output.json", ABANDON_RECIPE)
    with_attempt(f, ABANDON_THREAT)

    # abandon #2 repeating the subsumption lesson → the framing is indicted, re-diagnose
    f = fork("30_abandon_repeat_threat", coll)
    w(f / "phase3_critique" / "phase3_critique_output.json", ABANDON_THREAT)
    with_attempt(f, ABANDON_THREAT)

    # abandon with no new information at all → terminal
    f = fork("31_abandon_no_gain", coll)
    w(f / "phase3_critique" / "phase3_critique_output.json", ABANDON_RECIPE)
    with_attempt(f, ABANDON_RECIPE)

    # revise: patch written, merger not yet run
    f = fork("32_revise_patch", OUT / "16b_audit_revise")
    w(f / "phase3_revise" / "phase3_revise_output.json",
      {"applied_revisions": [{"revision_target_index": 0, "field_path": "core_mechanism", "op": "replace", "value": "restated"}]})

    # revise: merged with an audited falsification rewrite → the bounded re-audit is required
    f = fork("33_falsification_rewritten", OUT / "16b_audit_revise")
    w(f / "phase3_revise" / "phase3_revise_output.json",
      {"applied_revisions": [{"revision_target_index": 0, "field_path": "falsification_prediction", "op": "rewrite_falsification", "value": "repaired paragraph"}],
       "falsification_rewritten": True})
    w(f / "phase3_revise" / "final_candidate.json", dict(CANDIDATE, falsification_prediction="repaired paragraph"))

    # fill_map missing a technical TODO path → back to the fill contract, not to derive
    f = fork("34_fill_missing_tech", OUT / "17_fill_map")
    w(f / "phase4" / "phase4_expansion.json",
      {"title": "Operator-substituted routing", "abstract_draft": "<TODO[abstract_draft]: hint>", "title_zh": "<TODO[title_zh]: hint>"})

    # the rc=10 intent sentinel: phase0 was launched without --queries
    f = OUT / "37_intent_sentinel"
    f.mkdir()
    (f / "phase0").mkdir()
    w(f / "phase0" / ".intent_extraction_pending",
      {"rubric_file": str(RS_REF / "intent-recognition.md"), "re_invocation": 'phase0 --queries "q1|q2|q3|q4"'})

    # the coherence gate could not emit a valid verdict three times → the GATE failed, not the candidate
    f = fork("38_gate_broken", OUT / "13b_coherence_invalid")
    for n in (1, 2):
        (f / "phase2_coherence" / f"rejected_{n}").mkdir(parents=True, exist_ok=True)
        w(f / "phase2_coherence" / f"rejected_{n}" / "phase2_coherence_output.json", {"verdict": "unclear"})

    # grandfather clause: a run whose audit already consumed a candidate predates the 2.3 gate
    f = fork("39_legacy_no_gate", OUT / "15_audit_advance")
    shutil.rmtree(f / "phase2_coherence")

    # the one granted post-re-diagnosis attempt also died
    f = fork("40_bottleneck_exhausted", coll)
    w(f / "phase3_critique" / "phase3_critique_output.json", ABANDON_THREAT)
    with_attempt(f, ABANDON_THREAT)
    (f / ".bottleneck_retry_used").touch()

    # the one permitted falsification rewrite is still deficient
    f = fork("41_reaudit_abandon", OUT / "33_falsification_rewritten")
    w(f / "phase3_critique" / "falsification_reaudit.json", {"verdict": "abandon", "reason": "still tautological"})

    # env switches: the two Phase 0 host channels can be turned off
    f = fork("42_env_partition_off", OUT / "02_retrieved")
    (f / "_ENV").write_text("IDEASPARK_RELEVANCE_PARTITION=off\n")
    f = fork("43_env_coverage_off", OUT / "05_tagged")
    (f / "_ENV").write_text("IDEASPARK_COVERAGE_CHECK=off\n")

    # terminal files
    f = fork("35_terminal_dng", OUT / "09_fulltext")
    (f / "do_not_generate.md").write_text("# do_not_generate\n")
    f = fork("36_terminal_p3f", coll)
    (f / "phase_3_failed.md").write_text("# phase_3_failed\n")

    shutil.rmtree(stage)
    names = sorted(p.name for p in OUT.iterdir() if p.is_dir())
    print(f"built {len(names)} fixtures in {OUT}")
    for n in names:
        print("  " + n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
