#!/usr/bin/env python3
"""build_critic_md.py — assemble critic.md from VERBATIM slices of the sources (never retyped): ARIS reviewer-independence,
experiment-integrity, acceptance-gate, experiment-audit prompt, experiment-bridge review checklist; ASI how-scoring-works +
difficulty ladder + reviewer Dimension 3; ARFT nine iron rules + C.5 per-issue standard + code table rows + judge-guide Rules 1–2;
V8 prereg / self-check refs; Brain's own spec contract sentence. Re-run after any source changes; the test compares the output."""
import re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; WS = HERE.parents[2]; R = WS / "docs" / "refs"


def lines(p): return Path(p).read_text(encoding="utf-8").split("\n")   # never splitlines(): the PDF text carries form feeds that would shift line numbers


def slice_between(p, start_re, end_re=None, inclusive_end=False, max_lines=400):
    L = lines(p); out = []; on = False
    for l in L:
        if not on and re.search(start_re, l): on = True
        if on:
            if end_re and re.search(end_re, l) and out:
                if inclusive_end: out.append(l)
                break
            out.append(l)
            if len(out) >= max_lines: break
    assert out, f"empty slice {p} {start_re}"
    return "\n".join(out).rstrip()


def line_range(p, a, b): L = lines(p); return "\n".join(L[a - 1:b]).rstrip()


def rows(p, codes):
    return "\n".join(l for l in lines(p) if re.match(r"^\| (%s) \|" % "|".join(re.escape(c) for c in codes), l))


def strip_front(p):
    t = Path(p).read_text(encoding="utf-8")
    return re.sub(r"^---[\s\S]*?---\n", "", t, count=1).strip()


def q(title, src, body):
    return f"### {title}\n(source: `{src}`, verbatim)\n\n{body}\n"


aris = R / "aris"; refs = HERE / "refs"; paper = R / "papers" / "arft-2608.14905v2.txt"; guide = R / "papers" / "arft_guide.md"
brain_src = (WS / ".research" / "tools" / "brain_src" / "brain.logic.js").read_text(encoding="utf-8")
spec_sentence = re.search(r"The plan IS the experiment:[^\n]*?decision_points with a default value\.", brain_src).group(0)

