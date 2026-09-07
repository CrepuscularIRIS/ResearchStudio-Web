#!/usr/bin/env python3
"""precheck.py — claim the next block of the top-ranked idea and run every free check BEFORE a line of code.
    precheck.py <run_root> [--run rN] [--block Bk] [--x X-NNN] [--repo PATH]
Type-A only (ARIS acceptance-gate: a script DRIVES, it never acquits):
  1 ranking.json → run (rank 1 unless --run) · evidence_plan run_order → first block not yet survived
  2 spec/B<k>.json exists and is not "blocked" (blocked → back to Brain, exit 3)
  3 Brain's own SPEC_CHECK re-run locally (extracted from brain.workflow.js — one source of truth)
  4 candidate arm eval_type ∉ {synthetic_proxy, simulation_only} (V8 floor R13; missing → warn = Brain gap)
  5 budget: spec.gpu_h ≤ evidence_plan.total_gpu_h − GPU-h already spent on this run (ARFT X.8)
  6 spec sha over the decision-bearing fields → build/X/spec.sha (nothing scientific may change after this)
  7 canary env from instruments/README.md (never typed by a model — V8 P1#8)
Writes build/X/{spec.json, spec.sha, canary.env, progress.md}, experiments/X.json (status=precheck). Exit 0 ok, 1 bad, 3 blocked.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import WS, BUILD, EXPERIMENTS, jload, jsave, spec_sha, next_xid, save_x, canary_env_from_readme, now

HERE = Path(__file__).resolve().parent
BRAIN_WF = WS / ".claude" / "workflows" / "brain.workflow.js"   # unused since 2026-09-07 (spec_check.py is the gate); kept for the provenance note


def brain_spec_check(spec_dir: Path, repo: str, forbidden: list, impl: Path, block: str = "", plan: Path | None = None) -> str:
    """spec_check.py (the former Brain Phase 6 gate, now a script) on one block, with PLAN ⊆ SPEC binding when the plan is given."""
    cmd = [sys.executable, str(HERE / "spec_check.py"), str(spec_dir), repo, json.dumps(forbidden), str(impl)]
    if block: cmd += ["--block", block]
    if plan: cmd += ["--plan", str(plan)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_root"); ap.add_argument("--run", default=""); ap.add_argument("--block", default="")
    ap.add_argument("--x", default=""); ap.add_argument("--repo", default="")
    ap.add_argument("--forbidden", default='["test_half","test.txt","held_out","heldout"]')
    a = ap.parse_args()
    root = Path(a.run_root).resolve()
    ranking = jload(root / "ranking.json", {}) or {}
    run = a.run or next((r.get("run") for r in ranking.get("ranking") or [] if r.get("rank") == 1), "") or "r1"
    rd = root / run
    plan = jload(rd / "phase5" / "evidence_plan.json")
    index = jload(rd / "spec" / "index.json", {}) or {}
    if not plan:
        print(f"BAD: {rd} has no phase5/evidence_plan.json"); return 1
    order = plan.get("run_order") or index.get("run_order") or []
    done = {X.get("block_id") for X in (jload(p, {}) or {} for p in EXPERIMENTS.glob("X-*.json"))
            if X.get("run_root") == str(root) and X.get("run") == run and X.get("status") == "survived"}
    block = a.block or next((b for b in order if b not in done), "")
    if not block:
        print("DONE: every block in run_order has survived — nothing to claim (route: supported)"); return 0
    spec_path = rd / "spec" / f"{block}.json"
    spec = jload(spec_path)
    if not spec:
        print(f"BAD: {spec_path} missing or unreadable — draft it first: /exp-spec {root} --run {run} --block {block}"); return 1
    if spec.get("blocked"):
        print(f"BLOCKED by Brain: {block}: {spec['blocked']} — route to Brain, write no code"); return 3
    bad, warn = [], []
    repo = a.repo or spec.get("_repo") or ""
    chk = brain_spec_check(rd / "spec", repo, json.loads(a.forbidden), rd / "phase4" / "phase4_implementability.json", block, rd / "phase5" / "evidence_plan.json")
    if chk.startswith("__SPEC_BAD"): bad.append("spec_check: " + chk[len("__SPEC_BAD "):][:600])
    elif "warn:" in chk: warn.append(chk[chk.index("warn:"):][:300])
    cand = (spec.get("verdict_rule") or {}).get("arms", {}).get("candidate")
    arm = next((x for x in spec.get("arms") or [] if isinstance(x, dict) and x.get("name") == cand), None)
    et = (arm or {}).get("eval_type")
    if et is None: warn.append(f"candidate arm {cand} has no eval_type (Brain gap: add spec.arms[].eval_type)")
    elif et in ("synthetic_proxy", "simulation_only"): bad.append(f"candidate arm eval_type={et} cannot support primary rows (V8 R13)")
    spent = sum(float(X.get("gpu_h") or 0) for X in (jload(p, {}) or {} for p in EXPERIMENTS.glob("X-*.json"))
                if X.get("run_root") == str(root) and X.get("run") == run and X.get("status") in ("launched", "judged", "survived", "killed", "invalid"))
    total = float(plan.get("total_gpu_h") or 0); need = float(spec.get("gpu_h") or 0)
    if total and need > total - spent: bad.append(f"budget: block needs {need} GPU-h but only {total - spent:.1f} of {total} remain (spent {spent:.1f})")
    if bad:
        print("__PRECHECK_BAD " + " | ".join(bad + ["warn: " + w for w in warn])); return 1
    xid = a.x or next_xid()
    bd = BUILD / xid; bd.mkdir(parents=True, exist_ok=True)
    sha = spec_sha(spec)
    spec_out = dict(spec); spec_out["_provenance"] = {"run_root": str(root), "run": run, "block": block, "spec_path": str(spec_path),
                                                     "spec_sha": sha, "plan_path": str(rd / "phase5" / "evidence_plan.json"), "precheck_at": now(), "repo": repo}
    jsave(bd / "spec.json", spec_out); (bd / "spec.sha").write_text(sha + "\n")
    canary = canary_env_from_readme()
    (bd / "canary.env").write_text("".join(f"{k}={v}\n" for k, v in canary.items()))
    if not canary: warn.append("no canary line in instruments/README.md — the run launches WITHOUT the gate (recorded)")
    if not (bd / "progress.md").exists():
        (bd / "progress.md").write_text(f"# {xid} build progress ({block} of {run}, spec sha {sha[:12]})\n\n"
                                        "- [ ] worktree + repos/* symlinks (launcher_reference.sh STEP 0)\n- [ ] instrument library copied (m152 byte-identical)\n"
                                        "- [ ] mechanism delta implemented per spec.changes[] (deviation_notes.json for every adjustment)\n- [ ] smoke (smoke_cmd, NOT_A_RESULT) reached eval\n"
                                        "- [ ] SELF_CHECK 7 greps → self_check.json; blockers.json\n- [ ] diff.patch staged\n")
    pblock = next((b for b in plan.get("blocks") or [] if b.get("block_id") == block), {})
    save_x(xid, {"id": xid, "status": "precheck", "run_root": str(root), "run": run, "block_id": block, "spec_path": str(spec_path),
                 "spec_sha": sha, "build_dir": str(bd), "repo": repo, "gpu_h": need, "min_effect": pblock.get("min_effect"),
                 "fix_count": 0, "reimpl_count": 0, "warnings": warn, "claimed_at": now()})
    print(json.dumps({"x_id": xid, "run": run, "block": block, "spec": str(bd / "spec.json"), "spec_sha": sha, "canary": canary,
                      "budget_remaining_gpu_h": (total - spent) if total else None, "warnings": warn,
                      "worktree_bootstrap": [f"git -C {repo or '<REPO>'} worktree add /tmp/wt-{xid} -b exp/{xid}",
                                             "wire repos/* symlinks + .git/info/exclude as in instruments/launcher_reference.sh STEP 0",
                                             f"cp instruments/m15*.py /tmp/wt-{xid}/scripts/ (m152 stays byte-identical)"],
                      "next": f"/exp-critic {xid} spec"}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
