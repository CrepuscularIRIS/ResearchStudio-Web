#!/usr/bin/env python3
"""init_research.py [--slug <topic>] [--dir <project>] — set up one idea-spark run.

Installs the workflow into the project and writes the run's args.json, pointed at the
ResearchStudio checkout this plugin vendors. Nothing else is copied: the pipeline itself
lives in the vendored upstream tree, which is never edited.

Layout produced (upstream's own run-dir convention — one run, one directory):

    <project>/.claude/workflows/ideaspark.workflow.js
    <project>/ideaspark_run/<slug>/args.json        <- fill in `direction`, then launch

The run directory is NOT created here: `run.py phase0` mkdir -p's its own --out, and the
workflow treats a missing directory as a fresh run. args.json is written once and never
overwritten.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
VENDOR = PLUGIN / "vendor" / "researchstudio"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="topic", help="kebab-case topic slug; one run per slug")
    ap.add_argument("--dir", default="", help="project root (default: the current directory)")
    ap.add_argument("--direction", default="", help="the research direction, one sentence")
    ap.add_argument("--compute", default="", help="standing compute profile, e.g. '2x4090 48GB, ~30 GPU-days'")
    a = ap.parse_args()

    project = Path(a.dir).resolve() if a.dir else Path.cwd().resolve()
    wf_dir = project / ".claude" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(PLUGIN / "workflows" / "ideaspark.workflow.js", wf_dir / "ideaspark.workflow.js")

    # the web track: its skill and its deterministic half, plus the slash commands that fire both
    # tracks. Installed project-locally with the plugin-root placeholder resolved, so the commands
    # work whether or not this plugin is enabled as a plugin.
    sk = project / ".claude" / "skills" / "ideaspark-web"
    sk.mkdir(parents=True, exist_ok=True)
    shutil.copy(PLUGIN / "skills" / "ideaspark-web" / "SKILL.md", sk / "SKILL.md")
    web = project / ".research" / "web"
    web.mkdir(parents=True, exist_ok=True)
    shutil.copy(PLUGIN / "scripts" / "web" / "web.py", web / "web.py")
    (web / "web.py").chmod(0o755)
    cmd_dir = project / ".claude" / "commands"
    cmd_dir.mkdir(parents=True, exist_ok=True)
    for c in sorted((PLUGIN / "commands").glob("*.md")):
        if c.stem == "init":
            continue                      # installing is what just happened; the copy would be circular
        (cmd_dir / c.name).write_text(
            c.read_text(encoding="utf-8").replace('"${CLAUDE_PLUGIN_ROOT}/scripts/web/web.py"', ".research/web/web.py"),
            encoding="utf-8")

    run_root = project / "ideaspark_run" / a.slug
    args_path = run_root / "args.json"
    run_root.mkdir(parents=True, exist_ok=True)
    written = False
    if not args_path.exists():
        args_path.write_text(json.dumps({
            "root": str(run_root),
            "direction": a.direction or "<one sentence: the research direction to spark an idea in>",
            "rs_home": str(VENDOR),
            "compute": a.compute or "",
            "k": 1,
        }, indent=2) + "\n", encoding="utf-8")
        written = True

    env = VENDOR / ".env"
    print(f"workflow  → {wf_dir / 'ideaspark.workflow.js'}")
    print(f"skill     → {sk / 'SKILL.md'} (+ {web / 'web.py'})")
    print(f"commands  → {cmd_dir}: " + ", ".join("/" + c.stem for c in sorted(cmd_dir.glob("*.md"))))
    print(f"args.json → {args_path}" + ("" if written else "  (kept — already existed)"))
    print(f"upstream  → {VENDOR}")
    if not env.exists():
        print(f"\nconnectors: copy {VENDOR / '.env.template'} to {env} and fill in the OpenReview\n"
              f"user/password (+ a Semantic Scholar key). Without them those connectors are skipped\n"
              f"and Phase 0 loses the in-review window. Verify with:\n"
              f"  python3 {VENDOR / 'skills/idea_spark/scripts/run.py'} check_connectors")
    print("\nthen fill in `direction` in args.json and launch the `ideaspark` workflow with it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
