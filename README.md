# research-harness 0.2 — the claim loop

An unattended research loop for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview), in the shape of paperjury and the built-in workflows: six small **workflow files** do the semantic fan-out (inputs inline, schema outputs, no filesystem), and **scripts run between them** — a read-only navigator (`stage.py`), five idempotent actions (`step.py`), content-checking gates (`gate.py`), a record renderer, and a GPU launcher that writes the ledger. Main only ever executes the one line the navigator prints.

## What is different from 0.1

- **One claim, fixed by the owner** (`CLAIM.md` + `stage.py accept`). Every gate refuses while its sha differs.
- **Ideas come from a mechanism map, not from a lane's free text** (Sparking): Fable turns the claim and the project's *measured* anomalies into failure modes and three-level abstract mechanisms; K3 diverges into source domains with an isomorphism sentence and a disanalogy; Grok retrieves each recipe as a procedure with a quoted line and checks for precedent. Sources without a procedure or with a precedent are dropped by script.
- **Specs are B1**: every step names an existing file and what changes there; a method name is refused (ASI-Bench: a half-specified method costs 59% more tokens and scores 21.8 points lower than a full procedure).
- **The builder never judges itself**: the launcher runs a SMOKE phase (canary), then a watchdog kills a run whose dev gain is below the early-stop line at 25% / 50% of the schedule (exit 4 = recorded early kill) or that stalls (exit 5). ARFT: 82.5% of trajectories find their fatal flaw in self-review and ship anyway.
- **Verification the agent does not control**: Grok's coverage and findings must quote diff lines that exist in the real diff; Codex reviews the same diff; a token binds approval to the diff's sha; records come from result files inside the unit's window.
- **Cut losses by rule**: same source twice without a new best → source exhausted; every source exhausted → stop and pivot. Generalise only after one model keeps (3 seeds, CI95 above 0), one rung at a time.
- **Four lanes plus Codex**: Fable (abstraction, specs), K3 (divergence, pivot), Grok (retrieval, monitor, final review), GLM (Main, builder, writer), Codex (pre-launch review only).

## Install

```
claude plugin marketplace add CrepuscularIRIS/research-harness
claude plugin install research-harness
/research-harness:init       # in the project root
```

Then edit `GOAL.md` (campaign block + FROZEN), `.research/anomalies.md` (your measured findings), pin the lane models in `.claude/agents/*.md`, and run `python3 .research/stage.py`.

## The loop

```
A  frame      Fable writes CLAIM.md → owner accepts
M  mechanism  Fable (B, M) → K3 (C) → Grok (recipe, precedent) → mechanism-map.json
C  loop       per chain: propose → propose --finish → build → build --finish → record   (5 Main actions)
              unit: SMOKE → train under the watchdog → seed files; record gate; hill-climb on the map; band hit → confirm seeds
              after one KEEP: the support ladder (other networks, datasets, ablation), one rung at a time
P  pivot      K3 once → owner picks an exit
D  write      writer per section → Fable polish → Grok review → gate.py numbers (every number cites a record)
```

Docs: `docs/SPEC.md` (the design), `docs/ARCHITECTURE.md` (who decides what, step by step), `docs/REVIEW-2026-09-03.md` (the source review behind it), `docs/ACCEPTANCE.md`.

## Sources this shape comes from

paperjury (workflows + orchestrator-side scripts, isolation by not giving, quotes verified by script, idempotent retry), Claude Code's built-in deep-research and code-review (three-state votes, null is not a refutation, no silent caps), AAR (submit-model contract, monitor reads the code, frozen mini-paper, decoupled GPU jobs, one method per iteration), ResearchStudio (read-only navigator, execute-don't-review gate, kill-switch fields, naive baseline), ASI-Bench, "How Do AutoResearch Agents Fail" (ARFT), and the strategy-gene paper (one control object per context, failure warnings standalone).

MIT.
