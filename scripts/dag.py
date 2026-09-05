#!/usr/bin/env python3
"""dag — V8 state machine: research → experiment(plan/build/judge loop) → paper.

One line per `next`: WORKFLOW / WAIT / STOP / (put prints RETRY|REJECT).
Objects: claims/C-*.json · experiments/X-*.json (sketch/spec/evidence) · paper/.
Infra outcomes ({error}, infra_failure, launch_error) → RETRY; canary_fail/early_kill are scientific.
3 strikes in 2h → STOP: INFRA.
"""
import json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D = {k: ROOT / k for k in ("claims", "experiments", "paper", "bundles")}
for p in D.values():
    p.mkdir(exist_ok=True)
GOAL = ROOT / "GOAL.md"
# harness.json is written by init_research.py; every path the workflows need travels in args.paths
_H = json.loads((ROOT / "harness.json").read_text()) if (ROOT / "harness.json").exists() else {}
PATHS = {"root": _H.get("root", str(ROOT.parent)), "tools_dir": _H.get("tools_dir", str(ROOT / "tools")),
         "search_cmd": _H.get("search_cmd", "python3 " + str(ROOT.parent / ".claude/skills/paper-search/scripts/search_papers.py")),
         "fetch_cmd": _H.get("fetch_cmd", "python3 " + str(ROOT / "tools/fetch_text.py")),
         "rs_ref": _H.get("rs_ref", str(ROOT / "references/idea_spark/references")),
         "grok_cli": _H.get("grok_cli", "grok"), "exp_repo": _H.get("exp_repo", str(ROOT.parent))}
CAPS = {"research_redo": 3, "experiment_cycles": 8}
INFRA_STRIKES, INFRA_WINDOW = 3, 2 * 3600
INFRA_OUTCOMES = {"error", "infra_failure", "launch_error"}


