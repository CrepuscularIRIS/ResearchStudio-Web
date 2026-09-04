#!/usr/bin/env python3
"""critique.py — the three-family critique panel and its script aggregation (WORKFLOW-V4 §3, §10.5).

Slot 1 (sources): after `mechanism --finish`, every eligible mechanism-map source that has no `critique` field is judged by
critic-sol (GPT 5.6 sol) ∥ critic-k3 (Kimi K3) ∥ critic-glm (GLM 5.3) — same prompt, isolated, parallel (critique.workflow.js).
Slot 2 (spec): after `gate.py spec` passes and before the card is frozen, one spec gets the same panel; it is blind to Slot 1.

Script rules (the panel proposes, the script decides):
- a check or finding counts only when its anchor is a verbatim substring of the bundle the panel saw (an unanchored drop is a tell);
- Slot 1 drops a source only on a MAJORITY (≥2 families) of anchored fails; one anchored fail → `uncertain` (still eligible);
  ranks are averaged over the families that answered; a spread of at least half the list (min 2) marks the source `contested`, and the
  pick order then falls back to the hill-climb;
- Slot 2 takes the WORST verdict across families (fail-closed; a wrong `abandon` costs patience, never GPU), after each family's
  verdict is capped by its own anchored findings (abandon needs an anchored `blocking`, revise an anchored `major`);
- no aggregate value ever enters KEEP / best / ladder / DONE (ARFT: a score is a new target to game; only records acquit).
"""
from __future__ import annotations
import json, math, re, time
from pathlib import Path

HERE = Path(__file__).resolve().parent

FAMILIES = ("sol", "k3", "glm")
PANEL = {"sol": "critic-sol", "k3": "critic-k3", "glm": "critic-glm"}
SOURCE_CHECKS = ("naive_baseline", "recipe_not_gist", "graveyard_precedent", "falsifiable_at_scale")
SPEC_CHECKS = ("recipe_application", "falsification_structure", "naive_equivalence", "collision", "feasibility")
ORDER = {"abandon": 0, "revise": 1, "advance": 2}
MIN_ANCHOR = 12


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def anchored(anchor: str, text: str) -> bool:
    """A verbatim substring of what the panel saw (whitespace-normalised, case-insensitive), at least MIN_ANCHOR chars."""
    a = _norm(anchor)
    return len(a) >= MIN_ANCHOR and a in _norm(text)


# ── Slot 1 ──────────────────────────────────────────────────────────────────

def aggregate_sources(panel: dict, bundle_text: str, ids: list[str]) -> dict:
    """{id: {decision, rank_mean, contested, panel: {family: {verdict, rank, fails, unanchored}}}} — pure, no I/O."""
    out = {}
    spread_bar = max(2, math.ceil(len(ids) / 2))            # a spread of half the list (at least 2 places) is a real disagreement
    for sid in ids:
        fam_view, ranks, n_drop, n_uncertain = {}, [], 0, 0
        for fam, res in (panel or {}).items():
            if not isinstance(res, dict):
                continue
            entry = next((s for s in (res.get("sources") or []) if isinstance(s, dict) and str(s.get("id")) == sid), None)
            if not entry:
                continue
            fails, unanchored = [], []
            for c in entry.get("checks") or []:
                if not isinstance(c, dict) or c.get("result") != "fail":
                    continue
                (fails if anchored(c.get("anchor", ""), bundle_text) else unanchored).append(str(c.get("name")))
            verdict = str(entry.get("verdict") or "uncertain")
            rank = entry.get("rank")
            rank = int(rank) if isinstance(rank, (int, float)) and rank > 0 else None
            if rank is not None:
                ranks.append(rank)
            if verdict == "drop" and fails:
                n_drop += 1
            elif verdict == "drop" or verdict == "uncertain" or fails:
                n_uncertain += 1
            fam_view[fam] = {"verdict": verdict, "rank": rank, "fails": fails, "unanchored": unanchored}
        decision = "drop" if n_drop >= 2 else ("uncertain" if (n_drop or n_uncertain) else ("keep" if fam_view else "unjudged"))
        rank_mean = round(sum(ranks) / len(ranks), 2) if ranks else None
        contested = len(ranks) >= 2 and (max(ranks) - min(ranks)) >= spread_bar
        out[sid] = {"decision": decision, "rank_mean": rank_mean, "contested": contested, "panel": fam_view}
    return out


def apply_sources(mp: dict, agg: dict, t: str | None = None) -> dict:
    """Write the aggregate into the map (in place) — the only place a critique changes a source's status."""
    t = t or time.strftime("%Y-%m-%dT%H:%M:%S")
    counts = {"keep": 0, "uncertain": 0, "drop": 0, "unjudged": 0}
    for s in mp.get("sources") or []:
        a = agg.get(s.get("id"))
        if not a:
            continue
        s["critique"] = {**a, "t": t}
        counts[a["decision"]] = counts.get(a["decision"], 0) + 1
        if a["decision"] == "drop" and s.get("status") in ("open", "tried"):
            fams = [f for f, v in a["panel"].items() if v["fails"] and v["verdict"] == "drop"]
            checks = sorted({c for f in fams for c in a["panel"][f]["fails"]})
            s["status"] = "dropped"
            s["drop_reason"] = f"critique: {', '.join(checks)} ({', '.join(fams)})"
    return counts


