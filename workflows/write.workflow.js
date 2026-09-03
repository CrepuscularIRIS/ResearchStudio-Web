// write.workflow.js — stage D: writer (GLM) per section from records, then one Fable polish, then one Grok review.
// args: { sections: [ {path, prompt} ], polish_prompt, review_prompt }  from `bundle.py write`.
// Returns { written: [..], polish, review }. Numbers are then script-checked by `gate.py numbers` (every number cites a record).
export const meta = {
  name: 'write',
  description: 'Sections rewritten from records in parallel (writer), one register polish (scientist), one final review (researcher).',
  phases: [
    { title: 'Sections', detail: 'writer (GLM), one agent per section, numbers only from records' },
    { title: 'Polish', detail: 'scientist (Fable), once' },
    { title: 'Review', detail: 'researcher (Grok), once, artifact-aware' },
  ],
}
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const WRITTEN = { type: 'object', required: ['written'], properties: { written: { type: 'string' }, numbers_cited: { type: 'number' } } }

const written = (await parallel((A.sections || []).map((s) => () =>
  agent(s.prompt + '\n\nStructured output only.', { agentType: 'writer', label: `write:${s.path.split('/').pop()}`, phase: 'Sections', schema: WRITTEN, stallMs: 900000 })
))).filter(Boolean)
log(`sections: ${written.length}/${(A.sections || []).length} written`)

let polish = null, review = null
if (A.polish_prompt) polish = await agent(A.polish_prompt + '\n\nStructured output only.', { agentType: 'scientist', label: 'polish', phase: 'Polish', schema: WRITTEN, stallMs: 900000 })
if (A.review_prompt) review = await agent(A.review_prompt + '\n\nStructured output only.', {
  agentType: 'researcher', label: 'review', phase: 'Review', stallMs: 600000,
  schema: { type: 'object', required: ['verdict', 'issues'], properties: { verdict: { enum: ['pass', 'block'] }, issues: { type: 'array', items: { type: 'string' } } } },
})
if (!review) log('review returned nothing — treat as block (fail-closed)')
return { written, polish, review: review || { verdict: 'block', issues: ['reviewer returned nothing'] } }
