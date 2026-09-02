# Research workflow v6 — design spec (five models, dispatcher main, trimmed skills)

**Date:** 2026-09-02 · **Status:** draft v4 for user review · **Replaces:** the CCF-sprint workflow backed up at `.claude.backup0902` and drafts v1–v3.

## 1. Purpose

One persistent GLM 5.3 session in Claude Code dispatches the loop from a single goal file: research → card → oracle → build and run → verdict → iterate. Main organises and passes data; it does not reason about the science. Five models each do one job. Every capability is an existing skill in `.claude/skills/`, read by the agent that uses it before it starts. The custom layer is two scripts, three hooks, five agent files, five brief templates, one CLAUDE.md.

Research stance: a paper is a bridge between knowledge in domain A and domain B that nobody has connected. Phase R is built to find those bridges, not to deepen one domain.

Target: benchmark improvement and a publishable method on the objective in `GOAL.md`, at CCF-A level.

## 2. What the evidence says the harness must do

| Finding | Source | Mechanism |
|---|---|---|
| R1 Grounding, 31% of failures: report and run directory disagree; the comparison is never performed | AutoResearchEval §5.2 | records rendered from result files by a script; claims checked against records (§5, §7.1) |
| R2 Depth, 27.6%: agent finds a fatal flaw and ships anyway (82.5%); frame-lock in one hypothesis space is a model limit, fixable only by a second hypothesis in the trajectory | AutoResearchEval §5.2 | structured `blockers` the gate refuses to pass; Explorer on a second model family generates bridges (§4, §6) |
| R3 Integrity, 33.5%: metric substitution, circular validation, concealed negatives; needs verification the agent does not control | AutoResearchEval §5.2 | kill criterion fixed before the run; blind Codex verdict; held-out merge guard; every run in the ledger (§7.2, §5.1) |
| R4 Engineering only 7.9% | AutoResearchEval §5.1 | no execution framework beyond the systemd launcher |
| GLM-5.3 in Claude Code 41.65, above K3 37.09 and Opus 4.8 37.51 | ASI-Bench §3.1 | GLM is Main and Builder |
| Codex + GPT-5.6 xhigh: best cost-to-score reviewer | ASI-Bench §3.2 | Codex plugin is the Reviewer, invoked only in the experimental phases |
| Old gates checked form not content; enforcement saw under 30% of compute; fable alias silently ran as Opus; agent outputs went unused | post-mortem | launcher writes the ledger and refuses unfrozen cards; single-writer lock; identity probe; every output is a file a later phase requires (§7.3, §6) |
| Bare Claude Code beat every multi-agent scaffold; roles pay only where they create an information barrier | landscape survey | each lane justified by one barrier (§4) |

## 3. Principles

1. **Main dispatches; it does not reason.** Scripts, tree writes, briefs, status lines. Paths travel between agents, never content.
2. **Five models, one job each.** Coding: GLM. Science: Fable, sparingly. Divergence and bridges: K3. Retrieval: Grok. Verdicts: Codex, experimental phases only.
3. **Content gates are scripts; judgment gates are blind and outside the ecosystem.**
4. **Machines write the record and the ledger.**
5. **Every agent reads its skills first and says so.** A report without the `METHOD:` line is discarded.
6. **Only official or high-quality third-party skills, and only the parts we use.** §14 is the triage; nothing outside it is loaded.

## 4. Lanes

| Lane | Model (proxy id) | Harness | Barrier | Job | Never |
|---|---|---|---|---|---|
| **Main** | GLM 5.3 (`glm-5.3[1m]`), persistent | Claude Code | the owner | dispatch by the phase table; run `gate.py` and the launcher; Arbor writes; select one card when the Scientist offers several | reasoning about the science; summarising reports; typing numbers; launching outside the launcher |
| **Builder** | GLM 5.3, fresh per build | subagent | keeps Main small | implement from the card in an Arbor worktree, smoke → small → full; fix rounds continue the same instance | design; launches; state writes |
| **Scientist** | Fable 5.1 (`claude-fable-5-1`), fresh, ≤ N per cycle | subagent | strongest reasoner, quota-limited | judge bridges at mechanism level; write cards with mechanism, forbids, oracle design; diagnose out-of-band results | state writes; implementation; retrieval |
| **Explorer** | Kimi K3 (`k3-256k`), fresh | subagent | second family against frame-lock | 3 to 5 (A, B) bridges per cycle with keywords for both domains; advisory critique of cards; advisory findings on merge candidates | ranking cards; blocking anything; state writes |
| **Researcher** | Grok 4.6 (`grok-4.6`), fresh, parallel | subagent | context isolation for bulk retrieval | one packet per bridge: `paper-search` over both domains, `scoop-check` on the bridge claim, `corpus.py`, arXiv and repo fetch; dedup against tree, records, lit ledger | ranking; designing; state writes |
| **Reviewer** | GPT-5.6 via the Codex plugin | `codex-companion.mjs` through a thin subagent | out-of-ecosystem, blind | pre-launch `review` of the worktree diff; blind result verdict via read-only `task` on the packet; one `adversarial-review` before submission | Main's transcript, summaries, prior rounds; anything outside phases B, V, and pre-submission |

