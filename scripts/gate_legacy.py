#!/usr/bin/env python3
"""gate_legacy.py — the minimal-loop (Search → Idea → Experiment, ccf) gates the claim loop no longer calls: search screen,
schema-1/2 card links, critique sha, Type-B verdict / packet / merge, budget and the views. `G` is gate.py's namespace, passed at
call time. Kept behind `gate.py`'s CLI for the plugin's older campaigns; nothing under stage.py / step.py / bundle.py / outer.py
imports it directly.
"""
from __future__ import annotations
import fnmatch
import json, subprocess, time
from pathlib import Path
import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import gapmap  # noqa: E402


def screen(manifest: list[dict], insight_dir: Path, min_score: int, max_n: int) -> list[dict]:
    """Mechanical selection for REVERSE: full text present, relevance >= min_score, not already
    reverse-engineered. Ranked by score then citations. No judgment lives here."""
    done = {p.stem for p in insight_dir.glob("*.md")}
    rows = [p for p in manifest if p.get("status") == "text" and int(p.get("relevance_score") or 0) >= min_score
            and p["id"] not in done]
    rows.sort(key=lambda p: (-int(p.get("relevance_score") or 0), -int(p.get("citation_count") or 0)))
    return rows[:max_n]


def _check_schema1_links(card: dict, rdir: Path) -> list[str]:
    fails = []
    bfile, _, anchor = card["bridge"].partition("#")
    bpath = rdir / bfile
    if not bpath.exists():
        fails.append(f"bridge file {bfile} not found")
    else:
        stem = bpath.stem + (f"-{anchor}" if anchor else "")
        if not any(p.name.startswith(stem) for p in (rdir / "lit").glob("*.md")):
            fails.append(f"no lit packet for bridge {stem}; retrieval did not run")
    return fails


def _check_schema2_links(G, card: dict, rdir: Path) -> list[str]:
    fails = []
    if card["parent"] != "ROOT" and not (rdir / "cards" / f"{card['parent']}.json").exists():
        fails.append(f"parent {card['parent']} is not ROOT and no such card exists")
    if not isinstance(card["source_insights"], list) or not card["source_insights"]:
        fails.append("source_insights must be a non-empty list of insight ids")
    else:
        for sid in card["source_insights"]:
            if not (rdir / "insight" / f"{sid}.md").exists():
                fails.append(f"source insight {sid} not found under insight/")
    if not isinstance(card["cites"], list) or not card["cites"]:
        fails.append("cites must name >= 1 record, card, insight id, or GOAL")
    else:
        for ref in card["cites"]:
            if not G._cite_resolves(str(ref), rdir):
                fails.append(f"cites entry {ref} resolves to nothing on disk")
    for k in ("mediator", "conflicts"):
        if not str(card.get(k, "")).strip():
            fails.append(f"{k} must be a non-empty string")
    if card["source_lens"] not in G.LENSES:
        fails.append(f"source_lens must be one of {G.LENSES}")
    return fails


def record_critique(G, card_path: Path, critique_path: Path) -> int:
    card = json.loads(card_path.read_text())
    card["critique_sha"] = G.card_sha(card)
    card["critique_path"] = str(critique_path)
    card_path.write_text(json.dumps(card, indent=2))
    return 0


def compute_state(type_a: dict, type_b: dict) -> str:
    """REFUTED only by a record (kill_hit). SUPPORTED needs type-A pass, reviewer SUPPORTED, no open blockers."""
    if type_a.get("kill_hit"):
        return "REFUTED"
    if type_a.get("pass") and type_b.get("verdict") == "SUPPORTED" \
            and not type_a.get("blockers") and not type_b.get("blocking"):
        return "SUPPORTED"
    return "CONTESTED"


def write_packet(G, card: dict, rec: dict) -> Path:
    """The only thing the Reviewer sees: fixed role prompt + card + rendered record + artifact paths."""
    role = (G.HERE / "templates" / "role-prompt.md").read_text()
    rec_md_p = G.HERE / "records" / f"{rec['run']}.md"
    rec_md = rec_md_p.read_text() if rec_md_p.exists() else json.dumps(rec, indent=2)
    paths = "\n".join(f"- {a['path']}" for a in rec.get("artifacts", []))
    body = (f"{role}\n\n<card>\n{json.dumps(card, indent=2)}\n</card>\n\n"
            f"<record>\n{rec_md}\n</record>\n\n<artifact_paths>\n{paths}\n</artifact_paths>\n")
    out = G.HERE / "packets" / f"{card['id']}.md"; out.parent.mkdir(exist_ok=True)
    out.write_text(body)
    return out


