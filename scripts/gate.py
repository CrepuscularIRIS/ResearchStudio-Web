#!/usr/bin/env python3
"""gate.py — content gates over .research/ artifacts.

Subcommands: goal · card · critique · freeze · record · packet · verdict · budget · views
Every check reads artifacts on disk; nothing here trusts a label.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, re, sys, time
from pathlib import Path

import yaml

PLUGIN = Path(__file__).resolve().parents[1]     # plugin root (templates/ lives here)
HERE = Path(os.environ.get("RESEARCH_DIR") or Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()) / ".research")
W = HERE.parent                                  # project root (GOAL.md lives here)
YAML_BLOCK = re.compile(r"^```yaml\n(.*?)\n```", re.S)

REQUIRED = ["id", "bridge", "claim", "mechanism", "forbids", "prediction", "kill", "controls",
            "seed_sd", "n_required", "mde", "instrument", "oracle", "tier", "cost_gpu_h"]
MUTABLE = {"frozen_sha", "arbor_node", "critique_sha", "critique_path"}


# ── goal ────────────────────────────────────────────────────────────────────

def load_goal(workspace: Path = W) -> dict:
    text = (workspace / "GOAL.md").read_text(encoding="utf-8")
    m = YAML_BLOCK.search(text)
    if not m:
        raise SystemExit("GOAL.md has no leading ```yaml campaign block")
    return yaml.safe_load(m.group(1))


# ── card ────────────────────────────────────────────────────────────────────

def mde_lehr(seed_sd: float, n: int) -> float:
    """Lehr's rule: minimum detectable effect at 80% power, alpha 0.05, two arms of n seeds."""
    return 2.8 * float(seed_sd) * math.sqrt(2.0 / int(n))


def card_sha(card: dict) -> str:
    canon = {k: v for k, v in card.items() if k not in MUTABLE}
    return hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def ledger_used_gpu_h(ledger: Path) -> float:
    used = 0.0
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("event") == "stop":
                used += float(e.get("wall_s", 0)) / 3600.0
    return used


def remaining_gpu_h(goal: dict, ledger: Path) -> float:
    c = goal["campaign"]
    return float(c["gpu_h_ceiling"]) * (1 - float(c["caps"]["reserve_frac"])) - ledger_used_gpu_h(ledger)


def check_card(card: dict, goal: dict, rdir: Path) -> list[str]:
    fails: list[str] = []
    for k in REQUIRED:
        if k not in card:
            fails.append(f"missing field {k}")
    if fails:
        return fails
    kill = card["kill"]
    if not isinstance(kill.get("threshold"), (int, float)):
        fails.append("kill.threshold must be numeric")
    if card["prediction"].get("direction") not in ("maximize", "minimize"):
        fails.append("prediction.direction must be maximize|minimize")
    if int(card["n_required"]) < 3:
        fails.append("n_required must be >= 3")
    need = mde_lehr(card["seed_sd"], max(int(card["n_required"]), 1))
    if float(card["mde"]) + 1e-9 < need:
        fails.append(f"mde {card['mde']} below Lehr MDE {need:.3f} for n={card['n_required']}")
    band = card["prediction"].get("band") or [0, 0]
    if float(band[0]) <= float(card["mde"]):
        fails.append(f"band[0] {band[0]} must exceed mde {card['mde']}")
    if not card["controls"]:
        fails.append("controls must be non-empty")
    caps = goal["campaign"]["caps"]
    rem = remaining_gpu_h(goal, rdir / "ledger.jsonl")
    if float(card["cost_gpu_h"]) > rem * float(caps["single_run_frac"]):
        fails.append(f"budget: cost {card['cost_gpu_h']} > {caps['single_run_frac']} x remaining {rem:.1f} GPU-h")
    if float(card["oracle"].get("cost_gpu_h", 0)) > float(card["cost_gpu_h"]) * float(caps["oracle_frac"]):
        fails.append("budget: oracle cost exceeds oracle_frac of card cost")
    # dedup: the bridge must exist and have a lit packet; the claim must be new
    bfile, _, anchor = card["bridge"].partition("#")
    bpath = rdir / bfile
    if not bpath.exists():
        fails.append(f"bridge file {bfile} not found")
    else:
        stem = bpath.stem + (f"-{anchor}" if anchor else "")
        if not any(p.name.startswith(stem) for p in (rdir / "lit").glob("*.md")):
            fails.append(f"no lit packet for bridge {stem}; retrieval did not run")
    mine = _norm(card["claim"])
    for p in (rdir / "cards").glob("*.json"):
        other = json.loads(p.read_text())
        if other.get("id") != card["id"] and _norm(other.get("claim", "")) == mine:
            fails.append(f"duplicate claim of {other.get('id')}")
    for p in (rdir / "records").glob("*.json"):
        if json.loads(p.read_text()).get("claim_norm") == mine:
            fails.append(f"claim already measured in {p.name}")
    return fails


