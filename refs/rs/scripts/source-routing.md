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

- **Strength**: **CCF-A conference pool on OpenReview** — ICLR, NeurIPS, ICML, **CVPR, ICCV, ECCV**, AAAI, ACL, EMNLP, NAACL, CoRL, RSS (current + previous year).
- **Use for**: 0–18 calendar-month conference submission / public-note scan. **Not free-text search** — OpenReview rejects title-only queries. Per venue we try, in order: `content.venueid` → `content.venue` label (`"CVPR 2026"`) → invitation `/-/Submission`, then keyword-score title+abstract.
- **Auth**: `OPENREVIEW_USER` + `OPENREVIEW_PASS` from env.
- **Caveats**:
  - CVPR/ICCV often expose only a **partial** public note set via `venue` string after the cycle; final PDFs live on **CVF Open Access**, not OpenReview.
  - A paper can be **CVPR 2026 on CVF** but only appear on OpenReview as **ICLR withdrawn** (different venueid) — OR alone will not tag it as CVPR.
- **Phase0 knobs**: window 18mo, cap 25 unique, 80/query, `--per-venue-cap 1500`, timeout 1200s.

## Source selection rules

```
mode=map:        arXiv(0-6mo) + OpenAlex(6-24mo) + OpenReview(0-18mo CCF-A) + CVF(CVPR/ICCV/ECCV full) + Elsevier CAS-Q1(0-24mo)
mode=collision:  same connectors over COLLISION windows (cvf/elsevier if available)
```

## CVF Open Access — [scripts/search_cvf.py](../scripts/search_cvf.py)

- **Strength**: **full** CVPR / ICCV / ECCV proceedings from `openaccess.thecvf.com` (~3–4k papers/year). This is where final CVPR PDFs live; OpenReview only has a partial public note set.
- **Use for**: computer-vision conference coverage that OR cannot provide (e.g. *Generative Modeling of Weights…* is CVPR 2026 on CVF but ICLR-withdrawn on OpenReview).
- **Auth**: none. Indexes cached under `~/.cache/ideaspark/cvf/` (7-day TTL).
- **Phase0 knobs**: window 18mo, cap 25 unique, 40/query, abstract fill for top hits, timeout 600s.
```

## Elsevier / Scopus — [scripts/search_elsevier.py](../scripts/search_elsevier.py)

- **Strength**: CAS-Q1-oriented **journal** inventory via Scopus Search (`EXACTSRCTITLE` whitelist: Information Fusion, KBS, ESWA, Pattern Recognition, Neural Networks, …).
- **Use for**: journal-track idea mapping; Elsevier venues poorly surfaced by arXiv/OpenReview.
- **Auth**: `ELSEVIER_API_KEY` (required). Optional `ELSEVIER_INST_TOKEN` for COMPLETE view / abstracts when entitled.
- **Limits**: free keys typically get `view=STANDARD` only (title, venue, DOI, citations — often **no abstract**). ScienceDirect Search/full-text often 401 without institutional entitlements.
- **Phase0 knobs**: window 0–24mo, cap 15 unique, 20/query, timeout 300s.

If any source is unavailable (429 after retries, network down), continue with the others and emit a `lit_source_unavailable: <source>` warning. Do not silently skip.

## Dedup priority order

When the same paper appears in multiple sources after title-normalization:

1. Prefer **OpenAlex** (full abstract + citation count, broad coverage).
2. Then **Elsevier/Scopus** (CAS-Q1 venue lock + DOI/cites; abstract only with Inst Token).
3. Then **OpenReview** (in-review conference pool).
4. Then **arXiv** (preprint; lowest priority for published-window dedup).
