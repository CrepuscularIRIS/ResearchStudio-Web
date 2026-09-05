#!/usr/bin/env python3
"""snowball.py — one-hop citation snowball for a seed paper (v7 dossier Search step 4).

Backward (the seed's references) and forward (the seed's citations) via the OpenAlex API,
no key. Why: search_papers.py is a metadata search over a date window — it cannot see WHO
SHAPED WHOM. RS bottleneck_identify: a recent-only window is structurally blind to the
classical ancestors of the frontier; the seed's reference list reaches them directly.

Output rows mirror search_papers.py --json shape (title/year/venue/doi/citation_count/
publication_date) so dossier searchers consume them the same way. arxiv_id is extracted
when OpenAlex carries it (locations fallback), else null — fetch by title via the local
corpus when null.

Usage:
  python3 snowball.py <arxiv-id-or-doi> [--direction refs|cited|both] [--max N] [--json]
Exit 0 with a (possibly empty) JSON list; exit 2 if the seed cannot be resolved.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

BASE = "https://api.openalex.org/works"
MAILTO = "v7-snowball-pipeline"  # OpenAlex polite pool identifier


def _get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": f"{MAILTO} (openalex)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def find_work(seed: str, title: str | None = None) -> dict | None:
    """Resolution order: OpenAlex W-id → DOI → arXiv-DOI (recent preprints) → title search
    (sort by citations, takes the canonical record — arXiv-DOI forms 404 for older papers
    whose canonical record lives under the publisher DOI)."""
    seed = seed.strip()
    urls = []
    if seed.startswith("W") and seed[1:].isdigit():
        urls.append(f"{BASE}/{seed}")
    elif seed.startswith("10."):
        urls.append(f"{BASE}/doi:{seed}")
    else:
        urls.append(f"{BASE}/doi:10.48550/arXiv.{seed}")
    if title:
        urls.append(f"{BASE}?filter=title.search:{urllib.parse.quote(title)}"
                    f"&sort=cited_by_count:desc&per-page=1&mailto={MAILTO}")
    for url in urls:
        try:
            data = _get(url)
            if data.get("results"):
                r0 = data["results"][0]
                if r0.get("id") and r0.get("title"):
                    return r0
            elif data.get("id") and data.get("title"):
                return data
        except Exception:
            continue
    return None


def _arxiv_id(work: dict) -> str | None:
    for loc in work.get("locations") or []:
        src = (loc.get("source") or {})
        page = src.get("landing_page_url") or ""
        if "arxiv.org/abs/" in page:
            return page.rsplit("/", 1)[-1]
    return None


def row(work: dict) -> dict:
    src = ((work.get("primary_location") or {}).get("source") or {})
    return {"title": work.get("title") or "",
            "year": work.get("publication_year"),
            "venue": src.get("display_name") or "",
            "doi": (work.get("doi") or "").replace("https://doi.org/", "") or None,
            "arxiv_id": _arxiv_id(work),
            "citation_count": work.get("cited_by_count", 0),
            "publication_date": work.get("publication_date"),
            "openalex_id": (work.get("id") or "").rsplit("/", 1)[-1],
            "source": "openalex"}


def references(work: dict, max_n: int) -> list[dict]:
    ids = [u.rsplit("/", 1)[-1] for u in work.get("referenced_works") or []][:50]
    out: list[dict] = []
    for i in range(0, len(ids), 50):
        batch = "|".join(ids[i:i + 50])
        try:
            data = _get(f"{BASE}?filter=openalex:{batch}&per-page=50&mailto={MAILTO}")
            out.extend(row(w) for w in data.get("results", []))
        except Exception:
            continue
    return sorted(out, key=lambda r: -(r["citation_count"] or 0))[:max_n]


def citations(work: dict, max_n: int) -> list[dict]:
    url = (work.get("cited_by_api_url") or "") + f"&per-page={min(max_n, 25)}&mailto={MAILTO}"
    if not url.startswith("http"):
        return []
    try:
        data = _get(url)
    except Exception:
        return []
    return [row(w) for w in data.get("results", [])][:max_n]


def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("seed", help="arXiv id (no version), DOI, or OpenAlex W-id")
    ap.add_argument("--title", default=None, help="paper title — fallback resolution when the id 404s")
    ap.add_argument("--direction", choices=("refs", "cited", "both"), default="both")
    ap.add_argument("--max", type=int, default=10)
    ap.add_argument("--json", action="store_true", help="print a JSON list and exit")
    a = ap.parse_args(argv)
    work = find_work(a.seed, a.title)
    if work is None:
        print(json.dumps({"error": f"seed {a.seed!r} not found in OpenAlex"}), file=sys.stderr)
        raise SystemExit(2)
    rows: list[dict] = []
    if a.direction in ("refs", "both"):
        rows.extend({**r, "direction": "refs"} for r in references(work, a.max))
    if a.direction in ("cited", "both"):
        rows.extend({**r, "direction": "cited"} for r in citations(work, a.max))
    if not (work.get("referenced_works") or []) and a.direction in ("refs", "both"):
        print("warning: this OpenAlex record has no parsed reference list — "
              "seed may be too new or under-indexed; try --title or another seed", file=sys.stderr)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"[{r['direction']}] ({r['year']}) {r['title']} — cites={r['citation_count']}")


if __name__ == "__main__":
    main(sys.argv[1:])
