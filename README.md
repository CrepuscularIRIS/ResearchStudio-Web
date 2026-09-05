# research-harness 0.3 — the V8 pipeline

An unattended research loop for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) built on the native `Workflow` runtime. Three workflow files do all the thinking; one script (`dag.py`) decides what runs next and prints **one line per turn**. Main only ever executes that line.

```
research  →  Claim (statement · strategy · contract rows · premises · naive · falsifier)
experiment  plan → build → judge → plan …   (cheapest decision-changing test each cycle)
paper     →  draft from the evidence that exists
```

0.3 replaces everything in 0.1/0.2 (lanes, hooks, gate.py, stage/step/bundle, the six workflows). Nothing of those remains; git history has them.

## What each workflow is

**research** — *Speculative DeepResearch × ResearchStudio transformation priors.* Five phases, ~22 seats, no cascade gates:
- **Reframe** (t=0, no barrier): Opus (conceptual prior) ∥ K3 (adversarial prior) ∥ GLM ×3 foundation searches (baseline / closest / contrary). Reframe seats read exactly one file — the 15 ideation-pattern overview.
- **Routes**: Sol formalises every route (formal object · naive solution + branch · kill observation · runnable); `naive_suffices`/`runnable=false` is a formal kill. GLM planner emits decision-bound queries `{query, route_id, if_yes, if_no}`; a route changes state only with `evidence_ids` that exist in the pool — opinion never kills.
- **Digest**: GLM writes the bottleneck as a *failure, not an absent cure* + the negative-knowledge slice (Reject lessons quoted from the surviving pattern cards); lazy match against the 31 sub-patterns.
- **Factory**: GLM sketch swarm (smallest runnable mechanism) → mechanical prune → top-4 full Claims ∥ collision search (signature / alias / GitHub).
- **Verdict**: K3 prosecutes (CLEAR / CHALLENGE / SEARCH_REQUIRED — a challenge flags, never kills) ∥ Sol formal review (six HARD_KILL classes) → JS composes; Opus picks only on a true tie.

**experiment** — *Adaptive experimentation with failure-induced priors.* Three modes the dag cycles:
- **plan**: Sol ∥ K3 ∥ GLM each propose tests (MDE, kill_condition, cost, canary, dev-half only); JS hard floors; Opus picks the one that most changes what we believe.
- **build**: Sol compiles a B1-complete spec (steps down to functions; a method name is refused) → GLM implements in a worktree → one-pass Bash checks + review → one bounded fix round → Grok CLI review → canary launch via `launch_wrap.sh` (exit 3 canary · 4 early kill · 5 infra).
- **judge**: deterministic manifest → JS invalidity floors (NaN, test-half reads, missing seeds — *invalid ≠ refuted, Claim unchanged*) → GLM recompute ∥ integrity → analysis + conditional K3 → Grok audit → E with derived `claim_strength`.

**paper** — assemble (Claim + evidence → section plan, table skeleton) → draft (CCFA contracts in the prompt: evidence ladder, claim-action rules, one table one statement, number provenance) → lint → Grok audit.

**dag.py** — objects: `claims/C-*.json`, `experiments/X-*.json`, `paper/draft-*.md`. Commands: `next` (prints `WORKFLOW: <name> args=<file>` | `WAIT: <unit>` | `STOP: <why>`), `put <name> <out.json>` (validates the return against the lattice, prints `OK` | `RETRY` (infra, no cycle consumed; 3 in 2 h → `STOP: INFRA`) | `REJECT`), `board`. Cycle cap 8 per Claim; research redo cap 3.

## Model seats (one full pass)

|      | research | experiment (× cycles) | paper |
|------|----------|-----------------------|-------|
| Opus | 2 (reframe, tie-pick) | 1 (plan pick) | 0 |
| Sol  | 2 (routes, formal)    | 2 (falsifier, spec) | 0 |
| K3   | 2 (reframe, prosecute)| 1–2 (plan, conditional) | 0 |
| Grok CLI | 0 | 2 (review, audit) | 1 (audit) |
| GLM  | ~15–20 | ~8 / cycle | ~4 |

Model ids are constants at the top of each workflow (`MODEL = {...}`); change them there.

## Install

```
claude plugin marketplace add CrepuscularIRIS/research-harness
claude plugin install research-harness
/research-harness:init          # in the project root
```

`init` writes `.research/{dag.py,tools/,harness.json,GOAL.md,substrate.json}`, `.claude/workflows/*.workflow.js`, `.claude/skills/paper-search/`, `.claude/CLAUDE.md`, and the `Workflow(research|experiment|paper)` allow rules. Then:

1. Fill every field of `.research/GOAL.md` `## FROZEN` (objective, platform, measured facts, protocol, keep rule, budget, out of scope — **not** the claim; the research workflow produces that).
2. Put absolute paths and the canary number in `.research/substrate.json`.
3. In `.research/harness.json` set `exp_repo` (the git repo experiments are built in) and `rs_ref` (see *External dependencies*).
4. `python3 .research/dag.py next` → it prints `WORKFLOW: research …`. `/research-harness:research` runs one turn; `/goal "python3 .research/dag.py next prints STOP; …"` runs unattended.

## External dependencies (not vendored)

- **ResearchStudio `idea_spark` references** — the research workflow reads `ideation-patterns/overview.md`, the 31 sub-pattern cards, `companion-combos.md` and `anti-patterns.md` from `harness.json: rs_ref`. Clone ResearchStudio and point `rs_ref` at `…/ResearchStudio-Idea/skills/idea_spark/references`.
- **Grok CLI plugin** — `harness.json: grok_cli` (auto-detected under `~/.claude/plugins/cache/grok/` by `init`). Absent Grok is recorded as unavailable, never as a verdict.
- **paper-search skill** (vendored under `skills/`) needs its own API keys — see `skills/paper-search/SKILL.md`.
- **systemd --user** for launches (`launch_wrap.sh` writes the exit code to the ledger).

## Design documents

`docs/PIPELINE-V8.md` (why the rewrite), `PIPELINE-V8-PLAN.md` (object model, GATE primitive, budgets), `PIPELINE-V8-RESEARCH-V2.md` (the speculative-DR design that replaced the gate chain), `PIPELINE-V8-EXPERIMENT-PLAN.md` (ladder, K-gate/RR, ARFT/ARIS/CCFA sources), `PIPELINE-V8-PAPER-PLAN.md`.

## Tests

`node tests/mock_runtime_research.mjs` · `node tests/mock_runtime_experiment.mjs` — mock-runtime full-chain runs with schema-minimal fixtures (no model calls). `python3 -m py_compile scripts/dag.py`.

## Known issues (tracked for 0.3.1)

- `dag.py put` does not yet accept `spec_blocked` / `no_valid_tests` (REJECT); `canary_fail` / `early_kill` are treated as infra (RETRY) and can hit the 3-strike stop.
- `judge` reads the unit exit from `systemctl show`, which is empty once a transient unit has exited — it should read the `stop` event `launch_wrap.sh` writes.
- `build` proceeds when only floors (not findings) remain after the fix round (`&&` should be `||`).
- Budget (`kill_cap_gpu_h`, `total_gpu_h`) is read from FROZEN as JSON; FROZEN is markdown, so the defaults (4 / 100) apply. Put the numbers in `harness.json` in the next revision.

MIT.
