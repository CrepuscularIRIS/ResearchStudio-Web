---
name: experiment-audit
description: "Audit experiment integrity before claiming results. Uses cross-model review (external reviewer backend) to check for fake ground truth, score normalization fraud, phantom results, and insufficient scope. Use when user says \"审计实验\", \"check experiment integrity\", \"audit results\", \"实验诚实度\", or after experiments complete before writing claims."
argument-hint: "[experiment-dir-or-results-path]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, mcp__codex__codex, mcp__codex__codex-reply, mcp__manual_review__review, mcp__manual_review__review_reply
---

# Experiment Audit: Cross-Model Integrity Verification

> 🔒 **Do not wrap this skill in `/loop`, `/schedule`, or `CronCreate`.** It is
> verdict-bearing — it judges experiment integrity. Re-running that verdict on a
> timer adds no new signal, and a loop that accepts its own output to decide
> when to stop crosses into self-acquittal (`acceptance-gate.md`). Schedule the
> *external wait that precedes it* — experiments done → then audit **once**. See
> [`shared-references/external-cadence.md`](../shared-references/external-cadence.md).

Audit experiment integrity for: **$ARGUMENTS**

## Why This Exists

LLM agents can produce fraudulent experimental results through:
1. **Fake ground truth** — creating synthetic "reference" from model outputs, then reporting high agreement as performance
2. **Score normalization** — dividing metrics by the model's own max to get 0.99+
3. **Phantom results** — claiming numbers from files that don't exist or functions never called
4. **Insufficient scope** — reporting 2-scene pilots as "comprehensive evaluation"

These are NOT intentional deception — they are failure modes of optimizing agents that lack integrity constraints. This skill adds that constraint.

## Core Principle

**The executor collects file paths. The external reviewer backend reads code and judges integrity. The executor does NOT participate in integrity judgment.**

This follows `shared-references/reviewer-independence.md` and `shared-references/experiment-integrity.md`.

## Constants

- **REVIEWER_BACKEND = `codex`** — Default: Codex MCP (ultra). Override with `— reviewer: oracle-pro` for Oracle MCP, or `— reviewer: manual` for Manual Review MCP. If manual-review MCP is unavailable, stop and print the install command; do not fall back to Codex. See `shared-references/reviewer-routing.md`.

## Reviewer Calling Convention

When calling the reviewer, branch on REVIEWER_BACKEND:

**If REVIEWER_BACKEND = `codex`:**
  Use `mcp__codex__codex` for new review threads.
  Use `mcp__codex__codex-reply` for follow-up rounds (reuse threadId).

**If REVIEWER_BACKEND = `manual`:**
  Use `mcp__manual_review__review` for new review threads with:
    prompt: [exact same prompt that would go to Codex]
    config: {"model_reasoning_effort": "xhigh", "executor_model": "<actual executor model>", "require_reviewer_model": true}
  Save the returned `threadId`.
  Use `mcp__manual_review__review_reply` for follow-up rounds with:
    threadId: [saved manual-review threadId]
    prompt: [follow-up prompt]
    config: {"model_reasoning_effort": "xhigh", "executor_model": "<actual executor model>", "require_reviewer_model": true}

Prompt fidelity: the manual prompt must be exactly the same text that Codex would receive.
Review tracing applies equally to both backends.

## Workflow

### Step 1: Collect Artifacts (Executor — Claude)

Locate and list these files WITHOUT reading or summarizing their content:

```
Scan project directory for:
1. Evaluation scripts:    *eval*.py, *metric*.py, *test*.py, *benchmark*.py
2. Result files:          *.json, *.csv in results/, outputs/, logs/
3. Ground truth paths:    look in eval scripts for data loading (dataset paths, GT references)
4. Experiment tracker:    EXPERIMENT_TRACKER.md, EXPERIMENT_LOG.md
5. Paper claims:          NARRATIVE_REPORT.md, paper/sections/*.tex, PAPER_PLAN.md
6. Config files:          *.yaml, *.toml, *.json configs with metric definitions
```
  A verdict-bearing manual response MUST begin with
  `Reviewer-Model: <exact-model-id>` — pass the model THIS session is actually
  running as in `executor_model`. Missing, unknown, or same-family identity
  cannot acquit; emit `REVIEW_UNAVAILABLE` rather than guessing. If the executor
  model cannot be named, manual review's cross-family claim is unprovable — say
  so in the report instead of asserting it.


**DO NOT summarize, interpret, or explain any file content.** Only collect paths.

### Step 2: Send to Reviewer

Based on the selected reviewer backend (see Reviewer Calling Convention), pass ONLY file paths and the audit checklist to the reviewer. The reviewer reads everything directly.

