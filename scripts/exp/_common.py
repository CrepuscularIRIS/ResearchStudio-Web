"""Shared helpers for the experiment-side tools (main-window skills call these; no workflow, no dag)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent            # .research/tools/exp
RESEARCH = HERE.parents[1]                        # .research
WS = RESEARCH.parent                              # workspace
import os as _os
_SB = Path(_os.environ["EXP_SANDBOX"]) if _os.environ.get("EXP_SANDBOX") else None   # tests: redirect the three writable dirs
BUILD = (_SB / "build") if _SB else RESEARCH / "build"
EXPERIMENTS = (_SB / "experiments") if _SB else RESEARCH / "experiments"
FAILURES = (_SB / "failures") if _SB else RESEARCH / "failures"
INSTRUMENTS = (_SB / "instruments") if (_SB and (_SB / "instruments" / "README.md").exists()) else RESEARCH / "instruments"
LAUNCH_WRAP = RESEARCH / "tools" / "launch_wrap.sh"
REFS = HERE / "refs"
DECISION_FIELDS = ("block_id", "arms", "negctl_arm", "verdict_rule", "kill_condition", "forbids", "gates",
                   "run_cmd", "smoke_cmd", "outputs")
L4_CODES = {"A.5", "A.6", "D.4"}
FIX_CAP, REIMPL_CAP = 2, 1                        # V8 / ARIS budget: 2 patches + 1 clean reimplement


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def jload(p: Path | str, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def jsave(p: Path | str, obj) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def sha_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def sha_file(p: Path | str) -> str | None:
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except Exception:
        return None


def spec_sha(spec: dict) -> str:
    """sha over the DECISION-BEARING fields only (freeze.py idea): prose edits never change it."""
    return sha_json({k: spec.get(k) for k in DECISION_FIELDS})


def ledger_path(xid: str) -> Path:
    return EXPERIMENTS / f"{xid}.json"


def load_x(xid: str) -> dict:
    return jload(ledger_path(xid), {}) or {}


def save_x(xid: str, X: dict) -> None:
    X["updated_at"] = now()
    jsave(ledger_path(xid), X)


def next_xid() -> str:
    ids = [int(m.group(1)) for p in EXPERIMENTS.glob("X-*.json") if (m := re.match(r"X-(\d+)\.json$", p.name))]
    return "X-%03d" % ((max(ids) + 1) if ids else 1)


def arft_codes() -> set:
    p = REFS / "arft-codes.txt"
    return {l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")} if p.exists() else set()


def get_path(obj, dotted):
    cur = obj
    for k in str(dotted).split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def eval_rule(V: dict, keep_if_all: list):
    """V9 dag_verdict.eval_rule verbatim: missing key = fail; ops eq/gt/lt/lte/gte."""
    ok, reasons = True, []
    for cnd in keep_if_all or []:
        k, op, tv = cnd.get("key"), cnd.get("op"), cnd.get("value")
        v = get_path(V, k)
        if v is None:
            ok = False; reasons.append(f"missing_key:{k}"); continue
        try:
            good = {"eq": str(v) == str(tv), "gt": v > tv, "lt": v < tv, "lte": v <= tv, "gte": v >= tv}.get(op, False)
        except TypeError:
            good = False
        reasons.append(f"{k}={v} {op} {tv} {'✓' if good else '✗'}")
        ok &= bool(good)
    return ok, reasons


BRAIN_STALE_MIN = 45   # a Brain lock with no write under the root for this long is treated as dead (Opus seats think ≤ 8 min, Phase 0 ≤ 10 min)


def brain_lock_state(root: Path) -> dict:
    """Is a Brain workflow in flight on this root? lock file + heartbeat (newest mtime under the root, the lock excluded)."""
    import time
    lock = Path(root) / "brain.lock"
    if not lock.exists(): return {"locked": False, "fresh": False, "started_at": None, "quiet_min": None}
    newest = 0.0
    for p in Path(root).rglob("*"):
        if p.is_file() and p.name != "brain.lock":
            try: newest = max(newest, p.stat().st_mtime)
            except OSError: pass
    newest = max(newest, lock.stat().st_mtime)
    quiet = (time.time() - newest) / 60
    return {"locked": True, "fresh": quiet < BRAIN_STALE_MIN, "started_at": (jload(lock, {}) or {}).get("started_at"), "quiet_min": round(quiet, 1)}


def canary_env_from_readme() -> dict:
    txt = (INSTRUMENTS / "README.md").read_text(encoding="utf-8") if (INSTRUMENTS / "README.md").exists() else ""
    m = re.search(r"CANARY_EXPECTED=([0-9.]+) --setenv=CANARY_TOL=([0-9.]+)", txt)
    return {"CANARY_EXPECTED": m.group(1), "CANARY_TOL": m.group(2)} if m else {}
