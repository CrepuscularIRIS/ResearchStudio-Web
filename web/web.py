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
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

TRIGGER = "@ResearchStudio IdeaSpark Use IdeaSpark."
MARKER = "<<END OF IDEA CARD>>"
TAIL = f"End your answer with the single line {MARKER} and nothing after it."
REVIEW_MARKER = "<<END OF IDEA REVIEW>>"
REVIEW_TAIL = f"End your answer with the single line {REVIEW_MARKER} and nothing after it."
MAX_WINDOWS = 5
PATROL_MIN = 30          # a hosted answer takes 30-60 min; patrol on that clock, do not watch it stream
OVERDUE_MIN = 90         # past this a window is stuck, not slow


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def age_min(stamp: str) -> float | None:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds() / 60.0
    except Exception:
        return None


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



def _flat(x, cap: int = 600) -> str:
    """Prose-ify a JSON field for the web app: no paths, no JSON syntax — typed prose only."""
    if isinstance(x, str):
        return re.sub(r"\s+", " ", x).strip()[:cap]
    if isinstance(x, list):
        return "; ".join(_flat(i, cap) for i in x)[:cap]
    if isinstance(x, dict):
        return "; ".join(f"{k}: {_flat(v, 200)}" for k, v in x.items())[:cap]
    return str(x)[:cap]


def _lit_rows_for(root: Path, paper_ids: list[str], cap: int) -> str:
    """The lit_table rows of the papers Phase 1 actually leaned on (the anchor leaves),
    verbatim, capped last — the richest evidence the table offers for this diagnosis."""
    t = (root / "phase0" / "lit_table.md")
    if not t.exists():
        return ""
    try:
        lines = t.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    header = lines[0] if lines else ""
    keep = [header]
    for ln in lines[1:]:
        pid = ln.split("|")[0].strip() if "|" in ln else ""
        if pid and pid in paper_ids:
            keep.append(ln)
    if len(keep) < 2:                       # nothing cited matched: fall back to the head rows
        keep = [header] + lines[1:60]
    out = "\n".join(keep)
    return out[:cap]


def _evidence_pack(root: Path, cap: int = 14000) -> str:
    """Everything evidence-backed and mechanism-level this run has about the bottleneck,
    packed as prose/rows for a web window — as much of it as a paste can carry."""
    p1 = _load(root / "phase1" / "phase1_output.json") or {}
    parts: list[str] = []
    b = _flat(p1.get("bottleneck_statement", ""), 1500)
    if b:
        parts.append(f"DIAGNOSED BOTTLENECK: {b}")
    gaps = p1.get("what_phase_0_did_not_address") or []
    if gaps:
        parts.append("OPEN GAPS (each carries its own stakes clause):\n" +
                     "\n".join(f"- {_flat(g, 1600)}" for g in gaps))
    adj = p1.get("closest_adjacent") or []
    if adj:
        parts.append("CLOSEST ADJACENT WORK (frontier leaves + the residue each leaves open):\n" +
                     "\n".join(f"- {_flat(a, 700)}" for a in adj))
    ids = [str(a.get("paper_id", "")).strip() for a in adj if isinstance(a, dict)]
    rows = _lit_rows_for(root, [i for i in ids if i], cap=3000)
    if rows:
        parts.append("LIT_TABLE ROWS for the papers named above:\n" + rows)
    cand = _load(root / "phase2_generate" / "phase2_generate_output.json") or {}
    if cand:
        parts.append(f"CONTEXT — a candidate has just been built claiming to close this bottleneck: "
                     f"\"{_flat(cand.get('title', ''), 200)}\": {_flat(cand.get('core_mechanism', ''), 500)}")
    text = "\n\n".join(parts)
    return text[:cap]


