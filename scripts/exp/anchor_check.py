#!/usr/bin/env python3
"""anchor_check.py <X> --mode spec|code|process [--worktree PATH] — validate the critic's findings and ROUTE (zero discretion).
Revived from the archived v9 findings_check.py: class ∈ the 45 ARFT codes; every anchor must exist
(file:line with line ≤ file length | log:<path>:<line> | number:<literal present in results/>); a missing anchor
demotes the finding to advisory (never blocking); missing / unparseable / {"status":"critic_failed"} → pending_rejudge (fail closed).
Routing table (worker design §5, V8 _route_judged):
  spec    blocking → L2 (back to Brain, no code)            else pass → /exp-build
  code    blocking → blocked: fix (cap 2 patches + 1 reimplement) else pass → /exp-launch
  process gate survived & no blocking & verdict_agree → survived;  blocking → killed with level (L4 only for A.5/A.6/D.4 and only
          with a second independent vote; else L2); gate killed & no blocking → killed (L3 if negctl hint else L2)
Writes build/X/route.json and experiments/X.json. Exit 0.
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BUILD, WS, jload, jsave, load_x, save_x, arft_codes, L4_CODES, FIX_CAP, REIMPL_CAP, now


def anchor_exists(anchor: str, bases: list, results_text: str) -> bool:
    a = str(anchor).strip()
    m = re.match(r"^number:(.+)$", a)
    if m: return m.group(1).strip() in results_text
    m = re.match(r"^log:(.+?):(\d+)$", a) or re.match(r"^(.+?):(\d+)$", a)
    if m:
        for b in bases:
            p = Path(m.group(1)) if Path(m.group(1)).is_absolute() else b / m.group(1)
            if p.exists() and p.is_file():
                try: return int(m.group(2)) <= sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
                except OSError: return False
        return False
    return any((Path(a) if Path(a).is_absolute() else b / a).exists() for b in bases)


def results_blob(bd: Path) -> str:
    out = []
    for p in sorted(bd.glob("results/**/*.json")):
        try: out.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError: pass
    return "\n".join(out)


def validate(xid: str, mode: str, worktree: str):
    bd = BUILD / xid; f = bd / "findings" / f"{mode}.json"; F = jload(f)
    if not isinstance(F, dict) or F.get("status") == "critic_failed":
        return None, {"status": "critic_failed", "reason": (F or {}).get("reason") if isinstance(F, dict) else "missing or unparseable findings file"}
    codes = arft_codes(); bases = [bd, bd / "results", WS] + ([Path(worktree)] if worktree else []); blob = results_blob(bd)
    for fd in F.get("findings") or []:
        if not isinstance(fd, dict): continue
        fd["advisory"] = False
        if not all(k in fd for k in ("anchor", "class", "blocking", "note")): fd["advisory"] = True; fd["why_advisory"] = "missing field"
        elif codes and fd.get("class") not in codes: fd["advisory"] = True; fd["why_advisory"] = "class not in the ARFT closed set"
        elif not anchor_exists(fd.get("anchor", ""), bases, blob): fd["advisory"] = True; fd["why_advisory"] = "anchor does not exist"
    jsave(f, F)
    return F, None


def route(xid: str, mode: str, F, err) -> dict:
    X = load_x(xid); R = {"x_id": xid, "mode": mode, "at": now()}
    if err:
        R.update({"outcome": "pending_rejudge", "next": f"/exp-critic {xid} {mode} (critic failed: {err.get('reason')}) — never survived"})
        X["status"] = "pending_rejudge"; X["rejudge_count"] = int(X.get("rejudge_count") or 0) + 1; save_x(xid, X); return R
    blocking = [fd for fd in F.get("findings") or [] if isinstance(fd, dict) and fd.get("blocking") and not fd.get("advisory")]
    R["blocking"] = [{"anchor": b.get("anchor"), "class": b.get("class"), "note": str(b.get("note"))[:200]} for b in blocking]
    if mode == "spec":
        R["outcome"] = "L2" if blocking else "pass"
        R["next"] = f"failure_card.py {xid} → Brain (spec defect, no code written)" if blocking else f"/exp-build {xid}"
        X["spec_review"] = R["outcome"]
    elif mode == "code":
        if blocking:
            fixes, reimpl = int(X.get("fix_count") or 0), int(X.get("reimpl_count") or 0)
            if fixes < FIX_CAP: X["fix_count"] = fixes + 1; R.update({"outcome": "blocked", "next": f"/exp-build {xid} fix (patch {fixes + 1}/{FIX_CAP})"})
            elif reimpl < REIMPL_CAP: X["reimpl_count"] = reimpl + 1; R.update({"outcome": "blocked", "next": f"/exp-build {xid} reimplement (clean tree; carry the lessons, not the files)"})
            else: R.update({"outcome": "escalate", "failure_level": "L2", "next": f"failure_card.py {xid} → Brain (budget exhausted: {FIX_CAP} patches + {REIMPL_CAP} reimplement)"}); X["failure_level"] = "L2"
            (BUILD / xid / "gate_passed").unlink(missing_ok=True)          # the build must re-earn gate_passed
        else: R.update({"outcome": "pass", "next": f"/exp-launch {xid} <worktree>"})
        X["code_review"] = R["outcome"]
    else:
        V = jload(BUILD / xid / "verdict.json", {}) or {}; gate = V.get("gate")
        lv = F.get("failure_level")
        if blocking:
            lv = lv or ("L3" if V.get("l3_hint") else "L2")
            if lv == "L4":
                if not any(b.get("class") in L4_CODES for b in blocking): lv = "L2"; R["note"] = "L4 requires A.5 / A.6 / D.4 — downgraded to L2"
                elif not (F.get("second_vote") or {}).get("kill"): R.update({"outcome": "needs_second_vote", "failure_level": "L4", "next": f"/exp-critic {xid} process --second (two independent kill votes before refuted)"}); X["status"] = "pending_second_vote"; save_x(xid, X); return R
            R.update({"outcome": "killed", "failure_level": lv})
        elif gate == "survived" and F.get("verdict_agree", True): R.update({"outcome": "survived", "failure_level": None})
        elif gate == "survived": R.update({"outcome": "killed", "failure_level": lv or "L2", "note": "critic disagrees with the numeric gate (verdict_agree=false) without a blocking finding — treated as L2"})
        else: R.update({"outcome": "killed", "failure_level": lv or ("L3" if V.get("l3_hint") else "L2")})
        cs = F.get("claim_supported")
        if cs: R["claim_supported"] = cs; X["claim_supported"] = cs          # ARIS result-to-claim: partial is never rounded up to yes; it travels into the tables
        if R["outcome"] == "survived": R["next"] = "/exp-next (next block in run_order); all blocks survived → supported" + (" — claim_supported=" + cs + ": keep the qualifier in every table" if cs and cs != "yes" else "")
        elif R.get("failure_level") in ("L0", "L1"): R["next"] = f"/exp-build {xid} fix ({R['failure_level']}: cap {FIX_CAP}+{REIMPL_CAP})"
        else: R["next"] = f"failure_card.py {xid} → Brain as a negative anchor ({R.get('failure_level')})"
        X["status"] = R["outcome"] if R["outcome"] in ("survived", "killed") else X.get("status"); X["failure_level"] = R.get("failure_level")
        if R["outcome"] == "killed" and R.get("failure_level") in ("L0", "L1"):
            X["status"] = "fix_needed"; X["code_review"] = None; (BUILD / xid / "gate_passed").unlink(missing_ok=True)
    X["findings_path"] = str(BUILD / xid / "findings" / f"{mode}.json"); save_x(xid, X)
    return R


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("x"); ap.add_argument("--mode", required=True, choices=["spec", "code", "process"]); ap.add_argument("--worktree", default="")
    a = ap.parse_args()
    F, err = validate(a.x, a.mode, a.worktree or (load_x(a.x).get("worktree") or ""))
    R = route(a.x, a.mode, F, err)
    jsave(BUILD / a.x / "route.json", R); print(json.dumps(R, indent=1, ensure_ascii=False)); return 0


if __name__ == "__main__":
    sys.exit(main())
