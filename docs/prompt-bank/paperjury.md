# Prompt-fragment harvest — paperjury (2026-09-04)

Root: `/home/lingxufeng/autoresearch/paperjury/`. All paths below are relative to it. JS fragments are copied as the file lines
read (string literals + JS punctuation kept, so `path:line` is checkable); the agent receives the `join('\n')` of those strings.
`already:` is judged against `/home/lingxufeng/workspace/.research/bundle.py`, `.research/critique.py`, `.claude/workflows/*.workflow.js`.
Ranked within each slot, most load-bearing first. 45 fragments (F01-F45).

---

## S12 readers / jury (future outer loop) — paperjury's home ground

### F01 — the reviewer persona core (S12; also S6/S7 panel opener) · already: no
`references/reviewer-personas.md:18-24` (identical text as `DEFAULT_CORE`, `workflows/assign-reviewers.workflow.js:40-48`)
```
> You are a senior reviewer for a top CS conference, known for being harsh, precise,
> and constructive. Your job is to find what is actually wrong, not to be agreeable.
> You separate fatal flaws from fixable nits and weight them accordingly. You do not
> pad with compliments, you do not invent problems to look thorough, and you do not
> soften a real flaw. You judge the paper on its actual merit: if method, experiments,
> and writing are sound you say so; if there is a structural defect you name it exactly
> and explain why.
```
Why: the two-sided calibration ("do not invent … do not soften") is the sentence that stops both flooding and rubber-stamping; every reader/juror prompt in the source inherits it.

### F02 — two-pass read: fatal-flaw list, then forensic interrogation (S12; S10 checklist) · already: no
`references/reviewer-personas.md:27-33`
```
- **Pass 1 - fatal-flaw diagnostic.** A blunt list of the candidate fatal flaws:
  unsupported central claims, unfair or missing baselines, ablations that do not cover
  the key design decisions, overclaims, internal contradictions, a contribution the
  experiments do not validate.
- **Pass 2 - forensic interrogation.** For each, interrogate it: where exactly
  (section/equation/table/figure), why it is a flaw, what evidence would settle it, and
  whether it is fatal or fixable within a revision.
```
Why: the Pass-1 list is a ready-made keyword list for a manuscript reader; Pass-2 forces location + settling evidence + fatal/fixable per flaw.

### F03 — weakness fields: evidence_anchor, significance, kind (S12; S6 anchor rule) · already: partial (critique.py anchor ≥12 chars; no significance/kind split)
`workflows/reading-check.workflow.js:104-111`
```
    'You are a HOLISTIC reviewer. Read the WHOLE manuscript below and file WEAKNESSES.',
    'For EACH weakness give:',
    '- summary: one line, what is wrong.',
    '- evidence_anchor: an EXACT VERBATIM quote from the manuscript the weakness rests',
    '  on (copy it character-for-character; do not paraphrase). Cannot quote = do not file.',
    '- section: a precise anchor (section + eq/table/figure/paragraph).',
    '- significance: major (a flaw that affects the paper\'s claims/soundness/contribution)',
    '  or minor (a local problem that does not threaten the central claims).',
```
Why: "Cannot quote = do not file" plus the major/minor definition is the whole filing contract in five lines.

### F04 — kind + the "when unsure, substantive" default; no fix, no invention (S12) · already: no
`workflows/reading-check.workflow.js:112-117`
```
    '- kind: substantive (a claim/method/evidence/clarity problem that needs judgment) or',
    '  mechanical (a copy-edit class issue: typo, formatting, a notation slip, a phrasing nit).',
    '  When unsure between the two, choose substantive (it will get a proper hearing).',
    '- references: optional, what would settle it or which other section it implicates (may be "").',
    'Do NOT propose the fix or a close_criterion (that is decided later). Do NOT invent',
    'flaws to look thorough and do NOT soften a real one.',
```
Why: routes uncertainty toward the expensive path (recall-safe) and separates filing from fixing.

### F05 — the hallucinated quote is a tell (S5 verify; S12) · already: yes (mechanism.workflow.js verifier re-checks lines; critique.py "an unanchored drop is a tell")
`references/reviewer-personas.md:65-66`
```
- `evidence_anchor`: an EXACT verbatim quote the weakness rests on. Cannot quote = do
  not file (the deterministic quote-verify enforces this; a hallucinated quote is a tell).
```
Why: names the deterministic backstop and the interpretation of a failed quote check.

