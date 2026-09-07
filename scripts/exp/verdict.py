#!/usr/bin/env python3
"""verdict.py <X> [--worktree PATH] — the numeric gate (Type-A, no model). Order never changes (V9 dag_verdict, verbatim logic):
  1 exit code: 5 → infra · 3 → invalid(canary_fail) · 4 → killed(watchdog_early_kill)
  2 seal: spec sha recomputed from build/X/spec.json must equal build/X/spec.sha (rule_changed → invalid)
  3 spec.gates (ASI evaluation.gates): file_exists / no_nan_inf / key_present over build/X and the worktree (hard → invalid)
  4 verdict*.json outside smoke/ and quarantine*/ (else invalid(no_verdict)); NOT_A_RESULT → invalid
  5 keep_if_all over the m158 keys as data; CI containing 0 = fail
  6 negctl: |negctrl_delta − delta| < |delta|/2 → l3_hint (mechanism attribution dead, never L0)
  7 too_good: delta > 3 × min_effect (ARFT J2) → not survivable until the critic decomposes it
Writes build/X/verdict.json (sealed with the m158 file's sha) and experiments/X.json; prints JSON. Exit 0 always — a verdict is data.
"""
import argparse, json, math, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BUILD, RESEARCH, jload, jsave, load_x, save_x, spec_sha, sha_file, eval_rule, now


def exit_code(bd: Path, xid: str):
    p = bd / "exit_code"
    if p.exists():
        try: return int(p.read_text().strip().split()[0]), "exit_code"
        except Exception: pass
    for ledger in (bd / "ledger.jsonl", RESEARCH / "tools" / "ledger.jsonl"):
        if ledger.exists():
            last = None
            for l in ledger.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(l)
                    if d.get("run") == xid and d.get("event") == "stop": last = d
                except Exception: pass
            if last is not None and last.get("exit") is not None: return int(last["exit"]), ledger.name
    return None, None


def find_verdicts(bd: Path):
    out = []
    for p in sorted(bd.glob("**/verdict*.json")):
        parts = p.relative_to(bd).parts[:-1]
        if any(seg == "smoke" or seg.startswith("quarantine") or seg == "evidence" for seg in parts): continue
        if p.name == "verdict.json" and p.parent == bd: continue          # our own sealed output
        out.append(p)
    return out


def has_nan_inf(obj) -> bool:
    if isinstance(obj, float): return math.isnan(obj) or math.isinf(obj)
    if isinstance(obj, dict): return any(has_nan_inf(v) for v in obj.values())
    if isinstance(obj, list): return any(has_nan_inf(v) for v in obj)
    return False


def run_gates(spec: dict, bases: list):
    res = []
    for g in spec.get("gates") or []:
        if not isinstance(g, dict): continue
        chk, cfg, sev = g.get("check"), g.get("config") or {}, g.get("severity", "hard")
        if chk in ("forbidden_pattern", "forbidden_import"): continue                  # launch.sh ran these over the diff
        f = cfg.get("file"); paths = [b / f for b in bases if f] if f else []
        hit = next((p for p in paths if p.exists()), None)
        if chk == "file_exists": ok = hit is not None
        elif chk == "no_nan_inf":
            d = jload(hit) if hit else None; ok = hit is not None and d is not None and not has_nan_inf(d)
        elif chk == "key_present":
            d = jload(hit) if hit else None; ok = isinstance(d, dict) and cfg.get("key") in d
        else: ok = None
        res.append({"name": g.get("name"), "check": chk, "file": f, "severity": sev, "pass": ok})
    return res


