#!/usr/bin/env python3
"""decompose.py — the manuscript as passages (paperjury `decompose.js`, reduced to what the outer loop needs).

A passage is one paragraph of one section file (blank-line separated, LaTeX comments stripped for matching but kept on disk).
Its id is `<section file name>:<index>` and stays stable while the paragraph order does; after an edit the clerk re-keys by
anchor. Anchors: a referee's `evidence_anchor` must be a verbatim quote of the manuscript — `locate` returns the passage that
contains it (whitespace-normalised, case-insensitive) or None, which is what makes "cannot quote = do not file" a script fact.
"""
from __future__ import annotations
import re
from pathlib import Path

MIN_ANCHOR = 12


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def strip_comments(tex: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in tex.split("\n"))


def passages(section_paths: list[Path]) -> list[dict]:
    """[{id, section, index, text}] over every section file, in file order."""
    out = []
    for p in section_paths:
        if not p.exists():
            continue
        body = strip_comments(p.read_text(encoding="utf-8", errors="ignore"))
        for i, para in enumerate(re.split(r"\n\s*\n", body)):
            txt = para.strip()
            if txt:
                out.append({"id": f"{p.name}:{i}", "section": p.name, "index": i, "text": txt})
    return out


def locate(anchor: str, plist: list[dict]) -> dict | None:
    """The passage whose text contains the anchor verbatim (normalised); None when the quote is not in the manuscript."""
    a = norm(anchor)
    if len(a) < MIN_ANCHOR:
        return None
    for ps in plist:
        if a in norm(ps["text"]):
            return ps
    return None


def manuscript_text(section_paths: list[Path], cap: int = 120_000) -> str:
    """The sections concatenated with their file names as headers — what a referee is given inline."""
    parts = []
    for p in section_paths:
        if p.exists():
            parts.append(f"%% ===== {p.name} =====\n" + p.read_text(encoding="utf-8", errors="ignore"))
    text = "\n\n".join(parts)
    if len(text) > cap:
        raise SystemExit(f"manuscript is {len(text)} chars > {cap}: split the sections or raise the cap; never let a referee see a silent cut")
    return text