### F06 — cross-section mandate (S12; S10) · already: partial (write review checks claim–evidence, not notation/abstract-vs-results)
`workflows/reading-check.workflow.js:97-100`
```
    `Your expert domain: ${rev.domain || '(general CS reviewer)'}. You cover the full review`,
    'surface (originality, soundness, significance, clarity, impact); your domain is a',
    'sensitivity, not a fence. You MUST reason across sections (abstract vs results,',
    'notation reused across sections, a contribution the experiments do not validate).',
```
Why: "a sensitivity, not a fence" keeps a specialist reader on the full surface; the three cross-section checks are the ones a section-by-section writer misses.

### F07 — ANTI-SKIM per-section coverage with an in-section quote (S12) · already: no
`workflows/reading-check.workflow.js:119-123`
```
    'ANTI-SKIM: you MUST also return per_section_coverage with ONE entry for EVERY section',
    'listed below: {section, status (thorough|light|skipped), in_section_quote = an exact',
    'verbatim quote FROM THAT SECTION proving you read it}. A section you genuinely cannot',
    'quote is `skipped`.',
    'Finally give ONE overall_confidence (1-5) for this review as a whole.',
```
Why: proof-of-reading per unit, script-verifiable; the single confidence feeds the later spot-check.

### F08 — the ISOLATION line (all slots) · already: yes (bundle.py:28 ISOLATION; mechanism.workflow.js:32)
`workflows/reading-check.workflow.js:52`
```
const ISOLATION = 'Judge ONLY the manuscript quoted in this prompt. Do not read files, search the project, or use any tool to find other context (the ledger, prior rounds, other reviewers, or any real manuscript on disk); base your review solely on the text quoted here.'
```
Why: the source enumerates the four things a roaming agent goes looking for; ours names only "other files".

### F09 — why the ISOLATION line exists in the prompt AND in the args (all slots) · already: partial (inline bundles; rationale not stated)
`SKILL.md:265-269`
```
2. **Reviewers / jurors are isolated.** Fresh eyes per round: no cross-talk, no
   prior-round leakage, no sight of the ledger. Enforced by (a) what goes into each
   agent's prompt AND (b) an explicit ISOLATION instruction in every reviewer-type
   prompt telling the agent to judge only the quoted text and not read files
   (workflow agents have read tools and will otherwise sometimes roam).
```
Why: states the two-layer enforcement and the observed failure ("will otherwise sometimes roam").

### F10 — each round is a parallel timeline (S12; S11) · already: no
`references/methodology.md:9-14`
```
Reviewers live ONLY in the current round. They have no memory of past rounds.
Each round simulates: "if THIS were the only version of the paper an outside
expert ever saw, what would they say?" This is why the reviewed text is frozen
and stripped of any revision marker, and why reviewers never see the ledger,
each other, or prior rounds. The isolation is what keeps the panel honest:
R2 and R3 must not anchor on R1.
```
Why: the one-sentence simulation frame ("if THIS were the only version…") is quotable as-is in a reader prompt.

### F11 — clean re-review is the test of the fix; a re-raise is corroboration (S12; S11) · already: no
`references/review-engine-v3.md:278-281`
```
Each 审 = one inner round on the CURRENT edited paper. CLEAN ROUNDS: the reviewer-facing
steps (assign/read/coverage) never see the ledger or prior open questions (max
decorrelation; a clean re-review IS the "did the edit fix it" test; an independent
re-raise = corroboration). Only the deterministic spine carries into core steps.
```
Why: defines the only honest convergence test for an outer loop: nothing new from fresh eyes.

### F12 — coverage-auditor: judge coverage quality only, file no charges (S12) · already: no
`workflows/coverage-auditor.workflow.js:50-55`
```
    'where a reviewer likely SKIMMED a section that carries reviewable content:',
    '- status skipped or light on a substantive section (method/experiments/claims), OR',
    '- a cross-reviewer DISAGREEMENT (one thorough, another skipped/light) on such a section, OR',
    '- a quote that is too thin/generic to evidence a real read of that section.',
    'You judge COVERAGE QUALITY only. Do NOT file content charges. Do not flag a genuinely',
    'minor section (e.g. acknowledgements) just for being light.',
```
Why: three skim signals incl. cross-reviewer disagreement; a strictly scoped meta-lens that cannot add issues.

