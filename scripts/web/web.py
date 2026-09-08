#!/usr/bin/env python3
"""web.py — the deterministic half of the IdeaSpark web track.

    web.py seed    --root <run_root> [--direction ... | --from-run] [--n 3] ...
    web.py collect --root <run_root>

`seed` composes the prompts (one per browser window) and writes them to
<root>/web/prompts/NN.txt with a manifest. `collect` indexes whatever the browser
captured into <root>/web/answers/NN.md and refuses to call an answer complete
without the end marker — a truncated capture is an unfinished answer, not a short one.

Nothing here touches the browser: the skill drives it, this script only decides what
to ask and judges what came back.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TRIGGER = "@ResearchStudio IdeaSpark Use IdeaSpark."
MARKER = "<<END OF IDEA CARD>>"
TAIL = f"End your answer with the single line {MARKER} and nothing after it."
MAX_WINDOWS = 5


def compose(direction: str, target: str = "", ctype: str = "", compute: str = "", extra: list[str] | None = None) -> str:
    lines = [TRIGGER]
    if target:
        lines.append(f"Target system: {target}.")
    lines.append(f"Research direction: {direction.strip().rstrip('.')}.")
    if ctype:
        lines.append(f"Contribution type: {ctype}.")
    if compute:
        lines.append(f"Compute budget: {compute}.")
    for e in extra or []:
        lines.append(e)
    lines.append(TAIL)
    return "\n".join(lines) + "\n"


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def from_run(root: Path, n: int) -> list[dict]:
    """Turn a local run into web questions: one per unaddressed gap, differentiated
    against the paper the audit pointed at (when the gauntlet got that far)."""
    p1 = _load(root / "phase1" / "phase1_output.json") or {}
    if not p1:
        raise SystemExit(f"--from-run needs {root/'phase1'/'phase1_output.json'} (run the local track first)")
    intake = p1.get("intake") or {}
    bottleneck = str(p1.get("bottleneck_statement") or "").strip()
    gaps = [str(g).strip() for g in (p1.get("what_phase_0_did_not_address") or []) if str(g).strip()]
    crit = _load(root / "phase3_critique" / "phase3_critique_output.json") or {}
    threat = (crit.get("paper_pointed_threat") or {}).get("threat_paper_id") or ""
    extra = []
    if threat and str(threat).lower() not in ("no_threat_found", "none", "null"):
        extra.append(f"Differentiate explicitly from {threat} — a local audit named it as the closest work.")

    out = []
    for g in gaps[:n]:
        # the gap is the bottleneck; the Phase 1 statement is the context that makes it one
        direction = f"{g.rstrip('.')}. This sits inside a known bottleneck: {bottleneck}" if bottleneck else g
        out.append({
            "direction": re.sub(r"\s+", " ", direction)[:1200],
            "target": str(intake.get("domain") or intake.get("task") or ""),
            "type": str(intake.get("contribution_type") or ""),
            "compute": str(intake.get("compute") or ""),
            "extra": extra,
            "source": "phase1.what_phase_0_did_not_address",
        })
    if not out and bottleneck:
        out.append({"direction": re.sub(r"\s+", " ", bottleneck)[:1200],
                    "target": str(intake.get("domain") or ""), "type": str(intake.get("contribution_type") or ""),
                    "compute": str(intake.get("compute") or ""), "extra": extra, "source": "phase1.bottleneck_statement"})
    return out


def cmd_seed(a) -> int:
    root = Path(a.root).resolve()
    n = max(1, min(MAX_WINDOWS, a.n))
    if a.from_run:
        specs = from_run(root, n)
    elif a.direction:
        specs = [{"direction": a.direction, "target": a.target, "type": a.type, "compute": a.compute, "extra": [], "source": "cli"}]
    else:
        raise SystemExit("pass --direction or --from-run")
    if not specs:
        raise SystemExit("nothing to ask: the run has no unaddressed gaps and no bottleneck statement")

    wdir = root / "web" / "prompts"
    wdir.mkdir(parents=True, exist_ok=True)
    manifest = {"trigger": TRIGGER, "marker": MARKER, "prompts": []}
    for i, s in enumerate(specs[:n], 1):
        text = compose(s["direction"], s.get("target", ""), s.get("type", ""), s.get("compute", ""), s.get("extra"))
        (wdir / f"{i:02d}.txt").write_text(text, encoding="utf-8")
        manifest["prompts"].append({"id": f"{i:02d}", "file": str(wdir / f"{i:02d}.txt"),
                                    "source": s.get("source", ""), "chars": len(text),
                                    "conversation_url": "", "answer": ""})
    (root / "web" / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"seeded {len(manifest['prompts'])} prompt(s) → {wdir}")
    for p in manifest["prompts"]:
        print(f"  {p['id']}  {p['chars']:5d} chars  [{p['source']}]")
    print(f"manifest → {root/'web'/'manifest.json'}  (fill conversation_url per window as you send)")
    return 0


def cmd_collect(a) -> int:
    root = Path(a.root).resolve()
    web = root / "web"
    man = _load(web / "manifest.json") or {"prompts": []}
    adir = web / "answers"
    rows, incomplete = [], 0
    for p in man.get("prompts", []):
        f = adir / f"{p['id']}.md"
        row = {"id": p["id"], "source": p.get("source", ""), "conversation_url": p.get("conversation_url", ""),
               "captured": f.exists(), "chars": 0, "complete": False, "first_heading": "", "tail": ""}
        if f.exists():
            t = f.read_text(encoding="utf-8")
            row["chars"] = len(t)
            row["complete"] = MARKER in t
            h = re.search(r"^#{1,3}\s*(.+)$", t, re.M)
            row["first_heading"] = (h.group(1).strip()[:80] if h else "")
            row["tail"] = t.rstrip()[-120:]
        if not row["complete"]:
            incomplete += 1
        rows.append(row)
    (web / "index.json").write_text(json.dumps({"marker": MARKER, "answers": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} prompt(s); {len(rows)-incomplete} complete, {incomplete} not")
    for r in rows:
        state = "complete" if r["complete"] else ("TRUNCATED — the end marker is missing, the answer is unfinished"
                                                 if r["captured"] else "not captured")
        print(f"  {r['id']}  {r['chars']:6d} chars  {state}")
        if r["captured"] and not r["complete"]:
            print(f"        tail: …{r['tail'][-80:]}")
    print(f"index → {web/'index.json'}")
    return 1 if incomplete else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed", help="compose the prompts, one per browser window")
    s.add_argument("--root", required=True, help="run root (the same one the local workflow uses)")
    s.add_argument("--direction", default="", help="one or two sentences: a direction or a named bottleneck")
    s.add_argument("--from-run", action="store_true", help="derive the questions from this run's Phase 1 gaps")
    s.add_argument("--target", default="", help="target system, e.g. PhyAgentOS")
    s.add_argument("--type", default="", help="contribution type, e.g. method")
    s.add_argument("--compute", default="", help="compute budget, e.g. 8xH100")
    s.add_argument("--n", type=int, default=1, help=f"number of windows, 1-{MAX_WINDOWS}")
    s.set_defaults(func=cmd_seed)
    c = sub.add_parser("collect", help="index the captured answers; a missing end marker is a failure")
    c.add_argument("--root", required=True)
    c.set_defaults(func=cmd_collect)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
