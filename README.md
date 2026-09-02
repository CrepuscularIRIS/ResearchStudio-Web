# research-harness

A simplified autonomous-research harness for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). Five model lanes with one job each, pre-registered hypothesis cards adjudicated blind by an out-of-ecosystem reviewer, script gates over artifacts, and a GPU ledger written by the launcher rather than by any agent.

It does not rebuild what exists. Ideation patterns, retrieval, novelty checks, experiment discipline, the hypothesis tree, and paper-side skills come from maintained third-party skills. The custom layer is under 900 lines.

## Why it looks like this

Two 2026 evaluations of autonomous research agents shaped every decision:

- **AutoResearchEval** (arXiv 2608.14905): 92% of failures are cognitive, not engineering. The single most common one, in 82.5% of runs, is the agent finding a fatal flaw in its own self-review and shipping anyway. The named fix is verification the agent does not control.
- **ASI-Bench** (arXiv 2608.17271): harness shapes capability; a coding-strong model in Claude Code matches far more expensive setups, and Codex with GPT-5.6 at high effort is the best cost-to-score reviewer.

So: records are rendered from result files by a script, never typed. Self-review findings are structured `blockers` the gate refuses to pass. The reviewer receives the card, the machine-rendered record, and file paths, and never the experimenter's narrative. The kill criterion is fixed before the run. Every run, including failures, is in the ledger.

## The lanes

| Lane | Model role | Job | Never |
|---|---|---|---|
| **Main** | coding model with the largest quota, persistent | dispatch by the phase table, run the scripts, write the Arbor tree, launch | reason about the science, summarise reports, type numbers |
| **Builder** | same coding model, fresh per build | implement one card in a worktree, smoke → small → full, emit per-seed result JSONs | design, launch, write state |
| **Scientist** | strongest reasoner, quota-limited | judge bridges at mechanism level, write cards, diagnose out-of-band results | state writes, implementation, retrieval |
| **Explorer** | a second model family | 3 to 5 domain-A to domain-B bridges per cycle, each with the disanalogy that could break it; advisory critique | rank, block, write state |
| **Researcher** | retrieval model | one prior-art packet per bridge across both domains; dedup | rank, design |
| **Reviewer** | Codex via the official plugin | diff review before launch, blind verdict after, one adversarial review before submission | see Main's transcript |

Main passes file paths between lanes, never content. Every dispatch is a fifteen-line brief; every report opens with `METHOD: <files read>` or the hook rejects it.

## The loop

```
R  Research   Explorer names bridges → Researcher ×N fetches both domains per bridge
C  Card       Scientist writes 1–3 cards → gate.py card → Explorer critique → Main picks one → Arbor node
O  Oracle     ≤ 1 GPU-hour probe: signal above MDE or the node is pruned
B  Build+run  Builder implements → Codex diff review → gate.py freeze → launcher writes the ledger → Monitor
V  Verdict    render_record → gate.py record → gate.py packet → Codex blind verdict → gate.py verdict → merge if the held-out margin clears
```

A phase ends when its artifact exists and its gate passed. Long runs are normal; R and C for the next bridge proceed while a run trains.

## Install

```bash
claude plugin marketplace add CrepuscularIRIS/research-harness
claude plugin install research-harness@research-harness
```

Then, in your project:

```bash
/research-harness:init        # scaffolds .research/, the GOAL.md campaign block, and CLAUDE.md
claude mcp add arbor -- arbor mcp
```

The plugin's hooks are active in every project once installed: a launch gate on `Bash` (no `nohup`, `systemd-run`, or GPU python outside the launcher), a single-writer lock at session start, and an identity probe on every subagent stop. Install it in a dedicated config dir if you do not want that everywhere:

```bash
cp -r ~/.claude ~/.claude-research && CLAUDE_CONFIG_DIR=~/.claude-research claude
```

### Third-party skills the lanes read

Install what your lanes need into `.claude/skills/` (the agent files reference them by relative path):

| Skill | From | Used by |
|---|---|---|
| `paper-search`, `scoop-check` | [microsoft/ResearchStudio](https://github.com/microsoft/ResearchStudio) (Idea) | Researcher |
| `idea-spark/references/ideation-patterns/overview.md`, `anti-patterns.md` | ResearchStudio (Idea); the reference files only, not the pipeline | Explorer |
| `experiment-bridge`, `experiment-queue`, `shared-references` | [wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) | Builder, Reviewer |
| Arbor MCP and `arbor-agent-merge-eval` | [RUC-NLPIR/Arbor](https://github.com/RUC-NLPIR/Arbor) | Main |
| `statistical-power`, `ablation-planner` | your global skills | Scientist |
| `codex@openai-codex` plugin | [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) | Reviewer |
| `ccf-experiment-designer`, `ccf-paper-writer`, `ccf-paper-reviewer`, `ccf-integrity-auditor`, `ccf-submission-checker` | CCFA-Skills | paper side |

### Model routing

Set the concrete model per lane in `.claude/agents/<lane>.md` (`model:`) or through your config dir's `ANTHROPIC_DEFAULT_*_MODEL` env when routing through a gateway. The identity-probe hook reads the model each subagent actually ran with from its transcript and rejects the report on mismatch, because a silent alias substitution is invisible in the conversation.

Keep the Codex plugin's stop-time review gate off (`CODEX_REVIEW_GATE_GLOBAL=false`); the harness calls Codex only in phases B and V and once before submission.

## Files the harness owns

```
.research/
  cards/<id>.json          written by the Scientist, frozen by gate.py (sha in the Arbor node)
  records/<run>.json,.md   rendered by render_record.py from results/<run>/seed_<k>.json
  packets/<id>.md          built by gate.py packet; the only thing the Reviewer sees
  verdicts/<id>.json       Reviewer JSON + type-A checks + computed state
  bridges/, lit/, briefs/, reports/, views/, tokens/
  ledger.jsonl             appended by run_protected.sh and launch_wrap.sh
  LOCK                     single-writer lock
```

State rule, computed by script: `REFUTED` only if the record hits the kill criterion; `SUPPORTED` only if type-A checks pass, the reviewer says SUPPORTED, and no blocker is open; otherwise `CONTESTED`. Reasoning demotes; only a record refutes.

## Acceptance test before real spend

`docs/ACCEPTANCE.md`: a known-real card must reach SUPPORTED blind, a known-null card must die, every lane must pass the identity and METHOD probe, a second session must be refused by the launcher, and one bridge cycle must complete. Nothing launches for real until it prints `ACCEPTED`.

## Tests

```bash
python3 -m pytest tests -q          # gates, record renderer, hooks
bash tests/test_launcher.sh         # spawns a real systemd --user unit in a temp project
```

## Design record

`docs/SPEC.md` is the design as approved for the campaign this was built for (RGB-D segmentation robustness), including the evidence table and the skills triage. Paths in it are that project's.

## License

MIT.