### F13 — merge: same issue only when anchor AND substance match; unsure = separate (S6; S12) · already: no
`workflows/merge.workflow.js:54-58`
```
    '1. GROUP weaknesses that are THE SAME underlying issue into one cluster (list their',
    '   member_indices). Two weaknesses are the same only when the section anchor AND the',
    '   substance genuinely match; when unsure, keep them SEPARATE (a missed merge is',
    '   recoverable; a wrong merge hides a distinct issue).',
    '2. Pick representative_index = the member whose evidence_anchor + section are the most',
```
Why: the asymmetry argument ("a missed merge is recoverable; a wrong merge hides a distinct issue") is the dedup rule for any panel aggregation.

### F14 — merge derives every scalar in code, never from the agent (S6/S7 aggregation) · already: yes (critique.py aggregates majority/rank by script)
`workflows/merge.workflow.js:6-9`
```
// and the clearest framing); every DERIVED field is computed deterministically in
// this workflow from the cluster's members, never trusted to the agent:
//   significance = MAX (major dominates),  kind = substantive if ANY member substantive,
//   raised_by    = unique reviewer_ids,    raised_by_count = |raised_by|,
```
Why: the exact derivation rules (MAX / substantive-dominates) for merging independent verdicts.

### F15 — corroboration never inflates significance (S6/S7 aggregation) · already: partial (critique.py: "Rank/verdict aggregates never enter KEEP")
`references/ledger-schema.md:143-146`
```
- corroboration (`raised_by_count`) is used ONLY for priority order + a clarity-via-conflict
  flag, NEVER to inflate `significance` (no double-count).
- The Markdown view is derived, never authoritative; edit the JSON (via the module), re-render.
- Reviewers/jurors never touch the ledger; the orchestrator owns all writes.
```
Why: three families agreeing is a priority signal, not a severity upgrade; stops the panel from double-counting.

### F16 — DEFENSE: steelman with evidence, scan the whole paper, pick grounds (S12; S7) · already: no
`workflows/trial.workflow.js:158-163`
```
    'You are the DEFENSE (the author\'s advocate) in a per-issue review trial. You have the',
    'WHOLE paper. Steelman it against ONE charge WITH EVIDENCE. Crucially, SCAN THE WHOLE',
    'PAPER for whether the charge is already addressed elsewhere (a different section, a',
    'footnote, the appendix-in-text). Pick grounds: addressed-in-text (cite WHERE),',
    'out-of-scope (name the norm), would-drift-anchor (name the frozen anchor a fix harms),',
    'severity-overstated, or charge-stands (concede). Be honest.',
```
Why: the five grounds are an enum of legitimate defenses; "charge-stands (concede)" makes honesty a schema value.

### F17 — JUROR: hear both sides, context-limited is a vote, do not guess (S12; S7) · already: no
`workflows/trial.workflow.js:177-183`
```
    'You are a TRIAL JUROR deciding whether the paper is GUILTY of one alleged flaw (is the',
    'charge VALID). You hear BOTH sides. Judge from THIS framing:',
    `  ${framing}`,
    'Vote `valid` (the paper really has this flaw), `invalid` (it does not), or',
    '`context-limited` if you genuinely cannot decide from the context shown -- in that case',
    'set `need` to the exact section/material you need (else need=""). Do not guess on missing',
    'context; do not convict on a weak charge or acquit a real flaw because the defense is glib.',
```
Why: "context-limited + need" converts insufficient context into a request instead of a forced verdict; the closing sentence is the two-sided calibration for judges.

### F18 — the twelve juror framings incl. the two decorrelators (S7 panel; S12) · already: no (our panel is split by model family, not by framing)
`workflows/trial.workflow.js:68-69,73-76`
```
  'baseline fairness and empirical rigor (is the empirical complaint fair and correct?)',
  'claims-vs-evidence (does the paper overclaim relative to what it shows here?)',
  'scope and venue fit (in scope for this venue, or out-of-scope nitpicking?)',
  'practical and deployment realism (is the practicality charge grounded?)',
  'adversarial competitor: read the paper in the MOST hostile reasonable way; is the charge valid?',
  'charitable peer: read the paper in the MOST charitable way that still respects the evidence; is it still valid?',
```
Why: "MOST hostile reasonable" / "MOST charitable … that still respects the evidence" are the bracketing lenses the source says must be present at every tier (`trial.workflow.js:79-81`).

