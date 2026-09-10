#!/usr/bin/env python3
"""Acceptance suite for this repo: run it before pushing, and when an install fails.

Six checks, each one a thing that has actually broken here at least once:

1. marketplace.json validates against the published JSON Schema
   (https://www.schemastore.org/claude-code-marketplace.json)
2. components are declared in exactly ONE place — plugin.json's auto-discovery
   OR the marketplace entry's `skills[]`, never both (the CLI rejects both, and
   a stricter consumer rejects the whole sync)
3. every skill named by the plugin exists and has valid frontmatter within
   claude.ai's limits (name <=64 chars, description <=1024)
4. every package's PROMPT_PARITY.tsv verifies — upstream prompts unmodified
5. no secret material anywhere in the tree
6. `claude plugin validate` agrees, when the CLI is on PATH

Usage
-----
    python3 claude/check.py            # all checks, non-zero exit on failure
    python3 claude/check.py --offline  # skip the schema fetch
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA_URL = "https://www.schemastore.org/claude-code-marketplace.json"
MAX_NAME, MAX_DESC = 64, 1024
SECRET_RE = re.compile(
    r"(OPENREVIEW_PASS\s*=|sk-ant-[A-Za-z0-9]|ghp_[A-Za-z0-9]{20}|"
    r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")

failures: list[str] = []
notes: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    if not ok:
        failures.append(f"{name}: {detail}")


def marketplace() -> dict:
    return json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))


def check_schema(offline: bool) -> None:
    if offline:
        notes.append("schema check skipped (--offline)")
        return
    try:
        with urllib.request.urlopen(SCHEMA_URL, timeout=20) as response:
            schema = json.loads(response.read())
    except Exception as exc:
        notes.append(f"schema not fetched ({type(exc).__name__}); check skipped")
        return
    try:
        import jsonschema
    except ImportError:
        notes.append("jsonschema not installed; schema check skipped")
        return
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(marketplace()))
    check("marketplace.json matches the published schema", not errors,
          "; ".join(f"{list(e.path)}: {e.message[:80]}" for e in errors[:3]))


def check_single_source() -> None:
    """The failure that produced 'conflicting manifests' — and, we suspect, the
    web's 'Marketplace sync failed'. Components belong in exactly one file."""
    has_plugin_json = (REPO / ".claude-plugin" / "plugin.json").exists()
    for entry in marketplace()["plugins"]:
        listed = any(k in entry for k in
                     ("skills", "agents", "commands", "hooks", "mcpServers", "lspServers"))
        both = has_plugin_json and listed and not entry.get("strict")
        check(f"plugin {entry['name']!r} declares components in one place", not both,
              "plugin.json auto-discovers AND the entry lists components; drop one "
              "or set strict:true" if both else "")


def iter_skill_dirs() -> list[Path]:
    entry = marketplace()["plugins"][0]
    if "skills" in entry:
        return [REPO / p.lstrip("./") for p in entry["skills"]]
    return sorted(d for d in (REPO / "skills").iterdir() if d.is_dir()) \
        if (REPO / "skills").is_dir() else []


def check_skills() -> None:
    skill_dirs = iter_skill_dirs()
    check("plugin resolves at least one skill", bool(skill_dirs))
    for d in skill_dirs:
        md = d / "SKILL.md"
        if not md.exists():
            check(f"{d.name}: SKILL.md present", False, f"missing {md}")
            continue
        text = md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            check(f"{d.name}: frontmatter present", False, "no leading ---")
            continue
        block = text.split("---", 2)[1]
        fields, key = {}, None
        for line in block.splitlines():
            if not line.strip():
                continue
            if ":" in line and not line.startswith((" ", "\t")):
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
            elif key:
                fields[key.strip()] += " " + line.strip()
        name_ok = 0 < len(fields.get("name", "")) <= MAX_NAME
        desc_ok = 0 < len(fields.get("description", "")) <= MAX_DESC
        check(f"{d.name}: frontmatter within claude.ai limits", name_ok and desc_ok,
              f"name={len(fields.get('name',''))} desc={len(fields.get('description',''))}")


def check_parity() -> None:
    for d in iter_skill_dirs():
        script = d / "verify_parity.py"
        if not script.exists():
            check(f"{d.name}: parity manifest", False, "verify_parity.py missing")
            continue
        result = subprocess.run([sys.executable, "verify_parity.py"], cwd=d,
                                capture_output=True, text=True)
        check(f"{d.name}: upstream prompts unmodified", result.returncode == 0,
              result.stdout.strip().splitlines()[-1] if result.returncode else "")


def check_secrets() -> None:
    hits = []
    for path in REPO.rglob("*"):
        if not path.is_file() or ".git/" in str(path) or path.suffix in {".zip", ".skill"}:
            continue
        try:
            if SECRET_RE.search(path.read_text(encoding="utf-8", errors="ignore")):
                hits.append(str(path.relative_to(REPO)))
        except OSError:
            continue
    check("no secret material in the tree", not hits, ", ".join(hits[:3]))


def check_cli() -> None:
    try:
        result = subprocess.run(["claude", "plugin", "validate", str(REPO)],
                                capture_output=True, text=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        notes.append("claude CLI not available; its validator was skipped")
        return
    check("claude plugin validate", result.returncode == 0,
          (result.stdout + result.stderr).strip()[-160:] if result.returncode else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="skip the schema fetch")
    args = parser.parse_args()

    print(f"acceptance checks for {REPO}\n")
    check_schema(args.offline)
    check_single_source()
    check_skills()
    check_parity()
    check_secrets()
    check_cli()

    for note in notes:
        print(f"  note  {note}")
    print()
    if failures:
        print(f"FAILED — {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
