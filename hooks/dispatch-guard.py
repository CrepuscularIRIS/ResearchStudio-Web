#!/usr/bin/env python3
"""PreToolUse (every tool): a subagent does only the task its brief names.

Three denials, each an exit code, not a sentence in a skill:
  1. BUDGET       — tool calls per dispatch are capped per lane; past the cap every tool is
                    denied with "write the report now".
  2. OUT OF BRIEF — reading a research document (.research/ plan/ .claude/ docs/ paper/ .grill/)
                    that the dispatch prompt or its brief file did not name is denied; the agent
                    returns NEEDS_CONTEXT naming the file instead of reading around. Code and
                    result directories are not restricted.
  3. SEARCH       — paper search, corpus lookup, WebSearch/WebFetch are denied unless the brief
                    is MODE SEARCH or SCOOP.
The main session is never affected: the hook acts only when the transcript is a subagent's.
Measured cause (2026-09-03): ~1 min per tool call on GLM; a dispatch that reads seven files
before working spends its first ten minutes on reading the harness told it to read.
"""
import json, os, re, sys
from pathlib import Path

W = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
BUDGET = {"builder": 80, "writer": 80, "researcher": 40, "scientist": 15, "reviewer": 12, "reader": 15, "explorer": 12, "critic-sol": 8, "critic-k3": 8, "critic-glm": 8, "searcher": 40, "verifier": 12}
DEFAULT_BUDGET = 40
DOC_DIRS = (".research/", "plan/", ".claude/", "docs/", "paper/", ".grill/")
LANES = "builder|writer|scientist|researcher|reviewer|reader|explorer|critic-sol|critic-k3|critic-glm|searcher|verifier"
SEARCH_RX = re.compile(r"search_papers\.py|corpus\.py|scoop-check|scoop_check", re.I)
READ_CMD = re.compile(r"^\s*(?:cat|head|tail|less|more|sed\s+-n|grep\b.*?-r?n?\s|python3?\s+-c\s+.*open\()", re.S)
PATH_RX = re.compile(r"(?:/home/\S+?|(?:\.research|plan|\.claude|docs|paper|\.grill)/\S+?)(?=[\s;,)\]\"'`]|$)")


def lane_of(prompt: str, agent_type: str | None = None) -> str | None:
    if agent_type:
        return agent_type
    m = re.search(rf"LANE:\s*({LANES})|briefs/({LANES})-", prompt)
    return next((g for g in m.groups() if g), None) if m else None


def first_prompt(transcript: Path) -> str:
    try:
        with transcript.open(errors="ignore") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") != "user":
                    continue
                c = d.get("message", {}).get("content")
                if isinstance(c, str):
                    return c
                if isinstance(c, list):
                    return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    except OSError:
        pass
    return ""


def count_calls(transcript: Path) -> int:
    try:
        return transcript.read_text(errors="ignore").count('"type":"tool_use"') + \
            transcript.read_text(errors="ignore").count('"type": "tool_use"')
    except OSError:
        return 0


def find_transcript(tp: str, agent_id: str) -> Path | None:
    """The docs give agent_id but do not say whose transcript transcript_path is. Resolve the
    subagent's own file: <session>/subagents/agent-<id>.jsonl next to whatever path we were given."""
    if not tp:
        return None
    p = Path(tp)
    if "/subagents/" in tp and p.exists():
        return p
    cand = p.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"   # parent transcript → its subagents dir
    if cand.exists():
        return cand
    hits = sorted(p.parent.glob(f"**/subagents/agent-{agent_id}.jsonl"))
    return hits[0] if hits else None


def _rel(p: str) -> str:
    p = p.strip("`'\";,)")
    if not Path(p).is_absolute():
        return p.lstrip("./") if p.startswith("./") else p
    try:
        return str(Path(p).resolve().relative_to(W.resolve()))
    except (ValueError, OSError):
        return p


def named_paths(prompt: str, workspace: Path = W) -> set[str]:
    """Paths the dispatch names, plus every path inside a BRIEF: file it names."""
    found = {_rel(p) for p in PATH_RX.findall(prompt)}
    found = {p for p in found if p.rstrip("/") + "/" not in DOC_DIRS}      # a bare `.research/` in an ISOLATION sentence names nothing
    for p in list(found):
        if "/briefs/" in p or p.startswith(".research/briefs/"):
            bp = workspace / p
            if bp.exists():
                found |= {_rel(q) for q in PATH_RX.findall(bp.read_text(errors="ignore"))}
    return found


def _allowed(rel: str, named: set[str]) -> bool:
    for n in named:
        n = n.rstrip("/")
        if rel == n or rel.startswith(n + "/") or n.endswith("/" + rel) or rel.endswith("/" + n):
            return True
        if any(ch in n for ch in "*<>") and re.fullmatch(re.escape(n).replace(r"\*", ".*").replace(r"<", ".").replace(r">", ".").replace(r"\.\.", ".*"), rel):
            return True
    return False


def decide(tool_name: str, tool_input: dict, prompt: str, n_calls: int, lane: str | None, named: set[str]) -> str | None:
    budget = BUDGET.get(lane or "", DEFAULT_BUDGET)
    if n_calls >= budget:
        return (f"BUDGET: {n_calls} tool calls used of {budget} for lane {lane or 'unknown'}. "
                f"Stop. Write the report to the path in your brief and return the status line now.")
    cmd = str(tool_input.get("command", "")) if tool_name == "Bash" else ""
    is_search_mode = re.search(r"MODE[:=]\s*(SEARCH|SCOOP)", prompt) is not None
    if not is_search_mode and (tool_name in ("WebSearch", "WebFetch") or (cmd and SEARCH_RX.search(cmd))):
        return ("SEARCH DENIED: this brief is not a SEARCH or SCOOP dispatch. If information is missing, "
                "return NEEDS_CONTEXT naming exactly what you need instead of searching for it.")
    targets: list[str] = []
    if tool_name == "Read":
        targets = [str(tool_input.get("file_path", ""))]
    elif tool_name == "Bash" and READ_CMD.match(cmd):
        targets = PATH_RX.findall(cmd)
    for t in targets:
        rel = _rel(t)
        if rel.startswith(DOC_DIRS) and not _allowed(rel, named):
            return (f"OUT OF BRIEF: {rel} is not named in your brief. Do not read around the gap — "
                    f"return NEEDS_CONTEXT naming this file and why you need it.")
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    agent_id = data.get("agent_id")
    if not agent_id:
        sys.exit(0)                                  # main session: never guarded (docs: agent_id only inside a subagent)
    transcript = find_transcript(data.get("transcript_path") or data.get("agent_transcript_path") or "", agent_id)
    if transcript is None:
        sys.exit(0)                                  # cannot see the dispatch: fail open, never block blind
    prompt = first_prompt(transcript)
    lane = lane_of(prompt, data.get("agent_type"))
    if lane not in BUDGET:
        sys.exit(0)                                  # not one of the loop's lanes (review/general agents): never guarded
    why = decide(data.get("tool_name", ""), data.get("tool_input") or {}, prompt,
                 count_calls(transcript), lane, named_paths(prompt))
    if why:
        print(why, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