# ── Slot 2 ──────────────────────────────────────────────────────────────────

def _cap(verdict: str, findings: list[dict]) -> str:
    """A family's verdict can be no worse than its own anchored findings support."""
    sev = {str(f.get("severity")) for f in findings}
    v = verdict if verdict in ORDER else "advance"
    if v == "abandon" and "blocking" not in sev:
        v = "revise"
    if v == "revise" and not (sev & {"blocking", "major"}):
        v = "advance"
    return v


def aggregate_spec(panel: dict, bundle_text: str) -> dict | None:
    """{verdict, per_model, findings, revision_target} or None when no family answered (infrastructure, not a verdict)."""
    per, findings, targets = {}, [], []
    for fam, res in (panel or {}).items():
        if not isinstance(res, dict):
            continue
        anc = [f for f in (res.get("findings") or []) if isinstance(f, dict) and anchored(f.get("quote", ""), bundle_text)]
        raw = str(res.get("verdict") or "advance")
        eff = _cap(raw, anc)
        per[fam] = {"verdict": raw, "effective": eff, "anchored": len(anc), "unanchored": len(res.get("findings") or []) - len(anc)}
        findings += [{**f, "family": fam} for f in anc]
        if eff != "advance" and str(res.get("revision_target") or "").strip():
            targets.append(f"{fam}: {res['revision_target']}")
    if not per:
        return None
    verdict = min((v["effective"] for v in per.values()), key=lambda v: ORDER[v])
    return {"verdict": verdict, "per_model": per, "findings": findings, "revision_target": targets}


def penalize_source(sid: str, why: str, patience: int = 2, rdir: Path = HERE) -> dict | None:
    """A spec abandoned by the panel counts as one non-improving version of its source (toward patience, never toward best)."""
    p = rdir / "mechanism-map.json"
    mp = json.loads(p.read_text()) if p.exists() else {}
    src = next((s for s in mp.get("sources") or [] if s.get("id") == sid), None)
    if not src or src.get("status") not in ("open", "tried"):
        return None
    src["no_improve"] = int(src.get("no_improve") or 0) + 1
    src.setdefault("critique_abandons", []).append(why)
    src["status"] = "exhausted" if src["no_improve"] >= patience else "tried"
    p.write_text(json.dumps(mp, indent=1, ensure_ascii=False))
    return {"id": sid, "status": src["status"], "no_improve": src["no_improve"]}


# ── bundles (prompts) ───────────────────────────────────────────────────────

def _bundle_mod():
    import sys
    sys.path.insert(0, str(HERE))
    import bundle  # noqa: E402
    return bundle


SOURCES_SCHEMA = {"sources": [{"id": "S1", "verdict": "keep|drop|uncertain", "rank": 1,
                               "checks": [{"name": "|".join(SOURCE_CHECKS), "result": "pass|fail|unclear",
                                           "anchor": "verbatim substring of the bundle (recipe step / anomaly line / graveyard entry) the result rests on",
                                           "why": "one line"}]}]}
SPEC_SCHEMA = {"verdict": "advance|revise|abandon",
               "findings": [{"check": "|".join(SPEC_CHECKS), "severity": "blocking|major|minor",
                             "quote": "verbatim substring of spec / source / script_facts in the bundle", "text": "one line"}],
               "revision_target": "one line: the single change that would move the verdict (empty on advance)"}


def cmd_sources() -> dict:
    b = _bundle_mod()
    mp = b._map()
    srcs = mp.get("sources") or []
    targets = [s for s in srcs if b._eligible(s) and not s.get("critique")]
    if not targets:
        raise SystemExit("critique sources: every eligible source already carries a critique")
    ids = [s["id"] for s in targets]
    view = [v for v in b._map_view() if v["id"] in ids]
    graveyard = [{k: s.get(k) for k in ("id", "domain", "name", "mechanism", "status", "drop_reason", "no_improve", "best", "tried")}
                 for s in srcs if s["id"] not in ids]
    anomalies = (b.W / ".research" / "anomalies.md")
    bundle = {"claim": b._claim_core(), "sources": view, "graveyard": graveyard,
              "anomalies": anomalies.read_text(encoding="utf-8")[:12000] if anomalies.exists() else "(none)", "avoid": b._avoid_list()}
    task = "\n".join([
        f"你是三家族评审团的一员，只审不设计。对 sources 里每个来源（{', '.join(ids)}）做四项检查（ccf explorer 四项，逐条引用 bundle 原文作 anchor）：",
        "1. naive_baseline — 机制在 A 里最朴素的版本为什么还不够？若朴素版本就能达到，这个来源是增量：fail。",
        "2. recipe_not_gist — recipe_steps 是具体的机制改动（函数 / 损失 / 条件集 / 数字），还是只有名词的新标签？只有要点：fail。",
        "3. graveyard_precedent — graveyard（已试 / 已耗尽 / 已丢弃）或 AVOID 里是否已经执行过同一机制？是：fail，并在 anchor 引用那一条。",
        "4. falsifiable_at_scale — 一次 ≤ 预算的实验能否返回一个杀死它的符号（claim 的 metric、kill bar）？没有这样的实验：fail。",
        "每个 result=fail 必须带 anchor：bundle 里的原文子串（≥12 字符），脚本会核对；没有 anchor 的 fail 不算数。",
        "verdict：drop 只在至少一项 fail 且 anchor 成立时给；拿不准给 uncertain。rank：1 = 最值得先花 GPU 的来源，按'最可能在预算内证伪 claim 且不与 graveyard 重复'排，不按品味。",
        "铁律：不排品味；每个 drop 引一项检查；不新增候选；不改 claim。",
    ])
    prompt = b._prompt(task, bundle, SOURCES_SCHEMA, untrusted=True)
    b._assert_size("critique", {"prompt": prompt})
    return {"mode": "sources", "ids": ids, "panel": PANEL, "prompt": prompt}


