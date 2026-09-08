---
description: Set up one idea-spark run — install the workflow and write args.json
argument-hint: "<topic-slug> [research direction]"
---

Set up a ResearchStudio idea-spark run in this project.

Run the installer, taking the slug from the first word of `$ARGUMENTS` and the direction from the rest (quote it):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_research.py" --slug <slug> --direction "<the rest>"
```

Then report what it printed, and — if it warned that the connector credentials are missing — say so plainly, with the two keys that matter (OpenReview user/password, Semantic Scholar key) and the `check_connectors` command it named. Do not fill in credentials yourself.

Finally tell the user the one next action: `/research-harness:spark <slug>`.
