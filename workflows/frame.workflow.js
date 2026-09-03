// frame.workflow.js — stage A: the scientist (Fable) reads the manuscripts named in the bundle and writes CLAIM.md.
// args: { prompt }  from `bundle.py A`.  Returns { written }.  The human then reviews; stage B runs next.
export const meta = {
  name: 'frame',
  description: 'One Fable call: from the two manuscripts, the records and the local library, write CLAIM.md (one claim, insight, evidence table, rules, seed methods).',
  phases: [{ title: 'Frame', detail: 'scientist (Fable), reads only the bundle paths, writes CLAIM.md' }],
}
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const r = await agent(A.prompt + '\n\nStructured output only.', {
  agentType: 'scientist', label: 'frame', phase: 'Frame',
  schema: { type: 'object', required: ['written'], properties: { written: { type: 'string' } } },
})
if (!r) return { written: '', error: 'scientist returned nothing' }
log(`frame: wrote ${r.written}`)
return r
