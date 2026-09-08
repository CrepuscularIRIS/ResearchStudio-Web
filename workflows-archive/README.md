# workflows-archive

- `ideaspark.workflow.js` — the seat-per-step build (retired 2026-09-08). Superseded by
  `rs.workflow.js` (ONE persistent GLM driver + generation-side Opus mega-seat + fresh verifiers).
  Kept as the FALLBACK: if the driver ever cannot spawn nested seats, dispatch it explicitly —
  `Workflow(scriptPath: <this path>, args {root, direction, rs_home})`. Its BANK is verified
  20/20 byte-identical to the vendored ResearchStudio originals.
