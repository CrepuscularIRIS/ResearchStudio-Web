"""Elsevier / Scopus search connector — CAS Q1 journal lane.

Why: arXiv / OpenAlex / OpenReview under-cover Elsevier-native journal inventory
(Information Fusion, KBS, ESWA, Pattern Recognition, …). Scopus Search API
indexes those serials with EXACTSRCTITLE filters.

Auth (env):
  ELSEVIER_API_KEY   required  — X-ELS-APIKey (dev.elsevier.com)
  ELSEVIER_INST_TOKEN optional — X-ELS-Insttoken; unlocks COMPLETE view / abstracts
                                  and ScienceDirect full-text when the institution
                                  is entitled. Without it we use view=STANDARD
                                  (title, venue, DOI, citations; usually no abstract).

API (verified):
  GET https://api.elsevier.com/content/search/scopus
  Headers: Accept: application/json, X-ELS-APIKey: <key>
  Query: query=<Scopus boolean>, count, start, date=YYYY-YYYY, view=STANDARD|COMPLETE
  Free academic keys often allow STANDARD only; COMPLETE → 401 AUTHORIZATION_ERROR.
  ScienceDirect Search (/content/search/sciencedirect) may also 401 without entitlements.

I/O:
  python3 -m scripts.search_elsevier --queries '["..."]' --window-months 24 --out hits.json

Rate: academic keys commonly ~20k requests/week (see X-RateLimit-* response headers).
Pace ~0.3s between calls.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

SCOPUS_SEARCH = 'https://api.elsevier.com/content/search/scopus'

# Default CAS-Q1-oriented CS / AI / IS journal set (Scopus EXACTSRCTITLE strings).
# Override via --journals "A|B|C" or env ELSEVIER_CAS_Q1_JOURNALS (pipe- or comma-separated).
# Names must match Scopus serial titles closely; quotes are added by the query builder.
DEFAULT_CAS_Q1_JOURNALS: tuple[str, ...] = (
    'Information Fusion',
    'Knowledge-Based Systems',
    'Expert Systems with Applications',
    'Pattern Recognition',
    'Neural Networks',
    'Engineering Applications of Artificial Intelligence',
    'Applied Soft Computing',
    'Neurocomputing',
    'Information Sciences',
    'Future Generation Computer Systems',
    'Swarm and Evolutionary Computation',
    'Advanced Engineering Informatics',
    'Information Processing and Management',
    'Computer Vision and Image Understanding',
    'Journal of Network and Computer Applications',
    'Decision Support Systems',
    'Computers in Industry',
    'Artificial Intelligence in Medicine',
    'Medical Image Analysis',
    'ISPRS Journal of Photogrammetry and Remote Sensing',
)


def normalize_title(t: str) -> str:
    return re.sub(r'\W+', ' ', (t or '').lower()).strip()[:80]


def _parse_journals(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        env = os.environ.get('ELSEVIER_CAS_Q1_JOURNALS', '').strip()
        raw = env
    if not raw:
        return list(DEFAULT_CAS_Q1_JOURNALS)
    parts = re.split(r'[|,;]', raw)
    return [p.strip() for p in parts if p.strip()]


def _journal_clause(journals: list[str]) -> str:
    """Build (EXACTSRCTITLE("A") OR EXACTSRCTITLE("B") …)."""
    bits = [f'EXACTSRCTITLE("{j}")' for j in journals]
    return '(' + ' OR '.join(bits) + ')'


def _escape_query_phrase(q: str) -> str:
    """Light sanitise for TITLE-ABS-KEY(...). Strip characters that break Scopus syntax."""
    q = (q or '').strip()
    q = re.sub(r'[(){}\\"]+', ' ', q)
    q = re.sub(r'\s+', ' ', q).strip()
    return q


def _api_get(params: dict) -> dict:
    key = os.environ.get('ELSEVIER_API_KEY', '').strip()
    if not key:
        raise RuntimeError('ELSEVIER_API_KEY not set')
    headers = {
        'Accept': 'application/json',
        'X-ELS-APIKey': key,
        'User-Agent': 'research-studio-idea/1.0 (CAS-Q1 Scopus connector)',
    }
    inst = os.environ.get('ELSEVIER_INST_TOKEN', '').strip()
    if inst:
        headers['X-ELS-Insttoken'] = inst
    url = SCOPUS_SEARCH + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:600]
        raise RuntimeError(f'Scopus HTTP {e.code}: {body}') from e


def _entry_to_record(e: dict) -> dict | None:
    title = (e.get('dc:title') or '').strip()
    if not title:
        return None
    doi = (e.get('prism:doi') or '').strip()
    cover = (e.get('prism:coverDate') or '')[:10]  # YYYY-MM-DD
    year = None
    if cover[:4].isdigit():
        year = int(cover[:4])
    elif (e.get('prism:coverDisplayDate') or '')[:4].isdigit():
        year = int(e['prism:coverDisplayDate'][:4])
    eid = (e.get('eid') or e.get('dc:identifier') or '').replace('SCOPUS_ID:', '')
    # COMPLETE view carries abstract as dc:description; STANDARD usually does not.
    abstract = (e.get('dc:description') or '').strip()
    try:
        cites = int(e.get('citedby-count') or 0)
    except (TypeError, ValueError):
        cites = None
    creators = e.get('dc:creator') or ''
    authors = [a.strip() for a in creators.split(';') if a.strip()][:6] if isinstance(creators, str) else []
    venue = e.get('prism:publicationName') or ''
    paper_url = f'https://doi.org/{doi}' if doi else (e.get('prism:url') or '')
    return {
        'title': title,
        'title_norm': normalize_title(title),
        'abstract': abstract,
        'year': year,
        'venue': venue,
        'authors': authors,
        'citations': cites,
        'source': 'elsevier',
        'source_id': eid or doi or normalize_title(title)[:40],
        'doi': doi,
        'paper_url': paper_url,
        'published_iso': cover if len(cover) >= 7 else '',
        'scopus_eid': e.get('eid') or '',
        'openaccess': bool(e.get('openaccessFlag') or e.get('openaccess') in (1, '1', True)),
    }


def search(query: str, journals: list[str], start_year: int, end_year: int,
           max_results: int = 25, view: str = 'STANDARD') -> list[dict]:
    """Scopus TITLE-ABS-KEY search restricted to the CAS Q1 journal list."""
    phrase = _escape_query_phrase(query)
    if not phrase:
        return []
    # date=YYYY-YYYY is year-granular on Scopus Search.
    date_range = f'{start_year}-{end_year}'
    scopus_q = f'TITLE-ABS-KEY({phrase}) AND {_journal_clause(journals)}'
    # Prefer COMPLETE only when inst token present (otherwise 401).
    if view == 'COMPLETE' and not os.environ.get('ELSEVIER_INST_TOKEN', '').strip():
        view = 'STANDARD'

    out: list[dict] = []
    start = 0
    page = min(25, max_results)  # Scopus free tier page size is typically ≤25
    while len(out) < max_results:
        data = _api_get({
            'query': scopus_q,
            'date': date_range,
            'count': str(page),
            'start': str(start),
            'view': view,
            'sort': 'relevancy',
            'httpAccept': 'application/json',
        })
        res = data.get('search-results') or {}
        entries = res.get('entry') or []
        if not entries:
            break
        # Error-as-entry when zero results
        if len(entries) == 1 and entries[0].get('error'):
            break
        for e in entries:
            rec = _entry_to_record(e)
            if rec:
                out.append(rec)
            if len(out) >= max_results:
                break
        total = int(res.get('opensearch:totalResults') or 0)
        start += len(entries)
        if start >= total or len(entries) < page:
            break
        time.sleep(0.35)
    return out[:max_results]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queries', required=True, help='JSON list of query strings')
    ap.add_argument('--window-months', type=int, default=24, help='Window-max in months')
    ap.add_argument('--window-min-months', type=int, default=0,
                    help='Window-min in months (exclude most recent N months)')
    ap.add_argument('--as-of', default='',
                    help='YYYY-MM-DD: backdate the window reference date')
    ap.add_argument('--max-per-query', type=int, default=25)
    ap.add_argument('--max-results', type=int, default=0,
                    help='Final cap on output (0 = no cap)')
    ap.add_argument('--journals', default='',
                    help='Pipe/comma-separated EXACTSRCTITLE list; empty = default CAS Q1 set')
    ap.add_argument('--view', default='',
                    help='STANDARD (default) or COMPLETE (needs ELSEVIER_INST_TOKEN)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    from scripts._time_guard import resolve_now
    queries = json.loads(args.queries)
    now = resolve_now(args.as_of)
    since = now - timedelta(days=30 * args.window_months)
    until = now - timedelta(days=30 * args.window_min_months) \
        if (args.window_min_months > 0 or args.as_of) else now
    start_year, end_year = since.year, until.year
    if end_year < start_year:
        start_year, end_year = end_year, start_year

    journals = _parse_journals(args.journals)
    view = (args.view or os.environ.get('ELSEVIER_VIEW') or 'STANDARD').upper()
    if view not in ('STANDARD', 'COMPLETE'):
        view = 'STANDARD'

    if not os.environ.get('ELSEVIER_API_KEY', '').strip():
        print('elsevier unavailable: ELSEVIER_API_KEY not set', file=sys.stderr)
        Path(args.out).write_text('[]')
        return

    print(f'elsevier/scopus journals={len(journals)} years={start_year}-{end_year} '
          f'view={view} max_per_query={args.max_per_query}', file=sys.stderr)

    seen: set[str] = set()
    merged: list[dict] = []
    for q in queries:
        try:
            hits = search(q, journals, start_year, end_year,
                          max_results=args.max_per_query, view=view)
        except Exception as e:
            print(f'  elsevier {q!r} failed: {e}', file=sys.stderr)
            # If COMPLETE rejected, one retry with STANDARD
            if view == 'COMPLETE' and '401' in str(e):
                try:
                    hits = search(q, journals, start_year, end_year,
                                  max_results=args.max_per_query, view='STANDARD')
                    print(f'  elsevier fallback STANDARD ok for {q!r}', file=sys.stderr)
                except Exception as e2:
                    print(f'  elsevier STANDARD also failed: {e2}', file=sys.stderr)
                    continue
            else:
                continue
        print(f'  elsevier query={q!r} hits={len(hits)}', file=sys.stderr)
        for h in hits:
            key = h.get('title_norm') or ''
            if not key or key in seen:
                continue
            # Client-side year gate (Scopus `date=` is year-granular).
            y = h.get('year')
            if isinstance(y, int) and (y < start_year or y > end_year):
                continue
            seen.add(key)
            merged.append(h)
        time.sleep(0.35)

    if args.max_results > 0:
        merged = merged[:args.max_results]
    Path(args.out).write_text(json.dumps(merged, ensure_ascii=False, indent=1))
    print(f'wrote {args.out} with {len(merged)} unique papers', file=sys.stderr)


if __name__ == '__main__':
    main()
