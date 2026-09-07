#!/usr/bin/env python3
"""failure_card.py <X> — the only channel back to Brain: a killed/escalated block becomes a negative anchor.
Reads verdict.json, route.json, findings/*.json, the evidence plan block (role, failure_interpretation, kill_condition) and the spec
(anti_claim, tests_premise); writes failures/X.md + failures/X.json. Numbers come from verdict.json only.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BUILD, FAILURES, jload, jsave, load_x, save_x, now


def main() -> int:
    if len(sys.argv) < 2: print(__doc__); return 2
    xid = sys.argv[1]; X = load_x(xid); bd = BUILD / xid
    V = jload(bd / "verdict.json", {}) or {}; R = jload(bd / "route.json", {}) or {}; spec = jload(bd / "spec.json", {}) or {}
    plan = jload(Path(X.get("run_root") or "") / (X.get("run") or "") / "phase5" / "evidence_plan.json", {}) or {}
    block = next((b for b in plan.get("blocks") or [] if b.get("block_id") == X.get("block_id")), {})
    findings = []
    for mode in ("spec", "code", "process"):
        F = jload(bd / "findings" / f"{mode}.json", {}) or {}
        findings += [dict(f, mode=mode) for f in F.get("findings") or [] if isinstance(f, dict) and f.get("blocking") and not f.get("advisory")]
    card = {"x_id": xid, "run_root": X.get("run_root"), "run": X.get("run"), "block_id": X.get("block_id"), "role": block.get("role"),
            "level": R.get("failure_level") or X.get("failure_level"), "outcome": R.get("outcome") or X.get("status"),
            "arft_codes": sorted({f.get("class") for f in findings if f.get("class")}), "anchors": [f.get("anchor") for f in findings],
            "notes": [str(f.get("note"))[:300] for f in findings], "tests_premise": spec.get("tests_premise"), "anti_claim": spec.get("anti_claim"),
            "kill_condition": spec.get("kill_condition"), "failure_interpretation": block.get("failure_interpretation"),
            "numbers": {k: (V.get("verdict") or {}).get(k) for k in ("delta", "ci_lo", "ci_hi", "negctrl_delta", "negctrl_ci_lo", "candidate_clean_cost")},
            "reasons": V.get("reasons"), "spec_sha": X.get("spec_sha"), "written_at": now()}
    jsave(FAILURES / f"{xid}.json", card)
    X["failure_card"] = str(FAILURES / f"{xid}.json"); X["status"] = "carded"; save_x(xid, X)
    if (card["level"] or card["outcome"]) == "L2" and X.get("run_root") and X.get("run"):
        # L2 = the spec left a scientific decision open → the PLAN must decide it (Brain Phase 5 repair), and the drafted spec is retired
        rd = Path(X["run_root"]) / X["run"]
        jsave(rd / "phase5" / "plan_findings.json", {"x_id": xid, "block_id": card["block_id"], "written_at": card["written_at"],
              "findings": [{"mode": f.get("mode"), "class": f.get("class"), "anchor": f.get("anchor"), "note": str(f.get("note"))[:400]} for f in findings]})
        sp = rd / "spec" / f"{card['block_id']}.json"
        if sp.exists(): sp.rename(rd / "spec" / f"{card['block_id']}.L2-{xid}.json")
        card["plan_repair"] = str(rd / "phase5" / "plan_findings.json"); jsave(FAILURES / f"{xid}.json", card)
    md = [f"# Failure card {xid} — {card['block_id']} ({card['role']}) → {card['level']} / {card['outcome']}", "",
          f"- tests_premise: {card['tests_premise']}", f"- anti_claim: {card['anti_claim']}", f"- kill_condition: {card['kill_condition']}",
          f"- the plan's own failure_interpretation: {card['failure_interpretation']}", f"- numbers (verdict.json): {json.dumps(card['numbers'])}",
          f"- numeric gate reasons: {'; '.join(card['reasons'] or [])}", ""]
    md += [f"- [{f.get('mode')}] {f.get('class')} @ {f.get('anchor')}: {str(f.get('note'))[:300]}" for f in findings] or ["- (no anchored blocking finding; killed by the numeric gate)"]
    (FAILURES / f"{xid}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"card": str(FAILURES / f"{xid}.md"), "level": card["level"], "arft_codes": card["arft_codes"],
                      "brain": "re-trigger brain.workflow.js with args.negative_anchors += [this card]"}, indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
