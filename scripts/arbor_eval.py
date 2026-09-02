#!/usr/bin/env python3
"""arbor_eval.py — the one evaluation entry Arbor calls. Prints exactly one JSON line: {"score": <float>, ...}.

  --split dev   → scripts/eval_robust_suite.py (frozen robustness harness, env-driven) on the node's checkpoint;
                  score = mIoU of --condition (default: gaussian, the wrong-depth condition) in EVAL mode single.
  --split test  → scripts/p0_final_eval.py --tag <run> (held-out val, one evaluation per run, never re-spent);
                  score = final_eval.json["miou"].

Protected path: never edited by a Builder. A wrong score here corrupts every merge decision.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def suite_score(payload: dict, condition: str, mode: str = "single") -> float:
    """Extract results[mode][condition]['miou'] from eval_robust_suite output; fall back to any nested match."""
    res = payload.get("results") or {}
    try:
        return float(res[mode][condition]["miou"])
    except (KeyError, TypeError):
        pass
    for m, conds in res.items():
        if isinstance(conds, dict) and condition in conds and "miou" in conds[condition]:
            return float(conds[condition]["miou"])
    summ = (payload.get("summary") or {}).get(mode) or {}
    if f"{condition}_miou" in summ:
        return float(summ[f"{condition}_miou"])
    raise SystemExit(f"arbor_eval: no miou for condition={condition} mode={mode} in payload keys {list(payload)}")


def eval_dev(run: str, ckpt: str, condition: str, gpu: str) -> float:
    out_json = PROJECT / "results" / "arbor" / run / f"suite_{condition}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CKPT=ckpt, EVAL_MODES="single", EVAL_CONDITIONS=f"clean,{condition}",
               OUT_JSON=str(out_json), MODEL_TAG=run, CUDA_VISIBLE_DEVICES=gpu)
    subprocess.run([sys.executable, str(PROJECT / "scripts" / "eval_robust_suite.py")], env=env, check=True,
                   cwd=str(PROJECT / "repos" / "DFormer"))
    return suite_score(json.loads(out_json.read_text()), condition)


def eval_test(run: str, gpu: str) -> float:
    subprocess.run([sys.executable, str(PROJECT / "scripts" / "p0_final_eval.py"), "--tag", run, "--gpu", gpu],
                   check=True, cwd=str(PROJECT))
    rec = json.loads((PROJECT / "results" / "p0" / run / "final_eval.json").read_text())
    return float(rec["miou"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--ckpt", default=None, help="dev only; default experiments/<run>/latest.pth relative to repos/DFormer")
    ap.add_argument("--condition", default=os.environ.get("ARBOR_EVAL_CONDITION", "gaussian"))
    ap.add_argument("--gpu", default=os.environ.get("GPU", "1"))
    a = ap.parse_args(argv)
    if a.split == "dev":
        ckpt = a.ckpt or f"../../experiments/{a.run_name}/latest.pth"
        score = eval_dev(a.run_name, ckpt, a.condition, a.gpu)
        print(json.dumps({"score": score, "split": "dev", "condition": a.condition, "run": a.run_name}))
    else:
        score = eval_test(a.run_name, a.gpu)
        print(json.dumps({"score": score, "split": "test", "run": a.run_name}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
