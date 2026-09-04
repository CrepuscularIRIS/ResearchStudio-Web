#!/usr/bin/env python3
"""step.py — Main's actions, each idempotent; stage.py prints which one to run. Every action either prints ONE Workflow line
(with its args file and where to save the result) or consumes a saved result (`--finish`) through the script gates.

  claim loop
  mechanism [--finish <out>]            stage M workflow (Opus B→M · K3 C · GLM search/reverse · sol verify) → mechanism-map.json
  critique sources | spec <Q> [--finish] three-family panel (Slot 1 over map sources, Slot 2 over one gated spec) → map / critique/<Q>.json
  propose <chain> [--rung R] [--retry]  spec workflow (Opus); --finish <Q>: gate.py spec → panel verdict → card → freeze → worktree
  build <Q> [--fix]                     build workflow (GLM builder → Grok plugin review); --finish <Q> <out>: gate.py monitor → token → launcher
  record <Q>                            render_record → gate.py record → notebook + map; confirm seeds on a band hit
  pivot --finish <out>                  saves the explorer's verdict (owner picks the exit; `stage.py ship` is exit (a))
  outer manuscript loop (outer.py)
  write [--merge | --review]            W0 merge · sections from records + fact review · review only; --finish <out>: review → ledger rows
  read | trial | draft <n> [--finish <n> <out>]   referees → ledger · trials → verdicts · patches → applied, journaled, gated
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parent
sys.path.insert(0, str(HERE))
import stage, gate  # noqa: E402


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def py(*args: str) -> subprocess.CompletedProcess:
    return sh([sys.executable, *args], cwd=str(W))


def say(*lines: str) -> None:
    for l in lines:
        print(l)


# ── mechanism ───────────────────────────────────────────────────────────────

def mechanism(finish: str | None) -> int:
    if finish:
        r = py(str(HERE / "bundle.py"), "mechanism-finish", finish)
        say(r.stdout.strip() or r.stderr.strip())
        return r.returncode
    r = py(str(HERE / "bundle.py"), "M")
    if r.returncode:
        say(r.stderr.strip()); return 1
    (HERE / "bundles" / "args-mechanism.json").write_text(r.stdout)
    say("Workflow(name='mechanism', args=<contents of .research/bundles/args-mechanism.json>)   # scientist (B,M) → explorer (C) → searcher/reader (GLM) → verifier (sol)",
        "save the returned JSON to .research/bundles/mechanism-out.json, then: python3 .research/step.py mechanism --finish .research/bundles/mechanism-out.json")
    return 0


# ── propose ─────────────────────────────────────────────────────────────────

def propose(chain: str, retry: bool = False, rung: str | None = None) -> int:
    r = py(str(HERE / "bundle.py"), "spec", "--chain", chain, *(["--retry"] if retry else []), *(["--rung", rung] if rung else []))
    if r.returncode:
        say(r.stderr.strip()); return 1
    d = json.loads(r.stdout)
    (HERE / "bundles" / f"args-spec-{d['qid']}.json").write_text(r.stdout)
    if retry:                                                      # the revised spec must pass the gate and the panel again
        for p in (HERE / "gates" / f"{d['qid']}.spec.ok", HERE / "critique" / f"{d['qid']}.json", HERE / "bundles" / f"critique-out-{d['qid']}.json"):
            p.unlink(missing_ok=True)
    say(f"Workflow(name='spec', args=<contents of .research/bundles/args-spec-{d['qid']}.json>)   # scientist (Opus) writes {d['spec_path']}",
        f"then: python3 .research/step.py propose --finish {d['qid']}")
    return 0


def propose_finish(qid: str, out_path: str | None = None) -> int:
    chain = qid.split("-")[-1]
    spec_p = HERE / "bundles" / f"spec-{qid}.json"
    if not spec_p.exists() and out_path and Path(out_path).exists():
        out = stage._json(Path(out_path))
        if isinstance(out.get("spec"), dict) and out["spec"]:
            spec_p.write_text(json.dumps(out["spec"], indent=1, ensure_ascii=False))     # the returned object is authoritative; the scientist's Write is a convenience
    if not spec_p.exists():
        say(f"no spec at {spec_p}: the scientist wrote nothing → python3 .research/bundle.py queue {qid} \"spec workflow returned nothing (infrastructure)\""); return 1
    if not (HERE / "gates" / f"{qid}.spec.ok").exists():
        r = py(str(HERE / "gate.py"), "spec", qid)
        if r.returncode:
            retries = (HERE / "gates" / f"{qid}.spec.retries")
            if retries.exists():
                say("spec gate failed twice:", r.stdout.strip(), f"→ python3 .research/bundle.py queue {qid} \"spec failed the gate twice\"")
                return 1
            say("spec gate failed:", r.stdout.strip(), f"→ python3 .research/step.py propose {chain} --retry   # the scientist gets the failure list once")
            return 1
    mode = stage._json(HERE / "bundles" / f"args-spec-{qid}.json").get("mode", "mechanism")
    crit = stage._json(HERE / "critique" / f"{qid}.json")
    if mode == "mechanism" and not (HERE / "cards" / f"{qid}.json").exists():
        if not crit:
            say(f"{qid}: spec gated; the critique panel has not judged it (Slot 2) → python3 .research/step.py critique spec {qid}"); return 1
        if crit.get("verdict") != "advance":
            say(f"{qid}: critique verdict {crit.get('verdict')} — no card (stage.py prints the retry or the queue)"); return 1
    card_p = HERE / "cards" / f"{qid}.json"
    if not card_p.exists():
        r = py(str(HERE / "bundle.py"), "card", str(spec_p))
        if r.returncode:
            say(r.stderr.strip()); return 1
    card = stage._json(card_p)
    if not card.get("frozen_sha"):
        r = py(str(HERE / "gate.py"), "card", str(card_p))
        if r.returncode:
            say("gate.py card refused:", r.stdout.strip()); return 1
        r = py(str(HERE / "gate.py"), "freeze", str(card_p))
        if r.returncode:
            say("gate.py freeze refused:", r.stdout.strip(), r.stderr.strip()); return 1
        card = stage._json(card_p)
    wt = Path(card["worktree"])
    if not wt.exists():
        repo = stage.load_goal_repo(W)
        sh(["git", "-C", str(repo), "worktree", "prune"])
        has_branch = sh(["git", "-C", str(repo), "rev-parse", "--verify", "-q", f"exp/{qid}"]).returncode == 0
        r = sh(["git", "-C", str(repo), "worktree", "add", str(wt), f"exp/{qid}"] if has_branch else ["git", "-C", str(repo), "worktree", "add", str(wt), "-b", f"exp/{qid}", "research-trunk"])
        if r.returncode:
            say("worktree add failed:", r.stderr.strip()); return 1
        links = subprocess.run(["git", "-C", str(repo), "ls-files", "-s", "research-trunk"], capture_output=True, text=True).stdout
        gitlinks = [l.split()[-1] for l in links.splitlines() if l.startswith("160000")]
        if gitlinks:
            say(f"WARNING: research-trunk keeps {gitlinks[:4]} as gitlinks (nested repos): the worktree has them EMPTY and no edit inside them can be reviewed; "
                f"the owner should track that code as files on research-trunk before any candidate touches it")
    say(f"{qid}: spec gated, card frozen ({card['frozen_sha'][:12]}), worktree {wt}", f"next: python3 .research/step.py build {qid}")
    return 0


# ── critique (Slot 1 sources / Slot 2 spec) ─────────────────────────────────

def critique(kind: str, qid: str | None = None) -> int:
    import critique as cq  # noqa: E402
    d = cq.cmd_sources() if kind == "sources" else cq.cmd_spec(qid)
    p = HERE / "bundles" / ("args-critique-sources.json" if kind == "sources" else f"args-critique-{qid}.json")
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    out = HERE / "bundles" / ("critique-sources-out.json" if kind == "sources" else f"critique-out-{qid}.json")
    say(f"Workflow(name='critique', args=<contents of {p}>)   # critic-sol ∥ critic-k3 ∥ critic-glm, save the returned JSON to {out}",
        f"then: python3 .research/step.py critique --finish {kind}{' ' + qid if qid else ''} {out}")
    return 0


def critique_finish(kind: str, qid: str | None, out_path: str) -> int:
    import critique as cq  # noqa: E402
    out = stage._json(Path(out_path))
    panel = out.get("panel") if isinstance(out.get("panel"), dict) else {}
    key = "sources" if kind == "sources" else qid
    args = stage._json(HERE / "bundles" / ("args-critique-sources.json" if kind == "sources" else f"args-critique-{qid}.json"))
    text = str(args.get("prompt") or "")
    (HERE / "critique").mkdir(exist_ok=True)
    if not any(isinstance(v, dict) for v in panel.values()) or not text:
        infra_p = HERE / "critique" / f"{key}.infra"
        n = int(infra_p.read_text().strip() or 0) + 1 if infra_p.exists() else 1
        infra_p.write_text(f"{n}\n")
        Path(out_path).rename(Path(out_path).with_suffix(f".null{n}.json"))
        if n >= 2 and kind == "spec":
            say(f"{qid}: critique panel returned nothing twice → python3 .research/bundle.py queue {qid} \"critique panel returned nothing twice (infrastructure)\"")
        else:
            say(f"critique {key}: no family answered (infrastructure failure, not a verdict) → python3 .research/step.py critique {kind}{' ' + qid if qid else ''}")
        return 1
    if kind == "sources":
        agg = cq.aggregate_sources(panel, text, list(args.get("ids") or []))
        mp = stage._json(HERE / "mechanism-map.json")
        counts = cq.apply_sources(mp, agg)
        (HERE / "mechanism-map.json").write_text(json.dumps(mp, indent=1, ensure_ascii=False))
        say(f"critique sources: {counts}", *[f"  {sid}: {a['decision']} · rank {a['rank_mean']}{' · contested' if a['contested'] else ''} · " +
                                            ", ".join(f"{f}={v['verdict']}" + (f"[{','.join(v['fails'])}]" if v['fails'] else "") for f, v in a["panel"].items())
                                            for sid, a in agg.items()], "next: python3 .research/stage.py")
        return 0
    agg = cq.aggregate_spec(panel, text)
    rec = {**agg, "qid": qid, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (HERE / "critique" / f"{qid}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    per = " · ".join(f"{f}={v['verdict']}→{v['effective']} ({v['anchored']} anchored, {v['unanchored']} dropped)" for f, v in agg["per_model"].items())
    if agg["verdict"] == "advance":
        say(f"{qid}: critique ADVANCE — {per}", f"next: python3 .research/step.py propose --finish {qid}"); return 0
    fails = [f"{f['family']}/{f['check']} [{f['severity']}]: {f['text']} — \"{str(f['quote'])[:120]}\"" for f in agg["findings"]]
    if agg["verdict"] == "revise":
        (HERE / "gates" / f"{qid}.critique.fail.json").write_text(json.dumps({"fails": fails, "revision_target": agg["revision_target"]}, indent=1, ensure_ascii=False))
        chain = qid.split("-")[-1]
        nxt = f"python3 .research/bundle.py queue {qid} \"critique panel asked for a revision twice\"" if (HERE / "gates" / f"{qid}.spec.retries").exists() else f"python3 .research/step.py propose {chain} --retry"
        say(f"{qid}: critique REVISE — {per}", *[f"  - {x}" for x in fails[:6]], f"next: {nxt}"); return 1
    src = args.get("source")
    pen = cq.penalize_source(src, f"{qid}: " + "; ".join(fails[:3])) if src else None
    r = py(str(HERE / "bundle.py"), "queue", qid, "critique panel: abandon — " + "; ".join(fails[:3])[:400])
    say(f"{qid}: critique ABANDON — {per}", *[f"  - {x}" for x in fails[:6]], f"source {src}: {pen}" if pen else f"source {src}: not penalised (not open/tried)", r.stdout.strip()[:200], "next: python3 .research/stage.py"); return 1


# ── build ───────────────────────────────────────────────────────────────────

def build(qid: str, fix: bool = False) -> int:
    r = py(str(HERE / "bundle.py"), "build", qid, *(["--fix"] if fix else []))
    if r.returncode:
        say(r.stderr.strip()); return 1
    (HERE / "bundles" / f"args-build-{qid}.json").write_text(r.stdout)
    say(f"Workflow(name='build', args=<contents of .research/bundles/args-build-{qid}.json>)   # builder (GLM) → Grok plugin review",
        f"save the returned JSON to .research/bundles/build-out-{qid}.json, then: python3 .research/step.py build --finish {qid} .research/bundles/build-out-{qid}.json")
    return 0


def build_finish(qid: str, out_path: str, gpu: int | None = None) -> int:
    out_p = Path(out_path)
    out = stage._json(out_p)
    card = stage._json(HERE / "cards" / f"{qid}.json")
    (HERE / "build").mkdir(exist_ok=True)
    mon_p = HERE / "monitor" / f"{qid}.json"
    fresh = bool(out.get("monitor")) and (not mon_p.exists() or out_p.stat().st_mtime > mon_p.stat().st_mtime)
    ext = (out.get("monitor") or {}).get("external")
    if fresh and (out.get("build") is None or ext is None or not ext.get("available")):
        infra_p = HERE / "build" / f"{qid}.infra"
        n_infra = int(infra_p.read_text().strip() or 0) + 1 if infra_p.exists() else 1
        infra_p.write_text(f"{n_infra}\n")
        out_p.rename(out_p.with_suffix(f".null{n_infra}.json"))          # not a verdict: never gate an empty output
        if n_infra >= 2:
            say(f"{qid}: builder or the external review returned nothing twice → python3 .research/bundle.py queue {qid} \"build workflow returned nothing twice (infrastructure)\"")
        else:
            say(f"{qid}: builder or the external review returned nothing / unavailable (infrastructure failure, not a rejection) → python3 .research/step.py build {qid}{' --fix' if (HERE / 'build' / f'{qid}.fixes').exists() else ''}")
        return 1
    if fresh:
        (HERE / "build" / f"{qid}.json").write_text(json.dumps(out.get("build") or {}, indent=1, ensure_ascii=False))
    if fresh or not (stage._json(mon_p).get("approved") and stage._json(mon_p).get("diff_sha")):
        tmp = HERE / "bundles" / f"monitor-out-{qid}.json"
        tmp.write_text(json.dumps(out.get("monitor") or {}, indent=1, ensure_ascii=False))
        r = py(str(HERE / "gate.py"), "monitor", qid, str(tmp))
        say(r.stdout.strip())
        if r.returncode:
            fixes = (HERE / "build" / f"{qid}.fixes")
            if fixes.exists():
                say(f"→ python3 .research/bundle.py queue {qid} \"monitor rejected twice\"")
            else:
                say(f"→ python3 .research/step.py build {qid} --fix   # one fix round, then queue")
            return 1
    import gate  # noqa: E402
    _, sha_now = gate.diff_of(card["worktree"])
    if sha_now != stage._json(mon_p).get("diff_sha"):
        for p in (HERE / "tokens" / f"{qid}.clean", mon_p):
            p.unlink(missing_ok=True)
        say(f"{qid}: the worktree diff changed after the monitor approved it (sha {sha_now[:12]}); token and approval withdrawn → python3 .research/step.py build {qid}")
        return 1
    (HERE / "tokens" / f"{qid}.clean").unlink(missing_ok=True)      # always re-mint: the token names the CURRENT diff sha
    r = py(str(HERE / "bundle.py"), "token", qid)
    if r.returncode:
        say(r.stderr.strip()); return 1
    if stage.unit_active(qid):
        say(f"research-{qid}.service already active — wait"); return 0
    if stage.last_exit(HERE, qid) == 5:
        (HERE / "build" / f"{qid}.relaunched").write_text("1\n")   # one relaunch after a stall; the navigator queues the second
    claim = stage.load_claim(W) or {}
    g = gpu if gpu is not None else int((claim.get("chains") or {}).get(qid.split("-")[-1], {}).get("gpu", 0))
    env = {**os.environ, "GPU": str(g), "SEEDS": "0"}
    r = subprocess.run(["bash", str(W / "bin" / "run_protected.sh"), qid, qid, "40G", card["kill"]["cmd"]], cwd=str(W), env=env, capture_output=True, text=True)
    say(r.stdout.strip(), r.stderr.strip(), f"{'launched' if r.returncode == 0 else 'launch REFUSED'}: research-{qid}.service on GPU {g} (smoke phase first, then the kill test)")
    return r.returncode


# ── record ──────────────────────────────────────────────────────────────────

def record(qid: str, gpu: int | None = None) -> int:
    card = stage._json(HERE / "cards" / f"{qid}.json")
    wt = Path(card["worktree"])
    res = wt / "results" / qid
    conf = wt / "results" / f"{qid}-confirm"
    if stage.unit_active(qid) or stage.unit_active(f"{qid}-confirm"):
        say(f"a unit for {qid} is still active — wait"); return 0
    for sp in conf.glob("seed_*.json") if conf.exists() else []:
        shutil.copy2(sp, res / sp.name)
    if not any(res.glob("seed_*.json")) if res.exists() else True:
        say(f"no seed files under {res}: the unit produced nothing (see journalctl --user -u research-{qid}.service); notebook error, next candidate")
        return 1
    r = py(str(HERE / "render_record.py"), qid, str(HERE / "cards" / f"{qid}.json"), str(res))
    say(r.stdout.strip() or r.stderr.strip())
    if r.returncode:
        return 1
    r = py(str(HERE / "gate.py"), "record", str(HERE / "records" / f"{qid}.json"), str(HERE / "cards" / f"{qid}.json"))
    say("record gate: " + (r.stdout.strip() or r.stderr.strip()))
    gate_ok = r.returncode == 0
    rec_p = HERE / "records" / f"{qid}.json"
    rec = stage._json(rec_p)
    rec["gate_pass"] = gate_ok                                   # script-written: the verdict every reader consumes (stage.valid)
    rec["gate_fails"] = [l for l in (r.stdout.strip().splitlines()[1:] if not gate_ok else [])][:8]
    rec_p.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    if not gate_ok:
        why = "record refused by gate.py record: " + "; ".join(rec["gate_fails"])[:300]
        r3 = py(str(HERE / "bundle.py"), "queue", qid, why)
        say(r3.stdout.strip() or r3.stderr.strip(), f"{qid}: not counted (no notebook/map update); the chain moves on. Owner: queue.json")
        return 1
    r2 = py(str(HERE / "bundle.py"), "notebook", qid)
    say(r2.stdout.strip() or r2.stderr.strip())
    if r2.returncode:
        say(f"{qid}: notebook/map update failed; stage.py will print `bundle.py notebook {qid}` until it lands"); return 1
    claim = stage.load_claim(W) or {}
    need = int(claim.get("seeds_for_keep", 3))
    missing = [k for k in range(need) if not (res / f"seed_{k}.json").exists()]
    if rec.get("band_hit") and not rec.get("early_kill") and missing:
        att_p = HERE / "build" / f"{qid}.confirm_attempts"
        n_att = int(att_p.read_text().strip() or 0) if att_p.exists() else 0
        if n_att >= 2:
            r3 = py(str(HERE / "bundle.py"), "queue", qid, f"confirm launched twice, still missing seeds {missing} (unit exit {stage.last_exit(HERE, f'{qid}-confirm')})")
            say(r3.stdout.strip() or r3.stderr.strip()); return 1
        g = gpu if gpu is not None else int((claim.get("chains") or {}).get(qid.split("-")[-1], {}).get("gpu", 0))
        seeds = ",".join(str(s) for s in missing)
        env = {**os.environ, "GPU": str(g), "SEEDS": seeds}
        r = subprocess.run(["bash", str(W / "bin" / "run_protected.sh"), f"{qid}-confirm", qid, "40G", card["kill"]["cmd"]], cwd=str(W), env=env, capture_output=True, text=True)
        if r.returncode == 0:
            att_p.write_text(f"{n_att + 1}\n")
        say(r.stdout.strip(), r.stderr.strip(), f"band hit → {'launched' if r.returncode == 0 else 'REFUSED'} research-{qid}-confirm.service (SEEDS={seeds}, attempt {n_att + 1}); re-run `step.py record {qid}` when it ends")
        return r.returncode
    say(f"{qid}: {'KEEP candidate confirmed' if rec.get('band_hit') and int(rec.get('n_realized', 0)) >= need else 'recorded'}; next: python3 .research/stage.py")
    return 0 if gate_ok else 1


def write_start(mode: str) -> int:
    r = py(str(HERE / "bundle.py"), "write", *(["--merge"] if mode == "merge" else ["--review"] if mode == "review" else []))
    if r.returncode:
        say(r.stderr.strip()); return 1
    (HERE / "bundles" / "args-write.json").write_text(r.stdout)
    say(f"Workflow(name='write', args=<contents of .research/bundles/args-write.json>)   # mode {mode}; save the returned JSON to .research/bundles/write-out.json",
        "then: python3 .research/step.py write --finish .research/bundles/write-out.json")
    return 0


def write_finish(out_path: str) -> int:
    import outer, paper_ledger as L  # noqa: E402
    out = stage._json(Path(out_path))
    mode = out.get("mode") or stage._json(HERE / "bundles" / "args-write.json").get("mode") or "sections"
    (HERE / "gates").mkdir(exist_ok=True)
    if mode == "merge":
        main = outer.paper_dir(W) / "main.tex"
        if not main.exists():
            say(f"merge: {main} was not written (infrastructure or NEEDS_CONTEXT): re-run python3 .research/step.py write --merge"); return 1
        say(f"merged manuscript at {main}", "next: python3 .research/stage.py"); return 0
    rev = out.get("review") if isinstance(out.get("review"), dict) else None
    if not rev or rev.get("verdict") not in ("pass", "block"):
        (HERE / "gates" / "write-review.json").unlink(missing_ok=True)
        say("write workflow returned no review verdict (infrastructure failure, not a pass): re-run Workflow(write)"); return 1
    rev = {**rev, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "written": out.get("written"), "mode": mode}
    (HERE / "gates" / "write-review.json").write_text(json.dumps(rev, indent=1, ensure_ascii=False))
    led = L.load(HERE)
    rd = L.current_round(led) or L.start_round(led, 0)
    L.save(led, HERE)
    k = outer.intake_review(HERE, rd["n"], rev)
    say(f"fact review: {rev['verdict']}" + ("" if rev["verdict"] == "pass" else " — " + "; ".join(str(x) for x in (rev.get("issues") or [])[:5])),
        f"ledger: {L.summary(L.load(HERE))}" + (f" · {k} review issues became valid-fixable rows" if k else ""), "next: python3 .research/stage.py")
    return 0 if rev["verdict"] == "pass" else 1


def outer_start(kind: str, rnd: int) -> int:
    import outer  # noqa: E402
    d = outer.cmd_read(W, rnd) if kind == "read" else outer.cmd_trial(W, HERE, rnd) if kind == "trial" else outer.cmd_draft(W, HERE, rnd)
    p = HERE / "bundles" / f"args-{kind}.json"
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    out = HERE / "bundles" / f"{kind}-out-{rnd}.json"
    say(f"Workflow(name='{kind}', args=<contents of {p}>)   # save the returned JSON to {out}", f"then: python3 .research/step.py {kind} --finish {rnd} {out}")
    return 0


def outer_finish(kind: str, rnd: int, out_path: str) -> int:
    import outer  # noqa: E402
    out = stage._json(Path(out_path))
    if not out:
        say(f"{kind} round {rnd}: the workflow returned nothing (infrastructure, not a verdict) → python3 .research/step.py {kind} {rnd}"); return 1
    res = outer.finish_read(W, HERE, rnd, out) if kind == "read" else outer.finish_trial(HERE, rnd, out) if kind == "trial" else outer.finish_draft(W, HERE, rnd, out)
    if res.get("error"):
        Path(out_path).rename(Path(out_path).with_suffix(".null.json"))
        say(f"{kind} round {rnd}: {res['error']} (infrastructure) → python3 .research/step.py {kind} {rnd}"); return 1
    import paper_ledger as L  # noqa: E402
    say(f"{kind} round {rnd}: {res}", f"ledger: {L.summary(L.load(HERE))}", "next: python3 .research/stage.py")
    return 0


def pivot_finish(out_path: str) -> int:
    out = stage._json(Path(out_path))
    (HERE / "gates").mkdir(exist_ok=True)
    if not out.get("verdict"):
        say(f"pivot workflow returned no verdict ({out.get('error') or 'empty'}): infrastructure failure, not an exit — re-run Workflow(pivot)"); return 1
    p = HERE / "gates" / f"pivot-{time.strftime('%Y%m%dT%H%M%S')}.json"
    p.write_text(json.dumps({**out, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1, ensure_ascii=False))
    say(f"pivot verdict saved to {p}: {out['verdict']}", *[f"  - {x}" for x in (out.get("reasons") or [])[:5]],
        "owner: (a) ship the incumbent, (b) edit CLAIM.md and re-accept, (c) python3 .research/step.py mechanism  (new_sources: the associations feed the next map)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("mechanism"); p.add_argument("--finish")
    p = sub.add_parser("propose"); p.add_argument("chain", nargs="?"); p.add_argument("--finish"); p.add_argument("out", nargs="?"); p.add_argument("--retry", action="store_true"); p.add_argument("--rung")
    p = sub.add_parser("critique", help="critique sources | critique spec <Q> | critique --finish sources <out> | critique --finish spec <Q> <out>")
    p.add_argument("kind", choices=["sources", "spec"]); p.add_argument("rest", nargs="*"); p.add_argument("--finish", action="store_true")
    p = sub.add_parser("write"); p.add_argument("--finish"); p.add_argument("--merge", action="store_true"); p.add_argument("--review", action="store_true")
    for name in ("read", "trial", "draft"):
        p = sub.add_parser(name, help=f"outer loop: {name} <round> | {name} --finish <round> <out>"); p.add_argument("round", type=int); p.add_argument("out", nargs="?"); p.add_argument("--finish", action="store_true")
    p = sub.add_parser("pivot"); p.add_argument("--finish", required=True)
    p = sub.add_parser("status"); p.add_argument("qid")
    p = sub.add_parser("build"); p.add_argument("qid"); p.add_argument("--finish"); p.add_argument("--fix", action="store_true"); p.add_argument("--gpu", type=int)
    p = sub.add_parser("record"); p.add_argument("qid"); p.add_argument("--gpu", type=int)
    a = ap.parse_args()
    hook = W / ".claude" / "hooks" / "session-lock.py"          # single writer: refuse under another live session, take over a dead/stale one
    if a.cmd != "status" and hook.exists() and subprocess.run([sys.executable, str(hook), "--check", str(os.getpid())]).returncode:
        return 1
    for d in ("bundles", "gates", "build", "monitor", "tokens", "records", "cards", "critique"):
        (HERE / d).mkdir(exist_ok=True)
    if a.cmd == "mechanism":
        return mechanism(a.finish)
    if a.cmd == "propose":
        return propose_finish(a.finish, a.out or a.chain) if a.finish else propose(a.chain, a.retry, a.rung)
    if a.cmd == "critique":
        qid = a.rest[0] if a.kind == "spec" and a.rest else None
        out = (a.rest[1] if a.kind == "spec" else (a.rest[0] if a.rest else None)) if a.finish else None
        if a.kind == "spec" and not qid or (a.finish and not out):
            say("usage: critique sources | critique spec <Q> | critique --finish sources <out> | critique --finish spec <Q> <out>"); return 2
        return critique_finish(a.kind, qid, out) if a.finish else critique(a.kind, qid)
    if a.cmd == "write":
        return write_finish(a.finish) if a.finish else write_start("merge" if a.merge else "review" if a.review else "sections")
    if a.cmd in ("read", "trial", "draft"):
        if a.finish and not a.out:
            say(f"usage: {a.cmd} --finish <round> <out>"); return 2
        return outer_finish(a.cmd, a.round, a.out) if a.finish else outer_start(a.cmd, a.round)
    if a.cmd == "pivot":
        return pivot_finish(a.finish)
    if a.cmd == "status":
        card = stage._json(HERE / "cards" / f"{a.qid}.json")
        for run in (a.qid, f"{a.qid}-confirm"):
            say(f"{run}: {'ACTIVE' if stage.unit_active(run) else 'not running'} · {stage.progress_line(card, run)}")
        return 0
    if a.cmd == "build":
        return build_finish(a.qid, a.finish, a.gpu) if a.finish else build(a.qid, a.fix)
    if a.cmd == "record":
        return record(a.qid, a.gpu)
    return 2


if __name__ == "__main__":
    sys.exit(main())
