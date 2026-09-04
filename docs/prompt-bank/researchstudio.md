# Prompt-fragment harvest — ResearchStudio (idea_spark)

Root: `/home/lingxufeng/autoresearch/ResearchStudio/ResearchStudio-Idea/skills/idea_spark/` — every path below is relative to it.
Read in full: `references/system-prompts/{critique,coherence_trace,ideate_select,falsification_reaudit,bottleneck_identify,ideate_generate,expand,revise,implementability_audit,refutation_recheck,derive_plain}.txt`, `references/anti-patterns.md`, `references/design-notes.md`, `SKILL.md`, `references/ideation-patterns/overview.md`, `references/ideation-sub-patterns/C12.md` (one representative cluster card), `references/pattern-summary-rubric.md`, `references/intent-recognition.md`, `references/regression-directions.md`.
"already" was checked against `/home/lingxufeng/workspace/.research/bundle.py`, `.research/critique.py`, `.claude/workflows/*.workflow.js` (line refs given).

45 fragments, verbatim. A fragment quoted from one very long source line is one physical line in the fence. Rank 1 = most load-bearing within the slot.

---

## S1 abstract — claim + anomalies → failure modes B → mechanisms M

### F01 · S1 · rank 1 · already: partial
Why: the litmus that keeps B problem-shaped; ours forbids a method in the claim sentence (CLAUDE.md) but the B/M prompt has no test for a smuggled cure. Also S2.
`references/system-prompts/bottleneck_identify.txt:197`
```
**Problem-level, not solution-level (applies to `bottleneck_statement` AND every `what_phase_0_did_not_address` entry).** Diagnose the failure; let Phase 2.2 invent the cure. Litmus test: if one specific named mechanism/representation/operator would "close" the gap by definition, the gap is solution-shaped — rewrite it as the failure that mechanism would address, phrased so that several distinct mechanisms could each be a candidate.
```

### F02 · S1 · rank 2 · already: partial
Why: the exact shape of a failure-mode statement (what breaks, when, why the machinery cannot produce the quantity) with a worked contrast.
`references/system-prompts/bottleneck_identify.txt:90`
```
State the FAILURE (what breaks, under what condition, and why the current machinery cannot produce the needed quantity), NOT the absence of a specific cure: 'no method maintains a per-prompt signal that survives across visits' smuggles one mechanism (a persistent baseline) into the diagnosis and forces every downstream gap and idea to be that one mechanism. Write it so that several distinct cures could each address it — e.g. 'once a group saturates, no within-group statistic can produce a non-zero advantage numerator, so the gradient vanishes' admits persistence, resampling, regrouping, off-policy correction, etc.
```

### F03 · S1 · rank 3 · already: no
Why: the "mattering test" — a B with no nameable cost is retrieval negative-space; the stakes clause is the enforceable form. Also S11.
`references/system-prompts/bottleneck_identify.txt:199`
```
**The mattering test (applies to every `what_phase_0_did_not_address` entry).** Being unaddressed in a ~34-paper retrieval window is NOT evidence a gap matters — it may be unaddressed because it is a non-problem. Every gap must therefore carry the inline stakes clause defined in the field spec, and the litmus is concrete: if you can name NEITHER a practitioner scenario NOR an intellectual cost (invalid conclusions, non-transferring results, blocked principled design) where this failure costs something specific, the entry is retrieval negative-space and must not be emitted.
```

### F04 · S1 · rank 4 · already: no
Why: the abstraction ladder (class → primary instance) with the honesty escape; this is what our "three abstraction levels" should enforce. Also S10.
`references/system-prompts/bottleneck_identify.txt:201`
```
**Structural-property framing (class over instance).** Write `bottleneck_statement` and each gap as a STRUCTURAL PROPERTY of a problem class when one honestly exists — name the property (e.g. "any verification schedule that adapts to observed acceptances censors its own future observations"), then name the anchor's setting as the PRIMARY INSTANCE where the property bites. This costs nothing when true and buys transfer: downstream phases inherit the framing, so the final card claims the class, not one system. The honesty constraint is absolute: if the failure genuinely is specific to one system's quirk, say so plainly ("this gap is specific to <setting>; no broader class is claimed") — manufacturing fake generality is itself an overclaim and reads worse to an expert than an honest class-of-one.
```

### F05 · S1 · rank 5 · already: no
Why: the "subtractive" gap — name the inherited assumption and STOP; forbids appending the replacement. Directly the B→M boundary.
`references/system-prompts/bottleneck_identify.txt:101`
```
Name the assumption being questioned and STOP there — do NOT append the specific replacement you have in mind ('...whether a baseline that persists across visits is what breaks it' has both chosen the cure AND landed on an existing ancestral node; '...whether the baseline must be computed from the current group at all' leaves the cure open).
```

---

## S2 diverge — source domains C per mechanism