For `codex`, call `mcp__codex__codex` with:
- `model: gpt-6-astra`
- `config: {"model_reasoning_effort": "ultra"}`
- `sandbox: read-only`
- `cwd: [project directory]`
- `prompt: [the exact full prompt below]`

For `manual`, call `mcp__manual_review__review` with:
- `config: {"model_reasoning_effort": "xhigh", "executor_model": "<actual executor model>", "require_reviewer_model": true}`
- `prompt: [the exact full prompt below]`

Manual review cannot use Codex-only `model`, `sandbox`, or `cwd`; include the same file paths in the prompt so the user can inspect them.

Use this exact prompt for both backends:

```
You are an experiment integrity auditor. Start from the assumption that the
    evaluation is compromised somewhere — your job is to find where. Be
    adversarial. Trust nothing the author tells you — verify everything
    yourself. Read ALL files listed below and check for the following fraud
    patterns.

    Files to read:
    - Evaluation scripts: [list paths]
    - Result files: [list paths]
    - Experiment tracker: [list paths]
    - Paper claims: [list paths]
    - Config files: [list paths]

    ## Audit Checklist

    ### A. Ground Truth Provenance
    For each evaluation script:
    1. Where does "ground truth" / "reference" / "target" come from?
    2. Is it loaded from the DATASET, or generated/derived from MODEL OUTPUTS?
    3. If derived: is it explicitly labeled as proxy evaluation?
    4. Are official eval scripts used when available for this benchmark?
    FAIL if: GT is derived from model outputs without explicit proxy labeling.

    ### B. Score Normalization
    For each metric computation:
    1. Is any metric divided by max/min/mean of the model's OWN output?
    2. Are raw scores reported alongside any normalized scores?
    3. Are any scores suspiciously close to 1.0 or 100%?
    FAIL if: Normalization denominator comes from prediction statistics.

    ### C. Result File Existence
    For each claim in the paper/narrative:
    1. Does the referenced result file actually exist?
    2. Does the claimed metric key exist in that file?
    3. Does the claimed NUMBER match what's in the file?
    4. Is the experiment tracker status DONE (not TODO/IN_PROGRESS)?
    FAIL if: Claimed results reference nonexistent files or mismatched numbers.

    ### D. Dead Code Detection
    For each metric function defined in eval scripts:
    1. Is it actually CALLED in any evaluation pipeline?
    2. Does its output appear in any result file?
    WARN if: Metric functions exist but are never called.

    ### E. Scope Assessment
    1. How many scenes/datasets/configurations were actually tested?
    2. How many seeds/runs per configuration?
    3. Does the paper use words like "comprehensive", "extensive", "robust"?
    4. Is the actual scope sufficient for those claims?
    WARN if: Scope language exceeds actual evidence.

    ### F. Evaluation Type Classification
    Classify each evaluation as:
    - real_gt: uses dataset-provided ground truth
    - synthetic_proxy: uses model-generated reference
    - self_supervised_proxy: no GT by design
    - simulation_only: simulated environment
    - human_eval: human judges

    ## Output Format

    For each check (A-F), report:
    - Status: PASS | WARN | FAIL
    - Evidence: exact file:line references
    - Details: what specifically was found

    Overall verdict: PASS | WARN | FAIL
    
    Be thorough. Read every eval script line by line.
```

<!-- ARFT/ASI-BENCH BLOCK: audit-arft-codes-and-anomalies -->
<!-- source: ARFT (arXiv 2608.14905) §0 scoring, §1 rules 1-3, §3 discrimination, §5 code list · ASI-Bench (arXiv 2608.17271) analysis/reviewer.py:212-284 dimensions 2/3/5 + CAUSE_BUCKET -->
### Step 2.9: Code Every Finding, and Read Its Polarity

The reviewer returns findings in prose. Before they become a report, each one gets a code from a
closed vocabulary and passes a polarity check. Both are cheap; both are load-bearing.

#### A. One ARFT code per finding

ARFT is a 45-code taxonomy of autoresearch failures across seven stages — A ideation, B
retrieval, C execution, D analysis, E write-up, F self-review, X cross-stage — rolling up to four
pillars (P1 grounding, P2 depth, P3 integrity, P4 engineering robustness). Give every finding
exactly one primary code, and additional codes when a single mechanism genuinely lands on
several: *"a hard-coded constant that produces the headline number is `C.1` + `D.4`, and `F.4`
too if the agent's own review flagged it and shipped anyway."*

Score each as ARFT scores them:

| Score | Meaning |
|---|---|
| **HIT** | The finding is established, with evidence. |
| **PARTIAL** | A real but qualified concern — hedged, minor, a single instance, or "risk of" rather than demonstrated. |
| **miss** | Not present, **or** the audit explicitly clears the run of it. |

