# ResearchStudio for claude.ai

A **prompt-preserving port** of the ResearchStudio Idea skills to claude.ai's
web app, packaged as uploadable `.skill` files. Sibling of the ChatGPT port in
this repo; same integrity model, different host.

| Package | What it does |
|---|---|
| `idea-spark.skill` | The full IdeaSpark phase graph — research direction → one reviewer-defensible idea card |
| `paper-search.skill` | Paper search over arXiv + host `web_search`, deduped and relevance-ranked |
| `scoop-check.skill` | Prior-art / novelty-collision check for a specific claim |
| `idea-quality.skill` | Score an idea Markdown file (Title / Motivation / Method) at the idea stage |

## Install on claude.ai

1. Build (or take a file from `dist/`).
2. claude.ai → **Settings → Capabilities → Skills → Upload skill** → pick the
   `.skill` file. It installs read-only under `/mnt/skills/user/<name>/`.
3. Ask for the thing the skill describes. Each package's `SKILL.md` frontmatter
   carries its own trigger description, so they can be installed independently
   — though `scoop-check` uses `paper-search` when both are present.

Skills need a plan that enables them, and the bash sandbox must be available
(the packages run real Python).

## Build

```bash
python3 build.py                 # all four -> dist/*.skill
python3 build.py idea-spark      # just one
python3 build.py --no-zip        # stage into .build/ without zipping
```

The build vendors upstream files **byte-for-byte** from the pinned
ResearchStudio checkout (expected at `../../ResearchStudio`), overlays this
port's host layer, validates the frontmatter against claude.ai's limits
(name ≤64 chars, description ≤1024), and writes `PROMPT_PARITY.tsv`.

Verify any built package:

```bash
cd .build/idea-spark && python3 verify_parity.py
```

## How the port is structured

```
claude/
├── build.py                       # vendor + overlay + validate + zip
├── shared/
│   ├── ORIGIN.template.md         # parity statement, filled with the pinned commit
│   ├── package/verify_parity.py   # ships inside every package
│   └── references/
│       ├── claude-web-runtime.md   # mounts, network, phase isolation, budget
│       └── claude-web-retrieval.md # the two transports and their rules
└── <skill>/                       # host overlay only — SKILL.md + host-native scripts
    ├── manifest.json              # which upstream subtree to vendor
    └── SKILL.md                   # the claude.ai runbook
```

Nothing upstream is copied into git here. That is deliberate: the only way to
change a reasoning prompt is to move the pin, and `verify_parity.py` proves it.

### Two kinds of file, one rule

- `bundled_exact` — upstream prompts, taxonomy, rubrics, schemas, scripts, and
  the original runbook at `references/upstream/SKILL.md`. **Never edited.**
- `host_native` — this port: the root `SKILL.md`, the `claude-web-*.md` notes,
  `verify_parity.py`, and two bridge scripts.

Host policy never goes inside a reasoning prompt. A phase gets the exact prompt
file plus its named artifacts.

## What changes on claude.ai

1. **Retrieval.** arXiv runs as the real vendored connector (pure stdlib — no
   pip install, no key). The published tier that upstream gets from OpenAlex /
   Semantic Scholar / OpenReview comes from host `web_search`, normalized back
   into the upstream record schema by `scripts/host_search_ingest.py` and
   merged through upstream's own `dedup_merge`. The Claude Code install's local
   corpus of ~80K proceedings PDFs does not exist on this host.
2. **Filesystem.** `/mnt/skills/user/<name>/` is read-only, so each run copies
   the skill to `/tmp` and writes artifacts under `/mnt/user-data/outputs/`
   where the user can download them.
3. **Phase isolation.** claude.ai has no sub-agents, so upstream's fresh-context
   phases become a documented discipline rather than a mechanism.
4. **Job list.** idea-spark disables the unavailable connectors through
   upstream's own `IDEASPARK_POOL` override — `run.py` itself stays
   byte-identical to the pinned commit.

## Not ported

`ResearchStudio-Reel` (paper2poster / paper2video / paper2reel) needs
LibreOffice, ffmpeg, texlive-xetex and a Playwright Chromium — hundreds of MB
of system packages in an ephemeral sandbox. `paper2blog` is text-only and could
be ported if wanted.
