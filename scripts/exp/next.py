#!/usr/bin/env python3
"""next.py <run_root> [--json] — the navigator: a PURE FUNCTION of what is on disk → the next step (which skill, which args).
Same shape as ResearchStudio's `run.py next` that drives the Brain; no bus, no sessions, no hooks, never runs anything itself
(the owner killed dag for those). The main window does what it prints, then calls next.py again; `/exp-auto` is that loop.
Phases: BRAIN (no ranking / spec yet → Workflow brain with <run_root>/args.json) → EXPERIMENT (ledger X state machine over
precheck → spec review → build → code review → launch → WAIT → verdict → process review → survived | fix | failure card)
→ SUPPORTED (every block of run_order survived → report.py; paper stage) · BLOCKED (owner decision) · WAIT (unit alive).
After a failure card the run is dead at that block. The ladder: the ranking's backup_run (0 quota) → Brain re-trigger with every card as
args.negative_anchors (retrigger.py: new root <base>-n<round>, _shared reused; capped by args.max_brain_rounds, default 2) → BLOCKED.
A re-triggered root carries retrigger.json and navigation follows it to the new root (the `lineage` field lists the roots passed).
"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BUILD, EXPERIMENTS, FAILURES, WS, jload, load_x, FIX_CAP, REIMPL_CAP, brain_lock_state, BRAIN_STALE_MIN

TERMINAL = {"survived", "carded"}
EXP = ".research/tools/exp"
DEFAULT_BRAIN_ROUNDS = 2         # rounds per lineage: the first Brain run + one re-trigger with negative anchors; args.max_brain_rounds overrides


def emit(phase, state, **kw):
    d = {"phase": phase, "state": state, "x": None, "skill": None, "skill_args": "", "run": [], "wait_s": 0, "blocked": False, "note": ""}
    d.update(kw); return d


def unit_active(xid: str) -> bool | None:
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", f"research-{xid}"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() == "active"
    except Exception:
        return None


def brain_done(root: Path, k: int) -> bool:
    """The workflow writes brain.done.json as its last step; artifacts alone are accepted only for roots finished before that marker existed."""
    if (root / "brain.done.json").exists(): return True
    return (root / "ranking.json").exists() if k >= 2 else (root / "r1" / "phase5" / "evidence_plan.json").exists()


def card_level(X: dict) -> str | None:
    card = Path(X["failure_card"]) if X.get("failure_card") else FAILURES / f"{X.get('id')}.json"
    c = (jload(card, {}) or {}) if card.exists() else {}
    return X.get("failure_level") or c.get("level") or c.get("outcome")


def dead(X: dict) -> bool:
    """A block is dead for this idea once its failure card exists (or the ledger says carded). Exception: an L2 card (the spec left a
    scientific decision open) is answered by a PLAN repair on the same root — once evidence_plan.json is newer than the card, the block is
    claimable again (its retired spec is re-drafted from the repaired plan)."""
    s, lvl = X.get("status"), X.get("failure_level")
    card = Path(X["failure_card"]) if X.get("failure_card") else FAILURES / f"{X.get('id')}.json"
    if not (s == "carded" or (s in ("killed", "invalid", "fix_needed") and lvl in ("L2", "L3", "L4") and card.exists())): return False
    if card.exists() and card_level(X) == "L2":
        plan = Path(X.get("run_root") or "") / (X.get("run") or "") / "phase5" / "evidence_plan.json"
        if plan.exists() and plan.stat().st_mtime > card.stat().st_mtime: return False
    return True


def ledger_for(root: Path, run: str | None = None) -> list:
    xs = [jload(p, {}) or {} for p in sorted(EXPERIMENTS.glob("X-*.json"))]
    return [X for X in xs if X.get("run_root") == str(root) and (run is None or X.get("run") == run)]


def cards_for(root: Path) -> list[str]:
    """Every failure card written for this root (all runs) — the negative anchors a Brain re-trigger carries."""
    return sorted({X["failure_card"] for X in ledger_for(root) if X.get("failure_card") and Path(X["failure_card"]).exists()})


def run_candidates(root: Path) -> list[str]:
    """The rank-1 run, then the ranking's backup_run (CCF tournament rule); nothing below the backup is tried automatically."""
    rk = jload(root / "ranking.json", {}) or {}
    top = next((r.get("run") for r in rk.get("ranking") or [] if r.get("rank") == 1), None) or "r1"
    out = [top]
    bk = rk.get("backup_run")
    if bk and bk != top and (root / bk / "phase5" / "evidence_plan.json").exists(): out.append(bk)
    return out


