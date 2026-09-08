# Native Retrieval + OpenAI IdeaSpark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace browser-automation/Python-first retrieval with native Claude/OpenAI retrieval adapters while preserving ResearchStudio reasoning prompts and the existing isolated-seat phase graph.

**Architecture:** Keep `workflows/ideaspark.workflow.js` unchanged and drive it one step at a time from a Claude host adapter that intercepts Phase 0 and Phase 3.1 retrieval. Add a shared ChatGPT/Codex Skill under `openai/idea-spark/`, sourced from the already-validated native-retrieval port and packaged against the vendored ResearchStudio prompt/card source.

**Tech Stack:** Claude Code plugin Markdown/workflows, Python 3 stdlib, ResearchStudio vendored Python runtime, OpenAI Skill (`SKILL.md`, `agents/openai.yaml`), GitHub connector/app, native web search.

**Spec:** `docs/superpowers/specs/2026-09-08-native-retrieval-openai-skill-design.md`

## Global Constraints

- Do not modify the eleven ResearchStudio system prompts.
- Do not modify `vendor/researchstudio/` upstream files.
- Do not rewrite the existing Claude phase graph or `workflows/ideaspark.workflow.js`.
- Native retrieval writes the artifact protocol the existing navigator already understands.
- Keep an explicit `retrieval_mode=upstream` fallback.
- GitHub-only evidence must never be inserted into scholarly collision results or used alone for novelty verdicts.
- The distributable ChatGPT/Codex archive must be named exactly `skill.zip` and contain no credentials/cache files.

---

### Task 1: Claude native host adapter

**Files:**
- Create: `skills/ideaspark-native/SKILL.md`
- Modify: `commands/spark.md`
- Test: `tests/test_native_host_adapter.py`

**Interfaces:**
- Consumes: existing `ideaspark` workflow, vendored `scripts/run.py next`, run `args.json`.
- Produces: a host loop that intercepts Phase 0 and Phase 3.1, otherwise invokes `Workflow(name="ideaspark", max_steps=1)`.

- [x] Write failing tests asserting `/spark` defaults to native retrieval, preserves `retrieval_mode=upstream`, inspects `run.py next`, invokes workflow with `max_steps=1`, and names both Phase 0 and Phase 3.1 interception artifacts.
- [x] Run the targeted test and confirm the expected red state.
- [x] Implement `skills/ideaspark-native/SKILL.md` with exact artifact contracts and rewrite `commands/spark.md` to load/follow it.
- [x] Re-run the unit test and confirm pass.

### Task 2: OpenAI ChatGPT/Codex Skill source

**Files:**
- Create: `openai/idea-spark/**`
- Test: `tests/test_openai_skill.py`

**Interfaces:**
- Consumes: `vendor/researchstudio/skills/idea_spark/` as upstream source of truth.
- Produces: installable OpenAI Skill source supporting ChatGPT and Codex, native GitHub/web/Files retrieval, deterministic Python state/merge helpers.

- [x] Write failing tests for layout, metadata, required adapter references, routing behavior, and eleven prompt byte identity against vendor paths.
- [x] Run the targeted test and confirm failure because `openai/idea-spark/` did not exist.
- [x] Assemble `openai/idea-spark/` from the vendored upstream tree plus a small OpenAI control-plane overlay, keeping eleven prompt bytes unchanged.
- [x] Re-run the targeted test and confirm pass.

### Task 3: Self-contained OpenAI packaging

**Files:**
- Create: `scripts/openai/build_skill.py`
- Extend: `tests/test_openai_skill.py`

**Interfaces:**
- Consumes: `openai/idea-spark/` plus vendored C00-C30 cards.
- Produces: `dist/openai/skill.zip` with exact vendored cards overlaid and no credentials/cache files.

- [x] Add failing tests for exact archive filename, clean members, required OpenAI metadata, and card byte identity versus vendor.
- [x] Run tests and confirm failure because builder was absent.
- [x] Implement stdlib-only builder: stage source, overlay vendor cards, verify prompt identity, reject `.env`/cache files, write `skill.zip`.
- [x] Run builder and tests; confirm pass.

### Task 4: Product surface cleanup and docs

**Files:**
- Modify: `README.md`
- Modify: `.claude-plugin/plugin.json`
- Delete: `skills/ideaspark-web/SKILL.md`
- Delete: `commands/web.md`
- Delete: `scripts/web/web.py`
- Extend: `tests/test_native_host_adapter.py`

**Interfaces:**
- Produces: exactly two documented surfaces: Claude Code and OpenAI (ChatGPT/Codex).

- [x] Add failing assertions that primary docs no longer advertise Playwright/browser automation and do advertise `openai/idea-spark`, ChatGPT, Codex, native web search, GitHub connector/app, and upstream fallback.
- [x] Rewrite README and plugin metadata; remove legacy Playwright files.
- [x] Re-run targeted tests.

### Task 5: Full verification and GitHub integration

**Files:**
- Modify: `tests/selftest.sh` to invoke the two new unit suites without changing existing differential assertions.

**Interfaces:**
- Produces: feature branch, PR, squash merge to `main`.

- [x] Run new Python unit suites locally.
- [x] Run OpenAI package build and inspect archive members/hashes.
- [ ] Run repository-level verification on the committed branch / CI-equivalent materialization.
- [ ] Open a PR, inspect its file list and patch, and verify only intended files changed.
- [ ] Merge the PR to `main` and fetch `main` to confirm the merged commit is the current head.
