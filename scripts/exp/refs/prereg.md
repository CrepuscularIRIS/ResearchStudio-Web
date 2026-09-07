---
source: .claude/workflows/experiment.workflow.js
sliced_from: .claude/workflows/experiment.workflow.js:81-90
const: PREREG
sha256_of_source_slice: 21d427dedba90e35503c3760e18daa4e8bba6fc0e602d48ffa5c8472c881d67f
consumer: worker build/fix
checker: .research/tools/assets_check.py A3 (re-evaluates the JS constant with tools/js_consts.mjs)
placeholders: BUILD_DIR -> <BUILD_DIR> (per-X path; INSTR and PROMPTS_DOC resolved to their real paths)
extracted: 2026-09-06
---
PRE-REGISTRATION: the candidate carries mve_design (arms, verdict_rule as keep_if_all over m158
keys, negctl_arm, kill_condition, budget) — designed at research time with full claim context.
You GROUND it in the repo (exact flags, paths, wiring) and IMPLEMENT it. If repo reality conflicts
with the pre-registered design you may adjust, but every adjustment must appear in spec.deviation_notes
with the reason — silent redesign is the blocked-round pattern. spec.verdict_rule defaults to the
candidate's; change it only with a deviation note.
DUAL-READING (F20): an operative term in mve_design admitting more than one defensible reading
('unchanged', 'similar', 'stable', 'same curriculum') is itself a finding — pin WHICH reading the
spec implements, in deviation_notes; never silently pick one.
