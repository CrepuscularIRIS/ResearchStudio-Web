# Host runtime adapter

This file is a **host compatibility layer**. It is NOT part of the upstream
ResearchStudio prompt set, and nothing in it may be pasted into, prepended to,
or merged with a reasoning system prompt.

## Integrity boundary

The pinned ResearchStudio tree is the semantic source of truth. Preserve
exactly, byte for byte:

- every file under `references/system-prompts/`;
- the ideation taxonomy and the C00-C30 sub-pattern cards;
- schemas, rubrics, validators, and the artifact contracts;
- the original runbook, preserved at `references/upstream/SKILL.md`.

`PROMPT_PARITY.tsv` records which files are `bundled_exact` (must match the
pinned commit) and which are `host_native` (this adapter). Adapt transport and
plumbing only.

## Two hosts, one package

| | claude.ai | Claude Code |
|---|---|---|
| Skill lives at | `/mnt/skills/user/<name>/` — **read-only** | `~/.claude/skills/<name>/` or a plugin dir |
| Run directory | `/mnt/user-data/outputs/<name>-<ts>/` | `./<name>-run-<ts>/` in the project |
| Uploaded input | `/mnt/user-data/uploads/` — read-only | any path the user names |
| Search tool | `web_search` / `web_fetch` | `WebSearch` / `WebFetch` |
| Sub-agents | none | available, but not required by this package |

Everything else is identical. Retrieval is web search on both — see
`websearch-retrieval.md`.

## Preflight

```bash
# claude.ai — the installed skill is read-only, so work from a copy.
export PYTHONDONTWRITEBYTECODE=1
cp -r /mnt/skills/user/<name> /tmp/<name> && cd /tmp/<name>
export RUN_DIR="/mnt/user-data/outputs/<name>-$(date +%Y%m%d-%H%M%S)"

# Claude Code — run in place.
cd <skill dir>
export RUN_DIR="$PWD/<name>-run-$(date +%Y%m%d-%H%M%S)"

mkdir -p "$RUN_DIR"
```

## What bash is and is not for

**Not for retrieval.** No `curl`, no arXiv API call, no connector script. The
vendored `scripts/search_*.py` exist because the engine imports them; they are
stubs on this host. Running one is a bug, not a shortcut.

**Yes for deterministic state**: `scripts/run.py next` (the phase navigator),
`dedup_merge`, the validators, the Phase 4 assembly, and the ingest script.
These are cheap, exact, and they save tokens — a validator that returns one
line replaces a page of the model re-deriving what a schema requires.

Python 3 with the standard library is all that is needed. Nothing here calls
`pip`.

## Phase isolation

Upstream runs some phases in a fresh context. claude.ai has no sub-agents, so
that isolation is a discipline:

- load the exact phase prompt file plus **only** the named input artifacts;
- do not carry prior reasoning, earlier drafts, or discarded candidates across
  a phase boundary — a phase's inputs are files, not conversation;
- write the phase's output artifact before starting the next phase.

State lives in artifacts. When unsure what comes next, run
`python3 -m scripts.run next --dir "$RUN_DIR"` rather than guessing.

## Token discipline

This package is built to run inside one conversation, so spending is the real
constraint:

- read a search result's snippet before deciding to fetch its page;
- never `cat` an artifact you just wrote — the writer already knows it;
- read a reference file when the phase needs it, not preemptively;
- quote the lines that carry a judgment, not whole sections.

## Non-equivalence statement

This port preserves reasoning-prompt bytes, pinned reference identities,
schemas, and phase artifact contracts. It does not preserve upstream's
connector stack: retrieval is host web search, which upstream itself models as
`lit_grounding_mode = webfallback`. It does not claim token-identical outputs
across hosts or search backends.
