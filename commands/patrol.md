---
description: One sweep across every run root in this project — what needs sending, what needs checking, what is overdue
argument-hint: ""
---

Sweep **every** run root under `ideaspark_run/` and report what needs doing. Read-only and idempotent, so it is equally safe from a fresh session, on a timer, or by hand.

```bash
for d in ideaspark_run/*/; do
  s=$(basename "$d")
  echo "── $s"
  python3 .research/web/web.py watch  --root "$d"
  python3 .research/web/web.py patrol --root "$d"
done
```

Read the exit codes, not the prose: **2 means something needs doing**, 0 means nothing does.

- `NEW-BOTTLENECK` → the local run reached Phase 1 and nobody has asked the web about this diagnosis. Seed and send per the `ideaspark-web` skill.
- `POLL-NOW` → a window is past its interval. Capture it per the skill's completion rule; a length that stopped growing without the end marker is a window that stopped early, not one that finished.
- `OVERDUE` → past 90 minutes. Screenshot it and report what the screenshot showed; do not keep waiting.
- `NOT-SENT` → seeded but never sent.

If every root reports nothing due, say exactly that and stop. Do not re-check, and do not open a browser tab to "have a look".
