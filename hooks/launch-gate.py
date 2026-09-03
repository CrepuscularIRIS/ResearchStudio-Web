#!/usr/bin/env python3
"""PreToolUse on Bash: GPU work starts only through bin/run_protected.sh."""
import json, re, sys

EXEC_POS = r"(?:^\s*|[;&|(]\s*)"
BANNED = [(re.compile(EXEC_POS + r"nohup\b", re.M), "bare nohup"),
          (re.compile(EXEC_POS + r"systemd-run\b", re.M), "bare systemd-run")]
GPU_PY = re.compile(r"(CUDA_VISIBLE_DEVICES=|\btorchrun\b|--gpu\b).*\bpython[0-9.]*\b|\bpython[0-9.]*\b.*(--gpu\b|\btorchrun\b)")


def decide(command: str):
    if "bin/run_protected.sh" in command:
        return None
    for rx, why in BANNED:
        if rx.search(command):
            return f"BLOCKED (launch gate): {why} is forbidden; use GPU=<n> bin/run_protected.sh <run> <card> <mem>G <cmd>"
    if GPU_PY.search(command):
        return "BLOCKED (launch gate): GPU python outside the launcher; use bin/run_protected.sh"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    why = decide((data.get("tool_input") or {}).get("command") or "")
    if why:
        print(why, file=sys.stderr); sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
