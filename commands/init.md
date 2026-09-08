---
name: init
description: Set up one IdeaSpark run with the isolated workflow and native retrieval adapter
argument-hint: "<topic-slug> [research direction]"
---

Set up a ResearchStudio IdeaSpark run in this project.

Run the installer, taking the slug from the first word of `$ARGUMENTS` and the direction from the rest:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_research.py" --slug <slug> --direction "<the rest>"
```

The default is `--retrieval-mode native`: Phase 0 and Phase 3.1 use the host's Web/GitHub capabilities,
so connector credentials are not required. Use `--retrieval-mode upstream` only when the user explicitly
wants the historical ResearchStudio Python-connector path; in that mode, report any credential warning
printed by the installer and do not fill credentials yourself.

Finally tell the user the next action: `/research-harness:spark <slug>`.
