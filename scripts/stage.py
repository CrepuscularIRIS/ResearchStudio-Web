#!/usr/bin/env python3
"""stage.py — read the file state, print the stage and, per chain, exactly ONE `step.py` action. Main never decides.

Stages: A frame · M mechanism map · R review (human) · C loop · P pivot · D write · STOP (identity mismatch).
Inside C every chain is a sub-state machine over files, but Main only ever sees one of:
  step.py propose <chain> [--rung R] · step.py propose --finish <Q> · step.py build <Q> [--fix] · step.py build --finish <Q> <out>
  step.py record <Q> · (wait, with the run's progress) · bundle.py queue <Q> "<why>"
Re-running is always safe: everything is recomputed from files.

Files (under .research/; Q = card id like Q-0001-alpha):
  mechanism-map.json                    A→B→M→C map with per-source status (open|tried|exhausted|dropped) — the hill-climb ledger
  bundles/spec-Q.json · gates/Q.spec.{ok,fail.json,retries}
  cards/Q.json (worktree set before freeze; frozen_sha after; phase search|support; source; rung)
  bundles/build-out-Q.json (the build workflow's returned JSON) · build/Q.json · build/Q.fixes · monitor/Q.json · tokens/Q.clean
  records/Q.json · notebook.json · queue.json · ledger.jsonl
  <worktree>/results/<run>/  run ∈ {Q, Q-confirm}; progress.json is the watchdog's and Main's window into a running unit
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
W = HERE.parent
YAML_BLOCK = re.compile(r"^```yaml\n(.*?)\n```", re.S | re.M)
WT_ROOT = Path("/tmp")


# ── state readers ───────────────────────────────────────────────────────────

def load_claim(w: Path = W) -> dict | None:
    p = w / "CLAIM.md"
    if not p.exists():
        return None
    m = YAML_BLOCK.search(p.read_text(encoding="utf-8"))
    if not m:
        return {"_error": "CLAIM.md has no ```yaml claim: block"}
    d = yaml.safe_load(m.group(1)) or {}
    return d.get("claim") or {"_error": "yaml block has no `claim:` key"}


def claim_sha(w: Path = W) -> str:
    return hashlib.sha256((w / "CLAIM.md").read_bytes()).hexdigest()


def accepted(w: Path = W, r: Path | None = None) -> bool:
    r = r or (w / ".research")
    f = r / "CLAIM.sha"
    return f.exists() and f.read_text().strip() == claim_sha(w)


def load_goal_repo(w: Path = W) -> Path:
    m = YAML_BLOCK.search((w / "GOAL.md").read_text(encoding="utf-8"))
    g = yaml.safe_load(m.group(1))["campaign"] if m else {}
    return w / str(g.get("repo_root", "."))


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _json_list(p: Path) -> list:
    try:
        v = json.loads(p.read_text())
        return v if isinstance(v, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def cards(r: Path) -> list[dict]:
    out = []
    for p in sorted((r / "cards").glob("Q-*.json")):
        c = _json(p)
        if c.get("id") and c.get("chain"):
            out.append(c)
    return out


def results_dir(card: dict, run: str) -> Path:
    return Path(card.get("worktree") or WT_ROOT / f"wt-{card['id']}") / "results" / run


def records(r: Path) -> list[dict]:
    """Records of THIS campaign only (cards with a chain); legacy C-* records never enter the board or budget."""
    out = []
    by_id = {c["id"]: c for c in cards(r)}
    for p in sorted((r / "records").glob("Q-*.json")):
        rec = _json(p)
        card = by_id.get(rec.get("card"))
        if not card or rec.get("run") != card["id"]:
            continue
        rec["_mtime"] = p.stat().st_mtime
        rec["_chain"] = card.get("chain"); rec["_network"] = card.get("network"); rec["_phase"] = card.get("phase", "search")
        rec["_source"] = card.get("source"); rec["_rung"] = card.get("rung")
        rec["_clean_cost"] = _clean_cost(card, rec)
        out.append(rec)
    return out


def _clean_cost(card: dict, rec: dict) -> float | None:
    vals = []
    for p in results_dir(card, str(rec.get("run", ""))).glob("seed_*.json"):
        v = _json(p).get("clean_cost")
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return max(vals) if vals else None


def valid(rec: dict, claim: dict) -> bool:
    if not (rec.get("canary") or {}).get("pass", False):
        return False
    cc = rec.get("_clean_cost")
    return cc is not None and cc <= float(claim.get("clean_cost_max", 0.2))


def keep_records(recs: list[dict], claim: dict) -> list[dict]:
    """KEEP = valid, band hit, enough seeds, CI95 excludes zero, not an early kill."""
    need = int(claim.get("seeds_for_keep", 3))
    out = []
    for x in recs:
        if not (valid(x, claim) and x.get("band_hit") and x["_phase"] == "search" and not x.get("early_kill")):
            continue
        if int(x.get("n_realized", 0)) < need:
            continue
        lo = (x.get("ci95") or [None, None])[0]
        if lo is None or float(lo) <= 0:
            continue
        out.append(x)
    return out


def best_gain(recs: list[dict], claim: dict) -> tuple[float | None, float | None]:
    v = [x for x in recs if valid(x, claim) and x["_phase"] == "search"]
    if not v:
        return None, None
    b = max(v, key=lambda x: float(x.get("mean", -1e9)))
    return float(b["mean"]), b["_mtime"]


def kill_threshold(recs: list[dict], claim: dict) -> float:
    best, _ = best_gain(recs, claim)
    floor = float(claim.get("kill_floor", 0.5))
    return floor if best is None else max(floor, best * float(claim.get("kill_frac_of_best", 0.5)))


def search_gpu_h(recs: list[dict]) -> float:
    return sum(float(x.get("cost_gpu_h", 0) or 0) for x in recs if x["_phase"] == "search")


def gpu_idle(threshold_mib: int = 2000) -> list[int]:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    idle = []
    for line in out.strip().splitlines():
        idx, used = [s.strip() for s in line.split(",")]
        if int(used) < threshold_mib:
            idle.append(int(idx))
    return idle


def unit_active(run: str) -> bool:
    try:
        return subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"research-{run}.service"], timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def queued(r: Path, qid: str) -> bool:
    return any(e.get("qid") == qid for e in _json_list(r / "queue.json"))


def progress_line(card: dict, run: str) -> str:
    p = results_dir(card, run) / "progress.json"
    d = _json(p)
    if not d:
        return "no progress.json yet" if not (results_dir(card, run) / "smoke").exists() else "smoke phase"
    return f"fraction {float(d.get('fraction') or 0):.2f} · dev_gain {d.get('dev_gain')} · clean_dev_cost {d.get('clean_dev_cost')} · loss {d.get('loss')}"


# ── the support ladder (after ONE model keeps: other networks / datasets / ablations, one at a time) ──

def support_rungs(claim: dict, r: Path) -> dict:
    """{kept: card id|None, rungs: [{id, kind, value, status: open|active|done|queued, card}]}; the ladder comes from CLAIM
    `support_ladder` when present, else one rung per other network in claim.networks plus one leave-one-condition-out ablation."""
    recs = records(r)
    keeps = keep_records(recs, claim)
    if not keeps:
        return {"kept": None, "rungs": []}
    best = max(keeps, key=lambda x: float(x.get("mean") or -1e9))
    kept_card = next((c for c in cards(r) if c["id"] == best["card"]), {})
    ladder = claim.get("support_ladder")
    if not ladder:
        ladder = [{"kind": "network", "value": n} for n in (claim.get("networks") or []) if n != kept_card.get("network")]
        ladder.append({"kind": "ablation", "value": "leave-one-training-condition-out over the kept spec's conditions"})
    rungs = []
    for i, rung in enumerate(ladder, 1):
        rid = f"R{i}"
        card = next((c for c in cards(r) if c.get("rung") == rid), None)
        status = "open"
        if card:
            status = "queued" if queued(r, card["id"]) else ("done" if (r / "records" / f"{card['id']}.json").exists() else "active")
        rungs.append({"id": rid, **rung, "status": status, "card": card["id"] if card else None})
    return {"kept": best["card"], "rungs": rungs}


# ── per-chain sub-state machine ─────────────────────────────────────────────

def chain_next(name: str, cfg: dict, claim: dict, r: Path, idle: list[int], active=unit_active) -> dict:
    """Return {state, qid, lines[]} — exactly one next action for this chain."""
    g = int(cfg.get("gpu", -1))
    mine = [c for c in cards(r) if c.get("chain") == name]
    L = mine[-1] if mine else None
    need = int(claim.get("seeds_for_keep", 3))
    baseline = cfg.get("mode") == "baseline" or "baseline" in str(cfg.get("seed_method", "")).lower()

    def new_candidate(reason: str) -> dict:
        q = f"Q-{len(mine) + 1:04d}-{name}"
        ladder = support_rungs(claim, r)
        rung = next((x for x in ladder["rungs"] if x["status"] == "open"), None) if ladder["kept"] and not baseline else None
        if ladder["kept"] and not baseline and not rung:
            return {"state": "ladder_done", "qid": q, "lines": [f"# chain {name}: KEEP exists and the support ladder is complete — nothing to propose"]}
        if not baseline and not ladder["kept"]:
            mp = _json(r / "mechanism-map.json")
            srcs = mp.get("sources") or []
            if srcs and not any(s.get("status") == "open" for s in srcs) and not any(s.get("status") == "tried" and int(s.get("no_improve") or 0) == 0 for s in srcs):
                return {"state": "sources_exhausted", "qid": q, "lines": [f"# chain {name}: every mechanism-map source is exhausted or dropped — the stop rule fires"]}
        spec = r / "bundles" / f"spec-{q}.json"
        fail = r / "gates" / f"{q}.spec.fail.json"
        retries = r / "gates" / f"{q}.spec.retries"
        if queued(r, q):
            return {"state": "queued", "qid": q, "lines": [f"# chain {name}: {q} is queued; owner decides (queue.json)"]}
        if fail.exists():
            if retries.exists():
                return {"state": "spec_failed", "qid": q, "lines": [f"python3 .research/bundle.py queue {q} \"spec failed the gate twice: {fail}\""]}
            return {"state": "spec_retry", "qid": q, "lines": [f"python3 .research/step.py propose {name} --retry"]}
        if spec.exists():
            return {"state": "spec_written", "qid": q, "lines": [f"python3 .research/step.py propose --finish {q}"]}
        rung_arg = f" --rung {rung['id']}" if rung else ""
        why = f"support rung {rung['id']} ({rung['kind']}: {rung['value']})" if rung else reason
        return {"state": "spec_pending", "qid": q, "lines": [f"# {why}", f"python3 .research/step.py propose {name}{rung_arg}"]}

    if L is None:
        return new_candidate(f"chain {name}: no candidates yet")
    q = L["id"]
    if queued(r, q):
        return new_candidate(f"chain {name}: {q} queued; next candidate")
    wt = Path(L.get("worktree") or WT_ROOT / f"wt-{q}")
    rec_p = r / "records" / f"{q}.json"
    if rec_p.exists():
        rec = _json(rec_p); rec["_mtime"] = rec_p.stat().st_mtime; rec["_chain"] = name; rec["_network"] = L.get("network"); rec["_phase"] = L.get("phase", "search")
        rec["_clean_cost"] = _clean_cost(L, rec)
        if valid(rec, claim) and rec.get("band_hit") and not rec.get("early_kill") and int(rec.get("n_realized", 0)) < need:
            conf = results_dir(L, f"{q}-confirm")
            if active(f"{q}-confirm"):
                return {"state": "confirm_running", "qid": q, "lines": [f"# chain {name}: research-{q}-confirm.service active — wait · {progress_line(L, f'{q}-confirm')}"]}
            if g not in idle and not any(conf.glob("seed_*.json")):
                return {"state": "confirm_wait_gpu", "qid": q, "lines": [f"# chain {name}: GPU {g} busy; confirm of {q} waits"]}
            return {"state": "confirm", "qid": q, "lines": [f"python3 .research/step.py record {q}   # band hit: re-renders with the confirm seeds, or launches SEEDS=1..{need - 1}"]}
        verdict = "early kill" if rec.get("early_kill") else ("KEEP" if rec.get("band_hit") and int(rec.get("n_realized", 0)) >= need else ("kill" if rec.get("kill_hit") else "below band"))
        return new_candidate(f"chain {name}: {q} recorded ({verdict}); next candidate")
    if active(q):
        return {"state": "running", "qid": q, "lines": [f"# chain {name}: research-{q}.service active — wait · {progress_line(L, q)}"]}
    if any(results_dir(L, q).glob("seed_*.json")):
        return {"state": "finished", "qid": q, "lines": [f"python3 .research/step.py record {q}"]}
    if (r / "tokens" / f"{q}.clean").exists():
        if g not in idle:
            return {"state": "launch_wait_gpu", "qid": q, "lines": [f"# chain {name}: GPU {g} busy; launch of {q} waits"]}
        return {"state": "launch", "qid": q, "lines": [f"python3 .research/step.py build --finish {q} .research/bundles/build-out-{q}.json   # token exists: (re)launch"]}
    out = r / "bundles" / f"build-out-{q}.json"
    mon = r / "monitor" / f"{q}.json"
    fixes = (r / "build" / f"{q}.fixes").exists()
    if out.exists() and (not mon.exists() or out.stat().st_mtime > mon.stat().st_mtime):
        return {"state": "build_out", "qid": q, "lines": [f"python3 .research/step.py build --finish {q} {out}"]}
    if mon.exists() and not _json(mon).get("approved"):
        if fixes:
            return {"state": "monitor_rejected_twice", "qid": q, "lines": [f"python3 .research/bundle.py queue {q} \"monitor rejected twice: {mon}\""]}
        return {"state": "monitor_rejected", "qid": q, "lines": [f"python3 .research/step.py build {q} --fix"]}
    if mon.exists() and _json(mon).get("approved"):
        return {"state": "approved", "qid": q, "lines": [f"python3 .research/step.py build --finish {q} {out}"]}
    if wt.exists():
        return {"state": "wt_ready", "qid": q, "lines": [f"python3 .research/step.py build {q}"]}
    return {"state": "card_pending", "qid": q, "lines": [f"python3 .research/step.py propose --finish {q}"]}


# ── stage decision ──────────────────────────────────────────────────────────

def decide(w: Path = W, r: Path | None = None, now: float | None = None, idle: list[int] | None = None, active=unit_active) -> dict:
    r = r or (w / ".research")
    now = now or time.time()
    if (r / "IDENTITY-MISMATCH").exists():
        return {"stage": "STOP", "reason": ".research/IDENTITY-MISMATCH exists: a lane ran on the wrong model", "next": ["fix the model pin, re-dispatch the probe, then delete .research/IDENTITY-MISMATCH"]}
    claim = load_claim(w)
    if claim is None:
        return {"stage": "A", "reason": "no CLAIM.md", "next": ["python3 .research/bundle.py A > .research/bundles/args-frame.json",
                 "Workflow(name='frame', args=<contents of args-frame.json>)   # scientist (Fable) writes CLAIM.md"]}
    if "_error" in claim:
        return {"stage": "A", "reason": claim["_error"], "next": ["fix CLAIM.md's yaml block (bundle.py A prints the template)"]}
    if not accepted(w, r):
        return {"stage": "R", "reason": "CLAIM.md not accepted (or edited since)", "next": ["human: python3 .research/stage.py accept"]}
    mp = _json(r / "mechanism-map.json")
    if not mp or mp.get("claim_sha") != claim_sha(w):
        return {"stage": "M", "reason": "no mechanism map for this claim (A→B→M→C; Sparking.md)", "next": ["python3 .research/step.py mechanism"]}
    open_sources = [s for s in mp.get("sources") or [] if s.get("status") == "open"]
    if not open_sources and not any(s.get("status") in ("tried", "exhausted") for s in mp.get("sources") or []):
        return {"stage": "R", "reason": "the mechanism map has no open source (all dropped: no recipe / precedent found) — owner reads .research/mechanism-map.json, then re-run step.py mechanism or edit CLAIM.md",
                "next": ["human: read .research/mechanism-map.json"]}
    recs = records(r)
    ladder = support_rungs(claim, r)
    if ladder["kept"] and all(x["status"] in ("done", "queued") for x in ladder["rungs"]):
        return {"stage": "D", "reason": f"KEEP {ladder['kept']} and the support ladder is complete ({len(ladder['rungs'])} rungs)",
                "next": ["python3 .research/bundle.py write > .research/bundles/args-write.json",
                         "Workflow(name='write', args=<contents of args-write.json>)   # writer (GLM) per section, polish (Fable), review (Grok)",
                         "python3 .research/gate.py numbers paper/merged/sections/05_method.tex paper/merged/sections/06_experiments.tex",
                         "cd paper/merged && latexmk -pdf main.tex"]}
    best, t_best = best_gain(recs, claim)
    clock_start = t_best if t_best else max((r / "CLAIM.sha").stat().st_mtime, (r / "mechanism-map.json").stat().st_mtime)
    hours = (now - clock_start) / 3600
    used = search_gpu_h(recs)
    srcs = mp.get("sources") or []
    exhausted = bool(srcs) and not ladder["kept"] and not open_sources and not any(s.get("status") == "tried" and int(s.get("no_improve") or 0) == 0 for s in srcs)
    if not ladder["kept"] and (hours >= float(claim.get("stop_hours_no_improve", 24)) or used >= float(claim.get("stop_search_gpu_h", 24)) or exhausted):
        why = "every mechanism-map source exhausted" if exhausted else f"no improvement for {hours:.1f} h (best {best}), search GPU-h {used:.1f}"
        return {"stage": "P", "reason": why,
                "next": ["python3 .research/bundle.py pivot > .research/bundles/args-pivot.json",
                         "Workflow(name='pivot', args=<contents of args-pivot.json>)   # explorer (K3) once",
                         "human: exit (a) ship the incumbent, (b) edit CLAIM.md and re-accept, or (c) step.py mechanism again with the pivot's associations"]}
    idle = gpu_idle() if idle is None else idle
    chains_out, lines = [], []
    for name, cfg in (claim.get("chains") or {}).items():
        st = chain_next(name, cfg, claim, r, idle, active)
        chains_out.append({"name": name, "gpu": cfg.get("gpu"), "qid": st["qid"], "state": st["state"]})
        lines += [f"# chain {name} · GPU {cfg.get('gpu')} · {st['qid']} · {st['state']}"] + st["lines"]
    return {"stage": "C", "chains": chains_out,
            "reason": f"best {best}, kill line {kill_threshold(recs, claim):.2f}, {hours:.1f} h since improvement, search GPU-h {used:.1f}, "
                      f"map sources open {len(open_sources)}/{len(srcs)}, idle GPUs {idle}" + (f", KEEP {ladder['kept']} → support ladder" if ladder["kept"] else ""),
            "next": lines}


def board(w: Path = W, r: Path | None = None) -> str:
    r = r or (w / ".research")
    claim = load_claim(w) or {}
    rows = ["| run | chain | phase | source | network | gain | clean_cost | n | band | kill | early | GPU-h | valid |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in sorted(records(r), key=lambda x: -float(x.get("mean", -1e9) or -1e9)):
        cc = x["_clean_cost"]
        rows.append(f"| {x.get('run')} | {x['_chain'] or '—'} | {x['_phase']} | {x['_source'] or '—'} | {x['_network'] or '—'} | {float(x.get('mean', 0)):.2f} | "
                    f"{'—' if cc is None else f'{cc:.2f}'} | {x.get('n_realized', 0)} | {'Y' if x.get('band_hit') else '·'} | {'Y' if x.get('kill_hit') else '·'} | "
                    f"{'Y' if x.get('early_kill') else '·'} | {float(x.get('cost_gpu_h', 0) or 0):.1f} | {'Y' if valid(x, claim) else '·'} |")
    return "\n".join(rows) if len(rows) > 2 else "(no records yet)"


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("accept", help="owner only: record CLAIM.md's sha as accepted")
    sub.add_parser("board", help="print the leaderboard")
    sub.add_parser("map", help="print the mechanism map's source statuses")
    sub.add_parser("json")
    a = ap.parse_args()
    if a.cmd == "accept":
        (HERE / "CLAIM.sha").write_text(claim_sha() + "\n"); print("accepted", claim_sha()[:12]); return 0
    if a.cmd == "board":
        print(board()); return 0
    if a.cmd == "map":
        mp = _json(HERE / "mechanism-map.json")
        for s in mp.get("sources") or []:
            print(f"{s['id']:4} {s.get('status', ''):10} best={s.get('best')} no_improve={s.get('no_improve')} tried={s.get('tried')}  {s.get('domain')} — {s.get('name')}"
                  + (f"  [{s.get('drop_reason')}]" if s.get("drop_reason") else ""))
        return 0
    d = decide()
    if a.cmd == "json":
        print(json.dumps(d, ensure_ascii=False)); return 0
    print(f"STAGE {d['stage']} — {d['reason']}")
    for line in d["next"]:
        print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
