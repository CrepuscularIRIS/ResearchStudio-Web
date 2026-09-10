---
name: paper-search
description: Search academic papers on a topic and year range with web search, then present a deduped, relevance-ranked table plus a written synthesis of trends, themes and a reading path. Use when the user asks to find papers, related work, prior art, or recent publications on a topic, especially when they name a date range or venues like NeurIPS, ICLR, ICML, ACL or CVPR. Not for reading one specific paper the user already has.
---

# ResearchStudio paper-search — web-search host

Read `references/host-runtime.md` and `references/websearch-retrieval.md`
first. `references/upstream/SKILL.md` is the preserved upstream runbook and
remains the authority on **what to display and how to synthesize** — the ranked
table, the Step 1.5 relevance filter, and the summary sections. This file
changes only where papers come from.

## Retrieval

There is no CLI on this host. Do not run `scripts/search_papers.py` or any
connector — retrieval is `web_search`, following the loop and the four source
rules in `references/websearch-retrieval.md`.

Infer everything from the user's message and start immediately — never ask for
confirmation:

- **queries**: rephrase the question into 2-4 focused searches. Different
  phrasings of one idea, not one phrasing repeated.
- **year window**: what the user said, else the last two years.
- **how many**: enough that two consecutive searches stop surfacing anything
  new. That is usually 15-30 papers, and it is a stopping rule, not a quota.

`web_fetch` a paper's page only when it is going into the final table and its
abstract is not in the snippet. Snippets triage; fetches confirm.

## Presenting results

Follow `references/upstream/SKILL.md`: one ranked markdown table with every
paper that survives the relevance filter, then the model-knowledge section,
then the summary (overview, trends, key themes, keyword frequency, reading
path). Four host-specific notes:

1. **Judge relevance from what you actually read.** Upstream's Step 1.5 filter
   assumes abstracts are in a JSON file; here they are in your context from the
   search. A paper whose abstract you never saw cannot be dropped as
   irrelevant — when unsure, keep it.
2. **Citation counts are usually unavailable.** Web search rarely surfaces
   them. Write "n/a" rather than 0, say once that counts were unavailable, and
   do not rank by them.
3. **Every row needs a URL** — the one you retrieved it from. A row you cannot
   link is a row you cannot include.
4. **Model recall is labelled.** Papers you add from memory rather than search
   go in the model-knowledge section with that label, never mixed into the
   searched table.

If the user wants the report as a file, write it to the run directory
(`references/host-runtime.md` names it per host) and say where it is — but
always display the full report inline too. The file is a copy, not a
replacement for showing the work.
