# OpenAI native retrieval routing

This file is a ChatGPT/Codex runtime adapter. It changes retrieval plumbing only. It does not replace or
rewrite any ResearchStudio reasoning system prompt.

## Routing priority

Use the strongest host-native source for each evidence type:

1. **User-provided files** — when papers, notes, PDFs, or project files are present, use the host Files
   connector/search/read capability first for those materials. Treat user files as explicit anchors and
   preserve their provenance.
2. **GitHub connector** — when the research target is a GitHub repository or the user names a repo,
   prefer the authorized GitHub connector for repository metadata, README/docs, code search, exact file
   contents, issues, pull requests, and commits. Do not scrape GitHub HTML when the connector can return
   the structured resource directly.
3. **Native web search** — use live web search for scholarly retrieval, paper pages, venue pages,
   documentation, and public web evidence. Prefer authoritative sources such as arXiv, OpenReview,
   publisher/venue pages, Semantic Scholar, OpenAlex, and official project documentation.
4. **Public-web GitHub fallback** — if the GitHub connector is unavailable or cannot access a public
   repository, web retrieval may inspect public GitHub pages. Mark this as a fallback in provenance.

Do not call the bundled `scripts/search_*.py` retrievers on ChatGPT or Codex. They remain unchanged upstream fallback code. Python remains appropriate for deterministic local tasks such as state inspection,
JSON transformation, merge operations, validation, and rendering.

## Repository evidence protocol

When a repository is part of the user's research target, collect only evidence that can affect the
research bottleneck or implementability. Prefer:

- repository identity, description, default branch, recent activity;
- README / architecture / design docs;
- code paths implementing execution, scheduling, memory, tool use, recovery, evaluation, or other
  subsystems relevant to the user's direction;
- high-signal issues and pull requests that document recurrent failures, design constraints, or rejected
  approaches;
- recent commits when they materially change the subsystem under study.

Do not turn IdeaSpark into a general code review. Ignore style issues, ordinary refactoring debt, missing
unit tests, and isolated bugs unless they expose a structural research bottleneck.

## Evidence discipline

Every retrieved fact must remain traceable to a source record. Do not convert parametric memory into a
citation. Do not invent missing abstracts, file contents, issue details, PR rationale, commit behavior,
or full-text method details.

Repository evidence is **system-under-study evidence**, not literature novelty evidence. Novelty claims
must still be decided primarily from scholarly retrieval. GitHub can expose implementation collisions or
vocabulary aliases, but the Phase 3 scholarly collision pool remains the authoritative novelty input.

## Native artifact protocol

For every native retrieval pass, write `source_manifest.json` beside the canonical artifacts. It must
record query text, source URL or connector identifier, retrieval channel (`web`, `GitHub`, or `Files`),
and whether the source supplied metadata, abstract, or full text.

When a repository/system is in scope, write `target_context.json` separately from the scholarly pool.
It contains only system-under-study evidence: exact repository paths/symbols, issue/PR/commit references,
architecture constraints, and measurable failure observations. Keep `lit_results.json` and
`collision_hits.json` literature-only.

Remote-retrieval Python commands in the upstream runbook are capability requests, not mandatory
implementations on OpenAI hosts. Substitute native tools for `phase0`, `phase0_fulltext`,
`phase1_fulltext_topup`, host/user reference resolution, and `phase3_collision`. Continue to use Python
for deterministic state inspection, JSON merge/patch operations, schema validation, assembly, and
rendering.
