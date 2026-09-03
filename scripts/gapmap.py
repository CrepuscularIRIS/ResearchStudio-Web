#!/usr/bin/env python3
"""gapmap.py — insight-card front-matter → gap map + flip candidates. No model call.

An insight card is `insight/<id>.md`: a YAML front-matter block (schema 2, below), then
free prose. Only the front-matter is read here.

Typed assumptions: every load-bearing belief is a (noun, type) pair — the noun is one of a
short controlled list (future, action, state, ...), the type is the slot the paper gives it
("joint(current, future) latent", "grid point + RVQ token"). A paper RELIES ON some pairs and
CHANGES others (old_type → new_type). That makes the owner's rule computable:

  good innovation = core insight × one assumption changed

  bridge      : (noun, T) relied on by ≥2 papers in domain A, changed away from T in domain ≠ A
  unchallenged: (noun, T) relied on by ≥3 papers, changed by none
  flip        : (noun, T) relied on by ≥2 papers × any other type T' seen for that noun
  sign flip   : a result in the paper's own tables that contradicts the conventional expectation
"""
from __future__ import annotations
import json, re
from collections import defaultdict
from pathlib import Path

import yaml

FM = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
NOUNS = ["future", "action", "state", "observation", "history", "reward", "objective", "supervision",
         "data", "compute", "evaluation", "memory", "planning", "representation", "modality", "loss"]
INSIGHT_REQUIRED = ["paper", "title", "year", "domain", "predecessor", "old_belief", "anomaly", "gap_crossed",
                    "core_insight", "hidden_hypothesis", "fragile_assumption", "relies_on", "changes",
                    "sign_flips", "untested", "reproduce", "naive_baseline", "mechanism",
                    "innovation_mechanism", "critical_experiment", "ablation_gaps", "formulations", "provenance"]
FORMULATION_KEYS = ["question", "hypothesis", "minimal_experiment", "kills", "conflicts"]
PROVENANCE_KEYS = ["stated", "inferred", "abduced", "speculated"]
MIN_FORMULATIONS = 3
MIN_BODY_CHARS = 1500
NUM = re.compile(r"\d+\.\d+")


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def split(text: str) -> tuple[dict, str]:
    m = FM.match(text)
    if not m:
        raise ValueError("no YAML front-matter block (--- ... ---) at the top of the file")
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        raise ValueError("front-matter is not a mapping")
    return fm, m.group(2)


# ── form check ──────────────────────────────────────────────────────────────

def _line_refs(fm: dict) -> list[tuple[str, int, str]]:
    """(field, line, text-that-should-be-near-that-line)"""
    out = []
    for r in fm.get("relies_on") or []:
        if isinstance(r, dict) and r.get("line"):
            out.append(("relies_on", int(r["line"]), str(r.get("type", ""))))
    for c in fm.get("changes") or []:
        if isinstance(c, dict) and c.get("line"):
            out.append(("changes", int(c["line"]), str(c.get("new_type", ""))))
    for s in (fm.get("provenance") or {}).get("stated") or []:
        if isinstance(s, dict) and s.get("line"):
            out.append(("provenance.stated", int(s["line"]), str(s.get("claim", ""))))
    for s in fm.get("sign_flips") or []:
        if isinstance(s, dict) and isinstance(s.get("where"), int):
            out.append(("sign_flips", int(s["where"]), f"{s.get('observed', '')}"))
    return out


def check_line_refs(fm: dict, paper_text: str) -> list[str]:
    """Every cited line must exist; a number quoted in the claim must appear within ±2 lines."""
    lines = paper_text.split("\n")  # \n only: pdftotext emits \r/\x0c that splitlines() would count as extra line breaks, desynchronising cited line numbers
    fails = []
    for field, ln, claim in _line_refs(fm):
        if ln < 1 or ln > len(lines):
            fails.append(f"{field}: line {ln} outside paper.txt (1..{len(lines)})")
            continue
        nums = NUM.findall(claim)
        if nums:
            window = "\n".join(lines[max(0, ln - 3):ln + 2])
            missing = [n for n in nums if n not in window]
            if missing:
                fails.append(f"{field}: numbers {missing} not found within ±2 of line {ln}")
    return fails


