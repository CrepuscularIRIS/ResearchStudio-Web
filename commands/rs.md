---
name: rs
description: One command, the whole two-track research pipeline — local IdeaSpark workflow (GLM main + Opus5 seats, ends at the cards), the web lite track (Phase-1 gaps + 2.2 bottleneck-evidence windows, patrol, canvas capture), consolidation, and the three-judge idea-quality finish. Fire and patrol; everything derives from disk and resumes.
argument-hint: "<research direction — or an existing topic-slug to resume> [--n-web 5]"
---

## What this is

`/rs` runs BOTH tracks on one direction and finishes with one judged ranking. You (this session)
are the **main agent**: you dispatch the local workflow, drive the browser windows on the patrol
clock, consolidate at the end, and fire the judges. You never reason inside a track — every seat
is an isolated agent; every artifact lives on disk.

    /rs <direction>
      ├─ local track   Workflow(ideaspark.workflow.js)  → GLM main + serial Opus5 → idea cards (NO scoring inside)
      ├─ web track     web.py watch → seed → chatgpt.com windows → patrol/capture (canvas = the card)
      └─ finish        consolidate all cards → Workflow(webjudge.workflow.js, {cards}) → Opus5∥Sol∥K3 ranking

## Phase A — pre-flight (once)

1. Zone guard: `test -d ideaspark_run || { echo "not a dual-track zone"; exit 1; }` — this command
   runs inside a zone (`~/ccf`, `~/icml`, `~/imcl`, `~/linxiao`). Never touch another zone's runs.
2. `RUN_ROOT=$PWD/ideaspark_run/<slug>` — slug = short kebab of the direction. If the dir exists
   this is a RESUME: skip to Phase C, everything re-derives from disk.
3. Dispatch the local track — Workflow tool, `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/rs.workflow.js`,
   args `{root: RUN_ROOT, direction: "<the direction>", rs_home: /home/lingxufeng/.claude/plugins/marketplaces/research-harness/vendor/researchstudio}`.
   This is ONE persistent GLM main agent that walks the navigator loop to the end (the RS-native
   host shape), spawning every phase as an Opus5 subagent and the mechanical steps as GLM seats.
   FALLBACK: if the driver reports it cannot spawn nested seats, re-dispatch on
   `.claude/workflows/ideaspark.workflow.js` with the same args (the seat-per-step build).
   Then keep working; the completion notification finds you.

## Phase C — the web track (runs UNDER the local track)

The local chain's longest serial stretch (2.3 → 3.1 → 3.2) is 30–50 min; hosted answers take
30–60 min. Send early, never wait.

Every ~30 minutes (and on each workflow notification) run BOTH:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/web/web.py watch  --root RUN_ROOT     # exit 2 = something to send
python3 ${CLAUDE_PLUGIN_ROOT}/web/web.py patrol --root RUN_ROOT     # exit 2 = a window is due/overdue
```

- `NEW-BOTTLENECK` → `web.py seed --root RUN_ROOT --from-run --n <min(5, gaps)>`. One window per
  unaddressed gap, IdeaSpark trigger format.
- `NEW-CANDIDATE` (the 2.2 dispatch, the valuable one) → `web.py seed --root RUN_ROOT
  --from-candidate --n 5`. ONE WINDOW PER ITEM: the diagnosed structural bottleneck, then each
  open gap — each with stakes, the residue map, and a six-section detailed card demanded
  (diagnosis / evidence for / evidence against / binding constraint / attack sketch / verdict).
  Plain prompts, `<<END OF IDEA REVIEW>>` marker.
- Read every prompt file before sending — you are responsible for what goes into the account.
- Send: `browser_tabs` one `chatgpt.com` window per prompt (≤5, staggered ~10 s), `browser_type`
  with `submit: true`, CONFIRM the user turn, then `web.py mark --id NN --sent --url <url>`.
- Patrol due windows: one `browser_evaluate` capture per the ideaspark-web skill's protocol;
  **if the answer opened a Canvas, the canvas document IS the card** — capture its text, verify
  the marker in it, save as `web/answers/NN.md` (gap batch) or `web/candidate_answers/NN.md`
  (candidate batch). Then `web.py collect --root RUN_ROOT` and `web.py collect --root RUN_ROOT --candidate`.
- A window OVERDUE (90 min) or stopped-early: screenshot, report, re-send once in a fresh window.
- Follow the `ideaspark-web` skill's seven browser rules — they exist because each was violated once.

## Phase D — the finish line (both tracks done)

1. Done means: the local workflow returned (cards, or `do_not_generate` / `phase_3_failed` —
   surface those verbatim and stop), AND every dispatched window is complete or formally overdue.
2. Consolidate — you do this, no agent: list the local `RUN_ROOT/phase4/idea.std.*.md` (or
   `RUN_ROOT/<run>/phase4/...` for k>1) plus every `web/candidate_answers/*.md`. Write the list to
   `RUN_ROOT/web/review_set.json`.
3. Judges — Workflow tool, `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/webjudge.workflow.js`,
   args `{cards: [<the consolidated absolute paths>]}`. Opus5 ∥ Sol ∥ K3 (the only parallel step
   anywhere): every card gets A novelty&depth / B validity / C significance (1–5), overall,
   verdict; plus the ranking of which line of attack is most worth a method paper.
4. Report: the ranking table with per-card medians, the top card's one-line case, where every
   artifact lives, and any window that never completed. Do not editorialize the judges.

## Discipline

- Never hold the local track waiting on a window; never run a phase's reasoning yourself.
- One question per window, one conversation per window; patrol on the 30-minute clock only.
- Resume = re-invoke `/rs` with the same slug — `watch`/`patrol` fingerprints make re-sends
  idempotent and the workflow resumes from disk.
- Granular commands (`rs-spark`, `rs-web`, `rs-patrol`, `rs-dual`) remain for manual recovery;
  `/rs` is the single front door.