### F19 — the deterministic verdict rule (S7 aggregation; S12) · already: partial (critique.py: drop needs ≥2 families; worst verdict for a spec)
`workflows/trial.workflow.js:12-15`
```
//   JUDGE: the verdict rule is mostly DETERMINISTIC -- decide iff quorum
//     (surviving >= ceil(0.8*jurySize)) AND one side > 60% of SURVIVING votes
//     (context-limited votes do not count). Decided-invalid -> invalid-drop;
//     all-context-limited or undecided-at-tier-12 -> author-required; undecided at
```
Why: quorum + supermajority over SURVIVING votes, abstentions excluded; undecided escalates rather than defaulting.

### F20 — JUDGE routes only; close_criterion must need no new data (S12; S8 shape of a close criterion) · already: no
`workflows/trial.workflow.js:198-205`
```
    'You are the PRESIDING JUDGE. The jury found this charge VALID by a clear majority. You',
    'do NOT re-litigate validity. ROUTE it:',
    '- valid-fixable: it can be closed by EDITING EXISTING TEXT (reword, restrict/soften a',
    '  claim to match the evidence, surface info already present). Set close_criterion = one',
    '  sentence an editor can satisfy with NO new experiment, measurement, number, or citation.',
    '- author-required: closing it needs NEW data/experiment/number/citation or author-private',
    '  intent. Set close_criterion = null. (If it could be closed EITHER by new data OR by an',
    '  honest text-only softening, PREFER the text-only fix and route valid-fixable.)',
```
Why: separates "fixable by text" from "needs data"; the PREFER clause is the bias that keeps a writer from inventing experiments.

### F21 — close_criterion as a unit-test (S8 kill_cmd analogue; S12) · already: partial (kill_cmd + canary + gate.py record; no per-issue criterion)
`references/methodology.md:61-66`
```
Every issue must carry a `close_criterion`: one concrete sentence describing what
an author edit must satisfy to close it. Issues without one are dropped at merge
(note the drop so the author sees it). After an edit lands, re-read the relevant
text and confirm the criterion holds before marking `closed`. For `override`
issues there is no criterion to satisfy; they ship as-is with the override
recorded.
```
Why: an issue without a testable closing condition is dropped; the verify-after-edit step is the test.

### F22 — RECALL: independent re-judgement of a drop, bias to revive (S11; S12) · already: no
`workflows/recall-audit.workflow.js:56-60`
```
    'You are a fresh RECALL AUDITOR (prosecution-side appeal). The charge below was DROPPED.',
    'You did not see the original trial; judge independently from the text. Was the drop WRONG?',
    'Set revive=true if the charge is in fact a real and material flaw that should NOT have been',
    'dropped; revive=false if the drop was correct (it really does not hold or is immaterial).',
    'Recall matters: revive a genuine flaw, but do not revive an immaterial or truly-invalid one.',
```
Why: the pivot-stage question for a dropped source is exactly "was the drop WRONG?", asked by someone who did not see the trial.

### F23 — recall aggregation: ANY single skeptic revives (S6/S11 aggregation) · already: no (critique.py drops on majority; no revive path)
`workflows/recall-audit.workflow.js:4-7`
```
//   MODE A (revive drops): re-examine EVERY drop (trial invalid-drops + polish-dropped
//     invalids). Was the drop WRONG? Bias to revive (recall is non-negotiable): ANY
//     single skeptic that revives flags it. recommend = 're-trial' for a never-tried
//     drop, 'escalate' for a drop that already lost a full trial.
```
Why: asymmetric aggregation (one voice suffices to revive) is the recall rule; re-trial vs escalate depends on prior history.

