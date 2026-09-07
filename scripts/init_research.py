#!/usr/bin/env python3
"""init_research.py [--slug <topic>] [--repo </abs/path>] — install the V9 harness into the current project.

Code trees are copied whole (they are the harness, not yours to edit): .claude/workflows/brain.workflow.js, .claude/skills/exp-*,
.research/tools/{exp,brain_src,launch_wrap.sh}, .research/tests, docs/refs (the verbatim prompt bank the Brain is generated from and
runs on — ResearchStudio idea_spark scripts + references, CCF / ARIS / ASI-Bench / ARFT texts). Owner files are written once and never
overwritten: .research/GOAL.md, .research/instruments/README.md, .claude/CLAUDE.md, <root>/args.json. No settings.json, no hooks.
"""
import argparse, json, shutil, stat
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
IGN = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", default="topic"); ap.add_argument("--repo", default="")
    a = ap.parse_args(); W = Path.cwd().resolve(); R = W / ".research"
    for d in ("build", "experiments", "failures", "instruments", "research/ideaspark", "tools", "tests"): (R / d).mkdir(parents=True, exist_ok=True)
    (W / ".claude/workflows").mkdir(parents=True, exist_ok=True); (W / ".claude/skills").mkdir(parents=True, exist_ok=True); (W / "docs").mkdir(exist_ok=True)
    shutil.copy(PLUGIN / "workflows/brain.workflow.js", W / ".claude/workflows/brain.workflow.js")
    for sk in sorted((PLUGIN / "skills").glob("exp-*")): shutil.copytree(sk, W / ".claude/skills" / sk.name, dirs_exist_ok=True, ignore=IGN)
    shutil.copytree(PLUGIN / "scripts/exp", R / "tools/exp", dirs_exist_ok=True, ignore=IGN)
    shutil.copytree(PLUGIN / "scripts/brain_src", R / "tools/brain_src", dirs_exist_ok=True, ignore=IGN)
    shutil.copy(PLUGIN / "scripts/launch_wrap.sh", R / "tools/launch_wrap.sh")
    for f in (R / "tools/launch_wrap.sh", R / "tools/exp/launch.sh"): f.chmod(f.stat().st_mode | stat.S_IXUSR)
    shutil.copytree(PLUGIN / "tests", R / "tests", dirs_exist_ok=True, ignore=IGN)
    shutil.copytree(PLUGIN / "refs", W / "docs/refs", dirs_exist_ok=True, ignore=IGN)
    written = []
    def once(dst: Path, text: str):
        if not dst.exists(): dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(text, encoding="utf-8"); written.append(str(dst.relative_to(W)))
    once(R / "GOAL.md", (PLUGIN / "templates/GOAL.md.tmpl").read_text(encoding="utf-8"))
    once(R / "instruments/README.md", (PLUGIN / "templates/instruments-README.md.tmpl").read_text(encoding="utf-8").replace("<PROJECT>", W.name))
    once(W / ".claude/CLAUDE.md", (PLUGIN / "templates/CLAUDE.md.tmpl").read_text(encoding="utf-8"))
    root = R / "research/ideaspark" / a.slug
    once(root / "args.json", (PLUGIN / "templates/args.json.tmpl").read_text(encoding="utf-8").replace("<HARNESS>", str(W)).replace("<SLUG>", a.slug).replace("<REPO>", a.repo or str(W)))
    once(R / "anomalies.md", "# Measured anomalies\n\n(experimental facts about the repository that no retrieved paper explains; one per bullet, with the number and where it was measured; may be empty)\n")
    print(json.dumps({"harness": str(W), "run_root": str(root), "written_once": written,
                      "next": ["fill .research/GOAL.md ## FROZEN", f"paste it into {root / 'args.json'} goal; fill dataset / venue", "canary number → .research/instruments/README.md",
                               "tests: python3 -m pytest .research/tests -q", f"/exp-auto {root}  (claude-kimi session)"]}, indent=1)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
