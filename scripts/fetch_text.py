#!/usr/bin/env python3
"""fetch_text.py — search results → full text on disk → the cycle manifest.

usage: fetch_text.py <search.json> --cycle <c> [--corpus <corpus.py>] [--max N] [--sleep S]

<search.json> is `search_papers.py ... --json` output (ranked, deduped). For every paper:
local corpus PDF first (80k CCF-A papers on /data), arXiv PDF second, then `pdftotext`.
Writes `lit/papers/<id>.txt` and `lit/<cycle>.json`; never ranks, never reads the text.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIT = HERE / "lit"; PAPERS = LIT / "papers"
CORPUS = Path(os.environ.get("RESEARCH_CORPUS", str(Path.cwd() / "search" / "corpus.py")))      # the local corpus index; RESEARCH_CORPUS or <project>/search/corpus.py
UA = "research-loop fetch_text.py (mailto:anjun.lyu@gmail.com)"
KEEP = ["title", "year", "venue", "url", "doi", "arxiv_id", "authors", "relevance_score",
        "citation_count", "found_in", "is_survey"]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def paper_id(p: dict) -> str:
    a = str(p.get("arxiv_id") or "")
    a = re.sub(r"v\d+$", "", a.split("/")[-1]) if a else ""
    if a:
        return a
    if p.get("doi"):
        return re.sub(r"[^A-Za-z0-9.]+", "_", str(p["doi"]))[:60]
    return "t_" + "_".join(norm(p.get("title")).split()[:6])


def corpus_pdf(title: str, corpus: Path) -> Path | None:
    """Title-only lookup; a miss means 'not titled that'."""
    words = norm(title).split()[:8]
    if not words or not corpus.exists():
        return None
    q = '"' + " ".join(words) + '"'
    try:
        out = subprocess.run([sys.executable, str(corpus), "search", q, "--paths", "--limit", "5"],
                             capture_output=True, text=True, timeout=60).stdout.splitlines()
    except (subprocess.SubprocessError, OSError):
        return None
    want = norm(title)[:80]
    for i, line in enumerate(out):
        m = re.match(r"\[.\]\s+\S+\s+(.*)$", line)
        if m and norm(m.group(1))[:80] == want and i + 1 < len(out):
            cand = out[i + 1].strip()
            if cand.endswith(".pdf") and Path(cand).exists():
                return Path(cand)
    return None


def arxiv_pdf(aid: str, dest: Path) -> bool:
    req = urllib.request.Request(f"https://arxiv.org/pdf/{aid}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except Exception:
        return False
    if not data.startswith(b"%PDF"):
        return False
    dest.write_bytes(data)
    return True


def to_text(pdf: Path, txt: Path) -> int:
    r = subprocess.run(["pdftotext", str(pdf), str(txt)], capture_output=True, text=True)
    if r.returncode or not txt.exists():
        return 0
    return len(txt.read_text(errors="ignore"))


def fetch_one(p: dict, corpus: Path, sleep: float) -> dict:
    pid = paper_id(p)
    row = {"id": pid, **{k: p.get(k) for k in KEEP}, "text_path": None, "text_chars": 0,
           "status": "no_text", "text_source": None}
    txt = PAPERS / f"{pid}.txt"
    if txt.exists() and txt.stat().st_size > 1000:
        row.update(text_path=str(txt), text_chars=txt.stat().st_size, status="text", text_source="cached")
        return row
    src = corpus_pdf(p.get("title", ""), corpus)
    origin = "corpus"
    if src is None and row["arxiv_id"]:
        dest = PAPERS / f"{pid}.pdf"
        if arxiv_pdf(pid, dest):
            src, origin = dest, "arxiv"
        time.sleep(sleep)
    if src is None:
        return row
    n = to_text(src, txt)
    if n > 1000:
        row.update(text_path=str(txt), text_chars=n, status="text", text_source=origin)
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fetch_text.py")
    ap.add_argument("search_json", nargs="?"); ap.add_argument("--cycle")
    ap.add_argument("--one", help="fetch a single arXiv id (no version) → lit/papers/<id>.txt; prints the row as JSON")
    ap.add_argument("--corpus", default=str(CORPUS)); ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between arXiv downloads")
    a = ap.parse_args(argv)
    if a.one:
        PAPERS.mkdir(parents=True, exist_ok=True)
        row = fetch_one({"arxiv_id": a.one, "id": a.one, "title": ""}, Path(a.corpus), a.sleep)
        print(json.dumps(row, ensure_ascii=False)); return 0 if row["status"] == "text" else 1
    if not a.search_json or not a.cycle:
        ap.error("either --one <id> or <search_json> --cycle <c>")
    papers = json.loads(Path(a.search_json).read_text())
    if a.max:
        papers = papers[:a.max]
    PAPERS.mkdir(parents=True, exist_ok=True)
    rows = [fetch_one(p, Path(a.corpus), a.sleep) for p in papers]
    out = LIT / f"{a.cycle}.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    got = sum(r["status"] == "text" for r in rows)
    by = {}
    for r in rows:
        by[r["text_source"]] = by.get(r["text_source"], 0) + 1
    print(f"{got}/{len(rows)} with full text ({by}) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
