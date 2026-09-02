#!/usr/bin/env python3
"""SessionStart: single-writer lock. `--check <pid>` verifies the caller descends from the lock holder."""
import json, os, sys, time
from pathlib import Path

W = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
LOCK = W / ".research" / "LOCK"


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False


def acquire(lock: Path, session_id: str, pid: int) -> str:
    if lock.exists():
        cur = json.loads(lock.read_text())
        if alive(int(cur["pid"])) and int(cur["pid"]) != pid:
            return "read-only"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"session_id": session_id, "pid": pid, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    return "acquired"


def ancestors(pid: int):
    while pid > 1:
        yield pid
        try:
            pid = int(open(f"/proc/{pid}/stat").read().split(")")[-1].split()[1])
        except OSError:
            return


def claude_pid() -> int:
    for pid in ancestors(os.getpid()):
        try:
            if "claude" in open(f"/proc/{pid}/comm").read():
                return pid
        except OSError:
            pass
    return os.getppid()


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        holder = int(json.loads(LOCK.read_text())["pid"]) if LOCK.exists() else None
        ok = holder is None or not alive(holder) or holder in set(ancestors(int(sys.argv[2])))
        print("lock ok" if ok else f"REFUSED: another session ({holder}) holds .research/LOCK", file=sys.stderr)
        sys.exit(0 if ok else 1)
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        data = {}
    state = acquire(LOCK, data.get("session_id", "unknown"), claude_pid())
    if state == "read-only":
        print("READ-ONLY SESSION: another live session holds .research/LOCK; do not write the tree, cards, or launch.")
    sys.exit(0)


if __name__ == "__main__":
    main()
