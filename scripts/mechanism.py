#!/usr/bin/env python3
"""mechanism.py — stage M bundles and the finish script (A → B → M → C → recipe gene + precedent; Sparking.md, WORKFLOW-V4 §12.2).
`cmd_M` builds the scientist's B→M prompt and the workflow args; `cmd_mechanism_finish` turns the workflow's output into
`mechanism-map.json`: every quote re-checked at its line (`_quote_at`), ungrounded failure modes and domain-bound mechanisms dropped,
sources without a procedure or with a verified precedent dropped, the hill-climb memory of an earlier map preserved.
Functions that read loop state take `B`, the bundle namespace (paths, readers, prompt builder): bundle.py passes its own at call
time, so a test that monkeypatches bundle.HERE / bundle.W is honoured and there is no import cycle. Reached as `bundle.cmd_M` /
`bundle.cmd_mechanism_finish`.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path
import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import stage  # noqa: E402
import gapmap  # noqa: E402
import gate  # noqa: E402


def _a_terms(c: dict) -> list[str]:
    """Domain terms of A for the precedent search: CLAIM `a_terms`, else the longest words of the claim sentence."""
    if c.get("a_terms"):
        return [str(t) for t in c["a_terms"]]
    import gate
    terms = [str(n) for n in (c.get("networks") or [])] + gate.held_out_terms(c)
    return terms[:6] or [str(c.get("metric", "the target task"))]


def cmd_M(B) -> dict:
    c = B._claim()
    anomalies = (B.HERE / "anomalies.md").read_text(encoding="utf-8") if (B.HERE / "anomalies.md").exists() else "(no anomalies file; ground B in the claim's evidence table only)"
    bundle = {"claim": B._claim_core(), "anomalies": anomalies, "held_out": c.get("held_out"), "metric": c.get("metric")}
    task = ("按 A→B→M 做三层：(1) 列出 2–4 个失败模式 B：现有方法为什么满足不了 claim，每条必须引用 anomalies 或 claim 证据表里的一条测量（grounded_in），"
            "不引用测量的 B 不要写；(2) 对每个 B 做三层抽象得到机制 M：连问三次“去掉领域名词后本质是什么”，把三层都写出来，最后一层是一句不含 RGB/深度/分割等领域词的机制陈述。"
            "第一性原理：observation → failure mode → mechanism；不要用 domain adaptation / fusion 这类领域标签当机制。不要提任何解决方法，不要提任何论文。返回 {\"failure_modes\": [{\"id\": \"B1\", \"text\": \"\", \"grounded_in\": [\"\"]}], "
            "\"mechanisms\": [{\"id\": \"M1\", \"from\": \"B1\", \"levels\": [\"\", \"\", \"\"], \"text\": \"\"}]}。")
    task += "\n" + "\n".join([                                    # docs/prompt-bank: ResearchStudio bottleneck_identify F01-F05, ccf framework S1.1/S1.3/S1.5
        "Rules for B (verbatim from the sources this loop was built on):",
        "- Problem-level, not solution-level. Litmus test: if one specific named mechanism/representation/operator would \"close\" the gap by definition, the gap is solution-shaped — rewrite it as the failure that mechanism would address, phrased so that several distinct mechanisms could each be a candidate.",
        "- State the FAILURE (what breaks, under what condition, and why the current machinery cannot produce the needed quantity), NOT the absence of a specific cure.",
        "- Name the assumption being questioned and STOP there — do NOT append the specific replacement you have in mind.",
        "- The mattering test: every B carries an inline stakes clause — a practitioner scenario or an intellectual cost (invalid conclusions, non-transferring results, blocked principled design). If you can name neither, the entry is retrieval negative-space and must not be emitted.",
        "- Each B ends with the forcing sentence filled in: \"Everyone had always believed ______, but the real problem might actually be ______.\"",
        "- grounded_in entries are 【Explicitly stated in anomalies / CLAIM】 measurements; do not present inference as fact.",
        "Rules for M:",
        "- Structural-property framing (class over instance): write the last level as a STRUCTURAL PROPERTY of a problem class when one honestly exists, then name A as the PRIMARY INSTANCE where the property bites. The honesty constraint is absolute: if the failure genuinely is specific to one system's quirk, say so plainly — manufacturing fake generality is itself an overclaim.",
        "- Say for each M whether it is fundamentally adding something, or removing an unnecessary assumption.",
    ])
    B._assert_size("M", bundle)
    return {"prompt_fable": B._prompt(task, bundle, {"failure_modes": [{"id": "B1", "text": "", "grounded_in": [""]}], "mechanisms": [{"id": "M1", "from": "B1", "levels": ["", "", ""], "text": ""}]}),
            "claim": c.get("sentence", ""), "held_out": c.get("held_out"), "a_terms": _a_terms(c), "library": str(B._repo() / "papers"),
            "search": B.SEARCH, "fetch": ".research/fetch_text.py", "papers_dir": str(B.HERE / "lit" / "papers"),
            "max_sources_per_mechanism": 3, "max_papers_per_source": 3, "precedent_max": 2, "out": str(B.HERE / "bundles" / "mechanism-out.json")}


def _grounded(g: str, ground_txt: str) -> bool:
    """A grounded_in entry counts when its normalised text (>= 12 chars) is a substring of anomalies.md + CLAIM.md, or when
    every number it quotes appears there (a measurement can be cited by its value)."""
    n = gapmap.norm(g)
    if len(n) >= 12 and n in ground_txt:
        return True
    nums = re.findall(r"\d+(?:\.\d+)?", g)
    return bool(nums) and all(gapmap.norm(x) in ground_txt for x in nums)


def _domain_stoplist(c: dict) -> list[str]:
    """Words that mean the mechanism or query is still inside A (Sparking: 'strip the domain nouns'): A terms, networks, held-out words."""
    import gate
    base = ["rgb-d", "rgbd", "depth", "segmentation", "miou", "rgb"]
    return sorted({w.lower() for w in base + [str(t) for t in (c.get("a_terms") or [])] + [str(n) for n in (c.get("networks") or [])] + gate.held_out_terms(c)} - {"structured"})


def _domain_words(text: str, stop: list[str]) -> list[str]:
    low = str(text or "").lower()
    return [w for w in stop if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low)]


def _quote_at(paper_txt: str, quote: str, line: int, window: int = 3, min_words: int = 6) -> bool:
    """The quote's first words appear (whitespace-normalised, case-insensitive) within ±window lines of `line`. pdftotext breaks
    lines mid-sentence, so the check joins the window and uses the first min_words words of the quote."""
    lines = paper_txt.split("\n")
    if line < 1 or line > len(lines):
        return False
    seg = re.sub(r"\s+", " ", " ".join(lines[max(0, line - 1 - window):line + window])).lower()
    words = re.sub(r"\s+", " ", quote).strip().lower().split(" ")
    if not words:
        return False
    return " ".join(words[:min_words]) in seg


def cmd_mechanism_finish(B, out_path: str) -> dict:
    out = json.loads(Path(out_path).read_text())
    if out.get("error") or not out.get("failure_modes"):
        nb = B._notebook(); nb.append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": "error", "run": "mechanism", "text": f"mechanism workflow returned nothing usable: {out.get('error') or 'no failure modes'} (infrastructure, not a verdict)"})
        (B.HERE / "notebook.json").write_text(json.dumps(nb, indent=1, ensure_ascii=False))
        raise SystemExit(f"mechanism workflow: {out.get('error') or 'no failure modes returned'} — infrastructure failure, the map is NOT written; re-run: python3 .research/step.py mechanism")
    stop = _domain_stoplist(B._claim())
    old = B._map() if (B.HERE / "mechanism-map.json").exists() else {}
    old_by_key = {(str(s.get("domain")).lower() + "|" + str(s.get("name")).lower()): s for s in (old.get("sources") or [])}
    ground_txt = gapmap.norm(((B.HERE / "anomalies.md").read_text(encoding="utf-8") if (B.HERE / "anomalies.md").exists() else "")
                             + " " + ((B.W / "CLAIM.md").read_text(encoding="utf-8") if (B.W / "CLAIM.md").exists() else ""))
    fms, bad_b = [], set()
    for fm in out.get("failure_modes") or []:
        hits = [g for g in (fm.get("grounded_in") or []) if _grounded(str(g), ground_txt)]
        if hits:
            fms.append({**fm, "grounded_in": hits})
        else:
            bad_b.add(str(fm.get("id"))); fms.append({**fm, "status": "dropped", "drop_reason": "no grounded_in entry is found in anomalies.md / CLAIM.md (a failure mode is a measurement, not an opinion)"})
    mechs, bad_m = [], set()
    for m in out.get("mechanisms") or []:
        last = (m.get("levels") or [""])[-1]
        dw = _domain_words(f"{last} {m.get('text', '')}", stop)
        if str(m.get("from")) in bad_b:
            bad_m.add(str(m.get("id"))); mechs.append({**m, "status": "dropped", "drop_reason": f"its failure mode {m.get('from')} is ungrounded"})
        elif dw:
            bad_m.add(str(m.get("id"))); mechs.append({**m, "status": "dropped", "drop_reason": f"not domain-free: still says {dw} (Sparking: strip the domain nouns three times)"})
        else:
            mechs.append(m)
    sources, dropped, errors = [], [], []
    used_ids = {str(s.get("id")) for s in (old.get("sources") or [])}
    n_new = 0
    for s in out.get("sources") or []:
        key = str(s.get("domain")).lower() + "|" + str(s.get("name")).lower()
        prev = old_by_key.get(key)
        if prev:
            sid = prev["id"]
        else:
            n_new += 1
            while f"S{len(used_ids) + n_new}" in used_ids:
                n_new += 1
            sid = f"S{len(used_ids) + n_new}"
        rec = s.get("recipe")
        if rec is None or s.get("error"):
            errors.append({"id": sid, "mechanism": s.get("mechanism"), "domain": s.get("domain"), "name": s.get("name"), "isomorphism": s.get("isomorphism"),
                           "disanalogy": s.get("disanalogy"), "naive_in_A": s.get("naive_in_A"), "pattern": s.get("pattern"), "query": s.get("query"),
                           "status": "error", "drop_reason": f"retrieval returned nothing: {s.get('error') or 'no recipe object'} (infrastructure; re-run step.py mechanism to retry)",
                           "best": None, "no_improve": 0, "tried": []})
            continue
        rec = rec or {}
        kn = rec.get("key_number") or {}
        fails = []
        raw_steps = rec.get("steps") or []
        steps_txt = [st if isinstance(st, str) else str((st or {}).get("text") or "") for st in raw_steps]
        step_quotes = [{"quote": st.get("quote"), "line": st.get("line")} for st in raw_steps if isinstance(st, dict)]
        if str(s.get("mechanism")) in bad_m:
            fails.append(f"mechanism {s.get('mechanism')} rests on an ungrounded or domain-bound failure mode")
        qw = _domain_words(s.get("query", ""), stop)
        if qw:
            fails.append(f"query is not cross-domain: contains {qw}")
        if not [s_ for s_ in steps_txt if s_.strip()]:
            fails.append("no procedure steps (a name is not a recipe)")
        if not str(s.get("disanalogy", "")).strip():
            fails.append("no disanalogy (which assumption of C fails in A)")
        txt = rec.get("text_path")
        if txt and Path(txt).exists() and kn.get("line"):
            paper_txt = Path(txt).read_text(errors="ignore")
            fm = {"provenance": {"stated": [{"claim": f"{kn.get('value', '')} {kn.get('quote', '')}", "line": int(kn["line"])}]}}
            fails += gapmap.check_line_refs(fm, paper_txt)
            if kn.get("quote") and not _quote_at(paper_txt, str(kn["quote"]), int(kn["line"])):
                fails.append(f"key_number quote is not at line {kn['line']} of {Path(txt).name}")
            for i, sq in enumerate(step_quotes, 1):        # v4: every step carries its own quote and line; an invented one costs the source
                if sq.get("quote") and not _quote_at(paper_txt, str(sq["quote"]), int(sq.get("line") or 0)):
                    fails.append(f"step {i} quote is not at line {sq.get('line')} of {Path(txt).name}")
            aq = rec.get("avoid_quote") or {}
            if isinstance(aq, dict) and aq.get("quote") and not _quote_at(paper_txt, str(aq["quote"]), int(aq.get("line") or 0)):
                fails.append(f"avoid quote is not at line {aq.get('line')} of {Path(txt).name}")
        elif kn and (kn.get("quote") or kn.get("line")):
            fails.append("key_number has no verifiable text_path/line")
        prec = dict(s.get("precedent") or {})
        if prec.get("found"):
            # an agent's boolean drops nothing on its own: the precedent needs a paper id AND a quote of >= 8 words; with a text_path
            # and line (v4 verifier) the quote must also be there
            ptxt = prec.get("text_path")
            at_line = (not ptxt or not Path(str(ptxt)).exists() or not prec.get("line")) or _quote_at(Path(str(ptxt)).read_text(errors="ignore"), str(prec.get("quote", "")), int(prec["line"]))
            if prec.get("paper") and len(str(prec.get("quote", "")).split()) >= 8 and at_line:
                fails.append(f"precedent: {prec.get('paper')} already applies this mechanism to A — {str(prec.get('quote', ''))[:120]}")
            else:
                prec["found"] = False; prec["unverified"] = True
        entry = {"id": sid, "mechanism": s.get("mechanism"), "domain": s.get("domain"), "name": s.get("name"), "isomorphism": s.get("isomorphism"),
                 "disanalogy": s.get("disanalogy"), "naive_in_A": s.get("naive_in_A"), "pattern": s.get("pattern"), "query": s.get("query"),
                 "alias_terms": s.get("alias_terms"), "chain_object": s.get("chain_object"),
                 "recipe": {**{k: rec.get(k) for k in ("paper", "title", "key_number", "text_path", "avoid", "code_url", "disanalogy_to_A", "relation_to_claim", "scooped")},
                            "steps": steps_txt, "step_quotes": step_quotes},
                 "genes": s.get("genes"), "verify": s.get("verify"), "search": s.get("search"),
                 "precedent": prec, "status": "dropped" if fails else "open", "drop_reason": "; ".join(fails) if fails else None,
                 "best": None, "no_improve": 0, "tried": []}
        if prev and not fails:                                   # the hill-climb memory survives a re-run / an owner edit
            for k in ("status", "best", "no_improve", "tried", "queued"):
                if prev.get(k) is not None:
                    entry[k] = prev[k]
            if entry["status"] == "dropped":
                entry["status"] = "open"
        (dropped if fails else sources).append(entry)
    if out.get("sources") and len(errors) * 2 >= len(out.get("sources")):
        raise SystemExit(f"mechanism workflow: {len(errors)}/{len(out['sources'])} sources came back without a recipe object (retrieval lane failed) — infrastructure, the map is NOT written; re-run: python3 .research/step.py mechanism")
    retired = [{**s, "status": "retired", "drop_reason": "not in the latest mechanism run"} for k, s in old_by_key.items()
               if k not in {str(s.get("domain")).lower() + "|" + str(s.get("name")).lower() for s in (out.get("sources") or [])} and s.get("tried")]
    mp = {"made_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "claim_sha": stage.claim_sha(B.W),
          "failure_modes": fms, "mechanisms": mechs, "sources": sources + dropped + errors + retired,
          "infra": out.get("stats"), "runs": int(old.get("runs") or 0) + 1}
    (B.HERE / "mechanism-map.json").write_text(json.dumps(mp, indent=1, ensure_ascii=False))
    return {"open": len(sources), "dropped": [{"id": d["id"], "why": d["drop_reason"]} for d in dropped], "error": [e["id"] for e in errors], "retired": [x["id"] for x in retired]}
