// write.workflow.js — stage D: writer (GLM) per section from records, then one Grok review (the Opus polish pass was cut 2026-09-04:
// the writer owns register, the review flags `style:` issues without blocking). args: { sections: [ {path, prompt} ], review_prompt }
// from `bundle.py write`. Returns { written: [..], review }. Numbers are then script-checked by `gate.py numbers` (every number cites a record).
export const meta = {
  name: 'write',
  description: 'Sections rewritten from records in parallel (writer), then one final review (researcher).',
  phases: [
    { title: 'Sections', detail: 'writer (GLM), one agent per section, numbers only from records' },
    { title: 'Review', detail: 'researcher (Grok), once, artifact-aware' },
  ],
}
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const WRITTEN = { type: 'object', required: ['written'], properties: { written: { type: 'string' }, numbers_cited: { type: 'number' } } }

const written = (await parallel((A.sections || []).map((s) => () =>
  agent(s.prompt + '\n\nStructured output only.', { agentType: 'writer', label: `write:${s.path.split('/').pop()}`, phase: 'Sections', schema: WRITTEN, stallMs: 900000 })
))).filter(Boolean)
log(`sections: ${written.length}/${(A.sections || []).length} written`)

let review = null
if (A.review_prompt) review = await agent(A.review_prompt + '\n\nStructured output only.', {
  agentType: 'researcher', label: 'review', phase: 'Review', stallMs: 600000,
  schema: { type: 'object', required: ['verdict', 'issues'], properties: { verdict: { enum: ['pass', 'block'] }, issues: { type: 'array', items: { type: 'string' } } } },
})
if (A.review_prompt && !review) log('review returned nothing — infrastructure (step.py write --finish retries), not a verdict')
return { mode: A.mode || 'sections', written, review: review || null }
