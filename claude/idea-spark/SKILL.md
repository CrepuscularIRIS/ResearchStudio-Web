---
name: idea-spark
description: Generate ONE reviewer-defensible, implementable research idea with a concrete method and falsification plan from a stated research direction. Use when the user asks for a research idea, novelty analysis, bottleneck diagnosis, or a paper-shape suggestion, including when a GitHub repository or software system is the research target. Treat repositories as systems under study rather than ordinary code review. Skip code review, debugging, and unconstrained brainstorming without research context.
---

# ResearchStudio IdeaSpark — web-search host

Run the ResearchStudio IdeaSpark phase graph with **web search as the only
retrieval transport**. The eleven reasoning system prompts under
`references/system-prompts/` are upstream artifacts and must stay
byte-identical to the vendored ResearchStudio source.

Read before starting a run:

- `references/host-runtime.md` — paths, what bash is and is not for, phase isolation
- `references/websearch-retrieval.md` — the search loop, source rules, stopping policy

`references/upstream/SKILL.md` is the preserved upstream runbook and **the
authority on phase semantics, schemas, gates, validators and retry rules**.
This file overrides only how papers are retrieved.

## Core invariants

1. **Never modify a system prompt.** Load `references/system-prompts/*.txt`
   as-is; no paraphrase, no prepended host policy.
2. **Never run a connector script.** `scripts/search_*.py` are stubs on this
   host. Papers come from `web_search`.
3. **Phases talk through artifacts.** Exact prompt + named files in, artifact
   out. No reasoning carried across a phase boundary.
4. **`scripts/run.py next` is the navigator.** Ask it what comes next.

## Phase 0 — retrieval

```bash
export PYTHONDONTWRITEBYTECODE=1
cp -r /mnt/skills/user/idea-spark /tmp/idea-spark && cd /tmp/idea-spark   # claude.ai only
export RUN_DIR="/mnt/user-data/outputs/idea-spark-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR/phase0"
```

**Step 1 — queries.** Read `references/intent-recognition.md` (Map mode) and
write 3-5 queries yourself: one broad-domain, one method-signature, one
most-similar-problem, and one in the escape-mechanism vocabulary the field
itself uses. Also list any paper or system the user NAMED without a link — a
bare name is invisible to the URL regex and must be resolved by search.

**Step 2 — search.** Run the loop in `references/websearch-retrieval.md`: one
`web_search` per query, read snippets rather than fetching pages, `web_fetch`
only a paper that is going into the corpus and whose abstract you still lack.
Stop when two consecutive searches return nothing new. Target 20-40 papers.

**Step 3 — build the corpus.** Write the rows to
`$RUN_DIR/phase0/websearch_raw.json` (schema in the retrieval reference), then:

```bash
python3 -m scripts.websearch_ingest \
  --raw "$RUN_DIR/phase0/websearch_raw.json" \
  --run-dir "$RUN_DIR/phase0" \
  --query "<the user's research direction, VERBATIM>"
```

That one command writes `user_query.txt`, `user_refs.json`, `lit_results.json`
(deduped through upstream's own `dedup_merge`, surveys demoted) and the
`lit_grounding_mode = webfallback` marker. Re-run it with more rows any time;
new papers merge into the existing corpus.

Do **not** run `python3 -m scripts.run phase0` — it is the connector path.

**Step 4 — the host-LLM steps.** From here, ask the navigator:

```bash
python3 -m scripts.run next --dir "$RUN_DIR"
```

It will route you through the 0.4 relevance partition, the pattern summary and
the 0.5 coverage check, naming the rubric file and the artifact each one owes.
Read the rubric it names; do not skip a step to save time — Phase 1's entry
assertion checks for the artifacts.

Full text: upstream's `phase0_fulltext` is a connector-era step. On this host,
`web_fetch` the handful of papers a phase actually needs to read (the user's
named refs, the closest adjacent work) and quote from what you fetched. Do not
try to fetch the whole corpus.

## Phases 1-4

Follow `references/upstream/SKILL.md` exactly, with `$RUN_DIR` as the run
directory and `scripts/run.py next` between phases. Phase 3.1 collision
retrieval uses the same web-search loop as Phase 0, ingested the same way into
its own run directory.

## Deliverables

Artifacts already live under `$RUN_DIR`, which on claude.ai is downloadable.
When a run ends, tell the user:

- the idea card (the Phase 4 artifact) — the deliverable;
- `phase0/lit_results.json` — the evidence corpus, every row carrying
  `retrieved_via: webfallback`;
- that the corpus came from web search, and anything that degraded or was
  skipped.

If the run stops early, name the phase it reached and the next command. A
half-run with a named next step is useful; a half-run presented as finished is
not.

## Failure modes

| Symptom | Cause | What to do |
|---|---|---|
| `Read-only file system` | running from `/mnt/skills/user/…` | Copy to `/tmp` first |
| navigator says "no literature retrieved yet" | `lit_results.json` missing | Run the Step 3 ingest command |
| a phase demands a fresh sub-agent | upstream assumes one | Load the prompt + named artifacts only; see host-runtime.md |
| `ModuleNotFoundError` from a connector | you ran a `search_*.py` stub | Don't; retrieval is `web_search` |

## What this port does not do

No connectors, no API keys, no local corpus, no process-level fresh-context
isolation. `ORIGIN.md` states the parity boundary; `verify_parity.py` proves
the prompt bytes are intact.
