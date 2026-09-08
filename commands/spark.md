---
name: spark
description: Run the idea-spark pipeline on a prepared run directory
argument-hint: "<topic-slug>"
---

Launch the `ideaspark` workflow for the run named by `$ARGUMENTS`.

1. Read `ideaspark_run/<slug>/args.json`. If `direction` is still the placeholder, stop and ask for one sentence — the pipeline has nothing to ground a bottleneck against without it.
2. Check the session is a `claude-kimi` one: the workflow pins per-seat model ids (`claude-opus-5`, `glm-5.3[1m]`, `k3-256k`, `gpt-5.6-sol`) that exist only on the local LiteLLM route. On the official API they are silently served by the session model instead, which makes the run neither cheap nor the routing you asked for. If you cannot tell, say so rather than guessing.
3. Call the `Workflow` tool with `name: "ideaspark"` and `args` set to the contents of that args.json.

Retrieval alone takes 3–10 minutes and the whole run is hours, so report the phase the workflow logs rather than waiting silently. When it returns, give the three card paths, the validator exit code, and the score aggregate.

A run is resumable: launching again on the same `root` picks up from the artifacts already on disk. Never pass `resumeFromRunId` — the fresh launch is the resume.
