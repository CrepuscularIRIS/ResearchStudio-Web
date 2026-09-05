// Mock for experiment v3 (adaptive, no verify seats, Grok CLI)
import { readFileSync } from 'node:fs'
const src = readFileSync(new URL('../workflows/experiment.workflow.js', import.meta.url), 'utf8').replace(/^export /m, '')
const calls = []
const claim = { id: "CL-1", statement: "attenuation beats dropout", strategy: "per-position gating",
  target_metric: "mIoU", margin_rule: "beat control +1.5 CI95",
  contract_rows: [{ id: "primary", metric: "mIoU", threshold: "+1.5", direction: "higher_better" },
                  { id: "control", metric: "mIoU", threshold: "noise", direction: "within_tol" },
                  { id: "clean_cost", metric: "clean", threshold: "0.2", direction: "within_tol" }],
  naive_baseline: { version: "dropout", branch: "false_premise" }, falsification_prediction: "zeroing restores",
  premises: [], signature_terms: ["att"], alias_terms: ["conf"] }
const sketch = { test_id: "probe-01", target_rows: ["primary", "control"],
  hypothesis_edge: "if gating works mIoU improves", intervention: "zero gated residual",
  expected_if_claim: "+1.5", expected_if_anti_claim: "no change", kill_condition: "gain < noise",
  mde: "0.5", cost_gpu_h: 0.5, eval_only: true, canary: true, uses_dev_half_only: true }
const spec = { name: "p1", steps: ["s1","s2","s3"], run_cmd: "python eval.py", smoke_cmd: "python eval.py --smoke",
  eval_entry: "scripts/eval.py", outcome_metric: "mIoU", arms: ["att","dropout"], budget_gpu_h: 1,
  kind: "mve", result_contract: "results/<arm>.json:miou", seeds: "0", forbids: [] }
const FIX = (label) => {
  if (label.startsWith("plan:")) return label === "plan:pick" ? { index: 0, rationale: "r" } :
    { tests: [{ ...sketch }] }
  if (label === "spec") return { ...spec }
  if (label === "implement" || label === "fix") return { worktree: "/tmp/wt-CL-1", diff_path: "/tmp/d.p", files: ["a.py"], deviations: [], blockers: [], smoke_passed: true }
  if (label === "check" || label === "refloor") return { diff_nonempty: true, eval_entry_hunks: 0, smoke_seed_exists: true, test_token_hits: [], nan_or_inf: false, findings: [] }
  if (label === "grok:review") return { output: "clean", unavailable: false, findings: [] }
  if (label === "grok:audit") return { output: "pass", unavailable: false, verdict: "pass", issues: [] }
  if (label === "launch") return { unit: "research-CL-1" }
  if (label === "manifest") return { unit_exit: 0, result_files: ["r.json"], per_arm_seeds: [{arm:"att",seed_files:1},{arm:"dropout",seed_files:1}], metric_keys: ["miou"], test_half_reads: 1, nan_count: 0, extreme_metrics: [], diff_sha8: "a" }
  if (label === "recompute") return { table: [{arm:"att",metric:"mIoU",value:"50.1",source:"r.json"},{arm:"dropout",metric:"mIoU",value:"48.9",source:"r.json"}], triggers_fired: [] }
  if (label === "integrity") return { findings: [] }
  if (label === "analysis") return { row_evidence: [{row_id:"primary",verdict:"supports",value:"50.1",source:"r"},{row_id:"control",verdict:"supports",value:"tol",source:"r"}], strongest_counterargument: "single seed", counterargument_changes_claim: false, unresolved_claim_edges: ["clean_cost"] }
  if (label === "k3:cond") return { objection: "single seed", severity: "minor" }
  throw new Error("unmocked: " + label)
}
const stub = async (p, o) => { calls.push(o.label); return FIX(o.label) }
const par = async t => await Promise.all(t.map(f => f()))
const pipe = par
const AF = Object.getPrototypeOf(async function(){}).constructor
const main = new AF('args','agent','parallel','pipeline','phase','log', src)
const sub = { frozen_hosts: { D: { canary: { expected: 49.11, tol: 0.1 } } } }
const modes = [
  ["plan", { mode: "plan", claim, substrate: sub }],
  ["build", { mode: "build", claim, substrate: sub, sketch, no_launch: true }],
  ["judge", { mode: "judge", claim, substrate: sub, sketch, spec, method_id: "CL-1-p1" }],
]
let fail = 0
for (const [n, a] of modes) {
  calls.length = 0
  const out = await main(a, stub, par, pipe, ()=>{}, ()=>{})
  const o = out.outcome ?? out.error ?? "?"
  const ok = typeof o === "string" && !/error|absent/i.test(o)
  if (!ok) fail++
  let x = ""
  if (out.sketch) x = " sketch=" + out.sketch.test_id
  if (out.e) x = " strength=" + out.e.claim_strength + " grok=" + out.stats.grok
  console.log((ok?"PASS ":"FAIL ") + n.padEnd(8) + " → " + o + x + " (" + [...new Set(calls)].join(",") + ")")
}
console.log(fail === 0 ? "ALL PASS" : fail + " FAILED")
process.exit(fail ? 1 : 0)
