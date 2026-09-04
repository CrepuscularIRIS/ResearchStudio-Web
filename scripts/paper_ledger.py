#!/usr/bin/env python3
"""paper_ledger.py — the outer loop's issue ledger (paperjury `ledger.js`, reduced): the only durable record of what the referees
raised, what the jury decided, what the drafter closed, and what still needs data. Scripts write it; no lane ever does.

Statuses: raised → in-trial → {valid-fixable → closed | needs-data → closed (by a record) | invalid-drop | author-required};
minor / mechanical issues skip the trial (valid-fixable at once). GATE-BLOCKING = active major in {raised, in-trial,
valid-fixable, needs-data}; author-required, invalid-drop and closed are gate-ok. An issue with no verdict is a blocker, never a
pass: budget exhaustion cannot fake completion.

Dedup (the clerk): a new weakness on the same passage whose summary shares ≥ SAME_JACCARD of its tokens with an existing row
is a RE-RAISE (corroboration +1, or — for a closed row — proof that the fix did not land: it reopens); otherwise it is
genuinely new. When unsure, keep separate: a missed merge is recoverable, a wrong merge hides a distinct issue.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = "paper-ledger.json"
ACTIVE = ("raised", "in-trial", "valid-fixable", "needs-data")
SAME_JACCARD = 0.6
STOP = {"the", "a", "an", "of", "to", "in", "is", "and", "or", "not", "for", "on", "that", "this", "with", "as", "be", "are", "it", "its"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def load(rdir: Path = HERE) -> dict:
    p = rdir / LEDGER
    return json.loads(p.read_text()) if p.exists() else {"issues": [], "rounds": [], "next_id": 1}


def save(led: dict, rdir: Path = HERE) -> None:
    (rdir / LEDGER).write_text(json.dumps(led, indent=1, ensure_ascii=False))


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(s or "").lower()) if w not in STOP and len(w) > 2}


def same_issue(a: dict, b: dict) -> bool:
    if a.get("passage_id") != b.get("passage_id") or not a.get("passage_id"):
        return False
    ta, tb = _tokens(a.get("summary")), _tokens(b.get("summary"))
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= SAME_JACCARD


def add(led: dict, weakness: dict, family: str, rnd: int) -> dict:
    """Intake one anchored weakness. Returns {id, event: new|corroborated|reopened}."""
    for row in led["issues"]:
        if same_issue(row, weakness):
            if family not in row["raised_by"]:
                row["raised_by"].append(family)
                row["corroboration"] = len(row["raised_by"])
            if row["status"] == "closed":                      # a clean re-review re-raised it: the fix did not land
                _set(row, "raised", f"re-raised in round {rnd} by {family} after a close", reraised=True)
                return {"id": row["id"], "event": "reopened"}
            if row["status"] == "invalid-drop":
                return {"id": row["id"], "event": "dropped-before"}
            return {"id": row["id"], "event": "corroborated"}
    rid = f"I-{led['next_id']:03d}"; led["next_id"] += 1
    row = {"id": rid, "round": rnd, "summary": weakness["summary"], "evidence_anchor": weakness.get("evidence_anchor", ""),
           "section": weakness.get("section"), "passage_id": weakness.get("passage_id"),
           "significance": weakness.get("significance", "major"), "kind": weakness.get("kind", "substantive"),
           "references": weakness.get("references", ""), "raised_by": [family], "corroboration": 1,
           "status": "raised", "close_criterion": None, "tally": None, "claim_sha": None, "records": [],
           "history": [{"t": _now(), "status": "raised", "why": f"round {rnd}, {family}"}]}
    led["issues"].append(row)
    return {"id": rid, "event": "new"}


def _set(row: dict, status: str, why: str, **fields) -> None:
    row["status"] = status
    row.update(fields)
    row["history"].append({"t": _now(), "status": status, "why": why})


def set_status(led: dict, rid: str, status: str, why: str, **fields) -> dict:
    row = get(led, rid)
    if row is None:
        raise KeyError(rid)
    _set(row, status, why, **fields)
    return row


def get(led: dict, rid: str) -> dict | None:
    return next((r for r in led["issues"] if r["id"] == rid), None)


def route(led: dict) -> dict:
    """Deterministic routing of `raised` rows: major & substantive → in-trial; anything else → valid-fixable with the summary
    as its criterion (the polish track, without a light-check agent)."""
    n = {"in-trial": 0, "valid-fixable": 0}
    for row in led["issues"]:
        if row["status"] != "raised":
            continue
        if row["significance"] == "major" and row["kind"] == "substantive":
            _set(row, "in-trial", "routed: major substantive"); n["in-trial"] += 1
        else:
            _set(row, "valid-fixable", "routed: minor or mechanical (polish track)", close_criterion=row["summary"]); n["valid-fixable"] += 1
    return n


def rows(led: dict, *statuses: str) -> list[dict]:
    return [r for r in led["issues"] if r["status"] in statuses]


def active_major(led: dict) -> list[dict]:
    return [r for r in led["issues"] if r["status"] in ACTIVE and r["significance"] == "major"]


def gate(led: dict) -> tuple[bool, list[str]]:
    """PASS iff no gate-blocking active major. The list names what blocks."""
    bad = [f"{r['id']} [{r['status']}] {r['summary'][:80]}" for r in active_major(led)]
    return (not bad), bad


def bind_needs_data(led: dict, claim_sha: str) -> list[str]:
    """When the owner accepts a claim, every unbound needs-data row is bound to it: the claim loop is that row's handler."""
    out = []
    for r in led["issues"]:
        if r["status"] == "needs-data" and not r.get("claim_sha"):
            r["claim_sha"] = claim_sha; r["history"].append({"t": _now(), "status": "needs-data", "why": f"bound to claim {claim_sha[:12]}"}); out.append(r["id"])
    return out


