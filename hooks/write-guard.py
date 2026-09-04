#!/usr/bin/env python3
"""PreToolUse (Write/Edit/NotebookEdit/Bash) inside a subagent: the state the loop treats as truth is never written by a lane.

Denied for any agent (agent_id set):
  - Write/Edit/NotebookEdit to CLAIM.md, GOAL.md, .research/{records,ledger.jsonl,notebook.json,verdicts,CLAIM.sha,FROZEN.sha,tokens,monitor,gates,queue.json},
    paper/neuro2col/, paper/icassp/, and GOAL.md's protected_paths (matched by prefix inside any worktree)
  - Bash that redirects/appends/copies/moves into those paths, or runs `stage.py accept` / `gate.py frozen --accept`
Main is never affected. Exit 2 = deny (exit 1 would fail OPEN).
"""
import json, os, re, sys
from pathlib import Path

W = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
GUARDED = ("CLAIM.md", "GOAL.md", ".research/records", ".research/ledger.jsonl", ".research/notebook.json", ".research/verdicts",
           ".research/CLAIM.sha", ".research/FROZEN.sha", ".research/tokens", ".research/monitor", ".research/gates", ".research/queue.json",
           ".research/mechanism-map.json", ".research/cards", ".research/build",
           ".research/paper-ledger.json", ".research/paper-journal.jsonl", ".research/critique",
           "paper/neuro2col", "paper/icassp")
OWNER_CMDS = re.compile(r"stage\.py\s+accept\b|gate\.py\s+frozen\s+--accept\b")
WRITE_VERB = re.compile(r"((?<![0-9&])>>?(?!&)|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i|\bperl\s+-i|\btruncate\b|\brm\b|\bln\b|open\([^)]*['\"][wa])")
TOKEN = re.compile(r"[^\s;&|'\"<>()]+")


def protected_paths(workspace: Path = W) -> list[str]:
    try:
        m = re.search(r"protected_paths:\s*\[(.*?)\]", (workspace / "GOAL.md").read_text(encoding="utf-8"))
    except OSError:
        return []
    return [s.strip().strip('"').rstrip("*/") for s in m.group(1).split(",")] if m else []


def _rel(p: str, workspace: Path = W) -> str:
    p = p.strip("`'\";,)")
    if not Path(p).is_absolute():
        return p.lstrip("./") if p.startswith("./") else p
    try:
        return str(Path(p).resolve().relative_to(workspace.resolve()))
    except (ValueError, OSError):
        return p


def guarded(path: str, protected: list[str], workspace: Path = W) -> str | None:
    rel = _rel(path, workspace)
    for g in GUARDED:
        if rel == g or rel.startswith(g + "/"):
            return g
    tail = re.sub(r"^.*?/wt-[^/]+/", "", path) if "/wt-" in path else rel
    for p in protected:
        if p and (tail == p or tail.startswith(p + "/") or tail.startswith(p)):
            return f"protected path {p}"
    return None


def decide(tool_name: str, tool_input: dict, protected: list[str], workspace: Path = W) -> str | None:
    if tool_name in ("Write", "Edit", "NotebookEdit"):
        target = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        g = guarded(target, protected, workspace)
        return f"WRITE DENIED: {target} is loop state ({g}); only scripts and the owner write it." if g else None
    if tool_name == "Bash":
        cmd = str(tool_input.get("command") or "")
        if OWNER_CMDS.search(cmd):
            return "DENIED: accept/freeze commands are the owner's; a lane never runs them."
        if WRITE_VERB.search(cmd):
            for tok in TOKEN.findall(cmd):
                if "/" not in tok and not tok.endswith((".md", ".json", ".jsonl", ".sha")):
                    continue
                g = guarded(tok, protected, workspace)
                if g:
                    return f"WRITE DENIED: shell write touching {tok} ({g})."
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if not data.get("agent_id"):
        sys.exit(0)
    why = decide(data.get("tool_name", ""), data.get("tool_input") or {}, protected_paths())
    if why:
        print(why, file=sys.stderr); sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
