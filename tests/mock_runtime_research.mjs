// Mock-runtime smoke test for research.workflow.js v2 (speculative DR) — no real model calls.
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../workflows/research.workflow.js', import.meta.url), 'utf8')
  .replace(/^export /m, '')
const calls = []
const card = (id, ang) => ({
  id, title: "Paper " + id, text_path: "/tmp/" + id + ".txt", on_topic: true,
  summary: "summary " + id, mechanism_class: "family-X", angle: ang || "closest",
  residue: { what_not_done: "not d", abstract_level: false },
})
const claim = (n) => ({
  statement: "problem " + n, strategy: "mechanism " + n, target_metric: "mIoU", margin_rule: "beat control +1 CI95",
  contract_rows: [{ id: "primary", metric: "miou", threshold: "+1", direction: "higher_better" },
                  { id: "control", metric: "miou", threshold: "noise", direction: "within_tol" },
                  { id: "clean_cost", metric: "clean", threshold: "0.2", direction: "within_tol" }],
  premises: [{ statement: "p", kind: "evidence_backed", evidence_id: "p1" }, { statement: "q", kind: "bet_untested" }],
  naive_baseline: { version: "nv", branch: "false_premise" },
  steps: ["s1", "s2", "s3"],
  falsification_prediction: "exp; metric; var V; control restores outcome",
  signature_terms: ["a b", "c d", "e f"], alias_terms: ["g h", "i j"], compute_budget: "1 GPU-day",
})
const FIXTURE = (label) => {
  if (label === "reframe:opus" || label === "reframe:k3") return { reframes: [{
    pattern: "structural_prior_encoding", trigger: "failure X → encode prior → artifact A → metric",
    reframe: "worldview " + label.slice(8), bottleneck_hypothesis: "hyp", smallest_artifact: "artifact",
    queries: ["q1 " + label.slice(8), "q2 " + label.slice(8)] }] }
  if (label.startsWith("found:")) { const k = label.slice(6); return { cards: [card("f-" + k, k)] } }
  if (label === "routes:final") return { routes: [] }
  if (label === "routes:sol") return { routes: [
    { route_id: "R1", formal_object: "obj", naive_solution: "naive", transformation_changes: "changes",
      kill_observation: "obs", runnable: true, naive_suffices: false },
    { route_id: "R2", formal_object: "obj2", naive_solution: "naive2", transformation_changes: "changes2",
      kill_observation: "obs2", runnable: false, naive_suffices: false }] }
  if (label.startsWith("plan:")) return { queries: [
      { query: "plan query " + label, route_id: "R1", if_yes: "weakens", if_no: "viable" } ],
    routes: [{ id: "R1", status: "supported", evidence_ids: ["p1"], reason: "r" }] }
  if (label.startsWith("q:")) return { cards: [card("q" + calls.filter(c => c.startsWith("q:")).length)] }
  if (label === "digest") return { bottleneck_statement: "the failure is X", method_target: "target",
    surviving_patterns: ["structural_prior_encoding"], negative_knowledge_slice: "- gain confounded; - silent ceiling" }
  if (label === "sub:match") return { picks: [{ parent: "structural_prior_encoding", sub_or_none: "none" }] }
  if (label === "sketch") return { sketches: Array.from({ length: 4 }, (_, i) => ({
    statement_stub: "stub " + i, mechanism: "mech " + i, pattern: "structural_prior_encoding",
    naive_baseline: "nv" + i, why_not_naive: "because", target_row: "primary",
    signature_terms: ["s" + i], alias_terms: ["a" + i] })) }
  if (label === "prune") return { keep: [0, 1, 2] }
  if (label.startsWith("claim:")) return claim(label.slice(6))
  if (label.startsWith("coll:")) return { verdicts: [{ index: 0, collision: "NONE" }] }
  if (label === "prosecute") return { verdicts: [0, 1, 2].map(i => ({ index: i, call: "CLEAR" })) }
  if (label === "formal") return { verdicts: [0, 1, 2].map(i => ({ index: i, verdict: "PASS" })) }
  if (label.startsWith("fatal:")) return { collision: "NONE" }
  if (label === "pick") return { index: 0, rationale: "r" }
  throw new Error("unmocked seat: " + label)
}
const agentStub = async (prompt, opts) => {
  calls.push(opts.label)
  if (calls.filter(c => c === opts.label).length > 8) throw new Error("runaway on " + opts.label)
  return FIXTURE(opts.label)
}
const parallelStub = async thunks => (await Promise.all(thunks.map(f => Promise.resolve().then(f))))
const pipelineStub = async (items, ...stages) => parallelStub(items.map(item => async () => {
  let v = item
  for (const st of stages) v = await st(v, item)
  return v
}))
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const main = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', src)
const out = await main(
  { frozen: "TEST Anchor with keep rule: candidate > control CI95 excluding zero", round: 1 },
  agentStub, parallelStub, pipelineStub, t => console.log("── " + t), m => console.log("  " + m))
