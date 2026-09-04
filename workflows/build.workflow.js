// build.workflow.js — stage C3+C4 in ONE workflow: the builder (GLM) implements the frozen spec in its worktree, then ONE external
// lens reads the diff: the Grok plugin code review (reviewer lane = thin forwarder). The GLM monitor lens was retired 2026-09-04
// (it stalled on large diffs and dead-locked the chain); spec coverage is now a script fact in gate.py (every step's file in the
// diff) and the review focus asks Grok to flag an unimplemented step as `high`. The builder never sees the lens; the lens never
// sees the builder's report. args: { qid, worktree, prompt, review_prompt }  from `bundle.py build <qid> [--fix]`.
// Returns { qid, build, monitor: { external } }. The orchestrator then runs `step.py build --finish <qid> <saved json>` (gate.py
// monitor → token → launch). A null or unavailable lens is never a verdict: step.py counts it as infrastructure and retries.
export const meta = {
  name: 'build',
  description: 'Builder implements one frozen spec; the Grok plugin reviews the diff; script checks coverage and gates the launch.',
  phases: [
    { title: 'Build', detail: 'builder (GLM) in the worktree; no self-reported verdict' },
    { title: 'Review', detail: 'reviewer (forwarder) → Grok plugin review --json' },
  ],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const RESULT = {
  type: 'object', required: ['files_changed', 'deviations', 'blockers', 'notes'],
  properties: {
    files_changed: { type: 'array', items: { type: 'string' } },
    deviations: { type: 'array', items: { type: 'object', required: ['step_id', 'reason'], properties: { step_id: { type: 'string' }, reason: { type: 'string' } } } },
    blockers: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}
const EXTERNAL = {
  type: 'object', required: ['available', 'findings'],
  properties: {
    available: { type: 'boolean' }, verdict: { type: 'string' }, raw: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', required: ['severity', 'file', 'line', 'text'],
      properties: { severity: { type: 'string' }, file: { type: 'string' }, line: { type: 'number' }, text: { type: 'string' } } } },
  },
}

phase('Build')
const b = await agent(A.prompt + '\n\nStructured output only.', { agentType: 'builder', label: `build:${A.qid}`, phase: 'Build', schema: RESULT, stallMs: 600000 })
if (!b) {
  log(`${A.qid}: builder returned nothing (infrastructure failure) — no review run`)
  return { qid: A.qid, build: null, monitor: { external: null }, error: 'builder returned nothing' }
}
log(`${A.qid}: ${b.files_changed.length} files changed · ${b.deviations.length} deviations · ${b.blockers.length} blockers`)

phase('Review')
const external = A.review_prompt
  ? await agent(A.review_prompt, { agentType: 'reviewer', label: `review:${A.qid}`, phase: 'Review', schema: EXTERNAL, stallMs: 900000 })
  : null
if (!external) log(`${A.qid}: external review returned nothing — infrastructure, not a verdict (step.py retries)`)
else log(`${A.qid}: review ${external.available ? (external.verdict || 'done') + ' · ' + external.findings.length + ' findings' : 'UNAVAILABLE'}`)
return { qid: A.qid, build: b, monitor: { external: external } }