### F06 · S2 · rank 1 · already: no
Why: enumerate by the residual, not the surface verb — the rule that stops K3 from collapsing to the framing family's vocabulary.
`references/system-prompts/ideate_select.txt:188-194`
```
   For the anchor gap, enumerate candidates by the residual the gap must
   close, not by the gap's surface verb: a pattern from a different
   mechanism family that closes the same residual through a different move
   must not be excluded because the gap was phrased in one family's
   vocabulary. When to apply is matched against the residual, so the
   enumeration spans families rather than collapsing to the most literal
   framing.
```

### F07 · S2 · rank 2 · already: no
Why: the alias move — name the mechanism in another community's words from parametric knowledge; the precedent query in A should carry these, not paraphrases. Also S3.
`references/system-prompts/ideate_generate.txt:294-305`
```
- `alias_terms[]`: 2-4 entries, 3-7 words each — how OTHER research
  communities would name this candidate's core mechanism. This is a
  PARAMETRIC-KNOWLEDGE step, not a paraphrase step: ask "if a reward-modeling
  / classical-CV / RL / NLP / theory group had built this same mechanism 2-3
  years ago, what would their papers' titles call it?" and write those names
  [...] Do NOT reuse signature_terms vocabulary or the candidate's own
  domain wording — the whole point is the words your community does NOT use.
```

### F08 · S2 · rank 3 · already: no
Why: a composed mechanism must NAME the intermediate object O or it is decorative — a one-line test for chained sources. Also S8.
`references/system-prompts/ideate_select.txt:109-112`
```
- To adopt a chain you must state it concretely — "A's move yields O; B's
  move on O yields the demanded deliverable" — NAMING O. If you cannot name
  O, the chain is decorative; drop it.
```

### F09 · S2 · rank 4 · already: partial (critique.py:178 anchors a graveyard entry; the naming rule is not stated)
Why: anti-over-conservatism — to call a source "already done" you must name the concrete prior method; "feels done before" never suppresses. Also S6.
`references/system-prompts/bottleneck_identify.txt:120`
```
(3) ANTI-OVER-CONSERVATISM: to flag a candidate cure as 'an existing node' (a regression), you MUST name the concrete prior method (name + its move); if you cannot name a specific one, do NOT flag it — a vague 'feels done before' must never suppress a gap.
```

### F10 · S2 · rank 5 · already: no
Why: collateral families — enumerate the older method families that attacked the same residual via a different mechanism; declare absence rather than invent. Also S6 (graveyard).
`references/system-prompts/bottleneck_identify.txt:53-56`
```
To enumerate them by recognition rather than free
  recall, first derive the 4-6 mechanism families that have historically
  attacked this bottleneck's residual — the families are specific to this
  bottleneck, not a fixed list — then check each family for a representative
  outside the retrieval window. A family with no such representative is simply
  declared absent; do NOT invent one to fill it.
```

---

## S3 search — paper-search, procedure-grade papers, precedent query

### F11 · S3 · rank 1 · already: partial (mechanism.workflow.js:100 queries `name + a_terms`; no solution-vocabulary instruction)
Why: the ESCAPE-MECHANISM query — the paper that scoops you titles itself by its fix; problem-keyed queries miss it by construction.
`references/intent-recognition.md:18`
```
- Query 4: ESCAPE-MECHANISM — the vocabulary a paper that *already fixed* this bottleneck would title itself with, ~4-7 words. A solver paper names itself by its solution ("empirical Bayes shrinkage baseline", "global running reward statistic"), not by the problem — so queries 1-3, all keyed on the problem, systematically miss exactly the closest prior work (the paper that scoops you). Reason about 1-2 plausible solution families for the stated bottleneck and phrase this query in that SOLUTION vocabulary, not the problem's. This query is load-bearing for recall; do not skip it.
```

### F12 · S3 · rank 2 · already: no
Why: the alias channel is multi-year and an ancestor subsumes regardless of age — the precedent window rule. Also S6.
`references/system-prompts/critique.txt:11`
```
Alias-channel hits are older by design; do NOT discount a threat for being 2-3 years old — a same-mechanism ancestor subsumes the candidate regardless of age.
```

### F13 · S3 · rank 3 · already: no
Why: term construction rules for a BM25 query — length, facets, no generic words.
`references/intent-recognition.md:60-64`
```
- Each term is 3-7 words.
- Cover (a) the mechanism, (b) the claim, (c) the setting/setup. One term per facet, plus 1-2 specific identifiers (e.g. dataset name, theorem name).
- Avoid generic terms ("deep learning", "transformer") — they retrieve too much noise.
- Prefer noun phrases over verb phrases.
```

### F14 · S3 · rank 4 · already: partial (searcher prefers `is_survey=false`, mechanism.workflow.js:97)
Why: survey magnets — the phrasing rule that keeps the query mechanism-first.
`SKILL.md:132`
```
Phrase queries mechanism-first: generic "`<topic>` challenges/overview/landscape" phrasings are survey magnets that dilute corpus density — the orchestrator demotes survey-titled hits to the bottom of lit_results (kept, never dropped), but each connector's cap slots are still spent on them.
```

---

## S4 reverse — one paper → gene card

