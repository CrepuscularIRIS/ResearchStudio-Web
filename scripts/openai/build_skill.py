#!/usr/bin/env python3
"""Build the ChatGPT/Codex IdeaSpark skill from the OpenAI source + vendored upstream cards."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "openai" / "idea-spark"
VENDOR = ROOT / "vendor" / "researchstudio" / "skills" / "idea_spark"
PROMPTS = (
    "bottleneck_identify.txt",
    "coherence_trace.txt",
    "critique.txt",
    "derive_plain.txt",
    "expand.txt",
    "falsification_reaudit.txt",
    "ideate_generate.txt",
    "ideate_select.txt",
    "implementability_audit.txt",
    "refutation_recheck.txt",
    "revise.txt",
)


def _same(a: Path, b: Path) -> bool:
    return a.read_bytes() == b.read_bytes()


def _rejectable(path: Path) -> bool:
    return (
        path.name == ".env"
        or path.suffix == ".pyc"
        or "__pycache__" in path.parts
        or path.name in {".DS_Store"}
    )


def verify_source() -> None:
    if not (SOURCE / "SKILL.md").is_file():
        raise SystemExit(f"missing OpenAI skill source: {SOURCE / 'SKILL.md'}")
    if not (SOURCE / "agents" / "openai.yaml").is_file():
        raise SystemExit("missing agents/openai.yaml")
    for name in PROMPTS:
        a = SOURCE / "references" / "system-prompts" / name
        b = VENDOR / "references" / "system-prompts" / name
        if not a.is_file() or not b.is_file() or not _same(a, b):
            raise SystemExit(f"prompt integrity mismatch: {name}")
    upstream = SOURCE / "references" / "upstream" / "SKILL.md"
    if not upstream.is_file() or not _same(upstream, VENDOR / "SKILL.md"):
        raise SystemExit("references/upstream/SKILL.md is not byte-identical to vendor")
    bad = [p for p in SOURCE.rglob("*") if p.is_file() and _rejectable(p)]
    if bad:
        raise SystemExit("refusing cache/credential files: " + ", ".join(map(str, bad)))


def build(out_dir: Path) -> Path:
    verify_source()
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / "skill.zip"
    if archive.exists():
        archive.unlink()

    with tempfile.TemporaryDirectory(prefix="ideaspark-openai-") as td:
        stage = Path(td) / "idea-spark"
        shutil.copytree(SOURCE, stage)

        # The repository source may keep compact compatibility pointers for C00-C30.
        # The distributable archive is always self-contained: overlay exact vendored cards.
        dst_cards = stage / "references" / "ideation-sub-patterns"
        src_cards = VENDOR / "references" / "ideation-sub-patterns"
        for i in range(31):
            name = f"C{i:02d}.md"
            src = src_cards / name
            if not src.is_file():
                raise SystemExit(f"missing vendored sub-pattern card: {src}")
            shutil.copyfile(src, dst_cards / name)

        bad = [p for p in stage.rglob("*") if p.is_file() and _rejectable(p)]
        if bad:
            raise SystemExit("staged skill contains cache/credential files")

        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(stage.rglob("*")):
                if not p.is_file():
                    continue
                rel = Path("idea-spark") / p.relative_to(stage)
                zf.write(p, rel.as_posix())

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"built {archive}")
    print(f"sha256 {digest}")
    return archive


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "openai")
    ns = ap.parse_args()
    build(ns.out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