### 4.1 Routing

Campaign config dir `~/.claude-research`, cloned from `~/.claude-kimi`:

```
ANTHROPIC_BASE_URL=http://127.0.0.1:4001/
ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5.3[1m]
ANTHROPIC_DEFAULT_FABLE_MODEL=claude-fable-5-1
ANTHROPIC_DEFAULT_SONNET_MODEL=k3-256k
ANTHROPIC_DEFAULT_HAIKU_MODEL=grok-4.6
CLAUDE_CODE_SUBAGENT_MODEL=inherit
CODEX_REVIEW_GATE_GLOBAL=false      # the plugin's stop-time review gate would spend Codex on every turn
model=opus
```

Agent files pin the full proxy id in `model:`. A `SubagentStop` hook reads the transcript's first `"model"` field and compares it with the agent file; on mismatch it writes `.research/IDENTITY-MISMATCH` and exits 2, and Main discards that report. Codex: the installed `codex@openai-codex` plugin 1.0.6 supplies the runtime; `codex` 0.152.1 is logged in; `~/.codex/config.toml` pins `gpt-5.6-sol`.

Reviewer invocations, all through the plugin's script:

```
node "$CODEX_PLUGIN/scripts/codex-companion.mjs" review --wait --scope working-tree           # phase B, diff
node "$CODEX_PLUGIN/scripts/codex-companion.mjs" task --wait --effort xhigh < .research/packets/<id>.md   # phase V, read-only, no --write
node "$CODEX_PLUGIN/scripts/codex-companion.mjs" adversarial-review --wait "<packet path>"    # once, pre-submission
```

### 4.2 Skills each agent reads first

| Lane | Required reading (absolute paths under `.claude/skills/`) | Tools |
|---|---|---|
| Main | CLAUDE.md; `arbor-agent-merge-eval/SKILL.md` before any merge | Bash, Read, Agent, Monitor, `mcp__arbor__*` |
| Builder | `experiment-bridge/SKILL.md` (with `CODE_REVIEW=false`; the plugin reviews instead); `experiment-queue/SKILL.md` only for grids of ten or more jobs | Bash, Edit, Read, Write inside its worktree |
| Scientist | `statistical-power/SKILL.md` when sizing n and MDE; `ablation-planner/SKILL.md` at card time | Read, read-only Bash |
| Explorer | `idea-spark/references/ideation-patterns/overview.md`, `idea-spark/references/anti-patterns.md` | Read |
| Researcher | `paper-search/SKILL.md`, `scoop-check/SKILL.md` | Bash for search scripts and git clone, Read, Write to `.research/lit/` only |
| Reviewer | `shared-references/reviewer-independence.md`, `shared-references/acceptance-gate.md` | Bash to run the plugin script, Read of the packet |

Subagents carry `disallowedTools: mcp__arbor__*`. Hypotheses never enter CLAUDE.md or rules, because those load into every subagent.

### 4.3 The dispatch contract

Every dispatch prompt is at most fifteen lines: lane, brief path, REQUIRED READING paths, input artifact paths, output path, status contract. Exact values live in the brief file. Every report is a file; the agent's final message is one status line, `DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED`, plus the report path. Main reads the status line and passes the path on. Main never pastes history, never summarises a report into the next brief, never rewrites an agent's artifact.

## 5. State

### 5.1 Arbor holds the tree

`arbor mcp` registered in the campaign config; one run rooted at `ugra-rgbd-robust/` (git, trunk branch `research-trunk`). Metadata from GOAL.md: `eval_cmd` (dev), `eval_cmd_test` (held-out: real Kinect, SUN RGB-D), `metric_direction`, `baseline_score`, `test_baseline_score`, `trunk_branch`, `protected_paths` (evaluation code, dataset configs, metric implementation).