### F15 · S4 · rank 1 · already: no
Why: the "scooped / precedent" bar — closes vs executes; the vocabulary that distinguishes a settling paper from one more instance. Also S3.
`references/pattern-summary-rubric.md:82-89`
```
Most papers EXECUTE the ideation pattern and add to its open frontier — they do NOT resolve. The bar for `resolves_problem`:

- The paper proves an exhaustive characterization (e.g., "all relaxations of A under condition C reduce to one of these K forms")
- The paper provides a definitive impossibility / lower bound that closes the space
- The paper's abstract or claimed contribution explicitly says the work "closes", "settles", "characterizes", or "resolves" — not just "extends" or "improves"
- The paper is itself widely-cited as the reference work for that sub-problem
```

### F16 · S4 · rank 2 · already: no
Why: `disanalogy_to_A` / `what_step_was_missed` must be SUBSTANTIVE (a construction, a regime, a primitive), never a methodological label. Also S7.
`references/system-prompts/ideate_generate.txt:223`
```
"what_step_was_missed": "<a specific SUBSTANTIVE step that paper would have needed for our contribution to already exist. Substantive forms: a derivation, a construction, a regime extension, a measurement primitive, an architectural property. NOT methodological labels ('they didn't apply Tweedie', 'they used a different pattern'). Substantive example: 'they constructed the equivalence for single-network ELBO; the parallel for two-network distillation requires a teacher-conditioned augmentation distribution they didn't construct.'>",
```

### F17 · S4 · rank 3 · already: no
Why: the hard rule behind F16, stated as a process error.
`references/system-prompts/ideate_generate.txt:241-247`
```
1. **Substantive > methodological** in `differentiation_from_lit[].delta` and
   `what_step_was_missed`. Methodological framing ("they used pattern X, we
   use Y" / "they didn't apply Tweedie") is a process error — it describes
   method choice, not contribution. Substantive framing names what is
   derived / constructed / measured / tightened (a derivable theorem, an
   observable empirical regime, a measurement primitive, an architectural
   property without precedent, a scaling exponent).
```

### F18 · S4 · rank 4 · already: partial (we obtain full texts; the reason is not in the prompt)
Why: why abstracts are not enough for residue/AVOID — the justification for insisting on method-section text. Also S3.
`references/system-prompts/bottleneck_identify.txt:75`
```
Read this BEFORE writing bottleneck or closest_adjacent — abstracts alone systematically underestimate residue because limitations / scope boundaries / implementation details that determine "what this paper actually did not do" live in method sections, not abstracts.
```

---

## S5 verify — re-read the paper for one card

### F19 · S5 · rank 1 · already: partial (critique.py:215 "script_facts 不得推翻" — no refutation standard)
Why: what counts as a refutation of executed/quoted evidence — three concrete flaw classes; re-reasoning never refutes; asymmetry is intentional. Also S7, S12.
`references/system-prompts/refutation_recheck.txt:17-21`
```
- A basis that re-reasons about what the mechanism "should" do, appeals to plausibility, cites author intent, or re-derives the conclusion without touching the script/numbers does NOT refute. Mark invalid.
- Flaw (a) claims: the basis must point at specific words of the step text that the gate's formalization contradicts. Verify against the candidate's actual text; a "charitable reading" argument counts ONLY if the finding's own `reading_dependence` tag says reading_dependent AND the basis names the alternative reading — a reading_robust finding cannot be refuted by re-reading.
- Flaw (b) claims: the basis must identify the specific computation. Recompute it yourself — you have a code-execution tool; write and RUN a short stdlib-only check and paste script + output into `reason`. Hand-verification only if no execution tool exists (mark it unexecuted).
- Flaw (c) claims: the basis must name the violated premise as the candidate states it. Verify the premise actually appears in the candidate.
- When in doubt, the executed finding stands: `refutation_valid: false`. Asymmetry is intentional — the gate ran code; the audit reasoned.
```

### F20 · S5 · rank 2 · already: no
Why: dual-reading protocol — an ambiguous operative term in a step is itself a finding; never silently pick one reading. Applies to a verifier judging "is this step a procedure".
`references/system-prompts/coherence_trace.txt:14`
```
DUAL-READING PROTOCOL (formalization is itself interpretation — control for it): before formalizing each step, QUOTE the step text verbatim. When an operative term admits more than one defensible reading (e.g. "unchanged": strictly-equal vs does-not-decrease; "similar", "stable", "near"), formalize EVERY defensible reading and run T2/T3/T5 under each. Tag every downstream finding `reading_robust` (holds under all defensible readings) or `reading_dependent` (name the reading it needs). An ambiguous operative term is ALWAYS itself a wording finding — whichever reading the author intended, the text must be edited to say it precisely, so emit a wording patch (or, if the step is only sound under one reading, patch the text to that reading and say so). Never silently pick one reading and report its findings as unconditional.
```

