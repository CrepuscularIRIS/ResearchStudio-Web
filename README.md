# ResearchStudio-Web

[ResearchStudio](https://github.com/microsoft/ResearchStudio)'s Idea skills,
ported to hosts whose only retrieval transport is **web search** — claude.ai,
Claude Code without a paper corpus, and ChatGPT.

No API keys. No connectors. No local corpus. No `pip install`.

| Skill | What it does |
|---|---|
| **idea-spark** | A research direction → one reviewer-defensible idea card with a concrete method and a falsification plan |
| **paper-search** | Find papers on a topic and year range; deduped, relevance-ranked, with a written synthesis |
| **scoop-check** | Does this specific novelty claim collide with published work? |
| **idea-quality** | Score an idea (Title / Motivation / Method) at the idea stage, before any experiment exists |

## Install

**claude.ai** — Settings → Capabilities → Skills → Upload skill, then pick a
file from [`dist/`](dist/). Each `.skill` is independent.

**Claude Code** — add this repo as a plugin marketplace:

```
/plugin marketplace add CrepuscularIRIS/ResearchStudio-Web
/plugin install researchstudio-web
```

**ChatGPT / Codex** — the sibling port lives in [`openai/`](openai/), packaged
the same way with its own host adapter.

## What "prompt-preserving" means here

The eleven reasoning system prompts, the ideation taxonomy, the C00-C30
tactical cards, the rubrics, the schemas and the validators are vendored
**byte-for-byte** from a pinned `microsoft/ResearchStudio` commit. Every
package ships `PROMPT_PARITY.tsv` (a Git blob SHA-1 per file) and a checker:

```bash
cd skills/idea-spark && python3 verify_parity.py
# pinned: microsoft/ResearchStudio @ 0597891df1a1
# verified 110/110 files
# OK: byte-identical to the pinned commit.
```

Two kinds of file, one rule:

- `bundled_exact` — upstream reasoning material. Never edited. A drift here
  fails the check.
- `host_native` — this port's adapter: the root `SKILL.md`, the two
  `references/*.md` notes, `verify_parity.py`, and one ingest script. **The
  only place host policy is allowed to live.** Host policy never goes inside a
  reasoning prompt.

## Retrieval: web search, and nothing else

Upstream runs arXiv / OpenAlex / Semantic Scholar / OpenReview connectors and,
in Claude Code, a local corpus of proceedings PDFs. None of that exists on a
web host — and a sandbox's network egress is a per-account setting that can
disappear without warning, so a bash-driven connector is a dependency you
cannot promise.

So this port retrieves with the host's own `web_search`: snippets triage,
`web_fetch` confirms the papers that are actually going into the corpus, and
`scripts/websearch_ingest.py` writes them into upstream's record schema through
upstream's own `dedup_merge`. That is not an improvisation — it is upstream's
own `lit_grounding_mode = webfallback`, made first-class, with every row
carrying `retrieved_via: webfallback` so a reader always knows what the
evidence rests on.

Four rules keep the corpus honest, and they are enforced in the ingest script
as well as the prompt: scholarly sources only, never invent a record, abstracts
are quoted rather than written, and **no URL means no row**.

## Build

```bash
git clone https://github.com/microsoft/ResearchStudio      # the pinned upstream
export RESEARCHSTUDIO_REPO=$PWD/ResearchStudio

python3 claude/build.py                    # -> claude/dist/*.skill  (claude.ai)
python3 claude/build.py --emit skills      # -> skills/<name>/       (Claude Code)
python3 claude/build.py idea-spark         # just one
```

The build vendors upstream at its pinned commit, overlays the host layer,
validates each `SKILL.md` against claude.ai's frontmatter limits (name ≤64
chars, description ≤1024), writes `PROMPT_PARITY.tsv`, and zips. Nothing
upstream is committed to this repo by hand — moving the pin is the only way to
change a prompt.

```
claude/                 port source: build.py, shared adapters, per-skill overlays
skills/                 built packages (what the Claude Code plugin installs)
dist/                   built .skill files (what claude.ai uploads)
openai/idea-spark/      the ChatGPT port
```

## Not included

`ResearchStudio-Reel` (paper2poster / paper2video / paper2reel) needs
LibreOffice, ffmpeg, texlive and a headless Chromium — not something a web
sandbox can carry.

## License

MIT, matching upstream. Upstream reasoning material remains
© Microsoft under its own MIT license; see `ORIGIN.md` inside each package for
the pinned commit and the parity boundary.