def close_by_claim(led: dict, claim_sha: str, records: list[str], why: str) -> list[str]:
    """The claim loop finished (KEEP + ladder, or the incumbent shipped): its needs-data rows close with the records that answer them."""
    out = []
    for r in led["issues"]:
        if r["status"] == "needs-data" and r.get("claim_sha") == claim_sha:
            _set(r, "closed", why, records=records); out.append(r["id"])
    return out


def start_round(led: dict, n: int) -> dict:
    rd = {"n": n, "t": _now(), "genuinely_new": None, "read": None, "trial": None, "draft": None, "review": None}
    led["rounds"] = [x for x in led["rounds"] if x["n"] != n] + [rd]
    return rd


def current_round(led: dict) -> dict | None:
    return led["rounds"][-1] if led["rounds"] else None


def summary(led: dict) -> str:
    counts = {}
    for r in led["issues"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    rd = current_round(led)
    return f"round {rd['n'] if rd else '-'} · " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())) if counts else "ledger empty"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gate"); sub.add_parser("docket"); sub.add_parser("summary")
    p = sub.add_parser("set", help="owner: set a row's status (author-required | invalid-drop | closed) with a reason"); p.add_argument("id"); p.add_argument("status", choices=["author-required", "invalid-drop", "closed"]); p.add_argument("--why", required=True)
    a = ap.parse_args()
    led = load()
    if a.cmd == "gate":
        ok, bad = gate(led); print("PASS" if ok else "BLOCKED\n" + "\n".join(bad)); raise SystemExit(0 if ok else 1)
    if a.cmd == "docket":
        for r in led["issues"]:
            print(f"{r['id']} {r['status']:15} {r['significance']:5} {r['kind']:11} x{r['corroboration']} {r.get('passage_id') or '-':28} {r['summary'][:90]}")
        raise SystemExit(0)
    if a.cmd == "summary":
        print(summary(led)); raise SystemExit(0)
    set_status(led, a.id, a.status, f"owner: {a.why}"); save(led); print(f"{a.id} → {a.status}")