### F21 · S5 · rank 3 · already: no
Why: "an anomaly you assert without the computed number is not a finding" — the executed-evidence bar for any numeric claim a verifier or critic makes. Also S7.
`references/system-prompts/coherence_trace.txt:16`
```
EXECUTE, don't estimate: when a code-execution tool is available in your context, write a short stdlib-only Python script for the instance, RUN it, and paste both the script and its output into the report — hand-arithmetic is permitted only when no execution tool exists, and every hand-computed quantity must then be marked `unexecuted`. Show the arithmetic (or executed output) in the report — an anomaly you assert without the computed number is not a finding.
```

---

## S6 critique-sources — four checks per source

### F22 · S6 · rank 1 · already: no
Why: STANDARD-TOOL FOLLOW-UP — our sources ARE textbook mechanisms from other fields; this is the check that separates "method" from "application of a textbook tool". Also S8 (rationale_line).
`references/system-prompts/ideate_generate.txt:207`
```
STANDARD-TOOL FOLLOW-UP (branch (i) only): if the confrontation you reach for is itself a textbook tool from another field (examples, not an exhaustive list: bandits/off-policy evaluation, missing-data methods, survival analysis, active sensing, experimental design), name the DOMAIN-SPECIFIC STRUCTURE that makes this instance not already solved by the textbook tool (a budget constraint, a coupling, adaptivity, a scale regime) and make that structure part of the contribution; if no such structure exists, declare the contribution application-grade honestly — do not dress a textbook application as a method;
```

### F23 · S6 · rank 2 · already: partial (our result enum is pass/fail/unclear; no `n_a` with a reason, no fabrication ban; the independent-construction rule itself is already in critique.py:212)
Why: the three T5 verdict definitions, including the honest `n_a` — "never fabricate a comparison".
`references/system-prompts/coherence_trace.txt:29-31`
```
- `confronts_obstacle` — the naive version demonstrably fails on the instance for the reason the candidate names (show the number), and the full mechanism's extra machinery is what fixes it. Positive confirmation.
- `equivalent_to_naive` — the mechanism's behavior on the instance is the naive version's plus cosmetic differences, while the candidate declared branch (i). FINDING: the mechanism does not confront its own declared obstacle. This is an OBSTACLE HOLE (below), not a patchable defect.
- `n_a` — no meaningful naive execution exists for this shape (e.g. a pure equivalence theorem): degrade to tracing where the STANDARD argument breaks on the instance; if neither is expressible, record n_a with the reason — never fabricate a comparison.
```

### F24 · S6 · rank 3 · already: no
Why: the family-level scoop flag — name the FAMILY and query vocabulary, never a paper from memory ("family names don't hallucinate"). Also S3.
`references/system-prompts/critique.txt:66`
```
"parametric_family_concern": "<SOFT SIGNAL, from your own knowledge, NOT from the retrieved pool: if the candidate's core mechanism plainly resembles an older, named research family the pool did not surface (e.g. 'goal-conditioned success detectors', 'learned value-function reward models'), NAME THE FAMILY and 1-2 vocabulary phrases a scoop-check should query — do NOT cite specific papers from memory (titles/authors/years hallucinate; family names don't). null when the pool covered the mechanism's obvious relatives. This field NEVER feeds the hard floor or the verdict
```

### F25 · S6 · rank 4 · already: partial (mechanism.workflow.js:101 "None is a valid answer" for the searcher; not in the panel prompt)
Why: `no_threat_found` is valid; fabricating a generic threat is forbidden — the graveyard/precedent check needs the symmetric rule.
`SKILL.md:183`
```
| paper_pointed_threat | most specific subsuming/competing paper in `lit_table ∪ collision_hits` (both channels; alias-channel threats are NOT discounted for age); `no_threat_found` is valid — fabricating a generic threat is forbidden.
```

### F26 · S6 · rank 5 · already: no
Why: the falsifiable-at-scale self-check in a cluster card's own words — "exhibit at least one regime the original cannot reach; measure the bought property head-on".
`references/ideation-sub-patterns/C12.md:26`
```
A diagnostic tell is validation on a proxy: throughput reported instead of accuracy, toy-scale data, or no matched baseline for the specific property claimed. Self-check: can you exhibit at least one object, capability, or regime the original structure provably cannot reach, and is the property the swap buys measured head-on rather than assumed to follow from the swap?
```

### F27 · S6 · rank 6 · already: no
Why: the anti-pattern that most resembles our "adapt a source + manufacture a signal" candidates, with its required mitigation (an ablation that holds one axis fixed). Also S8 (ablation rung), S12.
`references/anti-patterns.md:13`
```
"We made up the groups AND made up the labels." Decomposing into sub-populations is one un-derived choice; manufacturing supervision for each sub-population is a second un-derived choice; the paper is reviewed as two stacked heuristics, neither of which is testable independently of the other. By a wide margin the dataset's strongest reject signal. | The decomposition criterion must be derivable from observed structure or task-level supervision (not just intuition), AND the manufactured signal must be the *unique* signal the decomposition implies. An ablation that holds the decomposition fixed and varies the signal (or vice versa) must show the two are not conflated.
```

