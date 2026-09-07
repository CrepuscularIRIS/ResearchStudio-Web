"""OpenReview search connector.

Why: OpenReview surfaces conference submissions for ICLR/NeurIPS/ICML — in-review
and recently decided work that may not yet have full peer-reviewed metadata elsewhere.

IMPORTANT — this is NOT a real free-text search API.
OpenReview's notes endpoint rejects title/keyword-only queries (needs invitation /
venueid / id). We therefore:
  1. pull notes per venue (venueid content filter, paginated),
  2. filter by cdate window client-side,
  3. score title+abstract with a stopword-stripped keyword overlap (BM25-lite).

Auth: OPENREVIEW_USER + OPENREVIEW_PASS in env.

I/O:
  python3 -m scripts.search_openreview --queries '["..."]' --window-months 18 --out hits.json
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dateutil.relativedelta import relativedelta
except ImportError:  # pragma: no cover — dateutil is a std dep of openreview-py
    relativedelta = None  # type: ignore

try:
    import openreview  # type: ignore
except ImportError:
    openreview = None

# Stopwords that inflate overlap scores on long natural-language queries.
# Content tokens only are used for the score threshold.
_STOP = frozenset({
    'a', 'an', 'the', 'of', 'for', 'and', 'or', 'in', 'on', 'to', 'with', 'via',
    'by', 'from', 'using', 'based', 'over', 'under', 'into', 'as', 'is', 'are',
    'be', 'this', 'that', 'vs', 'versus', 'toward', 'towards', 'between', 'among',
    'its', 'their', 'our', 'your', 'how', 'what', 'when', 'where', 'which', 'who',
    'why', 'can', 'could', 'should', 'would', 'may', 'might', 'not', 'no', 'yes',
    'new', 'novel', 'study', 'paper', 'approach', 'method', 'model', 'models',
    'learning', 'deep',  # too generic alone; kept only if other content tokens match
})


def normalize_title(t: str) -> str:
    return re.sub(r'\W+', ' ', (t or '').lower()).strip()[:80]


def _query_tokens(query: str) -> list[str]:
    """Content tokens from a query (stopword-stripped, alnum only)."""
    raw = re.findall(r'[a-z0-9]+', (query or '').lower())
    # Drop pure stopwords; keep short technical tokens (e.g. rl, ml) of len>=2
    return [w for w in raw if w not in _STOP and len(w) >= 2]


def get_client():
    if openreview is None:
        raise RuntimeError('openreview-py not installed; pip install openreview-py')
    return openreview.api.OpenReviewClient(
        baseurl='https://api2.openreview.net',
        username=os.environ.get('OPENREVIEW_USER', ''),
        password=os.environ.get('OPENREVIEW_PASS', ''),
    )


# CCF-A AI / CV / NLP / robotics venues hosted on OpenReview (verified prefixes).
# Each entry: (venueid template with {y}, short venue-string templates).
# CVPR/ICCV often expose public notes via content.venue ("CVPR 2026") while
# content.venueid / invitation Submission return empty after the review cycle ends.
CCF_A_OR_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('ICLR.cc/{y}/Conference', ('ICLR {y}', 'ICLR {y} Conference')),
    ('NeurIPS.cc/{y}/Conference', ('NeurIPS {y}', 'NeurIPS {y} Conference')),
    ('ICML.cc/{y}/Conference', ('ICML {y}', 'ICML {y} Conference')),
    ('thecvf.com/CVPR/{y}/Conference', ('CVPR {y}', 'CVPR {y} Conference')),
    ('thecvf.com/ICCV/{y}/Conference', ('ICCV {y}', 'ICCV {y} Conference')),
    ('thecvf.com/ECCV/{y}/Conference', ('ECCV {y}', 'ECCV {y} Conference')),
    ('AAAI.org/{y}/Conference', ('AAAI {y}', 'AAAI {y} Conference')),
    ('aclweb.org/ACL/{y}/Conference', ('ACL {y}', 'ACL {y} Conference')),
    ('aclweb.org/EMNLP/{y}/Conference', ('EMNLP {y}', 'EMNLP {y} Conference')),
    ('aclweb.org/NAACL/{y}/Conference', ('NAACL {y}', 'NAACL {y} Conference')),
    ('robot-learning.org/CoRL/{y}/Conference', ('CoRL {y}', 'CoRL {y} Conference')),
    ('roboticsfoundation.org/RSS/{y}/Conference', ('RSS {y}', 'RSS {y} Conference')),
)


def derive_active_venues(now: datetime, custom_venues: list[str] | None = None) -> list[dict]:
    """Return venue dicts for the CCF-A OpenReview pool (current + previous year).

    Each dict: {venue_id, venue_labels, year}.
    Years: {now.year-1, now.year} plus now.year+1 when early in a cycle so
    in-flight submissions (e.g. ICLR Y+1 after September) are covered.
    """
    if custom_venues:
        # custom strings may be venueids or free labels
        out = []
        for v in custom_venues:
            v = v.strip()
            if not v:
                continue
            if '/' in v and v.endswith('Conference'):
                out.append({'venue_id': v, 'venue_labels': [], 'year': None})
            else:
                out.append({'venue_id': '', 'venue_labels': [v], 'year': None})
        return out

    years = {now.year - 1, now.year}
    if now.month >= 9:  # ICLR / fall cycles already open for next calendar year
        years.add(now.year + 1)
    years = sorted(years)

    out: list[dict] = []
    seen: set[str] = set()
    for y in years:
        for tmpl, labels in CCF_A_OR_SPECS:
            vid = tmpl.format(y=y)
            labs = [lb.format(y=y) for lb in labels]
            key = vid or '|'.join(labs)
            if key in seen:
                continue
            seen.add(key)
            out.append({'venue_id': vid, 'venue_labels': labs, 'year': y})
    return out


def _field(content: dict, key: str, default=''):
    v = (content or {}).get(key, default)
    if isinstance(v, dict) and 'value' in v:
        return v['value']
    return v if v is not None else default


def _note_cdate(note) -> datetime | None:
    published = getattr(note, 'cdate', None) or getattr(note, 'pdate', None)
    if not published:
        return None
    try:
        return datetime.fromtimestamp(int(published) / 1000, tz=timezone.utc)
    except Exception:
        return None


def _note_id(note) -> str:
    return str(getattr(note, 'id', None) or '')


def _page_notes(client, since: datetime, per_venue_cap: int, page_size: int,
                collected: list, seen_ids: set[str], **query_kwargs) -> None:
    """Paginate get_notes(**query_kwargs), append until cap / older than since."""
    offset = 0
    while len(collected) < per_venue_cap:
        kwargs = dict(query_kwargs)
        kwargs.update({
            'limit': min(page_size, per_venue_cap - len(collected), 1000),
            'offset': offset,
            'sort': 'cdate:desc',
        })
        try:
            batch = client.get_notes(**kwargs) or []
        except Exception as e:
            print(f'  openreview page {query_kwargs}: {e}', file=sys.stderr)
            return
        if not batch:
            return
        stop_older = False
        for n in batch:
            nid = _note_id(n)
            if nid and nid in seen_ids:
                continue
            d = _note_cdate(n)
            if d is not None and d < since:
                stop_older = True
                break
            if nid:
                seen_ids.add(nid)
            collected.append(n)
            if len(collected) >= per_venue_cap:
                break
        if stop_older or len(batch) < kwargs['limit']:
            return
        offset += len(batch)
        time.sleep(0.35)


def _fetch_venue_notes(client, venue: dict, since: datetime, per_venue_cap: int,
                       page_size: int = 1000) -> list:
    """Pull notes for one CCF-A venue via venueid → venue label → invitation.

    CVPR/ICCV often have public notes only under content.venue ("CVPR 2026"),
    while venueid / invitation Submission return empty after the PC cycle.
    """
    since_ms = int(since.timestamp() * 1000)
    collected: list = []
    seen_ids: set[str] = set()
    venue_id = (venue.get('venue_id') or '').strip()
    labels = list(venue.get('venue_labels') or [])

    # 1) content.venueid (works well for ICLR / NeurIPS / ICML)
    if venue_id:
        _page_notes(client, since, per_venue_cap, page_size, collected, seen_ids,
                    content={'venueid': venue_id})

    # 2) content.venue display strings (critical for CVPR / ICCV / ACL)
    if len(collected) < per_venue_cap:
        for lab in labels:
            _page_notes(client, since, per_venue_cap, page_size, collected, seen_ids,
                        content={'venue': lab})
            if len(collected) >= per_venue_cap:
                break

    # 3) invitation Submission (+ optional mintcdate)
    if venue_id and len(collected) < per_venue_cap:
        inv = f'{venue_id}/-/Submission'
        _page_notes(client, since, per_venue_cap, page_size, collected, seen_ids,
                    invitation=inv, mintcdate=since_ms)
        if len(collected) < max(10, per_venue_cap // 10):
            _page_notes(client, since, per_venue_cap, page_size, collected, seen_ids,
                        invitation=inv)

    return collected


def search(client, query: str, since: datetime, venues: list[dict], max_results: int = 50,
           per_venue_cap: int = 2000, until: datetime | None = None) -> list[dict]:
    """Pull CCF-A venue notes, date-filter, keyword-score, return top max_results.

    Scoring: count of distinct content-query tokens found as substrings in
    title+abstract. Threshold: 1 if the query has ≤1 content token, else 2.
    (Prevents empty-result on short technical queries like "RLHF".)
    """
    out: list[dict] = []
    q_tokens = _query_tokens(query)
    # If the whole query was stopwords, fall back to raw split so we don't match everything.
    if not q_tokens:
        q_tokens = [w for w in (query or '').lower().split() if len(w) >= 2][:6]
    min_score = 1 if len(q_tokens) <= 1 else 2

    for venue in venues:
        venue_id = venue.get('venue_id') or ''
        notes = _fetch_venue_notes(client, venue, since=since, per_venue_cap=per_venue_cap)
        print(f'  openreview venue={venue_id or venue.get("venue_labels")} raw={len(notes)}',
              file=sys.stderr)
        for n in notes:
            content = n.content or {}
            title = str(_field(content, 'title', '') or '')
            abstract = str(_field(content, 'abstract', '') or '')
            text = (title + ' ' + abstract).lower()
            if q_tokens:
                score = sum(1 for w in q_tokens if w in text)
                if score < min_score:
                    continue
            else:
                score = 0
            d = _note_cdate(n)
            if d is not None:
                if d < since:
                    continue
                if until is not None and d > until:
                    continue
            authors_raw = _field(content, 'authors', []) or []
            if isinstance(authors_raw, str):
                authors_raw = [authors_raw]
            year = venue.get('year')
            if year is None:
                try:
                    year = int((venue_id or '').split('/')[-2])
                except Exception:
                    year = d.year if d else None
            # Prefer human venue string from the note when present (e.g. "CVPR 2026")
            venue_label = str(_field(content, 'venue', '') or '') or venue_id
            out.append({
                'title': title,
                'title_norm': normalize_title(title),
                'abstract': abstract,
                'year': year,
                'venue': venue_label,
                'venueid': str(_field(content, 'venueid', '') or venue_id),
                'authors': list(authors_raw)[:6],
                'citations': None,
                'source': 'openreview',
                'source_id': n.id,
                'doi': '',
                'paper_url': f'https://openreview.net/forum?id={n.id}',
                'published_iso': d.date().isoformat() if d else '',
                '_score': score,
            })
        time.sleep(0.5)
    out.sort(key=lambda x: (-x['_score'], x.get('published_iso') or ''))
    return out[:max_results]


def _months_ago(now: datetime, months: int) -> datetime:
    if relativedelta is not None:
        return now - relativedelta(months=months)
    # Fallback if dateutil missing: average month length (still better than 30*n for long windows)
    from datetime import timedelta
    return now - timedelta(days=int(round(months * 30.44)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queries', required=True)
    ap.add_argument('--window-months', type=int, default=18,
                    help='Window-max in calendar months (default 18: covers prior NeurIPS May cycle)')
    ap.add_argument('--window-min-months', type=int, default=0,
                    help='Window-min in months (default 0 = include up to now)')
    ap.add_argument('--as-of', default='',
                    help='YYYY-MM-DD: backdate the window reference date; default = real now')
    ap.add_argument('--max-per-query', type=int, default=80)
    ap.add_argument('--max-results', type=int, default=0,
                    help='Final cap on output (0 = no cap; if set, take top by query-overlap score)')
    ap.add_argument('--per-venue-cap', type=int, default=2000,
                    help='Max notes pulled per venue after date filter (paginated)')
    ap.add_argument('--venues', default='',
                    help='Comma-separated OpenReview venue ids. Empty = ICLR+NeurIPS+ICML current+previous.')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    from scripts._time_guard import resolve_now
    queries = json.loads(args.queries)
    now = resolve_now(args.as_of)
    since = _months_ago(now, args.window_months)
    until = _months_ago(now, args.window_min_months) \
        if (args.window_min_months > 0 or args.as_of) else None
    custom_venues = [v.strip() for v in args.venues.split(',') if v.strip()] if args.venues else None
    venues = derive_active_venues(now, custom_venues)

    try:
        client = get_client()
    except Exception as e:
        print(f'openreview unavailable: {e}', file=sys.stderr)
        Path(args.out).write_text('[]')
        return

    print(f'openreview CCF-A venues={len(venues)} since={since.date()} '
          f'per_venue_cap={args.per_venue_cap} max_per_query={args.max_per_query}',
          file=sys.stderr)
    for v in venues:
        print(f'  - {v.get("venue_id")} labels={v.get("venue_labels")}', file=sys.stderr)

    seen: set[str] = set()
    merged: list[dict] = []
    for q in queries:
        try:
            hits = search(
                client, q, since, venues=venues,
                max_results=args.max_per_query,
                per_venue_cap=args.per_venue_cap,
                until=until,
            )
        except Exception as e:
            print(f'  openreview {q!r} failed: {e}', file=sys.stderr)
            continue
        print(f'  openreview query={q!r} hits={len(hits)}', file=sys.stderr)
        for h in hits:
            key = h['title_norm']
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(h)
        time.sleep(1.0)

    if args.max_results > 0:
        merged.sort(key=lambda x: -x.get('_score', 0))
        merged = merged[:args.max_results]
    Path(args.out).write_text(json.dumps(merged, ensure_ascii=False, indent=1))
    print(f'wrote {args.out} with {len(merged)} unique papers', file=sys.stderr)


if __name__ == '__main__':
    main()
