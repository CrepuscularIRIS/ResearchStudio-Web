#!/usr/bin/env python3
"""brain_lock.py <run_root> acquire|release|status — never launch two Brain workflows on one root.
acquire: exit 3 (and launch nothing) while a fresh lock exists — fresh = some file under the root was written in the last 45 min; a
stale lock is the previous launch that died: it is replaced and the workflow resumes from the artifacts on disk. release: delete the lock.
/exp-auto wraps the Workflow call in acquire … release; next.py turns a fresh lock into WAIT.
"""
import json, os, socket, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brain_lock_state, jsave, now, BRAIN_STALE_MIN


def main() -> int:
    if len(sys.argv) < 3: print(__doc__); return 2
    root, op = Path(sys.argv[1]).resolve(), sys.argv[2]
    st = brain_lock_state(root)
    if op == "status": print(json.dumps(st, indent=1)); return 0
    if op == "release":
        (root / "brain.lock").unlink(missing_ok=True); print(f"released {root / 'brain.lock'}"); return 0
    if op == "acquire":
        if st["locked"] and st["fresh"]:
            print(f"IN_FLIGHT: Brain running on {root} since {st['started_at']} (last write {st['quiet_min']} min ago) — not launching a second one"); return 3
        if st["locked"]: print(f"stale lock from {st['started_at']} ({st['quiet_min']} min without writes, threshold {BRAIN_STALE_MIN}) — replaced; the workflow resumes from disk")
        jsave(root / "brain.lock", {"started_at": now(), "pid": os.getpid(), "host": socket.gethostname()})
        print(f"acquired {root / 'brain.lock'}"); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