---

## S7 critique-spec — five checks, two-layer verdict

### F28 · S7 · rank 1 · already: partial (critique.py:211 names "一个承重变量"; no negative-control / tautology definition)
Why: the falsification_structure_check field definitions — the tautological negative control is the exact hole our kill_cmd check does not name.
`references/system-prompts/critique.txt:72-75`
```
"load_bearing_variable": "<quote the ONE named quantity the mechanism claim pivots on (a gradient norm, an information-gain term, a logit divergence, a learned threshold, a representational direction, ...), or 'absent' if no single variable is named>",
"negative_control_target": "<'outcome_metric' when the negative-control intervention on the load-bearing variable predicts the DOWNSTREAM outcome metric returns to baseline; 'tautological' when the predicted effect is the load-bearing variable's own value or a quantity analytically derived from it (a control of the form \"intervene on X → X becomes 0\" tests a definition, not a mechanism); 'absent' when no negative control is stated>",
"verdict": "sound | deficient | borderline",
"reasoning": "<1-2 sentences: which sub-answer drove the verdict. 'sound' requires ALL of: minimal_experiment_named=yes, outcome_metric_named=yes, load_bearing_variable quoted (not absent), negative_control_target=outcome_metric. Any 'no'/'absent'/'tautological' → deficient. borderline is reserved for a named-but-ambiguous variable or a control whose target metric is arguably-but-not-explicitly the outcome.>"
```

### F29 · S7 · rank 2 · already: no
Why: anti-claim-avoidance — grading must never reward vagueness; an all-hedged spec is itself a weakness finding. Protects method_prose from being sanded down by revise.
`references/system-prompts/coherence_trace.txt:26`
```
ANTI-CLAIM-AVOIDANCE: this grading must never reward vagueness. A candidate making strong claims with honest stated assumptions outranks one making only hedged weak claims; do NOT emit findings that push claims to become vaguer, and if EVERY claim is already hedged/unfalsifiable-soft, record that itself as a weakness finding (the mechanism asserts nothing checkable).
```

### F30 · S7 · rank 3 · already: no
Why: OBSTACLE HOLES — a revise that abstains/clamps/skips the regime the mechanism exists to solve is forbidden; it is abandon, not revise. Also S8 (retry).
`references/system-prompts/coherence_trace.txt:40`
```
OBSTACLE HOLES — the one class of finding you must NOT patch around. A finding is an obstacle hole when its honest fix would change what the mechanism IS (a redesign, not a repair), or when it coincides with the obstacle the candidate's own PREMISES / NAIVE-BASELINE AUDIT declared it exists to solve (including T5's `equivalent_to_naive`). For obstacle holes, avoidance-style patches — abstain on the affected cells, clamp the affected range, skip the affected regime — are FORBIDDEN when their effect is to sidestep the declared obstacle rather than solve it (such patches remain legitimate for genuine engineering edges unrelated to the declared obstacle). Record obstacle holes under `unrepaired[]` with severity `blocking`, verbatim and unsoftened.
```

### F31 · S7 · rank 4 · already: no
Why: strengthen-only rule for touching the kill test on revise — additions only; never cheaper, never a swapped metric.
`references/system-prompts/critique.txt:128`
```
Strengthen-only means ADDITIONS ONLY — the experiment, outcome metric, claim, load-bearing variable, and every existing control stay verbatim; anything that removes, swaps, weakens, or cheapens is NOT authorized under this clause and must not be requested. Name in fix_direction exactly what to ADD and which check finding requires it.
```

### F32 · S7 · rank 5 · already: partial (bundle.py:500 hands findings + revision_target to the retry; no "do not re-judge")
Why: the reviser applies, never re-judges — the separation that removes self-answering bias. Also S8 (`--retry`).
`references/system-prompts/revise.txt:79`
```
4. **Do NOT re-judge the audit's verdict.** Phase 3.3 does not run sanity checks, does not search lit_table, does not query whether the audit's revision_target is "really" the right fix. The audit determined what needs to change; 3.3 just applies it.
```

### F33 · S7 · rank 6 · already: no
Why: anti-pattern mitigation is judged at the artifact level — keyword presence is not delivery (generalises to any "we control for X" claim in a spec).
`references/system-prompts/critique.txt:137` · `references/anti-patterns.md:25`
```
2. **anti_pattern_check evaluates substantive delivery, not keyword presence**. Does the candidate's core_mechanism actually produce the artifact the mitigation names? Keyword present but artifact absent → `mitigation_substantively_delivered = false`.
The mitigation must be **visible in the candidate's `core_mechanism`** at the artifact level, not merely claimed in the framing — keyword presence is not delivery.
```