| Card | Arbor node |
|---|---|
| id + one-line claim + frozen sha | `hypothesis` |
| lifecycle | `status`: pending → running → done or pruned → merged |
| dev metric | `score` |
| record path | `result` |
| verdict one-liner and lesson | `insight` |
| worktree branch | `code_ref` |

Merges go only through `git_merge_branch` with `test_score` from the held-out record and `protected_paths` enforced.

### 5.2 Files under `.research/`

```
briefs/<lane>-<id>.md    one per dispatch, from the lane's template; exact values live here
bridges/<cycle>.md       Explorer output: (A, B) bridges with keywords, analogy, disanalogy, pattern
lit/<bridge>.md          Researcher packets; LIT-LEDGER.md appended with every query verbatim
cards/<id>.json          written by the Scientist, frozen by gate.py (sha in the node)
records/<run>.json,.md   rendered by render_record.py from result files; never hand-edited
packets/<id>.md          built by gate.py packet; the only thing the Reviewer sees
verdicts/<id>.json       Reviewer JSON + gate.py Type-A output + computed state
reports/<lane>-<id>.md   every agent report
ledger.jsonl             appended by run_protected.sh at start and stop
LOCK                     single-writer lock: session id + pid
views/                   HYPOTHESES.md, RESULTS.md, DECISIONS.md, BUDGET.md rendered by gate.py views
```

Paper side keeps CCFA's contracts: `ccfa.yaml`, `manuscript/*.tex`, `ccfa-review-reports/`.

### 5.3 Schemas

**Bridge** (one entry in `bridges/<cycle>.md`): `domain_a`, `domain_b`, `what_b_knows_that_a_has_not_used`, `mechanism_analogy`, `disanalogy_that_could_break_it`, `pattern` (one of the 15 idea-spark patterns), `keywords_a[]`, `keywords_b[]`.

**Card:**

```json
{
  "id": "C-0007", "bridge": "bridges/2026-09-03.md#3",
  "claim": "Training against smooth-wrong depth raises held-out wrong-depth mIoU without lowering clean mIoU",
  "mechanism": "...", "forbids": "what must NOT be observed if the mechanism is right",
  "prediction": {"metric": "mIoU_nyu_heldout_wrong", "band": [0.8, 2.0], "direction": "maximize"},
  "kill": {"metric": "mIoU_nyu_heldout_wrong", "threshold": 0.3, "rule": "mean over n_required seeds below threshold"},
  "controls": ["absent-depth arm, same schedule and aug budget", "shuffled-corruption arm"],
  "seed_sd": 0.564, "n_required": 3, "mde": 1.71,
  "instrument": {"checkpoint": "...", "reference_number": 54.93, "canary": "entire_missing reproduces 49.95 ± 0.10"},
  "oracle": {"design": "feed the ground-truth corruption mask; downstream must move", "cost_gpu_h": 0.5, "pass": "delta > oracle_mde"},
  "tier": "T4", "cost_gpu_h": 31, "frozen_sha": null, "arbor_node": null
}
```

