"""stage.py / bundle.py: stages, the per-chain actions Main sees, the mechanism map's hill-climb rule, the support ladder."""
import importlib.util, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))
import stage  # noqa: E402
import gate   # noqa: E402

CLAIM = """# CLAIM.md — test

```yaml
claim:
  sentence: "test claim"
  metric: gain_test
  held_out: "structured interference class: mirrored map + smoothed random field; never in any training condition"
  keep_gain: 1.0
  keep_networks: 2
  clean_cost_max: 0.2
  seeds_for_keep: 3
  kill_floor: 0.5
  kill_frac_of_best: 0.5
  kill_gpu_h_cap: 4
  stop_hours_no_improve: 24
  stop_search_gpu_h: 24
  networks: [NetA, NetB]
  chains:
    alpha: {gpu: 0, seed_method: "seed alpha"}
    beta:  {gpu: 1, seed_method: "ConD original three conditions — the missing-only baseline"}
```

## AVOID
- probes must prove themselves
"""
GOAL = "```yaml\ncampaign:\n  run_name: t\n  repo_root: repo\n  gpu_h_ceiling: 200\n  caps: {oracle_frac: 0.05, single_run_frac: 0.25, reserve_frac: 0.2}\n  protected_paths: [\"scripts/eval.py\"]\n```\n"
NEVER = lambda run: False


def ws(tmp_path: Path) -> tuple[Path, Path]:
    w = tmp_path; r = w / ".research"
    for d in ("cards", "records", "bundles", "tokens", "gates", "build", "monitor"):
        (r / d).mkdir(parents=True)
    (w / "repo").mkdir()
    (w / "GOAL.md").write_text(GOAL)
    (w / "CLAIM.md").write_text(CLAIM)
    (r / "CLAIM.sha").write_text(stage.claim_sha(w))
    write_map(r, stage.claim_sha(w))
    return w, r


def write_map(r: Path, sha: str, sources=None):
    srcs = sources if sources is not None else [
        {"id": "S1", "mechanism": "M1", "domain": "robust statistics", "name": "contamination-aware aggregation", "status": "open", "best": None, "no_improve": 0, "tried": []},
        {"id": "S2", "mechanism": "M1", "domain": "sensor fusion", "name": "reliability weighting", "status": "open", "best": None, "no_improve": 0, "tried": []},
        {"id": "S3", "mechanism": "M2", "domain": "x", "name": "y", "status": "dropped", "drop_reason": "no procedure steps", "best": None, "no_improve": 0, "tried": []}]
    (r / "mechanism-map.json").write_text(json.dumps({"claim_sha": sha, "failure_modes": [], "mechanisms": [], "sources": srcs}))


def card(r: Path, qid: str, chain: str, net: str, wt: Path, frozen=True, source="S1", phase="search", rung=None):
    c = {"schema": 3, "id": qid, "chain": chain, "network": net, "phase": phase, "source": source, "rung": rung, "method": f"m-{qid}", "worktree": str(wt),
         "prediction": {"metric": "gain_test", "band": [1.0, 99.0], "direction": "maximize"}, "kill": {"threshold": 0.5, "gpu_h": 2.0, "cmd": "python train.py"},
         "frozen_sha": "abc" if frozen else None, "spec": {"source": source, "steps": [{"id": "s1", "file": "a.py", "change": "x" * 40}], "conditions": ["complete", "missing"]}}
    (r / "cards" / f"{qid}.json").write_text(json.dumps(c))
    return c


def record(r: Path, wt: Path, qid: str, mean: float, clean_cost, canary=True, age_h=0.0, gpu_h=2.0, n=1, ci=None, early=False):
    rec = {"run": qid, "card": qid, "metric": "gain_test", "mean": mean, "n_realized": n, "ci95": ci or [None, None], "band_hit": mean >= 1.0, "kill_hit": mean < 0.5,
           "canary": {"pass": canary}, "cost_gpu_h": gpu_h, "artifacts": [], "early_kill": early}
    p = r / "records" / f"{qid}.json"; p.write_text(json.dumps(rec))
    t = time.time() - age_h * 3600; os.utime(p, (t, t))
    d = wt / "results" / qid; d.mkdir(parents=True, exist_ok=True)
    for k in range(n):
        seed = {"seed": k, "metric": "gain_test", "value": mean}
        if clean_cost is not None:
            seed["clean_cost"] = clean_cost
        (d / f"seed_{k}.json").write_text(json.dumps(seed))
    return rec


