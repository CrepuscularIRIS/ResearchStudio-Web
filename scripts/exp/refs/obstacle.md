---
source: .claude/workflows/experiment.workflow.js
sliced_from: .claude/workflows/experiment.workflow.js:103-109
const: OBSTACLE_RULE
sha256_of_source_slice: 2e1aa1400676740562ec4f29650dbdddb167162f52501e991e4b8e8b9c713be3
consumer: worker fix
checker: .research/tools/assets_check.py A3 (re-evaluates the JS constant with tools/js_consts.mjs)
placeholders: BUILD_DIR -> <BUILD_DIR> (per-X path; INSTR and PROMPTS_DOC resolved to their real paths)
extracted: 2026-09-06
---
OBSTACLE RULES (RS F30/F48):
- An avoidance patch (abstain on the affected cells, clamp the affected range, skip the affected regime)
  that sidesteps the obstacle the candidate exists to confront is ABANDON, not fix — name it as a blocker
  instead of shipping it.
- If the previous attempt failed to confront a named obstacle X, then X becomes a REQUIREMENT for the next
  attempt: the new mechanism must solve X head-on; record that obligation explicitly.