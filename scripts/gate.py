#!/usr/bin/env python3
"""gate.py — content gates over .research/ artifacts.

Subcommands: goal · screen · insight · graph · card · critique · freeze · record · packet ·
verdict · merge · budget · views. Every check reads artifacts on disk; nothing trusts a label.

Card schemas: 1 = v6 (bridge-based, in-flight cards keep it); 2 = minimal loop
(parent · mediator · conflicts · source_insights · cites; no bridge).
"""
from __future__ import annotations
import argparse, fnmatch, hashlib, json, math, re, subprocess, sys, time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent          # $W/.research
W = HERE.parent                                  # workspace root
sys.path.insert(0, str(HERE))
import gapmap  # noqa: E402

YAML_BLOCK = re.compile(r"^```yaml\n(.*?)\n```", re.S)

REQUIRED1 = ["id", "bridge", "claim", "mechanism", "forbids", "prediction", "kill", "controls",
             "seed_sd", "n_required", "mde", "instrument", "oracle", "tier", "cost_gpu_h"]
REQUIRED2 = [k for k in REQUIRED1 if k != "bridge"] + ["parent", "mediator", "conflicts", "source_insights", "cites", "source_lens"]
# schema 3 = a CANDIDATE in the method queue: one claim, one ceiling, one kill test, one keep rule.
# prediction.band is the KEEP zone, kill.threshold the kill line; render_record's band_hit/kill_hit apply unchanged.
REQUIRED3 = ["id", "schema", "parent", "claim", "method", "family", "ceiling", "prediction", "kill", "keep", "cost_gpu_h", "cites"]
FAMILIES = ["route", "repair", "train", "gate", "other"]
LENSES = ["gap", "anomaly", "bottleneck", "assumption-reversal", "cross-domain", "writing-to-think"]  # DeepScientist, imported 2026-09-02
MUTABLE = {"frozen_sha", "arbor_node", "critique_sha", "critique_path"}


# ── goal ────────────────────────────────────────────────────────────────────

def load_goal(workspace: Path = W) -> dict:
    text = (workspace / "GOAL.md").read_text(encoding="utf-8")
    m = YAML_BLOCK.search(text)
    if not m:
        raise SystemExit("GOAL.md has no leading ```yaml campaign block")
    return yaml.safe_load(m.group(1))


# ── search screen ───────────────────────────────────────────────────────────

def screen(manifest: list[dict], insight_dir: Path, min_score: int, max_n: int) -> list[dict]:
    """Mechanical selection for REVERSE: full text present, relevance >= min_score, not already
    reverse-engineered. Ranked by score then citations. No judgment lives here."""
    done = {p.stem for p in insight_dir.glob("*.md")}
    rows = [p for p in manifest if p.get("status") == "text" and int(p.get("relevance_score") or 0) >= min_score
            and p["id"] not in done]
    rows.sort(key=lambda p: (-int(p.get("relevance_score") or 0), -int(p.get("citation_count") or 0)))
    return rows[:max_n]


# ── card ────────────────────────────────────────────────────────────────────

def mde_lehr(seed_sd: float, n: int) -> float:
    """Lehr's rule: minimum detectable effect at 80% power, alpha 0.05, two arms of n seeds."""
    return 2.8 * float(seed_sd) * math.sqrt(2.0 / int(n))


def card_sha(card: dict) -> str:
    canon = {k: v for k, v in card.items() if k not in MUTABLE}
    return hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def card_schema(card: dict) -> int:
    return int(card.get("schema", 1))


def headline(card: dict) -> str:
    return str(card.get("claim") or card.get("method") or "")


# ── FROZEN block (GOAL.md `## FROZEN` … next `## `): the problem no lane may reopen ──────────

def frozen_text(workspace: Path = W) -> str | None:
    gp = workspace / "GOAL.md"
    if not gp.exists():
        return None
    text = gp.read_text(encoding="utf-8")
    m = re.search(r"^## FROZEN.*?(?=^## |\Z)", text, re.S | re.M)
    return m.group(0) if m else None


def frozen_sha(workspace: Path = W) -> str | None:
    t = frozen_text(workspace)
    return hashlib.sha256(t.encode()).hexdigest() if t else None


def frozen_check(workspace: Path = W, rdir: Path = HERE) -> list[str]:
    """Empty when GOAL has no FROZEN block, or its sha matches the accepted one."""
    sha = frozen_sha(workspace)
    if sha is None:
        return []
    acc = rdir / "FROZEN.sha"
    if not acc.exists():
        return ["GOAL.md has a FROZEN block that nobody accepted: owner runs `gate.py frozen --accept`"]
    if acc.read_text().strip() != sha:
        return ["GOAL.md FROZEN block changed since it was accepted; only the owner may re-run `gate.py frozen --accept`"]
    return []


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