def decide(w, r, idle=(0, 1), active=NEVER):
    return stage.decide(w, r, idle=list(idle), active=active)


def test_global_stages(tmp_path):
    w, r = ws(tmp_path)
    (w / "CLAIM.md").unlink()
    assert stage.decide(w, r, idle=[])["stage"] == "A"
    (w / "CLAIM.md").write_text(CLAIM); (r / "CLAIM.sha").unlink()
    assert stage.decide(w, r, idle=[])["stage"] == "R"
    (r / "CLAIM.sha").write_text(stage.claim_sha(w)); (r / "mechanism-map.json").unlink()
    d = stage.decide(w, r, idle=[]); assert d["stage"] == "M" and "step.py mechanism" in d["next"][0]
    write_map(r, "stale-sha")
    assert stage.decide(w, r, idle=[])["stage"] == "M", "a map made for another claim text is not this claim's map"
    write_map(r, stage.claim_sha(w), sources=[{"id": "S1", "status": "dropped", "drop_reason": "precedent"}])
    assert stage.decide(w, r, idle=[])["stage"] == "R", "a map with no open source goes back to the owner"
    write_map(r, stage.claim_sha(w))
    d = decide(w, r)
    assert d["stage"] == "C" and {c["name"] for c in d["chains"]} == {"alpha", "beta"} and all(c["state"] == "spec_pending" for c in d["chains"])
    assert "step.py propose alpha" in " ".join(d["next"]) and "step.py propose beta" in " ".join(d["next"])
    (w / "CLAIM.md").write_text(CLAIM + "\nedited\n")
    assert stage.decide(w, r, idle=[])["stage"] == "R"
    (r / "IDENTITY-MISMATCH").write_text("x")
    assert stage.decide(w, r, idle=[])["stage"] == "STOP"


