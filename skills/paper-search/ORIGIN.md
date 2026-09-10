# Origin and compatibility boundary

Skill: `paper-search`
Built: 2026-09-10

Upstream reasoning source: `microsoft/ResearchStudio`
Pinned upstream commit: `0597891df1a153b8e4cbdc8c1c685f43a0a6abcf`
Upstream subtree: `ResearchStudio-Idea/skills/paper_search`

This package is a **prompt-preserving claude.ai port with host-native retrieval
fallback**. The compatibility target is prompt + artifact-contract parity, not
byte-for-byte runtime parity.

## Integrity boundary

Files marked `bundled_exact` in `PROMPT_PARITY.tsv` are vendored from the
pinned commit and must stay byte-identical to it. That covers every reasoning
system prompt, the ideation taxonomy, the rubrics, the schemas, the validators,
and the upstream runbook preserved at `references/upstream/SKILL.md`.

Files marked `host_native` are this port's adapter layer — the root `SKILL.md`,
the `references/host-runtime.md` and `references/websearch-retrieval.md` notes,
and any script that exists only to
bridge a host gap. They may diverge from upstream, and they are the ONLY place
host policy belongs.

Do not prepend, append, paraphrase, or merge host policy into a reasoning
system prompt. A reasoning phase receives the exact prompt file plus only the
named phase artifacts.

## Intentionally adapted for claude.ai

1. **Retrieval is host web search, and nothing else.** No connector runs: the
   vendored `scripts/search_*.py` are compatibility stubs. Papers are found
   with `web_search`, read from snippets, confirmed with `web_fetch` only when
   a record needs it, and written into upstream's record schema by
   `scripts/websearch_ingest.py` through upstream's own `dedup_merge`. This is
   upstream's own `lit_grounding_mode = webfallback`, made first-class: no API
   keys, no sandbox egress dependency, and no transport chatter in context.
2. **Filesystem.** On claude.ai the installed skill is read-only at
   `/mnt/skills/user/`, so a run copies itself to `/tmp` and writes artifacts
   under `/mnt/user-data/outputs/` where the user can download them. In Claude
   Code it runs in place.
3. **Phase isolation.** claude.ai has no sub-agents, so upstream's fresh-context
   phases become a documented discipline: exact prompt + named artifacts only,
   no carried reasoning history.
4. **Budget.** Retrieval stops adaptively rather than filling a fixed quota;
   the upstream lit-table row expectation is preserved as documentation, not as
   a hard gate.

See `references/host-runtime.md` and `references/websearch-retrieval.md`.

## Verification

```bash
python3 verify_parity.py          # inside the package
```

The check recomputes the Git blob SHA-1 of every `bundled_exact` file and fails
on any drift from the pinned commit.

## Non-equivalence statement

This port preserves reasoning-prompt bytes, pinned reference identities,
schemas, and phase artifact contracts. It does not preserve upstream's Python
retrieval stack — no connector runs here — and it does not claim
token-identical outputs across models or search backends.
