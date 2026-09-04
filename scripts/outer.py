#!/usr/bin/env python3
"""outer.py — the manuscript loop (WORKFLOW-V4 §12.1; paperjury-shaped). The reader is the top-level evaluator; the claim loop
is the handler for one `needs-data` row; stopping is a ledger fact plus the script gates, never a score.

One round r on the CURRENT manuscript:
  read   three referees (critic-sol ∥ critic-k3 ∥ critic-glm, REFEREE mode) read the sections inline → anchored weaknesses
         → script: anchor located in a passage (or the weakness is not filed), clerk dedup, ledger intake, routing
  trial  every in-trial row: DEFENSE (GLM, whole paper) → 5 JURORS (GLM ×3 framings, K3, sol; local passage) → quorum by
         script → JUDGE (sol) routes valid-fixable (close_criterion needs no new data) or needs-data
  needs-data rows wait for the owner: a CLAIM.md for that row, accepted → the claim loop runs → its records close the row
  draft  every valid-fixable row: the writer (PATCH mode) returns an exact-string before/after; the script applies it once,
         journals it, and re-runs the numbers gate on the section (revert on failure); the row closes
  review the fact review (write.workflow.js, review only) → issues become valid-fixable rows
  clerk  the round is clean when nothing is raised / in-trial / valid-fixable and the review passed; DONE when a clean read round
         added no genuinely new issue, the ledger gate passes and `gate.py deliverables` passes.
Every step is one printed command for Main; state is recomputed from files (ledger, bundles/*-out-<r>.json, gates/).
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decompose  # noqa: E402
import paper_ledger as L  # noqa: E402

PANEL = {"sol": "critic-sol", "k3": "critic-k3", "glm": "critic-glm"}
FRAMINGS = ["baseline fairness and empirical rigor (is the empirical complaint fair and correct?)",
            "claims-vs-evidence (does the paper overclaim relative to what it shows here?)",
            "adversarial competitor: read the paper in the MOST hostile reasonable way; is the charge valid?",
            "charitable peer: read the paper in the MOST charitable way that still respects the evidence; is it still valid?",
            "reproducibility and scope (is what is claimed actually shown at the scope and scale stated?)"]
JURY = [("glm", FRAMINGS[0]), ("glm", FRAMINGS[1]), ("k3", FRAMINGS[2]), ("sol", FRAMINGS[3]), ("glm", FRAMINGS[4])]
QUORUM, MAJORITY = 0.8, 0.6
PERSONA = ("You are a senior reviewer for a top CS conference, known for being harsh, precise, and constructive. Your job is to find what is "
           "actually wrong, not to be agreeable. You separate fatal flaws from fixable nits and weight them accordingly. You do not pad with "
           "compliments, you do not invent problems to look thorough, and you do not soften a real flaw.")
ISOLATION = ("Judge ONLY the manuscript quoted in this prompt. Do not read files, search the project, or use any tool to find other context "
             "(the ledger, prior rounds, other reviewers, or any manuscript on disk); base your review solely on the text quoted here. "
             "Reviewers live only in the current round: if THIS were the only version of the paper an outside expert ever saw, what would they say?")


def _b():
    import bundle  # noqa: E402
    return bundle


def sections(w: Path) -> list[Path]:
    b = _b()
    return [w / str(s) for s in b._goal_field("paper_sections", ["paper/pr/sections/05_method.tex", "paper/pr/sections/06_experiments.tex"], w)]


def paper_dir(w: Path) -> Path:
    return w / str(_b()._goal_field("paper_dir", "paper/pr", w))


# ── read ────────────────────────────────────────────────────────────────────

def cmd_read(w: Path, rnd: int) -> dict:
    secs = sections(w)
    text = decompose.manuscript_text(secs)
    names = [p.name for p in secs if p.exists()]
    prompt = "\n".join([
        ISOLATION, "", "## REFEREE (paperjury reading-check)", PERSONA,
        "Read the WHOLE manuscript below and file WEAKNESSES. Pass 1 — fatal-flaw diagnostic: unsupported central claims, unfair or missing baselines, ablations that do not cover the key design decisions, overclaims, internal contradictions, a contribution the experiments do not validate. Pass 2 — forensic interrogation: for each, where exactly, why it is a flaw, what evidence would settle it, and whether it is fatal or fixable within a revision.",
        "You cover the full review surface (originality, soundness, significance, clarity, impact). You MUST reason across sections (abstract vs results, notation reused across sections, a contribution the experiments do not validate).",
        "For EACH weakness give: summary (one line, what is wrong); evidence_anchor (an EXACT VERBATIM quote from the manuscript the weakness rests on — copy it character for character; cannot quote = do not file; a hallucinated quote is a tell and the script drops it); section (the file name and paragraph); significance: major (affects the paper's claims / soundness / contribution) or minor (local); kind: substantive (needs judgment) or mechanical (copy-edit class) — when unsure choose substantive; references (what would settle it, may be \"\").",
        "Do NOT propose the fix or a close criterion. Do NOT invent flaws to look thorough and do NOT soften a real one. Fatal-risk categories to name explicitly when they apply: the central contribution is unclear; the novelty claim collapses under close prior work; a main claim lacks evidence; the strongest baseline or comparison is missing; the evaluation protocol is invalid; the paper is not reproducible enough for the claim type.",
        f"ANTI-SKIM: also return per_section_coverage with ONE entry for EVERY section listed here: {names} — {{section, status (thorough|light|skipped), in_section_quote = an exact verbatim quote FROM THAT SECTION proving you read it}}. Finally give ONE overall_confidence (1-5).",
        "", "## Manuscript", text,
    ])
    return {"round": rnd, "panel": PANEL, "sections": names, "prompt": prompt}


def finish_read(w: Path, r: Path, rnd: int, out: dict) -> dict:
    """Anchor every weakness, intake into the ledger, route. Returns counts; None panel = infrastructure."""
    panel = out.get("panel") if isinstance(out.get("panel"), dict) else {}
    answered = {f: v for f, v in panel.items() if isinstance(v, dict)}
    if not answered:
        return {"error": "no referee answered"}
    plist = decompose.passages(sections(w))
    led = L.load(r)
    n = {"filed": 0, "unanchored": 0, "new": 0, "corroborated": 0, "reopened": 0, "dropped-before": 0}
    coverage = {}
    for fam, res in answered.items():
        coverage[fam] = {"confidence": res.get("overall_confidence"), "skipped": [c.get("section") for c in (res.get("per_section_coverage") or []) if c.get("status") == "skipped"]}
        for wk in res.get("weaknesses") or []:
            if not isinstance(wk, dict) or not str(wk.get("summary", "")).strip():
                continue
            ps = decompose.locate(wk.get("evidence_anchor", ""), plist)
            if ps is None:
                n["unanchored"] += 1; continue                                   # cannot quote = not filed
            ev = L.add(led, {**wk, "passage_id": ps["id"], "section": ps["section"]}, fam, rnd)
            n["filed"] += 1; n[ev["event"]] = n.get(ev["event"], 0) + 1
    routed = L.route(led)
    rd = L.current_round(led) or L.start_round(led, rnd)
    rd["genuinely_new"] = n["new"] + n["reopened"]; rd["read"] = {**n, "coverage": coverage, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
    L.save(led, r)
    return {**n, "routed": routed, "genuinely_new": rd["genuinely_new"]}


# ── trial ───────────────────────────────────────────────────────────────────

def cmd_trial(w: Path, r: Path, rnd: int) -> dict:
    led = L.load(r)
    charges = L.rows(led, "in-trial")
    if not charges:
        raise SystemExit("trial: no in-trial rows")
    secs = sections(w)
    text = decompose.manuscript_text(secs)
    plist = {p["id"]: p for p in decompose.passages(secs)}
    items = []
    for c in charges:
        local = (plist.get(c.get("passage_id")) or {}).get("text", "")
        items.append({"id": c["id"], "summary": c["summary"], "evidence_anchor": c["evidence_anchor"], "section": c["section"], "passage": local,
                      "significance": c["significance"], "raised_by": c["raised_by"]})
    return {"round": rnd, "panel": PANEL, "jury": JURY, "quorum": QUORUM, "majority": MAJORITY, "persona": PERSONA, "isolation": ISOLATION,
            "charges": items, "paper": text}


def finish_trial(r: Path, rnd: int, out: dict) -> dict:
    led = L.load(r)
    n = {"valid-fixable": 0, "needs-data": 0, "invalid-drop": 0, "author-required": 0, "null": 0}
    for v in out.get("verdicts") or []:
        row = L.get(led, str(v.get("id")))
        if not row or row["status"] != "in-trial":
            continue
        verdict = v.get("verdict")
        tally = v.get("tally")
        if verdict in ("valid-fixable", "needs-data", "invalid-drop", "author-required"):
            L.set_status(led, row["id"], verdict, f"trial round {rnd}: {v.get('rationale', '')[:160]}", tally=tally,
                         close_criterion=(v.get("close_criterion") or None) if verdict == "valid-fixable" else None, defense=v.get("defense"))
            n[verdict] += 1
        else:
            n["null"] += 1                                                         # no verdict = still in-trial (unadjudicated blocks the gate)
    rd = L.current_round(led) or L.start_round(led, rnd)
    rd["trial"] = {**n, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
    L.save(led, r)
    return n


# ── draft ───────────────────────────────────────────────────────────────────

def cmd_draft(w: Path, r: Path, rnd: int) -> dict:
    led = L.load(r)
    todo = L.rows(led, "valid-fixable")
    if not todo:
        raise SystemExit("draft: no valid-fixable rows")
    secs = {p.name: p for p in sections(w)}
    b = _b()
    rules = w / str(b._goal_field("manuscript_rules", "paper/.claude/CLAUDE.md", w))
    rules_txt = rules.read_text(encoding="utf-8") if rules.exists() else ""
    items = []
    for row in todo:
        sec = secs.get(row.get("section") or "")
        if not sec or not sec.exists():
            continue
        prompt = "\n".join([
            "LANE: writer", "MODE: PATCH",
            "You are the AUTHOR drafting a MINIMAL edit to close one review charge. Make the SMALLEST change that satisfies the close_criterion AND preserves the surrounding claim's meaning. Output an exact-string patch: `before` = copy VERBATIM the smallest contiguous span of the section text below that you are changing (it must appear exactly once in the text); `after` = the replacement, plain prose, no new citations or numbers you cannot support, no revision notes in the text.",
            "If the only honest fix needs information not in the text (a new experiment, a number you do not have), do NOT fabricate: set before and after equal (no_op=true) and explain in rationale that it needs the author. Numbers enter the text only with a `% src: <record path>` comment already present on the same line; never invent one. Do not touch a line with `% src:` unless the criterion is about that number. Unsupported claims must be weakened, removed, or backed by evidence — never rhetorically strengthened.",
            "", f"## Charge {row['id']} ({row['significance']}, {row['kind']})", f"summary: {row['summary']}", f"evidence_anchor: {row['evidence_anchor']}", f"close_criterion: {row.get('close_criterion') or row['summary']}",
            "", "## manuscript_rules", rules_txt[:6000], "", f"## Section {sec.name}", sec.read_text(encoding="utf-8", errors="ignore"),
        ])
        items.append({"id": row["id"], "section": str(sec), "prompt": prompt})
    return {"round": rnd, "rows": items}


def apply_patch(section: Path, before: str, after: str, rdir: Path) -> list[str]:
    """Exact-once substring replace, journaled; the numbers gate re-runs on the section and a failure reverts."""
    import gate  # noqa: E402
    text = section.read_text(encoding="utf-8", errors="ignore")
    if not before or text.count(before) != 1:
        return [f"`before` occurs {text.count(before) if before else 0} times in {section.name} (must be exactly once)"]
    new = text.replace(before, after)
    fails = gate.check_numbers(new, rdir)
    if fails:
        return [f"numbers gate on {section.name} after the edit: {f}" for f in fails[:3]]
    section.write_text(new, encoding="utf-8")
    with (rdir / "paper-journal.jsonl").open("a") as fh:
        fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "section": section.name, "before": before, "after": after}) + "\n")
    return []


def finish_draft(w: Path, r: Path, rnd: int, out: dict) -> dict:
    led = L.load(r)
    n = {"closed": 0, "no_op": 0, "refused": 0, "null": 0}
    for p in out.get("patches") or []:
        row = L.get(led, str(p.get("id")))
        if not row or row["status"] != "valid-fixable":
            continue
        if not isinstance(p.get("patch"), dict):
            n["null"] += 1; continue
        pt = p["patch"]
        if pt.get("no_op") or pt.get("before") == pt.get("after"):
            L.set_status(led, row["id"], "author-required", f"drafter: {str(pt.get('rationale', ''))[:160]} (needs the author)"); n["no_op"] += 1; continue
        sec = next((s for s in sections(w) if s.name == row.get("section")), None)
        fails = apply_patch(sec, str(pt.get("before", "")), str(pt.get("after", "")), r) if sec else ["section not found"]
        if fails:
            L.set_status(led, row["id"], "author-required", "patch refused: " + "; ".join(fails)[:200]); n["refused"] += 1
        else:
            L.set_status(led, row["id"], "closed", f"drafted round {rnd}: {str(pt.get('rationale', ''))[:120]}"); n["closed"] += 1
    rd = L.current_round(led) or L.start_round(led, rnd)
    rd["draft"] = {**n, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
    L.save(led, r)
    return n


def intake_review(r: Path, rnd: int, review: dict) -> int:
    """The fact review's non-style issues become valid-fixable rows (criterion = the issue text; anchor = the issue's location)."""
    led = L.load(r)
    k = 0
    for iss in review.get("issues") or []:
        s = str(iss)
        if s.lower().startswith("style:"):
            continue
        wk = {"summary": s[:300], "evidence_anchor": "", "section": s.split(":")[0] if ":" in s else None, "passage_id": f"review:{rnd}:{k}",
              "significance": "major", "kind": "substantive", "references": "fact review"}
        ev = L.add(led, wk, "review", rnd)
        if ev["event"] in ("new", "reopened"):
            L.set_status(led, ev["id"], "valid-fixable", f"fact review round {rnd}", close_criterion=s[:300]); k += 1
    rd = L.current_round(led) or L.start_round(led, rnd)
    rd["review"] = {"verdict": review.get("verdict"), "issues_to_rows": k, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
    L.save(led, r)
    return k


# ── navigator ───────────────────────────────────────────────────────────────

def _newer(a: Path, b: Path | None) -> bool:
    return a.exists() and (b is None or not b.exists() or a.stat().st_mtime > b.stat().st_mtime)


def decide(w: Path, r: Path, head: str, claim_sha: str, done_records: list[str]) -> dict:
    """The outer loop's next action. `done_records` = the records that finish the current claim (KEEP + ladder, or the shipped
    incumbent); they close the needs-data rows bound to this claim before anything else."""
    b = _b()
    led = L.load(r)
    closed = L.close_by_claim(led, claim_sha, done_records, "claim loop finished: " + ", ".join(done_records)) if done_records else []
    if closed:
        L.save(led, r)
    pdir = paper_dir(w)
    ledger_p = r / L.LEDGER
    if not (pdir / "main.tex").exists():
        return {"stage": "W", "reason": head + "; no manuscript yet (W0 merge)",
                "next": ["python3 .research/step.py write --merge   # writer MERGE: the incumbent written in, the paper complete on day one"]}
    review_p = r / "gates" / "write-review.json"                        # W0's review lands here before the ledger exists
    if not ledger_p.exists():
        if _newer(r / "bundles" / "write-out.json", review_p):
            return {"stage": "W", "reason": head + "; sections written, review pending", "next": ["python3 .research/step.py write --finish .research/bundles/write-out.json"]}
        return {"stage": "W", "reason": head + "; W0: sections from records + fact review",
                "next": ["python3 .research/step.py write", "Workflow(name='write', args=<contents of .research/bundles/args-write.json>)", "python3 .research/step.py write --finish .research/bundles/write-out.json"]}
    rd = L.current_round(led)
    n = rd["n"] if rd else 0
    max_rounds = int(b._goal_field("max_rounds", 4, w) or 4)
    tag = lambda kind: r / "bundles" / f"{kind}-out-{n}.json"
    if rd and rd.get("read") is None:
        if tag("read").exists():
            return {"stage": "W", "reason": head + f"; round {n}: referee output waiting", "next": [f"python3 .research/step.py read --finish {n} {tag('read')}"]}
        return {"stage": "W", "reason": head + f"; round {n}: three referees read the manuscript",
                "next": [f"python3 .research/step.py read {n}", "Workflow(name='read', args=<contents of .research/bundles/args-read.json>)", f"python3 .research/step.py read --finish {n} {tag('read')}"]}
    if L.rows(led, "in-trial"):
        if _newer(tag("trial"), None) and (rd.get("trial") is None or tag("trial").stat().st_mtime > _t(rd["trial"])):
            return {"stage": "W", "reason": head + f"; round {n}: trial output waiting", "next": [f"python3 .research/step.py trial --finish {n} {tag('trial')}"]}
        return {"stage": "W", "reason": head + f"; round {n}: {len(L.rows(led, 'in-trial'))} charges to try",
                "next": [f"python3 .research/step.py trial {n}", "Workflow(name='trial', args=<contents of .research/bundles/args-trial.json>)", f"python3 .research/step.py trial --finish {n} {tag('trial')}"]}
    nd = [x for x in L.rows(led, "needs-data") if not x.get("claim_sha")]
    if nd:
        return {"stage": "W", "reason": head + f"; round {n}: {len(nd)} needs-data rows wait for the owner",
                "next": [f"human: {x['id']} — {x['summary'][:120]}" for x in nd[:4]]
                + ["human: write CLAIM.md for one row (method-free; the row is the main-table cell it must fill) and `stage.py accept` (binds the rows), or `python3 .research/paper_ledger.py set <id> author-required --why \"…\"`"]}
    if L.rows(led, "valid-fixable"):
        if _newer(tag("draft"), None) and (rd.get("draft") is None or tag("draft").stat().st_mtime > _t(rd["draft"])):
            return {"stage": "W", "reason": head + f"; round {n}: drafter output waiting", "next": [f"python3 .research/step.py draft --finish {n} {tag('draft')}"]}
        return {"stage": "W", "reason": head + f"; round {n}: {len(L.rows(led, 'valid-fixable'))} rows to draft",
                "next": [f"python3 .research/step.py draft {n}", "Workflow(name='draft', args=<contents of .research/bundles/args-draft.json>)", f"python3 .research/step.py draft --finish {n} {tag('draft')}"]}
    bound = [x for x in L.rows(led, "needs-data") if x.get("claim_sha") and x["claim_sha"] != claim_sha]
    if bound:
        return {"stage": "W", "reason": head + f"; round {n}: {len(bound)} needs-data rows bound to another claim text — re-accept that claim or set them author-required", "next": [f"human: {x['id']} bound to {x['claim_sha'][:12]}" for x in bound[:4]]}
    drafted_t = _t(rd.get("draft")) if rd and rd.get("draft") else 0.0
    review = (rd.get("review") or {}) if rd else {}                     # the ledger's copy of the last fact review (write_finish → intake_review)
    rev_done = bool(review) and _t(review) >= drafted_t
    if not rev_done:
        if _newer(r / "bundles" / "write-out.json", review_p):
            return {"stage": "W", "reason": head + f"; round {n}: fact review output waiting", "next": ["python3 .research/step.py write --finish .research/bundles/write-out.json"]}
        return {"stage": "W", "reason": head + f"; round {n}: fact review of the current sections",
                "next": ["python3 .research/step.py write --review", "Workflow(name='write', args=<contents of .research/bundles/args-write.json>)", "python3 .research/step.py write --finish .research/bundles/write-out.json"]}
    if review.get("verdict") != "pass":
        return {"stage": "W", "reason": head + f"; round {n}: fact review blocked and its issues are rows — run stage.py again", "next": ["python3 .research/stage.py"]}
    ok, bad = L.gate(led)
    if not ok:
        return {"stage": "W", "reason": head + f"; round {n}: ledger blocked", "next": ["human: " + x for x in bad[:5]]}
    if rd and rd.get("genuinely_new") == 0 and n >= 1:
        if (r / "DONE").exists():
            return {"stage": "DONE", "reason": (r / "DONE").read_text().strip(), "next": ["# nothing: the paper is built and gated"]}
        return {"stage": "W", "reason": head + f"; round {n} clean and nothing genuinely new: deliverables",
                "next": ["python3 .research/gate.py deliverables   # numbers on every section, review pass, main.pdf fresh → writes .research/DONE"]}
    if n >= max_rounds:
        return {"stage": "W", "reason": head + f"; {n} rounds reached max_rounds ({max_rounds}) with new issues still appearing", "next": ["human: read .research/paper-ledger.json; raise max_rounds in GOAL.md or set the remaining rows author-required"]}
    L.start_round(led, n + 1); L.save(led, r)
    return {"stage": "W", "reason": head + f"; round {n} clean → round {n + 1}", "next": [f"python3 .research/step.py read {n + 1}"]}


def _t(d: dict | None) -> float:
    try:
        return time.mktime(time.strptime(str((d or {}).get("t")), "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return 0.0