def from_candidate(root: Path, n: int) -> list[dict]:
    """2.2 候选发布后派发:ONE WINDOW PER ITEM — the diagnosed structural bottleneck is
    its own window, then each open gap. Each prompt carries that item in full detail plus
    the shared evidence context, and asks for a DETAILED card-shaped analysis. Plain
    prompts (no IdeaSpark trigger): these ask GPT-web to think, not to ideate."""
    p1 = _load(root / "phase1" / "phase1_output.json") or {}
    b = _flat(p1.get("bottleneck_statement", ""), 1500)
    if not b:
        raise SystemExit(f"--from-candidate needs {root/'phase1'/'phase1_output.json'} with a bottleneck_statement")
    gaps = [_flat(g, 1800) for g in (p1.get("what_phase_0_did_not_address") or []) if _flat(g, 10)]
    adj = p1.get("closest_adjacent") or []
    residues = "\n".join(f"- {_flat(a, 700)}" for a in adj) or "(none recorded)"
    cand = _load(root / "phase2_generate" / "phase2_generate_output.json") or {}
    cand_line = ""
    if cand:
        cand_line = (f"CONTEXT — a candidate has just been built claiming to close this bottleneck: "
                     f"\"{_flat(cand.get('title', ''), 200)}\": {_flat(cand.get('core_mechanism', ''), 400)}\n\n")
    ctx = (f"SHARED EVIDENCE CONTEXT (the grounded run's residue map):\n{residues}\n\n" + cand_line +
           "Produce a DETAILED, card-shaped analysis of the item above with EXACTLY these sections:\n"
           "## Mechanism-level diagnosis — the structural property, the causal chain that produces the "
           "failure, walked link by link with the weakest link named\n"
           "## Evidence for — concrete work/results that support this being real and unaddressed (use web "
           "search; title + one line each)\n"
           "## Evidence against — the strongest counter-evidence or alternative attribution you can find, "
           "or an honest 'none found'\n"
           "## Binding constraint — what a method MUST confront for this to move; what is merely an amplifier\n"
           "## Attack sketch — the shape of a method that would close it, in 3-5 sentences, mechanism not "
           "implementation\n"
           "## Verdict — one paragraph: is this item a genuine, load-bearing, unaddressed structural bottleneck?")
    items = [("bottleneck", f"ITEM: THE DIAGNOSED STRUCTURAL BOTTLENECK (verbatim from the run's Phase 1):\n{b}")]
    items += [(f"gap-{i}", f"ITEM: OPEN GAP {i} (verbatim, stakes included):\n{g}") for i, g in enumerate(gaps, 1)]
    out = []
    for k, item in items[:max(1, n)]:
        out.append({"direction": f"{item}\n\n{ctx}", "target": "", "type": "", "compute": "",
                    "extra": [], "source": f"bottleneck-evidence:{k}", "plain": True})
    if len(items) > max(1, n):
        print(f"note: {len(items)} item(s) available, sending {max(1, n)} (raise --n, max {MAX_WINDOWS})")
    return out


