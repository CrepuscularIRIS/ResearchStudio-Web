"""CVF Open Access connector — CVPR / ICCV / ECCV full proceedings.

Why: OpenReview only exposes a **partial** public note set for CVPR/ICCV (often
hundreds, not the full ~4k accepted). Final papers live on
https://openaccess.thecvf.com/{CONF}{YEAR}?day=all — e.g. CVPR 2026 has ~4000+
entries including papers that appear on OpenReview only as ICLR-withdrawn.

No auth required. Index pages are gzip HTML (~1–12 MB). We cache them under
~/.cache/ideaspark/cvf/ (7-day TTL) and keyword-score titles (+ optional abstract
fetch for top candidates).

I/O:
  python3 -m scripts.search_cvf --queries '["..."]' --window-months 18 --out hits.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = 'https://openaccess.thecvf.com'
UA = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ResearchStudio-Idea/1.0'
)
CACHE_DIR = Path(os.environ.get(
    'IDEASPARK_CVF_CACHE',
    Path.home() / '.cache' / 'ideaspark' / 'cvf',
))
CACHE_TTL_S = int(os.environ.get('IDEASPARK_CVF_CACHE_TTL', str(7 * 24 * 3600)))

# (conf_code, months when that year's proceedings are typically online)
# We include conf years that overlap the retrieval window rather than a fixed list.
CONF_CODES = ('CVPR', 'ICCV', 'ECCV')

_STOP = frozenset({
    'a', 'an', 'the', 'of', 'for', 'and', 'or', 'in', 'on', 'to', 'with', 'via',
    'by', 'from', 'using', 'based', 'over', 'under', 'into', 'as', 'is', 'are',
    'be', 'this', 'that', 'vs', 'versus', 'new', 'novel', 'study', 'paper',
    'approach', 'method', 'model', 'models', 'learning', 'deep', 'via',
})

# <dt class="ptitle">...<a href="...html">TITLE</a></dt>  then <dd> ... authors ...
_PTITLE = re.compile(
    r'<dt class="ptitle">\s*(?:<br\s*/?>)?\s*'
    r'<a href="(/content/(CVPR|ICCV|ECCV)(20\d{2})/html/[^"]+_paper\.html)">'
    r'([^<]+)</a>\s*</dt>\s*<dd>(.*?)</dd>',
    re.S | re.I,
)
_AUTHOR = re.compile(r'name="query_author"\s+value="([^"]+)"')
_ABSTRACT = re.compile(
    r'id="abstract"[^>]*>\s*(.*?)\s*</div>',
    re.S | re.I,
)


def normalize_title(t: str) -> str:
    return re.sub(r'\W+', ' ', (t or '').lower()).strip()[:80]


def _query_tokens(query: str) -> list[str]:
    raw = re.findall(r'[a-z0-9]+', (query or '').lower())
    return [w for w in raw if w not in _STOP and len(w) >= 2]


def _http_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Encoding': 'gzip',
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        enc = (r.headers.get('Content-Encoding') or '').lower()
        if enc == 'gzip' or data[:2] == b'\x1f\x8b':
            data = gzip.decompress(data)
        return data


def _cache_path(conf: str, year: int) -> Path:
    return CACHE_DIR / f'{conf}{year}_dayall.html'


def fetch_index(conf: str, year: int, force: bool = False) -> str:
    """Download (or load cache) the day=all proceedings index HTML."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(conf, year)
    if not force and path.exists():
        age = time.time() - path.stat().st_mtime
        if age < CACHE_TTL_S and path.stat().st_size > 10_000:
            return path.read_text(encoding='utf-8', errors='replace')
    url = f'{BASE}/{conf}{year}?day=all'
    try:
        raw = _http_get(url)
    except Exception as e:
        if path.exists() and path.stat().st_size > 10_000:
            print(f'  cvf {conf}{year}: fetch failed ({e}); using stale cache',
                  file=sys.stderr)
            return path.read_text(encoding='utf-8', errors='replace')
        raise
    text = raw.decode('utf-8', errors='replace')
    if 'ptitle' not in text and len(text) < 50_000:
        raise RuntimeError(f'cvf {conf}{year}: index too small / missing ptitle '
                           f'({len(text)} chars) url={url}')
    path.write_text(text, encoding='utf-8')
    return text