### F24 — SPOT-CHECK a strong consensus for correlated-wrong agreement (S7; S11) · already: partial (pivot: "同族委员会不算第二意见")
`workflows/recall-audit.workflow.js:73-79`
```
    'You are a fresh, independent skeptic stress-testing a review verdict BEFORE the paper is',
    'edited. A jury found this charge VALID by a STRONG majority and it is about to be fixed.',
    'Your job is to decorrelate from that consensus: could the agreement be CORRELATED-WRONG?',
    'Set sound=false if EITHER the agreed flaw is actually illusory/overstated on a careful read,',
    'OR the implied fix (the close_criterion) would HARM the paper or misrepresent it. Set',
    'sound=true if the charge and its fix direction genuinely hold up. Be willing to dissent from',
    'the majority; that is the point.',
```
Why: the only prompt in the source whose job is to disagree with a unanimous panel; fits a 3-family "advance" verdict before GPU.

### F25 — low confidence or few raisers weakens a consensus (S7 aggregation) · already: no
`workflows/recall-audit.workflow.js:86`
```
      ? `  NOTE: raised by ${m.raised_by_count ?? '?'} reviewer(s) at overall_confidence ~${m.reviewer_confidence ?? '?'}/5. LOWER confidence or FEWER raisers means a weaker basis for the consensus -- scrutinize harder for a correlated-wrong agreement.`
```
Why: tells the skeptic how to scale scrutiny with the provenance of the verdict.

### F26 — the deterministic recall filter (which consensus gets spot-checked) (S7 aggregation) · already: no
`references/review-engine-v3.md:114-116`
```
[SEAM 3] orchestrator CONSENSUS FILTER for recall Mode B: from the valid-fixable MAJORS, select
   those with tally.valid >= 0.8*jury_size AND escalated==false; enrich each with
   reviewer_confidence + raised_by_count from its ledger row.
```
Why: a "strong consensus" is defined numerically (≥80%, never escalated) by script, not by the skeptic.

### F27 — the completion gate cannot be faked by exhaustion (S11; loop control) · already: partial (rule 7: null ≠ verdict; INFRA-STOP)
`references/review-engine-v3.md:271-274`
```
GATE (per round) = `node ledger.js gate` = 0 GATE-BLOCKING active major, where GATE-BLOCKING =
{raised, in-trial, re-trial, valid-fixable}. author-required / queued / dropped / closed are
gate-ok. `node ledger.js unadjudicated` (active major with no verdict) must be empty too:
budget exhaustion or a stalled trial cannot fake completion.
```
Why: an item with no verdict is a blocker, not a pass; the sentence transfers directly to a stage-D deliverables gate.

### F28 — termination sanity check: a new blocker on the final read means prior closures were premature (S11; S12) · already: no
`references/methodology.md:145-151`
```
Done when the ledger has zero `blocker` and zero `major` in active statuses (not
closed / withdrawn / override), and all remaining active issues are `minor` or
`nit`. `withdrawn` and `closed` do not count; `override` ships without an edit
and does not block termination but must be re-read at submission. No score gate,
no "N consecutive clean rounds". Recommended sanity check: one more `full` round
on the final draft; if it surfaces a new blocker/major, prior closures were
premature.
```
Why: "No score gate" and the final-round falsification of earlier closures.

### F29 — CLERK dedup: unsure → genuinely new (S12 outer loop; S6) · already: no
`workflows/clerk.workflow.js:89-94`
```
    'You are the clerk checking whether a NEWLY-raised issue is the SAME underlying issue as one',
    'already on the docket (a re-raise) or genuinely new. Compare ONLY against the candidates',
    'below (they share the same passage). If it is the same issue as one of them, set same_as to',
    'that ledger_id and confidence in [0,1]; if it is genuinely new (or you are unsure), set',
    'same_as=null. When unsure, prefer null (a missed merge is recoverable; a wrong merge hides',
    'a distinct issue).',
```
Why: the agent judges similarity only; the merge GATE is a numeric threshold in code (`clerk.workflow.js:126-134`).