def _cite_resolves(ref: str, rdir: Path) -> bool:
    if ref == "GOAL":
        return True
    return any(p.exists() for p in (rdir / "records" / f"{ref}.json", rdir / "cards" / f"{ref}.json",
                                    rdir / "insight" / f"{ref}.md"))


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


def _check_schema3(card: dict, goal: dict, rdir: Path) -> list[str]:
    fails = []
    if card["parent"] != "ROOT" and not (rdir / "cards" / f"{card['parent']}.json").exists():
        fails.append(f"parent {card['parent']} is not ROOT and no such card exists")
    if card["family"] not in FAMILIES:
        fails.append(f"family must be one of {FAMILIES}")
    ce = card["ceiling"]
    if not isinstance(ce, dict) or not str(ce.get("source", "")).strip():
        fails.append("ceiling must be {value: number|null, source: where that number was measured, or why unknown}")
    elif ce.get("value") is not None and not isinstance(ce["value"], (int, float)):
        fails.append("ceiling.value must be a number or null")
    kill = card["kill"]
    cap = float(goal["campaign"].get("kill_cap_gpu_h", 4))
    if not isinstance(kill.get("gpu_h"), (int, float)) or float(kill["gpu_h"]) > cap:
        fails.append(f"kill.gpu_h must be a number <= kill_cap_gpu_h {cap}")
    if not str(kill.get("cmd", "")).strip():
        fails.append("kill.cmd must name the command the Builder runs (the kill test is the whole build)")
    if not str(card["keep"].get("rule", "")).strip():
        fails.append("keep.rule must say what result makes this THE method")
    if not isinstance(card["cites"], list) or not card["cites"]:
        fails.append("cites must name >= 1 record, card, GOAL, or paper/ path")
    else:
        for ref in card["cites"]:
            r = str(ref)
            if not (_cite_resolves(r, rdir) or (r.startswith("paper/") and (W / r).exists())):
                fails.append(f"cites entry {ref} resolves to nothing on disk")
    if card.get("chain"):                                   # claim-loop card (WORKFLOW.md v2)
        if not str(card.get("worktree", "")).strip():
            fails.append("worktree must be set before freeze (bundle.py card does it)")
        claim = _claim_block(rdir.parent)
        nets = claim.get("networks") or []
        if nets and card.get("network") not in nets:
            fails.append(f"network {card.get('network')!r} not in claim.networks {nets}")
        fails += claim_check(rdir.parent, rdir)
    return fails


def _claim_block(workspace: Path) -> dict:
    p = workspace / "CLAIM.md"
    if not p.exists():
        return {}
    m = re.search(r"^```yaml\n(.*?)\n```", p.read_text(encoding="utf-8"), re.S | re.M)
    if not m:
        return {}
    try:
        return (yaml.safe_load(m.group(1)) or {}).get("claim") or {}
    except yaml.YAMLError:
        return {}


def claim_check(workspace: Path = W, rdir: Path = HERE) -> list[str]:
    """CLAIM.md must be accepted (sha recorded by the owner) and unchanged since."""
    p = workspace / "CLAIM.md"
    if not p.exists():
        return ["CLAIM.md missing"]
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    f = rdir / "CLAIM.sha"
    if not f.exists():
        return ["CLAIM.md not accepted: owner runs `stage.py accept`"]
    if f.read_text().strip() != sha:
        return ["CLAIM.md changed since it was accepted: owner re-runs `stage.py accept`"]
    return []


def _check_schema2_links(card: dict, rdir: Path) -> list[str]:
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
            if not _cite_resolves(str(ref), rdir):
                fails.append(f"cites entry {ref} resolves to nothing on disk")
    for k in ("mediator", "conflicts"):
        if not str(card.get(k, "")).strip():
            fails.append(f"{k} must be a non-empty string")
    if card["source_lens"] not in LENSES:
        fails.append(f"source_lens must be one of {LENSES}")
    return fails


