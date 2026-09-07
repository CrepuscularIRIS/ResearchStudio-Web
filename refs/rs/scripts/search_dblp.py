"""DBLP connector — broad CCF-A conference coverage via stream-filtered search.

API:
  GET https://dblp.org/search/publ/api?q=...&format=json&h=N

Strategies (in order):
  1) Per-stream:  stream:streams/conf/{key}:{query}
  2) Fallback:    global query, keep hits whose venue matches CCF-A labels
     (used when DBLP rate-limits / closes stream queries)

No auth. Polite pacing + exponential backoff on 429/5xx/connection drops.

I/O:
  python3 -m scripts.search_dblp --queries '["..."]' --window-months 24 --out hits.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

API = 'https://dblp.org/search/publ/api'
UA = 'ResearchStudio-Idea/1.0 (literature connector; +https://dblp.org)'

# CCF-A (and key near-A) CS venues. key = DBLP streams/conf/{key}
CCF_A_STREAMS: tuple[tuple[str, str], ...] = (
    # ML
    ('nips', 'NeurIPS'),
    ('icml', 'ICML'),
    ('iclr', 'ICLR'),
    ('aaai', 'AAAI'),
    ('ijcai', 'IJCAI'),
    ('uai', 'UAI'),
    ('aistats', 'AISTATS'),
    ('colt', 'COLT'),
    # CV
    ('cvpr', 'CVPR'),
    ('iccv', 'ICCV'),
    ('eccv', 'ECCV'),
    # NLP
    ('acl', 'ACL'),
    ('emnlp', 'EMNLP'),
    ('naacl', 'NAACL'),
    # Data / IR / web
    ('kdd', 'KDD'),
    ('www', 'WWW'),
    ('sigir', 'SIGIR'),
    ('wsdm', 'WSDM'),
    ('cikm', 'CIKM'),
    # Multimedia / recsys
    ('mm', 'ACM MM'),
    ('recsys', 'RecSys'),
    # Robotics
    ('corl', 'CoRL'),
    ('rss', 'RSS'),
    ('icra', 'ICRA'),
    ('iros', 'IROS'),
    # Systems
    ('osdi', 'OSDI'),
    ('sosp', 'SOSP'),
    ('nsdi', 'NSDI'),
    ('asplos', 'ASPLOS'),
    ('eurosys', 'EuroSys'),
    # Security
    ('ccs', 'CCS'),
    ('uss', 'USENIX Security'),
    ('sp', 'IEEE S&P'),
    ('ndss', 'NDSS'),
)

_STOP = frozenset({
    'a', 'an', 'the', 'of', 'for', 'and', 'or', 'in', 'on', 'to', 'with', 'via',
    'by', 'from', 'using', 'based', 'new', 'novel', 'paper', 'study', 'method',
    'model', 'models', 'learning', 'deep',
})

# Venue substrings for global-search post-filter (case-insensitive).
_VENUE_ALIASES: dict[str, tuple[str, ...]] = {
    'NeurIPS': ('neurips', 'nips', 'advances in neural information processing'),
    'ICML': ('icml', 'international conference on machine learning'),
    'ICLR': ('iclr', 'international conference on learning representations'),
    'AAAI': ('aaai',),
    'IJCAI': ('ijcai',),
    'UAI': ('uai', 'uncertainty in artificial intelligence'),
    'AISTATS': ('aistats',),
    'COLT': ('colt', 'conference on learning theory'),
    'CVPR': ('cvpr', 'computer vision and pattern recognition'),
    'ICCV': ('iccv', 'international conference on computer vision'),
    'ECCV': ('eccv', 'european conference on computer vision'),
    'ACL': ('acl', 'association for computational linguistics'),
    'EMNLP': ('emnlp', 'empirical methods in natural language'),
    'NAACL': ('naacl', 'north american chapter'),
    'KDD': ('kdd', 'knowledge discovery and data mining'),
    'WWW': ('www', 'world wide web', 'the web conference'),
    'SIGIR': ('sigir',),
    'WSDM': ('wsdm',),
    'CIKM': ('cikm',),
    'ACM MM': ('acm multimedia', 'acmmm', 'mm '),
    'RecSys': ('recsys',),
    'CoRL': ('corl', 'conference on robot learning'),
    'RSS': ('robotics: science and systems', 'rss'),
    'ICRA': ('icra',),
    'IROS': ('iros',),
    'OSDI': ('osdi',),
    'SOSP': ('sosp',),
    'NSDI': ('nsdi',),
    'ASPLOS': ('asplos',),
    'EuroSys': ('eurosys',),
    'CCS': ('ccs', 'computer and communications security'),
    'USENIX Security': ('usenix security',),
    'IEEE S&P': ('s&p', 'oakland', 'ieee symposium on security'),
    'NDSS': ('ndss',),
}


def normalize_title(t: str) -> str:
    t = re.sub(r'<[^>]+>', '', t or '')
    return re.sub(r'\W+', ' ', t.lower()).strip()[:80]


def _clean_query(q: str) -> str:
    q = re.sub(r'[:"(){}\\]', ' ', q or '')
    return re.sub(r'\s+', ' ', q).strip()


def _http_get_json(params: dict, retries: int = 4) -> dict:
    url = API + '?' + urllib.parse.urlencode(params)
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': UA,
                'Accept': 'application/json',
                'Connection': 'close',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode('utf-8', errors='replace'))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2.0 * (2 ** attempt))  # 2, 4, 8, 16
                continue
            raise
        except Exception as e:
            # Connection reset / remote closed — backoff and retry
            last_err = e
            if attempt < retries - 1:
                time.sleep(2.0 * (2 ** attempt))
                continue
            raise
    raise RuntimeError(f'dblp request failed after retries: {last_err}')


def _authors(info: dict) -> list[str]:
    a = info.get('authors') or {}
    raw = a.get('author') if isinstance(a, dict) else a
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, dict):
        name = raw.get('text') or raw.get('#text') or ''
        return [name] if name else []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            name = item.get('text') or item.get('#text') or ''
            if name:
                out.append(name)
    return out[:8]


def _hit_to_record(info: dict, stream_label: str = '') -> dict | None:
    title = re.sub(r'<[^>]+>', '', info.get('title') or '').strip().rstrip('.')
    if not title:
        return None
    year_s = str(info.get('year') or '')
    year = int(year_s) if year_s.isdigit() else None
    ee = info.get('ee')
    if isinstance(ee, list):
        ee = ee[0] if ee else ''
    url = str(ee or info.get('url') or '')
    doi = ''
    if 'doi.org/' in url:
        doi = url.split('doi.org/', 1)[-1]
    elif info.get('doi'):
        doi = str(info['doi'])
    venue = info.get('venue') or stream_label
    if isinstance(venue, list):
        venue = venue[0] if venue else stream_label
    key = info.get('key') or info.get('url') or title
    return {
        'title': title,
        'title_norm': normalize_title(title),
        'abstract': '',
        'year': year,
        'venue': str(venue),
        'authors': _authors(info),
        'citations': None,
        'source': 'dblp',
        'source_id': str(key).replace('https://dblp.org/rec/', ''),
        'doi': doi,
        'paper_url': url or f'https://dblp.org/search?q={urllib.parse.quote(title)}',
        'published_iso': f'{year}-01-01' if year else '',
        'dblp_stream': stream_label,
    }


def _parse_hits(data: dict) -> list[dict]:
    hits = (data.get('result') or {}).get('hits') or {}
    raw = hits.get('hit') or []
    if isinstance(raw, dict):
        raw = [raw]
    out = []
    for h in raw:
        info = h.get('info') or {}
        if info:
            out.append(info)
    return out


def search_stream(stream_key: str, stream_label: str, query: str,
                  start_year: int, end_year: int, max_results: int = 20) -> list[dict]:
    q_clean = _clean_query(query)
    if not q_clean:
        return []
    dblp_q = f'stream:streams/conf/{stream_key}: {q_clean}'
    data = _http_get_json({'q': dblp_q, 'format': 'json', 'h': str(min(max_results, 80))})
    out: list[dict] = []
    for info in _parse_hits(data):
        rec = _hit_to_record(info, stream_label)
        if not rec:
            continue
        y = rec.get('year')
        if isinstance(y, int) and (y < start_year or y > end_year):
            continue
        out.append(rec)
        if len(out) >= max_results:
            break
    return out


def _venue_is_ccf_a(venue: str) -> str | None:
    """Return canonical label if venue string matches a known CCF-A alias."""
    v = (venue or '').lower()
    for label, aliases in _VENUE_ALIASES.items():
        for a in aliases:
            if a in v:
                return label
    return None


def search_global_fallback(query: str, start_year: int, end_year: int,
                           max_results: int = 50) -> list[dict]:
    """One global DBLP query; keep only hits at CCF-A venues in year range."""
    q_clean = _clean_query(query)
    if not q_clean:
        return []
    # Prefer recent years in the query string to bias ranking
    year_bits = ' '.join(f'year:{y}:' for y in range(end_year, start_year - 1, -1)[:4])
    dblp_q = f'{q_clean} {year_bits}'.strip()
    data = _http_get_json({'q': dblp_q, 'format': 'json', 'h': str(min(max(max_results * 3, 50), 100))})
    out: list[dict] = []
    for info in _parse_hits(data):
        rec = _hit_to_record(info, '')
        if not rec:
            continue
        y = rec.get('year')
        if isinstance(y, int) and (y < start_year or y > end_year):
            continue
        label = _venue_is_ccf_a(str(rec.get('venue') or ''))
        if not label:
            continue
        rec['dblp_stream'] = label
        # normalize venue display a bit
        if label and label not in str(rec.get('venue') or ''):
            rec['venue'] = f"{label} ({rec.get('venue')})"
        out.append(rec)
        if len(out) >= max_results:
            break
    return out


def search(queries: list[str], start_year: int, end_year: int,
           max_per_query: int = 50, max_results: int = 0,
           streams: list[tuple[str, str]] | None = None,
           per_stream: int = 12,
           stream_pause: float = 0.8) -> list[dict]:
    streams = streams or list(CCF_A_STREAMS)
    seen: set[str] = set()
    merged: list[dict] = []

    for q in queries:
        stream_hits: list[dict] = []
        stream_ok = 0
        stream_fail = 0
        for key, label in streams:
            try:
                hits = search_stream(key, label, q, start_year, end_year,
                                     max_results=per_stream)
                stream_hits.extend(hits)
                stream_ok += 1
            except Exception as e:
                stream_fail += 1
                print(f'  dblp {label}({key}): {type(e).__name__}: {e}', file=sys.stderr)
            time.sleep(stream_pause)

        # If most streams failed or almost nothing came back, use global fallback once.
        if stream_ok == 0 or (len(stream_hits) < 5 and stream_fail >= max(1, len(streams) // 3)):
            print(f'  dblp fallback global search for {q!r} '
                  f'(ok_streams={stream_ok} fail={stream_fail} hits={len(stream_hits)})',
                  file=sys.stderr)
            try:
                fb = search_global_fallback(q, start_year, end_year,
                                            max_results=max_per_query * 2)
                stream_hits.extend(fb)
                print(f'  dblp fallback got {len(fb)}', file=sys.stderr)
            except Exception as e:
                print(f'  dblp fallback failed: {e}', file=sys.stderr)
            time.sleep(stream_pause)

        # Light title token boost (DBLP already ranked)
        tokens = re.findall(r'[a-z0-9]+', (q or '').lower())
        tokens = [t for t in tokens if t not in _STOP and len(t) >= 2]
        ranked: list[dict] = []
        for h in stream_hits:
            text = h['title'].lower()
            score = sum(1 for t in tokens if t in text) if tokens else 1
            hh = dict(h)
            hh['_score'] = score
            ranked.append(hh)
        ranked.sort(key=lambda x: (-x.get('_score', 0), -(x.get('year') or 0)))

        q_kept = 0
        for h in ranked:
            k = h.get('title_norm') or ''
            if not k or k in seen:
                continue
            seen.add(k)
            merged.append(h)
            q_kept += 1
            if q_kept >= max_per_query:
                break
        print(f'  dblp query={q!r} kept={q_kept} raw_stream_hits={len(stream_hits)}',
              file=sys.stderr)

    merged.sort(key=lambda x: (-x.get('_score', 0), -(x.get('year') or 0)))
    if max_results > 0:
        merged = merged[:max_results]
    return merged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queries', required=True)
    ap.add_argument('--window-months', type=int, default=36)
    ap.add_argument('--window-min-months', type=int, default=0)
    ap.add_argument('--as-of', default='')
    ap.add_argument('--max-per-query', type=int, default=50)
    ap.add_argument('--max-results', type=int, default=0)
    ap.add_argument('--per-stream', type=int, default=12)
    ap.add_argument('--stream-pause', type=float, default=0.8,
                    help='Seconds between DBLP stream requests (default 0.8)')
    ap.add_argument('--streams', default='',
                    help='Subset of stream keys, comma-separated (e.g. nips,icml,acl,cvpr)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    from scripts._time_guard import resolve_now
    queries = json.loads(args.queries)
    now = resolve_now(args.as_of)
    since = now - timedelta(days=30 * args.window_months)
    until = now - timedelta(days=30 * args.window_min_months) if args.window_min_months > 0 else now
    start_year, end_year = since.year, until.year
    if end_year < start_year:
        start_year, end_year = end_year, start_year

    streams = list(CCF_A_STREAMS)
    if args.streams.strip():
        want = {s.strip() for s in args.streams.split(',') if s.strip()}
        streams = [(k, lab) for k, lab in CCF_A_STREAMS if k in want] or list(CCF_A_STREAMS)

    print(f'dblp streams={len(streams)} years={start_year}-{end_year} '
          f'max_per_query={args.max_per_query} per_stream={args.per_stream}',
          file=sys.stderr)

    try:
        hits = search(
            queries, start_year, end_year,
            max_per_query=args.max_per_query,
            max_results=args.max_results,
            streams=streams,
            per_stream=args.per_stream,
            stream_pause=args.stream_pause,
        )
    except Exception as e:
        print(f'dblp unavailable: {e}', file=sys.stderr)
        Path(args.out).write_text('[]')
        return

    Path(args.out).write_text(json.dumps(hits, ensure_ascii=False, indent=1))
    print(f'wrote {args.out} with {len(hits)} unique papers', file=sys.stderr)


if __name__ == '__main__':
    main()