### F34 · S7 · rank 7 · already: partial (anchors are required; "looks fine" is not named a process error)
Why: verdict rationale must cite check findings; "Looks fine overall" is a process error.
`references/system-prompts/critique.txt:88,139`
```
"verdict_rationale": "<2-3 sentences citing specific check findings (gap_closure_reject_check.entries[X].reject_lessons_evaluated[N].lesson_quoted / recipe_application_check.entries[X].verdict / anti_pattern_check.mitigation_substantively_delivered / paper_pointed_threat.subsumption_argument). 'Looks fine overall' is a process error.>",
3. **Verdict must cite specific check findings**. `verdict_rationale` cites lesson_quoted / mitigation field / subsumption_argument. Generic "all checks pass" is a process error.
```

---

## S8 spec — the next candidate as a complete B1 procedure

### F35 · S8 · rank 1 · already: partial (SPEC_SCHEMA steps: "function, loss, condition set, schedule, numbers")
Why: "computable from the text alone" — every quantity defined, every free index fixed or given a selection rule, bridging weights named.
`references/system-prompts/ideate_generate.txt:205`
```
**Make the central object computable from the text alone**: define every quantity it is built from (what it is, and where it comes from — model-internal readout / computed / external oracle), fix or give a selection rule for every free index or layer-set, and write out any weight that bridges different-unit quantities as a named hyperparameter. A reader must be able to compute the object without guessing.
```

### F36 · S8 · rank 2 · already: no
Why: every intervening step must state how it propagates to the downstream output — else it "changes a bookkeeping value with no shown effect on the result".
`references/system-prompts/ideate_generate.txt:209`
```
For any step that intervenes on the model or inference (an operator, edit, ablation, restoration), state how that modification propagates to the downstream task output — not just the intermediate quantity it changes (e.g., not 'raises margin M' but 'raises M via a second forward pass, which changes the generated answer'); otherwise the step changes a bookkeeping value with no shown effect on the result. A reader should be able to ask 'if I build this, what do I do first, second, third?' and your list answers that. Write at the code-pathway level — concrete enough to implement, not abstract design language.
```

### F37 · S8 · rank 3 · already: no
Why: the falsification paragraph's anti-tautology guard and the two recommended controls (positive control; full-observation oracle).
`references/system-prompts/ideate_generate.txt:211`
```
Anti-tautology guard: the control's predicted effect MUST be the downstream task-outcome metric that defines the mechanism's value (accuracy, win-rate, regret slope, real refusal pass-rate) — NOT the variable's own value, nor a quantity analytically a function of it. 'Intervene on X → X becomes 0' only tests a definition; 'intervene on X → downstream metric moves in direction D' is the real Popper test, because 'the metric moved' alone is equally consistent with calibration, estimator quality, or distribution shift. A positive control — a stripped-down model using only the load-bearing variable that recovers most of the downstream effect — is recommended when feasible, converting a falsifier into a constructive identification. Where the setting limits observability, a full-observation oracle (an upper-bound run with the hidden quantity revealed) is the second recommended control.
```

### F38 · S8 · rank 4 · already: no
Why: PREMISES ledger + mandatory observation-model premise — where the hidden assumption a naive mechanism relies on lives (our "disanalogy" should be one such premise, tagged as the falsification target).
`references/system-prompts/ideate_generate.txt:207`
```
BLOCK 1 — PREMISES ledger: every load-bearing empirical/domain premise the mechanism stands on, one per line, each with a one-line reason it is believed true in this field; any premise that is actually a bet gets the tag 'untested — falsification target' and should be what falsification_prediction's load-bearing variable pivots on. WHEN the mechanism consumes sampled/observed data or signals (most mechanisms do; a pure construction or equivalence contribution may not), at least ONE premise MUST be an OBSERVATION-MODEL premise: how are the mechanism's inputs/signals sampled or observed, and is that sampling unbiased/complete in THIS setting? (Censoring, selection bias, non-iid sampling, leakage, self-preference all live here — it is where the hidden assumptions that naive mechanisms silently rely on are found.) If the mechanism consumes no sampled inputs, write 'observation-model: n/a (no sampled inputs)' — never fabricate one.
```

### F39 · S8 · rank 5 · already: no
Why: claim strength — guarantee words only with assumptions stated where they appear; do not self-censor ambition (governs method_prose written before results).
`references/system-prompts/ideate_generate.txt:277-283`
```
4. **State every claim at the strength you can defend.** Guarantee-grade
   assertions (unbiased / provable / exact / optimal / lossless — and any
   paraphrase of them) are permitted ONLY with their assumptions stated
   where they appear; otherwise use the honest weaker grade (consistent /
   asymptotic / empirical). The coherence gate grades every claim (T4). Do
   NOT self-censor ambition to dodge the grading: a strong claim with
   honest stated assumptions is BETTER than a hedged weak claim.
```

### F40 · S8 · rank 6 · already: partial (gate.py spec: files exist on research-trunk; substrate paths)
Why: name existing resources only — the first implementation step may not be "build a dataset that does not exist"; modest self-built resources allowed with their cost counted.
`references/system-prompts/ideate_generate.txt:263-275`
```
3. **Name existing resources only.** Every dataset, benchmark, annotation
   source, tool, and model-access level (weights / logits / gradients /
   API-only) that core_mechanism, core_mechanism_steps, or
   falsification_prediction invokes must be a NAMEABLE, currently-existing
   artifact — name it. If the mechanism needs something that does not exist
   (a corpus with annotation X, gradients of a closed-weight model),
   redesign around an existing equivalent or scope the claim down NOW — do
   not ship an idea whose first implementation step is "first, build a
   dataset that does not exist".
```

