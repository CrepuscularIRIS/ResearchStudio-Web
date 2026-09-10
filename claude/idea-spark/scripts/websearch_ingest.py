"""Turn host web-search results into the upstream `lit_results.json` corpus.

Why this exists: this port retrieves with the host's own web search — no
connectors — so nothing else writes the Phase 0 corpus. The rows still have to
land in the exact record shape every downstream phase reads, with upstream's
dedup keys, upstream's survey demotion, and honest provenance. Doing that by
hand is how a corpus quietly acquires a paper nobody retrieved.

Re-runnable: call it again with more rows and they merge into the existing
corpus rather than replacing it.

Host adapter file: NOT upstream. See references/websearch-retrieval.md.

I/O:
  python3 -m scripts.websearch_ingest --raw <raw.json> --run-dir <phase0 dir>

`raw.json` is a JSON list of objects; `title` and `url` are required, everything
else is optional. Records without a retrievable URL are refused: an unsourced
row is exactly the failure mode host search has to be kept away from.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

_SURVEY_RE = re.compile(
    r'^(a |an )?(comprehensive |systematic |brief )*(survey|review|meta-analysis)\b'
    r'|:\s*(a )?(comprehensive |systematic )*(survey|review)\b', re.I)

# Mirrors scripts/search_arxiv.py: dedup keys must be computed identically or a
# paper found by both transports lands in lit_results twice.
def normalize_title(t: str) -> str:
    return re.sub(r'\W+', ' ', (t or '').lower()).strip()[:80]


def _source_id(record: dict) -> str:
    """A stable id for `paper_id`, preferring a real identifier over a slug."""
    url = (record.get('url') or '').strip()
    arxiv = re.search(r'arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})', url)
    if arxiv:
        return arxiv.group(1)
    forum = re.search(r'openreview\.net/forum\?id=([A-Za-z0-9_-]+)', url)
    if forum:
        return forum.group(1)
    acl = re.search(r'aclanthology\.org/([0-9]{4}\.[a-z-]+\.[0-9]+)', url)
    if acl:
        return acl.group(1)
    doi = (record.get('doi') or '').strip()
    if doi:
        return doi
    return normalize_title(record.get('title', ''))[:60].replace(' ', '_') or 'unknown'


def to_connector_record(record: dict) -> dict:
    """One raw host-search hit -> one upstream-schema hit record."""
    title = (record.get('title') or '').strip()
    year = record.get('year')
    try:
        year = int(str(year)[:4]) if year else None
    except (TypeError, ValueError):
        year = None
    authors = record.get('authors')
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(',') if a.strip()]
    return {
        'title': title,
        'title_norm': normalize_title(title),
        'abstract': (record.get('abstract') or '').strip(),
        'year': year,
        'venue': (record.get('venue') or '').strip(),
        'authors': authors if isinstance(authors, list) else [],
        'citations': None,
        'source': 'websearch',
        'source_id': _source_id(record),
        'doi': (record.get('doi') or '').strip(),
        'paper_url': (record.get('url') or '').strip(),
        # Venue-year granularity: host search rarely surfaces a submission date,
        # and a fabricated day would silently pass upstream's window filters.
        'published_iso': f'{year}-01-01' if year else '',
        # Upstream's own vocabulary for host-search grounding (schemas.md).
        'retrieved_via': 'webfallback',
    }


def validate(raw: list) -> tuple[list[dict], list[str]]:
    kept, refused = [], []
    seen: set[str] = set()
    for i, record in enumerate(raw):
        if not isinstance(record, dict):
            refused.append(f'[{i}] not an object')
            continue
        title = (record.get('title') or '').strip()
        url = (record.get('url') or '').strip()
        if not title:
            refused.append(f'[{i}] missing title')
            continue
        if not url.startswith(('http://', 'https://')):
            refused.append(f'[{i}] {title[:50]!r}: no retrievable URL — refused')
            continue
        key = normalize_title(title)
        if key in seen:
            refused.append(f'[{i}] {title[:50]!r}: duplicate title in raw file')
            continue
        seen.add(key)
        kept.append(to_connector_record(record))
    return kept, refused


def merge_into_lit_results(run_dir: Path, host_file: Path) -> int:
    """Merge through upstream's own dedup_merge; returns the corpus size.

    Works whether or not a corpus already exists: on the first call the merge
    has a single input and simply canonicalizes it (paper_id, year_month); on a
    later call the EXISTING corpus goes first, so rows already in it keep their
    fields and only take what they lack from the new batch.
    """
    lit = run_dir / 'lit_results.json'
    inputs = ([str(lit)] if lit.exists() else []) + [str(host_file)]
    merged_tmp = run_dir / 'lit_results.merged.json'
    cmd = [sys.executable, '-m', 'scripts.dedup_merge',
           '--inputs', *inputs, '--out', str(merged_tmp)]
    result = subprocess.run(cmd, cwd=str(SKILL_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f'dedup_merge failed: {result.stderr[:600]}')
    print('  ' + result.stdout.strip())

    papers = json.loads(merged_tmp.read_text(encoding='utf-8'))
    rows = papers['papers'] if isinstance(papers, dict) and 'papers' in papers else papers
    for paper in rows:
        if not paper.get('retrieved_via'):
            paper['retrieved_via'] = paper.get('source')
    # Upstream demotes survey/review titles to the bottom of the corpus; the
    # merge reorders, so re-apply it here rather than leaving them ranked high.
    n_surveys = sum(1 for p in rows if _SURVEY_RE.search(p.get('title') or ''))
    if n_surveys:
        rows.sort(key=lambda p: bool(_SURVEY_RE.search(p.get('title') or '')))
        print(f'  demoted {n_surveys} survey/review-titled paper(s) to the bottom')
    lit.write_text(json.dumps(papers, indent=2, ensure_ascii=False), encoding='utf-8')
    merged_tmp.unlink()
    return len(rows)


def write_run_context(run_dir: Path, query: str) -> None:
    """Write the Phase 0 artifacts a connector run would have produced.

    `user_query.txt` is load-bearing: the 0.4 partition, the coverage check and
    Phases 1 and 2.1 are all pointed at the FILE rather than at a string the
    host retypes, so a paraphrase cannot silently propagate.
    """
    (run_dir / 'user_query.txt').write_text(query, encoding='utf-8')

    refs_path = run_dir / 'user_refs.json'
    if not refs_path.exists():
        try:
            from scripts.extract_user_refs import extract_refs_from_query
            refs = extract_refs_from_query(query)
        except Exception as exc:                 # never block a run on ref parsing
            print(f'  (user-ref extraction skipped: {exc})', file=sys.stderr)
            refs = []
        refs_path.write_text(json.dumps(refs, indent=2, ensure_ascii=False), encoding='utf-8')
        if refs:
            print(f'  extracted {len(refs)} user reference(s) -> {refs_path}')

    # Upstream's marker for "grounded in host search, not connectors". Phase 1
    # reads it; downstream consumers treat such a run as lower-confidence, and
    # they are entitled to know.
    (run_dir / '.lit_grounding_mode').write_text('webfallback', encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw', required=True, help='JSON list of host-search hits')
    ap.add_argument('--run-dir', required=True, help='the phase0 directory of this run')
    ap.add_argument('--query', default=None,
                    help="the user's research question, VERBATIM — writes user_query.txt, "
                         "user_refs.json and the grounding-mode marker (pass it on the first "
                         "ingest of a run; harmless to repeat)")
    ap.add_argument('--no-merge', action='store_true',
                    help='write websearch_phase0.json without building lit_results')
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.query:
        write_run_context(run_dir, args.query)
    try:
        raw = json.loads(Path(args.raw).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f'could not read --raw {args.raw}: {exc}')
    if not isinstance(raw, list):
        raise SystemExit('--raw must contain a JSON list of hit objects')

    kept, refused = validate(raw)
    for reason in refused:
        print(f'  refused {reason}', file=sys.stderr)
    if not kept:
        raise SystemExit('no valid host-search records — nothing written')

    host_file = run_dir / 'websearch_phase0.json'
    host_file.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding='utf-8')
    n_abs = sum(1 for r in kept if r['abstract'])
    print(f'wrote {host_file} with {len(kept)} record(s) '
          f'({n_abs} with an abstract, {len(refused)} refused)')

    if not args.no_merge:
        total = merge_into_lit_results(run_dir, host_file)
        print(f'lit_results.json now holds {total} unique paper(s) '
              f'(lit_grounding_mode = webfallback)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
