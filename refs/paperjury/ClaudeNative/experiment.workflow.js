/**
 * experiment — V8 v3: Adaptive Experimentation (WORKFLOW.md final minimal main line).
 *
 * GLM does the work. Opus decides what is worth doing. Grok checks what was actually
 * done. Sol appears only when the math itself is the bottleneck.
 *
 * Three modes:
 *   plan  — Sol ∥ K3 ∥ GLM propose tests → Opus picks the ONE that most changes belief
 *           → JS hard floors → frozen TestSketch
 *   build — Sol B1 spec → GLM implement → GLM probe+finders (one pass) → JS floors
 *           → [fix] → Grok CLI review (final gate) → launch under canary
 *   judge — GLM manifest → JS det floors → GLM recompute ∥ integrity ∥ grounding
 *           → GLM analysis + conditional K3 → Grok CLI audit → JS composes E
 *
 * No verifier seats. No cascade. No paper logic. Invalid ≠ refuted (JS state machine).
 * Grok is invoked via the plugin CLI (grok-companion.mjs), not as a direct agent model.
 */

export const meta = {
  name: 'experiment',
  description: "Adaptive Experimentation: plan (Sol∥K3∥GLM propose, Opus picks, JS floors) / build (Sol B1, GLM implement, GLM probe+finders, Grok CLI review, launch) / judge (GLM manifest, GLM recompute∥integrity∥grounding, conditional K3, Grok CLI audit, JS E).",
  whenToUse: "dag offers WORKFLOW: experiment with mode ∈ {plan, build, judge}.",
  phases: [
    { title: "Plan", detail: "Sol falsifiers ∥ K3 prosecutor ∥ GLM alternatives → Opus taste-pick → JS floors → TestSketch" },
    { title: "Build", detail: "Sol B1 spec → GLM implement → GLM probe+finders (one pass, no verify seat) → JS floors → [fix] → Grok CLI review → launch" },
    { title: "Judge", detail: "GLM manifest → JS det floors → GLM recompute ∥ integrity ∥ grounding → GLM analysis + conditional K3 → Grok CLI audit → JS E" },
  ],
}

const MODEL = { opus: 'claude-opus-5', sol: 'gpt-5.6-sol', k3: 'k3-256k', glm: 'glm-5.3[1m]' }
const GROK_CLI = "node /home/lingxufeng/.claude/plugins/cache/grok/grok/0.3.0/scripts/grok-companion.mjs"
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const MODE = A.mode || "plan"
const ROOTDIR = A.root || "/home/lingxufeng/workspace"
const FROZEN = (() => {
  const f = A.frozen
  if (typeof f === "string") { try { return JSON.parse(f) } catch { return {} } }
  return f || {}
})()

// ─── prompt contracts (from ARFT/RS/CCFA — not verifier seats, just instructions) ───
const NAIVE = "NAIVE FIRST: the most naive runnable version; ONE branch — (i) false premise (confrontation IS the contribution) / (ii) works & known (incremental) / (iii) works but disbelieved. candidate ≈ naive → kill."
const FALSIFY = "FALSIFIER: (a) minimal experiment procedure; (b) outcome metric + direction; (c) ONE load-bearing variable; (d) negative control predicting the OUTCOME metric returns to baseline — 'intervene X → X=0' is tautological."
const MVE_PRIORITY = "MVE priority: eval-only > frozen-ckpt intervention > small subset > partial training > full. Cheapest that changes Claim state."
const BUILD_DISCIPLINE =
  "BUILD discipline (ARFT contracts, not verifier seats):\n" +
  "- spec-drift: every step in the spec has a corresponding diff hunk; nothing changed that no step asked for\n" +
  "- leakage: no training/selection statistic reads the test half; targets not analytically derivable from inputs\n" +
  "- integrity: no fake GT, no normalization fraud, no phantom results, no hardcoded numbers in code\n" +
  "- numbers live in result documents, never in implementation code"