def test_chain_actions_walk_the_ladder(tmp_path):
    w, r = ws(tmp_path)
    claim = stage.load_claim(w); cfg = claim["chains"]["alpha"]
    nxt = lambda idle=(0, 1), active=NEVER: stage.chain_next("alpha", cfg, claim, r, list(idle), active)
    q = "Q-0001-alpha"; wt = tmp_path / f"wt-{q}"
    st = nxt(); assert st["state"] == "spec_pending" and st["qid"] == q and st["lines"][-1] == "python3 .research/step.py propose alpha"
    (r / "bundles" / f"spec-{q}.json").write_text("{}")
    assert nxt()["lines"][0] == f"python3 .research/step.py propose --finish {q}"
    (r / "gates" / f"{q}.spec.fail.json").write_text(json.dumps({"fails": ["x"]}))
    assert nxt()["state"] == "spec_retry" and "--retry" in nxt()["lines"][0]
    (r / "gates" / f"{q}.spec.retries").write_text("1\n")
    assert nxt()["state"] == "spec_failed" and "bundle.py queue" in nxt()["lines"][0]
    (r / "gates" / f"{q}.spec.fail.json").unlink(); (r / "gates" / f"{q}.spec.ok").write_text("t\n")
    card(r, q, "alpha", "NetA", wt, frozen=False)
    assert nxt()["state"] == "card_pending" and "propose --finish" in nxt()["lines"][0]
    card(r, q, "alpha", "NetA", wt, frozen=True)
    assert nxt()["state"] == "card_pending", "frozen but no worktree: propose --finish creates it"
    wt.mkdir()
    assert nxt()["state"] == "wt_ready" and nxt()["lines"][0] == f"python3 .research/step.py build {q}"
    out = r / "bundles" / f"build-out-{q}.json"; out.write_text("{}")
    assert nxt()["state"] == "build_out" and f"build --finish {q} {out}" in nxt()["lines"][0]
    time.sleep(0.02); (r / "monitor" / f"{q}.json").write_text(json.dumps({"approved": False, "reasons": ["s1: missing"]}))
    assert nxt()["state"] == "monitor_rejected" and nxt()["lines"][0] == f"python3 .research/step.py build {q} --fix"
    (r / "build" / f"{q}.fixes").write_text("1\n")
    assert nxt()["state"] == "monitor_rejected_twice" and "queue" in nxt()["lines"][0]
    time.sleep(0.02); out.write_text("{}")                      # a newer build output after the fix round → gate it again
    assert nxt()["state"] == "build_out"
    time.sleep(0.02); (r / "monitor" / f"{q}.json").write_text(json.dumps({"approved": True, "diff_sha": "d"}))
    assert nxt()["state"] == "approved"
    (r / "tokens" / f"{q}.clean").write_text("abc\n")
    assert nxt(idle=(1,))["state"] == "launch_wait_gpu"
    assert nxt()["state"] == "launch" and "build --finish" in nxt()["lines"][0]
    assert nxt(active=lambda run: run == q)["state"] == "running"
    (wt / "results" / q).mkdir(parents=True); (wt / "results" / q / "progress.json").write_text(json.dumps({"fraction": 0.4, "dev_gain": 0.7}))
    assert "fraction 0.40" in nxt(active=lambda run: run == q)["lines"][0], "Main sees the run's progress while it waits"
    (wt / "results" / q / "seed_0.json").write_text("{}")
    assert nxt()["state"] == "finished" and nxt()["lines"][0] == f"python3 .research/step.py record {q}"
    record(r, wt, q, 1.4, 0.1)                                  # band hit, one seed → confirm through step.py record
    assert nxt()["state"] == "confirm" and f"step.py record {q}" in nxt()["lines"][0]
    assert nxt(active=lambda run: run == f"{q}-confirm")["state"] == "confirm_running"
    record(r, wt, q, 1.4, 0.1, n=3, ci=[0.9, 1.9])              # confirmed KEEP → the support ladder takes over
    st = nxt(); assert st["state"] == "spec_pending" and "--rung R1" in st["lines"][-1] and "NetB" in st["lines"][0]
    record(r, wt, q, 0.2, 0.1)                                  # killed → plain next candidate
    st = nxt(); assert st["qid"] == "Q-0002-alpha" and "--rung" not in st["lines"][-1]
    record(r, wt, q, 1.4, 0.1, early=True)                      # an early kill never confirms
    assert nxt()["state"] == "spec_pending"


def test_support_ladder_and_stage_D(tmp_path):
    w, r = ws(tmp_path)
    claim = stage.load_claim(w); wt = tmp_path / "wt"
    assert stage.support_rungs(claim, r)["kept"] is None
    card(r, "Q-0001-alpha", "alpha", "NetA", wt); record(r, wt, "Q-0001-alpha", 1.4, 0.1, n=3, ci=[0.9, 1.9])
    lad = stage.support_rungs(claim, r)
    assert lad["kept"] == "Q-0001-alpha" and [x["kind"] for x in lad["rungs"]] == ["network", "ablation"] and lad["rungs"][0]["value"] == "NetB"
    assert decide(w, r)["stage"] == "C"
    card(r, "Q-0002-alpha", "alpha", "NetB", wt, phase="support", rung="R1")
    assert stage.support_rungs(claim, r)["rungs"][0]["status"] == "active"
    record(r, wt, "Q-0002-alpha", 1.1, 0.1, n=3, ci=[0.5, 1.7])
    card(r, "Q-0003-alpha", "alpha", "NetA", wt, phase="support", rung="R2"); record(r, wt, "Q-0003-alpha", 0.9, 0.1)
    d = decide(w, r)
    assert d["stage"] == "D" and "gate.py numbers" in " ".join(d["next"])
    assert stage.search_gpu_h(stage.records(r)) == 2.0, "support runs never count against the search budget"