### F30 — assign-reviewers: subfields by professional domain, not methodology axis (S12; S2 diverge shape) · already: no
`workflows/assign-reviewers.workflow.js:86-91`
```
    `You are the program chair assigning reviewers for ONE CS paper. Read it and name the ${N}`,
    'most relevant expert SUBFIELDS (by professional domain, e.g. "3D vision / neural rendering",',
    '"video object segmentation", "optimization theory", NOT a generic methodology axis). For',
    'EACH, write a short DOMAIN OVERLAY: 2-4 sentences of the failure modes and conventions a',
    'reviewer from that subfield is especially alert to in THIS paper. Pick subfields that',
    'cover the paper\'s actual contributions with minimal overlap.',
```
Why: the overlay ("failure modes and conventions a reviewer from that subfield is especially alert to") is how the source gives each reader a distinct sensitivity without a generic lens.

### F31 — never let an agent echo an identifier (script rule for every per-item workflow) · already: partial (critique.py keys by family; sources by id in schema)
`workflows/meaning-audit.workflow.js:30-33`
```
// NOTE: anchor_id is NOT in the agent schema. We fan out one agent per anchor, so
// we KNOW which anchor each result is for and inject the id in code -- never rely on
// an agent to echo an identifier back (it confuses id with type). This pattern
// applies to every per-item workflow in the skill.
```
Why: a bundle-script rule: ids are injected by the orchestrator, never trusted from the model.

---

## S6 critique-sources · S7 critique-spec

### F32 — the three refutation angles (S6; S7) · already: partial (S6 has four checks; no "misreading"/"already-addressed" angle)
`workflows/review-panel.workflow.js:66-70`
```
const ANGLES = [
  'misreading: the issue claims something is wrong or missing that is actually present or correct in the frozen text',
  'already-addressed: the concern is already handled elsewhere in the frozen text, so the issue does not stand',
  'scope-or-severity: the concern is real but out of scope for this venue, or its severity is materially overstated',
]
```
Why: three orthogonal ways a plausible finding is wrong; each anchored fail from our panel could be re-tested against them.

### F33 — adversarial verifier calibration; keep unless a majority refute (S6; S7) · already: partial (critique.py "默认 advance"; majority drop)
`workflows/review-panel.workflow.js:193-195` and `:37-39`
```
    'Set refuted=true ONLY if, from this angle, the issue does not hold (give the',
    'reason grounded in the frozen text). Otherwise refuted=false. Be skeptical but',
    'fair: do not refute a genuine flaw just to look decisive, and do not rubber-stamp.',
```
```
// Perspective-diverse skeptics try to refute each candidate; an issue is kept
// unless a majority refute it (bias to keep, so real flaws are not lost; the human
// gate catches any residual noise).
```
Why: "do not refute a genuine flaw just to look decisive" is the anti-decisiveness sentence our critics lack; the bias direction is stated with its reason.

### F34 — precision from the verify layer, not agent count; judgment never forced (S6/S7 design) · already: partial (three families = count; script anchor check = verify layer)
`docs/REVIEW_ENGINE_V3_DESIGN.md:157-159` and `:77-78`
```
seam, with a fresh-skeptic verify of each finding); the confirmed code defects were fixed and the
orchestrator-seam contracts written into `references/review-engine-v3.md`. Precision comes from
the verify layer, not from agent count.
```
```
- On-demand context expansion: a juror returns `context-limited` + `need`; the orchestrator
  re-invokes it with the requested part (cap 2). Judgment is never forced on insufficient context.
```
Why: two rationale sentences that justify adding a "need" field and a fresh-skeptic re-check to our panel rather than a fourth family.

### F35 — polish light-check: escalate when it is actually major; flag when it needs the author (S6 four-way outcome shape) · already: no
`workflows/polish.workflow.js:78-84`
```
    'You LIGHT-CHECK one minor-substantive review item on a CS paper. Choose ONE action:',
    '- edit: a small, honest text fix closes it -> give an exact-string before/after patch',
    '  (before VERBATIM from the text; plain prose; no em-dashes; no new numbers/citations).',
    '- drop: the item is invalid or immaterial -> say why (a recall auditor will re-check drops).',
    '- escalate: on a closer look this is actually a SUBSTANTIVE, MAJOR flaw that deserves the',
    '  full trial -> say why (it will be re-tried, not silently polished).',
    '- flag: valid but cannot be closed by editing existing text (needs the author) -> say why.',
```
Why: a cheap track that can promote (never silently demote) an item; "a recall auditor will re-check drops" tells the agent its drop is reviewable.

---