const JUDGE_DISCIPLINE =
  "JUDGE discipline (ARFT contracts):\n" +
  "- A GT provenance: dataset GT, not model outputs\n" +
  "- B normalization: denominator not from predictions\n" +
  "- C artifact existence: every number traces to a file\n" +
  "- D scope: words match actual N\n" +
  "- E counterevidence: strong counterargument → does Claim state change? (D.7: not changing it is a violation)\n" +
  "- F right-for-wrong-reason: is the metric achieved through the claimed mechanism, not a shortcut?"

// ─── infra ───
let agentCalls = 0
const byModel = {}
const seat = async (prompt, opts) => {
  agentCalls++; byModel[opts.model] = (byModel[opts.model] || 0) + 1
  return agent(prompt, opts)
}

if (!A.claim || !A.claim.statement) return { error: "No claim in args." }
const C = A.claim
const rows = C.contract_rows || []
const M = { id: A.method_id || C.id + "-" + (A.sketch ? A.sketch.test_id : "plan") }
const BUILD_DIR = ROOTDIR + "/.research/build/" + M.id

// ─── Grok CLI helper (invoked by a GLM proxy seat that runs the Bash command) ───
async function grokReview(cwd, focus) {
  const r = await seat(
    "Run this Bash command and return its stdout verbatim (do NOT interpret, do NOT add commentary):\n" +
    "`cd " + cwd + " && " + GROK_CLI + " review --read-only" + (focus ? " --focus \"" + focus + "\"" : "") + "`\n" +
    "If it fails or times out, return {unavailable: true}.",
    { label: "grok:review", phase: "Build", schema: {
      type: "object", required: ["output"],
      properties: { output: { type: "string" }, unavailable: { type: "boolean" },
        findings: { type: "array", items: { type: "object", required: ["summary", "severity"], properties: {
          summary: { type: "string" }, severity: { enum: ["critical", "high", "medium", "low"] },
          file: { type: "string" }, line: { type: "number" } } } } },
    }, model: MODEL.glm })
  return r
}
async function grokAudit(cwd, task) {
  const r = await seat(
    "Run this Bash command and return its stdout verbatim:\n" +
    "`cd " + cwd + " && " + GROK_CLI + " task --read-only \"" + task + "\"`\n" +
    "If it fails, return {unavailable: true}.",
    { label: "grok:audit", phase: "Judge", schema: {
      type: "object", required: ["output"],
      properties: { output: { type: "string" }, unavailable: { type: "boolean" },
        verdict: { type: "string" }, issues: { type: "array", items: { type: "string" } } },
    }, model: MODEL.glm })
  return r
}