def write_verdict(G, card: dict, reviewer_out: dict) -> str:
    vp = G.HERE / "verdicts" / f"{card['id']}.json"
    v = json.loads(vp.read_text()) if vp.exists() else {
        "card": card["id"], "type_a": {"pass": False, "checks": ["no type_a"], "kill_hit": False, "blockers": []}}
    v["type_b"] = {k: reviewer_out.get(k) for k in ("verdict", "criterion_met", "blocking", "reviewer", "evidence")}
    v["state"] = compute_state(v["type_a"], v["type_b"])
    v["decided_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    vp.parent.mkdir(exist_ok=True)
    vp.write_text(json.dumps(v, indent=2))
    return v["state"]


def merge_decision(card: dict, verdict: dict, test_rec: dict, goal: dict, changed: list[str]) -> list[str]:
    """Held-out merge guard. Refusals, empty = allowed."""
    c = goal["campaign"]
    fails = []
    if verdict.get("state") != "SUPPORTED":
        fails.append(f"state is {verdict.get('state')}, not SUPPORTED")
    base = c.get("test_baseline_score")
    if base is None:
        fails.append("GOAL.md test_baseline_score is null: measure the trunk's held-out baseline first")
    else:
        sign = 1.0 if c.get("metric_direction", "maximize") == "maximize" else -1.0
        margin = sign * (float(test_rec["mean"]) - float(base))
        need = float(c.get("merge_margin") or card["mde"])
        if margin < need:
            fails.append(f"held-out margin {margin:.3f} below required {need:.3f}")
    if test_rec.get("card") != card["id"]:
        fails.append("test record belongs to another card")
    prot = c.get("protected_paths") or []
    hit = [f for f in changed if any(fnmatch.fnmatch(f, g) for g in prot)]
    if hit:
        fails.append(f"branch touches protected paths: {hit}")
    return fails


def merge(G, card_id: str, branch: str, test_record: Path, dry_run: bool) -> int:
    goal = G.load_goal(); c = goal["campaign"]
    repo = G.W / c["repo_root"]; trunk = c.get("trunk_branch", "research-trunk")
    card = json.loads((G.HERE / "cards" / f"{card_id}.json").read_text())
    vp = G.HERE / "verdicts" / f"{card_id}.json"
    verdict = json.loads(vp.read_text()) if vp.exists() else {}
    test_rec = json.loads(test_record.read_text())
    diff = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", f"{trunk}...{branch}"],
                          capture_output=True, text=True)
    # decision checks first: a config refusal (null baseline, wrong state) must name itself
    # even when the branch string does not resolve in the repo (cheap preconditions fail loud).
    changed = [l for l in diff.stdout.splitlines() if l.strip()] if diff.returncode == 0 else []
    fails = merge_decision(card, verdict, test_rec, goal, changed)
    if diff.returncode and not fails:
        print(f"REFUSED: git diff failed: {diff.stderr.strip()}", file=sys.stderr); return 1
    if fails:
        print("REFUSED:\n" + "\n".join(f"  {f}" for f in fails), file=sys.stderr); return 1
    if dry_run:
        print(f"WOULD MERGE {branch} into {trunk} ({len(changed)} files)"); return 0
    r = subprocess.run(["git", "-C", str(repo), "merge", "--no-ff", "-m", f"merge {card_id}: {branch}", branch],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip()); return r.returncode


def budget(G, goal: dict) -> dict:
    ledger = G.HERE / "ledger.jsonl"
    return {"ceiling": goal["campaign"]["gpu_h_ceiling"], "used": round(G.ledger_used_gpu_h(ledger), 2),
            "remaining_spendable": round(G.remaining_gpu_h(goal, ledger), 2)}


def graveyard(G, cards: dict, verdicts: dict) -> list[str]:
    return [f"{cid}: {G.headline(cards[cid])[:120]}" for cid, v in sorted(verdicts.items())
            if v.get("state") == "REFUTED" and cid in cards]