def test_keep_rules(tmp_path):
    w, r = ws(tmp_path); wt = tmp_path / "wt"; claim = stage.load_claim(w)
    card(r, "Q-0001-alpha", "alpha", "NetA", wt)
    record(r, wt, "Q-0001-alpha", 1.4, None, n=3, ci=[0.9, 1.9]); assert stage.keep_records(stage.records(r), claim) == []
    record(r, wt, "Q-0001-alpha", 1.4, 0.1, n=1); assert stage.keep_records(stage.records(r), claim) == []
    record(r, wt, "Q-0001-alpha", 1.4, 0.1, n=3, ci=[-0.1, 2.9]); assert stage.keep_records(stage.records(r), claim) == []
    record(r, wt, "Q-0001-alpha", 1.4, 0.1, n=3, ci=[0.9, 1.9], early=True); assert stage.keep_records(stage.records(r), claim) == []
    record(r, wt, "Q-0001-alpha", 1.4, 0.1, n=3, ci=[0.9, 1.9]); assert len(stage.keep_records(stage.records(r), claim)) == 1


def test_stop_rules(tmp_path):
    w, r = ws(tmp_path); wt = tmp_path / "wt"; claim = stage.load_claim(w)
    (r / "records" / "C-OLD.json").write_text(json.dumps({"run": "C-OLD", "card": "C-OLD", "mean": 9, "cost_gpu_h": 500, "canary": {"pass": True}}))
    (r / "cards" / "C-OLD.json").write_text(json.dumps({"id": "C-OLD", "prediction": {"metric": "x"}}))
    assert stage.records(r) == []
    card(r, "Q-0001-alpha", "alpha", "NetA", wt); record(r, wt, "Q-0001-alpha", 1.6, 0.1, age_h=30)
    assert stage.kill_threshold(stage.records(r), claim) == 0.8
    assert decide(w, r)["stage"] == "P"
    record(r, wt, "Q-0001-alpha", 1.6, 0.1, age_h=1, gpu_h=30)
    assert decide(w, r)["stage"] == "P"
    record(r, wt, "Q-0001-alpha", 0.2, 0.1, age_h=1, gpu_h=1)
    write_map(r, stage.claim_sha(w), sources=[{"id": "S1", "status": "exhausted", "no_improve": 2, "tried": ["Q-0001-alpha"]}, {"id": "S2", "status": "dropped"}])
    d = decide(w, r); assert d["stage"] == "P" and "exhausted" in d["reason"], "all sources exhausted stops the search"


def _bundle(w, r, monkeypatch):
    spec = importlib.util.spec_from_file_location("bundle", HERE / "bundle.py"); bundle = importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)
    monkeypatch.setattr(bundle, "W", w); monkeypatch.setattr(bundle, "HERE", r); monkeypatch.setattr(stage, "W", w); monkeypatch.setattr(stage, "HERE", r)
    monkeypatch.setattr(bundle, "_repo_files", lambda limit=80: ["a.py"])
    return bundle


def test_spec_bundle_modes_and_card(tmp_path, monkeypatch):
    w, r = ws(tmp_path); bundle = _bundle(w, r, monkeypatch)
    sp = bundle.cmd_spec("alpha")
    assert sp["qid"] == "Q-0001-alpha" and bundle.NO_HISTORY in sp["prompt"] and "$RESULTS_DIR" in sp["prompt"]
    assert '"mechanism_map"' in sp["prompt"] and "contamination-aware aggregation" in sp["prompt"] and "status=open" in sp["prompt"]
    sb = bundle.cmd_spec("beta")
    assert '"mode": "baseline"' in sb["prompt"] and '"mechanism_map"' not in sb["prompt"], "the baseline chain never sees the map"
    spec_p = r / "bundles" / "spec-Q-0001-alpha.json"
    spec_p.write_text(json.dumps({"source": "S1", "method": "m", "steps": [{"id": "s1", "file": "a.py", "change": "x" * 40}] * 3, "files": ["a.py"], "conditions": ["clean"],
                                  "held_out": "structured", "schedule": {"gpu_h": 2.0}, "network": "NetA", "kill_cmd": "python train.py --out $RESULTS_DIR --seed $SEED",
                                  "canary": {"what": "w", "expected": 1, "tol": 0.1}, "rationale_line": "x" * 30, "naive_baseline": "y" * 30}))
    (r / "bundles" / "args-spec-Q-0001-alpha.json").write_text(json.dumps(sp))
    c = json.loads(Path(bundle.cmd_card(str(spec_p))["card_path"]).read_text())
    assert c["source"] == "S1" and c["phase"] == "search" and c["rung"] is None and c["worktree"] == "/tmp/wt-Q-0001-alpha"
    goal = {"campaign": {"gpu_h_ceiling": 200, "caps": {"oracle_frac": 0.05, "single_run_frac": 0.25, "reserve_frac": 0.2}, "kill_cap_gpu_h": 4}}
    assert gate.check_card(c, goal, r) == []
    b = bundle.cmd_build("Q-0001-alpha")
    assert b["qid"] == "Q-0001-alpha" and "scripts/eval.py" in b["prompt"] and "git -C /tmp/wt-Q-0001-alpha diff research-trunk" in b["monitor_prompt"] and "codex-companion" in b["codex_prompt"]
    assert '"smoke"' not in b["prompt"].split("## 返回的 JSON")[1]