def parse_index(html: str, conf: str, year: int) -> list[dict]:
    """Parse title / authors / html+pdf paths from a day=all page."""
    out: list[dict] = []
    for m in _PTITLE.finditer(html):
        rel_html, conf_m, year_m, title, dd = m.groups()
        title = re.sub(r'\s+', ' ', title).strip()
        if not title:
            continue
        authors = _AUTHOR.findall(dd)
        # de-dup authors preserving order
        seen: set[str] = set()
        auth_u: list[str] = []
        for a in authors:
            if a not in seen:
                seen.add(a)
                auth_u.append(a)
        conf_code = conf_m.upper()
        yr = int(year_m)
        rel_pdf = rel_html.replace('/html/', '/papers/').replace('.html', '.pdf')
        # slug id from filename
        slug = rel_html.rsplit('/', 1)[-1].replace('_paper.html', '')
        out.append({
            'title': title,
            'title_norm': normalize_title(title),
            'abstract': '',  # filled on demand
            'year': yr,
            'venue': f'{conf_code} {yr}',
            'authors': auth_u[:8],
            'citations': None,
            'source': 'cvf',
            'source_id': f'{conf_code}{yr}:{slug}',
            'doi': '',
            'paper_url': BASE + rel_html,
            'pdf_url': BASE + rel_pdf,
            'published_iso': f'{yr}-06-01',  # conf mid-year proxy; real day unknown
            '_html_path': rel_html,
        })
    return out


def conf_years_for_window(now: datetime, window_months: int) -> list[tuple[str, int]]:
    """Pick (CONF, year) pairs whose proceedings likely fall in the window.

    Heuristic:
      CVPR every year ~June; ICCV odd years ~Oct; ECCV even years ~Sep/Oct.
    We include conf years whose approximate date is inside
    [now - window_months - 3mo, now + 1mo].
    """
    since = now - timedelta(days=30 * (window_months + 3))
    until = now + timedelta(days=30)
    pairs: list[tuple[str, int]] = []
    for year in range(since.year, now.year + 1):
        candidates = [('CVPR', 6)]
        if year % 2 == 1:
            candidates.append(('ICCV', 10))
        else:
            candidates.append(('ECCV', 9))
        for conf, month in candidates:
            conf_day = datetime(year, month, 15, tzinfo=timezone.utc)
            if since <= conf_day <= until:
                pairs.append((conf, year))
    # Ensure last two CVPR cycles always present when window ≥ 12mo
    if window_months >= 12:
        for y in (now.year, now.year - 1):
            if y >= 2015 and ('CVPR', y) not in pairs:
                pairs.append(('CVPR', y))
    seen: set[tuple[str, int]] = set()
    out: list[tuple[str, int]] = []
    for p in sorted(pairs, key=lambda x: (x[1], x[0])):
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def fetch_abstract(rel_html: str, timeout: int = 20) -> str:
    url = BASE + rel_html
    try:
        raw = _http_get(url, timeout=timeout)
        text = raw.decode('utf-8', errors='replace')
    except Exception:
        return ''
    m = _ABSTRACT.search(text)
    if not m:
        return ''
    abs_html = m.group(1)
    abs_txt = re.sub(r'<[^>]+>', ' ', abs_html)
    abs_txt = re.sub(r'\s+', ' ', abs_txt).strip()
    return abs_txt[:4000]


