---
name: spark
description: Run IdeaSpark with native Web/GitHub retrieval and the existing isolated-seat workflow
argument-hint: "<topic-slug>"
---

Run the IdeaSpark research pipeline for the run named by `$ARGUMENTS`.

1. Read `ideaspark_run/<slug>/args.json`. If `direction` is still the placeholder, stop: the pipeline has
   no research question to ground.
2. Treat `retrieval_mode` as `native` when the field is absent. `upstream` is the explicit reproducibility
   fallback that leaves all retrieval to vendored ResearchStudio Python connectors.
3. Load and follow the `ideaspark-native` skill. It is the host adapter; do not duplicate its Phase 0 or
   Phase 3.1 contracts here.
4. In native mode, drive the existing workflow one step at a time. Before every step run:

   `python3 "$SKILL_DIR/scripts/run.py" next --dir "$RUN_DIR" --query "$DIRECTION"`

   Intercept only the Phase 0 and Phase 3.1 retrieval states described by `ideaspark-native`. For every
   other state call the `Workflow` tool with `name: "ideaspark"`, the run's args, and `max_steps: 1`.
   Re-run `next` after each artifact lands. Never pass `resumeFromRunId`.
5. In upstream mode call the same `ideaspark` workflow without native interception so the original
   ResearchStudio connector path remains available.
6. Keep the existing `claude-kimi` model-routing warning: the workflow pins `claude-opus-5`,
   `glm-5.3[1m]`, `k3-256k`, and `gpt-5.6-sol` on that LiteLLM route. If the route cannot be verified,
   state that rather than claiming the per-seat routing was honored.

When terminal, return the three Phase 4 card paths (or the upstream terminal failure artifact), validator
status, and score aggregate. The run remains resumable because state is the artifact directory.