def record_critique(card_path: Path, critique_path: Path) -> int:
    card = json.loads(card_path.read_text())
    card["critique_sha"] = card_sha(card)
    card["critique_path"] = str(critique_path)
    card_path.write_text(json.dumps(card, indent=2))
    return 0


def freeze_card(card_path: Path) -> int:
    card = json.loads(card_path.read_text())
    sha = card_sha(card)
    if card.get("critique_sha") and card["critique_sha"] != sha:
        print("REFUSED: card changed after the Explorer critique; re-run critique first", file=sys.stderr)
        return 1
    card["frozen_sha"] = sha
    card_path.write_text(json.dumps(card, indent=2))
    print(sha)
    return 0


# ── record ──────────────────────────────────────────────────────────────────

def check_record(rec: dict, card: dict) -> list[str]:
    fails: list[str] = []
    if int(rec["n_realized"]) < int(card["n_required"]):
        fails.append(f"n_realized {rec['n_realized']} < n_required {card['n_required']}")
    if not rec["canary"]["pass"]:
        fails.append("canary failed: instrument not validated")
    if float(rec["checkpoint_loaded_frac"]) < 0.9:
        fails.append(f"checkpoint_loaded_frac {rec['checkpoint_loaded_frac']} < 0.9")
    if rec["card"] != card["id"]:
        fails.append("record/card id mismatch")
    missing = [a["path"] for a in rec["artifacts"] if not a["sha256"]]
    if missing:
        fails.append(f"artifacts missing on disk: {missing}")
    return fails


def write_type_a(card_id: str, rec: dict, fails: list[str]) -> Path:
    vdir = HERE / "verdicts"; vdir.mkdir(exist_ok=True)
    vp = vdir / f"{card_id}.json"
    v = json.loads(vp.read_text()) if vp.exists() else {"card": card_id}
    v["type_a"] = {"pass": not fails, "checks": fails, "band_hit": rec["band_hit"],
                   "kill_hit": rec["kill_hit"], "blockers": rec.get("blockers", []), "record": rec["run"]}
    vp.write_text(json.dumps(v, indent=2))
    return vp


# ── verdict, packet, budget, views ──────────────────────────────────────────

def compute_state(type_a: dict, type_b: dict) -> str:
    """REFUTED only by a record (kill_hit). SUPPORTED needs type-A pass, reviewer SUPPORTED, no open blockers."""
    if type_a.get("kill_hit"):
        return "REFUTED"
    if type_a.get("pass") and type_b.get("verdict") == "SUPPORTED" \
            and not type_a.get("blockers") and not type_b.get("blocking"):
        return "SUPPORTED"
    return "CONTESTED"


def write_packet(card: dict, rec: dict) -> Path:
    """The only thing the Reviewer sees: fixed role prompt + card + rendered record + artifact paths."""
    role_p = HERE / "templates" / "role-prompt.md"
    role = (role_p if role_p.exists() else PLUGIN / "templates" / "role-prompt.md").read_text()
    rec_md_p = HERE / "records" / f"{rec['run']}.md"
    rec_md = rec_md_p.read_text() if rec_md_p.exists() else json.dumps(rec, indent=2)
    paths = "\n".join(f"- {a['path']}" for a in rec.get("artifacts", []))
    body = (f"{role}\n\n<card>\n{json.dumps(card, indent=2)}\n</card>\n\n"
            f"<record>\n{rec_md}\n</record>\n\n<artifact_paths>\n{paths}\n</artifact_paths>\n")
    out = HERE / "packets" / f"{card['id']}.md"; out.parent.mkdir(exist_ok=True)
    out.write_text(body)
    return out