def check_card(card: dict, goal: dict, rdir: Path) -> list[str]:
    schema = card_schema(card)
    required = REQUIRED3 if schema == 3 else REQUIRED2 if schema == 2 else REQUIRED1
    fails: list[str] = [f"missing field {k}" for k in required if k not in card]
    if fails:
        return fails
    fails += frozen_check(rdir.parent, rdir)
    kill = card["kill"]
    if not isinstance(kill.get("threshold"), (int, float)):
        fails.append("kill.threshold must be numeric")
    if card["prediction"].get("direction") not in ("maximize", "minimize"):
        fails.append("prediction.direction must be maximize|minimize")
    if schema == 3:
        band = card["prediction"].get("band") or [0, 0]
        if not (isinstance(band, list) and len(band) == 2 and all(isinstance(x, (int, float)) for x in band)):
            fails.append("prediction.band must be [keep_low, keep_high] numbers")
        fails += _check_schema3(card, goal, rdir)
        caps = goal["campaign"]["caps"]
        rem = remaining_gpu_h(goal, rdir / "ledger.jsonl")
        if float(card["cost_gpu_h"]) > rem * float(caps["single_run_frac"]):
            fails.append(f"budget: cost {card['cost_gpu_h']} > {caps['single_run_frac']} x remaining {rem:.1f} GPU-h")
        mine = _norm(headline(card))
        for p in (rdir / "cards").glob("*.json"):
            other = json.loads(p.read_text())
            if other.get("id") != card["id"] and _norm(headline(other)) == mine:
                fails.append(f"duplicate candidate of {other.get('id')}")
        return fails
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
    fails += _check_schema2_links(card, rdir) if card_schema(card) >= 2 else _check_schema1_links(card, rdir)
    mine = _norm(headline(card))
    for p in (rdir / "cards").glob("*.json"):
        other = json.loads(p.read_text())
        if other.get("id") != card["id"] and _norm(headline(other)) == mine:
            fails.append(f"duplicate claim of {other.get('id')}")
    for p in (rdir / "records").glob("*.json"):
        rec = json.loads(p.read_text())
        if rec.get("claim_norm") == mine and rec.get("card") != card["id"]:
            fails.append(f"claim already measured in {p.name}")   # a card's own oracle/full records are not duplicates
    return fails


def record_critique(card_path: Path, critique_path: Path) -> int:
    card = json.loads(card_path.read_text())
    card["critique_sha"] = card_sha(card)
    card["critique_path"] = str(critique_path)
    card_path.write_text(json.dumps(card, indent=2))
    return 0


def freeze_card(card_path: Path) -> int:
    card = json.loads(card_path.read_text())
    rdir = card_path.resolve().parents[1]              # cards/ → .research/
    fz = frozen_check(rdir.parent, rdir)
    if fz:
        print("REFUSED: " + fz[0], file=sys.stderr); return 1
    sha = card_sha(card)
    if card.get("critique_sha") and card["critique_sha"] != sha:
        print("REFUSED: card changed after the recorded critique; re-run critique first", file=sys.stderr)
        return 1
    card["frozen_sha"] = sha
    card_path.write_text(json.dumps(card, indent=2))
    print(sha)
    return 0


# ── record ──────────────────────────────────────────────────────────────────

def check_record(rec: dict, card: dict) -> list[str]:
    fails: list[str] = []
    need = int(card.get("n_required", 1))          # schema 3 kill tests run one seed
    if int(rec["n_realized"]) < need:
        fails.append(f"n_realized {rec['n_realized']} < n_required {need}")
    if not rec["canary"]["pass"]:
        fails.append("canary failed: instrument not validated")
    if float(rec["checkpoint_loaded_frac"]) < 0.9:
        fails.append(f"checkpoint_loaded_frac {rec['checkpoint_loaded_frac']} < 0.9")
    if rec["card"] != card["id"]:
        fails.append("record/card id mismatch")
    missing = [a["path"] for a in rec["artifacts"] if not a["sha256"]]
    if missing:
        fails.append(f"artifacts missing on disk: {missing}")
    if card.get("chain"):                                   # claim-loop record: launcher provenance
        fails += record_provenance(rec, card, HERE)
    return fails


def _ledger_windows(ledger: Path, runs: set[str]) -> list[tuple[float, float, int]]:
    out = []
    if not ledger.exists():
        return out
    from datetime import datetime
    for line in ledger.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("event") != "stop" or e.get("run") not in runs:
            continue
        try:
            stop = datetime.fromisoformat(e["t"]).timestamp()
        except (KeyError, ValueError):
            continue
        out.append((stop - float(e.get("wall_s", 0) or 0) - 120, stop + 120, int(e.get("exit", 1))))
    return out


