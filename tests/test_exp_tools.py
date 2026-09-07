"""Experiment-side tools (.research/tools/exp): precheck → build → critic/anchor_check → launch → verdict → route — scripts only, no model."""
from __future__ import annotations

import json, time
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WS = Path(__file__).resolve().parents[2]
EXP = WS / ".research" / "tools" / "exp"
GOLD = Path(__file__).resolve().parent / "golden_exp"
sys.path.insert(0, str(EXP))
import _common  # noqa: E402

X011_VERDICT = GOLD / "x011_smoke_verdict.json"          # the real X-011 smoke output (m158), copied verbatim so the suite runs in any copy of the harness


def run(*args, env=None, cwd=None):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env={**os.environ, **(env or {})}, cwd=cwd, timeout=120)


run_ = run


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Redirect BUILD / EXPERIMENTS / FAILURES into tmp so the real ledger is untouched."""
    for name in ("BUILD", "EXPERIMENTS", "FAILURES"):
        (tmp_path / name.lower()).mkdir()
    env = {"EXP_SANDBOX": str(tmp_path)}
    # the tools honour EXP_SANDBOX by re-pointing the three dirs (see _common)
    return tmp_path, env


def canary_readme(tmp_path: Path) -> None:
    """The sandbox carries its own instruments/README.md (same canary line as the real one), so precheck never reads the workspace."""
    (tmp_path / "instruments").mkdir(exist_ok=True)
    (tmp_path / "instruments" / "README.md").write_text("Env flags: `--setenv=CANARY_EXPECTED=49.11 --setenv=CANARY_TOL=0.1`.\n")


def make_run_root(tmp_path: Path) -> Path:
    canary_readme(tmp_path)
    root = tmp_path / "run_root"; rd = root / "r1"; (rd / "spec").mkdir(parents=True); (rd / "phase5").mkdir(); (rd / "phase4").mkdir()
    json.dump({"ranking": [{"run": "r1", "rank": 1, "first_block_to_run": "B1"}]}, open(root / "ranking.json", "w"))
    json.dump({"run_order": ["B1"], "total_gpu_h": 4.0, "blocks": [{"block_id": "B1", "min_effect": 0.05, "role": "anchor", "failure_interpretation": "mechanism absent"}]}, open(rd / "phase5" / "evidence_plan.json", "w"))
    json.dump({"underspecified_points": []}, open(rd / "phase4" / "phase4_implementability.json", "w"))
    json.dump({"blocks": ["B1"], "run_order": ["B1"], "first_block": "B1"}, open(rd / "spec" / "index.json", "w"))
    spec = json.load(open(GOLD / "spec_B1.json")); json.dump(spec, open(rd / "spec" / "B1.json", "w"))
    repo = tmp_path / "repo"; (repo / "scripts").mkdir(parents=True); (repo / "scripts" / "train.py").write_text("#"); (repo / "README.md").write_text("#")
    return root


def test_precheck_claims_block_and_seals_spec(tmp_path):
    root = make_run_root(tmp_path)
    r = run(sys.executable, EXP / "precheck.py", root, "--repo", tmp_path / "repo", "--x", "X-900", env={"EXP_SANDBOX": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout[r.stdout.index("{"):])
    assert out["x_id"] == "X-900" and out["block"] == "B1" and out["spec_sha"] and out["next"].startswith("/exp-critic X-900 spec")
    bd = tmp_path / "build" / "X-900"
    assert (bd / "spec.json").exists() and (bd / "spec.sha").read_text().strip() == out["spec_sha"] and (bd / "progress.md").exists()
    assert (tmp_path / "experiments" / "X-900.json").exists()
    assert out["canary"].get("CANARY_EXPECTED") == "49.11"   # parsed from instruments/README.md (the sandbox copy), never typed


def test_precheck_rejects_budget_and_blocked(tmp_path):
    root = make_run_root(tmp_path)
    spec = json.load(open(root / "r1" / "spec" / "B1.json")); spec["gpu_h"] = 99; json.dump(spec, open(root / "r1" / "spec" / "B1.json", "w"))
    r = run(sys.executable, EXP / "precheck.py", root, "--repo", tmp_path / "repo", env={"EXP_SANDBOX": str(tmp_path)})
    assert r.returncode == 1 and "budget" in r.stdout
    spec["gpu_h"] = 1; spec["blocked"] = "no launcher in the repo"; json.dump(spec, open(root / "r1" / "spec" / "B1.json", "w"))
    r = run(sys.executable, EXP / "precheck.py", root, "--repo", tmp_path / "repo", env={"EXP_SANDBOX": str(tmp_path)})
    assert r.returncode == 3 and "BLOCKED by Brain" in r.stdout


def _build_dir(tmp_path: Path, xid: str, diff: str, blockers="[]", self_check=None) -> Path:
    bd = tmp_path / "build" / xid; bd.mkdir(parents=True, exist_ok=True)
    spec = json.load(open(GOLD / "spec_B1.json")); json.dump(spec, open(bd / "spec.json", "w"))
    (bd / "spec.sha").write_text(_common.spec_sha(spec) + "\n"); (bd / "diff.patch").write_text(diff); (bd / "blockers.json").write_text(blockers)
    json.dump(self_check or [{"check": "fake_gt", "result": "0", "pass": True}], open(bd / "self_check.json", "w"))
    (bd / "canary.env").write_text("CANARY_EXPECTED=49.11\nCANARY_TOL=0.1\n")
    json.dump({"id": xid, "status": "gate_passed", "min_effect": 0.05, "worktree": str(tmp_path / "wt")}, open(tmp_path / "experiments" / f"{xid}.json", "w"))
    return bd


def test_launch_blocks_on_forbidden_patterns_and_dry_runs(tmp_path):
    (tmp_path / "experiments").mkdir(); env = {"EXP_SANDBOX": str(tmp_path), "DRY_RUN": "1"}
    bd = _build_dir(tmp_path, "X-901", "+++ b/scripts/new_gate.py\n+import torch\n+x = 1\n")
    r = run("bash", EXP / "launch.sh", "X-901", tmp_path / "wt", "1", env=env)
    assert r.returncode == 0 and "systemd-run --user --unit=research-X-901" in r.stdout and "CANARY_EXPECTED=49.11" in r.stdout and "SEEDS='0,1,2'" in r.stdout, r.stdout + r.stderr
    _build_dir(tmp_path, "X-902", "+++ b/scripts/new_gate.py\n+split = load('test_half')\n")
    r = run("bash", EXP / "launch.sh", "X-902", tmp_path / "wt", "1", env=env)
    assert r.returncode == 2 and "test_half=1" in r.stdout
    _build_dir(tmp_path, "X-903", "+++ b/scripts/new_gate.py\n+ok\n", blockers='[{"text": "eval reads labels twice", "resolution": ""}]')
    r = run("bash", EXP / "launch.sh", "X-903", tmp_path / "wt", "1", env=env)
    assert r.returncode == 2 and "unresolved blockers" in r.stdout


def _verdict_case(tmp_path: Path, xid: str, exit_code: int, m158: dict | None, keep=None):
    bd = _build_dir(tmp_path, xid, "+ok\n"); (bd / "exit_code").write_text(str(exit_code))
    if keep is not None:
        spec = json.load(open(bd / "spec.json")); spec["verdict_rule"]["keep_if_all"] = keep; json.dump(spec, open(bd / "spec.json", "w")); (bd / "spec.sha").write_text(_common.spec_sha(spec) + "\n")
    if m158 is not None:
        (bd / "results").mkdir(parents=True, exist_ok=True); json.dump(m158, open(bd / "results" / "verdict.json", "w"))   # where spec.gates expect it
    r = run(sys.executable, EXP / "verdict.py", xid, env={"EXP_SANDBOX": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def test_verdict_gate_three_states(tmp_path):
    (tmp_path / "experiments").mkdir()
    real = json.load(open(X011_VERDICT))          # X-011's real m158 output: negctrl_delta 0.1029 ≈ delta 0.1030
    assert _verdict_case(tmp_path, "X-910", 3, None)["gate"] == "invalid"
    assert _verdict_case(tmp_path, "X-911", 5, None)["gate"] == "infra"
    assert _verdict_case(tmp_path, "X-912", 4, None)["reasons"][-1] == "watchdog_early_kill"
    v = _verdict_case(tmp_path, "X-913", 0, real, keep=[{"key": "n_frames", "op": "gt", "value": 1}])
    assert v["gate"] == "killed" and v["l3_hint"] is True and any(r.startswith("negctl_matched") for r in v["reasons"]), v["reasons"]
    good = dict(real); good.update({"delta": 0.12, "ci_lo": 0.02, "ci_hi": 0.2, "negctrl_delta": 0.01, "both_rungs_exclude_zero": True})
    v = _verdict_case(tmp_path, "X-914", 0, good, keep=[{"key": "both_rungs_exclude_zero", "op": "eq", "value": True}, {"key": "delta", "op": "gt", "value": 0.05}])
    assert v["gate"] == "survived", v["reasons"]
    v = _verdict_case(tmp_path, "X-915", 0, dict(good, delta=0.9), keep=[{"key": "delta", "op": "gt", "value": 0.05}])
    assert v["gate"] == "killed" and any(r.startswith("too_good") for r in v["reasons"])
    last = _verdict_case(tmp_path, "X-916", 0, None)["reasons"][-1]
    assert last == "no_verdict" or last.startswith("gate_failed")   # the ASI gates run before the verdict search


def _findings(tmp_path: Path, xid: str, mode: str, F):
    d = tmp_path / "build" / xid / "findings"; d.mkdir(parents=True, exist_ok=True); json.dump(F, open(d / f"{mode}.json", "w"))
    r = run(sys.executable, EXP / "anchor_check.py", xid, "--mode", mode, env={"EXP_SANDBOX": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def test_anchor_check_routes(tmp_path):
    (tmp_path / "experiments").mkdir()
    real = json.load(open(X011_VERDICT)); good = dict(real); good.update({"delta": 0.12, "ci_lo": 0.02, "ci_hi": 0.2, "negctrl_delta": 0.01, "both_rungs_exclude_zero": True})
    _verdict_case(tmp_path, "X-920", 0, good, keep=[{"key": "delta", "op": "gt", "value": 0.05}])
    base = {"x_id": "X-920", "verdict_agree": True, "failure_level": None, "credit_due": ["ran"], "anomalies": []}
    # 1 anchored blocking finding (spec.json exists, line 1) → killed L2
    r = _findings(tmp_path, "X-920", "process", dict(base, findings=[{"anchor": "spec.json:1", "class": "C.3", "blocking": True, "note": "impl differs"}]))
    assert r["outcome"] == "killed" and r["failure_level"] == "L2"
    # 2 unanchored blocking → advisory → survived
    r = _findings(tmp_path, "X-920", "process", dict(base, findings=[{"anchor": "nowhere.py:9", "class": "C.3", "blocking": True, "note": "x"}]))
    assert r["outcome"] == "survived" and r["blocking"] == []
    # 3 L4 code without a second vote → needs_second_vote
    r = _findings(tmp_path, "X-920", "process", dict(base, failure_level="L4", findings=[{"anchor": "spec.json:1", "class": "A.6", "blocking": True, "note": "does not test the hypothesis"}]))
    assert r["outcome"] == "needs_second_vote"
    # 4 critic failed → pending_rejudge
    r = _findings(tmp_path, "X-920", "process", {"status": "critic_failed", "reason": "timeout"})
    assert r["outcome"] == "pending_rejudge"
    # 5 code mode: blocked twice then reimplement then escalate
    outs = [_findings(tmp_path, "X-920", "code", dict(base, findings=[{"anchor": "spec.json:1", "class": "C.3", "blocking": True, "note": "bug"}]))["next"] for _ in range(4)]
    assert "patch 1/2" in outs[0] and "patch 2/2" in outs[1] and "reimplement" in outs[2] and "Brain" in outs[3]
    # 6 spec mode pass
    assert _findings(tmp_path, "X-920", "spec", dict(base, findings=[]))["next"] == "/exp-build X-920"


def test_critic_dry_run_and_failure_card(tmp_path):
    (tmp_path / "experiments").mkdir(); env = {"EXP_SANDBOX": str(tmp_path)}
    real = json.load(open(X011_VERDICT))
    _verdict_case(tmp_path, "X-930", 0, real, keep=[{"key": "n_frames", "op": "gt", "value": 1}])   # killed L3 (negctl)
    r = run(sys.executable, EXP / "critic.py", "X-930", "--mode", "process", "--dry-run", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout); assert "--permission-mode" in out["cmd"] and "plan" in out["cmd"]
    prompt = Path(out["prompt"]).read_text()
    assert "MODE: process" in prompt and "You are an experiment integrity auditor" in prompt and "Follow code evolution" in prompt and "MODE: code" not in prompt
    req = json.load(open(tmp_path / "build" / "X-930" / "findings" / "process.request.json")); assert any(p.endswith("verdict.json") for p in req["paths"])
    _findings(tmp_path, "X-930", "process", {"x_id": "X-930", "verdict_agree": True, "failure_level": None, "credit_due": ["ran"], "anomalies": [], "findings": []})
    r = run(sys.executable, EXP / "failure_card.py", "X-930", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    card = json.load(open(tmp_path / "failures" / "X-930.json")); assert card["level"] == "L3" and card["numbers"]["delta"] is not None
    assert (tmp_path / "failures" / "X-930.md").exists()


def test_critic_md_is_assembled_from_sources():
    before = (EXP / "critic.md").read_bytes()
    r = run(sys.executable, EXP / "build_critic_md.py"); assert r.returncode == 0, r.stderr
    assert (EXP / "critic.md").read_bytes() == before, "critic.md drifted from its sources — re-run build_critic_md.py"
    md = (EXP / "critic.md").read_text()
    for must in ("## MODE: spec", "## MODE: code", "## MODE: process", "## Output contract", "Self-reported scores are never trusted", "be disarmed", "### A. Ground Truth Provenance", "difficulty ladder"):
        assert must in md, must


def test_skills_exist_and_point_at_the_scripts():
    for name in ("exp-next", "exp-build", "exp-critic", "exp-launch", "exp-verdict", "exp-handoff"):
        p = WS / ".claude" / "skills" / name / "SKILL.md"; t = p.read_text()
        assert t.startswith("---\nname: " + name), name
    assert "precheck.py" in (WS / ".claude/skills/exp-next/SKILL.md").read_text() and "launch.sh" in (WS / ".claude/skills/exp-launch/SKILL.md").read_text()
    assert "verdict.py" in (WS / ".claude/skills/exp-verdict/SKILL.md").read_text() and "anchor_check.py" in (WS / ".claude/skills/exp-critic/SKILL.md").read_text()


def _nav(root: Path, env):
    r = run(sys.executable, EXP / "next.py", root, "--json", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def _set(tmp_path: Path, xid: str, **kw):
    p = tmp_path / "experiments" / f"{xid}.json"; d = json.load(open(p)); d.update(kw); json.dump(d, open(p, "w"))


def test_navigator_state_machine(tmp_path):
    root = make_run_root(tmp_path); env = {"EXP_SANDBOX": str(tmp_path)}
    json.dump({"root": str(root), "repo": str(tmp_path / "repo"), "goal": "FROZEN test goal", "k": 1}, open(root / "args.json", "w"))
    # BRAIN phase: hide the spec index
    (root / "r1" / "spec" / "index.json").rename(root / "r1" / "spec" / "index.bak")
    d = _nav(root, env); assert d["phase"] == "BRAIN" and d["skill"] == "brain" and any("brain.workflow.js" in c for c in d["run"])
    json.dump({"root": str(root), "repo": str(tmp_path / "repo"), "goal": "<paste the ## FROZEN block here>", "k": 1}, open(root / "args.json", "w"))
    d = _nav(root, env); assert d["phase"] == "BRAIN" and d["blocked"] and "FROZEN" in d["note"]          # placeholder goal never launches the Brain
    json.dump({"root": str(root), "repo": str(tmp_path / "repo"), "goal": "FROZEN test goal", "k": 1}, open(root / "args.json", "w"))
    # a Brain already in flight on this root: lock + heartbeat → WAIT, never a second launch; a stale lock resumes
    r = run(sys.executable, EXP / "brain_lock.py", root, "acquire", env=env); assert r.returncode == 0 and "acquired" in r.stdout, r.stdout
    r = run(sys.executable, EXP / "brain_lock.py", root, "acquire", env=env); assert r.returncode == 3 and "IN_FLIGHT" in r.stdout, r.stdout
    d = _nav(root, env); assert d["phase"] == "BRAIN" and d["wait_s"] == 900 and "in flight" in d["state"] and not d["run"], d
    old = time.time() - 3600
    for p in root.rglob("*"):
        if p.is_file(): os.utime(p, (old, old))
    d = _nav(root, env); assert d["phase"] == "BRAIN" and d["wait_s"] == 0 and "stale brain.lock" in d["note"] and "acquire" in d["run"][0] and "release" in d["run"][-1], d
    r = run(sys.executable, EXP / "brain_lock.py", root, "acquire", env=env); assert r.returncode == 0 and "stale" in r.stdout, r.stdout
    r = run(sys.executable, EXP / "brain_lock.py", root, "release", env=env); assert r.returncode == 0 and not (root / "brain.lock").exists()
    json.dump({"root": str(root), "repo": str(tmp_path / "repo"), "goal": "FROZEN test goal", "k": 1}, open(root / "args.json", "w"))
    (root / "r1" / "spec" / "index.bak").rename(root / "r1" / "spec" / "index.json")
    # no ledger → claim the first block
    d = _nav(root, env); assert d["skill"] == "exp-next" and "--block B1" in d["skill_args"]
    r = run(sys.executable, EXP / "precheck.py", root, "--repo", tmp_path / "repo", "--x", "X-950", env=env); assert r.returncode == 0, r.stdout
    seq = []
    d = _nav(root, env); seq.append((d["skill"], d["skill_args"])); assert d["skill"] == "exp-critic" and d["skill_args"] == "X-950 spec"
    _set(tmp_path, "X-950", spec_review="pass"); d = _nav(root, env); assert d["skill"] == "exp-build" and d["skill_args"] == "X-950 fresh"
    bd = tmp_path / "build" / "X-950"; (bd / "gate_passed").write_text("")
    d = _nav(root, env); assert d["skill"] == "exp-critic" and d["skill_args"] == "X-950 code"
    _set(tmp_path, "X-950", code_review="blocked", status="fix_needed"); (bd / "gate_passed").unlink()
    d = _nav(root, env); assert d["skill"] == "exp-build" and d["skill_args"] == "X-950 fix"
    (bd / "gate_passed").write_text(""); _set(tmp_path, "X-950", code_review="pass", status="precheck", worktree="/tmp/wt-X-950")
    d = _nav(root, env); assert d["skill"] == "exp-launch" and d["skill_args"] == "X-950 /tmp/wt-X-950"
    _set(tmp_path, "X-950", status="launched", unit="research-X-950")
    d = _nav(root, env); assert d["wait_s"] > 0 or d["skill"] == "exp-verdict"      # no real unit here: either WAIT (systemctl absent) or verdict
    (bd / "exit_code").write_text("0"); d = _nav(root, env); assert d["skill"] == "exp-verdict"
    _set(tmp_path, "X-950", status="judged", gate="killed"); d = _nav(root, env); assert d["skill_args"] == "X-950 process"
    _set(tmp_path, "X-950", status="fix_needed", failure_level="L1"); d = _nav(root, env); assert d["skill_args"] == "X-950 fix"
    _set(tmp_path, "X-950", status="killed", failure_level="L3"); d = _nav(root, env); assert "failure_card.py X-950" in d["run"][0]
    r = run(sys.executable, EXP / "failure_card.py", "X-950", env=env); assert r.returncode == 0, r.stdout + r.stderr
    d = _nav(root, env); assert d["phase"] == "BRAIN" and "retrigger.py" in d["run"][0] and not d["blocked"], d   # k=1: no backup run → re-trigger
    _set(tmp_path, "X-950", status="survived"); d = _nav(root, env); assert d["phase"] == "SUPPORTED" and "report.py" in d["run"][0]
    r = run(sys.executable, EXP / "report.py", root, env=env); assert r.returncode == 0, r.stdout + r.stderr
    t = (root / "results_table.md").read_text(); assert "Claim-Evidence Matrix" in t and "No-Fabrication Reminder" in t and "X-950" in t
    # pending_rejudge twice → blocked
    _set(tmp_path, "X-950", status="pending_rejudge", rejudge_count=2); d = _nav(root, env); assert d["blocked"]


def test_navigator_card_ladder(tmp_path):
    """dead rank-1 run → backup run (0 quota) → both dead → retrigger.py (new root, _shared reused, cards as negative anchors) → lineage → cap."""
    import shutil
    root = make_run_root(tmp_path); env = {"EXP_SANDBOX": str(tmp_path)}
    shutil.copytree(root / "r1", root / "r2"); (root / "_shared").mkdir(); (root / "_shared" / "intake.json").write_text("{}")
    json.dump({"ranking": [{"run": "r1", "rank": 1}, {"run": "r2", "rank": 2}], "backup_run": "r2"}, open(root / "ranking.json", "w"))
    json.dump({"root": str(root), "repo": str(tmp_path / "repo"), "goal": "FROZEN test goal", "k": 2}, open(root / "args.json", "w"))
    def kill(xid, run):
        r = run_(sys.executable, EXP / "precheck.py", root, "--run", run, "--repo", tmp_path / "repo", "--x", xid, env=env); assert r.returncode == 0, r.stdout
        _set(tmp_path, xid, status="killed", failure_level="L3")
        r = run_(sys.executable, EXP / "failure_card.py", xid, env=env); assert r.returncode == 0, r.stdout + r.stderr
    kill("X-960", "r1")
    d = _nav(root, env); assert d["skill"] == "exp-next" and "--run r2 --block B1" in d["skill_args"] and "backup" in d["state"], d
    kill("X-961", "r2")
    d = _nav(root, env); assert d["phase"] == "BRAIN" and "retrigger.py" in d["run"][0] and not d["blocked"] and "2 failure card" in d["state"], d
    json.dump({"root": str(root), "repo": str(tmp_path / "repo"), "goal": "FROZEN test goal", "k": 2, "max_brain_rounds": 1}, open(root / "args.json", "w"))
    d = _nav(root, env); assert d["blocked"] and "max_brain_rounds" in d["note"], d
    r = run_(sys.executable, EXP / "retrigger.py", root, env=env); assert r.returncode == 3 and "BLOCKED" in r.stdout, r.stdout
    json.dump({"root": str(root), "repo": str(tmp_path / "repo"), "goal": "FROZEN test goal", "k": 2}, open(root / "args.json", "w"))
    r = run_(sys.executable, EXP / "retrigger.py", root, env=env); assert r.returncode == 0, r.stdout + r.stderr
    new = Path(str(root) + "-n2"); a2 = json.load(open(new / "args.json"))
    assert a2["brain_round"] == 2 and a2["parent_root"] == str(root) and len(a2["negative_anchors"]) == 2 and all(Path(c).exists() for c in a2["negative_anchors"])
    assert (new / "_shared" / "intake.json").exists() and json.load(open(root / "retrigger.json"))["next_root"] == str(new)
    d = _nav(root, env); assert d["phase"] == "BRAIN" and d["root"] == str(new) and d["lineage"] == [str(root)] and any("brain.workflow.js" in c for c in d["run"]) and "round 2" in d["state"], d
    r = run_(sys.executable, EXP / "retrigger.py", root, env=env); assert r.returncode == 0 and "already" in r.stdout      # idempotent
    r = run_(sys.executable, EXP / "retrigger.py", new, env=env); assert r.returncode == 3                                 # cap: round 2 of 2


def test_auto_skill_exists():
    t = (WS / ".claude/skills/exp-auto/SKILL.md").read_text(); assert "next.py" in t and "/loop" in t and "BLOCKED" in t