parts = ["# critic.md — the external reviewer's contract (three modes; paths only, never a summary)",
         "You are the cross-family reviewer of one experiment block. The executor (GLM) collected the paths listed at the end; read every one yourself. Nothing you receive is a summary, and you never grade a summary. Every finding needs an anchor that exists (file:line, log:<path>:<line>, or number:<literal in results/>); a finding without one is dropped by a script.",
         "",
         "## Iron lines (verbatim)",
         q("ARIS experiment-integrity — core principle", "docs/refs/aris/shared-references/experiment-integrity.md", slice_between(aris / "shared-references/experiment-integrity.md", r"^## Core Principle", r"^## Prohibited")),
         q("ARIS reviewer-independence — what can and cannot be passed", "docs/refs/aris/shared-references/reviewer-independence.md", slice_between(aris / "shared-references/reviewer-independence.md", r"^## What CAN be passed", r"^## Why this matters")),
         q("ARIS acceptance-gate", "docs/refs/aris/shared-references/acceptance-gate.md", slice_between(aris / "shared-references/acceptance-gate.md", r"A goal/loop can DRIVE", None, max_lines=1)),
         q("ASI-Bench how-scoring-works", "docs/refs/papers/asi-bench/guide/how-scoring-works.md", slice_between(R / "papers/asi-bench/guide/how-scoring-works.md", r"Self-reported scores are never trusted", None, max_lines=2)),
         q("ARFT judge guide — Rule 1 Polarity and Rule 2 Credit Due", "docs/refs/papers/arft_guide.md", slice_between(guide, r"^### Rule 1", r"^### Rule 3")),
         "",
         "## MODE: spec — before any code is written (is every scientific decision made?)",
         q("Brain's own contract for spec/B<k>.json", ".research/tools/brain_src/brain.logic.js (BANK.spec)", spec_sentence),
         q("ASI-Bench — the difficulty ladder (B1 is the bar)", "docs/refs/papers/asi-bench/guide/authoring-a-task.md", slice_between(R / "papers/asi-bench/guide/authoring-a-task.md", r"^### The difficulty ladder", r"^## 3\.")),
         q("V8 PREREG (dual reading)", ".research/tools/exp/refs/prereg.md", strip_front(refs / "prereg.md")),
         q("ARFT codes that name a spec defect", "docs/refs/papers/arft_guide.md §5", rows(guide, ["A.2", "A.4", "A.5", "A.6"])),
         "Checks (each finding cites the spec field): (1) every decision_points entry — could a different default change which claim the result supports? then it is scientific, class A.6, blocking; (2) every open_holes entry — does the resolution rest on a file:line fact of the repository? (3) keep_if_all keys are keys the verdict instrument writes (instruments/README.md); (4) negctl_arm operates on the load-bearing variable named in anti_claim / tests_premise; (5) gates cover every outputs[] file and every forbids[] entry; (6) smoke_cmd cannot produce a reportable number (NOT_A_RESULT). Blocking → failure_level L2 (the spec goes back to Brain; no code is written).",
         "",
         "## MODE: code — before launch (does the code implement the spec, and only the spec?)",
         q("ARIS experiment-bridge — cross-model code review checklist", "~/oss/aris/skills/experiment-bridge/SKILL.md", slice_between(Path.home() / "oss/aris/skills/experiment-bridge/SKILL.md", r"^    Check for:", r"For each issue found, specify", inclusive_end=True)),
         q("V8 SELF_CHECK — re-run these greps yourself; the builder's counts are a claim", ".research/tools/exp/refs/self-check.md", strip_front(refs / "self-check.md")),
         q("ASI-Bench reviewer — anomaly detection", "docs/refs/papers/asi-bench/reviewer-extract.md (analysis/reviewer.py, verbatim extract)", slice_between(R / "papers/asi-bench/reviewer-extract.md", r"^### Dimension 3", r"^### Dimension 4")),
         q("ASI-Bench reviewer — GT leakage signs", "docs/refs/papers/asi-bench/reviewer-extract.md (analysis/reviewer.py, verbatim extract)", slice_between(R / "papers/asi-bench/reviewer-extract.md", r"^### Dimension 5", r"^## Required output")),
         q("ARFT per-issue standard", "docs/refs/papers/arft-2608.14905v2.txt:2397-2411", line_range(paper, 2397, 2411)),
         q("ARFT codes that name a code defect", "docs/refs/papers/arft_guide.md §5", rows(guide, ["C.1", "C.2", "C.3", "C.5", "X.4"])),
         "Blocking = the implementation differs from spec.changes / verdict_rule / arms, touches forbids, or a self-check grep is non-zero. Do not fix the code you review.",
         "",
         "## MODE: process — after the run (is the number real, and does it mean what the spec says?)",
         q("ARIS experiment-audit — the exact auditor prompt (checklist A–F)", "docs/refs/aris/experiment-audit/SKILL.md", line_range(aris / "experiment-audit/SKILL.md", 105, 173)),
         q("ARFT — the nine iron rules for judging a rollout", "docs/refs/papers/arft-2608.14905v2.txt:2359-2393", line_range(paper, 2359, 2393)),
         q("ARFT codes for the run itself", "docs/refs/papers/arft_guide.md §5", rows(guide, ["C.1", "C.3", "D.4", "D.5", "D.6", "D.7", "F.2", "F.4", "X.5", "X.6"])),
         q("ARIS result-to-claim — the seven-field judgment (fill these fields too; they never replace the numeric gate)", "docs/refs/aris/result-to-claim/SKILL.md", slice_between(aris / "result-to-claim/SKILL.md", r"^\s*1\. claim_supported:", r"^\s*A single positive result", inclusive_end=True)),
         q("ARIS review-tracing — when a verdict is surprising, read the raw record first", "docs/refs/aris/shared-references/review-tracing.md", slice_between(aris / "shared-references/review-tracing.md", r"^## Debugging With Traces", r"^```bash")),
         "Also: (a) read verdict.json (the numeric gate) and state verdict_agree — you never recompute the gate, you audit its inputs; (b) probe self-proof: the run must show its checkpoint loaded (≥ 90% of tensors) and its canary reproduced — a probe on an unloaded model is a false finding (feedback_probe_must_prove_itself); (c) too_good: if verdict.json says too_good, decompose the number — what privileged information or leaked condition could produce it; (d) which of the idea card's reviewer_concerns_and_responses did this run actually answer. L4 is a closed list: only A.5, A.6 or D.4, and only with a second independent vote; 'evidence missing but hypothesis reasonable' is L2, never L4.",
         "",
         "## Output contract",
         "Return ONE JSON object (the CLI enforces the schema; in process mode also fill claim_supported / what_results_support / what_results_dont_support / missing_evidence / suggested_claim_revision / next_experiments_needed / confidence): {\"x_id\", \"mode\", \"verdict_agree\": bool, \"findings\": [{\"anchor\": \"file:line | log:<path>:<line> | number:<literal>\", \"class\": \"<ARFT code>\", \"blocking\": bool, \"note\": \"<what, with the anchor's content>\"}], \"failure_level\": \"L0|L1|L2|L3|L4|null\", \"credit_due\": [\"<written BEFORE any failure — judge-guide Rule 2>\"], \"anomalies\": [{\"what\", \"where\", \"disposed\"}]}. Return findings: [] when you find nothing; never pad; never a finding without an anchor.",
         q("findings.schema.json (the file anchor_check.py validates against)", ".research/tools/exp/refs/findings.schema.json", (refs / "findings.schema.json").read_text(encoding="utf-8").strip())]
out = "\n".join(parts) + "\n"
(HERE / "critic.md").write_text(out, encoding="utf-8")
print("critic.md", len(out), "chars")