def record_provenance(rec: dict, card: dict, rdir: Path = HERE) -> list[str]:
    """Every seed file must have been written by a launcher unit that exited 0; blockers.json must exist; metric must be the card's."""
    fails = []
    run = str(rec.get("run", ""))
    wt = Path(card.get("worktree") or "")
    rdir_results = wt / "results" / run
    if rec.get("metric") != card["prediction"]["metric"]:
        fails.append(f"metric {rec.get('metric')!r} is not the card's {card['prediction']['metric']!r} (observable mismatch)")
    windows = _ledger_windows(rdir / "ledger.jsonl", {run, f"{run}-confirm"})
    seeds = sorted(rdir_results.glob("seed_*.json")) if rdir_results.exists() else []
    if not seeds:
        fails.append(f"no seed files under {rdir_results}")
    for sp in seeds:
        m = sp.stat().st_mtime
        hit = [w for w in windows if w[0] <= m <= w[1]]
        if not hit:
            fails.append(f"{sp.name}: no launcher window covers its mtime (written outside run_protected.sh?)")
        elif all(w[2] not in (0, 4) for w in hit):
            fails.append(f"{sp.name}: the unit that wrote it exited non-zero (4 = early kill is allowed)")
        try:
            d = json.loads(sp.read_text())
        except json.JSONDecodeError:
            fails.append(f"{sp.name}: not JSON"); continue
        if not run.endswith("-smoke") and not isinstance(d.get("clean_cost"), (int, float)):
            fails.append(f"{sp.name}: clean_cost missing")
    if seeds and not run.endswith("-smoke") and not (rdir_results / "blockers.json").exists():
        fails.append("blockers.json missing: an empty list is a claim, a missing file is not")
    elif (rdir_results / "blockers.json").exists():
        try:
            bl = json.loads((rdir_results / "blockers.json").read_text())
        except json.JSONDecodeError:
            bl = []; fails.append("blockers.json: not JSON")
        for b in [x for x in bl if isinstance(x, dict) and str(x.get("severity", "")).lower() in ("high", "critical")][:3]:
            fails.append(f"high blocker written by the run itself: {str(b.get('text', ''))[:120]} — a named flaw is not a fixed one "
                         f"(ARFT rule 9): one fix round, or the owner lowers it in blockers.json by hand and says why in the spec")
    if seeds and not run.endswith("-confirm") and not (rdir_results / "progress.json").exists():
        fails.append("progress.json missing: the command never reported a checkpoint (the watchdog contract)")
    idx = sorted(int(re.sub(r"\D", "", sp.stem) or 0) for sp in seeds)
    if idx and idx != list(range(len(idx))):
        fails.append(f"seed indices not contiguous from 0: {idx} (a seed was dropped or chosen)")
    return fails


# ── spec gate (B1 completeness; WORKFLOW.md §5) ─────────────────────────────

STOP = {"the", "and", "with", "from", "never", "training", "condition", "class", "any", "map", "field", "random"}


def held_out_terms(claim: dict) -> list[str]:
    if claim.get("held_out_terms"):
        return [str(t).lower() for t in claim["held_out_terms"]]
    words = re.findall(r"[a-zA-Z]{7,}", str(claim.get("held_out", "")))
    return sorted({w.lower() for w in words if w.lower() not in STOP})


def _trunk_has(repo: Path, rel: str) -> bool:
    try:
        return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"research-trunk:{rel}"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return (repo / rel).exists()


def check_spec(spec: dict, claim: dict, repo: Path, cap_gpu_h: float) -> list[str]:
    fails = []
    steps = spec.get("steps") or []
    files = set(spec.get("files") or [])
    if len(steps) < 3:
        fails.append("steps: fewer than 3 (a name is not a procedure)")
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            fails.append(f"steps[{i}]: must be an object {{id, file, change}}"); continue
        f = str(st.get("file", "")).strip()
        if not f:
            fails.append(f"steps[{i}]: names no file")
        elif f not in files:
            fails.append(f"steps[{i}]: file {f!r} is not in spec.files")
        elif not st.get("new") and not _trunk_has(repo, f):
            fails.append(f"steps[{i}]: {f!r} does not exist on research-trunk (mark new: true if it is created)")
        if len(str(st.get("change", ""))) < 30:
            fails.append(f"steps[{i}]: change is too short to be a procedure")
    terms = held_out_terms(claim)
    for c in spec.get("conditions") or []:
        low = str(c).lower()
        bad = [t for t in terms if t in low]
        if bad:
            fails.append(f"condition {c!r} names the held-out class ({bad}); held-out never trains")
    nets = claim.get("networks") or []
    if nets and spec.get("network") not in nets:
        fails.append(f"network {spec.get('network')!r} not in claim.networks {nets}")
    gh = (spec.get("schedule") or {}).get("gpu_h")
    if not isinstance(gh, (int, float)) or float(gh) > cap_gpu_h:
        fails.append(f"schedule.gpu_h {gh!r} must be a number <= {cap_gpu_h}")
    cmd = str(spec.get("kill_cmd", ""))
    for tok in ("$RESULTS_DIR", "$SEED"):
        if tok not in cmd:
            fails.append(f"kill_cmd must honour {tok} (the launcher sets it)")
    ee = str(claim.get("eval_entry") or "").strip()
    if ee and ee not in cmd:
        fails.append(f"kill_cmd must score through the shared eval entrypoint {ee!r} (CLAIM eval_entry: every chain, one protocol — ARIS normalisation fraud)")
    if ee and any(str(st.get("file", "")).strip() == ee for st in steps if isinstance(st, dict)):
        fails.append(f"steps may not modify the shared eval entrypoint {ee!r}")
    can = spec.get("canary") or {}
    if not isinstance(can.get("expected"), (int, float)) or not isinstance(can.get("tol"), (int, float)) or float(can.get("tol", 0)) <= 0:
        fails.append("canary.expected and canary.tol must be numbers, tol > 0")
    for k in ("rationale_line", "naive_baseline"):
        if len(str(spec.get(k, "")).strip()) < 20:
            fails.append(f"{k}: one real sentence required (AAR one-line rationale / ResearchStudio naive baseline)")
    return fails