// ═══ PLAN ═══════════════════════════════════════════════════════════════
if (MODE === "plan") {
  phase("Plan")
  const claimBlock = "## Claim\n" + C.statement + "\n## Strategy\n" + (C.strategy || "") +
    "\n## Margin rule\n" + (C.margin_rule || "") + "\n## Contract rows\n" + JSON.stringify(rows) +
    "\n## Falsifier\n" + (C.falsification_prediction || "") +
    "\n## Naive\n" + JSON.stringify(C.naive_baseline || {})

  const SKETCH_SCHEMA = {
    type: "object", required: ["test_id", "target_rows", "hypothesis_edge", "intervention", "expected_if_claim", "expected_if_anti_claim", "kill_condition", "mde", "cost_gpu_h", "eval_only", "canary", "uses_dev_half_only"],
    properties: {
      test_id: { type: "string" }, target_rows: { type: "array", items: { type: "string" } },
      hypothesis_edge: { type: "string" }, intervention: { type: "string" },
      expected_if_claim: { type: "string" }, expected_if_anti_claim: { type: "string" },
      kill_condition: { type: "string" }, mde: { type: "string" },
      cost_gpu_h: { type: "number" }, eval_only: { type: "boolean" },
      canary: { type: "boolean" }, uses_dev_half_only: { type: "boolean" },
      max_effect_available: { type: "string" },
    },
  }
  const [solT, k3T, glmT] = await parallel([
    () => seat(claimBlock + "\n\nSEAT (sol — cheapest technical falsifier). " + MVE_PRIORITY + " " + FALSIFY + " " + NAIVE +
      "\nPropose up to 3 tests. Each must name MDE and kill_condition.\n\nStructured output only.",
      { label: "plan:sol", phase: "Plan", schema: { type: "object", required: ["tests"], properties: { tests: { type: "array", maxItems: 3, items: SKETCH_SCHEMA } } }, model: MODEL.sol }),
    () => seat(claimBlock + "\n\nSEAT (K3 — prosecutor: what is the most FATAL possibility?). Propose up to 2 tests targeting the claim's weakest assumption. You are NOT the judge.\n\nStructured output only.",
      { label: "plan:k3", phase: "Plan", schema: { type: "object", required: ["tests"], properties: { tests: { type: "array", maxItems: 2, items: SKETCH_SCHEMA } } }, model: MODEL.k3 }),
    () => seat(claimBlock + "\n## Substrate\n" + JSON.stringify(A.substrate || {}).slice(0, 3000) +
      "\n\nSEAT (GLM — cheapest runnable alternatives on THIS substrate). " + MVE_PRIORITY +
      "\nPropose up to 3. Each ≤ " + (FROZEN.kill_cap_gpu_h || 4) + " GPU-h.\n\nStructured output only.",
      { label: "plan:glm", phase: "Plan", schema: { type: "object", required: ["tests"], properties: { tests: { type: "array", maxItems: 3, items: SKETCH_SCHEMA } } }, model: MODEL.glm }),
  ])
  if (!solT || !k3T || !glmT) return { error: "plan seat absent — infra, not a verdict; retry." }
  const all = [].concat(solT.tests || [], k3T.tests || [], glmT.tests || [])
  const cap = FROZEN.kill_cap_gpu_h || 4
  const valid = all.filter(t => t.kill_condition && t.mde && (t.cost_gpu_h || 0) <= cap &&
    t.expected_if_claim && t.expected_if_anti_claim && t.canary && t.uses_dev_half_only !== false)
  if (!valid.length) return { outcome: "no_valid_tests", remedial: ["all tests failed hard floors"] }

  // Opus taste-pick: which ONE test most changes what we believe about the Claim
  const pick = await seat(
    "SEAT (Opus — taste: which experiment is WORTH running?)\n## Claim\n" + C.statement +
    "\n## Margin rule\n" + (C.margin_rule || "") + "\n## Valid tests\n" +
    valid.map((t, i) => "[" + i + "] " + t.test_id + ": " + t.hypothesis_edge + " | cost " + t.cost_gpu_h + "h | eval_only=" + t.eval_only).join("\n") +
    "\n\nIf you could run only ONE, which most changes what we believe about this Claim? " +
    "Not the cheapest, not the most thorough — the one whose result would most update your posterior. " +
    "Return its index.\n\nStructured output only.",
    { label: "plan:pick", phase: "Plan", schema: {
      type: "object", required: ["index", "rationale"],
      properties: { index: { type: "number" }, rationale: { type: "string" } },
    }, model: MODEL.opus })
  if (!pick) return { error: "Opus pick seat absent — infra, not a verdict; retry." }
  const chosen = (pick.index >= 0 && pick.index < valid.length) ? valid[pick.index] : valid[0]
  return { outcome: "planned", claim: C.id, sketch: chosen,
    alternatives: valid.filter(t => t !== chosen).map(t => ({ test_id: t.test_id, cost: t.cost_gpu_h })),
    stats: { agentCalls, byModel } }
}

