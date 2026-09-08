# research-harness

Microsoft ResearchStudio's `idea_spark` skill, on two tracks. A research direction in, a
reviewer-defensible idea card out.

- **Local** — one Claude Code workflow, a 1:1 replica of the upstream pipeline rather than a
  re-interpretation of it. Every gate runs; hours; reproducible and auditable.
- **Web** — a skill that asks the hosted IdeaSpark the same question on `chatgpt.com` through the
  playwright extension, up to five conversations in parallel. 30–60 minutes, and far more
  literature behind the answer.

Neither replaces the other, and the same judge scores both.

```
/research-harness:init  <slug> "<one sentence: the research direction>"
/research-harness:spark <slug>              # local track — the workflow
/research-harness:web   <slug> --from-run   # web track — one window per Phase 1 gap
```

Three cards land in `ideaspark_run/<slug>/phase4/`: plain Chinese, plain English, and the
reviewer version. Or `do_not_generate.md` when the direction cannot be grounded, or
`phase_3_failed.md` when the idea died in the gauntlet and the retry budget ran out. Those
are the only three outcomes, and they are upstream's.

## What "1:1" means here, and how it is checked

The upstream skill is a phase graph (`scripts/next_step.py`) plus eleven system prompts. A
host is supposed to run its navigator, do what each emit says in an isolated context, and
loop. This plugin replaces the *host*, not the pipeline:

| | |
|---|---|
| **Prompts** | The 11 system prompts and 8 rubrics are packed into the workflow **byte for byte** by `scripts/ideaspark_src/gen.py`. A seat receives the verbatim contract plus ~1.6 KB of frame (you are a fresh sub-agent; these are your tools; write this file once). Nothing about goals, repositories or house style is appended — a test forbids the words. |
| **Logic** | The phase graph is ported to JS (`decide()`), driven by a read-only python probe that prints one JSON snapshot of the run directory. No text emit is parsed. Every deterministic step still runs upstream's own `run.py` subcommand. |
| **Proof** | A differential test feeds 52 layered run-directory fixtures to *both* upstream's `next` and `decide()` and asserts they pick the same step — every reachable node of the graph, including the bounded audit bounces, the information-gain retry ladder, the broken-gate terminal, and both Phase 0 env switches. **57/57.** |

The gates come with it, because they are the pipeline: the mandatory full-text gate, the
citation gate, the executed dry-run at 2.3, the blocking-evidence disposition guard, the
kill-switch byte-identity check, the retry budget, and the nine validators before render.

## What was changed on purpose

Four deviations, each declared and each tested:

1. **Per-seat model routing.** Upstream has two tiers (a host reasoning model and a fast
   classifier) and forbids downgrading the open-ended steps. This plugin routes each seat to
   a named model instead — Opus for every large/open-ended seat, GLM for the two mechanical
   ones and the host-level chores, and a three-model panel where a panel helps. The upstream
   tier is kept in the seat table as a `tier` field and a test asserts the mapping still
   honours "never downgrade an open-ended step".
2. **Phase 0.5 coverage check runs three judges** (Opus, Sol, K3) and unions their nominations
   instead of one. Every nomination is still connector-verified before admission, so a wider
   net cannot admit an unverified paper; the union is capped at 16 and drops are logged.
3. **A scoring stage after the cards**, using the suite's own `evaluation/idea_quality` skill:
   three independent judges, absolute plus blind pairwise, then a deterministic aggregate that
   surfaces where they disagree.
4. **One retry per seat** in a fresh context when the first attempt returns nothing.

Pattern tagging fans out to 2–3 parallel shards above 40 papers. That is not a deviation —
upstream sanctions it explicitly and its own validating merger rejects the whole set if a row
is malformed, the row count is wrong, or a paper is missing.

## The web track

`skills/ideaspark-web/` drives `chatgpt.com`. The prompt opens with the trigger line
`@ResearchStudio IdeaSpark Use IdeaSpark.` followed by the intake, one field per line, and ends
with a marker line the skill adds:

```
@ResearchStudio IdeaSpark Use IdeaSpark.
Target system: PhyAgentOS.
Research direction: long-horizon agents suffer from context growth and unreliable memory
  retrieval. I want a method that makes memory selection causally relevant to future tool decisions.
Contribution type: method.
Compute budget: 8×H100.
End your answer with the single line <<END OF IDEA CARD>> and nothing after it.
```

The marker is what turns "is it finished?" into a fact. An answer counts as captured only when the
marker is present, nothing is streaming, the turn carries its copy button, and the text stopped
growing across two polls — **a truncated capture is an unfinished answer, never a short one**.
Chats are persistent, one question per window, and the conversation URL goes in the manifest,
because that URL is the audit trail.

`scripts/web/web.py seed --from-run` is the point of running two tracks: it turns each gap the
local run's Phase 1 left unaddressed into its own web question, and adds the audit's
paper-pointed threat as a differentiation constraint. Run it whenever a local run reaches Phase 1,
and again when it finishes.

## Requirements

- For the local track, a `claude-kimi` session. The seat table pins model ids (`claude-opus-5`, `glm-5.3[1m]`,
  `k3-256k`, `gpt-5.6-sol`) that resolve on a local LiteLLM route. On the official Anthropic
  API those ids do not exist and the session model is served instead, silently.
- `python3` with `feedparser openreview-py beautifulsoup4 pymupdf` (upstream's connectors and
  full-text fetch). Optional: `xelatex` or `tectonic` for the PDF cards.
- For the web track, the `playwright-extension` MCP connected to a browser already signed in to
  ChatGPT. The skill never signs in, never clicks through account dialogs, and never pastes local
  file contents into the chat.
- Connector credentials: copy `vendor/researchstudio/.env.template` to `.env` **beside it** and
  fill in the OpenReview user/password and a Semantic Scholar key. `run.py` walks up from the
  skill directory and stops at the first `.env` it finds, so keep them in one file — a second
  `.env` deeper in the tree shadows it and the connector is skipped without an error.

## Layout

```
workflows/ideaspark.workflow.js     the local track (generated — edit the source, not this)
scripts/ideaspark_src/              logic + generator; `python3 gen.py` rebuilds the workflow
skills/ideaspark-web/               the web track: trigger format, browser protocol, completion rule
scripts/web/web.py                  seeds the web prompts, indexes the captures
vendor/researchstudio/              upstream idea_spark + idea_quality, MIT, unmodified
tests/                              differential test, fixtures, selftest.sh
commands/                           /init, /spark, /web
```

`tests/selftest.sh` runs everything: generator round-trip, byte-identical prompts, the
differential test, probe purity, and an install into a scratch project. No model calls, no
network.

## Upgrading the upstream

Replace `vendor/researchstudio/`, re-run `python3 scripts/ideaspark_src/gen.py`, then
`tests/selftest.sh`. If upstream moved the phase graph, the differential test says so
immediately and names the fixture where the two disagree.

## Licence

This plugin: MIT. `vendor/researchstudio/` is an unmodified copy of
[microsoft/ResearchStudio](https://github.com/microsoft/ResearchStudio) at commit `0597891`,
redistributed under its own MIT licence — see `vendor/researchstudio/PROVENANCE.md`.