def spec_fingerprint(spec: dict) -> set[str]:
    """Token set of what the steps change (files + change text), for a cheap have-we-done-this check."""
    toks = set()
    for st in spec.get("steps") or []:
        if isinstance(st, dict):
            toks |= set(re.findall(r"[a-z0-9_]{4,}", (str(st.get("file", "")) + " " + str(st.get("change", ""))).lower()))
    return toks


def duplicate_of(spec: dict, rdir: Path = HERE, threshold: float = 0.8) -> str | None:
    """The first existing card whose spec fingerprint overlaps this one by Jaccard >= threshold (a re-run in disguise)."""
    fp = spec_fingerprint(spec)
    if not fp:
        return None
    for p in sorted((rdir / "cards").glob("Q-*.json")):
        try:
            other = json.loads(p.read_text()).get("spec") or {}
        except json.JSONDecodeError:
            continue
        ofp = spec_fingerprint(other)
        if ofp and len(fp & ofp) / len(fp | ofp) >= threshold:
            return p.stem
    return None


def gate_spec(qid: str, rdir: Path = HERE) -> int:
    spec_p = rdir / "bundles" / f"spec-{qid}.json"
    if not spec_p.exists():
        print(f"no spec at {spec_p}"); return 1
    claim = _claim_block(rdir.parent)
    goal = load_goal(rdir.parent)
    repo = rdir.parent / str(goal["campaign"].get("repo_root", "."))
    cap = float(claim.get("kill_gpu_h_cap", goal["campaign"].get("kill_cap_gpu_h", 4)))
    try:
        spec = json.loads(spec_p.read_text())
    except json.JSONDecodeError as e:
        spec, fails = {}, [f"spec is not JSON: {e}"]
    else:
        fails = check_spec(spec, claim, repo, cap)
        dup = duplicate_of(spec, rdir)
        if dup and dup != qid:
            fails.append(f"duplicate of {dup}: the steps are the same work as an existing card (have-we-done-this check)")
    (rdir / "gates").mkdir(exist_ok=True)
    ok, bad = rdir / "gates" / f"{qid}.spec.ok", rdir / "gates" / f"{qid}.spec.fail.json"
    if fails:
        bad.write_text(json.dumps({"qid": qid, "fails": fails}, indent=1, ensure_ascii=False))
        if ok.exists():
            ok.unlink()
        print("\n".join(fails)); return 1
    ok.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n")
    if bad.exists():
        bad.unlink()
    print("PASS"); return 0


# ── monitor gate (quotes must exist in the diff; every step covered) ───────

def check_monitor(out: dict, diff: str, steps: list[dict], truncated: bool) -> tuple[bool, list[str]]:
    reasons = []
    lines = {l.strip() for l in diff.splitlines() if l.strip()}

    def quoted(qs: list) -> list[str]:
        return [q for q in (qs or []) if str(q).strip() and str(q).strip() not in lines]

    grok = out.get("grok") or out
    cov = {str(c.get("step_id")): c for c in (grok.get("coverage") or []) if isinstance(c, dict)}
    for st in steps:
        sid = str(st.get("id"))
        c = cov.get(sid)
        if not c:
            reasons.append(f"step {sid}: no coverage entry"); continue
        if c.get("status") != "implemented":
            reasons.append(f"step {sid}: {c.get('status')}")
        bad = quoted(c.get("diff_lines"))
        if bad:
            reasons.append(f"step {sid}: quoted lines not in the diff: {bad[:2]}")
        if not (c.get("diff_lines") or []):
            reasons.append(f"step {sid}: no diff lines quoted (cannot quote = did not read)")
    for f in grok.get("findings") or []:
        bad = quoted(f.get("diff_lines"))
        if bad:
            reasons.append(f"finding {f.get('kind')}: quoted lines not in the diff: {bad[:2]} (finding discarded)")
            continue
        reasons.append(f"finding {f.get('kind')}: {str(f.get('text', ''))[:160]}")
    if truncated:
        reasons.append("diff was truncated in the bundle: never approve what was not fully read")
    if not grok.get("approved"):
        reasons.append("monitor lens did not approve")
    codex = out.get("codex") or {}
    if codex.get("available"):
        for f in codex.get("findings") or []:
            if re.match(r"^(P1|critical|high)$", str(f.get("severity", "")), re.I):
                reasons.append(f"codex {f.get('severity')}: {f.get('file')}:{f.get('line')} {str(f.get('text', ''))[:120]}")
    return (len(reasons) == 0), reasons