## S9 build-review-focus · S10 write-review

### F36 — edit-audit verdict: holds vs drift with cross-passage number/symbol checks (S9; S10) · already: yes for numbers (write review recomputes mean/CI95 vs tex); no for symbol/reference drift
`workflows/edit-audit.workflow.js:65-72`
```
    'it could create a cross-section inconsistency. Decide ONE verdict:',
    '- holds: the rewritten text reads correctly in place AND stays consistent with the other',
    '  passages shown (no number/table mismatch, no broken reference, no contradicted definition).',
    '- drift: the edit no longer makes sense in place OR conflicts with another passage (e.g. a',
    '  result number now disagrees with the table, a symbol/term was redefined incoherently, a',
    '  reference no longer resolves). Set offending_text to the exact conflicting current text.',
    'Judge MEANING, not surface wording; do not flag a faithful edit, do not rubber-stamp a real',
    'conflict.',
```
Why: a two-value verdict with named failure classes and an `offending_text` anchor; "Judge MEANING, not surface wording" calibrates both ways.

### F37 — meaning-audit four-state verdict for a frozen sentence (S10: method_prose vs 05_method; claim vs evidence) · already: partial (review: "05_method 不得含 method_prose 之外的主张"; no weakened/now-unsupported vocabulary)
`workflows/meaning-audit.workflow.js:75-82`
```
    'Decide ONE verdict:',
    '- holds: still true AND still supported by the current text (a faithful heavy',
    '  rewrite still holds; judge meaning, not surface wording).',
    '- weakened: the anchor\'s commitment is softened (wording or support weaker).',
    '- contradicted: the current text directly conflicts with the anchor.',
    '- now-unsupported: the anchor is still stated, but the evidence that backed it',
    '  was edited away.',
    'If not `holds`, set offending_text to the exact current text that caused it',
```
Why: `now-unsupported` (claim still stated, evidence gone) is the failure a numbers-only check cannot see; the frozen anchor maps to our frozen `method_prose` and CLAIM sentence.

### F38 — arc check: problem → solution → evidence → resolution (S10) · already: no
`workflows/meaning-audit.workflow.js:91-98`
```
    'You are checking whether the SPINE of a CS paper still forms one coherent',
    'problem -> solution -> evidence -> resolution arc. Below are the frozen anchor',
    'sentences in order. Decide if the arc is unbroken: does the motivation lead to',
    'the stated gap, the gap to the contribution, the contribution to the method',
    'rationale, and (where present) the results/discussion answer back to the',
    'motivation? Return arc_intact=false ONLY if there is a real break or internal',
    'contradiction across these anchors, with the reason. A partial spine (some',
    'anchors not-yet-written) is fine; judge only the arc among the anchors present.',
```
Why: a whole-manuscript coherence check phrased as four named links, with a narrow false-trigger rule.

### F39 — experiment-analysis: no forced significant-improvement summary (S10; writer brief) · already: partial (negative results must appear; no "state that plainly" instruction)
`references/writing-toolkit.md:108-114`
```
Turn experiment data into a data-faithful {venue} results paragraph: comparison
and trend, not a number dump (SOTA margin, sensitivity, efficiency/accuracy
trade-off, ablation takeaway). If the data shows no clear advantage or trend, state
that plainly rather than forcing a significant-improvement summary. Render any
forced heading as a `\paragraph{}` run-in, not inline bold. No fabrication. Output:
LaTeX (keep back-translation author-side).
```
Why: "state that plainly rather than forcing a significant-improvement summary" is the anti-selective-narrative sentence for a results writer.

### F40 — the de-AI tell list and translationese tells (S10 register `style:`) · already: partial (manuscript_rules 禁用词 list lives in paper/.claude/CLAUDE.md; not verified here)
`references/writing-toolkit.md:69-75` (translationese tells continue `:75-77`)
```
Tells to scan for (replace only when it improves the sentence): leverage, delve,
utilize, showcase, underscore, intricate, pivotal, seamless, holistic, nuanced,
realm, tapestry, testament, landscape, "it is worth noting that", "plays a crucial
role", "in order to", rule-of-three triplets, mechanical connective stacks
(firstly / moreover / furthermore), em-dash abuse, empty -ing wind-ups, vague
attribution ("studies show"), and negative-parallelism overuse ("not only ... but
also").
```
Why: a concrete keyword list for the register lens, with "replace only when it improves the sentence" as the guard against churn.

