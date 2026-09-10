# Retrieval: web search only

Host adapter. Not an upstream prompt.

**Every paper in a run comes from the host's own web search.** No connector, no
API key, no `pip install`, no shelling out to arXiv. Upstream's
`scripts/search_*.py` are present because the vendored engine imports them;
they are compatibility stubs on this host and must not be executed.

Why: a sandbox's network egress is a per-account setting that can vanish
without warning, and a bash-driven connector spends tokens on transport output
that says nothing about the papers. Web search is always available, and its
output is already the part that matters.

## The loop

For each query the intent step produced:

1. **Search** — one `web_search` call, phrased as a researcher would phrase it,
   not as a keyword soup. Add the year window in words ("2025", "2026") when
   the window matters; the tool has no date parameter.
2. **Read the results list, not the pages.** Titles plus snippets are enough to
   decide what belongs. Fetching a page costs 10-50x the tokens of reading a
   snippet.
3. **Fetch only what earns it** — `web_fetch` a paper's page when the record is
   going into the evidence corpus AND its abstract is not already in the
   snippet. A paper you will cite is worth one fetch; a paper you are
   triaging is not.
4. **Stop when two consecutive searches surface nothing new.** That is
   coverage. A fixed quota is not — filling one is how a corpus gets padded
   with near-misses.

Target 20-40 papers for a Phase 0 corpus, fewer for a focused collision check.

## What may enter the corpus

**Scholarly pages only**: arxiv.org, openreview.net, aclanthology.org,
proceedings.mlr.press, neurips.cc, thecvf.com, publisher pages, an author's
copy of their own paper. Never a blog post, a paper-summary site, an X thread,
or an LLM-written listicle.

**Four hard rules:**

1. **Never invent a record.** Title, authors, year and URL must come from a
   result you actually saw. No URL → no row.
2. **Abstracts are quoted, never written.** Copy from the snippet or the fetched
   page. Not retrieved → leave it empty. Downstream treats an empty abstract as
   "unknown"; it treats an invented one as fact.
3. **Year is the venue year** when the page shows one, else the preprint year.
4. **Provenance is recorded.** Every row carries `retrieved_via: "websearch"`.
   A run says plainly that its corpus came from web search — that is honest
   grounding, not a caveat to bury.

## Writing the corpus

Collect rows in one JSON list and hand it to the ingest script. Do not
hand-write `lit_results.json`, and do not edit it after the fact — the schema,
the dedup keys and the survey demotion are upstream behaviour, and the script
is what applies them.

```json
[
  {
    "title": "Exact Paper Title",
    "authors": ["First Author", "Second Author"],
    "year": 2026,
    "venue": "ICLR",
    "url": "https://openreview.net/forum?id=...",
    "abstract": "Quoted from the page, or omitted.",
    "doi": "10.xxxx/yyyy"
  }
]
```

```bash
python3 -m scripts.websearch_ingest --raw <raw.json> --run-dir <phase0 dir>
```

The script computes the dedup keys, tags provenance, merges through upstream's
own `dedup_merge`, demotes surveys to the bottom, and refuses any row without a
retrievable URL.

## Repository evidence

A GitHub target belongs in `phase0/target_context.json`, never in
`lit_results.json`. Literature novelty claims may rest only on scholarly
evidence; a repo can constrain the system under study, not establish prior art.