def test_hill_climb_rule_on_the_map(tmp_path, monkeypatch):
    w, r = ws(tmp_path); bundle = _bundle(w, r, monkeypatch); wt = tmp_path / "wt"
    c = card(r, "Q-0001-alpha", "alpha", "NetA", wt, source="S1")
    res = bundle.update_map("Q-0001-alpha", record(r, wt, "Q-0001-alpha", 0.8, 0.1), c)
    assert res["status"] == "tried" and res["best"] == 0.8 and res["no_improve"] == 0
    c2 = card(r, "Q-0002-alpha", "alpha", "NetA", wt, source="S1")
    res = bundle.update_map("Q-0002-alpha", record(r, wt, "Q-0002-alpha", 0.7, 0.1), c2)
    assert res["no_improve"] == 1 and res["status"] == "tried"
    c3 = card(r, "Q-0003-alpha", "alpha", "NetA", wt, source="S1")
    res = bundle.update_map("Q-0003-alpha", record(r, wt, "Q-0003-alpha", 0.75, 0.1), c3)
    assert res["no_improve"] == 2 and res["status"] == "exhausted", "two versions without a new best exhaust the source"
    assert bundle.update_map("Q-0003-alpha", record(r, wt, "Q-0003-alpha", 0.75, 0.1), c3)["note"] == "already counted"
    cb = card(r, "Q-0001-beta", "beta", "NetA", wt, source="baseline")
    assert bundle.update_map("Q-0001-beta", record(r, wt, "Q-0001-beta", 0.1, 0.1), cb) is None
    mp = json.loads((r / "mechanism-map.json").read_text())
    assert next(s for s in mp["sources"] if s["id"] == "S1")["tried"] == ["Q-0001-alpha", "Q-0002-alpha", "Q-0003-alpha"]


def test_mechanism_finish_verifies_and_drops(tmp_path, monkeypatch):
    w, r = ws(tmp_path); bundle = _bundle(w, r, monkeypatch)
    txt = r / "lit" ; txt.mkdir(); paper = txt / "p.txt"; paper.write_text("line one\nthe estimator reaches 0.93 AUROC on contaminated data\nline three\n")
    out = r / "bundles" / "mechanism-out.json"
    out.write_text(json.dumps({"failure_modes": [{"id": "B1"}], "mechanisms": [{"id": "M1"}], "sources": [
        {"mechanism": "M1", "domain": "robust statistics", "name": "Huber aggregation", "isomorphism": "i", "disanalogy": "d",
         "recipe": {"paper": "p", "title": "t", "steps": ["a", "b"], "key_number": {"value": "0.93", "quote": "reaches 0.93 AUROC", "line": 2}, "text_path": str(paper), "avoid": "x"}, "precedent": {"found": False}},
        {"mechanism": "M1", "domain": "moe", "name": "routing", "isomorphism": "i", "disanalogy": "d",
         "recipe": {"paper": "p", "title": "t", "steps": [], "key_number": {"value": "", "quote": "", "line": 0}, "text_path": "", "avoid": ""}, "precedent": {"found": False}},
        {"mechanism": "M1", "domain": "fusion", "name": "reliability weighting", "isomorphism": "i", "disanalogy": "d",
         "recipe": {"paper": "p", "title": "t", "steps": ["a"], "key_number": {"value": "0.93", "quote": "wrong", "line": 1}, "text_path": str(paper), "avoid": ""}, "precedent": {"found": True, "paper": "q", "quote": "applied to RGB-D"}},
    ]}))
    res = bundle.cmd_mechanism_finish(str(out))
    assert res["open"] == 1 and len(res["dropped"]) == 2
    mp = json.loads((r / "mechanism-map.json").read_text())
    assert mp["sources"][0]["status"] == "open" and "no procedure" in mp["sources"][1]["drop_reason"] and "precedent" in mp["sources"][2]["drop_reason"]