def search(queries: list[str], window_months: int, now: datetime,
           max_per_query: int = 40, max_results: int = 0,
           fetch_abstracts: bool = True, abstract_cap: int = 30) -> list[dict]:
    pairs = conf_years_for_window(now, window_months)
    print(f'cvf targets={pairs}', file=sys.stderr)

    catalog: list[dict] = []
    for conf, year in pairs:
        try:
            html = fetch_index(conf, year)
            papers = parse_index(html, conf, year)
            print(f'  cvf {conf}{year}: {len(papers)} papers', file=sys.stderr)
            catalog.extend(papers)
        except Exception as e:
            print(f'  cvf {conf}{year}: FAILED {e}', file=sys.stderr)

    if not catalog:
        return []

    # Dedup catalog by title_norm
    by_title: dict[str, dict] = {}
    for p in catalog:
        k = p['title_norm']
        if k and k not in by_title:
            by_title[k] = p
    catalog = list(by_title.values())

    scored: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        tokens = _query_tokens(q)
        if not tokens:
            tokens = [w for w in (q or '').lower().split() if len(w) >= 2][:6]
        min_score = 1 if len(tokens) <= 1 else 2
        q_hits: list[tuple[int, dict]] = []
        for p in catalog:
            text = (p['title'] + ' ' + (p.get('abstract') or '')).lower()
            score = sum(1 for t in tokens if t in text) if tokens else 0
            if score < min_score:
                continue
            q_hits.append((score, p))
        q_hits.sort(key=lambda x: -x[0])
        kept = 0
        for score, p in q_hits:
            k = p['title_norm']
            if not k or k in seen:
                continue
            rec = dict(p)
            rec['_score'] = score
            scored.append(rec)
            seen.add(k)
            kept += 1
            if kept >= max_per_query:
                break
        print(f'  cvf query={q!r} kept={kept}', file=sys.stderr)

    scored.sort(key=lambda x: -x.get('_score', 0))
    if max_results > 0:
        scored = scored[:max_results]

    # Optional abstract fill for top hits (bounded HTTP)
    if fetch_abstracts and scored:
        n_abs = 0
        for rec in scored:
            if n_abs >= abstract_cap:
                break
            if rec.get('abstract'):
                continue
            rel = rec.pop('_html_path', None) or ''
            if not rel:
                # recover from paper_url
                if rec.get('paper_url', '').startswith(BASE):
                    rel = rec['paper_url'][len(BASE):]
            if not rel:
                continue
            abs_txt = fetch_abstract(rel)
            if abs_txt:
                rec['abstract'] = abs_txt
                n_abs += 1
            time.sleep(0.15)
        print(f'  cvf abstracts filled={n_abs}', file=sys.stderr)

    # strip internal keys
    for rec in scored:
        rec.pop('_html_path', None)

    return scored


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queries', required=True)
    ap.add_argument('--window-months', type=int, default=18)
    ap.add_argument('--window-min-months', type=int, default=0)
    ap.add_argument('--as-of', default='')
    ap.add_argument('--max-per-query', type=int, default=40)
    ap.add_argument('--max-results', type=int, default=0)
    ap.add_argument('--no-abstracts', action='store_true',
                    help='Skip per-paper abstract HTTP (title-only, much faster)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    from scripts._time_guard import resolve_now
    queries = json.loads(args.queries)
    now = resolve_now(args.as_of)
    # window-min unused for CVF (year-level indexes); kept for CLI parity with other connectors
    _ = args.window_min_months

    try:
        hits = search(
            queries,
            window_months=args.window_months,
            now=now,
            max_per_query=args.max_per_query,
            max_results=args.max_results,
            fetch_abstracts=not args.no_abstracts,
        )
    except Exception as e:
        print(f'cvf unavailable: {e}', file=sys.stderr)
        Path(args.out).write_text('[]')
        return

    Path(args.out).write_text(json.dumps(hits, ensure_ascii=False, indent=1))
    print(f'wrote {args.out} with {len(hits)} unique papers', file=sys.stderr)


if __name__ == '__main__':
    main()
