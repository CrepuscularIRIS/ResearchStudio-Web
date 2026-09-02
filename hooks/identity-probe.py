#!/usr/bin/env python3
"""SubagentStop: the transcript's model must match the agent file; reports must open with METHOD:."""
import json, os, re, sys
from pathlib import Path

W = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
PLUGIN_AGENTS = Path(__file__).resolve().parents[1] / "agents"
PROJECT_AGENTS = W / ".claude" / "agents"
MODEL_RX = re.compile(r'"model"\s*:\s*"([^"]+)"')


def probe(agent_type: str, transcript_text: str, last_msg: str, agents_dir: Path):
    af = agents_dir / f"{agent_type}.md"
    if not af.exists():
        af = PLUGIN_AGENTS / f"{agent_type}.md"
    if not af.exists():
        return None
    front = af.read_text()
    m = re.search(r"^model:\s*(\S+)", front, re.M)
    expected = m.group(1) if m else None
    seen = MODEL_RX.search(transcript_text or "")
    if expected and seen and seen.group(1) != expected:
        return f"IDENTITY MISMATCH: agent {agent_type} declares model {expected} but ran as {seen.group(1)}; report discarded"
    if "## REQUIRED READING" in front and not (last_msg or "").lstrip().startswith("METHOD:"):
        return "REPORT REJECTED: first line must be `METHOD: <required files actually read>`; add it and return the status line"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    tp = data.get("agent_transcript_path")
    text = Path(tp).read_text(errors="ignore")[:200000] if tp and Path(tp).exists() else ""
    why = probe(data.get("agent_type", ""), text, data.get("last_assistant_message", ""), PROJECT_AGENTS)
    if why:
        if why.startswith("IDENTITY"):
            (W / ".research" / "IDENTITY-MISMATCH").write_text(why + "\n")
        print(why, file=sys.stderr); sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