def _candidate_fingerprint(root: Path) -> str:
    """What a candidate dispatch was made against: title + core mechanism. A repair that
    keeps the mechanism must not re-ask; a redesign must."""
    cand = _load(root / "phase2_generate" / "phase2_generate_output.json") or {}
    payload = json.dumps([cand.get("title", ""), _flat(cand.get("core_mechanism", ""), 2000)],
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

def cmd_seed(a) -> int:
    root = Path(a.root).resolve()
    n = max(1, min(MAX_WINDOWS, a.n))
    if a.from_candidate:
        specs = from_candidate(root, n)
    elif a.from_run:
        specs = from_run(root, n)
    elif a.direction:
        specs = [{"direction": a.direction, "target": a.target, "type": a.type, "compute": a.compute, "extra": [], "source": "cli"}]
    else:
        raise SystemExit("pass --direction or --from-run")
    if not specs:
        raise SystemExit("nothing to ask: the run has no unaddressed gaps and no bottleneck statement")

    wdir = root / "web" / ("candidate_prompts" if a.from_candidate else "prompts")
    wdir.mkdir(parents=True, exist_ok=True)
    plain = bool(a.from_candidate)
    manifest = {"mode": "candidate-review" if plain else "ideaspark",
                "trigger": "" if plain else TRIGGER, "marker": REVIEW_MARKER if plain else MARKER,
                "seeded_at": now(), "patrol_minutes": PATROL_MIN, "overdue_minutes": OVERDUE_MIN, "prompts": []}
    for i, s in enumerate(specs[:n], 1):
        text = (s["direction"].rstrip() + "\n" + REVIEW_TAIL) if plain else \
            compose(s["direction"], s.get("target", ""), s.get("type", ""), s.get("compute", ""), s.get("extra"))
        (wdir / f"{i:02d}.txt").write_text(text, encoding="utf-8")
        manifest["prompts"].append({"id": f"{i:02d}", "file": str(wdir / f"{i:02d}.txt"),
                                    "source": s.get("source", ""), "chars": len(text),
                                    "conversation_url": "", "sent_at": "", "polls": [], "completed_at": ""})
    man_path = root / "web" / ("candidate_manifest.json" if plain else "manifest.json")
    man_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"seeded {len(manifest['prompts'])} prompt(s) → {wdir}")
    for p in manifest["prompts"]:
        print(f"  {p['id']}  {p['chars']:5d} chars  [{p['source']}]")
    if a.from_run:
        (root / "web" / "dispatch.json").write_text(json.dumps(
            {"phase1_fingerprint": _fingerprint(root), "dispatched_at": now(), "n": len(manifest["prompts"])},
            indent=1) + "\n", encoding="utf-8")
    if a.from_candidate:
        (root / "web" / "candidate_dispatch.json").write_text(json.dumps(
            {"candidate_fingerprint": _candidate_fingerprint(root), "dispatched_at": now(), "n": len(manifest["prompts"])},
            indent=1) + "\n", encoding="utf-8")
    print(f"manifest → {man_path}")
    print("record each send with:  web.py mark --root <root> --id NN --sent --url <conversation url>")
    return 0


def _fingerprint(root: Path) -> str:
    """What a dispatch was made against: the bottleneck statement plus the gap list.
    A re-run that keeps the same diagnosis must not re-ask the same questions."""
    p1 = _load(root / "phase1" / "phase1_output.json") or {}
    payload = json.dumps([p1.get("bottleneck_statement", ""), p1.get("what_phase_0_did_not_address", [])],
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cmd_watch(a) -> int:
    """Has the local run produced a bottleneck this track has not asked about yet?"""
    root = Path(a.root).resolve()
    p1 = root / "phase1" / "phase1_output.json"
    if not p1.exists():
        print(f"NO-BOTTLENECK-YET  {p1} does not exist — the local run has not reached Phase 1")
        return 0
    doc = _load(p1) or {}
    if doc.get("state") == "do_not_generate":
        print("NO-BOTTLENECK  Phase 1 routed to do_not_generate; there is nothing to ask about")
        return 0
    due = False
    fp = _fingerprint(root)
    prev = _load(root / "web" / "dispatch.json") or {}
    if prev.get("phase1_fingerprint") == fp:
        age = age_min(prev.get("dispatched_at", ""))
        print(f"ALREADY-DISPATCHED  same bottleneck, {prev.get('n', '?')} window(s), "
              f"{age:.0f} min ago" if age is not None else "ALREADY-DISPATCHED  same bottleneck")
    else:
        gaps = len(doc.get("what_phase_0_did_not_address") or [])
        print(f"NEW-BOTTLENECK  fingerprint {fp}, {gaps} unaddressed gap(s)"
              + (f" (previous dispatch was {prev.get('phase1_fingerprint')})" if prev else ""))
        print(f"  {(doc.get('bottleneck_statement') or '')[:200]}")
        print(f"\nseed it:  web.py seed --root {root} --from-run --n {min(MAX_WINDOWS, max(1, gaps))}")
        due = True
    # second dispatch point: the 2.2 candidate — an independent cross-family review fires the
    # moment the candidate is written (it overlaps the local 2.3/3.1/3.2 gauntlet, so the web
    # latency hides under the local serial chain)
    p2g = root / "phase2_generate" / "phase2_generate_output.json"
    if p2g.exists():
        cand = _load(p2g) or {}
        fp2 = _candidate_fingerprint(root)
        prev2 = _load(root / "web" / "candidate_dispatch.json") or {}
        if prev2.get("candidate_fingerprint") == fp2:
            age = age_min(prev2.get("dispatched_at", ""))
            print(f"CANDIDATE-ALREADY-DISPATCHED  same mechanism, {prev2.get('n', '?')} window(s)"
                  + (f", {age:.0f} min ago" if age is not None else ""))
        else:
            print(f"NEW-CANDIDATE  fingerprint {fp2}")
            print(f"  {(cand.get('title') or '')[:200]}")
            print(f"\nseed it:  web.py seed --root {root} --from-candidate --n 3  (bottleneck-evidence windows)")
            due = True
    return 2 if due else 0


def cmd_mark(a) -> int:
    """Record what the browser did. The skill drives the browser; the clock lives here."""
    root = Path(a.root).resolve()
    mp = root / "web" / "manifest.json"
    man = _load(mp)
    if not man:
        raise SystemExit(f"no manifest at {mp} — seed first")
    hit = [p for p in man["prompts"] if p["id"] == a.id]
    if not hit:
        raise SystemExit(f"no prompt {a.id} in {mp}")
    p = hit[0]
    if a.sent:
        p["sent_at"] = now()
    if a.url:
        p["conversation_url"] = a.url
    if a.poll is not None:
        p.setdefault("polls", []).append({"at": now(), "len": a.poll})
    if a.done:
        p["completed_at"] = now()
    mp.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{a.id}: sent_at={p['sent_at'] or '-'} polls={len(p.get('polls') or [])} "
          f"done={p['completed_at'] or '-'} url={'yes' if p['conversation_url'] else 'MISSING'}")
    return 0