Every HIT and PARTIAL carries `evidence`: one to three sentences quoting or citing a specific
place — a file, a line, a log excerpt. **A code with no locatable citation is rejected, not
downgraded.** If a real mechanism fits no code, say so and refute the two or three nearest codes
one by one; that escape hatch is for genuine gaps, not for saving effort.

The clusters that actually get confused, and the line between them:

- **`A.5` vs `A.6` vs `C.3`** — wrong yardstick chosen (`A.5`, the default for proxy substitution
  or narrowing); design structurally incapable of adjudicating the hypothesis (`A.6`, stronger,
  usually `A.5 + A.6`); code differs from the methodology *we ourselves claimed* (`C.3`,
  self-inconsistency rather than objective-mismatch).
- **`C.1` vs `C.2` vs `X.6`** — the result is a deterministic consequence of what we wrote
  (`C.1`, the default: self-generated data recovered by a model of the same class, a hard-coded
  constant reappearing as the headline, an algebraic identity reported as a finding); a grader,
  sealed evaluator or held-out set was used as a tuning signal (`C.2`, requires an external
  scorer in the loop); the metric **was actually hit**, but through a bug, leak or luck rather
  than the claimed mechanism (`X.6`, requires a real success to explain). `C.1` and `X.6` co-occur
  often: `C.1` names the mechanism, `X.6` records that it still scored.
- **`D.1` vs `D.6`** — numbers real but a bug or noise read as a result (`D.1`, misinterpretation)
  versus numbers never computed (`D.6`, invention).
- **`D.2` vs `D.7` vs `F.4`** — counter-evidence never engaged (`D.2`); noticed during analysis
  then dropped from the conclusions (`D.7`); flagged in our own review and shipped unchanged
  (`F.4`).
- **`C.7` vs `X.7`** — gave up at the first friction versus ground on down a dead end without
  re-planning. They are opposites; a run cannot be both.
- **`C.4` vs `C.5` vs `C.8`** — the fault itself; an infrastructure fault *misread as an
  algorithmic result*; mis-parsing the environment.

#### B. Polarity — the failure mode of this step

An audit that looks for fabrication and finds none has produced a **miss**, not a hit. ARFT's
first precision rule exists because this is the dominant labelling error:

> **The presence of a fabrication-adjacent term is an audited dimension, not a detected
> failure.** Read the polarity every single time. If the analysis says the agent did *not*
> fabricate, that is a **miss** for `B.1`/`D.6`/`E.4`, not a HIT.

Two more, applied here:

- **Credit is not evidence of failure.** Anything the report records under what the run did
  *right* — real data, honest disclosure, self-correction — can never be the sole source of a
  code. A code whose only support is a credit line is a polarity error.
- **A retracted finding is a miss.** If an earlier pass raised something and a later one withdrew
  it, it does not appear in this report as a HIT.

And the fairness rule that decides who is at fault: when the infrastructure genuinely broke and
the run is cleared of blame, that is **not** `C.4`/`C.5`/`C.8`. Code only our *response* to the
outage — usually `X.7` (kept polling a dead service) or `C.7` (gave up immediately).

#### C. Anomalies that indicate the block is wrong, not the run

ASI-Bench's trajectory review inverts the usual reading: *"Problems you find in the agent's
behavior often point to task design issues (unclear prompts, scorer bugs, GT leakage)."* Check
its anomaly list against this run, and route each hit to a cause bucket rather than to blame:

- **Searching for ground truth** — reading reference files, `../`, or run metadata it was not
  given. Points to a leak in the block, not only to the run.
- **Hard-coding values** — writing "known" numbers without computing them (`C.1`).
- **Bypassing the core computation** — using something in the inputs that makes the intended
  calculation unnecessary. The inputs gave too much away.
- **Repeated failure on the same step** — output requirements unclear, or a dependency missing.
- **Unexpected external resources** — searching the web for an answer the block was supposed to
  produce.

Then close with the two consistency questions the same review asks, because they catch opposite
errors and both are silent otherwise:

- **Right process, low score** → the scorer may be too strict, the format check too rigid, or a
  gate misfiring. Do not record a failure the numbers do not support.
- **Wrong process, high score** → the scorer has a hole, the tolerance is too wide, or a check is
  missing. This is the more dangerous direction, and it is `X.6` until proven otherwise.

Every finding therefore leaves this step with three fields: its **code**, its **score**
(HIT/PARTIAL), and its **cause bucket** — `Environment` | `Task` | `Agent` — where *Task* means
the block spec is at fault and must be repaired before the result means anything.
<!-- END BLOCK: audit-arft-codes-and-anomalies -->

### Step 3: Parse and Write Report (Executor — Claude)

