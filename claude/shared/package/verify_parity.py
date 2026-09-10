#!/usr/bin/env python3
"""Verify this package against the pinned ResearchStudio commit.

Recomputes the Git blob SHA-1 of every file listed in ``PROMPT_PARITY.tsv`` and
reports any drift. `bundled_exact` rows are upstream prompt/reference material
and MUST match — a mismatch means a reasoning prompt was edited, which the
port's whole integrity claim rests on not happening. `host_native` rows are
this port's adapter layer; they are checked too, but a change there is a change
to adapter policy, not a parity violation.

Usage
-----
    python3 verify_parity.py            # verify, exit non-zero on drift
    python3 verify_parity.py --list     # print the manifest and exit
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PROMPT_PARITY.tsv"


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def read_manifest() -> list[dict]:
    if not MANIFEST.exists():
        raise SystemExit(f"missing manifest: {MANIFEST}")
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:] if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print the manifest and exit")
    args = parser.parse_args()

    rows = read_manifest()
    if args.list:
        for row in rows:
            print(f"{row['mode']:<14} {row['path']}")
        return 0

    missing, drifted, ok = [], [], 0
    for row in rows:
        path = ROOT / row["path"]
        if not path.exists():
            missing.append(row)
            continue
        if git_blob_sha1(path) != row["git_blob_sha1"]:
            drifted.append(row)
        else:
            ok += 1

    commit = rows[0]["commit"] if rows else "unknown"
    print(f"pinned: {rows[0]['repository'] if rows else '?'} @ {commit[:12]}")
    print(f"verified {ok}/{len(rows)} files")

    for row in missing:
        print(f"  MISSING       {row['path']}")
    for row in drifted:
        severity = "PARITY VIOLATION" if row["mode"] == "bundled_exact" else "adapter changed"
        print(f"  {severity:<17} {row['path']}")

    violations = [r for r in drifted if r["mode"] == "bundled_exact"] + missing
    if violations:
        print(f"\nFAILED: {len(violations)} file(s) differ from the pinned commit.")
        return 1
    if drifted:
        print("\nOK (adapter files changed; no upstream prompt drift).")
        return 0
    print("\nOK: byte-identical to the pinned commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
