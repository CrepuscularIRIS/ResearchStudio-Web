import pathlib, re
W = pathlib.Path(__file__).resolve().parents[1]
A = W / "agents"
LANES = {"builder": "glm-5.3[1m]", "scientist": "claude-fable-5-1", "explorer": "k3-256k",
         "researcher": "grok-4.6", "reviewer": "glm-5.3[1m]", "writer": "glm-5.3[1m]"}

def test_agent_files():
    for lane, model in LANES.items():
        t = (A / f"{lane}.md").read_text()
        assert re.search(rf"^model:\s*{re.escape(model)}\s*$", t, re.M), lane
        assert "arbor" not in t.lower(), f"{lane}: Arbor was removed on 2026-09-02"
        assert "## REQUIRED READING" in t and "METHOD:" in t and "## NEVER" in t, lane
        for p in re.findall(r"^- (/home/\S+)", t, re.M):
            assert pathlib.Path(p).exists(), f"{lane}: missing {p}"

def test_writing_lanes_can_write_their_artifacts():
    for lane in ("scientist", "writer"):        # explorer/reader are out of the loop; explorer returns JSON via schema
        assert re.search(r"^tools:.*\bWrite\b", (A / f"{lane}.md").read_text(), re.M), lane
