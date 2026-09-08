# Native Retrieval + OpenAI IdeaSpark Design

## Goal

Keep ResearchStudio IdeaSpark's research-reasoning contracts intact while adapting the host layer for two supported surfaces:

1. Claude Code: preserve the existing isolated-seat workflow and phase graph, but let the host intercept retrieval-heavy steps with native Web/GitHub capabilities.
2. ChatGPT/Codex: ship one installable OpenAI Skill that uses native web search, GitHub connector/app access, and uploaded files, while retaining the eleven ResearchStudio reasoning prompts byte-for-byte.

## Architecture

### Claude Code track

The existing `workflows/ideaspark.workflow.js` remains the authoritative isolated-seat executor. It is not rewritten. The `/research-harness:spark` command becomes a host adapter that drives the workflow one step at a time (`max_steps=1`). Before each workflow step it asks the vendored ResearchStudio navigator what is next.

The adapter intercepts only retrieval-owned states:

- Fresh Phase 0: use Claude Code native web search/fetch and an available GitHub MCP/connector when the target is a repository or codebase. Materialize the canonical Phase 0 artifact protocol (`user_query.txt`, `lit_results.json`, `lit_table.md`, `fulltext_cache.json`) so the existing workflow resumes at Phase 1 without invoking the upstream Python search connectors. Preserve a separate `target_context.json` and also expose it inside the Phase 1-readable full-text cache under a reserved non-paper key.
- Phase 3.1 collision: use native scholarly web search, with GitHub only as a vocabulary/implementation-awareness channel. Write `collision_hits.json`, `.collision_terms.json`, and `source_manifest.json`. Do not decide novelty in the retrieval adapter; unchanged `critique.txt` owns the verdict.

Every other step is delegated back to the existing workflow for exactly one step. This retains fresh sub-agent seats, the 57/57-tested phase routing, all deterministic gates, and unchanged ResearchStudio reasoning prompts. An explicit `retrieval_mode=upstream` escape hatch preserves the previous Python connector path for reproducibility.

### ChatGPT/Codex track

Add `openai/idea-spark/` as the shared OpenAI Skill source. It contains:

- ChatGPT/Codex entrypoint `SKILL.md`.
- `agents/openai.yaml` product metadata.
- ResearchStudio system prompts byte-identical to the pinned upstream commit.
- Native retrieval and collision adapter instructions.
- A deterministic state/merge/validation runner; upstream Python search scripts remain unchanged as the explicit fallback path.

Tool priority:

1. GitHub connector/app for repositories, code, issues, PRs, commits, and repo-grounded system evidence.
2. Native web search for scholarly discovery, paper pages, venue pages, and collision retrieval.
3. Files for user-supplied papers, repo notes, and local evidence.
4. Python only for deterministic state transitions, merges, schema checks, and rendering in native mode.

ChatGPT Web does not guarantee process-level fresh-context isolation. Documentation must therefore claim prompt parity and phase-input discipline, not runtime identity. Codex may provide stronger task/process isolation depending on its execution surface, but the Skill must not assume it.

### Shared provenance and packaging

`vendor/researchstudio/` remains the sole upstream source of truth. OpenAI packaging verifies the eleven prompt files against the vendored copies and overlays the exact C00-C30 sub-pattern cards from the vendor into the distributable `skill.zip` so the upload is self-contained.

The old Playwright `skills/ideaspark-web/` path is removed to avoid three competing web entrypoints.

## Interfaces and artifacts

Claude native Phase 0 must produce:

- `phase0/user_query.txt`
- `phase0/lit_results.json`
- `phase0/lit_table.md`
- `phase0/fulltext_cache.json`
- `phase0/source_manifest.json`
- optional `phase0/target_context.json`

`lit_results.json` remains literature-only. Repository evidence is never fabricated as a paper record.

Claude native Phase 3.1 must produce:

- `phase3_collision/collision_hits.json`
- `phase3_collision/.collision_terms.json`
- `phase3_collision/source_manifest.json`

`collision_hits.json` remains literature-only; GitHub evidence may only suggest search vocabulary and implementation context.

## Testing

- Keep the current ResearchStudio workflow differential suite untouched.
- Add static/contract tests for the Claude host adapter: native-by-default, upstream fallback, `max_steps=1`, Phase 0 interception, Phase 3.1 interception, no prompt rewriting.
- Add OpenAI Skill tests: required layout, metadata, 11 prompt byte identity, native retrieval routing, GitHub-target routing, package cleanliness, exact vendored sub-pattern overlay.
- Build `skill.zip` from the repository source and verify it contains no `__pycache__`, `.pyc`, or credential files.

## Repository surface

- Rewrite README around two supported surfaces: Claude Code and OpenAI (ChatGPT/Codex).
- Remove Playwright-specific requirements and `/web` command from the primary product surface.
- Bump plugin version and describe native retrieval rather than browser automation.