console.log("\n=== RESULT ===")
console.log("outcome:", out.outcome ?? out.error)
if (out.selected) console.log("selected.strategy:", out.selected.strategy, "| rows:", out.selected.contract_rows.length,
  "| sol:", out.selected.sol_verdict)
if (out.stats) console.log("stats:", JSON.stringify({ ...out.stats, byModel: undefined }))
console.log("seats (" + calls.length + "):", [...new Set(calls)].join(","))

// ─── hostile paths (HOSTILE=name[,name]) ───
if (process.env.HOSTILE) {
  const H = { }  // filled below
  globalThis.__h = {}
  const HARGS = {
    pattern_mismatch: [{ frozen: "TEST Anchor" }],
    coll_exact_on_2: [{ frozen: "TEST Anchor" }],
    fake_evidence: [{ frozen: "TEST Anchor" }],
    sol_hardkill: [{ frozen: "TEST Anchor" }],
  }
  const HFIX = {
    pattern_mismatch: { "sketch": { sketches: Array.from({length:4},(_,i)=>({
        statement_stub:"s"+i, mechanism:"m"+i, pattern:"some_other_pattern",
        naive_baseline:"nv", why_not_naive:"w", target_row:"primary",
        signature_terms:["x"+i], alias_terms:["y"+i] })) } },
    coll_exact_on_2: { "coll:2": { verdicts: [{ index: 0, collision: "EXACT", evidence: "prior" }] },
                       "coll:0": { verdicts: [{ index: 0, collision: "NONE" }] },
                       "coll:1": { verdicts: [{ index: 0, collision: "NONE" }] } },
    fake_evidence: { "plan:1": { queries: [], routes: [
        { id: "R1", status: "killed", evidence_ids: ["FAKE-ID-999"], reason: "fabricated" } ] } },
    sol_hardkill: { "formal": { verdicts: [0,1,2].map(i => ({ index: i, verdict: i === 1 ? "HARD_KILL" : "PASS", reason: "equivalent_to_naive" })) } },
  }
  for (const name of process.env.HOSTILE.split(",")) {
    calls.length = 0
    const base = FIXTURE
    const stub = async (prompt, opts) => {
      calls.push(opts.label)
      if (calls.filter(c => c === opts.label).length > 8) throw new Error("runaway on " + opts.label)
      if ((HFIX[name] || {})[opts.label] !== undefined) return HFIX[name][opts.label]
      return base(opts.label)
    }
    const m2 = new AsyncFunction('args','agent','parallel','pipeline','phase','log', src)
    const out = await m2({ frozen: "TEST Anchor with keep rule" }, stub, parallelStub, pipelineStub, ()=>{}, ()=>{})
    const o = out.outcome ?? out.error ?? "?"
    let extra = ""
    if (name === "fake_evidence" && out.routes) extra = " R1.status=" + (out.routes.find(r=>r.id==="R1")||{}).status
    if (name === "sol_hardkill" && out.selected) extra = " picked=" + out.selected.strategy
    if (name === "coll_exact_on_2" && out.selected) extra = " picked=" + out.selected.strategy + " killed=" + (out.stats.killed ?? "?")
    console.log(name.padEnd(18) + " → " + o + extra)
  }
}