def check_insight(text: str, paper_text: str | None = None) -> list[str]:
    """Form checks on one insight card. Content is the Scientist's to judge."""
    try:
        fm, body = split(text)
    except ValueError as e:
        return [str(e)]
    fails = [f"missing field {k}" for k in INSIGHT_REQUIRED if k not in fm]
    if fails:
        return fails
    pred = fm["predecessor"]
    if not isinstance(pred, dict) or not str(pred.get("paper", "")).strip() or not str(pred.get("assumed", "")).strip():
        fails.append("predecessor must be {paper, assumed}: the work the authors reacted to and what it assumed")
    rel = fm["relies_on"]
    if not isinstance(rel, list) or not rel:
        fails.append("relies_on must be a non-empty list of {noun, type, line}")
    else:
        for i, r in enumerate(rel, 1):
            if not isinstance(r, dict) or not str(r.get("noun", "")).strip() or not str(r.get("type", "")).strip():
                fails.append(f"relies_on[{i}] lacks noun or type")
            elif len(str(r["noun"]).split()) > 3:
                fails.append(f"relies_on[{i}] noun must be ≤ 3 words (use the controlled list)")
    ch = fm["changes"]
    if not isinstance(ch, list):
        fails.append("changes must be a list (may be empty)")
    else:
        for i, c in enumerate(ch, 1):
            if not isinstance(c, dict) or any(not str(c.get(k, "")).strip() for k in ("noun", "old_type", "new_type")):
                fails.append(f"changes[{i}] needs noun, old_type, new_type")
    for k in ("sign_flips", "untested", "ablation_gaps"):
        if not isinstance(fm[k], list):
            fails.append(f"{k} must be a list (may be empty)")
    for i, s in enumerate(fm["sign_flips"] if isinstance(fm["sign_flips"], list) else [], 1):
        if not isinstance(s, dict) or any(not str(s.get(k, "")).strip() for k in ("observation", "expected", "observed", "where")):
            fails.append(f"sign_flips[{i}] needs observation, expected, observed, where")
    rep = fm["reproduce"]
    if not isinstance(rep, dict) or any(k not in rep for k in ("code", "compute", "key_number")):
        fails.append("reproduce must carry code, compute, key_number")
    fs = fm["formulations"]
    if not isinstance(fs, list) or len(fs) < MIN_FORMULATIONS:
        fails.append(f"formulations must list >= {MIN_FORMULATIONS} new formulations (ablation gaps go in ablation_gaps)")
    else:
        for i, d in enumerate(fs, 1):
            for k in FORMULATION_KEYS:
                if not isinstance(d, dict) or not str(d.get(k, "")).strip():
                    fails.append(f"formulation {i} lacks {k}")
    prov = fm["provenance"]
    if not isinstance(prov, dict) or any(k not in prov for k in PROVENANCE_KEYS):
        fails.append(f"provenance must carry the four keys {PROVENANCE_KEYS}")
    else:
        st = prov.get("stated") or []
        if not st:
            fails.append("provenance.stated is empty: nothing in the card is anchored to the paper's own text")
        elif any(not isinstance(s, dict) or not s.get("line") for s in st):
            fails.append("every provenance.stated entry needs {claim, line}")
    if len(body) < MIN_BODY_CHARS:
        fails.append(f"body is {len(body)} chars; the reasoning is shorter than {MIN_BODY_CHARS}")
    if paper_text is not None and not fails:
        fails += check_line_refs(fm, paper_text)
    return fails


# ── graph ───────────────────────────────────────────────────────────────────

