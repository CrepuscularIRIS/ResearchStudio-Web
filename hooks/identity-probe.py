#!/usr/bin/env python3
"""SubagentStop: the transcript's model must match the agent file; reports must open with METHOD:."""
import json, os, re, sys
from pathlib import Path

W = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
_CANDS = [W / ".claude" / "agents", Path(os.environ.get("CLAUDE_PLUGIN_ROOT", "/nonexistent")) / "agents", Path(__file__).resolve().parents[1] / "agents"]
AGENTS = next((c for c in _CANDS if c.is_dir()), _CANDS[0])
MODEL_RX = re.compile(r'"model"\s*:\s*"([^"]+)"')


def same_model(declared: str, reported: str) -> bool:
    """The transcript records the upstream provider's echoed model id, not the
    proxy alias: glm-5.3[1m] echoes glm-5.3; grok-4.6 echoes grok-4.6-build.
    Accept exact match, the alias without its [...] qualifier, and same-base
    variant suffixes; a different family never shares the base, so swaps still
    fail. Residual risk: a same-base tier variant (glm-5.3-flash) would pass."""
    base = re.sub(r"\[[^\]]*\]$", "", declared)
    return reported == declared or reported == base or reported.startswith(base + "-")


def probe(agent_type: str, transcript_text: str, last_msg: str, agents_dir: Path):
    af = agents_dir / f"{agent_type}.md"
    if not af.exists():
        return None
    front = af.read_text()
    m = re.search(r"^model:\s*(\S+)", front, re.M)
    expected = m.group(1) if m else None
    seen = MODEL_RX.search(transcript_text or "")
    if expected and seen and not same_model(expected, seen.group(1).strip()):
        return f"IDENTITY MISMATCH: agent {agent_type} declares model {expected} but ran as {seen.group(1)}; report discarded"
    msg = (last_msg or "").lstrip()
    json_report = msg.startswith("{") or "the JSON is the report" in front   # workflow lanes: schema output IS the report
    if "## REQUIRED READING" in front and not json_report and not msg.startswith("METHOD:"):
        return "REPORT REJECTED: first line must be `METHOD: <required files actually read>`; add it and return the status line"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    tp = data.get("agent_transcript_path")
    text = Path(tp).read_text(errors="ignore")[:200000] if tp and Path(tp).exists() else ""
    why = probe(data.get("agent_type", ""), text, data.get("last_assistant_message", ""), AGENTS)
    if why:
        if why.startswith("IDENTITY"):
            (W / ".research" / "IDENTITY-MISMATCH").write_text(why + "\n")
        print(why, file=sys.stderr); sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