def write_verdict(card: dict, reviewer_out: dict) -> str:
    vp = HERE / "verdicts" / f"{card['id']}.json"
    v = json.loads(vp.read_text()) if vp.exists() else {
        "card": card["id"], "type_a": {"pass": False, "checks": ["no type_a"], "kill_hit": False, "blockers": []}}
    v["type_b"] = {k: reviewer_out.get(k) for k in ("verdict", "criterion_met", "blocking", "reviewer", "evidence")}
    v["state"] = compute_state(v["type_a"], v["type_b"])
    v["decided_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    vp.parent.mkdir(exist_ok=True)
    vp.write_text(json.dumps(v, indent=2))
    return v["state"]


def budget(goal: dict) -> dict:
    ledger = HERE / "ledger.jsonl"
    return {"ceiling": goal["campaign"]["gpu_h_ceiling"], "used": round(ledger_used_gpu_h(ledger), 2),
            "remaining_spendable": round(remaining_gpu_h(goal, ledger), 2)}


def render_views(goal: dict) -> None:
    vdir = HERE / "views"; vdir.mkdir(exist_ok=True)
    cards = {p.stem: json.loads(p.read_text()) for p in (HERE / "cards").glob("*.json")}
    verdicts = {p.stem: json.loads(p.read_text()) for p in (HERE / "verdicts").glob("*.json")}
    records = [json.loads(p.read_text()) for p in (HERE / "records").glob("*.json")]
    rows = ["| card | state | claim | n_req | mde | cost |", "|---|---|---|---|---|---|"]
    for cid, c in sorted(cards.items()):
        st = verdicts.get(cid, {}).get("state", "LIVE" if c.get("frozen_sha") else "DRAFT")
        rows.append(f"| {cid} | {st} | {c['claim'][:80]} | {c['n_required']} | {c['mde']} | {c['cost_gpu_h']} |")
    (vdir / "HYPOTHESES.md").write_text("# Hypotheses\n\n" + "\n".join(rows) + "\n")
    rrows = ["| run | card | n | mean | ci95 | band | kill | canary | cost |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(records, key=lambda r: r["run"]):
        rrows.append(f"| {r['run']} | {r['card']} | {r['n_realized']} | {r['mean']:.3f} | {r['ci95']} | "
                     f"{r['band_hit']} | {r['kill_hit']} | {r['canary']['pass']} | {r['cost_gpu_h']} |")
    (vdir / "RESULTS.md").write_text("# Results\n\n" + "\n".join(rrows) + "\n")
    drows = [f"- {cid}: {v.get('state')} — reviewer {v.get('type_b', {}).get('reviewer')} · blocking {v.get('type_b', {}).get('blocking')}"
             for cid, v in sorted(verdicts.items())]
    (vdir / "DECISIONS.md").write_text("# Decisions\n\n" + "\n".join(drows or ["- none"]) + "\n")
    (vdir / "BUDGET.md").write_text("# Budget\n\n```json\n" + json.dumps(budget(goal), indent=2) + "\n```\n")


# ── cli ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("goal", help="print the parsed campaign block")
    p = sub.add_parser("card", help="content checks on a card"); p.add_argument("card")
    p = sub.add_parser("critique", help="record the Explorer critique sha on a card"); p.add_argument("card"); p.add_argument("critique")
    p = sub.add_parser("freeze", help="freeze a card (writes frozen_sha)"); p.add_argument("card")
    p = sub.add_parser("record", help="type-A checks on a rendered record"); p.add_argument("record"); p.add_argument("card")
    p = sub.add_parser("packet", help="build the Reviewer packet"); p.add_argument("card"); p.add_argument("record")
    p = sub.add_parser("verdict", help="merge reviewer JSON, compute state"); p.add_argument("card"); p.add_argument("reviewer_json")
    sub.add_parser("budget", help="GPU-h used and remaining"); sub.add_parser("views", help="render views/")
    a = ap.parse_args(argv)
    if a.cmd == "packet":
        print(write_packet(json.loads(Path(a.card).read_text()), json.loads(Path(a.record).read_text()))); return 0
    if a.cmd == "verdict":
        print(write_verdict(json.loads(Path(a.card).read_text()), json.loads(Path(a.reviewer_json).read_text()))); return 0
    if a.cmd == "budget":
        print(json.dumps(budget(load_goal()))); return 0
    if a.cmd == "views":
        render_views(load_goal()); print("views rendered"); return 0
    if a.cmd == "goal":
        print(json.dumps(load_goal(), indent=2)); return 0
    if a.cmd == "card":
        fails = check_card(json.loads(Path(a.card).read_text()), load_goal(), HERE)
        print("\n".join(fails) if fails else "PASS")
        return 1 if fails else 0
    if a.cmd == "critique":
        return record_critique(Path(a.card), Path(a.critique))
    if a.cmd == "freeze":
        return freeze_card(Path(a.card))
    if a.cmd == "record":
        rec = json.loads(Path(a.record).read_text()); card = json.loads(Path(a.card).read_text())
        fails = check_record(rec, card); write_type_a(card["id"], rec, fails)
        print("\n".join(fails) if fails else "PASS")
        return 1 if fails else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