**Record:** `run`, `card`, `seeds`, `per_seed`, `mean`, `ci95`, `n_realized`, `canary {expected, observed, pass}`, `checkpoint_loaded_frac`, `band_hit`, `kill_hit`, `cost_gpu_h` (from ledger), `artifacts [{path, sha256}]`, `blockers []` (the Builder's own self-review, structured), `rendered_by`.

**Verdict:** `type_a {pass, checks}`, `type_b {reviewer, verdict, criterion_met, blocking []}`, `state`.

State rule, computed by script: `REFUTED` if `kill_hit`; `SUPPORTED` only if `type_a.pass`, `type_b.verdict == SUPPORTED`, and `blockers` and `blocking` are both empty; otherwise `CONTESTED`. Reasoning demotes; only a record refutes. Disagreement becomes `CONTESTED` plus the next cheapest discriminating test; the loop never blocks on the user.

## 6. The loop

| Phase | Main dispatches | Reads | Produces | Gate |
|---|---|---|---|---|
| **R Research** | Explorer once: 3 to 5 (A, B) bridges; then Researcher ×N in parallel, one per bridge, searching both domains | GOAL, tree constraints view, previous records | `bridges/<cycle>.md`; one `lit/` packet per bridge with dedup and scoop verdicts | every bridge has a packet |
| **C Card** | Scientist judges the bridges at mechanism level and writes one to three cards; Main runs `gate.py card`; Explorer appends advisory critique; Main selects one and adds the node | bridges, packets, records | one frozen-ready card, node `pending` | `gate.py card` passes |
| **O Oracle** | Builder implements the oracle probe in a worktree, T0–T3, at most 1 GPU-h; Main launches | card | oracle record | signal above oracle MDE, else `tree_prune` with reason |
| **B Build and run** | Builder implements smoke → small → full; Reviewer `review` on the diff; Main freezes and launches; Monitor; meanwhile R and C for the next bridge | card, repo | code, review token, ledger row | `gate.py freeze`; launcher accepts |
| **V Verdict** | `render_record.py`; `gate.py record` and `packet`; Reviewer blind `task`; Scientist diagnosis first if out of band; Explorer advisory findings if a merge is possible | record, card, paths | verdict; node done or pruned; `git_merge_branch --dry-run`, merge if the held-out margin clears; lesson into `insight` | state written; views re-rendered; back to R |

Codex runs in B and V only, and once more before submission. Card critique in C is Explorer, advisory; the hard check is `gate.py`.

Paper side after the first `merged` node: `ccf-experiment-designer` result tables from records → `ccf-paper-writer` → `ccf-paper-reviewer` on K3 → `ccf-integrity-auditor` → Reviewer `adversarial-review` once → `ccf-submission-checker`. Numbers enter the manuscript only from `records/`.

## 7. Gates

### 7.1 Type-A, `gate.py`

- `card`: schema complete; `kill.threshold` numeric with direction; `n_required ≥ 3`; `mde` from `seed_sd` and `n_required`, and `mde < band[0]`; controls non-empty; `cost_gpu_h` within remaining budget and allocation caps; dedup query over tree hypotheses, `records/`, `LIT-LEDGER.md` returns no uncited hit.
- `freeze`: writes `frozen_sha` into card and node; refuses if the card changed after the Explorer critique was appended.
- `record`: `n_realized ≥ n_required`; `canary.pass`; `checkpoint_loaded_frac ≥ 0.9`; `band_hit` and `kill_hit` from the card; artifact shas verified; `blockers` empty or the state cannot be SUPPORTED.
- `packet`: assembles card + record + paths + the fixed role prompt (adapted from ARIS `result-to-claim` and `experiment-audit`). Main never composes a packet.
- `budget`: remaining GPU-h from `ledger.jsonl` against the GOAL.md ceiling; caps are GOAL.md parameters (defaults: oracle ≤ 5% of a card's cost, one T4 run ≤ 25% of remaining, reserve 20%).
- `views`: renders the four views from tree and files.

### 7.2 Type-B, Reviewer

Input is the packet only. Output is JSON: `verdict ∈ {SUPPORTED, REFUTED, CONTESTED, UNVERIFIABLE}`, `criterion_met`, `blocking[]`. Binary against the card, never a score. Pre-launch review uses the plugin's native `review`, whose output follows `schemas/review-output.schema.json`; a `critical` finding blocks the launch token. Explorer findings on merge candidates are appended to the packet as advisory input and cannot block.

### 7.3 Launcher and hooks

- `run_protected.sh` refuses without a frozen card, a passing `gate.py card`, and a review token naming the card sha; appends the ledger at start and at unit exit with systemd wall-time and GPU. A `PreToolUse` hook denies `nohup`, `systemd-run`, or a GPU python outside the launcher.
- `SessionStart` writes `.research/LOCK`; a second session with a live lock is read-only and the launcher refuses it.
- `SubagentStop` identity probe (§4.1), which also rejects a report whose first line is not `METHOD:`.

## 8. Component map

| Stage | Adopted | Custom |
|---|---|---|
| Bridges | idea-spark pattern cards and anti-patterns as Explorer reading | bridge schema, brief template |
| Retrieval, dedup | `paper-search`, `scoop-check`, `corpus.py` | dedup query in `gate.py` |
| Card | Scientist; `statistical-power`, `ablation-planner` | card schema |
| State, merge guard | Arbor MCP; `arbor-agent-merge-eval` | node mapping |
| Implement, run | ARIS `experiment-bridge`; `experiment-queue` for grids; `run_protected.sh`; Monitor | launcher extension |
| Record | driveline JSONL shape | `render_record.py` |
| Verdict | Codex plugin `review`, `task`, `adversarial-review`; ARIS `reviewer-independence`, `acceptance-gate`, `result-to-claim` prompt text | `gate.py`, packet and verdict schemas |
| Write, submit | `ccf-experiment-designer`, `ccf-paper-writer`, `ccf-paper-reviewer`, `ccf-integrity-auditor`, `ccf-submission-checker`, `ccf-latex-templates` | none |
| Disseminate (after acceptance) | `paper2assets`, `paper2poster`, `paper2blog` | none |
| Overnight | `claude --bg` or OS cron `claude -p --resume --bare`; a heartbeat may nudge, never acquit | none |

## 9. Custom inventory

| File | Lines | Job |
|---|---|---|
| `.research/gate.py` | ~250 | card, freeze, record, packet, budget, dedup, views |
| `.research/render_record.py` | ~150 | result JSONs → record; ledger join; shas |
| `scripts/run_protected.sh` | +40 | card, gate, token checks; ledger append |
| `.claude/hooks/{launch-gate,identity-probe,session-lock}.py` | ~120 total | deny ungated launches; verify models and METHOD line; single writer |
| `.claude/agents/{builder,scientist,explorer,researcher,reviewer}.md` | ~40 each | identity, model id, tools, required reading, brief and report contract |
| `.research/briefs/TEMPLATE-<lane>.md` | ~15 each | the fifteen-line dispatch shape per lane; the Explorer template carries the bridge schema |
| `CLAUDE.md` | ≤ 120 | model map, phase table, dispatch contract, six rules |
| `GOAL.md` | +8 fields | metric, eval commands, ceiling, caps, protected paths, repo root, N scientists, venue |

Under 900 lines. No MCP server. No stage skills. No router skill.

## 10. Deployment

1. `cp -r ~/.claude-kimi ~/.claude-research`; set the env block in §4.1 including `CODEX_REVIEW_GATE_GLOBAL=false`; keep `permissions.defaultMode`.
2. `claude mcp add arbor -- arbor mcp` in that config. Remove `grill`, `playwright-extension`, `agent-browser` from the campaign config. The `codex` plugin stays enabled for its script; its slash commands are not used by the loop.
3. `git init` in `ugra-rgbd-robust/` if needed; create `research-trunk`; Arbor run init; `tree_set_meta` from GOAL.md.
4. Populate `.claude/skills/` exactly per §14: keep `paper-search`, `scoop-check`, `idea-spark` (references only), five CCFA skills plus `ccf-latex-templates`, `paper2*` dormant; copy ARIS `experiment-bridge`, `experiment-queue`, `shared-references`; `arbor install --project` then delete every `arbor-agent-*` except `merge-eval`; symlink `statistical-power` and `ablation-planner` from the global set. Remove the other 11 CCFA symlinks.
5. Write the five agent files with REQUIRED READING, five brief templates, three hooks, two scripts, launcher extension.
6. Run `claude-md-management:revise-claude-md` to produce CLAUDE.md from this spec.
7. Acceptance test (§11) before the first real card.

## 11. Acceptance test

- **Known-real card:** a prediction the frozen checkpoint already satisfies (the entire_missing canary). Must reach `SUPPORTED` with a blind Codex verdict and a ledger row.
- **Known-null card:** a control that must fail (shuffled corruption arm). Must die at O or be `REFUTED` at V; the Reviewer must not be able to see why Main expected it to fail.
- **Identity and METHOD probe:** one dispatch of each lane; every transcript's model matches its agent file; every report opens with `METHOD:`; Codex returns valid JSON through the plugin script.
- **Lock:** a second session is refused by the launcher.
- **Bridge cycle:** one R phase end to end produces `bridges/` with 3 to 5 entries each carrying a disanalogy, and one packet per bridge.

Implementation about one day; the acceptance test about two hours.

## 12. Removed on purpose

Grill MCP and the six stage skills; idea-spark's five-phase run (180k to 250k tokens per idea); ARIS pipelines and review loops; eleven CCFA skills; `paperjury`; `autoresearch`, `auto-experiment`, `dse-loop`; the ChatGPT Playwright and Scholar lanes; the Codex stop-time review gate; MoA panels; agent teams; the Workflow tool; standing counters as triggers; Main as a reasoner.

## 13. Risks

1. **Codex quota.** Confined to B, V, and one pre-submission pass; the stop gate is off. `REVIEW_UNAVAILABLE` blocks a SUPPORTED state rather than substituting a same-family reviewer.
2. **Fable quota.** N per cycle is a GOAL.md field; diagnosis calls count against it.
3. **Explorer false rejections.** Structurally impossible: its output is bridges and advisory findings; it holds no gate.
4. **Bridges that are vocabulary, not mechanism.** The bridge schema requires the disanalogy and the pattern; the Scientist rejects a bridge without a mechanism-level analogy before any card is written.
5. **Arbor node schema is thin.** Cards live in files; if the constraints view is not enough lesson memory, `gate.py views` grows, not the MCP.
6. **Proxy uptime.** The identity probe turns a silent substitution into a hard stop; fallback is Anthropic-direct for Fable and the `grok` CLI for retrieval.
7. **Main drift into reasoning.** The dispatch contract is fifteen lines and paths only; any deviation is visible in `reports/`.

## 14. Skills triage

Legend: KEEP = as shipped · TRIM = named parts only · DROP = not loaded.

| Source | Skill | Verdict | Used by | Reason |
|---|---|---|---|---|
| ResearchStudio (Microsoft) | `paper-search` | KEEP | Researcher | script-backed, six sources, selftest green |
| ResearchStudio | `scoop-check` | KEEP | Researcher | script-backed novelty verdict per axis |
| ResearchStudio | `idea-spark` | TRIM to `references/ideation-patterns/overview.md`, `anti-patterns.md` | Explorer | the 15 corpus-induced patterns are the bridge vocabulary; the 5-phase run is too slow |
| ResearchStudio | `paper2assets`, `paper2poster`, `paper2blog` | KEEP, dormant | after acceptance | not part of the loop |
| ResearchStudio | `paper2video`, `paper2reel` | DROP | — | external deck dependency, missing `ffprobe` |
| OpenAI | `codex` plugin | KEEP: `review`, `task` read-only, `adversarial-review` | Reviewer | official runtime, structured review schema; stop gate disabled |
| RUC-NLPIR | Arbor MCP | KEEP | Main | tree, eval, worktrees, held-out merge guard |
| RUC-NLPIR | `arbor-agent-merge-eval` | KEEP | Main | merge and eval discipline |
| RUC-NLPIR | other 10 `arbor-agent-*` | DROP | — | our loop replaces coordinator, ideate, executor |
| ARIS | `experiment-bridge` | KEEP with `CODE_REVIEW=false` | Builder | implement → smoke → deploy discipline |
| ARIS | `experiment-queue` | KEEP, only for ≥ 10 jobs | Builder | the one real scheduler (`queue_manager.py`); needs `.aris/tools` |
| ARIS | `shared-references/reviewer-independence.md`, `acceptance-gate.md` | KEEP | Reviewer | the two contracts the packet enforces |
| ARIS | `result-to-claim`, `experiment-audit` | TRIM to prompt text inside `gate.py packet` | — | their MCP backend is replaced by the plugin |
| ARIS | everything else (`research-pipeline`, review loops, `kill-argument`, idea and paper skills) | DROP | — | pipelines we replace; `adversarial-review` covers kill-argument |
| CCFA | `ccf-experiment-designer` | KEEP | Scientist at card time; paper tables | claim-evidence matrix, no-fabrication rule |
| CCFA | `ccf-paper-writer`, `ccf-latex-templates` | KEEP | paper side | venue guides, templates present |
| CCFA | `ccf-paper-reviewer` | KEEP | paper side on K3 | assessment-only, cheap, no Codex quota |
| CCFA | `ccf-integrity-auditor`, `ccf-submission-checker` | KEEP | paper side | consistency and venue checks |
| CCFA | `ccf-rebuttal-writer` | KEEP, dormant | after reviews | not loaded until needed |
| CCFA | other 11 (`pipeline-orchestrator`, `scaffolder`, `idea-optimizer`, `idea-reviewer`, `literature-monitor`, `literature-searcher`, `humanization`, `paper-to-exemplar`, `visual-composer`, `skill-forger`, `common`) | DROP | — | orchestration we replace, prompt-only retrieval, unverifiable renderer, governance |
| global | `statistical-power` | KEEP | Scientist | n and MDE before launch |
| global | `ablation-planner` | KEEP | Scientist | design-time ablations, trivial baseline, negative control |
| global | `experimental-design` | KEEP, on demand | Scientist | controls and blocking when a card needs them |
| global | `paperjury`, `autoresearch`, `auto-experiment`, `dse-loop`, `what-if-oracle`, `paper-figure-loop` and the figure skills | DROP from the loop | — | different regime or paper-side tooling chosen later |
| ours | grill, `research-*`, `sprint`, `web-review`, `grilling-science` | DROP | — | retired |