### F41 — venue-family shared rule + vision profile (S10 register) · already: partial (register rules exist; "abstract's claims be the ones the experiments validate" not in the review prompt)
`references/reviewer-personas.md:94-98` and `:106-108`
```
- **vision** (CVPR/ICCV/ECCV/WACV): plain prose, no em-dashes, no gratuitous bold/italic
  in body text; figure/table captions conventionally use a bold run-in lead phrase
  (`\textbf{Overview.} ...`) plus sentence-case description and bold panel labels
  (`\textbf{(a-b)}`) -- this is convention, not an AI tell, do not strip it; dense
  experiments, qualitative figures expected.
```
```
All three CS families share: never accept hallucinated citations, demand fair and
vintage-correct baselines, demand that the abstract's claims be the ones the experiments
validate.
```
Why: the three shared demands are a compact S10 checklist; "this is convention, not an AI tell, do not strip it" prevents a register pass from damaging captions.

---

## S8 spec · S9 build (drafting-side guards)

### F42 — drafter: minimal edit, exact `before`, no numbers you cannot support, never fabricate to close (S8/S9; S10 writer) · already: yes for numbers (write task: 不引入 records 之外的数字); no for "set before/after equal and explain"
`workflows/drafter.workflow.js:68-75`
```
    'You are the AUTHOR drafting a MINIMAL edit to close one review charge. Make the',
    'SMALLEST change that satisfies the close_criterion AND preserves the surrounding',
    'claim\'s meaning. Output an exact-string patch:',
    '- `before`: copy VERBATIM the smallest contiguous span of the text below that you',
    '  are changing (it must appear exactly in the text).',
    afterLine,
    '  citations or numbers you cannot support, no revision notes in the text.',
    'If the only honest fix needs information not in the text (a new experiment, a',
```
(continues `:76-77`: `'number you do not have), do NOT fabricate: set before/after equal and explain in'` / `'rationale that it needs the author (the orchestrator will queue it).'`)
Why: gives the writer a legal no-op ("before/after equal") as the alternative to inventing a number; the exact-substring rule makes the patch script-applicable.

### F43 — logic-check: post-edit self-gate reports only a show-stopper (S9 second-round build check; S10) · already: no
`references/writing-toolkit.md:117-122`
```
Run AFTER a patch lands, on ONLY the edited passage: check for a logic
contradiction, an undeclared terminology switch, or severe Chinglish introduced
by the edit. Assume the patch is already high quality and report ONLY a
show-stopper; do not raise style or word-choice nits, and if there is none, emit
the pass marker. Output a pass marker or brief author-side notes; emits no prose
into the manuscript. This formalizes step 9's "verify the close_criterion" check; it
```
Why: a narrow, high-precision self-gate framing ("Assume the patch is already high quality and report ONLY a show-stopper") for a fix-round reviewer.

### F44 — the bounded-aggressive apply rule (S9 launch gate shape) · already: yes in substance (gate.py monitor: critical/high block; token names card sha + diff sha)
`references/auto-mode.md:33-35`
```
> Auto-apply a fix IFF: (a) it addresses a major (or a polish item), (b) it satisfies the
> issue's close_criterion, (c) the edit-safety guard passes, (d) the passage is within its
> rounds-touched cap, and (e) it does NOT edit a spine anchor sentence. Otherwise, QUEUE it.
```
Why: five conjunctive conditions with an explicit "otherwise QUEUE" default; the template for any auto-apply/launch rule.

### F45 — no leakage of aids into the reviewed text (S8 method_prose; S10) · already: partial (method_prose "no numbers, no results, no comparatives"; no rule about logs/notes in the manuscript)
`SKILL.md:272-276`
```
4. **No leakage into the reviewed text.** Revision logs, back-translations, and
   self-check verdicts are author-side aids; they never enter the manuscript or
   any frozen snapshot.
5. **Disagreement resolves through discussion, then override** (logged), never a
   silent dismissal.
```
Why: hard rules 4 and 5: nothing the loop writes for itself enters the artifact under review, and dismissals are always logged.