def test_ladder_complete_but_networks_short_is_a_pivot(tmp_path):
    w, r = ws(tmp_path); wt = tmp_path / "wt"
    card(r, "Q-0001-alpha", "alpha", "NetA", wt); record(r, wt, "Q-0001-alpha", 1.4, 0.1, n=3, ci=[0.9, 1.9])
    card(r, "Q-0002-alpha", "alpha", "NetB", wt, phase="support", rung="R1"); record(r, wt, "Q-0002-alpha", 0.3, 0.1, n=3, ci=[-0.2, 0.8])   # NetB fails
    card(r, "Q-0003-alpha", "alpha", "NetA", wt, phase="support", rung="R2"); record(r, wt, "Q-0003-alpha", 0.9, 0.1)
    d = decide(w, r)
    assert d["stage"] == "P" and "1/2 networks" in d["reason"], "keep_networks 2 with one network in band is not a paper (ARIS: the loop may drive, not acquit)"


def test_mechanism_finish_drops_ungrounded_failure_modes(tmp_path, monkeypatch):
    w, r = ws(tmp_path); bundle = _bundle(w, r, monkeypatch)
    (r / "anomalies.md").write_text("## measured\n- plausible wrong depth hurts more than missing depth: 6.24 vs 5.65 mIoU on NetA\n")
    paper = r / "p.txt"; paper.write_text("line one\nthe estimator reaches 0.93 AUROC on contaminated data\n")
    out = r / "bundles" / "mechanism-out.json"
    src = lambda m: {"mechanism": m, "domain": f"d-{m}", "name": f"n-{m}", "isomorphism": "i", "disanalogy": "d", "naive_in_A": "zero fill",
                     "recipe": {"paper": "p", "title": "t", "steps": ["a", "b"], "key_number": {"value": "0.93", "quote": "reaches 0.93 AUROC", "line": 2}, "text_path": str(paper), "avoid": "x"},
                     "precedent": {"found": False}}
    out.write_text(json.dumps({"failure_modes": [{"id": "B1", "text": "wrong depth hurts more than missing", "grounded_in": ["6.24 vs 5.65"]},
                                                 {"id": "B2", "text": "attention collapses under fog", "grounded_in": ["everyone knows this"]}],
                               "mechanisms": [{"id": "M1", "from": "B1"}, {"id": "M2", "from": "B2"}], "sources": [src("M1"), src("M2")]}))
    res = bundle.cmd_mechanism_finish(str(out))
    mp = json.loads((r / "mechanism-map.json").read_text())
    assert res["open"] == 1 and "ungrounded" in res["dropped"][0]["why"]
    assert mp["failure_modes"][1].get("status") == "dropped" and mp["mechanisms"][1].get("status") == "dropped"
    assert mp["sources"][0]["naive_in_A"] == "zero fill", "K3's naive_in_A reaches the map (ResearchStudio T5)"


def test_accept_refuses_keep_gain_below_mde(tmp_path, monkeypatch):
    w, r = ws(tmp_path)
    monkeypatch.setattr(stage, "W", w); monkeypatch.setattr(stage, "HERE", r)
    (w / "CLAIM.md").write_text(CLAIM.replace("keep_gain: 1.0", "keep_gain: 1.0\n  seed_sd: 0.564"))
    monkeypatch.setattr(sys, "argv", ["stage.py", "accept"])
    assert stage.main() == 1, "keep_gain 1.0 < MDE 1.71 at 3 seeds must be refused"
    (w / "CLAIM.md").write_text(CLAIM.replace("keep_gain: 1.0", "keep_gain: 1.0\n  seed_sd: 0.564\n  seeds_for_keep: 5").replace("  seeds_for_keep: 3\n", ""))
    assert stage.main() == 0, "five seeds bring the MDE to 1.0"