def render_tree(G, cards: dict, verdicts: dict) -> str:
    def state(cid):
        c = cards[cid]
        return verdicts.get(cid, {}).get("state", "LIVE" if c.get("G.frozen_sha") else "DRAFT")
    kids: dict[str, list] = {}
    for cid, c in cards.items():
        kids.setdefault(c.get("parent", "ROOT"), []).append(cid)
    lines = ["# Hypothesis tree", "", "ROOT"]

    def walk(pid, depth):
        for cid in sorted(kids.get(pid, [])):
            lines.append(f"{'  ' * depth}- {cid} [{state(cid)}] {G.headline(cards[cid])[:100]}")
            walk(cid, depth + 1)
    walk("ROOT", 1)
    dead = graveyard(G, cards, verdicts)
    lines += ["", "## Graveyard", ""] + ([f"- {d}" for d in dead] or ["- none"])
    return "\n".join(lines) + "\n"


def render_views(G, goal: dict) -> None:
    vdir = G.HERE / "views"; vdir.mkdir(exist_ok=True)
    cards = {p.stem: json.loads(p.read_text()) for p in (G.HERE / "cards").glob("*.json")}
    verdicts = {p.stem: json.loads(p.read_text()) for p in (G.HERE / "verdicts").glob("*.json")}
    records = [json.loads(p.read_text()) for p in (G.HERE / "records").glob("*.json")]
    rows = ["| card | schema | parent | lens | state | claim | n_req | mde | cost |", "|---|---|---|---|---|---|---|---|---|"]
    for cid, c in sorted(cards.items()):
        st = verdicts.get(cid, {}).get("state", "LIVE" if c.get("G.frozen_sha") else "DRAFT")
        rows.append(f"| {cid} | {G.card_schema(c)} | {c.get('parent', '—')} | {c.get('source_lens', c.get('family', '—'))} | {st} | "
                    f"{G.headline(c)[:80]} | {c.get('n_required', 1)} | {c.get('mde', '—')} | {c['cost_gpu_h']} |")
    (vdir / "HYPOTHESES.md").write_text("# Hypotheses\n\n" + "\n".join(rows) + "\n")
    rrows = ["| run | card | n | mean | ci95 | band | kill | canary | cost |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(records, key=lambda r: r["run"]):
        rrows.append(f"| {r['run']} | {r['card']} | {r['n_realized']} | {r['mean']:.3f} | {r['ci95']} | "
                     f"{r['band_hit']} | {r['kill_hit']} | {r['canary']['pass']} | {r['cost_gpu_h']} |")
    (vdir / "RESULTS.md").write_text("# Results\n\n" + "\n".join(rrows) + "\n")
    drows = [f"- {cid}: {v.get('state')} — reviewer {v.get('type_b', {}).get('reviewer')} · blocking {v.get('type_b', {}).get('blocking')}"
             for cid, v in sorted(verdicts.items())]
    (vdir / "DECISIONS.md").write_text("# Decisions\n\n" + "\n".join(drows or ["- none"]) + "\n")
    (vdir / "BUDGET.md").write_text("# Budget\n\n```json\n" + json.dumps(budget(G, goal), indent=2) + "\n```\n")
    (vdir / "TREE.md").write_text(render_tree(G, cards, verdicts))


def render_gapmap(G) -> Path:
    idir = G.HERE / "insight"; idir.mkdir(exist_ok=True)
    cards = {p.stem: json.loads(p.read_text()) for p in (G.HERE / "cards").glob("*.json")}
    verdicts = {p.stem: json.loads(p.read_text()) for p in (G.HERE / "verdicts").glob("*.json")}
    icards = gapmap.load_cards(idir)
    g = gapmap.build(icards)
    out = G.HERE / "views" / "GAPMAP.md"; out.parent.mkdir(exist_ok=True)
    out.write_text(gapmap.render(g, icards, graveyard(G, cards, verdicts)))
    dp = idir / "DROPPED.json"
    dropped = json.loads(dp.read_text()) if dp.exists() else {}
    (idir / "CANDIDATES.json").write_text(json.dumps(gapmap.candidates(g, dropped), indent=1, ensure_ascii=False))
    return out