def pick_run(root: Path) -> str | None:
    """The first candidate run with no dead block; None when every candidate is dead (→ the re-trigger ladder)."""
    return next((r for r in run_candidates(root) if not any(dead(X) for X in ledger_for(root, r))), None)


def after_all_dead(root: Path, args: dict) -> dict:
    deads = [X for X in ledger_for(root) if dead(X)]
    if deads and all(card_level(X) == "L2" for X in deads):
        # every death is an L2: the plan left scientific decisions open → repair the PLAN on this root (the Brain resumes from disk and only
        # Phase 5 re-runs, fed by phase5/plan_findings.json); the idea is kept, the retired spec is re-drafted afterwards
        who = ", ".join(f"{X.get('run')}/{X.get('block_id')} ({X.get('id')})" for X in deads)
        return emit("BRAIN", f"plan repair: {who} died L2 (the spec review found decisions the plan left open) — re-run the Brain on this root; Phase 5 repairs evidence_plan.json from plan_findings.json, everything else is kept",
                    skill="brain", skill_args=str(root / "args.json"),
                    run=[f"python3 {EXP}/brain_lock.py {root} acquire   # exit 3 = in flight: do not launch",
                         f'Workflow({{scriptPath: ".claude/workflows/brain.workflow.js", args: <contents of {root / "args.json"}>}})',
                         f"python3 {EXP}/brain_lock.py {root} release   # always, whatever the Workflow returned"],
                    note="same root, same idea: the Brain's Phase 5 pre-check sees plan_findings.json newer than the plan and runs the repair seat; when evidence_plan.json is newer than the card the block is claimable again and /exp-spec re-drafts it")
    cards = cards_for(root)
    rnd, cap = int(args.get("brain_round") or 1), int(args.get("max_brain_rounds") or DEFAULT_BRAIN_ROUNDS)
    dead_runs = ", ".join(f"{X.get('run')}/{X.get('block_id')}→{X.get('failure_level')}" for X in ledger_for(root) if dead(X))
    if rnd < cap:
        return emit("BRAIN", f"every candidate run is dead ({dead_runs}) — re-trigger Brain round {rnd + 1}/{cap} with {len(cards)} failure card(s) as negative anchors",
                    run=[f"python3 {EXP}/retrigger.py {root}"],
                    note="retrigger.py creates <root>-n<round> (args.json + negative_anchors, _shared reused) and writes retrigger.json; the next call navigates the new root and launches the Brain workflow there")
    return emit("BRAIN", f"every candidate run is dead ({dead_runs}) and Brain ran {rnd}/{cap} round(s)", blocked=True,
                note="owner decision: raise max_brain_rounds in args.json (then /exp-auto again) or change the FROZEN goal; cards: " + ", ".join(cards))


