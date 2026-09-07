#!/usr/bin/env python3
"""spec_packet.py <run_root> --run r1 --block B2 [--repo /abs/repo] — the drafting packet for ONE block spec (Worker side, GLM).
Writes <run>/spec/<block>.packet.md: the plan's block entry + the claims mapped to it + kill_conditions / frozen_untouched / budget,
the method_view equations and steps, the implementability points (open ones first), substrate.md, intake.json, the FROZEN goal,
and a repository map (git ls-files) so the drafter locates files without crawling. Sizes are capped; the contract to follow is
.research/tools/exp/refs/spec_contract.md (the former Brain Phase 6 prompt, verbatim) with the ASI refs under docs/refs/papers/asi-bench/.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import WS, jload


def cap(s, n):
    s = str(s); return s if len(s) <= n else s[:n] + "\n...[truncated %d chars]" % (len(s) - n)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_root"); ap.add_argument("--run", default="r1"); ap.add_argument("--block", required=True); ap.add_argument("--repo", default="")
    a = ap.parse_args(); root = Path(a.run_root).resolve(); rd = root / a.run; args = jload(root / "args.json", {}) or {}
    repo = a.repo or args.get("repo") or ""
    plan = jload(rd / "phase5" / "evidence_plan.json", {}) or {}
    blocks = [b for b in plan.get("blocks") or [] if isinstance(b, dict)]
    pb = next((b for b in blocks if b.get("block_id") == a.block), None)
    if not pb: print(f"BAD: {a.block} is not a block of {rd / 'phase5' / 'evidence_plan.json'} (blocks: {[b.get('block_id') for b in blocks]})"); return 1
    claims = [c for c in plan.get("claim_map") or [] if isinstance(c, dict) and c.get("evidence_block") == a.block]
    mv = jload(rd / "phase4" / "method_view.json", {}) or {}
    impl = jload(rd / "phase4" / "phase4_implementability.json", {}) or {}
    pts = [u for u in impl.get("underspecified_points") or [] if isinstance(u, dict)]
    pts.sort(key=lambda u: 0 if str(u.get("severity")) == "open" else 1)
    repo_map = ""
    if repo and Path(repo).is_dir():
        try:
            r = subprocess.run("git ls-files 2>/dev/null || find . -type f -not -path '*/.git/*'", shell=True, cwd=repo, capture_output=True, text=True, timeout=60)
            lines = [l for l in r.stdout.splitlines() if l.endswith((".py", ".sh", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".md", ".txt")) and not any(x in l for x in ("node_modules/", "__pycache__/", ".venv/", "/venv/", "/build/", "/dist/"))]
            repo_map = "\n".join(lines[:4000]) + ("\n...[+%d more]" % (len(lines) - 4000) if len(lines) > 4000 else "")
        except Exception as ex: repo_map = "(repository map failed: %s)" % ex
    parts = [f"# Block spec drafting packet — {a.run}/{a.block} (deterministic; the drafter's ONLY plan/method/implementability view)", "",
             "Contract: .research/tools/exp/refs/spec_contract.md (verbatim former Brain Phase 6 prompt). ASI refs: docs/refs/papers/asi-bench/task-exemplar/task.yaml, prompt_b1.md, guide/how-scoring-works.md.",
             "PLAN ⊆ SPEC (checked by spec_check.py --plan): keep_if_all numbers come from the block's keep_rule; kill_condition is one of the plan's; forbids cover frozen_untouched; the negative-control arm is the plan's negative control. You add engineering, never science.", "",
             f"## Evidence plan — block {a.block}", "```json", cap(json.dumps(pb, indent=1, ensure_ascii=False), 20000), "```", "",
             "## Claims mapped to this block", "```json", cap(json.dumps(claims, indent=1, ensure_ascii=False), 10000), "```", "",
             "## Plan-level constraints (kill_conditions, frozen_untouched, run_order, total_gpu_h, ablations)", "```json",
             cap(json.dumps({k: plan.get(k) for k in ("kill_conditions", "frozen_untouched", "run_order", "total_gpu_h", "ablations", "minimum_convincing_package") if k in plan}, indent=1, ensure_ascii=False), 12000), "```", "",
             "## FROZEN goal (verbatim)", str(args.get("goal") or "(args.json has no goal)"), "",
             "## method_view.json (equations and steps)", "```json", cap(json.dumps(mv, indent=1, ensure_ascii=False), 40000), "```", "",
             "## phase4_implementability.json — underspecified_points (open first) and per-step notes", "```json",
             cap(json.dumps({"underspecified_points": pts, "steps": impl.get("steps") or impl.get("per_step") or impl.get("step_notes")}, indent=1, ensure_ascii=False), 40000), "```", "",
             "## substrate.md (file:line facts)", cap((root / "_shared" / "substrate.md").read_text(encoding="utf-8") if (root / "_shared" / "substrate.md").exists() else "(missing)", 30000), "",
             "## intake.json", "```json", cap(json.dumps(jload(root / "_shared" / "intake.json", {}) or {}, indent=1, ensure_ascii=False), 8000), "```", "",
             f"## REPOSITORY MAP ({repo or 'no repo'}) — locate files here; Read only to confirm a function/line you will name", "```", repo_map or "(no repository map)", "```", ""]
    out = rd / "spec" / f"{a.block}.packet.md"; out.parent.mkdir(parents=True, exist_ok=True); txt = "\n".join(parts); out.write_text(txt, encoding="utf-8")
    print(json.dumps({"packet": str(out), "chars": len(txt), "block": a.block, "claims": len(claims), "open_points": sum(1 for u in pts if str(u.get("severity")) == "open"),
                      "write": str(rd / "spec" / f"{a.block}.json"), "then": f"python3 .research/tools/exp/spec_check.py {rd / 'spec'} {repo or '<REPO>'} '{json.dumps(args.get('forbidden_patterns') or ['test_half', 'test.txt', 'held_out', 'heldout'])}' {rd / 'phase4' / 'phase4_implementability.json'} --block {a.block} --plan {rd / 'phase5' / 'evidence_plan.json'}"}, indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
