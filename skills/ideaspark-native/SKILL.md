---
name: ideaspark-native
description: Host-side native-retrieval adapter for the research-harness IdeaSpark Claude Code workflow. Use from /research-harness:spark to intercept ResearchStudio Phase 0 literature/system retrieval and Phase 3.1 collision retrieval with Claude Code WebSearch/WebFetch and an available GitHub MCP/connector, while delegating all reasoning phases to the existing isolated-seat ideaspark workflow. Keep retrieval_mode=upstream as the reproducible Python-connector fallback.
---

# IdeaSpark native host adapter

This is a host adapter, not a replacement for ResearchStudio's reasoning pipeline.

Do not rewrite, paraphrase, prepend to, or append to the eleven ResearchStudio system prompts. Do not
run bottleneck, ideation, coherence, critique, revision, or expansion reasoning in the parent context.
Those steps stay in the existing `ideaspark` workflow's fresh isolated seats.

The adapter owns only retrieval-heavy host work. The invariant is: **phase artifacts cross boundaries;
reasoning history does not.**

## Control loop

Read the run's `args.json`. `retrieval_mode` defaults to `native` when absent. Accepted values:

- `native`: intercept Phase 0 and Phase 3.1 below.
- `upstream`: do not intercept; let the existing workflow use vendored ResearchStudio Python connectors.

For `native`, repeat until a terminal state:

1. Run the vendored navigator read-only:
   `python3 "$SKILL_DIR/scripts/run.py" next --dir "$RUN_DIR" --query "$DIRECTION"`.
2. Inspect `STATE`, `STEP`, and `TYPE` only. Never execute an emitted retrieval command blindly.
3. If the next step is fresh **Phase 0 retrieval**, perform Native Phase 0 below.
4. If the next step is **Phase 3.1 collision retrieval** (including a stale-collision rerun), perform
   Native Phase 3.1 below.
5. Otherwise call `Workflow` with `name: "ideaspark"`, the same args, and `max_steps: 1`. This is what
   preserves the existing seat isolation and phase graph while giving the host a chance to intercept
   the next retrieval state.
6. Re-run the navigator and continue. Do not use `resumeFromRunId`; the artifact directory is the resume.

If `retrieval_mode=upstream`, call the existing `ideaspark` workflow normally and do not materialize
native retrieval artifacts.

## Native Phase 0

Use native tools rather than the bundled `search_*.py` connectors. Prefer:

1. **GitHub MCP/connector** when the user names a repository, GitHub URL, codebase, package, agent system,
   or other implementation target. Inspect README/docs, architecture-defining code, issues, PRs, and
   recent commits that are relevant to the stated research question. Do not perform generic code review.
2. **WebSearch/WebFetch** for scholarly retrieval. Prefer primary paper/venue/publisher pages and current
   authoritative records. Search the user's vocabulary plus an escape-mechanism query in the vocabulary
   of the possible solution family.
3. User-provided files/references when present.

Build a broad but relevant literature pool, deduplicate by DOI/arXiv/OpenReview ID/title, then perform the
same conceptual precision stages the upstream host expects: relevance partition, pattern tagging, coverage
check, and full-text acquisition for the candidate/core pool. Never invent an abstract, venue, date,
identifier, citation, or full-text detail.

Materialize these paths exactly:

- `phase0/user_query.txt` — the original user research question verbatim.
- `phase0/lit_results.json` — **literature-only** JSON records. Repository/issues/PR evidence never becomes
  a fake paper record.
- `phase0/lit_table.md` — the normal ResearchStudio 9-column literature table using the vendored
  `references/pattern-summary-rubric.md` contract.
- `phase0/fulltext_cache.json` — canonical full-text/abstract evidence for the core paper pool. A reserved
  top-level `_target_context` entry may mirror the target-system evidence described below so Phase 1 can
  see implementation constraints without changing its system prompt. Mark it explicitly as
  `kind: "target_system_evidence"` and `cite_as_literature: false`.
- `phase0/source_manifest.json` — every web query/source plus GitHub operations used, with retrieval time
  and provenance sufficient to audit the pool.
- `phase0/target_context.json` — when a repository/system is in scope: architecture facts, exact file/code
  paths or symbols, issue/PR/commit evidence, measurable failure modes, and implementation constraints.
  Every claim must carry a GitHub URL/ref or connector identifier. Omit the file when there is no target
  system.

`phase0/lit_results.json` must remain literature-only even when `target_context.json` exists.

Before returning to the host loop, verify all JSON parses and that every `lit_table.md` paper_id exists in
`lit_results.json`. Do not create ResearchStudio private markers merely to skip gates; the canonical
artifacts above are the compatibility boundary.

## Native Phase 3.1 collision

Read the canonical candidate chosen by the navigator and its `signature_terms` / `alias_terms`. Search two
scholarly channels:

- `signature`: candidate vocabulary with an emphasis on the recent ~10-month window.
- `alias`: cross-community vocabulary over a wider ~48-month window to catch renamed ancestors.

Use WebSearch/WebFetch for the scholarly pool. GitHub may be consulted only for implementation-awareness
and vocabulary hints (for example, an issue uses another mechanism name); GitHub-only records must not be
inserted into the collision literature pool.

Materialize exactly:

- `phase3_collision/collision_hits.json` — **literature-only** list. Each hit should include at least
  `paper_id`, `title`, `year_month`, `venue`, `url`, `abstract`, `collision_channel`, `query`, and a simple
  `relevance_score`. Deduplicate by stable identifier/title.
- `phase3_collision/.collision_terms.json` — the exact `signature_terms` and `alias_terms` used. This keeps
  the upstream stale-hit guard meaningful after a coherence patch.
- `phase3_collision/source_manifest.json` — scholarly queries/sources and any GitHub-derived vocabulary
  hints, clearly separated.

Retrieval only: **do not decide novelty** and do not issue an advance/revise/abandon judgment here. The
unchanged `critique.txt` fresh seat owns the collision interpretation and verdict.

If signature terms are missing, follow the navigator's collision-mode intent-recognition contract to add
3-5 tight terms to the candidate before searching. If alias terms are missing, add 2-4 cross-community
names rather than silently dropping the alias channel.

## Failure and fallback

If native tools cannot establish enough scholarly provenance or full text, do not fabricate. Report the
specific missing evidence and either:

- continue with a clearly degraded native artifact only when the upstream prompt permits abstract-only
  evidence, or
- set `retrieval_mode=upstream` for the run and resume through the existing Python connectors.

Never mix a partial native collision pool with an upstream pool without recording both routes in
`source_manifest.json`.