def step_for(X: dict, root: Path) -> dict:
    xid, s, bd = X["id"], X.get("status"), BUILD / X["id"]
    lvl, wt = X.get("failure_level"), X.get("worktree") or f"/tmp/wt-{xid}"
    card = FAILURES / f"{xid}.json"
    E = lambda state, **kw: emit("EXPERIMENT", state, x=xid, **kw)
    # --- terminal by card: only Brain can move it
    if dead(X):                                     # navigate() never routes a dead X here; defensive
        return E(f"{xid} {lvl or s}: failure card written — the run is dead at this block", blocked=True,
                 note="navigate() routes the ladder (backup run → retrigger.py → cap); reaching this line means the ledger is inconsistent")
    if lvl in ("L2", "L3", "L4") and s in ("killed", "invalid") and not card.exists():
        return E(f"{xid} killed {lvl}: write the failure card", run=[f"python3 {EXP}/failure_card.py {xid}"], note="the only channel back to Brain")
    if X.get("spec_review") == "L2" and not card.exists():
        return E(f"{xid} spec review: L2 (scientific decision left open)", run=[f"python3 {EXP}/failure_card.py {xid}"], note="no code is written for an L2 spec")
    if X.get("code_review") == "escalate" and not card.exists():
        return E(f"{xid} fix budget exhausted ({FIX_CAP} patches + {REIMPL_CAP} reimplement)", run=[f"python3 {EXP}/failure_card.py {xid}"])
    # --- launched: wait or judge
    if s == "launched":
        if (bd / "exit_code").exists(): return E(f"{xid} unit ended", skill="exp-verdict", skill_args=xid)
        act = unit_active(xid)
        if act: return E(f"{xid} unit research-{xid} active", wait_s=600, note="poll with /loop 10m /exp-auto or Monitor systemctl --user is-active")
        return E(f"{xid} unit not active and no exit_code", skill="exp-verdict", skill_args=xid, note="verdict.py will record no_exit_code → invalid")
    if s == "infra":
        if int(X.get("infra_count") or 0) < 3: return E(f"{xid} infra exit (×{X.get('infra_count')}) — relaunch the same build", skill="exp-launch", skill_args=f"{xid} {wt}")
        return E(f"{xid} infra ×3 — treat as a build problem", skill="exp-build", skill_args=f"{xid} fix", note="infra ≠ verdict; never refuted")
    if s == "judged": return E(f"{xid} numeric gate {X.get('gate')} — process review", skill="exp-critic", skill_args=f"{xid} process")
    if s == "pending_rejudge":
        if int(X.get("rejudge_count") or 0) < 2: return E(f"{xid} critic failed — re-run the process review", skill="exp-critic", skill_args=f"{xid} process")
        return E(f"{xid} critic failed twice", blocked=True, note="reviewer lane broken (grok CLI / auth) — never survived; owner checks /grok:setup")
    if s == "pending_second_vote": return E(f"{xid} L4 needs the second independent vote", skill="exp-critic", skill_args=f"{xid} process --second")
    # --- fixes (L0/L1, invalid) and the build ladder
    if s in ("killed", "invalid", "fix_needed") and lvl in ("L0", "L1", None):
        if int(X.get("fix_count") or 0) >= FIX_CAP and int(X.get("reimpl_count") or 0) >= REIMPL_CAP:
            return E(f"{xid} fix budget exhausted", run=[f"python3 {EXP}/failure_card.py {xid}"], note="escalates as L2 to Brain")
        return E(f"{xid} {s} ({lvl or ', '.join((X.get('reasons') or [])[-2:])}) — fix in the worktree", skill="exp-build", skill_args=f"{xid} fix")
    if not X.get("spec_review"): return E(f"{xid} claimed — review the spec before any code", skill="exp-critic", skill_args=f"{xid} spec")
    if X.get("spec_review") == "pass":
        if not (bd / "gate_passed").exists():
            mode = "fix" if X.get("code_review") in ("blocked",) else "fresh"
            return E(f"{xid} spec passed — implement ({mode})", skill="exp-build", skill_args=f"{xid} {mode}",
                     note=("" if X.get("worktree") else f"worktree not recorded yet: git worktree add {wt} -b exp/{xid}; then write it into experiments/{xid}.json"))
        if X.get("code_review") != "pass": return E(f"{xid} gate_passed — code review", skill="exp-critic", skill_args=f"{xid} code")
        return E(f"{xid} code review passed — launch", skill="exp-launch", skill_args=f"{xid} {wt}")
    return E(f"{xid} in state {s} / spec_review {X.get('spec_review')} — no rule", blocked=True, note="navigator has no rule for this ledger state; inspect experiments/" + xid + ".json")


def navigate(root: Path, depth: int = 0) -> dict:
    ptr = jload(root / "retrigger.json", {}) or {}
    if ptr.get("next_root") and depth < 8 and Path(ptr["next_root"]).exists():      # follow the lineage to the re-triggered root
        d = navigate(Path(ptr["next_root"]), depth + 1); d["lineage"] = [str(root)] + d.get("lineage", []); return d
    d = _navigate(root); d["root"] = str(root); return d


