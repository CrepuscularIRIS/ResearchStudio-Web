#!/usr/bin/env python3
"""init_research.py — install the claim loop into the current project: .research/ scripts, bin/run_protected.sh, the paper-search skill,
templates, GOAL.md campaign block, CLAUDE.md, and the Workflow(<name>) allow rules. Idempotent; never overwrites an edited file."""
import json, shutil, stat, sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
W = Path.cwd(); R = W / ".research"
for d in ("cards", "records", "bundles", "gates", "build", "monitor", "tokens", "reports", "verdicts", "lit/papers", "templates", "tests"):
    (R / d).mkdir(parents=True, exist_ok=True)
for n in ("stage.py", "step.py", "bundle.py", "gate.py", "gapmap.py", "render_record.py", "fetch_text.py", "launch_wrap.sh"):
    shutil.copy(PLUGIN / "scripts" / n, R / n)
(W / "bin").mkdir(exist_ok=True); shutil.copy(PLUGIN / "scripts/run_protected.sh", W / "bin/run_protected.sh")
for p in (W / "bin/run_protected.sh", R / "launch_wrap.sh"):
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
skill = W / ".claude/skills/paper-search"
if not skill.exists():
    shutil.copytree(PLUGIN / "skills/paper-search", skill)
for t in (PLUGIN / "templates").iterdir():
    dst = R / "templates" / t.name
    if not dst.exists():
        shutil.copy(t, dst)
for n in ("anomalies.md", "retracted.txt"):
    if not (R / n).exists():
        shutil.copy(PLUGIN / "templates" / n, R / n)
goal = W / "GOAL.md"
block = "```yaml\n" + (PLUGIN / "templates/GOAL-block.yaml").read_text() + "```\n\n"
if not goal.exists():
    goal.write_text(block + "# GOAL\n\n## FROZEN\nThe problem sentence, metric, protocol and baselines. The owner edits this block only; every gate refuses while its sha differs from `gate.py frozen --accept`.\n"); print("wrote GOAL.md — edit every field, then `python3 .research/gate.py frozen --accept`")
elif not goal.read_text().startswith("```yaml"):
    goal.write_text(block + goal.read_text()); print("prepended the campaign block to GOAL.md — edit every field")
card = W / "CLAUDE.md"
if not card.exists():
    shutil.copy(PLUGIN / "templates/CLAUDE.md.tmpl", card); print("wrote CLAUDE.md from the template")
settings = W / ".claude/settings.json"; settings.parent.mkdir(exist_ok=True)
cfg = json.loads(settings.read_text()) if settings.exists() else {}
allow = cfg.setdefault("permissions", {}).setdefault("allow", [])
for name in ("frame", "mechanism", "spec", "build", "write", "pivot"):
    if f"Workflow({name})" not in allow:
        allow.append(f"Workflow({name})")
settings.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"ok: {R} ready. Next: edit GOAL.md (campaign block + FROZEN), `gate.py frozen --accept`, then `python3 .research/stage.py` (it starts at A: the scientist writes CLAIM.md).")
