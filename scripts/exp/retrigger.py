#!/usr/bin/env python3
"""retrigger.py <run_root> — the deterministic Brain re-trigger next.py emits when every candidate run of a root is dead. Idempotent.
Creates <base>-n<round+1>/ (base = the root without its -n<k> suffix), reuses _shared/ (intake + Phase 0, copied), writes args.json =
the old args + brain_round + negative_anchors (every failure card of this root plus the ones it inherited) + parent_root, and writes
<run_root>/retrigger.json so next.py follows the lineage. Never re-triggers past args.max_brain_rounds (exit 3): Brain runs cost quota.
"""
import json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import jload, jsave, now
from next import cards_for, DEFAULT_BRAIN_ROUNDS

EXP = ".research/tools/exp"


def main() -> int:
    if len(sys.argv) < 2: print(__doc__); return 2
    root = Path(sys.argv[1]).resolve()
    ptr = jload(root / "retrigger.json", {}) or {}
    if ptr.get("next_root"): print(json.dumps({"already": ptr, "next": f"python3 {EXP}/next.py {root}"}, indent=1)); return 0
    args = jload(root / "args.json", {}) or {}
    rnd, cap = int(args.get("brain_round") or 1), int(args.get("max_brain_rounds") or DEFAULT_BRAIN_ROUNDS)
    if rnd >= cap: print(f"BLOCKED: brain_round {rnd} >= max_brain_rounds {cap} — raise it in {root / 'args.json'} or change the goal"); return 3
    cards = sorted(set(list(args.get("negative_anchors") or []) + cards_for(root)))
    if not cards: print("BLOCKED: no failure card on this root — nothing to anchor a re-trigger on"); return 3
    base = re.sub(r"-n\d+$", "", str(root)); new = Path(f"{base}-n{rnd + 1}")
    new.mkdir(parents=True, exist_ok=True)
    if (root / "_shared").exists() and not (new / "_shared").exists():
        shutil.copytree(root / "_shared", new / "_shared", symlinks=True, ignore=shutil.ignore_patterns("*.pid", "*.lock"))
    jsave(new / "args.json", dict(args, root=str(new), brain_round=rnd + 1, negative_anchors=cards, parent_root=str(root)))
    jsave(root / "retrigger.json", {"next_root": str(new), "round": rnd + 1, "cards": cards, "at": now()})
    print(json.dumps({"new_root": str(new), "round": rnd + 1, "negative_anchors": cards, "shared_reused": (new / "_shared").exists(),
                      "next": f"python3 {EXP}/next.py {root}  (follows retrigger.json → BRAIN in the new root)"}, indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
