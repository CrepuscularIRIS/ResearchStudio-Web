// critique.workflow.js — the three-family critique panel: critic-sol (GPT 5.6 sol) ∥ critic-k3 (Kimi K3) ∥ critic-glm (GLM 5.3),
// same prompt, isolated, parallel. Slot 1 (mode 'sources'): every eligible mechanism-map source without a critique. Slot 2 (mode
// 'spec'): one gated spec, blind to Slot 1. The panel proposes; `step.py critique --finish` aggregates by script (anchored findings
// only; majority drop for sources, worst verdict for a spec) and writes the map / .research/critique/<qid>.json. A null family is
// never a verdict. args: { mode, qid?, ids?, panel: {sol, k3, glm}, prompt }  from `step.py critique {sources | spec <qid>}`.
export const meta = {
  name: 'critique',
  description: 'Three-family critique panel (sol ∥ K3 ∥ GLM) over mechanism-map sources or one spec; script aggregates afterwards.',
  phases: [{ title: 'Panel', detail: 'critic-sol ∥ critic-k3 ∥ critic-glm, same prompt, isolated' }],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const SOURCES = {
  type: 'object', required: ['sources'],
  properties: { sources: { type: 'array', items: { type: 'object', required: ['id', 'verdict', 'rank', 'checks'],
    properties: { id: { type: 'string' }, verdict: { enum: ['keep', 'drop', 'uncertain'] }, rank: { type: 'number' },
      checks: { type: 'array', items: { type: 'object', required: ['name', 'result', 'anchor', 'why'],
        properties: { name: { enum: ['naive_baseline', 'recipe_not_gist', 'graveyard_precedent', 'falsifiable_at_scale'] },
          result: { enum: ['pass', 'fail', 'unclear'] }, anchor: { type: 'string' }, why: { type: 'string' } } } } } } } },
}
const SPEC = {
  type: 'object', required: ['verdict', 'findings', 'revision_target'],
  properties: { verdict: { enum: ['advance', 'revise', 'abandon'] }, revision_target: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', required: ['check', 'severity', 'quote', 'text'],
      properties: { check: { enum: ['recipe_application', 'falsification_structure', 'naive_equivalence', 'collision', 'feasibility'] },
        severity: { enum: ['blocking', 'major', 'minor'] }, quote: { type: 'string' }, text: { type: 'string' } } } } },
}
const schema = A.mode === 'spec' ? SPEC : SOURCES
const panel = A.panel || { sol: 'critic-sol', k3: 'critic-k3', glm: 'critic-glm' }
const keys = Object.keys(panel)

phase('Panel')
const res = await parallel(keys.map((k) => () =>
  agent(A.prompt + '\n\nStructured output only.', { agentType: panel[k], label: `critique:${k}${A.qid ? ':' + A.qid : ''}`, phase: 'Panel', schema, stallMs: 900000 })))
const out = {}
keys.forEach((k, i) => { out[k] = res[i] || null; if (!res[i]) log(`critique ${k}: returned nothing (infrastructure, not a verdict)`) })
log(`critique ${A.mode || 'sources'}: ${keys.filter((k) => out[k]).length}/${keys.length} families answered`)
return { mode: A.mode || 'sources', qid: A.qid || null, panel: out }