def diff_of(worktree: str) -> tuple[str, str]:
    """THE diff the monitor, the token and the launcher all hash. `git add -N` (intent-to-add) first, so a NEW file the
    builder created is in it — plain `git diff` never shows untracked files (AAR: the approved code must be the launched code).
    .gitignore still applies (results/, logs/ stay out)."""
    subprocess.run(["git", "-C", worktree, "add", "-N", "-A"], capture_output=True)
    diff = subprocess.run(["git", "-C", worktree, "diff", "research-trunk"], capture_output=True, text=True).stdout
    return diff, hashlib.sha256(diff.encode()).hexdigest()


def gate_monitor(qid: str, out_path: Path, rdir: Path = HERE) -> int:
    card = json.loads((rdir / "cards" / f"{qid}.json").read_text())
    out = json.loads(Path(out_path).read_text())
    wt = card["worktree"]
    diff, sha = diff_of(wt)
    truncated = bool(out.get("diff_truncated")) or len(diff) > 200_000
    approved, reasons = check_monitor(out, diff, card["spec"].get("steps", []), truncated)
    ee = str((_claim_block() or {}).get("eval_entry") or "").strip()
    if ee and re.search(r"^diff --git a/" + re.escape(ee) + r"\b", diff, re.M):
        approved = False; reasons.append(f"the diff modifies the shared eval entrypoint {ee} (CLAIM eval_entry): the scoring protocol is not a candidate's to change")
    (rdir / "monitor").mkdir(exist_ok=True)
    (rdir / "monitor" / f"{qid}.json").write_text(json.dumps({"qid": qid, "approved": approved, "diff_sha": sha, "reasons": reasons,
                                                              "findings": (out.get("grok") or out).get("findings", []), "codex": out.get("codex"),
                                                              "t": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1, ensure_ascii=False))
    print(("APPROVED" if approved else "REJECTED") + ("\n" + "\n".join(reasons) if reasons else ""))
    return 0 if approved else 1


# ── numbers gate (every number in a section cites a record that contains it) ─

def retracted(rdir: Path = HERE) -> list[str]:
    """Literals the manuscript may never contain: one per line in .research/retracted.txt (project-owned)."""
    p = rdir / "retracted.txt"
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []
NUM = re.compile(r"(?<![\w.])[-−+]?\d+\.\d+(?![\w.])")


def check_numbers(tex: str, rdir: Path = HERE) -> list[str]:
    fails = []
    for i, line in enumerate(tex.splitlines(), 1):
        body = line.split("%")[0]
        if "\\begin" in body or "\\label" in body or "\\ref" in body:
            continue
        nums = NUM.findall(body)
        if not nums:
            continue
        m = re.search(r"%\s*src:\s*(\S+)", line)
        if not m:
            fails.append(f"line {i}: numbers {nums} without `% src: <record>`"); continue
        src = m.group(1)
        rp = (rdir.parent / src) if not src.startswith("/") else Path(src)
        if not rp.exists():
            rp2 = rdir / "records" / Path(src).name
            rp = rp2 if rp2.exists() else rp
        if not rp.exists():
            fails.append(f"line {i}: src {src} not found"); continue
        text = rp.read_text(errors="ignore")
        toks = {float(t) for t in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", text.replace("−", "-"))}
        for n in nums:
            v = n.replace("−", "-").lstrip("+")
            try:
                fv = float(v)
            except ValueError:
                fails.append(f"line {i}: {n} is not a number"); continue
            # numeric-token equality (ARIS evidence-precheck): 73.2 matches 73.20 and never a digit-substring of 173.25
            if not any(abs(fv - t) < 1e-9 or abs(abs(fv) - t) < 1e-9 for t in toks):
                fails.append(f"line {i}: {n} is not a number token in {src}")
    for bad in retracted(rdir):
        if bad in tex:
            fails.append(f"retracted literal {bad!r} appears (paper/.claude/CLAUDE.md forbids it)")
    return fails


def write_type_a(card_id: str, rec: dict, fails: list[str]) -> Path:
    vdir = HERE / "verdicts"; vdir.mkdir(exist_ok=True)
    vp = vdir / f"{card_id}.json"
    v = json.loads(vp.read_text()) if vp.exists() else {"card": card_id}
    v["type_a"] = {"pass": not fails, "checks": fails, "band_hit": rec["band_hit"],
                   "kill_hit": rec["kill_hit"], "blockers": rec.get("blockers", []), "record": rec["run"]}
    vp.write_text(json.dumps(v, indent=2))
    return vp


# ── verdict, packet, merge ──────────────────────────────────────────────────

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
    role = (HERE / "templates" / "role-prompt.md").read_text()
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


def merge(card_id: str, branch: str, test_record: Path, dry_run: bool) -> int:
    goal = load_goal(); c = goal["campaign"]
    repo = W / c["repo_root"]; trunk = c.get("trunk_branch", "research-trunk")
    card = json.loads((HERE / "cards" / f"{card_id}.json").read_text())
    vp = HERE / "verdicts" / f"{card_id}.json"
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


# ── budget, views ───────────────────────────────────────────────────────────

def budget(goal: dict) -> dict:
    ledger = HERE / "ledger.jsonl"
    return {"ceiling": goal["campaign"]["gpu_h_ceiling"], "used": round(ledger_used_gpu_h(ledger), 2),
            "remaining_spendable": round(remaining_gpu_h(goal, ledger), 2)}


def graveyard(cards: dict, verdicts: dict) -> list[str]:
    return [f"{cid}: {headline(cards[cid])[:120]}" for cid, v in sorted(verdicts.items())
            if v.get("state") == "REFUTED" and cid in cards]


def render_tree(cards: dict, verdicts: dict) -> str:
    def state(cid):
        c = cards[cid]
        return verdicts.get(cid, {}).get("state", "LIVE" if c.get("frozen_sha") else "DRAFT")
    kids: dict[str, list] = {}
    for cid, c in cards.items():
        kids.setdefault(c.get("parent", "ROOT"), []).append(cid)
    lines = ["# Hypothesis tree", "", "ROOT"]

    def walk(pid, depth):
        for cid in sorted(kids.get(pid, [])):
            lines.append(f"{'  ' * depth}- {cid} [{state(cid)}] {headline(cards[cid])[:100]}")
            walk(cid, depth + 1)
    walk("ROOT", 1)
    dead = graveyard(cards, verdicts)
    lines += ["", "## Graveyard", ""] + ([f"- {d}" for d in dead] or ["- none"])
    return "\n".join(lines) + "\n"


def render_views(goal: dict) -> None:
    vdir = HERE / "views"; vdir.mkdir(exist_ok=True)
    cards = {p.stem: json.loads(p.read_text()) for p in (HERE / "cards").glob("*.json")}
    verdicts = {p.stem: json.loads(p.read_text()) for p in (HERE / "verdicts").glob("*.json")}
    records = [json.loads(p.read_text()) for p in (HERE / "records").glob("*.json")]
    rows = ["| card | schema | parent | lens | state | claim | n_req | mde | cost |", "|---|---|---|---|---|---|---|---|---|"]
    for cid, c in sorted(cards.items()):
        st = verdicts.get(cid, {}).get("state", "LIVE" if c.get("frozen_sha") else "DRAFT")
        rows.append(f"| {cid} | {card_schema(c)} | {c.get('parent', '—')} | {c.get('source_lens', c.get('family', '—'))} | {st} | "
                    f"{headline(c)[:80]} | {c.get('n_required', 1)} | {c.get('mde', '—')} | {c['cost_gpu_h']} |")
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
    (vdir / "TREE.md").write_text(render_tree(cards, verdicts))


def render_gapmap() -> Path:
    idir = HERE / "insight"; idir.mkdir(exist_ok=True)
    cards = {p.stem: json.loads(p.read_text()) for p in (HERE / "cards").glob("*.json")}
    verdicts = {p.stem: json.loads(p.read_text()) for p in (HERE / "verdicts").glob("*.json")}
    icards = gapmap.load_cards(idir)
    g = gapmap.build(icards)
    out = HERE / "views" / "GAPMAP.md"; out.parent.mkdir(exist_ok=True)
    out.write_text(gapmap.render(g, icards, graveyard(cards, verdicts)))
    dp = idir / "DROPPED.json"
    dropped = json.loads(dp.read_text()) if dp.exists() else {}
    (idir / "CANDIDATES.json").write_text(json.dumps(gapmap.candidates(g, dropped), indent=1, ensure_ascii=False))
    return out


# ── cli ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("goal", help="print the parsed campaign block")
    p = sub.add_parser("frozen", help="sha of GOAL's FROZEN block; --accept records it (owner only)")
    p.add_argument("--accept", action="store_true")
    p = sub.add_parser("screen", help="select papers for REVERSE from a search manifest")
    p.add_argument("manifest"); p.add_argument("--cycle", required=True)
    p.add_argument("--min-score", type=int); p.add_argument("--max", type=int)
    p = sub.add_parser("insight", help="form checks on an insight card"); p.add_argument("file")
    sub.add_parser("graph", help="render views/GAPMAP.md from insight front-matter")
    p = sub.add_parser("card", help="content checks on a card"); p.add_argument("card")
    p = sub.add_parser("critique", help="record a critique sha on a card"); p.add_argument("card"); p.add_argument("critique")
    p = sub.add_parser("freeze", help="freeze a card (writes frozen_sha)"); p.add_argument("card")
    p = sub.add_parser("record", help="type-A checks on a rendered record"); p.add_argument("record"); p.add_argument("card")
    p = sub.add_parser("packet", help="build the Reviewer packet"); p.add_argument("card"); p.add_argument("record")
    p = sub.add_parser("verdict", help="merge reviewer JSON, compute state"); p.add_argument("card"); p.add_argument("reviewer_json")
    p = sub.add_parser("merge", help="held-out merge guard, then git merge")
    p.add_argument("card_id"); p.add_argument("branch"); p.add_argument("--test-record", required=True)
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("budget", help="GPU-h used and remaining"); sub.add_parser("views", help="render views/")
    p = sub.add_parser("spec", help="B1 completeness gate on bundles/spec-<qid>.json"); p.add_argument("qid")
    p = sub.add_parser("monitor", help="verify the monitor workflow's output against the worktree diff"); p.add_argument("qid"); p.add_argument("out")
    p = sub.add_parser("numbers", help="every number in the .tex files cites a record that contains it"); p.add_argument("tex", nargs="+")
    p = sub.add_parser("diffsha", help="sha of the worktree diff the monitor approved (intent-to-add included); the launcher compares it to the token"); p.add_argument("worktree")
    a = ap.parse_args(argv)
    if a.cmd == "spec":
        return gate_spec(a.qid)
    if a.cmd == "monitor":
        return gate_monitor(a.qid, Path(a.out))
    if a.cmd == "diffsha":
        print(diff_of(a.worktree)[1]); return 0
    if a.cmd == "numbers":
        fails = []
        for t in a.tex:
            fails += [f"{t}: {f}" for f in check_numbers(Path(t).read_text(encoding="utf-8"))]
        print("\n".join(fails) if fails else "PASS"); return 1 if fails else 0
    if a.cmd == "goal":
        print(json.dumps(load_goal(), indent=2)); return 0
    if a.cmd == "frozen":
        sha = frozen_sha()
        if sha is None:
            print("GOAL.md has no ## FROZEN block"); return 1
        if a.accept:
            (HERE / "FROZEN.sha").write_text(sha + "\n"); print(f"accepted {sha[:12]}"); return 0
        fz = frozen_check()
        print(f"{sha[:12]} " + ("ACCEPTED" if not fz else "NOT ACCEPTED: " + fz[0])); return 1 if fz else 0
    if a.cmd == "screen":
        s = load_goal()["campaign"].get("search", {})
        rows = screen(json.loads(Path(a.manifest).read_text()), HERE / "insight",
                      a.min_score if a.min_score is not None else int(s.get("min_score", 2)),
                      a.max if a.max is not None else int(s.get("batch", 100)))
        out = HERE / "insight" / f"QUEUE-{a.cycle}.json"; out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(rows, indent=1))
        print(f"{len(rows)} papers queued → {out}"); return 0
    if a.cmd == "insight":
        text = Path(a.file).read_text(encoding="utf-8")
        paper_text = None
        try:
            pid = str(gapmap.split(text)[0].get("paper", ""))
            pt = HERE / "lit" / "papers" / f"{pid}.txt"
            paper_text = pt.read_text(errors="ignore") if pt.exists() else None
        except ValueError:
            pass
        fails = gapmap.check_insight(text, paper_text)
        if paper_text is None:
            print("note: no lit/papers/<paper>.txt found; line refs not verified")
        print("\n".join(fails) if fails else "PASS"); return 1 if fails else 0
    if a.cmd == "graph":
        print(render_gapmap()); return 0
    if a.cmd == "card":
        fails = check_card(json.loads(Path(a.card).read_text()), load_goal(), HERE)
        print("\n".join(fails) if fails else "PASS"); return 1 if fails else 0
    if a.cmd == "critique":
        return record_critique(Path(a.card), Path(a.critique))
    if a.cmd == "freeze":
        return freeze_card(Path(a.card))
    if a.cmd == "record":
        rec = json.loads(Path(a.record).read_text()); card = json.loads(Path(a.card).read_text())
        fails = check_record(rec, card); write_type_a(card["id"], rec, fails)
        print("\n".join(fails) if fails else "PASS"); return 1 if fails else 0
    if a.cmd == "packet":
        print(write_packet(json.loads(Path(a.card).read_text()), json.loads(Path(a.record).read_text()))); return 0
    if a.cmd == "verdict":
        print(write_verdict(json.loads(Path(a.card).read_text()), json.loads(Path(a.reviewer_json).read_text()))); return 0
    if a.cmd == "merge":
        return merge(a.card_id, a.branch, Path(a.test_record), a.dry_run)
    if a.cmd == "budget":
        print(json.dumps(budget(load_goal()))); return 0
    if a.cmd == "views":
        render_views(load_goal()); print("views rendered"); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