---

## S9 build-review-focus — external diff reviewer

### F41 · S9 · rank 1 · already: yes (bundle.py:568 "a mechanism the spec does not name (extra machinery)")
Why: the "do not change the method" contract in reviewer-facing words — new/removed/renamed mechanism = scope creep (canonical wording, kept for the focus text).
`references/system-prompts/implementability_audit.txt:117-120`
```
3. Do NOT change the method: no new steps, no removed steps, no renamed mechanisms, no new claims. You
   specify HOW to build the existing method, faithful to `core_claim` / `sub_claims`. Adding mechanism is
   out of scope and reads as scope creep to a reviewer.
```

### F42 · S9 · rank 2 · already: partial (builder returns deviations/blockers; the "open hole" honesty rule is not stated)
Why: honest open holes over confident guesses — the builder's blockers.json should be governed by this sentence.
`references/system-prompts/implementability_audit.txt:56-60`
```
- If a hole genuinely requires a design decision you cannot make without overclaiming (a choice the
  method's authors must own, where any confident fill would be fabrication), DO NOT invent detail.
  Mark it `severity: "open"` and state precisely what decision is needed. Honest open holes are far more
  valuable than confident-sounding guesses — surfacing them is the whole point of an adversarial audit.
```

---

## S10 write-review — final manuscript review

### F43 · S10 · rank 1 · already: partial (gate.py numbers: `% src:` per line; the fidelity sentence is not in the review prompt)
Why: "no new content — fidelity beats fluency": the writer/reviewer rule for any sentence without a record behind it.
`references/system-prompts/derive_plain.txt:77-78`
```
3. **No new content**: if you find yourself writing a sentence with no source in the technical
   fields, delete it. Fidelity beats fluency.
```

### F44 · S10 · rank 2 · already: no
Why: "what changes when the gap closes" must name a capability, NOT "better numbers" — the selective-narrative check in positive form; pairs with F04 for class-vs-instance ("do not inflate", expand.txt:73).
`references/system-prompts/expand.txt:82`
```
**`motivation.what_changes_when_gap_closes`** — 2–3 sentences naming downstream consequences. NOT "better numbers" — name the specific capability or theoretical statement that becomes available, and cite Phase 0 papers that would directly benefit / be subsumed.
```

### F45 · S10 · rank 3 · already: no
Why: the proxy-validation tell a reviewer looks for (throughput not accuracy, toy scale, no matched baseline) — a must-discuss-comparison rule.
`references/ideation-sub-patterns/C12.md:14`
```
5. Validate the unlocked gain in the exact regime and at the scale where it is claimed, against baselines matched to that specific property. Reporting a secondary proxy — throughput without accuracy, toy-scale data, or no matched-compression/matched-parameter comparison — while leaving the headline property unverified is the single most common reason an otherwise-sound substitution is rejected.
```

---

## S11 pivot — after the stop rule

### F46 · S11 · rank 1 · already: no
Why: the failure-attribution rule that decides revise-claim vs new-sources: only two independent mechanisms subsumed indict the framing; mechanism-level deaths do not.
`references/design-notes.md:115`
```
The repair adds one bottleneck re-diagnosis, but gated on DETERMINISTIC failure attribution: only when BOTH attempts died with `paper_pointed_threat.addressable_via = "unaddressable"` (two independently-generated mechanisms subsumed ⇒ the occupied space indicts the framing, not the generator). Mechanism-level deaths do NOT trigger it — a third mechanism roll has diminishing returns, and the space of sharp bottlenecks per corpus is small (the first diagnosis is usually the sharpest; a forced second is often blander).
```

### F47 · S11 · rank 2 · already: partial (pivot.workflow.js exits revise_claim / new_sources; no re-phrasing ban, no "honest exit preferred")
Why: a re-phrased claim dies the same death; a different failure axis; the honest "no second sharp claim" exit is preferred over a blander re-framing.
`references/system-prompts/bottleneck_identify.txt:14-16`
```
- Do NOT re-frame the retired bottleneck in new words — the collision channel already proved that space occupied; a re-phrasing dies the same death. Diagnose a DIFFERENT failure axis of the field, which typically means a different anchor paper (closest_adjacent[0]) and a different residue family.
- The killer papers define occupied ground: the new bottleneck must not be one they already resolve.
- `do_not_generate` REMAINS a legitimate — and preferred — outcome: if this corpus does not support a second literature-groundable sharp bottleneck, say so honestly (the run then terminates with that diagnosis instead of shipping a blander re-framing that will die downstream). Do not lower the sharpness bar to manufacture a second bottleneck.
```