// ═══ BUILD ══════════════════════════════════════════════════════════════
if (MODE === "build") {
  if (!A.sketch) return { error: "build needs args.sketch." }
  const sketch = A.sketch
  phase("Build")
  // Sol B1 spec
  const SPEC_SCHEMA = {
    type: "object", required: ["name", "steps", "run_cmd", "smoke_cmd", "eval_entry", "outcome_metric", "arms", "budget_gpu_h", "kind", "result_contract"],
    properties: {
      name: { type: "string" }, steps: { type: "array", minItems: 3, items: { type: "string" } },
      run_cmd: { type: "string" }, smoke_cmd: { type: "string" },
      eval_entry: { type: "string" }, outcome_metric: { type: "string" },
      arms: { type: "array", items: { type: "string" } }, budget_gpu_h: { type: "number" },
      kind: { enum: ["mve", "claim_evidence"] }, result_contract: { type: "string" },
      seeds: { type: "string" }, forbids: { type: "array", items: { type: "string" } },
    },
  }
  const spec = await seat(
    "SEAT (sol — B1 compiler)\n## TestSketch\n" + JSON.stringify(sketch) +
    "\n## Claim rows\n" + JSON.stringify(rows) + "\n## Substrate\n" + JSON.stringify(A.substrate || {}).slice(0, 3000) +
    "\n\nCompile into a B1-complete immutable TestSpec: functions, params, run_cmd, smoke, seeds, output schema, forbids. " +
    "outcome_metric = row metric VERBATIM. eval_entry PROTECTED.\n\nStructured output only.",
    { label: "spec", phase: "Build", schema: SPEC_SCHEMA, model: MODEL.sol })
  if (!spec) return { error: "spec seat absent — infra; retry." }
  const floors = []
  if (!spec.run_cmd || !spec.run_cmd.trim()) floors.push("run_cmd empty")
  if (rows.length && !rows.some(r => r.metric && spec.outcome_metric === r.metric)) floors.push("outcome_metric ≠ any row")
  if (floors.length) return { outcome: "spec_blocked", floors, spec }

  // GLM implement
  const IMPL_SCHEMA = {
    type: "object", required: ["worktree", "diff_path", "files", "deviations", "blockers", "smoke_passed"],
    properties: {
      worktree: { type: "string" }, diff_path: { type: "string" }, files: { type: "array", items: { type: "string" } },
      deviations: { type: "array", items: { type: "string" } }, blockers: { type: "array", items: { type: "string" } },
      smoke_passed: { type: "boolean" },
    },
  }
  const EXP_REPO = ROOTDIR + "/ugra-rgbd-robust"
  const WT = "/tmp/wt-" + M.id
  const DIFF_PATH = BUILD_DIR + "/diff.patch"
  const impl = await seat(
    "## Implement " + M.id + "\n## Spec (VERBATIM)\n" +
    JSON.stringify({ steps: spec.steps, run_cmd: spec.run_cmd, smoke_cmd: spec.smoke_cmd,
      eval_entry: spec.eval_entry, forbids: spec.forbids, result_contract: spec.result_contract }, null, 1).slice(0, 18000) +
    "\n## Substrate\n" + JSON.stringify(A.substrate || {}, null, 1).slice(0, 4000) +
    (A.fix && A.fix.findings && A.fix.findings.length ? "\n## Prior findings (fix each)\n" + JSON.stringify(A.fix.findings).slice(0, 6000) : "") +
    "\n## Task\n0. `[ -d " + WT + " ] || git -C " + EXP_REPO + " worktree add " + WT + " exp/" + M.id +
    " 2>/dev/null || git -C " + EXP_REPO + " worktree add " + WT + " -b exp/" + M.id + "`\n" +
    "1. Implement every step in " + WT + ". " + BUILD_DISCIPLINE + "\n" +
    "2. `cd " + WT + " && SMOKE=1 " + spec.smoke_cmd + "` — must reach eval and write seed_0.json.\n" +
    "3. `mkdir -p " + BUILD_DIR + " && git -C " + WT + " add -A && git -C " + WT + " diff --cached > " + DIFF_PATH + "`\n" +
    "You report files/deviations/blockers — NEVER results or verdicts.\n\nworktree=" + WT + " diff=" + DIFF_PATH + "\n\nStructured output only.",
    { label: "implement", phase: "Build", schema: IMPL_SCHEMA, model: MODEL.glm })
  if (!impl) return { error: "implement seat absent — infra; retry." }
  if (!impl.smoke_passed) return { id: M.id, outcome: "blocked", floors: ["smoke failed"],
    remedial: impl.blockers || ["SMOKE did not reach eval"] }

  // GLM one-pass probe+finders (NO separate verify seat — build discipline in the prompt)
  const CHECK_SCHEMA = {
    type: "object", required: ["diff_nonempty", "eval_entry_hunks", "smoke_seed_exists", "test_token_hits", "nan_or_inf", "findings"],
    properties: {
      diff_nonempty: { type: "boolean" }, eval_entry_hunks: { type: "number" },
      smoke_seed_exists: { type: "boolean" }, test_token_hits: { type: "array", items: { type: "string" } },
      nan_or_inf: { type: "boolean" },
      findings: { type: "array", maxItems: 8, items: { type: "object", required: ["summary", "severity", "failure_scenario"], properties: {
        summary: { type: "string" }, severity: { enum: ["critical", "high", "medium", "low"] },
        failure_scenario: { type: "string" }, file: { type: "string" }, line: { type: "number" } } } },
    },
  }
  const check = await seat(
    "## One-pass check (Bash + review, one seat)\n## Diff\n" + (impl.diff_path || DIFF_PATH) +
    "\n## Worktree\n" + impl.worktree + "\n## Spec\n" +
    JSON.stringify({ steps: spec.steps.slice(0, 8), eval_entry: spec.eval_entry, forbids: spec.forbids }) + "\n\n" +
    "First run the deterministic checks (report verbatim):\n" +
    "1. `wc -l <diff>` → diff_nonempty\n" +
    "2. `grep -c '^+++ .*" + (spec.eval_entry || "").split("/").pop() + "' <diff>` → eval_entry_hunks (only +++ lines)\n" +
    "3. `find " + impl.worktree + " -name 'seed_0.json' | head -1` → smoke_seed_exists\n" +
    "4. `grep -nE 'cal_test|test_half' <diff>` → test_token_hits\n" +
    "5. NaN check in results\n\n" +
    "Then review the diff against this discipline:\n" + BUILD_DISCIPLINE + "\n" +
    "Report only critical/high findings with a nameable failure_scenario. Empty findings = clean.\n\nStructured output only.",
    { label: "check", phase: "Build", schema: CHECK_SCHEMA, model: MODEL.glm })
  if (!check) return { error: "check seat absent — infra; retry." }
  let gateFloors = []
  if (!check.diff_nonempty) gateFloors.push("empty diff")
  if (check.eval_entry_hunks > 0) gateFloors.push("eval_entry has hunks")
  if (!check.smoke_seed_exists) gateFloors.push("no seed_0.json")
  if ((check.test_token_hits || []).length) gateFloors.push("test-half tokens")
  if (check.nan_or_inf) gateFloors.push("NaN/Inf")
  const blockers = (check.findings || []).filter(f => f.severity === "critical" || f.severity === "high")

  // one fix round if needed
  let implRef = impl
  if ((blockers.length || gateFloors.length) && !A.no_fix) {
    const fixed = await seat(
      "## Fix " + M.id + "\n## Floors\n" + gateFloors.join("; ") + "\n## Findings\n" + JSON.stringify(blockers) +
      "\nFix in " + implRef.worktree + ". Re-smoke, re-diff.\n\nStructured output only.",
      { label: "fix", phase: "Build", schema: IMPL_SCHEMA, model: MODEL.glm })
    if (fixed) implRef = fixed
    // re-check floors only (not full findings re-review)
    const recheck = await seat(
      "## Re-check floors only (Bash)\ndiff=" + (implRef.diff_path || DIFF_PATH) + " wt=" + implRef.worktree +
      "\n1. `wc -l <diff>` 2. `grep -c '^+++ .*" + (spec.eval_entry || "").split("/").pop() + "' <diff>` 3. seed_0.json 4. test-half 5. NaN\n\nStructured output only.",
      { label: "refloor", phase: "Build", schema: CHECK_SCHEMA, model: MODEL.glm })
    if (recheck) {
      gateFloors = []
      if (!recheck.diff_nonempty) gateFloors.push("empty diff")
      if (recheck.eval_entry_hunks > 0) gateFloors.push("eval_entry hunks")
      if (!recheck.smoke_seed_exists) gateFloors.push("no seed")
      if ((recheck.test_token_hits || []).length) gateFloors.push("test-half")
      if (recheck.nan_or_inf) gateFloors.push("NaN")
      const reBlockers = (recheck.findings || []).filter(f => f.severity === "critical" || f.severity === "high")
      if (reBlockers.length) gateFloors.push("still has critical/high findings after fix")
    }
  }
  if (blockers.length || gateFloors.length) {
    return { id: M.id, outcome: "blocked", floors: gateFloors, remedial: blockers.map(b => b.summary),
      stats: { agentCalls, byModel } }
  }

  // Grok CLI review (final gate — replaces the Sol verify cascade)
  const grokR = await grokReview(implRef.worktree, "Does this diff faithfully implement the spec? Any leakage, fake GT, or hardcoded results?")
  if (grokR && !grokR.unavailable && (grokR.findings || []).some(f => f.severity === "critical")) {
    return { id: M.id, outcome: "blocked", floors: ["Grok: critical finding"],
      findings: grokR.findings, remedial: grokR.findings.filter(f => f.severity === "critical").map(f => f.summary),
      stats: { agentCalls, byModel, grok: true } }
  }

  if (A.no_launch) return { id: M.id, outcome: "gate_passed", no_launch: true, spec,
    worktree: implRef.worktree, stats: { agentCalls, byModel, grok: grokR && !grokR.unavailable } }

  // launch
  const canaryEnv = (() => {
    for (const n of Object.keys((A.substrate || {}).frozen_hosts || {})) {
      const c = (A.substrate || {}).frozen_hosts[n].canary
      if (c && c.expected != null) return " --setenv=CANARY_EXPECTED=" + c.expected + " --setenv=CANARY_TOL=" + c.tol
    }
    return ""
  })()
  const launch = await seat(
    "## Launch " + M.id + "\n1. Read `" + ROOTDIR + "/.research/tools/launch_wrap.sh` (exit 3=canary 4=kill 5=infra).\n" +
    "2. systemd-run --user --unit=research-" + M.id + " --working-directory='" + implRef.worktree +
    "' --setenv=RESULTS_DIR=" + BUILD_DIR + "/results --setenv=SEEDS=" + (spec.seeds || "0") + canaryEnv +
    " bash " + ROOTDIR + "/.research/tools/launch_wrap.sh " + M.id + " " + M.id + " -- 'cd " + implRef.worktree +
    " && " + spec.run_cmd + "'\n3. `systemctl --user is-active research-" + M.id + "`.\n\nStructured output only.",
    { label: "launch", phase: "Build", schema: {
      type: "object", required: ["unit"], properties: { unit: { type: "string" }, diff_sha: { type: "string" } },
    }, model: MODEL.glm })
  if (!launch || !launch.unit) return { id: M.id, launch_error: "launch failed — retry" }
  return { id: M.id, outcome: "launched", unit: launch.unit, diff_sha: launch.diff_sha,
    worktree: implRef.worktree, spec, stats: { agentCalls, byModel, grok: grokR && !grokR.unavailable } }
}

