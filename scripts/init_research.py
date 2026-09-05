#!/usr/bin/env python3
"""init_research.py — install the V8 pipeline into the current project.

Copies dag.py + tools into .research/, the three workflows into .claude/workflows/, the
paper-search skill into .claude/skills/, writes .research/harness.json (every path the
workflows need), a GOAL.md skeleton (## FROZEN), .research/substrate.json, CLAUDE.md, and
the Workflow(<name>) allow rules. Idempotent; never overwrites an edited file.
"""
import glob, json, shutil, stat, sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
W = Path.cwd(); R = W / ".research"
for d in ("claims", "experiments", "paper", "bundles", "tools", "lit/papers", "references"):
    (R / d).mkdir(parents=True, exist_ok=True)
shutil.copy(PLUGIN / "scripts/dag.py", R / "dag.py")
for n in ("fetch_text.py", "snowball.py", "search_github.py", "launch_wrap.sh"):
    shutil.copy(PLUGIN / "scripts/tools" / n, R / "tools" / n)
(R / "tools/launch_wrap.sh").chmod((R / "tools/launch_wrap.sh").stat().st_mode | stat.S_IXUSR)
(W / ".claude/workflows").mkdir(parents=True, exist_ok=True)
for n in ("research", "experiment", "paper"):
    shutil.copy(PLUGIN / "workflows" / f"{n}.workflow.js", W / ".claude/workflows" / f"{n}.workflow.js")
skill = W / ".claude/skills/paper-search"
if not skill.exists():
    shutil.copytree(PLUGIN / "skills/paper-search", skill)

grok = sorted(glob.glob(str(Path.home() / ".claude/plugins/cache/grok/grok/*/scripts/grok-companion.mjs")))
harness = R / "harness.json"
if not harness.exists():
    harness.write_text(json.dumps({
        "root": str(W),
        "tools_dir": str(R / "tools"),
        "search_cmd": "python3 " + str(skill / "scripts/search_papers.py"),
        "fetch_cmd": "python3 " + str(R / "tools/fetch_text.py"),
        "rs_ref": str(R / "references/idea_spark/references"),
        "grok_cli": ("node " + grok[-1]) if grok else "grok",
        "exp_repo": str(W),
    }, indent=1) + "\n")
    print("wrote .research/harness.json — set exp_repo (the experiment git repo) and rs_ref (ResearchStudio idea_spark/references clone)")

goal = R / "GOAL.md"
if not goal.exists():
    shutil.copy(PLUGIN / "templates/GOAL.md.tmpl", goal); print("wrote .research/GOAL.md — fill every field of ## FROZEN")
sub = R / "substrate.json"
if not sub.exists():
    shutil.copy(PLUGIN / "templates/substrate.json.tmpl", sub); print("wrote .research/substrate.json — name the frozen hosts, checkpoints, canary")
card = W / ".claude/CLAUDE.md"
if not card.exists():
    shutil.copy(PLUGIN / "templates/CLAUDE.md.tmpl", card); print("wrote .claude/CLAUDE.md (the Main card)")

settings = W / ".claude/settings.json"
cfg = json.loads(settings.read_text()) if settings.exists() else {}
allow = cfg.setdefault("permissions", {}).setdefault("allow", [])
for name in ("research", "experiment", "paper"):
    if f"Workflow({name})" not in allow:
        allow.append(f"Workflow({name})")
settings.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"ok: {R} ready. Next: edit .research/GOAL.md (## FROZEN) and substrate.json, then `python3 .research/dag.py next`.")
