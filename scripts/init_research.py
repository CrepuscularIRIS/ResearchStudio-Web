#!/usr/bin/env python3
"""init_research.py [--slug <topic>] [--dir <project>] — set up one IdeaSpark run.

Installs the unchanged isolated-seat workflow plus the Claude native-retrieval host adapter,
and writes the run's args.json pointed at the vendored ResearchStudio checkout.
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
    ap.add_argument(
        "--retrieval-mode",
        choices=("native", "upstream"),
        default="native",
        help="native Web/GitHub retrieval (default) or vendored ResearchStudio Python connectors",
    )
    a = ap.parse_args()

    project = Path(a.dir).resolve() if a.dir else Path.cwd().resolve()
    wf_dir = project / ".claude" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(PLUGIN / "workflows" / "ideaspark.workflow.js", wf_dir / "ideaspark.workflow.js")

    # Install only the Claude native host adapter. The former Playwright web track is gone.
    skill_src = PLUGIN / "skills" / "ideaspark-native" / "SKILL.md"
    skill_dst = project / ".claude" / "skills" / "ideaspark-native"
    skill_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(skill_src, skill_dst / "SKILL.md")

    cmd_dir = project / ".claude" / "commands"
    cmd_dir.mkdir(parents=True, exist_ok=True)
    for c in sorted((PLUGIN / "commands").glob("*.md")):
        if c.stem == "init":
            continue
        shutil.copy(c, cmd_dir / c.name)

    run_root = project / "ideaspark_run" / a.slug
    args_path = run_root / "args.json"
    run_root.mkdir(parents=True, exist_ok=True)
    written = False
    if not args_path.exists():
        args_path.write_text(
            json.dumps(
                {
                    "root": str(run_root),
                    "direction": a.direction or "<one sentence: the research direction to spark an idea in>",
                    "rs_home": str(VENDOR),
                    "compute": a.compute or "",
                    "retrieval_mode": "native" if a.retrieval_mode == "native" else "upstream",
                    "k": 1,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        written = True

    print(f"workflow  -> {wf_dir / 'ideaspark.workflow.js'}")
    print(f"skill     -> {skill_dst / 'SKILL.md'}")
    print(f"commands  -> {cmd_dir}: " + ", ".join("/" + c.stem for c in sorted(cmd_dir.glob("*.md"))))
    print(f"args.json -> {args_path}" + ("" if written else "  (kept — already existed)"))
    print(f"upstream  -> {VENDOR}")
    print(f"retrieval -> {a.retrieval_mode}")

    if a.retrieval_mode == "upstream":
        env = VENDOR / ".env"
        if not env.exists():
            print(
                f"\nupstream connector mode: copy {VENDOR / '.env.template'} to {env} and fill in "
                "the connector credentials, then verify with:\n"
                f"  python3 {VENDOR / 'skills/idea_spark/scripts/run.py'} check_connectors"
            )
    else:
        print("\nnative mode uses Claude host Web/GitHub tools for remote retrieval; connector credentials are optional.")

    print("then fill in `direction` if needed and run /research-harness:spark <slug>.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
