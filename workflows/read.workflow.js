// read.workflow.js — outer loop, one round: three referees (critic-sol ∥ critic-k3 ∥ critic-glm, REFEREE mode) read the manuscript
// quoted in the prompt and file anchored weaknesses plus per-section coverage. Isolated: no files, no ledger, no prior rounds.
// The script (`step.py read --finish`) locates every anchor in a passage (cannot quote = not filed), dedups by passage + wording,
// intakes into the ledger and routes. args: { round, panel: {sol, k3, glm}, sections, prompt }  from `step.py read <n>`.
export const meta = {
  name: 'read',
  description: 'Three-family referee panel over the current manuscript; anchored weaknesses and coverage; the script files and routes.',
  phases: [{ title: 'Referees', detail: 'critic-sol ∥ critic-k3 ∥ critic-glm, whole manuscript inline, isolated' }],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const WEAK = {
  type: 'object', required: ['weaknesses', 'per_section_coverage', 'overall_confidence'],
  properties: {
    weaknesses: { type: 'array', items: { type: 'object', required: ['summary', 'evidence_anchor', 'section', 'significance', 'kind'],
      properties: { summary: { type: 'string' }, evidence_anchor: { type: 'string' }, section: { type: 'string' },
        significance: { enum: ['major', 'minor'] }, kind: { enum: ['substantive', 'mechanical'] }, references: { type: 'string' } } } },
    per_section_coverage: { type: 'array', items: { type: 'object', required: ['section', 'status', 'in_section_quote'],
      properties: { section: { type: 'string' }, status: { enum: ['thorough', 'light', 'skipped'] }, in_section_quote: { type: 'string' } } } },
    overall_confidence: { type: 'number' },
  },
}
const panel = A.panel || { sol: 'critic-sol', k3: 'critic-k3', glm: 'critic-glm' }
const keys = Object.keys(panel)

phase('Referees')
const res = await parallel(keys.map((k) => () =>
  agent(A.prompt + '\n\nStructured output only.', { agentType: panel[k], label: `referee:${k}:r${A.round}`, phase: 'Referees', schema: WEAK, stallMs: 900000 })))
const out = {}
keys.forEach((k, i) => { out[k] = res[i] || null; if (!res[i]) log(`referee ${k}: returned nothing (infrastructure, not a verdict)`) })
log(`read round ${A.round}: ${keys.filter((k) => out[k]).length}/${keys.length} referees · ${keys.reduce((s, k) => s + ((out[k] || {}).weaknesses || []).length, 0)} weaknesses filed before anchoring`)
return { round: A.round, panel: out }
