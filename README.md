# research-harness

Microsoft ResearchStudio `idea_spark`, adapted for two supported host surfaces while keeping the
research-reasoning contracts intact:

- **Claude Code** — the existing isolated-seat workflow remains the phase executor. `/spark` now uses a
  native-retrieval host adapter: Claude WebSearch/WebFetch and an available GitHub MCP/connector handle
  Phase 0 and Phase 3.1; every other phase still runs in the original fresh workflow seat. Set
  `retrieval_mode=upstream` to reproduce the old Python-connector path.
- **OpenAI (ChatGPT + Codex)** — `openai/idea-spark/` is the shared Skill source. It routes repository
  evidence to the GitHub connector/app, scholarly evidence to native web search, user materials to Files,
  and reserves Python for deterministic state/merge/validation/rendering work.

A research direction goes in; one reviewer-defensible, implementable idea card comes out (or the same
ResearchStudio terminal failure states).

## Prompt and runtime guarantees

The vendored upstream lives at `vendor/researchstudio/` and is the source of truth. The eleven
ResearchStudio system prompts are never rewritten. The OpenAI package builder verifies byte identity
against the vendor before it will produce an archive, and overlays the exact vendored C00-C30
sub-pattern cards into the upload so the final Skill is self-contained.

Claude Code retains the strongest isolation guarantee in this repository: each reasoning phase is an
independent workflow seat with fresh context. The native host adapter only intercepts retrieval-heavy
steps and drives the already-tested workflow one step at a time (`max_steps=1`), so the existing phase
graph and deterministic gates are unchanged.

ChatGPT/Codex keep prompt parity and phase-input discipline, but ChatGPT Web does not guarantee
process-level fresh-context isolation. Do not describe the OpenAI path as runtime-identical to the Claude
workflow. It is a prompt-preserving, native-tool host port.

## Claude Code

Initialize and run as before:

```text
/research-harness:init  <slug> "<one sentence: the research direction>"
/research-harness:spark <slug>
```

`/spark` reads `ideaspark_run/<slug>/args.json`. With no `retrieval_mode`, native mode is used.

Native mode follows this host loop:

1. Run vendored `scripts/run.py next` read-only.
2. If the next state is fresh Phase 0, use native WebSearch/WebFetch plus GitHub MCP/connector when a
   repository/system is under study, then materialize the canonical Phase 0 artifacts.
3. If the next state is Phase 3.1 collision, run the signature/alias scholarly search natively and write
   the canonical collision artifacts.
4. Otherwise invoke the existing `ideaspark` workflow with `max_steps=1` so the reasoning step happens in
   its normal fresh isolated seat.
5. Repeat until terminal.

To force the historical connector behavior, put this in the run `args.json`:

```json
{"retrieval_mode": "upstream"}
```

The Claude adapter is documented in `skills/ideaspark-native/SKILL.md`. It treats GitHub repositories as
systems under study, not as generic code-review targets. Repo code/issues/PRs/commits can establish
implementation facts and bottlenecks; scholarly novelty is still decided from literature.

## ChatGPT + Codex Skill

The source is `openai/idea-spark/`. Its routing priority is:

1. GitHub connector/app for repository metadata, code, issues, PRs, commits, and system-under-study facts.
2. Native web search for papers, venue pages, publisher pages, documentation, and collision retrieval.
3. Files for user-supplied papers, notes, PDFs, and project material.
4. Python only for deterministic state inspection, JSON merge/patch, validation, assembly, and rendering.

Remote-retrieval commands in the upstream runbook are interpreted as capability requests on OpenAI hosts;
`phase0`, full-text/top-up resolution, and `phase3_collision` are fulfilled with native tools rather than
`scripts/search_*.py`.

Build the installable archive from the repository root:

```bash
python3 scripts/openai/build_skill.py
```

Output:

```text
dist/openai/skill.zip
```

Upload that `skill.zip` to ChatGPT Skills, or unpack/install the same Skill for Codex. The builder refuses
prompt drift, rejects `.env`/cache files, and replaces any compact C00-C30 source pointers with the exact
vendored ResearchStudio cards before zipping.

## Repository layout

```text
workflows/ideaspark.workflow.js     existing Claude isolated-seat phase executor (unchanged)
scripts/ideaspark_src/              existing workflow source/generator (unchanged)
skills/ideaspark-native/            Claude native-retrieval host adapter
commands/spark.md                   Claude host loop entrypoint
openai/idea-spark/                  ChatGPT/Codex Skill source
scripts/openai/build_skill.py       build + integrity-check dist/openai/skill.zip
vendor/researchstudio/              pinned upstream IdeaSpark + idea_quality, unmodified
tests/                              original differential suite + native/OpenAI adapter contracts
```

The former Playwright path that drove `chatgpt.com` from Claude Code is removed. ChatGPT is now a direct
OpenAI Skill surface rather than a browser-automation target.

## Existing ResearchStudio guarantees

The original workflow still carries the mandatory full-text gate, citation gate, Phase 2.3 executed
coherence trace, blocking-evidence disposition guard, information-gain retry ladder, falsification
re-audit, Phase 4 implementability audit, and final validators. The existing differential suite remains
the guard that the Claude workflow phase graph agrees with the vendored ResearchStudio navigator.

## Tests

Run the repository test suite:

```bash
tests/selftest.sh
```

The native/OpenAI contract tests can also be run directly:

```bash
python3 -m unittest -v tests/test_native_host_adapter.py tests/test_openai_skill.py
```

## Licence

This plugin: MIT. `vendor/researchstudio/` is the pinned, unmodified Microsoft ResearchStudio material
redistributed under its upstream MIT licence; see `vendor/researchstudio/PROVENANCE.md`.
