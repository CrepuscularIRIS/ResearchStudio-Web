#!/usr/bin/env python3
"""GitHub repo search — the 4th retrieval channel (PIPELINE-V8-PLAN §1.2d).

Implementation-first prior work lives in code before it lives in papers; this
channel catches the scoop arXiv cannot see (unpublished implementations).
Output is same-shaped as the paper channels: {"items": [{url, name, desc,
stars, pushed_at, language}]}. Never raises — any failure (no token, network,
rate limit) prints {"items": [], "warning": ...} and exits 0 so the GLM
searcher seat can degrade gracefully.

Usage: python3 search_github.py --query "persistent baseline GRPO" --json [--max 8]
       (multiple --query flags allowed; results dedup by repo url)
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://api.github.com/search/repositories?per_page={per_page}&q={q}"  # sort omitted = best match
HEADERS = {  # token from env; anonymous tier also works but is rate-starved
    "Accept": "application/vnd.github+json",
    "User-Agent": "v8-research-channel",
}


def _token() -> str:
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN"):
        v = os.environ.get(k)
        if v:
            HEADERS["Authorization"] = "Bearer " + v
            return v
    return ""


def search(query: str, max_results: int) -> list:
    url = API.format(per_page=min(max_results, 30), q=urllib.parse.quote(query))
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for it in data.get("items", [])[:max_results]:
        out.append({
            "url": it.get("html_url", ""),
            "name": it.get("full_name", ""),
            "desc": (it.get("description") or "")[:300],
            "stars": it.get("stargazers_count", 0),
            "pushed_at": it.get("pushed_at", ""),
            "language": it.get("language") or "",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", action="append", required=True, help="search phrase (repeatable)")
    ap.add_argument("--max", type=int, default=8, help="results per query (default 8)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    _token()
    items, seen, warnings = [], set(), []
    for q in args.query:
        try:
            for it in search(q, args.max):
                if it["url"] and it["url"] not in seen:
                    seen.add(it["url"])
                    items.append(it)
        except Exception as e:  # never raise — one failed query must not kill the channel
            warnings.append(q + ": " + str(e)[:120])

    payload = {"items": items, "queries": args.query}
    if warnings:
        payload["warning"] = warnings
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        for it in items:
            print(f"{it['name']}  ★{it['stars']}  {it['language']}  {it['url']}")
        for w in warnings:
            print("warning: " + w, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
