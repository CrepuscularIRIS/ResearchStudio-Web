#!/usr/bin/env python3
"""Build claude.ai `.skill` packages from the pinned ResearchStudio upstream.

Each package is an overlay: upstream files are vendored byte-for-byte at build
time (so this repo stays small and can never drift from upstream by hand), and
the Claude-web host layer — SKILL.md, the `claude-web-*.md` adapter notes, and
any host-native script — is copied over the top.

Every vendored file is recorded in ``PROMPT_PARITY.tsv`` with its Git blob
SHA-1, so a package can be verified against upstream later with
``verify_parity.py``.

Usage
-----
    python3 build.py                 # build every skill into dist/
    python3 build.py idea-spark      # build one
    python3 build.py --no-zip        # leave the staged tree, skip the .skill
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

logger = logging.getLogger("build")

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
STAGE = ROOT / ".build"

# claude.ai skill frontmatter limits (skill-creator/scripts/quick_validate.py).
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024
MAX_COMPATIBILITY_CHARS = 500

EXCLUDE_PARTS = {"__pycache__", ".git", ".ruff_cache", "node_modules"}
EXCLUDE_NAMES = {".env", ".DS_Store", ".connectors_degraded"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


@dataclass(frozen=True)
class Manifest:
    """One skill's build recipe, read from ``<skill>/manifest.json``."""

    name: str
    description_source: Path       # the SKILL.md whose frontmatter ships
    upstream_root: Path            # absolute path into the pinned repo
    vendor: tuple[str, ...]        # sub-paths of upstream_root to copy
    upstream_skill_md_to: str      # where the upstream runbook is preserved
    overlay_root: Path             # host-native files, copied last
    shared_references: tuple[str, ...] | None  # None = every shared reference

    @classmethod
    def load(cls, skill_dir: Path, repo: Path) -> "Manifest":
        raw = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
        return cls(
            name=raw["name"],
            description_source=skill_dir / "SKILL.md",
            upstream_root=(repo / raw["upstream_root"]).resolve(),
            vendor=tuple(raw.get("vendor", [])),
            upstream_skill_md_to=raw.get("upstream_skill_md_to",
                                         "references/upstream/SKILL.md"),
            overlay_root=skill_dir,
            shared_references=tuple(raw["shared_references"])
            if "shared_references" in raw else None,
        )


def repo_root() -> Path:
    """The pinned ResearchStudio checkout.

    Looked up in order: ``$RESEARCHSTUDIO_REPO``, a sibling of this repo, then
    ``~/autoresearch/ResearchStudio`` — so the build works from a fresh clone
    wherever the upstream checkout happens to live.
    """
    candidates = [Path(p) for p in (os.environ.get("RESEARCHSTUDIO_REPO"),) if p]
    candidates += [ROOT.parent.parent / "ResearchStudio",
                   Path.home() / "autoresearch" / "ResearchStudio"]
    for candidate in candidates:
        if (candidate / ".git").is_dir():
            return candidate.resolve()
    raise SystemExit(
        "pinned upstream checkout not found. Clone microsoft/ResearchStudio and "
        "point RESEARCHSTUDIO_REPO at it. Tried: "
        + ", ".join(str(c) for c in candidates))


