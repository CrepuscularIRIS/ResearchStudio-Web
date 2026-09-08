# OpenAI adapter — Phase 0 native retrieval grounding

This is adapter logic, not an upstream ResearchStudio system prompt.

Read `user_query.txt` and `references/native-retrieval-routing.md`. Build two evidence layers in one
retrieval pass: (A) recent scholarly grounding and (B) target-system grounding when the user names a
repository, codebase, project, or uploaded artifact.

## A. Scholarly grounding — native web

Use live web search rather than the bundled Python retrieval scripts. Search multiple complementary
queries for the user's direction, prioritizing work from the most recent ~24 months plus every paper
explicitly named by the user. Prefer authoritative paper pages: arXiv, OpenReview, publisher/venue pages,
Semantic Scholar, OpenAlex, and official author/project pages when needed. Deduplicate by DOI, arXiv ID,
then normalized title.

For the strongest candidates and user-named anchors, retrieve enough source text to recover introduction
and method details. Prefer accessible HTML/full text. If only an abstract is available, retain the paper
and mark the full-text record as failed rather than inferring the method from memory.

## B. Target-system grounding — GitHub / Files / web

If the query includes a GitHub repository URL or clearly names a repository, prefer the authorized GitHub
connector. Resolve the repository, then inspect only evidence relevant to the research direction:
README/docs, architecture files, code search hits, exact source files, high-signal issues, pull requests,
and recent commits. Use public web GitHub pages only when the connector cannot retrieve the public
resource.

If user files are available, use the host Files capability to search/read them and treat them as explicit
anchors. Do not duplicate file text into prompts unnecessarily; record compact evidence with source
identifiers.

Do not perform generic code review. Repository evidence should identify structural assumptions,
operational constraints, recurring failure modes, and implementability boundaries that can inform a
research bottleneck.

## Required artifacts

Write these artifacts under `<RUN_DIR>/phase0/`:

1. `.lit_grounding_mode` containing exactly `webfallback` when OpenAI-native live scholarly retrieval succeeded. This is the upstream-compatible sentinel for live web retrieval outside the bundled connectors; record the intentional native transport in `source_manifest.json`. Use `connector_failure` only when no usable native scholarly retrieval was possible.
2. `lit_results.json`: a JSON list or object containing, for each retained paper, at minimum
   `paper_id`, `title`, `authors`, `year_month`, `venue`, `url`, `abstract`, `retrieved_via`.
Compatibility note for `retrieved_via`: preserve the upstream source labels expected by downstream
prompts. When the authoritative page is arXiv, OpenReview, Semantic Scholar, or OpenAlex, set
`retrieved_via` to `arxiv`, `openreview`, `semanticscholar`, or `openalex` respectively even though the
transport was ChatGPT native web. Use `webfallback` only for records whose authoritative origin cannot be
represented by those upstream labels. The actual transport/tool provenance belongs in
`source_manifest.json`.

3. `lit_table.md` with columns exactly:
   `paper_id | year_month | venue | title | ideation pattern tags | bottleneck this paper targets | open issue / unresolved gap | resolves_problem | retrieved_via`.
   Keep roughly 20-40 high-signal results when available. `ideation pattern tags` must use the 15 IDs in
   `references/ideation-patterns/overview.md` or `outside_taxonomy`.
4. `fulltext_cache.json`: for the strongest ~15 candidates plus every user-named anchor, include
   `paper_id`, `source_used`, `intro`, `method`, and `warning`; use `source_used: "failed"` when enough
   full text cannot be obtained.
5. `target_context.json`: always write this file. Use `{}` when there is no target system. Otherwise use
   a compact object with `target_kind`, `repository` or `artifact`, `architecture_evidence`,
   `failure_evidence`, `implementation_constraints`, and `retrieval_warnings`. Each evidence item must
   include a source identifier/URL plus a concise factual observation.
6. `source_manifest.json`: provenance for every native retrieval channel used. Record at minimum
   `retrieval_mode: "native_retrieval"`, scholarly web sources/queries, GitHub resources queried (or the
   reason GitHub was unavailable), user files consulted, and any fallbacks.
7. `fulltext/index.json` plus one `<paper_id>.md` file per full-text record when convenient. The JSON blob
   remains canonical.

Never invent full-text details or repository facts. Repository evidence supplements the literature map;
it does not replace the scholarly basis for novelty claims.