def _navigate(root: Path) -> dict:
    args = jload(root / "args.json", {}) or {}
    k = int(args.get("k") or 1)
    lk = brain_lock_state(root)
    if lk["locked"] and lk["fresh"]:      # a Brain is writing this root (a first run OR a plan repair): never claim blocks under it; the Brain deletes brain.done.json when it starts
        return emit("BRAIN", f"Brain in flight on this root since {lk['started_at']} (last write {lk['quiet_min']} min ago) — nothing to launch, nothing to claim", wait_s=900,
                    note=f"the running Workflow writes here; /loop 10m /exp-auto or wait; a lock quiet for {BRAIN_STALE_MIN} min counts as dead and the next call resumes from disk")
    if not brain_done(root, k):
        goal = str(args.get("goal") or "")
        if not goal.strip() or "<paste" in goal or "<fill" in goal:
            return emit("BRAIN", "args.json has no FROZEN goal (empty or placeholder)", blocked=True,
                        note=f"paste the ## FROZEN block of .research/GOAL.md into {root / 'args.json'} → goal (the Brain hands it verbatim to every seat); also check repo / dataset / venue / anomalies")
        rnd = int(args.get("brain_round") or 1)
        lk = brain_lock_state(root)
        if lk["locked"] and lk["fresh"]:
            return emit("BRAIN", f"Brain in flight on this root since {lk['started_at']} (last write {lk['quiet_min']} min ago) — nothing to launch", wait_s=900,
                        note=f"another session's Workflow is writing here; /loop 10m /exp-auto or wait; a lock quiet for {BRAIN_STALE_MIN} min counts as dead and the next call resumes from disk")
        stale = f"; stale brain.lock from {lk['started_at']} ({lk['quiet_min']} min without writes): the previous launch died — acquire replaces it and the workflow resumes from the artifacts on disk" if lk["locked"] else ""
        return emit("BRAIN", "no Brain output yet (ranking.json / r1/phase5/evidence_plan.json missing)" + (f" — lineage round {rnd}, {len(args.get('negative_anchors') or [])} negative anchor(s)" if rnd > 1 else ""),
                    skill="brain", skill_args=str(root / "args.json"),
                    run=[f"python3 {EXP}/brain_lock.py {root} acquire   # exit 3 = in flight: do not launch",
                         f'Workflow({{scriptPath: ".claude/workflows/brain.workflow.js", args: <contents of {root / "args.json"}>}})',
                         f"python3 {EXP}/brain_lock.py {root} release   # always, whatever the Workflow returned"],
                    note="run from a claude-kimi session (glm/opus/k3/astra routes); the workflow is resumable — finished stages are never redone, a second launch on the same root is refused by the lock" + stale)
    run = pick_run(root)
    if run is None: return after_all_dead(root, args)
    rd = root / run
    order = (jload(rd / "phase5" / "evidence_plan.json", {}) or {}).get("run_order") or (jload(rd / "spec" / "index.json", {}) or {}).get("run_order") or []
    xs = ledger_for(root, run)
    current = next((X for X in reversed(xs) if X.get("status") not in TERMINAL and not dead(X)), None)
    if current: return step_for(current, root)
    survived = {X.get("block_id") for X in xs if X.get("status") == "survived"}
    nxt = next((b for b in order if b not in survived), None)
    if nxt is None:
        return emit("SUPPORTED", f"every block of run_order survived ({', '.join(order)})", run=[f"python3 {EXP}/report.py {root} --run {run}"],
                    note="tables from verdict.json only (CCF result-templates); ablations by evidence_plan.ablations priority next; then the paper stage")
    backup = run != run_candidates(root)[0]
    if not (rd / "spec" / f"{nxt}.json").exists():                                  # block specs are drafted one at a time on this side (Phase 6 left the Brain 2026-09-07)
        return emit("EXPERIMENT", f"block {nxt} of {run} has no spec yet — draft it (Worker) under the Brain's contract, then spec_check" + (" (backup run)" if backup else ""),
                    skill="exp-spec", skill_args=f"{root} --run {run} --block {nxt} --repo {args.get('repo', '')}".strip())
    return emit("EXPERIMENT", f"claim block {nxt} of {run}" + (" (the backup run — the rank-1 run is dead)" if backup else ""), skill="exp-next",
                skill_args=f"{root} --run {run} --block {nxt} --repo {args.get('repo', '')}".strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_root"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(); d = navigate(Path(a.run_root).resolve())
    if a.json: print(json.dumps(d, ensure_ascii=False, indent=1)); return 0
    print("━" * 72); print(f"PHASE  : {d['phase']}"); print(f"STATE  : {d['state']}")
    if d.get("lineage"): print(f"ROOT   : {d['root']}  (via {' → '.join(d['lineage'])})")
    if d["x"]: print(f"X      : {d['x']}")
    if d["skill"]: print(f"SKILL  : /{d['skill']} {d['skill_args']}")
    for c in d["run"]: print(f"RUN    : {c}")
    if d["wait_s"]: print(f"WAIT   : {d['wait_s']} s")
    if d["blocked"]: print("BLOCKED: owner decision needed")
    if d["note"]: print(f"NOTES  : {d['note']}")
    print(f"THEN   : python3 {EXP}/next.py {a.run_root}"); print("━" * 72); return 0


if __name__ == "__main__":
    sys.exit(main())