def pinned_commit(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def git_blob_sha1(path: Path) -> str:
    """Git's own object id for a file — comparable against `git hash-object`."""
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def is_excluded(path: Path) -> bool:
    if EXCLUDE_PARTS.intersection(path.parts):
        return True
    return path.name in EXCLUDE_NAMES or path.suffix in EXCLUDE_SUFFIXES


def copy_tree(src: Path, dst: Path) -> list[Path]:
    """Copy `src` into `dst`, skipping build/venv noise. Returns copied paths."""
    copied: list[Path] = []
    if src.is_file():
        if is_excluded(src):
            return copied
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return [dst]
    for item in sorted(src.rglob("*")):
        if not item.is_file() or is_excluded(item.relative_to(src)):
            continue
        target = dst / item.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied.append(target)
    return copied


def parse_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{skill_md}: missing YAML frontmatter")
    _, block, _ = text.split("---", 2)
    fields: dict[str, str] = {}
    key = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key:
            fields[key] += " " + line.strip()
    return fields


def validate(skill_md: Path) -> None:
    """Enforce the claude.ai frontmatter limits before packaging."""
    fields = parse_frontmatter(skill_md)
    for required in ("name", "description"):
        if not fields.get(required):
            raise SystemExit(f"{skill_md}: frontmatter is missing `{required}`")
    checks = (("name", MAX_NAME_CHARS), ("description", MAX_DESCRIPTION_CHARS),
              ("compatibility", MAX_COMPATIBILITY_CHARS))
    for field, limit in checks:
        value = fields.get(field)
        if value and len(value) > limit:
            raise SystemExit(
                f"{skill_md}: `{field}` is {len(value)} chars, limit is {limit}")
    logger.info("  frontmatter ok (name=%r, description=%d chars)",
                fields["name"], len(fields["description"]))


def write_parity(pkg: Path, rows: list[tuple[str, str, str]], commit: str) -> None:
    lines = ["mode\tpath\tgit_blob_sha1\trepository\tcommit\tsource_path"]
    for mode, rel, source in sorted(rows, key=lambda r: (r[0], r[1])):
        sha = git_blob_sha1(pkg / rel)
        lines.append(f"{mode}\t{rel}\t{sha}\tmicrosoft/ResearchStudio\t{commit}\t{source}")
    (pkg / "PROMPT_PARITY.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_origin(pkg: Path, manifest: Manifest, commit: str) -> None:
    template = (ROOT / "shared" / "ORIGIN.template.md").read_text(encoding="utf-8")
    (pkg / "ORIGIN.md").write_text(
        template.replace("{{SKILL}}", manifest.name)
                .replace("{{COMMIT}}", commit)
                .replace("{{UPSTREAM_PATH}}",
                         str(manifest.upstream_root.relative_to(repo_root())))
                .replace("{{DATE}}", date.today().isoformat()),
        encoding="utf-8")


def build_skill(skill_dir: Path, repo: Path, commit: str, make_zip: bool) -> Path:
    manifest = Manifest.load(skill_dir, repo)
    logger.info("building %s", manifest.name)
    pkg = STAGE / manifest.name
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    rows: list[tuple[str, str, str]] = []

    # 1. Vendor upstream, byte-for-byte.
    for sub in manifest.vendor:
        src = manifest.upstream_root / sub
        if not src.exists():
            raise SystemExit(f"{manifest.name}: upstream path missing: {src}")
        for copied in copy_tree(src, pkg / sub):
            rel = copied.relative_to(pkg).as_posix()
            source = (manifest.upstream_root.relative_to(repo) / sub /
                      copied.relative_to(pkg / sub)).as_posix() if src.is_dir() else \
                     (manifest.upstream_root.relative_to(repo) / sub).as_posix()
            rows.append(("bundled_exact", rel, source))

    # 2. Preserve the upstream runbook where the adapter can point at it.
    upstream_md = manifest.upstream_root / "SKILL.md"
    if upstream_md.exists():
        target = pkg / manifest.upstream_skill_md_to
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(upstream_md, target)
        rows.append(("bundled_exact", manifest.upstream_skill_md_to,
                     (manifest.upstream_root.relative_to(repo) / "SKILL.md").as_posix()))

    # 3. Shared host layer, then the skill's own overlay (overlay wins).
    # A skill only ships the adapter notes it actually needs: handing a
    # self-contained scorer the retrieval routing invites it to go searching.
    for ref in sorted((ROOT / "shared" / "references").glob("*.md")):
        if manifest.shared_references is not None and ref.name not in manifest.shared_references:
            continue
        for copied in copy_tree(ref, pkg / "references" / ref.name):
            rows.append(("host_native", copied.relative_to(pkg).as_posix(),
                         f"claude/shared/references/{ref.name}"))
    for copied in copy_tree(ROOT / "shared" / "package", pkg):
        rows.append(("host_native", copied.relative_to(pkg).as_posix(), "claude/shared/package"))
    for item in sorted(manifest.overlay_root.rglob("*")):
        if not item.is_file() or item.name == "manifest.json" or is_excluded(
                item.relative_to(manifest.overlay_root)):
            continue
        rel = item.relative_to(manifest.overlay_root)
        target = pkg / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        rows = [r for r in rows if r[1] != rel.as_posix()]
        rows.append(("host_native", rel.as_posix(), f"claude/{manifest.name}/{rel.as_posix()}"))

    validate(pkg / "SKILL.md")
    write_origin(pkg, manifest, commit)
    write_parity(pkg, rows, commit)

    n_files = sum(1 for p in pkg.rglob("*") if p.is_file())
    size_kb = sum(p.stat().st_size for p in pkg.rglob("*") if p.is_file()) / 1024
    logger.info("  staged %d files, %.0f KB", n_files, size_kb)

    if not make_zip:
        return pkg
    DIST.mkdir(exist_ok=True)
    out = DIST / f"{manifest.name}.skill"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(pkg.rglob("*")):
            if item.is_file():
                zf.write(item, Path(manifest.name) / item.relative_to(pkg))
    # Also ship a .zip copy: some upload surfaces filter on the extension, and
    # a user who cannot upload the file is not helped by it being correctly built.
    shutil.copy2(out, out.with_suffix(".zip"))
    logger.info("  wrote %s (+ .zip copy, %.0f KB)", out, out.stat().st_size / 1024)
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skills", nargs="*", help="skill names (default: all)")
    parser.add_argument("--no-zip", action="store_true",
                        help="stage the tree without producing a .skill file")
    parser.add_argument("--emit", metavar="DIR", default=None,
                        help="also copy each staged package to DIR/<name>/ — the "
                             "layout a Claude Code plugin marketplace installs from")
    args = parser.parse_args()

    repo = repo_root()
    commit = pinned_commit(repo)
    logger.info("pinned upstream: microsoft/ResearchStudio @ %s", commit[:12])

    available = sorted(d for d in ROOT.iterdir()
                       if d.is_dir() and (d / "manifest.json").exists())
    wanted = ([d for d in available if d.name in args.skills] if args.skills
              else available)
    if args.skills and len(wanted) != len(args.skills):
        missing = set(args.skills) - {d.name for d in wanted}
        raise SystemExit(f"unknown skill(s): {sorted(missing)}")

    for skill_dir in wanted:
        build_skill(skill_dir, repo, commit, make_zip=not args.no_zip)
    if args.emit:
        emit_root = Path(args.emit)
        for skill_dir in wanted:
            name = json.loads((skill_dir / "manifest.json").read_text())["name"]
            target = emit_root / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(STAGE / name, target)
            logger.info("emitted %s", target)
    logger.info("done: %d skill(s)", len(wanted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
