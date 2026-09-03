// pivot.workflow.js — stage P: the stop rule fired; one explorer (K3) call for the four checks + cross-domain associations.
// args: { prompt }  from `bundle.py pivot`.  Returns { verdict, reasons, associations }. Then the human picks an exit.
export const meta = {
  name: 'pivot',
  description: 'One K3 call after the stop rule: critique what was tried, propose associations; the human decides the exit.',
  phases: [{ title: 'Pivot', detail: 'explorer (K3), once, board + notebook inline' }],
}
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const r = await agent(A.prompt + '\n\nStructured output only.', {
  agentType: 'explorer', label: 'pivot', phase: 'Pivot', stallMs: 900000,
  schema: { type: 'object', required: ['verdict', 'reasons', 'associations'],
    properties: { verdict: { enum: ['ship_incumbent', 'revise_claim', 'new_sources'] }, reasons: { type: 'array', items: { type: 'string' } }, associations: { type: 'array', items: { type: 'string' } } } },
})
return r || { verdict: null, reasons: [], associations: [], error: 'explorer returned nothing (infrastructure failure, not a verdict): re-run Workflow(pivot)' }
