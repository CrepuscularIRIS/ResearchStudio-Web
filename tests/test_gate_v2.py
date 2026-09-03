"""gate.py v2: the spec gate (B1 completeness), the monitor gate (quotes must exist in the diff), record provenance, numbers."""
import json, os, pathlib, subprocess, sys, time
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import gate  # noqa: E402

CLAIM = {"held_out": "structured interference class: mirrored map + smoothed random field; never in any training condition",
         "networks": ["NetA", "NetB"], "kill_gpu_h_cap": 4}


def repo(tmp_path):
    r = tmp_path / "repo"; r.mkdir()
    subprocess.run(["git", "-C", r, "init", "-q", "-b", "research-trunk"], check=True)
    (r / "a.py").write_text("x = 1\n"); (r / "scripts").mkdir(); (r / "scripts" / "train.py").write_text("print(1)\n")
    subprocess.run(["git", "-C", r, "add", "."], check=True)
    subprocess.run(["git", "-C", r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"], check=True)
    return r


def good_spec():
    return {"method": "m", "files": ["a.py", "scripts/train.py", "new_loss.py"], "network": "NetA", "held_out": "structured",
            "steps": [{"id": "s1", "file": "a.py", "change": "replace the depth mask with alpha-scaled mask U(0.05,1)"},
                      {"id": "s2", "file": "scripts/train.py", "change": "add condition sampler over {complete, missing, amplitude}"},
                      {"id": "s3", "file": "new_loss.py", "change": "zero-init 1x1 injection head, lr 1e-4, 20 epochs", "new": True}],
            "conditions": ["complete", "depth-missing", "amplitude class"], "schedule": {"gpu_h": 2.0},
            "kill_cmd": "python scripts/train.py --out $RESULTS_DIR --seed $SEED", "canary": {"what": "clean mIoU", "expected": 55.7, "tol": 0.3},
            "rationale_line": "the binding failure mode is B1 (operator corruption); C2 attenuation failed via clean cost; this spec attacks it by zero-init injection",
            "naive_baseline": "the same conditions with the original ConD three-condition sampler and no ladder classes", "source": "S1",
            "method_prose": "We keep the original network frozen and copy its encoder. A zero-initialised injection head reads the copied features and adds them to the frozen stream. "
                            "Training samples one input condition per step from the audited ladder classes while the held-out class never appears. The source mechanism predicts that "
                            "reweighting by an estimate of contamination transfers to unseen corruption classes. The disanalogy forced us to estimate contamination from the input rather than from labels."}


def test_spec_gate_passes_a_b1_spec_and_rejects_b2(tmp_path):
    r = repo(tmp_path)
    assert gate.check_spec(good_spec(), CLAIM, r, 4.0) == []
    s = good_spec(); s["steps"] = [{"id": "s1", "file": "a.py", "change": "use ConD"}]
    f = gate.check_spec(s, CLAIM, r, 4.0)
    assert any("fewer than 3" in x for x in f) and any("too short" in x for x in f)
    s = good_spec(); s["steps"][0]["file"] = "ghost.py"; s["files"].append("ghost.py")
    assert any("does not exist on research-trunk" in x for x in gate.check_spec(s, CLAIM, r, 4.0))
    s = good_spec(); s["conditions"].append("structured interference (mirrored)")
    assert any("held-out" in x for x in gate.check_spec(s, CLAIM, r, 4.0))
    s = good_spec(); s["network"] = "NetZ"
    assert any("not in claim.networks" in x for x in gate.check_spec(s, CLAIM, r, 4.0))
    s = good_spec(); s["schedule"]["gpu_h"] = 9
    assert any("gpu_h" in x for x in gate.check_spec(s, CLAIM, r, 4.0))
    s = good_spec(); s["kill_cmd"] = "python scripts/train.py"
    assert sum("kill_cmd must honour" in x for x in gate.check_spec(s, CLAIM, r, 4.0)) == 2
    s = good_spec(); s["canary"]["tol"] = 0
    assert any("canary" in x for x in gate.check_spec(s, CLAIM, r, 4.0))
    s = good_spec(); s["naive_baseline"] = "none"
    assert any("naive_baseline" in x for x in gate.check_spec(s, CLAIM, r, 4.0))


def test_duplicate_spec_is_refused(tmp_path):
    rdir = tmp_path / ".research"; (rdir / "cards").mkdir(parents=True)
    (rdir / "cards" / "Q-0001-alpha.json").write_text(json.dumps({"id": "Q-0001-alpha", "spec": good_spec()}))
    assert gate.duplicate_of(good_spec(), rdir) == "Q-0001-alpha"
    s = good_spec(); s["steps"] = [{"id": "s1", "file": "a.py", "change": "a completely different mechanism: robust median aggregation over modality tokens"},
                                   {"id": "s2", "file": "scripts/train.py", "change": "contamination-aware weighting by per-sample reliability score"},
                                   {"id": "s3", "file": "new_loss.py", "change": "huber loss on the fusion residual with delta 0.1", "new": True}]
    assert gate.duplicate_of(s, rdir) is None


def test_held_out_terms():
    assert gate.held_out_terms(CLAIM) == ["interference", "mirrored", "smoothed", "structured"]
    assert gate.held_out_terms({"held_out_terms": ["Mirror"]}) == ["mirror"]


DIFF = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1,2 @@
 x = 1
+mask = mask * torch.empty_like(mask).uniform_(0.05, 1.0)
+sampler = ConditionSampler(["complete", "missing", "amplitude"])
"""
STEPS = [{"id": "s1", "file": "a.py", "change": "x"}, {"id": "s2", "file": "a.py", "change": "y"}]


def test_monitor_gate_verifies_quotes_and_coverage():
    out = {"grok": {"approved": True, "findings": [],
                    "coverage": [{"step_id": "s1", "status": "implemented", "diff_lines": ["+mask = mask * torch.empty_like(mask).uniform_(0.05, 1.0)"]},
                                 {"step_id": "s2", "status": "implemented", "diff_lines": ["+sampler = ConditionSampler([\"complete\", \"missing\", \"amplitude\"])"]}]},
           "codex": {"available": True, "findings": [{"severity": "P3", "file": "a.py", "line": 2, "text": "style"}]}}
    ok, reasons = gate.check_monitor(out, DIFF, STEPS, truncated=False)
    assert ok and reasons == []
    bad = json.loads(json.dumps(out)); bad["grok"]["coverage"][0]["diff_lines"] = ["+mask = mask * 2  # invented"]
    ok, reasons = gate.check_monitor(bad, DIFF, STEPS, truncated=False)
    assert not ok and any("not in the diff" in r for r in reasons), "a quote that is not in the diff is a tell"
    bad = json.loads(json.dumps(out)); bad["grok"]["coverage"].pop()
    ok, reasons = gate.check_monitor(bad, DIFF, STEPS, truncated=False)
    assert not ok and any("s2: no coverage" in r for r in reasons)
    bad = json.loads(json.dumps(out)); bad["grok"]["coverage"][1]["status"] = "missing"
    assert not gate.check_monitor(bad, DIFF, STEPS, truncated=False)[0]
    assert not gate.check_monitor(out, DIFF, STEPS, truncated=True)[0], "a truncated diff is never approved"
    bad = json.loads(json.dumps(out)); bad["codex"]["findings"] = [{"severity": "P1", "file": "a.py", "line": 2, "text": "reads the test split"}]
    ok, reasons = gate.check_monitor(bad, DIFF, STEPS, truncated=False)
    assert not ok and any("codex P1" in r for r in reasons)
    skipped = json.loads(json.dumps(out)); skipped["codex"] = {"available": False, "findings": []}
    assert gate.check_monitor(skipped, DIFF, STEPS, truncated=False)[0], "an unavailable Codex is skipped, never a verdict"
    bad = json.loads(json.dumps(out)); bad["grok"]["findings"] = [{"kind": "hardcode", "diff_lines": ["+mask = mask * torch.empty_like(mask).uniform_(0.05, 1.0)"], "text": "constant result"}]
    assert not gate.check_monitor(bad, DIFF, STEPS, truncated=False)[0]


def test_record_provenance(tmp_path):
    wt = tmp_path / "wt"; res = wt / "results" / "Q-0001-alpha"; res.mkdir(parents=True)
    rdir = tmp_path / ".research"; rdir.mkdir()
    card = {"id": "Q-0001-alpha", "chain": "alpha", "worktree": str(wt), "prediction": {"metric": "gain_test"}}
    rec = {"run": "Q-0001-alpha", "metric": "gain_test"}
    (res / "seed_0.json").write_text(json.dumps({"seed": 0, "value": 1.0, "clean_cost": 0.1}))
    f = gate.record_provenance(rec, card, rdir)
    assert any("no launcher window" in x for x in f) and any("blockers.json missing" in x for x in f)
    now = datetime.now().astimezone()
    (rdir / "ledger.jsonl").write_text(json.dumps({"event": "stop", "run": "Q-0001-alpha", "wall_s": 60, "exit": 0, "t": now.isoformat()}) + "\n")
    (res / "blockers.json").write_text("[]")
    assert any("progress.json" in x for x in gate.record_provenance(rec, card, rdir)), "a run that never reported a checkpoint fails"
    (res / "progress.json").write_text(json.dumps({"fraction": 1.0, "dev_gain": 1.2}))
    assert gate.record_provenance(rec, card, rdir) == []
    (rdir / "ledger.jsonl").write_text(json.dumps({"event": "stop", "run": "Q-0001-alpha", "wall_s": 60, "exit": 4, "t": now.isoformat()}) + "\n")
    assert gate.record_provenance(rec, card, rdir) == [], "exit 4 = early kill is a verdict, not an infrastructure failure"
    (rdir / "ledger.jsonl").write_text(json.dumps({"event": "stop", "run": "Q-0001-alpha", "wall_s": 60, "exit": 137, "t": now.isoformat()}) + "\n")
    assert any("exited non-zero" in x for x in gate.record_provenance(rec, card, rdir))
    (rdir / "ledger.jsonl").write_text(json.dumps({"event": "stop", "run": "Q-0001-alpha", "wall_s": 60, "exit": 0, "t": now.isoformat()}) + "\n")
    (res / "seed_0.json").write_text(json.dumps({"seed": 0, "value": 1.0}))
    assert any("clean_cost missing" in x for x in gate.record_provenance(rec, card, rdir))
    (res / "seed_0.json").write_text(json.dumps({"seed": 0, "value": 1.0, "clean_cost": 0.1})); (res / "seed_2.json").write_text(json.dumps({"seed": 2, "value": 1.0, "clean_cost": 0.1}))
    assert any("not contiguous" in x for x in gate.record_provenance(rec, card, rdir))
    assert any("observable mismatch" in x for x in gate.record_provenance({"run": "Q-0001-alpha", "metric": "other"}, card, rdir))


def test_numbers_gate(tmp_path):
    rdir = tmp_path / ".research"; (rdir / "records").mkdir(parents=True)
    (rdir / "records" / "Q-0001-alpha.json").write_text(json.dumps({"mean": 1.42, "per_seed": {"0": 1.31}}))
    (rdir / "retracted.txt").write_text("sixfold\n55.86\n")
    tex = "Gain is 1.42 mIoU. % src: .research/records/Q-0001-alpha.json\n"
    assert gate.check_numbers(tex, rdir) == []
    assert any("without `% src" in f for f in gate.check_numbers("Gain is 1.42 mIoU.\n", rdir))
    assert any("not a number token" in f for f in gate.check_numbers("Gain is 9.99 mIoU. % src: .research/records/Q-0001-alpha.json\n", rdir))
    assert any("retracted" in f for f in gate.check_numbers("a sixfold gap % src: .research/records/Q-0001-alpha.json\n", rdir))
    assert gate.check_numbers("\\label{tab:1.2}\n", rdir) == []
    (rdir / "records" / "Q-0002-alpha.json").write_text(json.dumps({"mean": 11.052, "ci95": [10.5, 11.6]}))
    assert any("not a number token" in f for f in gate.check_numbers("Gain 1.05 % src: .research/records/Q-0002-alpha.json\n", rdir)), \
        "a digit-substring of another number (1.05 inside 11.052) is not a source (ARIS: numeric-token equality)"
    assert gate.check_numbers("Gain 11.0520 % src: .research/records/Q-0002-alpha.json\n", rdir) == [], "73.2 matches 73.20"


def test_record_gate_refuses_high_blockers(tmp_path):
    wt = tmp_path / "wt"; res = wt / "results" / "Q-0001-alpha"; res.mkdir(parents=True)
    rdir = tmp_path / ".research"; rdir.mkdir()
    card = {"id": "Q-0001-alpha", "chain": "alpha", "worktree": str(wt), "prediction": {"metric": "gain_test"}}
    rec = {"run": "Q-0001-alpha", "metric": "gain_test"}
    now = datetime.now().astimezone()
    (rdir / "ledger.jsonl").write_text(json.dumps({"event": "stop", "run": "Q-0001-alpha", "wall_s": 60, "exit": 0, "t": now.isoformat()}) + "\n")
    (res / "seed_0.json").write_text(json.dumps({"seed": 0, "value": 1.0, "clean_cost": 0.1}))
    (res / "progress.json").write_text(json.dumps({"fraction": 1.0, "dev_gain": 1.2}))
    (res / "blockers.json").write_text(json.dumps([{"severity": "medium", "text": "slow dataloader"}]))
    assert gate.record_provenance(rec, card, rdir) == []
    (res / "blockers.json").write_text(json.dumps([{"severity": "high", "text": "injection layer never entered the optimizer"}]))
    f = gate.record_provenance(rec, card, rdir)
    assert any("high blocker" in x and "ARFT rule 9" in x for x in f), "a run that names its own critical flaw is not a result"


def test_diff_of_sees_new_files(tmp_path):
    r = tmp_path / "repo"; r.mkdir()
    def git(*a): subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)
    git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (r / "a.py").write_text("x = 1\n"); git("add", "a.py"); git("commit", "-qm", "init"); git("branch", "research-trunk")
    (r / "new_module.py").write_text("def f():\n    return 42\n")
    plain = subprocess.run(["git", "-C", str(r), "diff", "research-trunk"], capture_output=True, text=True).stdout
    assert "new_module" not in plain, "plain git diff never shows an untracked file (the AAR hole)"
    diff, sha = gate.diff_of(str(r))
    assert "new_module.py" in diff and "return 42" in diff and len(sha) == 64
    assert gate.diff_of(str(r))[1] == sha, "stable across calls"
    (r / "new_module.py").write_text("def f():\n    return 43\n")
    assert gate.diff_of(str(r))[1] != sha, "editing the new file after approval changes the sha the launcher checks"


def test_spec_gate_eval_entry(tmp_path):
    rp = repo(tmp_path)
    claim = {**CLAIM, "eval_entry": "tools/score.py"}
    spec = good_spec() if "good_spec" in globals() else None
    if spec is None:
        return
    spec["kill_cmd"] = "python train.py --out $RESULTS_DIR --seed $SEED"
    f = gate.check_spec(spec, claim, rp, 4)
    assert any("shared eval entrypoint" in x for x in f)
    spec["kill_cmd"] += " && python tools/score.py $RESULTS_DIR"
    assert not any("shared eval entrypoint" in x for x in gate.check_spec(spec, claim, rp, 4))


def test_numbers_gate_sources_only_result_fields(tmp_path):
    rdir = tmp_path / ".research"; (rdir / "records").mkdir(parents=True); (rdir / "retracted.txt").write_text("")
    (rdir / "records" / "Q-0001-alpha.json").write_text(json.dumps({"mean": 1.42, "ci95": [0.9, 1.9], "per_seed": {"0": 1.31}, "cost_gpu_h": 3.912, "band": [1.0, 99.0], "n_realized": 3}))
    (rdir / "records" / "Q-0001-alpha.md").write_text("band [1.0, 99.0] cost=3.912 GPU-h mean 1.42\n")
    ok = "% src: .research/records/Q-0001-alpha.md"
    assert gate.check_numbers(f"Gain 1.42 {ok}\n", rdir) == [], "the .md resolves to its .json result fields"
    assert any("not a number token" in f for f in gate.check_numbers(f"We reach 99.0 mIoU {ok}\n", rdir)), "a band ceiling printed in the record is not a result"
    assert any("not a number token" in f for f in gate.check_numbers(f"a gain of 3.912 {ok}\n", rdir)), "GPU-hours cannot source a gain"
    assert any("without" in f for f in gate.check_numbers("over 3 seeds on 2 networks\n", rdir)), "scope integers need a source"
    (tmp_path / "CLAIM.md").write_text("```yaml\nclaim:\n  seeds_for_keep: 3\n  keep_networks: 2\n```\n")
    assert gate.check_numbers("over 3 seeds on 2 networks % src: CLAIM.md\n", rdir) == []


def test_spec_gate_hygiene_and_source(tmp_path):
    rp = repo(tmp_path); spec = good_spec()
    spec["kill_cmd"] = "pip install x && python /home/me/train.py --out $RESULTS_DIR --seed $SEED"
    f = gate.check_spec(spec, CLAIM, rp, 4.0); assert any("kill_cmd: no package installs" in x for x in f)
    spec = good_spec(); spec["method_prose"] = spec["method_prose"] + " It outperforms the baseline by 2.3 mIoU."
    assert any("method_prose: no numbers" in x for x in gate.check_spec(spec, CLAIM, rp, 4.0))
    rdir = tmp_path / ".research"; (rdir / "bundles").mkdir(parents=True, exist_ok=True)
    (rdir / "mechanism-map.json").write_text(json.dumps({"sources": [{"id": "S1", "status": "open"}, {"id": "S2", "status": "exhausted", "no_improve": 2}]}))
    (rdir / "bundles" / "args-spec-Q-0001-alpha.json").write_text(json.dumps({"mode": "mechanism"}))
    (tmp_path / "GOAL.md").write_text("```yaml\ncampaign:\n  repo_root: repo\n```\n")
    (tmp_path / "CLAIM.md").write_text("```yaml\nclaim:\n  held_out: 'structured interference class'\n  networks: [NetA, NetB]\n  kill_gpu_h_cap: 4\n```\n")
    spec = good_spec(); spec["source"] = "S2"
    (rdir / "bundles" / "spec-Q-0001-alpha.json").write_text(json.dumps(spec))
    assert gate.gate_spec("Q-0001-alpha", rdir) == 1
    fails = json.loads((rdir / "gates" / "Q-0001-alpha.spec.fail.json").read_text())["fails"]
    assert any("not an eligible mechanism-map source" in x for x in fails), "an exhausted source never runs again"
    spec["source"] = "S1"; (rdir / "bundles" / "spec-Q-0001-alpha.json").write_text(json.dumps(spec))
    assert gate.gate_spec("Q-0001-alpha", rdir) == 0


def test_monitor_gate_refuses_gitlinks_and_hidden_codex_findings():
    diff = "diff --git a/repos/DFormer b/repos/DFormer\n-Subproject commit aaa\n+Subproject commit bbb-dirty\n"
    out = {"grok": {"approved": True, "coverage": [{"step_id": "s1", "status": "implemented", "diff_lines": ["-Subproject commit aaa"]}], "findings": []},
           "codex": {"available": True, "findings": [{"severity": "low", "text": "x"}], "raw": "[P1] eval split leaks into training"}}
    ok, reasons = gate.check_monitor(out, diff, [{"id": "s1"}], False)
    assert ok, "check_monitor itself passes; the gitlink and forwarder checks live in gate_monitor (they need the worktree)"