def cmd_spec(qid: str) -> dict:
    b = _bundle_mod()
    import stage  # noqa: E402
    c = b._claim()
    spec = stage._json(HERE / "bundles" / f"spec-{qid}.json")
    if not spec:
        raise SystemExit(f"no spec for {qid}")
    chain = qid.split("-")[-1]
    src = next((v for v in b._map_view() if v["id"] == spec.get("source")), None)
    raw_src = next((s for s in b._map().get("sources") or [] if s.get("id") == spec.get("source")), {})
    recs = stage.records(HERE)
    script_facts = {"spec_gate": "passed: gate.py spec (fields, files on research-trunk, held_out not in conditions, gpu_h cap, kill_cmd hygiene, dedup by step fingerprint)",
                    "precedent": raw_src.get("precedent"), "source_status": raw_src.get("status"), "source_no_improve": raw_src.get("no_improve"),
                    "eval_entry": c.get("eval_entry"), "kill_gpu_h_cap": c.get("kill_gpu_h_cap", 4), "keep_gain": c.get("keep_gain"), "seed_sd": c.get("seed_sd"),
                    "kill_threshold": stage.kill_threshold(recs, c), "held_out": c.get("held_out"), "metric": c.get("metric")}
    graveyard = [{k: s.get(k) for k in ("id", "domain", "name", "status", "drop_reason", "no_improve", "best")}
                 for s in b._map().get("sources") or [] if s.get("status") in ("tried", "exhausted", "dropped") and s.get("id") != spec.get("source")]
    bundle = {"claim": b._claim_core(), "spec": spec, "source": src, "script_facts": script_facts, "graveyard": graveyard,
              "chain_history": b._chain_history(chain) or [b.NO_HISTORY], "avoid": b._avoid_list()}
    task = "\n".join([
        f"你是三家族评审团的一员，对 {qid} 的规格做一次执行前裁定（ResearchStudio Phase 3.2 的形状：两层裁定）。只审不设计。五项检查：",
        "1. recipe_application — spec.steps 是否真的执行了 source.recipe_steps 的关键动作，还是绕过（bypassed）只保留了大意？bypassed 是增量输出的首因。",
        "2. falsification_structure — kill_cmd + canary + conditions + expected_gain 能否失败：指标与方向明确、一个承重变量、canary 是真实已知数；不能失败的实验不是实验。",
        "3. naive_equivalence — 自己独立构造机制在 A 里最朴素的版本（不要采用 spec.naive_baseline，它可能是稻草人）；spec 与之等价则 blocking。",
        "4. collision — 与 graveyard / chain_history / AVOID / script_facts.precedent 里任何一条是同一机制则 blocking；相近但有明确差异写 major 并说明差异。",
        "5. feasibility — schedule.gpu_h ≤ kill_gpu_h_cap、files 与 steps 自洽、method_prose 与 steps 一致、不依赖 worktree 外的东西。",
        "两层规则：script_facts 是脚本事实，不得推翻（spec 已过确定性门）；你只定严重度。每条 finding 的 quote 必须是 bundle 里 spec / source / script_facts 的原文子串（≥12 字符），脚本核对；没有 quote 的 finding 不算数。",
        "verdict：abandon 需要至少一条 blocking；revise 需要至少一条 major（并给 revision_target：一句话说明改哪一处能翻转裁定）；其余 advance。默认 advance：只有一处 borderline 且不承重时不 revise。",
        "铁律：不改 spec；不提自己的方案；不评价 claim 本身。",
    ])
    prompt = b._prompt(task, bundle, SPEC_SCHEMA, untrusted=True)
    b._assert_size("critique", {"prompt": prompt})
    return {"mode": "spec", "qid": qid, "source": spec.get("source"), "panel": PANEL, "prompt": prompt}
