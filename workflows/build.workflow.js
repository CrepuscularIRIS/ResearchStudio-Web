// build.workflow.js — stage C3+C4 in ONE workflow: the builder (GLM) implements the frozen spec in its worktree, then two independent
// lenses read the diff: the Grok monitor (coverage per spec step + leakage findings, every claim quoting diff lines) and the Codex
// code review (external CLI). The builder never sees the lenses; the lenses never see the builder's report.
// args: { qid, worktree, prompt, monitor_prompt, codex_prompt }  from `bundle.py build <qid> [--fix]`.
// Returns { qid, build, monitor: { grok, codex } }. The orchestrator then runs `step.py build --finish <qid> <saved json>`, which
// verifies every quoted line against the real diff (gate.py monitor), writes the token and launches. Null lenses are never verdicts:
// a null Grok fails closed (no launch), a null Codex is skipped.
export const meta = {
  name: 'build',
  description: 'Builder implements one frozen spec; then Grok monitor and Codex review read the diff in parallel; quotes are verified by script afterwards.',
  phases: [
    { title: 'Build', detail: 'builder (GLM) in the worktree; no self-reported verdict' },
    { title: 'Monitor', detail: 'researcher (Grok) coverage/leakage lens ∥ reviewer (Codex) code review' },
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
const GROK = {
  type: 'object', required: ['approved', 'coverage', 'findings'],
  properties: {
    approved: { type: 'boolean' },
    coverage: { type: 'array', items: { type: 'object', required: ['step_id', 'status', 'diff_lines'],
      properties: { step_id: { type: 'string' }, status: { enum: ['implemented', 'missing', 'changed'] }, diff_lines: { type: 'array', items: { type: 'string' } } } } },
    findings: { type: 'array', items: { type: 'object', required: ['kind', 'diff_lines', 'text'],
      properties: { kind: { enum: ['leak', 'protected', 'hardcode', 'held_out_in_training', 'contract', 'extra_mechanism'] }, diff_lines: { type: 'array', items: { type: 'string' } }, text: { type: 'string' } } } },
  },
}
const CODEX = {
  type: 'object', required: ['available', 'findings'],
  properties: {
    available: { type: 'boolean' }, raw: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', required: ['severity', 'file', 'line', 'text'],
      properties: { severity: { type: 'string' }, file: { type: 'string' }, line: { type: 'number' }, text: { type: 'string' } } } },
  },
}

phase('Build')
const b = await agent(A.prompt + '\n\nStructured output only.', { agentType: 'builder', label: `build:${A.qid}`, phase: 'Build', schema: RESULT, stallMs: 600000 })
if (!b) {
  log(`${A.qid}: builder returned nothing (infrastructure failure) — no monitor run`)
  return { qid: A.qid, build: null, monitor: { grok: null, codex: null }, error: 'builder returned nothing' }
}
log(`${A.qid}: ${b.files_changed.length} files changed · ${b.deviations.length} deviations · ${b.blockers.length} blockers`)

phase('Monitor')
const [grok, codex] = await parallel([
  () => agent(A.monitor_prompt + '\n\nStructured output only.', { agentType: 'researcher', label: `monitor:${A.qid}`, phase: 'Monitor', schema: GROK, stallMs: 600000 }),
  () => A.codex_prompt ? agent(A.codex_prompt, { agentType: 'reviewer', label: `codex:${A.qid}`, phase: 'Monitor', schema: CODEX, stallMs: 900000 }) : Promise.resolve(null),
])
if (!grok) log(`${A.qid}: Grok lens returned nothing — the gate will not approve (fail-closed)`)
if (!codex) log(`${A.qid}: Codex lens unavailable — skipped, not a verdict`)
log(`${A.qid}: grok ${grok ? (grok.approved ? 'APPROVED' : 'REJECTED') : 'null'} (${grok ? grok.findings.length : 0} findings) · codex ${codex && codex.available ? codex.findings.length + ' findings' : 'skipped'}`)
return { qid: A.qid, build: b, monitor: { grok: grok || { approved: false, coverage: [], findings: [] }, codex: codex || { available: false, findings: [] } } }
