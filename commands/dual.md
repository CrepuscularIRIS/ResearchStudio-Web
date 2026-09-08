---
name: dual
description: Fire both tracks on one run root — the local workflow, then the web windows the moment a bottleneck exists
argument-hint: "<topic-slug>"
---

Run **both tracks** for the run named by `$ARGUMENTS`. This is the dual-track trigger; `/spark` and `/web` are the single-track escapes.

## 1. Pre-flight (fast, and it saves a wasted retrieval)

- Read `ideaspark_run/$ARGUMENTS/args.json`. If `direction` is still a placeholder, stop and ask for one sentence.
- Confirm this is a `claude-kimi` session. The seat table pins model ids that resolve only on the local LiteLLM route; on the official API they are silently served by the session model, which is neither the routing asked for nor cheap. If you cannot tell, say so rather than guessing.
- Report which connectors are live: `set -a; . "$(python3 -c 'import json;print(json.load(open("ideaspark_run/'"$ARGUMENTS"'/args.json")).get("env_file",""))')" 2>/dev/null; set +a; python3 "$(python3 -c 'import json;print(json.load(open("ideaspark_run/'"$ARGUMENTS"'/args.json"))["rs_home"])')/skills/idea_spark/scripts/run.py" check_connectors`. A missing connector is not a blocker, but say which one — Phase 0 loses that window silently otherwise.

## 2. Local track — launch it

Call the `Workflow` tool with `name: "ideaspark"` and `args` set to the contents of that `args.json`. It runs in the background and notifies you when it finishes.

What to expect, so nothing reads as broken: Phase 0 retrieval takes 3–10 minutes (openreview alone budgets 600 s); the whole advance path is 10–11 isolated seats and runs for hours; a run is resumable by relaunching on the same `root`, and **never** with `resumeFromRunId`.

## 3. Web track — dispatch on the bottleneck, not on the finish

The local run writes its diagnosis at Phase 1, long before any card exists. **That** is the moment to ask the web the same question — not when the workflow returns.

While the workflow runs, check on each wake-up:

```bash
python3 .research/web/web.py watch --root ideaspark_run/$ARGUMENTS
```

- `NO-BOTTLENECK-YET` → the run has not reached Phase 1. Do nothing.
- `NEW-BOTTLENECK` (exit 2) → seed with the command it prints, then use the `ideaspark-web` skill to open one `chatgpt.com` tab per prompt (at most five, staggered ~10 s), send, and record each send:
  `python3 .research/web/web.py mark --root ideaspark_run/$ARGUMENTS --id NN --sent --url "<conversation url>"`
- `ALREADY-DISPATCHED` → this same diagnosis was already asked about. Do not re-ask.

## 4. Patrol both

```bash
python3 .research/web/web.py patrol --root ideaspark_run/$ARGUMENTS
```

30-minute clock, overdue at 90 — a hosted answer takes 30–60 minutes and holding a window under continuous poll spends a session to learn nothing. Capture a due window per the skill's completion rule, then `mark --poll <len> [--done]`. `--done` only with the end marker actually present.

You cannot sleep for 30 minutes inside a turn. Do the checks that are due now, then either keep the loop alive with `/loop` (which paces itself), or tell the user plainly that the next patrol is due in N minutes and that `/patrol` picks it up from any session.

## 5. Report

Both tracks in one report: the local run's phase and terminal state (three cards / `do_not_generate.md` / `phase_3_failed.md`), and per web window the state, the conversation URL, and whether the capture is complete. When both tracks have produced cards, score them together — same `idea_quality` judge, blind to which track wrote which, and say where the two disagree.
