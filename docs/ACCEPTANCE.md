# Acceptance test — run in the campaign session before any real GPU spend

Start the campaign session from the workspace:

```bash
cd  && cd <project> && CLAUDE_CONFIG_DIR=<your-campaign-config-dir> claude
```

The session-start hook must print nothing about READ-ONLY. If it does, another session holds `.research/LOCK`; close it first.

## 1. Identity and METHOD probe (five dispatches, one message)

Dispatch each lane once with a brief that says only `MODE: PROBE — read your REQUIRED READING, write a two-line report to .research/reports/probe-<lane>.md whose first line is METHOD:, and return the status line`. Then:

```bash
ls .research/IDENTITY-MISMATCH 2>/dev/null && echo "FAIL identity" || echo "identity ok"
grep -l "^METHOD:" .research/reports/probe-*.md | wc -l      # expect 5
```

Any mismatch stops the campaign until `~/.claude-research/settings.json` is fixed. The reviewer probe must show that `codex-companion.mjs task --prompt-file` returned JSON.

## 2. Lock

Open a second `claude` in the same config dir and workspace while the first is alive. Expected in the second session's start output: `READ-ONLY SESSION`. From the second session:

```bash
bin/run_protected.sh x C-REAL 1G true      # expect: REFUSED: another session ... holds .research/LOCK
```

## 3. Known-real card

Dispatch `scientist` MODE=CARDS with a brief whose bridge is the canary itself: claim "the frozen DFormerv2-S checkpoint reproduces entire_missing mIoU 49.95 on NYU", `prediction.band=[49.5, 50.4]`, `kill.threshold=48.0`, `n_required=3` (three evaluation seeds), `tier=T1`, `cost_gpu_h=0.3`, oracle = the same evaluation on ten frames. Run C → O → B → V by the CLAUDE.md table; the builder emits `results/C-REAL/seed_<k>.json`.

Expected: `gate.py verdict` prints `SUPPORTED`; `verdicts/C-REAL.json` has `type_b.reviewer` starting `codex:`; `ledger.jsonl` has a start and a stop line for the run; `views/RESULTS.md` lists it.

## 4. Known-null card

Same flow with a shuffled-corruption control: claim "a permuted corruption arm raises held-out wrong-depth mIoU by ≥ 1.5", `kill.threshold=0.3`. Check `packets/C-NULL.md` contains only the role prompt, card, record, and paths, and never says the arm is a control.

Expected: `gate.py verdict` prints `REFUTED` (kill hit) or the node is pruned at O; the Reviewer output does not reference any expectation of failure.

## 5. One bridge cycle

Run phase R once: `explorer` BRIDGES, then `researcher` ×N in one message.

Expected: `bridges/<cycle>.md` has 3 to 5 entries each with a non-empty `disanalogy_that_could_break_it` and a `pattern` from the 15; `lit/<cycle>-<n>.md` exists for every entry; `LIT-LEDGER.md` grew by at least one row per packet.

## 6. Record the outcome

```bash
python3 .research/gate.py views && git add .research/tests/acceptance && git commit -q -m "test: acceptance outcome" && echo ACCEPTED
```

Only after `ACCEPTED` may a real card be launched. Write the date and any deviations below.

## Owed at step 3 (first GPU use)

- `scripts/arbor_eval.py` (or your own eval adapter) has only been parser-tested; step 3 is its first real run. If `eval_robust_suite.py` refuses the checkpoint path or the JSON layout differs, fix the adapter before any card and note it here.
- The dev metric condition defaults to `gaussian` (env `ARBOR_EVAL_CONDITION`); the first card's Scientist must confirm the wrong-depth condition the campaign scores, and GOAL.md's `metric` line must match.

## Outcome log

- (pending)