def cmd_patrol(a) -> int:
    """One line per window: what it is doing and whether it is due. Exit 2 = something to do."""
    root = Path(a.root).resolve()
    man = _load(root / "web" / "manifest.json")
    if not man:
        print(f"NO-RUN  no manifest under {root/'web'} — nothing is in flight")
        return 0
    every = a.every or man.get("patrol_minutes", PATROL_MIN)
    overdue = man.get("overdue_minutes", OVERDUE_MIN)
    due = 0
    print(f"patrol every {every} min, overdue at {overdue} min  ({root})")
    for p in man["prompts"]:
        pid, sent = p["id"], p.get("sent_at", "")
        polls = p.get("polls") or []
        if p.get("completed_at"):
            print(f"  {pid}  DONE       completed {p['completed_at']}  {p.get('conversation_url') or 'NO URL RECORDED'}")
            continue
        if not sent:
            print(f"  {pid}  NOT-SENT   {p['file']}")
            due += 1
            continue
        age = age_min(sent) or 0.0
        last = age_min((polls[-1] or {}).get("at", "")) if polls else None
        # the first check is due one interval after the send, not immediately
        since = age if last is None else last
        state = "OVERDUE" if age > overdue else ("POLL-NOW" if since >= every else "WAIT")
        if state != "WAIT":
            due += 1
        grew = ""
        if len(polls) >= 2:
            d = polls[-1]["len"] - polls[-2]["len"]
            grew = f", grew {d:+d} chars since the previous poll" if d else ", unchanged since the previous poll"
        nxt = "" if state != "WAIT" else f", next check in {every - since:.0f} min"
        print(f"  {pid}  {state:9s} sent {age:.0f} min ago, {len(polls)} poll(s){grew}{nxt}")
        if state == "OVERDUE":
            print(f"        {age:.0f} min is past the budget — screenshot the window and report, do not keep waiting")
    print(f"{due} window(s) need action" if due else "nothing due")
    return 2 if due else 0