def compute(xid: str, worktree: str = "") -> dict:
    bd = BUILD / xid; X = load_x(xid); spec = jload(bd / "spec.json", {}) or {}
    R = {"x_id": xid, "gate": None, "reasons": [], "l3_hint": False, "exit_code": None, "verdict": None, "verdict_file": None, "gates": [], "at": now()}
    code, src = exit_code(bd, xid); R["exit_code"], R["exit_src"] = code, src
    if code is None:
        R["gate"] = "invalid"; R["reasons"].append("no_exit_code" if X.get("unit") else "not_launched"); return R
    R["reasons"].append(f"exit_{code}")
    if code == 5: R["gate"] = "infra"; R["reasons"].append("infra"); return R
    if code == 3: R["gate"] = "invalid"; R["reasons"].append("canary_fail"); return R
    if code == 4: R["gate"] = "killed"; R["reasons"].append("watchdog_early_kill"); R["watchdog"] = True; return R
    sealed = (bd / "spec.sha").read_text().strip() if (bd / "spec.sha").exists() else ""
    if sealed and spec_sha(spec) != sealed:
        R["gate"] = "invalid"; R["reasons"].append("rule_changed"); return R
    bases = [bd, bd / "results"] + ([Path(worktree)] if worktree else [])
    R["gates"] = run_gates(spec, bases)
    if any(g["pass"] is False and g["severity"] == "hard" for g in R["gates"]):
        R["gate"] = "invalid"; R["reasons"].append("gate_failed:" + ",".join(str(g["name"]) for g in R["gates"] if g["pass"] is False)); return R
    vfiles = find_verdicts(bd)
    if not vfiles: R["gate"] = "invalid"; R["reasons"].append("no_verdict"); return R
    V = jload(vfiles[0]) or {}; R["verdict"], R["verdict_file"], R["verdict_sha"] = V, str(vfiles[0]), sha_file(vfiles[0])
    if len(vfiles) > 1: R["reasons"].append(f"multiple_verdicts:{len(vfiles)}")
    if V.get("NOT_A_RESULT") or (vfiles[0].parent / "INVALID.json").exists():
        R["gate"] = "invalid"; R["reasons"].append("not_a_result"); return R
    vr = spec.get("verdict_rule") or {}; keep = list(vr.get("keep_if_all") or [])
    if not keep: R["gate"] = "invalid"; R["reasons"].append("no_keep_if_all"); return R
    ok, rs = eval_rule(V, keep); R["reasons"] += rs
    lo, hi = V.get("ci_lo"), V.get("ci_hi")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo <= 0 <= hi:
        ok = False; R["reasons"].append(f"ci_includes_zero:[{lo},{hi}]")
    me = X.get("min_effect"); dl = V.get("delta")
    if isinstance(me, (int, float)) and me > 0 and isinstance(dl, (int, float)) and dl > 3 * me:
        ok = False; R["reasons"].append(f"too_good:delta {dl:.4f} > 3×min_effect {me}")
    nd = V.get("negctrl_delta")
    if isinstance(nd, (int, float)) and isinstance(dl, (int, float)) and abs(nd - dl) < abs(dl) / 2:
        R["l3_hint"] = True; ok = False; R["reasons"].append(f"negctl_matched:{nd:.4f}~{dl:.4f}")
    R["gate"] = "survived" if ok else "killed"
    return R


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("x"); ap.add_argument("--worktree", default=""); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    try:   # the unit's stdout lives in the journal; write it where the critic can read it (ARIS monitor: check training logs before concluding)
        j = subprocess.run(["journalctl", "--user", "-u", f"research-{a.x}", "--no-pager", "-o", "cat"], capture_output=True, text=True, timeout=30)
        if j.stdout.strip(): (BUILD / a.x / "unit.log").write_text(j.stdout, encoding="utf-8")
    except Exception:
        pass
    R = compute(a.x, a.worktree or (load_x(a.x).get("worktree") or ""))
    if not a.dry:
        jsave(BUILD / a.x / "verdict.json", R)
        X = load_x(a.x); X.update({"status": "judged" if R["gate"] in ("survived", "killed") else ("fix_needed" if R["gate"] == "invalid" else R["gate"]), "gate": R["gate"], "reasons": R["reasons"],
                                    "l3_hint": R["l3_hint"], "exit_code": R["exit_code"], "judged_at": now(),
                                    "failure_level": "L3" if R["l3_hint"] else X.get("failure_level")})
        if R["gate"] == "infra": X["infra_count"] = int(X.get("infra_count") or 0) + 1
        if R["gate"] == "invalid": X["code_review"] = None; (BUILD / a.x / "gate_passed").unlink(missing_ok=True)
        save_x(a.x, X)
    R["next"] = {"survived": f"/exp-critic {a.x} process", "killed": f"/exp-critic {a.x} process", "invalid": "fix ladder (L0/L1) — see reasons; never refuted",
                 "infra": "retry the same build (infra ≠ verdict); after 2 infra exits treat as a build problem"}.get(R["gate"], "")
    print(json.dumps(R, indent=1, ensure_ascii=False, default=str)); return 0


if __name__ == "__main__":
    sys.exit(main())