def jload(p, d=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def jsave(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def objs(folder, pat):
    return sorted(folder.glob(pat))


def goal_frozen():
    t = GOAL.read_text(encoding="utf-8") if GOAL.exists() else ""
    m = re.search(r"^## FROZEN\n(.*?)(?=\n## |\Z)", t, re.S | re.M)
    return (m.group(1).strip() if m else t.strip()) or None


def substrate():
    return jload(ROOT / "substrate.json", {})

def budget():
    sub = substrate()
    return sub.get("budget") if isinstance(sub.get("budget"), dict) else (jload(ROOT / "FROZEN.json", {}) or {})


def write_args(name, payload):
    n = len(objs(D["bundles"], f"args-{name}-*.json")) + 1
    p = D["bundles"] / f"args-{name}-{n:03d}.json"
    jsave(p, {**payload, "paths": PATHS, "root": PATHS["root"]})
    return p


def unit_state(u):
    r = subprocess.run(["systemctl", "--user", "show", u, "-p", "ActiveState", "--value"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip() or "missing"


# ─── state helpers ───
def active_claim():
    for f in objs(D["claims"], "C-*.json"):
        c = jload(f) or {}
        if c.get("status") in (None, "active"):
            return c
    return None


def experiments_of(cid):
    return [jload(f) or {} for f in objs(D["experiments"], "X-*.json")
            if (jload(f) or {}).get("claim") == cid]


def latest_experiment(cid):
    es = experiments_of(cid)
    return es[-1] if es else None


def evidence_list(cid):
    return [e for e in experiments_of(cid) if e.get("e") and e["e"].get("valid")]


# ─── next ───
def cmd_next(_):
    if not GOAL.exists():
        return "STOP: .research/GOAL.md missing — write the Anchor (## FROZEN block) first"
    frozen = goal_frozen()
    if not frozen:
        return "STOP: GOAL.md has no ## FROZEN block"
    sub = substrate()
    C = active_claim()

    if not C:
        return "WORKFLOW: research args=" + str(write_args("research", {
            "frozen": frozen, "substrate": sub, "round": len(objs(D["claims"], "C-*.json")) + 1,
            "search_cmd": PATHS["search_cmd"], "fetch_cmd": PATHS["fetch_cmd"],
            "lit_count": len(list((ROOT / "lit/papers").glob("*.txt")))}))

    cid = C["id"]
    strength = C.get("strength") or "untested"

    if strength == "refuted":
        C["status"] = "dead"; jsave(D["claims"] / f"{cid}.json", C)
        (ROOT / "research").mkdir(exist_ok=True)
        rd = jload(ROOT / "research/redo.json", {"count": 0, "rounds": []})
        rd["count"] = (rd.get("count") or 0) + 1
        rd["rounds"].append({"refuted_claim": cid})
        jsave(ROOT / "research/redo.json", rd)
        if rd["count"] >= CAPS["research_redo"]:
            return f"STOP: {cid} refuted + redo cap — new Anchor"
        return f"OK: {cid} refuted → next will offer research redo"
    if strength == "supported":
        if not objs(D["paper"], "draft-*"):
            return "WORKFLOW: paper args=" + str(write_args("paper", {
                "claim": C, "evidence": [e.get("e") for e in evidence_list(cid)],
                "substrate": sub, "frozen": frozen}))
        return f"STOP: DONE — paper written for {cid}"

    for e in experiments_of(cid):
        u = e.get("unit")
        if u and e.get("status") == "launched":
            st = unit_state(u)
            if st == "active":
                return f"WAIT: {u}"
            if st in ("inactive", "failed"):
                e["status"] = "run_done"
                jsave(D["experiments"] / f"{e['id']}.json", e)
                break
            e["status"] = "launch_unknown"
            jsave(D["experiments"] / f"{e['id']}.json", e)
            return f"STOP: unit {u} unknown — systemd infra"

    exp = latest_experiment(cid)

    if not exp or exp.get("status") in ("judged", "invalid", "blocked_fatal"):
        cyc = len(experiments_of(cid))
        if cyc >= CAPS["experiment_cycles"]:
            C["strength"] = "active_stalled"; C["status"] = "stalled"
            jsave(D["claims"] / f"{cid}.json", C)
            return f"STOP: cycle cap ({CAPS['experiment_cycles']}) for {cid}"
        return "WORKFLOW: experiment args=" + str(write_args("experiment", {
            "mode": "plan", "claim": C, "substrate": sub, "frozen": budget(),
            "prior_evidence": [e.get("e") for e in evidence_list(cid)]}))

    if exp.get("status") == "planned":
        return "WORKFLOW: experiment args=" + str(write_args("experiment", {
            "mode": "build", "claim": C, "substrate": sub, "frozen": frozen,
            "sketch": exp.get("sketch"), "method_id": exp["id"]}))

    if exp.get("status") in ("built", "gate_passed", "blocked_fixable"):
        return "WORKFLOW: experiment args=" + str(write_args("experiment", {
            "mode": "build", "claim": C, "substrate": sub, "frozen": frozen,
            "sketch": exp.get("sketch"), "method_id": exp["id"],
            "fix": {"findings": exp.get("last_remedial", [])} if exp.get("last_remedial") else None}))

    if exp.get("status") == "run_done":
        return "WORKFLOW: experiment args=" + str(write_args("experiment", {
            "mode": "judge", "claim": C, "substrate": sub, "frozen": frozen,
            "sketch": exp.get("sketch"), "spec": exp.get("spec"),
            "method_id": exp["id"], "worktree": exp.get("worktree")}))

    return f"STOP: experiment {exp.get('id')} in unknown state {exp.get('status')}"


# ─── put ───
def cmd_put(name, outfile):
    out = jload(outfile)
    if out is None:
        return "REJECT: output unreadable — " + str(outfile)
    oc = out.get("outcome") or out.get("error")
    if out.get("launch_error") or oc in INFRA_OUTCOMES or (out.get("error") is not None and out.get("outcome") is None):
        return retry(name, out.get("launch_error") or oc or "error")
    if name == "research":
        return put_research(out)
    if name == "experiment":
        return put_experiment(out)
    if name == "paper":
        return put_paper(out)
    return f"REJECT: unknown workflow '{name}'"


def put_research(out):
    oc = out.get("outcome")
    if oc == "selected":
        sel = out.get("selected") or {}
        n = len(objs(D["claims"], "C-*.json")) + 1
        cid = f"C-{n:04d}"
        claim = {"id": cid, "status": "active", "strength": "untested",
                 "statement": sel.get("statement") or sel.get("title", ""),
                 "strategy": sel.get("strategy", ""),
                 "target_metric": sel.get("target_metric", ""),
                 "margin_rule": sel.get("margin_rule", ""),
                 "contract_rows": sel.get("contract_rows") or default_rows(sel),
                 "falsification_prediction": sel.get("falsification_prediction", ""),
                 "naive_baseline": sel.get("naive_baseline", {}),
                 "premises": sel.get("premises", []),
                 "signature_terms": sel.get("signature_terms", []),
                 "alias_terms": sel.get("alias_terms", []),
                 "negative_anchors": out.get("negative_anchors", []),
                 "bottleneck": out.get("bottleneck", {}),
                 "pool_ids": (out.get("pool") or {}).get("ids", [])}
        jsave(D["claims"] / f"{cid}.json", claim)
        return f"OK: {cid} created ({claim['statement'][:60]})"
    if oc == "do_not_generate":
        return f"STOP: {out.get('reason', 'do_not_generate')}; remedial: {out.get('remedial_steps', [])}"
    if oc in ("all_killed", "all_routes_dead", "all_abandoned"):
        (ROOT / "research").mkdir(exist_ok=True)
        rd = jload(ROOT / "research/redo.json", {"count": 0, "rounds": []})
        rd["count"] += 1
        rd["rounds"].append({"negative_anchors": out.get("negative_anchors", [])})
        jsave(ROOT / "research/redo.json", rd)
        if rd["count"] >= CAPS["research_redo"]:
            return "STOP: research redo cap — write a new Anchor"
        return "OK: negative anchors recorded — run next for redo"
    return f"REJECT: research outcome '{oc}' not in lattice"


def default_rows(sel):
    return [{"id": "primary", "metric": sel.get("target_metric", ""), "threshold": "beat baseline", "direction": "higher_better"},
            {"id": "control", "metric": sel.get("target_metric", ""), "threshold": "within noise", "direction": "within_tol"},
            {"id": "clean_cost", "metric": "clean", "threshold": "≤0.2", "direction": "within_tol"}]


def put_experiment(out):
    oc = out.get("outcome")
    C = active_claim()
    cid = C["id"] if C else "?"
    mid = out.get("id") or out.get("method_id") or ""

    if oc == "planned":
        n = len(objs(D["experiments"], "X-*.json")) + 1
        xid = f"X-{n:03d}"
        jsave(D["experiments"] / f"{xid}.json", {
            "id": xid, "claim": cid, "status": "planned",
            "sketch": out.get("sketch"), "alternatives": out.get("alternatives", [])})
        return f"OK: {xid} planned ({(out.get('sketch') or {}).get('test_id', '?')})"

    if oc == "gate_passed":
        e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
        e.update({"status": "gate_passed", "spec": out.get("spec"),
                  "worktree": out.get("worktree"), "diff_sha8": (out.get("diff_sha") or "")[:8]})
        jsave(D["experiments"] / f"{mid}.json", e)
        if out.get("no_launch"):
            return f"OK: {mid} gate passed (no_launch) — remove NO_LAUNCH and run next"
        return f"OK: {mid} gate passed — run next to launch"

    if oc == "launched":
        e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
        e.update({"status": "launched", "unit": out.get("unit"),
                  "launched_at": out.get("launched_at"), "spec": out.get("spec")})
        jsave(D["experiments"] / f"{mid}.json", e)
        return f"OK: {mid} launched as {out.get('unit')} — next will WAIT"

    if oc == "canary_fail":
        e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
        e.update({"status": "invalid", "det_floors": ["canary fail"]})
        jsave(D["experiments"] / f"{mid}.json", e)
        return f"OK: {mid} canary_fail — invalid, next will PLAN"

    if oc == "early_kill":
        e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
        e.update({"status": "judged", "e": {"valid": True, "claim_strength": "refuted",
            "row_evidence": [], "next_action": "claim_refuted"}})
        jsave(D["experiments"] / f"{mid}.json", e)
        if C: C["strength"] = "refuted"; jsave(D["claims"] / f"{cid}.json", C)
        return f"OK: {mid} early_kill — claim refuted"

    if oc in ("spec_blocked", "no_valid_tests"):
        if oc == "spec_blocked":
            e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
            prev = e.get("fixes", 0)
            e["fixes"] = prev + 1
            e["status"] = "blocked_fixable" if prev < 1 else "blocked_fatal"
            e["last_remedial"] = out.get("remedial", out.get("floors", []))
            jsave(D["experiments"] / f"{mid}.json", e)
            return f"OK: {mid} spec_blocked (round {e['fixes']})"
        else:
            n = len(objs(D["experiments"], "X-*.json")) + 1
            xid = f"X-{n:03d}"
            jsave(D["experiments"] / f"{xid}.json", {"id": xid, "claim": cid, "status": "invalid",
                "det_floors": out.get("remedial", ["no valid tests"])})
            return f"OK: {xid} no_valid_tests — next will re-PLAN"

    if oc == "blocked":
        e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
        prev = e.get("fixes", 0)
        e["fixes"] = prev + 1
        e["last_remedial"] = out.get("remedial", [])
        e["status"] = "blocked_fixable" if prev < 1 else "blocked_fatal"
        jsave(D["experiments"] / f"{mid}.json", e)
        if e["status"] == "blocked_fatal":
            return f"OK: {mid} blocked twice — next will PLAN a different test"
        return f"OK: {mid} blocked (round {e['fixes']}) — next offers fix"

    if oc == "invalid_experiment":
        e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
        e.update({"status": "invalid", "det_floors": out.get("det_floors", [])})
        jsave(D["experiments"] / f"{mid}.json", e)
        return f"OK: {mid} invalid — Claim unchanged, next will PLAN"

    if oc == "judged":
        e = jload(D["experiments"] / f"{mid}.json") or {"id": mid, "claim": cid}
        ev = out.get("e") or {}
        e.update({"status": "judged", "e": ev})
        jsave(D["experiments"] / f"{mid}.json", e)
        if C:
            all_ev = evidence_list(cid)
            row_v = {}
            for ev2 in all_ev:
                for re2 in (ev2.get("row_evidence") or []):
                    row_v[re2["row_id"]] = re2["verdict"]
            tids = [r.get("id") or r for r in C.get("contract_rows", [])]
            any_ref = any(row_v.get(rid) == "refutes" for rid in tids)
            all_sup = all(row_v.get(rid) == "supports" for rid in tids) if tids else False
            C["strength"] = "refuted" if any_ref else "supported" if all_sup else "active"
            jsave(D["claims"] / f"{cid}.json", C)
        return f"OK: {mid} judged → claim {ev.get('claim_strength', '?')} (next: {ev.get('next_action', '?')})"

    return f"REJECT: experiment outcome '{oc}' not in lattice"


def put_paper(out):
    oc = out.get("outcome")
    if oc == "written":
        (D["paper"] / "draft-v1.md").write_text(out.get("manuscript", ""), encoding="utf-8")
        return "OK: paper written → paper/draft-v1.md"
    return f"REJECT: paper outcome '{oc}' not in lattice"


def retry(name, msg):
    log = ROOT / "infra.jsonl"
    now = time.time()
    strikes = []
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                strikes.append(json.loads(line))
            except Exception:
                pass
    strikes.append({"t": now, "name": name, "msg": str(msg)[:120]})
    strikes = [s for s in strikes if now - s["t"] < INFRA_WINDOW]
    log.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in strikes), encoding="utf-8")
    if len(strikes) >= INFRA_STRIKES:
        return f"STOP: INFRA — {len(strikes)} failures in 2h; last: {msg}"
    return f"RETRY: {name} — {msg} ({len(strikes)}/{INFRA_STRIKES}); wait ~1 min"


def cmd_board(_):
    C = active_claim()
    print(f"claim: {C['id'] if C else '-'} | strength: {(C or {}).get('strength', '-')} | "
          f"experiments: {len(experiments_of(C['id']) if C else [])} | "
          f"evidence: {len(evidence_list(C['id']) if C else [])}")
    if C:
        for e in experiments_of(C["id"]):
            ev = e.get("e") or {}
            print(f"  {e['id']} | {e.get('status', '?'):14} | {(e.get('sketch') or {}).get('test_id', '?'):12} | "
                  f"strength={ev.get('claim_strength', '')} next={ev.get('next_action', '')}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 0
    cmd, rest = argv[1], argv[2:]
    if cmd == "next":
        print(cmd_next(rest))
    elif cmd == "put" and len(rest) >= 2:
        print(cmd_put(rest[0], rest[1]))
    elif cmd == "board":
        cmd_board(rest)
    else:
        print("usage: dag.py next | put <name> <out.json> | board")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
