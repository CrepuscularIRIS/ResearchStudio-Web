# OpenAI adapter — Phase 3.1 native retrieval collision search

This is adapter logic, not an upstream ResearchStudio system prompt.

Read the canonical candidate, its `signature_terms` and `alias_terms`, the Phase 0 literature table, and
`target_context.json` when present. Use live scholarly web retrieval for the collision pool. Do not call
the bundled Python search connectors.

Search two scholarly channels:

- `signature`: the candidate's own vocabulary, emphasizing the recent window.
- `alias`: cross-community vocabulary, using a wider multi-year window to catch renamed ancestors.

Prefer authoritative paper pages and venue/publisher sources. Deduplicate by DOI/arXiv ID/title. Write
`<RUN_DIR>/phase3_collision/collision_hits.json` as a JSON list. Every hit must include at least:
`paper_id`, `title`, `year_month`, `venue`, `url`, `abstract`, `collision_channel`, `query`, and a simple
`relevance_score`. Keep no more than ~120 relevant hits per channel. Also write
`collision_hits.full.json` if a larger pool was collected.

When the candidate targets a GitHub-hosted system, the GitHub connector may be used only as a vocabulary
and implementation-awareness channel: inspect repository code/issues/PRs for alternative names or known
implementations that suggest additional scholarly queries. Do NOT place GitHub-only records into
`collision_hits.json`, and do not use repository evidence alone to declare novelty or non-novelty.

Write `source_manifest.json` with the web queries/sources used and any GitHub-derived vocabulary hints.
Do not decide novelty here. Retrieval only; the unchanged `critique.txt` prompt owns the verdict.
