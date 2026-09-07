---
source: .claude/workflows/experiment.workflow.js
sliced_from: .claude/workflows/experiment.workflow.js:68-79
const: SELF_CHECK
sha256_of_source_slice: e6ffabe963255fb239f221114c39f7cc8f716de9bd95f2fd1e62822a872633f0
consumer: worker build (self_check[] in build.json)
checker: .research/tools/assets_check.py A3 (re-evaluates the JS constant with tools/js_consts.mjs)
placeholders: BUILD_DIR -> <BUILD_DIR> (per-X path; INSTR and PROMPTS_DOC resolved to their real paths)
extracted: 2026-09-06
---
SELF-CHECK before you return gate_passed (you are the reviewer now — run these, report the grep counts):
1. Fake GT: `grep -nE 'reference|baseline.*output|pseudo' <your eval files>` — no ground truth may be
   derived from model outputs; dataset GT / official scripts only.
2. Score normalization: no metric divided by this run's own max/min; raw values reported alongside.
3. Phantom results: every number the verdict writes must come from a file this run's code wrote;
   `grep -n 'def ' <metric files>` — every metric function is actually called.
4. Scope: smoke artifacts live ONLY under smoke/ stamped NOT_A_RESULT; no '[] done' on a truncated run.
5. eval_entry: `grep -c '^+++ .*m152_eval_rungs.py' <BUILD_DIR>/diff.patch` must be 0.
6. No test-half tokens (cal_test / test_half literals) in the diff.
7. GT-path leak (ASI): `grep -rnE '(\.\./)+(labels?|gt|ground_truth)|def .*ground_truth|hard.?cod' <your eval/dataset .py files>` —
   ground truth comes ONLY from the official dataset path; escaping the task dir or recomputing GT is the leak.