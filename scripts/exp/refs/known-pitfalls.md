---
source: .claude/workflows/experiment.workflow.js
sliced_from: .claude/workflows/experiment.workflow.js:111-121
const: KNOWN_PITFALLS
sha256_of_source_slice: ae812974641cf9f304290493325194ebb8c53cc5f1bc489a8c99558833df5afc
consumer: worker build/fix
checker: .research/tools/assets_check.py A3 (re-evaluates the JS constant with tools/js_consts.mjs)
placeholders: BUILD_DIR -> <BUILD_DIR> (per-X path; INSTR and PROMPTS_DOC resolved to their real paths)
extracted: 2026-09-06
---
KNOWN PITFALLS (each was a real blocked round — the numbered list with substrate figures
is in /home/lingxufeng/workspace/.research/instruments/README.md; the derivation rules that matter most):
- Never derive a ceiling from this run's own columns; cite the frozen oracle figures or a
  label-anchored oracle recomputed from the m78b cache.
- Sign: correlate WITHDRAWAL (1-rho) with |d_tilde-d|, positive coefficient.
- Never rebase the canary: measure the substrate's own protocol if the observable differs.
- All hosts on identical frames (the GF loader has its own order — map it onto the shared indices).
- Certificates gate on their full conjunction; a dropped leg is a blocked round.
- Shared trainers keep their defaults; your launcher passes its flags explicitly.
- run_cmd must NOT set SMOKE itself — launch_wrap does; a prefix overrides it (X-011's bug).