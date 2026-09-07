---
source: .claude/workflows/experiment.workflow.js
sliced_from: .claude/workflows/experiment.workflow.js:92-101
const: METHOD_COMPLETE
sha256_of_source_slice: ea33e001423d137f9d9665326887d8eadd451c9545c216a63a6df8cf214afef9
consumer: worker build/fix
checker: .research/tools/assets_check.py A3 (re-evaluates the JS constant with tools/js_consts.mjs)
placeholders: BUILD_DIR -> <BUILD_DIR> (per-X path; INSTR and PROMPTS_DOC resolved to their real paths)
extracted: 2026-09-06
---
METHOD-COMPLETE CONTRACT (you ground and implement a pre-registered design):
- Read /home/lingxufeng/workspace/.research/instruments/README.md (substrate facts: canary numbers, m78b guards, protected paths) and
  skim /home/lingxufeng/workspace/docs/prompt-bank/V8-EXPERIMENT-PROMPTS.md §1-§3 once. Copy the instrument library into your worktree; write ONLY the
  mechanism delta (gate head, loss, curriculum, generator) and a thin launcher parameterized
  NETWORK= and MODE={mve,full} — FULL will be a re-invocation, not a rewrite.
- Every formula, sign, threshold, column name and frame-index convention pinned in code with a
  one-line comment naming what it answers. The negative-control arm is part of the MVE.
- spec.verdict_rule is REQUIRED and references the m158 verdict.json keys verbatim
  (see instruments/README.md for the shape); the JS judge evaluates it as data.