### F48 · S11 · rank 3 · already: no
Why: POSITIVE OBSTACLE DIRECTIVES — an obstacle a killed candidate failed to confront becomes a REQUIREMENT for the next source, not just something to avoid.
`references/system-prompts/ideate_select.txt:65-71`
```
  (e) POSITIVE OBSTACLE DIRECTIVES:
  if the archived attempt carried blocking obstacle findings (2.3
  `unrepaired[]` entries or an `equivalent_to_naive` verdict — "the
  mechanism did not confront X"), the named obstacle X becomes a
  REQUIREMENT for this retry, not just something to avoid: prefer the
  gap×pattern selection whose natural mechanism must solve X head-on, and
  record that obligation in `selection_rationale` so Phase 2.2 inherits it.
```

---

## S12 readers / jury — future outer loop

### F49 · S12 · rank 1 · already: no
Why: the juror schema — each reject lesson is quoted verbatim and matched no/yes/borderline with a one-sentence reason naming the field that would trigger it; the aggregate rule is mechanical.
`references/system-prompts/critique.txt:23-34`
```
"tactical_failure_mode_quoted": "<quote the sub-pattern card's ## Tactical failure mode in ≤ 2 sentences>",
"reject_lessons_evaluated": [
  {
    "lesson_quoted": "<the bullet verbatim from ### Reject lessons>",
    "candidate_match": "no | yes | borderline",
    "reasoning": "<one sentence: which candidate field would trigger this lesson, or why it doesn't>"
  }
],
"verdict": "<aggregate: 'triggered' if ANY entry triggered; 'borderline' if ANY borderline and none triggered; 'clear' only when ALL clear>",
```

### F50 · S12 · rank 2 · already: no
Why: reject lessons in the form a reader/juror consumes — paper-agnostic, one failure per bullet (representative cluster C12).
`references/ideation-sub-patterns/C12.md:38-43`
```
- Proving the substitute operator preserves universal approximation via a trivial adaptation of known proofs, while never connecting that result to the practical advantage (e.g. sparsification) that motivated the swap, makes the contribution read as incremental.
- Claiming the rewired structure delivers a systems property — such as parallel forward/backward execution — that the underlying algorithm does not actually provide invites reviewers to falsify the headline claim head-on.
- A training-time re-parameterization that yields only marginal accuracy gains at higher training cost, without strong matched-baseline comparisons, reads as added overhead rather than as an insight.
- An elegant geometric reanalysis tool validated only on toy data, with no quantitative metric and an unclear delta over existing sensitivity measures, fails to show the substitution buys anything new.
- Rewiring the dependency chain and reporting only throughput/speedup while omitting accuracy validation at scale leaves the essential preserved-property claim unverified.
- Porting a two-component architecture from a separate domain and bolting on a cross-pathway coupling, without a unifying contribution grounded in the target task, reads as an uncoordinated assembly rather than a substitution insight.
```

### F51 · S12 · rank 3 · already: no
Why: executed evidence outranks unexecuted reasoning; advance is FORBIDDEN while any upheld blocking finding exists — the rule for consuming a record/verdict in the outer loop.
`references/system-prompts/critique.txt:7`
```
These are EXECUTED evidence and outrank unexecuted reasoning: you MUST emit one `blocking_findings_disposition[]` entry per finding (schema below). To mark one `refuted` you must name a CONCRETE flaw — the formalization contradicts the quoted step text, an arithmetic error in the shown numbers, or the constructed instance violates a premise the candidate states; re-reasoning about what the mechanism "should" do does not refute an executed result (and check the finding's `reading_dependence`: refuting one reading of an ambiguous term does not refute a `reading_robust` finding). While any disposition is `upheld`, `advance` is FORBIDDEN
```

---

## Coverage note
Present in the source and judged already fully in our loop, so not re-listed: independent construction of the naive baseline (coherence_trace.txt:28 ≙ critique.py:212, bundle.py:36); recipe_application "bypassed" (critique.txt:124,143 ≙ critique.py:210); the two-layer verdict, "default to advance" and "a borderline stays borderline" (critique.txt:100-123 ≙ critique.py:215-216); one pass / no iterate-until-clean (coherence_trace.txt:38 ≙ `propose --retry` once); kill-switch fields structurally off-limits (revise.txt:73, SKILL.md:237 ≙ frozen card sha, `eval_entry`); disanalogy per source (ideate_select/generate ≙ mechanism.workflow.js:78); precedent = same move not same words (≙ mechanism.workflow.js:120).
Not harvested (not load-bearing for our slots): Phase 0 connector/orchestration mechanics, context-discipline/timeouts (SKILL.md:82-98), Phase 4 skeleton/fill/assemble plumbing, Chinese-register and Unicode-glyph rules, compute-budget default envelope, cross-run dedup, the 2.1 sibling/coherence-thread taxonomy beyond the removal test, all cluster cards other than C12, the pattern signatures list (overview.md; our K3 prompt already names the lenses), design-notes' universality criterion and regression-directions' property-level rule (outer-loop meta, not prompt text).