Parse the reviewer's response and write `EXPERIMENT_AUDIT.md`:

```markdown
# Experiment Audit Report

**Date**: [today]
**Auditor**: External reviewer backend, ultra reasoning (cross-model, read-only)
**Project**: [project name]

## Overall Verdict: [PASS | WARN | FAIL]

## Integrity Status: [pass | warn | fail]

## Checks

### A. Ground Truth Provenance: [PASS|WARN|FAIL]
[details + file:line evidence]

### B. Score Normalization: [PASS|WARN|FAIL]
[details]

### C. Result File Existence: [PASS|WARN|FAIL]
[details]

### D. Dead Code Detection: [PASS|WARN|FAIL]
[details]

### E. Scope Assessment: [PASS|WARN|FAIL]
[details]

### F. Evaluation Type: [real_gt | synthetic_proxy | ...]
[classification + evidence]

## Action Items
- [specific fixes if WARN or FAIL]

## Claim Impact
- Claim 1: [supported | needs qualifier | unsupported]
- Claim 2: ...
```

Also write `EXPERIMENT_AUDIT.json` for machine consumption:

```json
{
  "date": "2026-04-10",
  "auditor": "external-reviewer-ultra",
  "overall_verdict": "warn",
  "integrity_status": "warn",
  "checks": {
    "gt_provenance": {"status": "pass", "details": "..."},
    "score_normalization": {"status": "warn", "details": "..."},
    "result_existence": {"status": "pass", "details": "..."},
    "dead_code": {"status": "pass", "details": "..."},
    "scope": {"status": "warn", "details": "..."},
    "eval_type": "real_gt"
  },
  "claims": [
    {"id": "C1", "impact": "supported"},
    {"id": "C2", "impact": "needs_qualifier"}
  ]
}
```

### Step 4: Print Summary

```
🔬 Experiment Audit Complete

  GT Provenance:      ✅ PASS — real dataset GT used
  Score Normalization: ⚠️ WARN — boundary metric uses self-reference
  Result Existence:    ✅ PASS — all files exist, numbers match
  Dead Code:           ✅ PASS — all metric functions called
  Scope:               ⚠️ WARN — 2 scenes, paper says "comprehensive"

  Overall: ⚠️ WARN
  
  See EXPERIMENT_AUDIT.md for details.
```

## Integration with Other Skills

### Automatic in /research-pipeline (advisory, never blocks)

When integrated into the pipeline, this skill runs automatically after `/experiment-bridge` and before `/auto-review-loop`:

```
/experiment-bridge → results ready
    ↓
/experiment-audit (automatic, advisory)
    ├── PASS  → continue normally
    ├── WARN  → print ⚠️ warning, continue, tag claims as [INTEGRITY: WARN]
    └── FAIL  → print 🔴 alert, continue, tag claims as [INTEGRITY CONCERN]
    ↓
/auto-review-loop → proceeds with integrity tags visible to reviewer
```

**Never blocks the pipeline.** Even on FAIL, the pipeline continues — but claims carry visible integrity tags.

### Read by /result-to-claim (if exists)

```
if EXPERIMENT_AUDIT.json exists:
    read integrity_status
    attach to verdict: {claim_supported: "yes", integrity_status: "warn"}
    if integrity_status == "fail":
        downgrade verdict display: "yes [INTEGRITY CONCERN]"
else:
    verdict as normal, integrity_status = "unavailable"
    mark as "provisional — no integrity audit"
```

### Read by /paper-write (if exists)

```
if EXPERIMENT_AUDIT.json exists AND integrity_status == "fail":
    add footnote to affected claims: "Note: integrity audit flagged concerns with this evaluation"
```

## Key Rules

- **Reviewer independence**: executor collects paths, reviewer judges. Period.
- **Never block**: warn loudly, never halt the pipeline.
- **File-as-switch**: no EXPERIMENT_AUDIT.md = skill was never run = zero impact on existing behavior.
- **Cross-model**: the reviewer MUST be a different model family from the executor.
- **Honest about limits**: the audit catches common patterns, not all possible fraud. It is a safety net, not a guarantee.

## Acknowledgements

Motivated by community-reported integrity issues (#57, #131) where executor agents created fake ground truth and self-normalized scores.

## Review Tracing

After each reviewer call (`mcp__codex__codex`, `mcp__codex__codex-reply`, `mcp__manual_review__review`, or `mcp__manual_review__review_reply`), save the trace following `shared-references/review-tracing.md` (Policy C — forensic; never silently skip). Use `save_trace.sh` (resolved per the chain in `shared-references/integration-contract.md` §2) or write files directly to `.aris/traces/<skill>/<date>_run<NN>/`. Respect the `--- trace:` parameter (default: `full`).
