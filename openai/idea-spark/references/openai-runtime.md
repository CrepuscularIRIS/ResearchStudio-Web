# OpenAI runtime adapter

This file is an OpenAI-host compatibility layer. It is NOT part of the upstream ResearchStudio prompt set.

## Integrity boundary

The OpenAI Skill is assembled from the vendored ResearchStudio `idea_spark` tree and then overlaid with a
small OpenAI control plane. The upstream tree is the source of truth for:

- all eleven files under `references/system-prompts/`;
- the ideation taxonomy and C00-C30 sub-pattern cards;
- deterministic scripts and validators;
- schemas, rubrics, and the original runbook.

The exact upstream `SKILL.md` is preserved at `references/upstream/SKILL.md`. The installed root
`SKILL.md` is intentionally OpenAI-specific because the upstream runbook hard-codes Python/API retrieval;
putting both host policies in the same entrypoint would create contradictory instructions. Do not change
ResearchStudio reasoning prompts to fit OpenAI hosts. Adapt only retrieval transport and host plumbing.

## Tool mapping

Map ResearchStudio host capabilities as follows:

- Scholarly/external retrieval: use native web search and authoritative paper/venue/publisher pages.
- GitHub target systems: prefer the authorized GitHub connector/app for repository, file, code, issue, PR,
  and commit evidence; use public web only as a fallback for public repositories.
- User material: use Files search/read for uploaded papers, PDFs, notes, and project documents.
- File state: write phase artifacts at the exact run-directory paths expected by the upstream navigator.
- Deterministic work: use the vendored `scripts/run.py` commands for state inspection, merging, validation,
  Phase 4 assembly, and rendering.
- Fresh-context phases: use delegated/fresh contexts when the host supports them. On ChatGPT Web, where
  process-level phase isolation is not guaranteed, load only the exact prompt and named input artifacts
  and do not pass prior reasoning history.

The bundled `scripts/search_arxiv.py`, `search_openalex.py`, `search_openreview.py`, and
`search_semanticscholar.py` remain unchanged upstream fallback code. In native mode, do not execute them;
perform the corresponding remote retrieval with OpenAI-native tools and write the same downstream
artifacts.

## Native retrieval phases

The OpenAI host overrides only remote retrieval operations, principally Phase 0, full-text/reference
resolution, and Phase 3.1 collision retrieval. Follow `references/native-retrieval-routing.md`,
`references/openai-phase0.md`, and `references/openai-collision.md`.

Repository/system evidence lives in `phase0/target_context.json`. Keep it separate from
`lit_results.json`, which remains literature-only. Pass `target_context.json` to Phase 1 as adapter context
without modifying `bottleneck_identify.txt`. If the host cannot add an extra Phase 1 input, mirror the same
object under the reserved `_target_context` key in `fulltext_cache.json` and mark it
`cite_as_literature: false`.

## State and isolation

Use `scripts/run.py next` as the authoritative state navigator. Phase boundaries communicate through
artifacts, not hidden reasoning history. A reasoning worker receives the exact upstream system prompt plus
the exact named artifacts for that phase. GitHub evidence can constrain the system-under-study, but only
scholarly evidence may support literature novelty/collision judgments.

## Non-equivalence statement

This port preserves ResearchStudio prompt bytes, cards, deterministic scripts, schemas, and phase artifact
contracts. It does not claim token-identical outputs across models/search backends, and ChatGPT Web does not
provide the same process-level fresh-context isolation as the Claude Code workflow. The intended parity is
prompt + artifact + phase-graph compatibility with OpenAI-native retrieval.
