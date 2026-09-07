#!/usr/bin/env python3
"""report.py <run_root> [--run rN] — result tables for one idea, numbers ONLY from build/X/verdict.json (the sealed numeric gate).
Shapes follow CCF result-templates (Claim-Evidence Matrix, Main Comparison, Ablation); unknown cells stay TBD; the No-Fabrication
reminder is appended verbatim. ARIS analyze-results: raw numbers before interpretation, delta vs the control always.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BUILD, EXPERIMENTS, WS, jload

NOFAB = WS / "docs/refs/ccf/ccf-experiment-designer/references/result-templates.md"


def fmt(v, nd=3):
    return "TBD" if v is None or not isinstance(v, (int, float)) else f"{v:.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("run_root"); ap.add_argument("--run", default="")
    a = ap.parse_args(); root = Path(a.run_root).resolve()
    run = a.run or next((r.get("run") for r in (jload(root / "ranking.json", {}) or {}).get("ranking") or [] if r.get("rank") == 1), "r1")
    plan = jload(root / run / "phase5" / "evidence_plan.json", {}) or {}
    blocks = {b.get("block_id"): b for b in plan.get("blocks") or []}
    xs = [X for X in (jload(p, {}) or {} for p in sorted(EXPERIMENTS.glob("X-*.json"))) if X.get("run_root") == str(root) and X.get("run") == run]
    cem = ["| Claim | Reviewer question | Evidence needed | Dataset/benchmark | Baselines | Metrics | Result placeholder | Status |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    main_t = ["| Method | Source | Setting | Metric 1 ↑/↓ | Metric 2 ↑/↓ | Metric 3 ↑/↓ | Notes |", "| --- | --- | --- | --- | --- | --- | --- |"]
    abl = ["| Variant | Component changed | Mechanism tested | Metric 1 ↑/↓ | Metric 2 ↑/↓ | Interpretation after user fills result |", "| --- | --- | --- | --- | --- | --- | --- |"[:0] or "| --- | --- | --- | --- | --- | --- |"]
    for X in xs:
        xid, bid = X.get("id"), X.get("block_id"); b = blocks.get(bid, {}); V = jload(BUILD / xid / "verdict.json", {}) or {}; m = V.get("verdict") or {}
        spec = jload(BUILD / xid / "spec.json", {}) or {}; arms = (spec.get("verdict_rule") or {}).get("arms") or {}
        claim = next((c for c in plan.get("claim_map") or [] if c.get("evidence_block") == bid), {})
        cem.append(f"| {claim.get('claim_id', 'TBD')} | {b.get('purpose', 'TBD')} | {b.get('role', 'TBD')} block | {b.get('metric', 'TBD')} | {', '.join(b.get('baselines') or []) or 'TBD'} | {(spec.get('verdict_rule') or {}).get('outcome_metric', 'TBD')} | Δ={fmt(m.get('delta'))} [{fmt(m.get('ci_lo'))}, {fmt(m.get('ci_hi'))}] | {X.get('status')} / {V.get('gate', 'TBD')}{' / claim ' + X['claim_supported'] if X.get('claim_supported') else ''} |")
        for role, key in (("candidate", "candidate_rung_mean"), ("control", "control_rung_mean"), ("negative_control", "negctrl_rung_mean")):
            main_t.append(f"| {arms.get(role, role)} ({role}) | {xid} | {bid} {b.get('role', '')} | {fmt(m.get(key))} | {fmt(m.get('candidate_clean_cost') if role == 'candidate' else m.get('control_clean_cost') if role == 'control' else None)} (clean cost) | TBD | {'negctrl Δ=' + fmt(m.get('negctrl_delta')) if role == 'negative_control' else ''} |")
        if b.get("role") and b.get("role") != "anchor":
            abl.append(f"| {bid} | {b.get('name', 'TBD')} | {b.get('role')} | Δ={fmt(m.get('delta'))} | clean cost {fmt(m.get('candidate_clean_cost'))} | {b.get('failure_interpretation', 'TBD') if V.get('gate') == 'killed' else ('kept' if V.get('gate') == 'survived' else 'TBD')} |")
    seeds_t = ["| X | block | seed | value | clean_cost | early_kill |", "| --- | --- | --- | --- | --- | --- |"]
    for X in xs:
        xid = X.get("id"); vals = []
        for p in sorted((BUILD / xid / "results").glob("seed_*.json")) if (BUILD / xid / "results").exists() else []:
            d = jload(p, {}) or {}; v = d.get("value")
            if isinstance(v, (int, float)): vals.append(v)
            seeds_t.append(f"| {xid} | {X.get('block_id')} | {d.get('seed', p.stem)} | {fmt(v)} | {fmt(d.get('clean_cost'))} | {d.get('early_kill', False)} |")
        if len(vals) >= 2:
            mu = sum(vals) / len(vals); sd = (sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
            seeds_t.append(f"| {xid} | {X.get('block_id')} | mean ± std (n={len(vals)}) | {fmt(mu)} ± {fmt(sd)} | | |")
    nofab = ""
    if NOFAB.exists():
        t = NOFAB.read_text(encoding="utf-8"); i = t.find("## No-Fabrication Reminder"); nofab = t[i:].strip() if i >= 0 else ""
    out = ["# Results — " + str(root.name) + " / " + run + " (numbers from build/X/verdict.json only)", "", "## Claim-Evidence Matrix", *cem, "", "## Main Comparison Table", *main_t, "", "## Ablation Table", *abl, "", "## Per-seed values (results/seed_*.json; ARIS analyze-results: mean ± std when several seeds)", *seeds_t, "", nofab, ""]
    (root / "results_table.md").write_text("\n".join(out), encoding="utf-8")
    print(json.dumps({"table": str(root / "results_table.md"), "rows": len(xs)})); return 0


if __name__ == "__main__":
    sys.exit(main())
