#!/usr/bin/env python3
"""render_record.py — per-seed result JSONs → records/<run>.json + .md. Never hand-edit a record.

Builder contract: results/<run>/seed_<k>.json =
  {"seed": k, "metric": str, "value": float,
   "canary": {"expected": float, "observed": float, "tol": float},
   "checkpoint_loaded_frac": float, "artifacts": ["<abs paths>"]}
Optional results/<run>/blockers.json = [{"severity": "high|medium", "text": "..."}]
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def cost_from_ledger(ledger: Path, run: str) -> float:
    secs = 0.0
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                if e.get("run") == run and e.get("event") == "stop":
                    secs += float(e.get("wall_s", 0))
    return round(secs / 3600.0, 3)


def render(run: str, card: dict, results_dir: Path, ledger: Path, rdir: Path) -> dict:
    seeds = sorted(results_dir.glob("seed_*.json"))
    rows = [json.loads(p.read_text()) for p in seeds]
    vals = [float(r["value"]) for r in rows]
    n = len(vals)
    mean = statistics.fmean(vals) if n else float("nan")
    if n >= 2:
        sd = statistics.stdev(vals); half = T95.get(n - 1, 1.96) * sd / math.sqrt(n)
        ci = [mean - half, mean + half]
    else:
        ci = [None, None]
    canary_rows = [r["canary"] for r in rows]
    canary_pass = bool(rows) and all(abs(c["observed"] - c["expected"]) <= c["tol"] for c in canary_rows)
    loaded = min((float(r.get("checkpoint_loaded_frac", 0)) for r in rows), default=0.0)
    direction = card["prediction"]["direction"]
    lo, hi = card["prediction"]["band"]
    thr = float(card["kill"]["threshold"])
    band_hit = n > 0 and (lo <= mean <= hi)
    kill_hit = n > 0 and ((mean < thr) if direction == "maximize" else (mean > thr))
    artifacts = []
    for r in rows:
        for a in r.get("artifacts", []):
            p = Path(a)
            artifacts.append({"path": str(p), "sha256": sha256(p) if p.exists() else None})
    blockers_p = results_dir / "blockers.json"
    blockers = json.loads(blockers_p.read_text()) if blockers_p.exists() else []
    rec = {
        "run": run, "card": card["id"], "claim_norm": _norm(card["claim"]),
        "metric": rows[0]["metric"] if rows else card["prediction"]["metric"],
        "seeds": [r["seed"] for r in rows], "per_seed": {str(r["seed"]): r["value"] for r in rows},
        "mean": mean, "ci95": ci, "n_realized": n,
        "canary": {"expected": canary_rows[0]["expected"] if rows else None,
                   "observed": [c["observed"] for c in canary_rows], "pass": canary_pass},
        "checkpoint_loaded_frac": loaded, "band_hit": band_hit, "kill_hit": kill_hit,
        "cost_gpu_h": cost_from_ledger(ledger, run), "artifacts": artifacts, "blockers": blockers,
        "early_kill": any(bool(r.get("early_kill")) for r in rows), "fraction": min((float(r.get("fraction") or 1.0) for r in rows), default=None),
        "rendered_by": f"render_record.py@{sha256(Path(__file__))[:12]}",
        "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    out = rdir / "records"; out.mkdir(parents=True, exist_ok=True)
    (out / f"{run}.json").write_text(json.dumps(rec, indent=2))
    md = [f"# Record {run} · card {card['id']}", "",
          f"metric: {rec['metric']} · n={n} · mean={mean:.4f} · ci95={ci} · cost={rec['cost_gpu_h']} GPU-h",
          f"band {card['prediction']['band']} hit={band_hit} · kill<{thr} hit={kill_hit} · canary pass={canary_pass} · ckpt loaded={loaded:.2f}", "",
          "| seed | value |", "|---|---|", *[f"| {r['seed']} | {r['value']} |" for r in rows], "",
          "## blockers", *([f"- [{b['severity']}] {b['text']}" for b in blockers] or ["- none"]), "",
          "## artifacts", *[f"- {a['path']} {a['sha256']}" for a in artifacts]]
    (out / f"{run}.md").write_text("\n".join(md) + "\n")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run"); ap.add_argument("card"); ap.add_argument("results_dir")
    ap.add_argument("--ledger", default=str(HERE / "ledger.jsonl"))
    a = ap.parse_args(argv)
    rec = render(a.run, json.loads(Path(a.card).read_text()), Path(a.results_dir), Path(a.ledger), HERE)
    print(json.dumps({k: rec[k] for k in ("run", "n_realized", "mean", "band_hit", "kill_hit", "cost_gpu_h")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
