---
name: idea-spark
description: Generate ONE reviewer-defensible, implementable research idea with a concrete method and falsification plan from a stated research direction. Use for research idea generation, novelty analysis, bottleneck diagnosis, and paper-shape suggestions, including when a GitHub repository or software system is the research target. Treat repositories as systems under study rather than ordinary code review; skip debugging/refactoring and unconstrained brainstorming without research context.
---

# ResearchStudio IdeaSpark — OpenAI host

Run the ResearchStudio IdeaSpark phase graph with OpenAI-native retrieval. The eleven reasoning system
prompts under `references/system-prompts/` are upstream artifacts and must remain byte-identical to the
vendored ResearchStudio source.

Read these adapter files before starting a run:

- `references/openai-runtime.md`
- `references/native-retrieval-routing.md`
- `references/openai-phase0.md`
- `references/openai-collision.md`

The exact upstream ResearchStudio runbook is preserved at `references/upstream/SKILL.md`. Consult it for
phase semantics, schemas, gates, validators, and retry rules. Where that runbook mandates a remote Python
retrieval command, the OpenAI adapter below overrides only the transport/tool choice; it does not change
the reasoning contract.

## Core invariants

1. **Do not modify any ResearchStudio system prompt.** Never paraphrase, prepend policy text to, or append
   host-specific instructions inside `references/system-prompts/*.txt`.
2. **Pass phase artifacts, not reasoning history.** Use a fresh/isolated worker context for each LLM phase
   whenever the host supports it. If ChatGPT Web cannot provide process-level isolation, restrict the
   worker to the exact phase files and disclose that the isolation guarantee is best-effort rather than
   runtime-identical to Claude Code.
3. **Use `scripts/run.py next` as the state navigator.** Consume the complete emit; do not grep away
   continuation input lines.
4. **Native tools own remote retrieval.** Do not install or invoke `scripts/search_*.py` for remote
   retrieval in native mode. Keep the vendored scripts untouched as the explicit upstream fallback.
5. **Python remains for deterministic work:** state inspection, JSON patch/merge, citation/schema checks,
   Phase 4 assembly, validation, and rendering.
6. **GitHub evidence is system evidence, not scholarly novelty evidence.** Code/issues/PRs/commits may
   establish architecture, constraints, aliases, and failure modes. A novelty verdict still requires the
   scholarly collision pool.

## Inputs

The minimum user input is a research direction. Optional inputs include:

- target repository/system (GitHub URL or name);
- user papers/files;
- contribution type;
- compute budget;
- explicit baselines or forbidden directions.

Do not ask for missing optional fields mid-run; follow the upstream intake-routing behavior.

## Host loop

Choose a fresh run directory, then repeatedly run:

```bash
python3 "$SKILL_DIR/scripts/run.py" next --dir "$RUN_DIR" --query "<user research question>"
```

For each emit:

- If it is fresh Phase 0 / literature retrieval, perform the native Phase 0 adapter instead of the emitted
  Python retrieval command.
- If it is Phase 3.1 collision retrieval (including a stale-term rerun), perform the native collision
  adapter instead of `phase3_collision`.
- If an LLM phase needs an anchor full-text top-up, resolve it with native web retrieval rather than
  `phase1_fulltext_topup`.
- If a user/host reference needs remote resolution, use native web/GitHub/File tools and update the same
  canonical artifact that the upstream command would have produced.
- For deterministic local steps, run the emitted `scripts/run.py` command unchanged.
- For LLM steps, load the exact system prompt path emitted by the navigator and provide only the named
  inputs plus the adapter-only target-system input described below.

Repeat until `next` reports `DONE`, `do_not_generate`, or `phase_3_failed`.

## Native Phase 0

Follow `references/openai-phase0.md` and `references/native-retrieval-routing.md`.

Use, in priority order:

1. authorized GitHub connector/app for repository code/docs/issues/PRs/commits when a repo is in scope;
2. native web search for scholarly retrieval and full text;
3. Files for user-provided papers, notes, PDFs, and project material;
4. public-web GitHub only as a fallback for public repositories when the connector cannot serve them.

Write the canonical Phase 0 artifacts, including:

- `phase0/.lit_grounding_mode` = `webfallback` for OpenAI-native scholarly retrieval. This is the exact
  upstream-compatible sentinel value for non-connector live web retrieval; `source_manifest.json` records
  that the transport was intentional native retrieval rather than an accidental degraded path.
- `phase0/lit_results.json` (literature only)
- `phase0/lit_table.md`
- `phase0/fulltext_cache.json`
- `phase0/target_context.json`
- `phase0/source_manifest.json`

Never fabricate a paper, abstract, full-text method detail, repository fact, issue rationale, or commit
behavior.

### Repository input to Phase 1

When `phase0/target_context.json` is non-empty, add that file path to the **Phase 1 input list** as an
adapter context file. Do not modify `bottleneck_identify.txt` or any other system prompt. The file carries
system-under-study evidence only: exact code paths/symbols, architecture constraints, issue/PR/commit
references, measurable failure observations, and provenance.

If the host cannot add an extra file to the Phase 1 worker, mirror the same object under a reserved
`_target_context` key in `fulltext_cache.json` with `kind: "target_system_evidence"` and
`cite_as_literature: false`; keep `lit_results.json` literature-only.

## Native Phase 3.1 collision

Follow `references/openai-collision.md`.

Search both channels:

- candidate `signature_terms` with the recent window;
- cross-community `alias_terms` with the wider multi-year window.

Write `phase3_collision/collision_hits.json`, `.collision_terms.json`, and `source_manifest.json` in the
upstream-compatible locations. GitHub may contribute vocabulary/implementation hints, but
`collision_hits.json` must remain literature-only. Do not decide novelty here; the unchanged
`critique.txt` worker owns that verdict.

## Reasoning phases

Run each reasoning phase against the exact ResearchStudio prompt emitted by the navigator:

- Phase 1: `bottleneck_identify.txt`
- Phase 2 selection/generation: `ideate_select.txt`, `ideate_generate.txt`
- Phase 2.3 coherence: `coherence_trace.txt`
- Phase 3 audit/recheck/revision: `critique.txt`, `refutation_recheck.txt`, `revise.txt`,
  `falsification_reaudit.txt`
- Phase 4: `expand.txt`, `derive_plain.txt`, `implementability_audit.txt`

Preserve the upstream output schemas, citation gate, blocking-evidence disposition rules, information-gain
retry ladder, kill-switch integrity, and Phase 4 validators.

## Output

Return the same terminal artifacts as ResearchStudio: the three rendered idea cards on success,
`do_not_generate.md` for an out-of-scope/ungroundable direction, or `phase_3_failed.md` when the bounded
gauntlet exhausts its information-gain retry budget.
