#!/usr/bin/env python3
"""step.py — the five Main actions of one iteration, each idempotent (WORKFLOW.md §4). stage.py tells Main which one to run.

  mechanism                 → prints the Workflow(mechanism) line (args written to bundles/args-mechanism.json)
  mechanism --finish <out>  → verifies quotes, writes mechanism-map.json
  propose <chain>           → prints the Workflow(spec) line (args written to bundles/args-spec-<Q>.json)
  propose --finish <Q>      → gate.py spec → bundle.py card → gate.py card → gate.py freeze → git worktree add   (retry / queue on failure)
  build <Q> [--fix]         → prints the Workflow(build) line (builder → Grok ∥ Codex inside one workflow)
  build --finish <Q> <out>  → saves build/<Q>.json, verifies the monitor's quotes against the real diff → token → launcher
  record <Q>                → (cp confirm seeds) render_record → gate.py record → notebook + map → launches the confirm seeds on a band hit
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
    say("Workflow(name='mechanism', args=<contents of .research/bundles/args-mechanism.json>)   # Fable (B,M) → K3 (C) → Grok (recipe, precedent)",
        "save the returned JSON to .research/bundles/mechanism-out.json, then: python3 .research/step.py mechanism --finish .research/bundles/mechanism-out.json")
    return 0


# ── propose ─────────────────────────────────────────────────────────────────

def propose(chain: str, retry: bool = False, rung: str | None = None) -> int:
    r = py(str(HERE / "bundle.py"), "spec", "--chain", chain, *(["--retry"] if retry else []), *(["--rung", rung] if rung else []))
    if r.returncode:
        say(r.stderr.strip()); return 1
    d = json.loads(r.stdout)
    (HERE / "bundles" / f"args-spec-{d['qid']}.json").write_text(r.stdout)
    say(f"Workflow(name='spec', args=<contents of .research/bundles/args-spec-{d['qid']}.json>)   # scientist (Fable) writes {d['spec_path']}",
        f"then: python3 .research/step.py propose --finish {d['qid']}")
    return 0


def propose_finish(qid: str, out_path: str | None = None) -> int:
    chain = qid.split("-")[-1]
    spec_p = HERE / "bundles" / f"spec-{qid}.json"
    if not spec_p.exists() and out_path and Path(out_path).exists():
        out = stage._json(Path(out_path))
        if isinstance(out.get("spec"), dict) and out["spec"]:
            spec_p.write_text(json.dumps(out["spec"], indent=1, ensure_ascii=False))     # the returned object is authoritative; Fable's Write is a convenience
    if not spec_p.exists():
        say(f"no spec at {spec_p}: the scientist wrote nothing → python3 .research/bundle.py queue {qid} \"spec workflow returned nothing (infrastructure)\""); return 1
    if not (HERE / "gates" / f"{qid}.spec.ok").exists():
        r = py(str(HERE / "gate.py"), "spec", qid)
        if r.returncode:
            retries = (HERE / "gates" / f"{qid}.spec.retries")
            if retries.exists():
                say("spec gate failed twice:", r.stdout.strip(), f"→ python3 .research/bundle.py queue {qid} \"spec failed the gate twice\"")
                return 1
            say("spec gate failed:", r.stdout.strip(), f"→ python3 .research/step.py propose {chain} --retry   # Fable gets the failure list once")
            return 1
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


# ── build ───────────────────────────────────────────────────────────────────

def build(qid: str, fix: bool = False) -> int:
    r = py(str(HERE / "bundle.py"), "build", qid, *(["--fix"] if fix else []))
    if r.returncode:
        say(r.stderr.strip()); return 1
    (HERE / "bundles" / f"args-build-{qid}.json").write_text(r.stdout)
    say(f"Workflow(name='build', args=<contents of .research/bundles/args-build-{qid}.json>)   # builder (GLM) → Grok monitor ∥ Codex",
        f"save the returned JSON to .research/bundles/build-out-{qid}.json, then: python3 .research/step.py build --finish {qid} .research/bundles/build-out-{qid}.json")
    return 0


def build_finish(qid: str, out_path: str, gpu: int | None = None) -> int:
    out_p = Path(out_path)
    out = stage._json(out_p)
    card = stage._json(HERE / "cards" / f"{qid}.json")
    (HERE / "build").mkdir(exist_ok=True)
    mon_p = HERE / "monitor" / f"{qid}.json"
    fresh = bool(out.get("monitor")) and (not mon_p.exists() or out_p.stat().st_mtime > mon_p.stat().st_mtime)
    if fresh and (out.get("build") is None or (out.get("monitor") or {}).get("grok") is None):
        infra_p = HERE / "build" / f"{qid}.infra"
        n_infra = int(infra_p.read_text().strip() or 0) + 1 if infra_p.exists() else 1
        infra_p.write_text(f"{n_infra}\n")
        out_p.rename(out_p.with_suffix(f".null{n_infra}.json"))          # not a verdict: never gate an empty output
        if n_infra >= 2:
            say(f"{qid}: builder/monitor returned nothing twice → python3 .research/bundle.py queue {qid} \"build workflow returned nothing twice (infrastructure)\"")
        else:
            say(f"{qid}: builder or monitor lens returned nothing (infrastructure failure, not a rejection) → python3 .research/step.py build {qid}{' --fix' if (HERE / 'build' / f'{qid}.fixes').exists() else ''}")
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


def write_finish(out_path: str) -> int:
    out = stage._json(Path(out_path))
    rev = out.get("review") if isinstance(out.get("review"), dict) else None
    (HERE / "gates").mkdir(exist_ok=True)
    if not rev or rev.get("verdict") not in ("pass", "block"):
        (HERE / "gates" / "write-review.json").unlink(missing_ok=True)
        say("write workflow returned no review verdict (infrastructure failure, not a pass): re-run Workflow(write)"); return 1
    rev = {**rev, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "written": out.get("written")}
    (HERE / "gates" / "write-review.json").write_text(json.dumps(rev, indent=1, ensure_ascii=False))
    say(f"final review: {rev['verdict']}" + ("" if rev["verdict"] == "pass" else " — " + "; ".join(str(x) for x in (rev.get("issues") or [])[:5])), "next: python3 .research/stage.py")
    return 0 if rev["verdict"] == "pass" else 1


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
    p = sub.add_parser("write"); p.add_argument("--finish", required=True)
    p = sub.add_parser("pivot"); p.add_argument("--finish", required=True)
    p = sub.add_parser("status"); p.add_argument("qid")
    p = sub.add_parser("build"); p.add_argument("qid"); p.add_argument("--finish"); p.add_argument("--fix", action="store_true"); p.add_argument("--gpu", type=int)
    p = sub.add_parser("record"); p.add_argument("qid"); p.add_argument("--gpu", type=int)
    a = ap.parse_args()
    for d in ("bundles", "gates", "build", "monitor", "tokens", "records", "cards"):
        (HERE / d).mkdir(exist_ok=True)
    if a.cmd == "mechanism":
        return mechanism(a.finish)
    if a.cmd == "propose":
        return propose_finish(a.finish, a.out or a.chain) if a.finish else propose(a.chain, a.retry, a.rung)
    if a.cmd == "write":
        return write_finish(a.finish)
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
