#!/usr/bin/env python3
"""critic.py <X> --mode spec|code|process [--worktree PATH] [--model grok-4.6] [--effort xhigh] [--dry-run] [--second]
The executor collects PATHS; the cross-family reviewer reads them itself (ARIS reviewer-independence / experiment-audit).
Runs the grok CLI headless and read-only exactly as the grok plugin does (--prompt-file, --output-format json, --json-schema,
--permission-mode plan). Fail closed: any failure → findings/<mode>.json = {"status": "critic_failed"} → anchor_check routes
pending_rejudge, never survived. --second runs Kimi-K3 through moa.sh review as the independent second vote (L4 only).
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BUILD, WS, HERE, REFS, jload, jsave, load_x, save_x, now, L4_CODES

MOA = Path.home() / "cli" / "grilling-science" / "scripts" / "moa.sh"
SCHEMA = {"type": "object", "required": ["x_id", "mode", "verdict_agree", "findings", "failure_level", "credit_due", "anomalies"],
          "properties": {"x_id": {"type": "string"}, "mode": {"type": "string"}, "verdict_agree": {"type": "boolean"},
                         "findings": {"type": "array", "items": {"type": "object", "required": ["anchor", "class", "blocking", "note"],
                                                                  "properties": {"anchor": {"type": "string"}, "class": {"type": "string"}, "blocking": {"type": "boolean"}, "note": {"type": "string"}}}},
                         "failure_level": {"type": ["string", "null"]}, "credit_due": {"type": "array", "items": {"type": "string"}},
                         "claim_supported": {"type": "string", "enum": ["yes", "partial", "no"]}, "what_results_support": {"type": "string"}, "what_results_dont_support": {"type": "string"},
                         "missing_evidence": {"type": "string"}, "suggested_claim_revision": {"type": "string"}, "next_experiments_needed": {"type": "string"}, "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                         "anomalies": {"type": "array", "items": {"type": "object", "required": ["what", "where", "disposed"],
                                                                   "properties": {"what": {"type": "string"}, "where": {"type": "string"}, "disposed": {"type": "string"}}}}}}


def packet(xid: str, mode: str, X: dict, worktree: str) -> list:
    bd = BUILD / xid; root = Path(X.get("run_root") or ""); run = X.get("run") or ""; rd = root / run if run else None
    P = [str(bd / "spec.json")]
    if rd: P += [str(rd / "phase5" / "evidence_plan.json"), str(rd / "phase4" / "method_view.json"), str(rd / "phase4" / "phase4_implementability.json"),
                 str(root / "_shared" / "substrate.md"), str(rd / "phase4" / "idea.detail.en.md")]
    P.append(str(WS / ".research" / "GOAL.md"))
    if mode in ("code", "process"):
        P += [str(bd / "diff.patch"), str(bd / "self_check.json"), str(bd / "blockers.json"), str(bd / "deviation_notes.json"), str(bd / "progress.md"), str(bd / "smoke.log")]
        if worktree: P.append(worktree + "  (the worktree: read the changed files themselves, not only the diff)")
    if mode == "process":
        P += [str(bd / "results") + "  (every result file; verdict*.json outside smoke/; progress.jsonl = every checkpoint the watchdog saw)", str(bd / "verdict.json"), str(bd / "exit_code"), str(bd / "ledger.jsonl"), str(bd / "unit.log") + "  (the unit's own stdout/stderr)"]
    return P


def build_prompt(xid: str, mode: str, paths: list) -> str:
    md = (HERE / "critic.md").read_text(encoding="utf-8")
    sec = re.search(r"^## MODE: %s\b[\s\S]*?(?=^## MODE: |^## Output contract)" % mode, md, re.M)
    head = md[:md.index("## MODE: ")] if "## MODE: " in md else md
    tail = md[md.index("## Output contract"):] if "## Output contract" in md else ""
    lines = [head.strip(), "", sec.group(0).strip() if sec else "", "", tail.strip(), "",
             f"## Packet for {xid} (mode = {mode}) — read every path yourself; nothing here is a summary", ""]
    lines += ["- " + p for p in paths]
    lines += ["", f'Set "x_id": "{xid}" and "mode": "{mode}". Return ONLY the JSON object.']
    return "\n".join(lines)


def run_grok(prompt_file: Path, cwd: str, model: str, effort: str, timeout: int):
    grok = shutil.which("grok") or str(Path.home() / ".grok" / "bin" / "grok")
    cmd = [grok, "--prompt-file", str(prompt_file), "--output-format", "json", "--json-schema", json.dumps(SCHEMA), "--permission-mode", "plan"]
    if model: cmd += ["--model", model]
    if effort: cmd += ["--reasoning-effort", effort]
    try:
        r = subprocess.run(cmd, cwd=cwd or str(WS), capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr, cmd
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s", cmd
    except FileNotFoundError as e:
        return 127, "", str(e), cmd


def parse_findings(text: str):
    """the CLI wraps the model's JSON; accept the first object that carries a findings[] list."""
    try:
        d = json.loads(text)
        for cand in (d, d.get("result") if isinstance(d, dict) else None, d.get("structured_output") if isinstance(d, dict) else None):
            if isinstance(cand, dict) and isinstance(cand.get("findings"), list): return cand
            if isinstance(cand, str):
                try:
                    c2 = json.loads(cand)
                    if isinstance(c2, dict) and isinstance(c2.get("findings"), list): return c2
                except Exception: pass
    except Exception: pass
    for m in re.finditer(r"\{[\s\S]*?\"findings\"[\s\S]*\}", text):
        try:
            c = json.loads(m.group(0))
            if isinstance(c.get("findings"), list): return c
        except Exception: continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("x"); ap.add_argument("--mode", required=True, choices=["spec", "code", "process"]); ap.add_argument("--worktree", default="")
    ap.add_argument("--model", default=os.environ.get("EXP_GROK_MODEL", "grok-4.6")); ap.add_argument("--effort", default=os.environ.get("EXP_GROK_EFFORT", "xhigh"))
    ap.add_argument("--timeout", type=int, default=900); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--second", action="store_true")
    a = ap.parse_args()
    X = load_x(a.x); wt = a.worktree or X.get("worktree") or ""
    bd = BUILD / a.x; fdir = bd / "findings"; fdir.mkdir(parents=True, exist_ok=True)
    paths = packet(a.x, a.mode, X, wt)
    req = {"x_id": a.x, "mode": a.mode, "paths": paths, "spec_sha": X.get("spec_sha"), "created": now(), "model": a.model, "effort": a.effort}
    jsave(fdir / f"{a.mode}.request.json", req)
    prompt = build_prompt(a.x, a.mode, paths); pf = fdir / f"{a.mode}.prompt.md"; pf.write_text(prompt, encoding="utf-8")
    if a.second:
        if not MOA.exists(): print("second vote unavailable: moa.sh missing"); return 1
        r = subprocess.run(["bash", str(MOA), "review", str(pf)], capture_output=True, text=True, timeout=a.timeout)
        (fdir / f"{a.mode}.k3.md").write_text(r.stdout + r.stderr, encoding="utf-8")
        F = jload(fdir / f"{a.mode}.json", {}) or {}
        kill = bool(re.search(r"\bblocking\b", r.stdout, re.I)) and any(c in r.stdout for c in L4_CODES)
        F["second_vote"] = {"family": "kimi-k3", "kill": kill, "raw": str(fdir / f"{a.mode}.k3.md")}; jsave(fdir / f"{a.mode}.json", F)
        print(json.dumps({"second_vote": F["second_vote"]}, indent=1)); return 0
    if a.dry_run:
        rc, out, err, cmd = 0, "", "", ["grok", "--prompt-file", str(pf), "--output-format", "json", "--json-schema", "<schema>", "--permission-mode", "plan", "--model", a.model, "--reasoning-effort", a.effort]
        print(json.dumps({"dry_run": True, "cmd": cmd, "prompt": str(pf), "paths": paths}, indent=1)); return 0
    rc, out, err, cmd = run_grok(pf, wt or str(WS), a.model, a.effort, a.timeout)
    (fdir / f"{a.mode}.raw.txt").write_text(out + "\n--- stderr ---\n" + err, encoding="utf-8")
    F = parse_findings(out) if rc == 0 else None
    if not F:
        F = {"status": "critic_failed", "reason": f"rc={rc}: {(err or out)[-300:]}", "x_id": a.x}
    else:
        F["x_id"], F["mode"], F["model"], F["reviewed_at"] = a.x, a.mode, a.model, now()
    jsave(fdir / f"{a.mode}.json", F)
    X["critic_" + a.mode] = "failed" if F.get("status") == "critic_failed" else "ok"; save_x(a.x, X)
    print(json.dumps({"status": F.get("status", "ok"), "findings": len(F.get("findings") or []), "file": str(fdir / f"{a.mode}.json"),
                      "next": f"anchor_check.py {a.x} --mode {a.mode}"}, indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