// ═══ JUDGE ══════════════════════════════════════════════════════════════
if (MODE === "judge") {
  const spec = A.spec || {}
  phase("Judge")
  // GLM manifest (deterministic checks, GLM runs the Bash)
  const manifest = await seat(
    "## Manifest (Bash, verbatim)\n" +
    "1. `systemctl --user show research-" + M.id + " -p ExecMainStatus --value` → unit_exit\n" +
    "2. `find " + BUILD_DIR + "/results -name '*.json' | head -40` → result_files\n" +
    "3. Per-arm seed counts\n4. Metric keys\n5. Test-half read count\n6. NaN count\n7. sha8\n\nStructured output only.",
    { label: "manifest", phase: "Judge", schema: {
      type: "object", required: ["unit_exit", "result_files", "per_arm_seeds", "metric_keys", "test_half_reads", "nan_count"],
      properties: {
        unit_exit: { type: "number" }, result_files: { type: "array", items: { type: "string" } },
        per_arm_seeds: { type: "array", items: { type: "object", required: ["arm", "seed_files"], properties: {
          arm: { type: "string" }, seed_files: { type: "number" } } } },
        metric_keys: { type: "array", items: { type: "string" } },
        test_half_reads: { type: "number" }, nan_count: { type: "number" },
        extreme_metrics: { type: "array", items: { type: "string" } }, diff_sha8: { type: "string" },
      },
    }, model: MODEL.glm })
  if (!manifest) return { error: "manifest seat absent — infra; retry." }
  // JS deterministic: infra ≠ science
  if (manifest.unit_exit === 5) return { id: M.id, outcome: "infra_failure" }
  if (manifest.unit_exit === 3) return { id: M.id, outcome: "canary_fail" }
  if (manifest.unit_exit === 4) return { id: M.id, outcome: "early_kill" }
  const det = []
  if (manifest.nan_count > 0) det.push("NaN")
  if (manifest.test_half_reads > 1) det.push("test-half >1")
  for (const a of manifest.per_arm_seeds) if (a.seed_files === 0) det.push("arm " + a.arm + " no seed")
  if (det.length) return { id: M.id, outcome: "invalid_experiment", valid: false, det_floors: det,
    note: "deterministic invalidity — Claim unchanged" }

  // GLM recompute ∥ integrity ∥ grounding (one parallel wave; no Sol — GLM runs the scripts)
  const [recompute, integrity] = await parallel([
    () => seat(
      "## Recompute (Bash; recompute from raw files)\n## Result files\n" + JSON.stringify(manifest.result_files) +
      "\n## Spec\n" + JSON.stringify({ arms: spec.arms, outcome_metric: spec.outcome_metric, result_contract: spec.result_contract }) +
      "\n\nFor every arm, recompute the outcome metric from the raw files (write a short script, paste it in notes). " +
      "Then check: effect direction correct? Any metric suspiciously perfect (≈1.0)? Control arm also moved? " +
      "Margin within noise? Report triggers that fire.\n\nStructured output only.",
      { label: "recompute", phase: "Judge", schema: {
        type: "object", required: ["table", "triggers_fired"],
        properties: {
          table: { type: "array", items: { type: "object", required: ["arm", "metric", "value", "source"], properties: {
            arm: { type: "string" }, metric: { type: "string" }, value: { type: "string" }, source: { type: "string" } } } },
          triggers_fired: { type: "array", items: { type: "string" } }, notes: { type: "string" },
        },
      }, model: MODEL.glm }),
    () => seat(
      "## Integrity + grounding (one seat)\n" + JUDGE_DISCIPLINE +
      "\n## Result files\n" + JSON.stringify(manifest.result_files) +
      "\n## Worktree\n" + (A.worktree || "/tmp/wt-" + M.id) +
      "\n\nCheck A-F. Report only fails/warns (empty = clean).\n\nStructured output only.",
      { label: "integrity", phase: "Judge", schema: {
        type: "object", required: ["findings"],
        properties: { findings: { type: "array", maxItems: 8, items: { type: "object", required: ["check", "status"], properties: {
          check: { type: "string" }, status: { enum: ["pass", "warn", "fail"] }, evidence: { type: "string" } } } } },
      }, model: MODEL.glm }),
  ])
  if (!recompute || !integrity) return { error: "recompute/integrity seat absent — infra; retry." }
  const integrityFails = (integrity.findings || []).filter(f => f.status === "fail")
  if (integrityFails.length) return { id: M.id, outcome: "invalid_experiment", valid: false,
    det_floors: integrityFails.map(f => f.check), note: "integrity fail — Claim unchanged",
    stats: { agentCalls, byModel } }

  // GLM analysis (+ conditional K3 if triggers fired)
  const triggers = recompute.triggers_fired || []
  const analysisSeats = [
    () => seat(
      "## Analysis\n## Recompute table\n" + JSON.stringify(recompute.table, null, 1) +
      "\n## Claim rows\n" + JSON.stringify(rows) + "\n## Margin rule\n" + (C.margin_rule || "") +
      "\n\nFor each contract row this test targets: supports / refutes / inconclusive? Cite value+source. " +
      "What is the strongest counterargument, and does it change the Claim?\n\nStructured output only.",
      { label: "analysis", phase: "Judge", schema: {
        type: "object", required: ["row_evidence", "strongest_counterargument"],
        properties: {
          row_evidence: { type: "array", items: { type: "object", required: ["row_id", "verdict", "value"], properties: {
            row_id: { type: "string" }, verdict: { enum: ["supports", "refutes", "inconclusive", "not_tested"] },
            value: { type: "string" }, ci: { type: "string" }, source: { type: "string" } } } },
          strongest_counterargument: { type: "string" },
          counterargument_changes_claim: { type: "boolean" },
          unresolved_claim_edges: { type: "array", items: { type: "string" } },
        },
      }, model: MODEL.glm }),
  ]
  if (triggers.length) analysisSeats.push(() =>
    seat("## K3 prosecutor (triggers: " + triggers.join(", ") + ")\n## Table\n" + JSON.stringify(recompute.table) +
      "\n## Claim\n" + C.statement + "\n\nStrongest alternative explanation? NOT the judge.\n\nStructured output only.",
      { label: "k3:cond", phase: "Judge", schema: {
        type: "object", required: ["objection", "severity"],
        properties: { objection: { type: "string" }, severity: { enum: ["critical", "major", "minor"] } },
      }, model: MODEL.k3 }))
  const analysisOuts = await parallel(analysisSeats)
  const analysis = analysisOuts[0]
  const k3Obj = triggers.length ? analysisOuts[1] : null
  if (!analysis) return { error: "analysis seat absent — infra; retry." }

  // Grok CLI audit (final check — replaces Sol evidence verifier)
  const grokA = await grokAudit(BUILD_DIR,
    "Audit these experiment results. Check: (1) every number traces to a real file (2) no leakage or fake GT (3) the conclusion follows from the data (4) no counterargument ignored. Files: " +
    JSON.stringify(manifest.result_files.slice(0, 5)))

  // JS composes E (no separate verifier seat)
  const targetRows = new Set((A.sketch || {}).target_rows || [])
  const e = {
    experiment_id: M.id, test_id: (A.sketch || {}).test_id || M.id, valid: true,
    row_evidence: (analysis.row_evidence || []).map(r => ({ row_id: r.row_id, verdict: r.verdict, value: r.value, source: r.source })),
    integrity_flags: (integrity.findings || []).filter(f => f.status === "warn").map(f => f.check),
    strongest_counterargument: analysis.strongest_counterargument,
    k3_objection: k3Obj ? k3Obj.objection : null,
    grok_audit: grokA && !grokA.unavailable ? (grokA.verdict || grokA.output || "").slice(0, 2000) : null,
    unresolved_claim_edges: analysis.unresolved_claim_edges || [],
    artifacts: manifest.result_files, recompute_table: recompute.table,
  }
  // cross-family: K3 critical objection or Grok issue → downgrade supports to inconclusive for affected rows
  const k3Critical = k3Obj && k3Obj.severity === "critical"
  const grokIssues = grokA && !grokA.unavailable && (grokA.issues || []).length > 0
  if (k3Critical || grokIssues) {
    e.row_evidence = e.row_evidence.map(r =>
      r.verdict === "supports" ? { ...r, verdict: "inconclusive", downgraded_by: k3Critical ? "k3_critical" : "grok_issue" } : r)
  }
  const anyRefuted = e.row_evidence.some(r => r.verdict === "refutes" && targetRows.has(r.row_id))
  const allSupported = rows.length > 0 && rows.every(row =>
    (e.row_evidence.find(r => r.row_id === (row.id || row)) || {}).verdict === "supports")
  e.claim_strength = anyRefuted ? "refuted" : allSupported ? "supported" : "active"
  e.next_action = anyRefuted ? "claim_refuted" : allSupported ? "claim_supported" :
    (analysis.unresolved_claim_edges || []).length ? "plan_next" : "stop_inconclusive"
  return { id: M.id, outcome: "judged", e, stats: { agentCalls, byModel, k3: triggers.length > 0,
    grok: grokA && !grokA.unavailable } }
}

return { error: "unknown mode '" + MODE + "'" }