def cmd_collect(a) -> int:
    root = Path(a.root).resolve()
    web = root / "web"
    if getattr(a, "candidate", False):
        man = _load(web / "candidate_manifest.json") or {"prompts": []}
        adir = web / "candidate_answers"
    else:
        man = _load(web / "manifest.json") or {"prompts": []}
        adir = web / "answers"
    marker = man.get("marker") or MARKER
    rows, incomplete = [], 0
    for p in man.get("prompts", []):
        f = adir / f"{p['id']}.md"
        row = {"id": p["id"], "source": p.get("source", ""), "conversation_url": p.get("conversation_url", ""),
               "captured": f.exists(), "chars": 0, "complete": False, "first_heading": "", "tail": ""}
        if f.exists():
            t = f.read_text(encoding="utf-8")
            row["chars"] = len(t)
            row["complete"] = (marker in t)
            h = re.search(r"^#{1,3}\s*(.+)$", t, re.M)
            row["first_heading"] = (h.group(1).strip()[:80] if h else "")
            row["tail"] = t.rstrip()[-120:]
        if not row["complete"]:
            incomplete += 1
        rows.append(row)
    idx = web / ("candidate_index.json" if getattr(a, "candidate", False) else "index.json")
    idx.write_text(json.dumps({"marker": marker, "answers": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} prompt(s); {len(rows)-incomplete} complete, {incomplete} not")
    for r in rows:
        state = "complete" if r["complete"] else ("TRUNCATED — the end marker is missing, the answer is unfinished"
                                                 if r["captured"] else "not captured")
        print(f"  {r['id']}  {r['chars']:6d} chars  {state}")
        if r["captured"] and not r["complete"]:
            print(f"        tail: …{r['tail'][-80:]}")
    print(f"index → {idx}")
    return 1 if incomplete else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed", help="compose the prompts, one per browser window")
    s.add_argument("--root", required=True, help="run root (the same one the local workflow uses)")
    s.add_argument("--direction", default="", help="one or two sentences: a direction or a named bottleneck")
    s.add_argument("--from-run", action="store_true", help="derive the questions from this run's Phase 1 gaps")
    s.add_argument("--from-candidate", action="store_true", help="derive review questions from the 2.2 candidate (design/bottleneck/domain angles, plain prompts)")
    s.add_argument("--target", default="", help="target system, e.g. PhyAgentOS")
    s.add_argument("--type", default="", help="contribution type, e.g. method")
    s.add_argument("--compute", default="", help="compute budget, e.g. 8xH100")
    s.add_argument("--n", type=int, default=1, help=f"number of windows, 1-{MAX_WINDOWS}")
    s.set_defaults(func=cmd_seed)
    w = sub.add_parser("watch", help="has the local run produced a bottleneck not asked about yet?")
    w.add_argument("--root", required=True)
    w.set_defaults(func=cmd_watch)
    m = sub.add_parser("mark", help="record a send / a poll / a completion against a window")
    m.add_argument("--root", required=True)
    m.add_argument("--id", required=True, help="prompt id, e.g. 01")
    m.add_argument("--sent", action="store_true", help="stamp the send time")
    m.add_argument("--url", default="", help="the conversation URL — the audit trail")
    m.add_argument("--poll", type=int, default=None, help="captured length at this poll")
    m.add_argument("--done", action="store_true", help="stamp completion (only with the end marker present)")
    m.set_defaults(func=cmd_mark)
    pt = sub.add_parser("patrol", help="per-window state on the 30-minute clock; exit 2 when something is due")
    pt.add_argument("--root", required=True)
    pt.add_argument("--every", type=int, default=0, help=f"patrol interval in minutes (default {PATROL_MIN})")
    pt.set_defaults(func=cmd_patrol)
    c = sub.add_parser("collect", help="index the captured answers; a missing end marker is a failure")
    c.add_argument("--root", required=True)
    c.add_argument("--candidate", action="store_true", help="index the candidate-review windows instead")
    c.set_defaults(func=cmd_collect)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