def load_cards(insight_dir: Path) -> list[dict]:
    out = []
    for p in sorted(insight_dir.glob("*.md")):
        try:
            fm, _ = split(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if "paper" in fm and "relies_on" in fm:
            fm["_file"] = p.name
            out.append(fm)
    return out


def build(cards: list[dict]) -> dict:
    relied: dict[tuple, list] = defaultdict(list)      # (noun, T) → [(paper, domain)]
    changed: dict[tuple, list] = defaultdict(list)     # (noun, oldT) → [(paper, domain, newT)]
    types_seen: dict[str, dict] = defaultdict(dict)    # noun → {T_norm: T_display}
    for c in cards:
        dom = str(c.get("domain", "?"))
        for r in c.get("relies_on") or []:
            n, t = norm(r.get("noun")), str(r.get("type", ""))
            relied[(n, norm(t))].append((c["paper"], dom))
            types_seen[n].setdefault(norm(t), t)
        for ch in c.get("changes") or []:
            n, o, w = norm(ch.get("noun")), str(ch.get("old_type", "")), str(ch.get("new_type", ""))
            changed[(n, norm(o))].append((c["paper"], dom, w))
            types_seen[n].setdefault(norm(o), o)
            types_seen[n].setdefault(norm(w), w)
    bridges, unchallenged, flips = [], [], []
    for (n, t), holders in relied.items():
        disp = types_seen[n].get(t, t)
        by_dom: dict[str, list] = defaultdict(list)
        for paper, dom in holders:
            by_dom[dom].append(paper)
        for dom, papers in by_dom.items():
            if len(papers) < 2:
                continue
            rel = [(p, d, w) for p, d, w in changed.get((n, t), []) if d != dom]
            if rel:
                bridges.append({"noun": n, "type": disp, "domain": dom, "held_by": papers,
                                "changed_by": [{"paper": p, "domain": d, "to": w} for p, d, w in rel]})
        if len(holders) >= 3 and not changed.get((n, t)):
            unchallenged.append({"noun": n, "type": disp, "held_by": [p for p, _ in holders]})
        if len(holders) >= 2:
            for t2, t2disp in types_seen[n].items():
                if t2 == t:
                    continue
                precedent = [p for p, _ in relied.get((n, t2), [])] + \
                            [p for p, _, w in changed.get((n, t), []) if norm(w) == t2]
                flips.append({"noun": n, "from": disp, "to": t2disp, "holders": [p for p, _ in holders],
                              "precedent": sorted(set(precedent))})
    bridges.sort(key=lambda b: (-len(b["held_by"]), -len(b["changed_by"])))
    unchallenged.sort(key=lambda u: -len(u["held_by"]))
    flips.sort(key=lambda f: (-len(f["holders"]), -len(f["precedent"]), f["noun"]))
    sign_flips = [{"paper": c["paper"], **s} for c in cards for s in (c.get("sign_flips") or []) if isinstance(s, dict)]
    return {"n_cards": len(cards), "bridges": bridges, "unchallenged": unchallenged, "flips": flips,
            "sign_flips": sign_flips}


def render(graph: dict, cards: list[dict], graveyard: list[str], cap: int = 40) -> str:
    L = [f"# Gap map — {graph['n_cards']} insight cards", "",
         "## Graveyard (every candidate below must dodge these)", ""]
    L += [f"- {g}" for g in graveyard] or ["- none yet"]
    L += ["", "## Bridge candidates — (noun, type) relied on in domain A, already changed elsewhere", "",
          "| # | noun | type | held in | by | changed to (paper, domain) |", "|---|---|---|---|---|---|"]
    for i, b in enumerate(graph["bridges"], 1):
        ch = "; ".join(f"{c['to']} ({c['paper']}, {c['domain']})" for c in b["changed_by"])
        L.append(f"| B{i} | {b['noun']} | {b['type']} | {b['domain']} | {', '.join(b['held_by'])} | {ch} |")
    if not graph["bridges"]:
        L.append("| — | none | | | | |")
    L += ["", "## Unchallenged — relied on by ≥3 papers, changed by none", "",
          "| # | noun | type | held by |", "|---|---|---|---|"]
    for i, u in enumerate(graph["unchallenged"], 1):
        L.append(f"| U{i} | {u['noun']} | {u['type']} | {', '.join(u['held_by'])} |")
    if not graph["unchallenged"]:
        L.append("| — | none | | |")
    L += ["", f"## Flip candidates — noun: type → other type (top {cap}; all in insight/CANDIDATES.json)", "",
          "| # | noun | from | to | holders | precedent |", "|---|---|---|---|---|---|"]
    for i, f in enumerate(graph["flips"][:cap], 1):
        L.append(f"| F{i} | {f['noun']} | {f['from']} | {f['to']} | {', '.join(f['holders'])} | {', '.join(f['precedent']) or '—'} |")
    if not graph["flips"]:
        L.append("| — | none | | | | |")
    L += ["", f"## Sign flips — results that contradicted the expectation (top {cap})", "",
          "| paper | observation | expected | observed | where |", "|---|---|---|---|---|"]
    for s in graph["sign_flips"][:cap]:
        L.append(f"| {s['paper']} | {str(s.get('observation', ''))[:90]} | {str(s.get('expected', ''))[:50]} | "
                 f"{str(s.get('observed', ''))[:50]} | {s.get('where', '')} |")
    if not graph["sign_flips"]:
        L.append("| — | none | | | |")
    L += ["", f"## Formulations index (top {cap})", ""]
    n = 0
    for c in cards:
        for d in c.get("formulations") or []:
            if n >= cap:
                break
            L.append(f"- **{c['paper']}** · {str(d.get('question', ''))[:140]} — kills: {str(d.get('kills', ''))[:60]} "
                     f"— conflicts: {str(d.get('conflicts', ''))[:60]}  (`insight/{c['_file']}`)")
            n += 1
    L += ["", f"## Ablation gaps the papers left (top {cap}; derivative — not candidates)", ""]
    n = 0
    for c in cards:
        for g in c.get("ablation_gaps") or []:
            if n >= cap:
                break
            L.append(f"- {c['paper']}: {str(g)[:140]}")
            n += 1
    return "\n".join(L) + "\n"


def cand_key(c: dict) -> str:
    """Stable id for a candidate across cycles (the CRITIQUE's DROPPED.json is keyed by it)."""
    if "from" in c:
        return f"flip:{norm(c['noun'])}:{norm(c['from'])}->{norm(c['to'])}"
    if "observation" in c:
        return f"sign:{c.get('paper', '?')}:{norm(c['observation'])[:60]}"
    return f"other:{norm(json.dumps(c, sort_keys=True))[:80]}"


def candidates(graph: dict, dropped: dict | None = None) -> dict:
    """What the CRITIQUE call reads. Candidates dropped in an earlier cycle (insight/DROPPED.json,
    key → {check, cycle, reason}) are set aside, not re-judged; they stay listed as possible parents
    — openevolve's archive rule: a structurally distinct loser is not discarded."""
    dropped = dropped or {}
    live, gone = {"flips": [], "sign_flips": []}, []
    for kind in ("flips", "sign_flips"):
        for c in graph[kind]:
            k = cand_key(c)
            if k in dropped:
                gone.append({"key": k, **dropped[k]})
            else:
                live[kind].append({"key": k, **c})
    return {**live, "bridges": graph["bridges"], "unchallenged": graph["unchallenged"], "dropped": gone}
