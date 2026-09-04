// draft.workflow.js — outer loop: one writer (PATCH mode) per valid-fixable row, in parallel, returning an exact-string before/after
// patch (or a legal no-op that hands the row to the author). The script applies each patch exactly once, journals it, re-runs the
// numbers gate on the section and reverts on failure. Ids are injected by the script, never echoed by the agent.
// args: { round, rows: [{id, section, prompt}] }  from `step.py draft <n>`.
export const meta = {
  name: 'draft',
  description: 'Minimal exact-string patches for valid-fixable rows; the script applies, journals and gates them.',
  phases: [{ title: 'Draft', detail: 'writer (GLM) PATCH mode, one row per agent' }],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const PATCH = { type: 'object', required: ['before', 'after', 'rationale', 'no_op'], properties: { before: { type: 'string' }, after: { type: 'string' }, rationale: { type: 'string' }, no_op: { type: 'boolean' } } }

phase('Draft')
const patches = await parallel((A.rows || []).map((row) => () =>
  agent(row.prompt + '\n\nStructured output only.', { agentType: 'writer', label: `draft:${row.id}`, phase: 'Draft', schema: PATCH, stallMs: 900000 })
    .then((p) => ({ id: row.id, section: row.section, patch: p || null }))))
log(`draft round ${A.round}: ${patches.filter((p) => p && p.patch && !p.patch.no_op).length} patches · ${patches.filter((p) => p && p.patch && p.patch.no_op).length} no-op · ${patches.filter((p) => !p || !p.patch).length} null`)
return { round: A.round, patches: patches.filter(Boolean) }
