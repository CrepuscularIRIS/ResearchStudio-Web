# Source routing — which connector handles which query type

## arXiv — [scripts/search_arxiv.py](../scripts/search_arxiv.py)

- **Strength**: freshest preprints, no auth, full abstracts.
- **Use for**: 6-month freshness scan in map mode; 6-month focused window in collision mode.
- **Auth**: none.
- **Rate**: throttle to 3 req/s. Use the `export.arxiv.org/api/query` endpoint with `sortBy=submittedDate&sortOrder=descending`.

## OpenAlex — [scripts/search_openalex.py](../scripts/search_openalex.py)

- **Strength**: comprehensive academic graph (~250M works), full abstracts, citation counts. Broad coverage including journals + adjacent fields.
- **Use for**: peer-reviewed proceedings + journals (6-24mo) in both map and collision modes.
- **Auth**: `OPENALEX_API_KEY` from env. Without it the polite-pool still works but rate is lower.
- **Rate**: ≥10 req/s with key, ≥1 req/s without. The connector pages with `cursor` for stable pagination.
- **Caveat**: OpenAlex's broad indexing causes some drift (~11% of hits drift to adjacent fields like biology/medicine for ML queries). Combine with Semantic Scholar to compensate.

## Semantic Scholar — [scripts/search_semanticscholar.py](../scripts/search_semanticscholar.py)

- **Strength**: CS-focused academic graph (~200M works), returns **TLDR auto-summary** (Allen-AI 1-sentence) and **`externalIds` block** with DOI + ArXiv ID + DBLP key + MAG ID + PMID — enabling cross-source dedup without title-only matching.
- **Use for**: peer-reviewed proceedings + journals (6-24mo). DBLP keys arrive via `externalIds`, so no standalone DBLP connector is needed.
- **Auth**: `SEMANTICSCHOLAR_API_KEY` strongly recommended. Apply free at https://www.semanticscholar.org/product/api#api-key-form
- **Rate**: 1 req/sec **cumulative across all SS endpoints** (introductory key tier); ~100 req/5min anonymous (bursty, frequent 429s). Connector sleeps 1.1s between calls when authenticated.
- **Caveat**: similar drift to OpenAlex (~73% on-topic in test) — keyword-search-driven, not topic-classified.

## OpenReview — [scripts/search_openreview.py](../scripts/search_openreview.py)

- **Strength**: conference submissions for ICLR / NeurIPS / ICML (current + previous cycle) — in-review and recently decided work that may not yet have full peer-reviewed metadata elsewhere.
- **Use for**: 0–18 calendar-month submission-pool scan in map mode. **Not free-text search** — paginate by `content.venueid`, then keyword-score. Short windows miss NeurIPS May cycles.
- **Auth**: `OPENREVIEW_USER` + `OPENREVIEW_PASS` from env.
- **Intensity knobs**: window 18mo, cap 20 unique, 80/query, 2000 notes/venue paginated, timeout 900s.

## Source selection rules

```
mode=map:        arXiv(0-6mo) + OpenAlex(6-24mo) + OpenReview(0-18mo) + Elsevier/Scopus CAS-Q1(0-24mo)
mode=collision:  arXiv + OpenAlex + OpenReview (+ Elsevier if key present) over COLLISION windows
```

## Elsevier / Scopus — [scripts/search_elsevier.py](../scripts/search_elsevier.py)

- **Strength**: CAS-Q1 journal lane via Scopus Search + `EXACTSRCTITLE` whitelist.
- **Auth**: `ELSEVIER_API_KEY` required; `ELSEVIER_INST_TOKEN` optional for COMPLETE abstracts.
- **Limits**: STANDARD view usually has no abstract; SD full-text needs institutional entitlement.

If any source is unavailable (429 after retries, network down), continue with the others and emit a `lit_source_unavailable: <source>` warning. Do not silently skip.

## Dedup priority order

When the same paper appears in multiple sources after title-normalization:

1. Prefer **OpenAlex** (full abstract + citation count, broad coverage).
2. Then **Elsevier/Scopus** (CAS-Q1 venue lock + DOI/cites).
3. Then **OpenReview** (in-review conference pool).
4. Then **arXiv** (preprint; lowest priority for published-window dedup).
