// trial.workflow.js — outer loop: per in-trial charge, DEFENSE (critic-glm, whole paper) → 5 JURORS in parallel (critic-glm ×3
// framings, critic-k3, critic-sol; local passage + claim spine) → deterministic quorum (surviving ≥ ceil(0.8·n) AND one side > 60%
// of surviving; context-limited votes do not count) → on `valid`, the JUDGE (critic-sol) routes valid-fixable (a close_criterion an
// editor can satisfy with NO new experiment, measurement, number or citation) or needs-data. Undecided → one re-run with 7 jurors;
// still undecided or all context-limited → author-required. Charges run through the pipeline independently.
// args: { round, panel, jury: [[family, framing]], quorum, majority, persona, isolation, charges: [{id, summary, evidence_anchor,
//         section, passage, significance, raised_by}], paper }  from `step.py trial <n>`.
export const meta = {
  name: 'trial',
  description: 'Per-charge trial: defense → decorrelated jurors → quorum by script → judge routes fixable vs needs-data.',
  phases: [{ title: 'Defense' }, { title: 'Jury' }, { title: 'Judge' }],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const panel = A.panel || { sol: 'critic-sol', k3: 'critic-k3', glm: 'critic-glm' }
const DEF = { type: 'object', required: ['grounds', 'argument', 'where'], properties: { grounds: { enum: ['addressed-in-text', 'out-of-scope', 'would-drift-anchor', 'severity-overstated', 'charge-stands'] }, argument: { type: 'string' }, where: { type: 'string' } } }
const VOTE = { type: 'object', required: ['vote', 'reason', 'need'], properties: { vote: { enum: ['valid', 'invalid', 'context-limited'] }, reason: { type: 'string' }, need: { type: 'string' } } }
const ROUTE = { type: 'object', required: ['route', 'close_criterion', 'rationale'], properties: { route: { enum: ['valid-fixable', 'needs-data'] }, close_criterion: { type: 'string' }, rationale: { type: 'string' } } }

const charge = (c) => [`## Charge ${c.id} (${c.significance}, raised by ${(c.raised_by || []).join(', ')})`, `summary: ${c.summary}`, `evidence_anchor: "${c.evidence_anchor}"`, `section: ${c.section}`].join('\n')
const defensePrompt = (c) => [A.isolation, '', 'MODE: DEFENSE', A.persona,
  'You are the DEFENSE (the author\'s advocate) in a per-issue review trial. You have the WHOLE paper. Steelman it against ONE charge WITH EVIDENCE. Crucially, SCAN THE WHOLE PAPER for whether the charge is already addressed elsewhere (a different section, a footnote). Pick grounds: addressed-in-text (cite WHERE), out-of-scope (name the norm), would-drift-anchor (name the frozen sentence a fix harms), severity-overstated, or charge-stands (concede). Be honest.',
  '', charge(c), '', '## Paper', A.paper].join('\n')
const jurorPrompt = (c, d, framing) => [A.isolation, '', 'MODE: JUROR', A.persona,
  'You are a TRIAL JUROR deciding whether the paper is GUILTY of one alleged flaw (is the charge VALID). You hear BOTH sides. Judge from THIS framing:', `  ${framing}`,
  'Vote `valid` (the paper really has this flaw), `invalid` (it does not), or `context-limited` if you genuinely cannot decide from the context shown — then set `need` to the exact section/material you need (else need=""). Do not guess on missing context; do not convict on a weak charge or acquit a real flaw because the defense is glib.',
  '', charge(c), '', '## The passage the charge rests on', c.passage || '(no local passage)', '', '## Defense', `grounds: ${d ? d.grounds : 'none (defense unavailable)'}`, d ? d.argument : '', d && d.where ? `where: ${d.where}` : ''].join('\n')
const judgePrompt = (c, votes) => [A.isolation, '', 'MODE: JUDGE', A.persona,
  'You are the PRESIDING JUDGE. The jury found this charge VALID by a clear majority. You do NOT re-litigate validity. ROUTE it:',
  '- valid-fixable: it can be closed by EDITING EXISTING TEXT (reword, restrict/soften a claim to match the evidence, surface info already present). Set close_criterion = one sentence an editor can satisfy with NO new experiment, measurement, number, or citation.',
  '- needs-data: closing it needs NEW data / an experiment / a number the records do not hold. Set close_criterion = the main-table cell it must fill (network × condition × metric). If it could be closed EITHER by new data OR by an honest text-only softening, PREFER the text-only fix and route valid-fixable.',
  '', charge(c), '', '## Jury reasons', ...votes.map((v) => `- ${v.vote}: ${v.reason}`), '', '## The passage', c.passage || ''].join('\n')

async function jury(c, d, seats, tag) {
  const votes = (await parallel(seats.map(([fam, framing], i) => () =>
    agent(jurorPrompt(c, d, framing) + '\n\nStructured output only.', { agentType: panel[fam], label: `juror:${c.id}:${fam}${i}`, phase: 'Jury', schema: VOTE, stallMs: 600000 })))).map((v) => v || { vote: 'context-limited', reason: 'juror returned nothing', need: '' })
  const surviving = votes.filter((v) => v.vote !== 'context-limited')
  const need = Math.ceil((A.quorum || 0.8) * seats.length)
  let decision = 'undecided'
  if (surviving.length >= need) {
    const valid = surviving.filter((v) => v.vote === 'valid').length
    if (valid > (A.majority || 0.6) * surviving.length) decision = 'valid'
    else if (surviving.length - valid > (A.majority || 0.6) * surviving.length) decision = 'invalid'
  }
  return { votes, tally: { valid: surviving.filter((v) => v.vote === 'valid').length, invalid: surviving.filter((v) => v.vote === 'invalid').length, context_limited: votes.length - surviving.length, size: seats.length }, decision, tag }
}

const extra = [['glm', 'internal consistency (does the charge survive a read of the whole passage and its neighbours?)'], ['sol', 'venue norms (would a careful reviewer at this venue raise this, or is it nitpicking?)']]

async function tryCharge(c) {
  phase('Defense')
  const d = await agent(defensePrompt(c) + '\n\nStructured output only.', { agentType: panel.glm, label: `defense:${c.id}`, phase: 'Defense', schema: DEF, stallMs: 600000 })
  let j = await jury(c, d, A.jury || [], 'tier-5')
  let escalated = false
  if (j.decision === 'undecided') { escalated = true; j = await jury(c, d, (A.jury || []).concat(extra), 'tier-7') }
  if (j.decision === 'invalid') return { id: c.id, verdict: 'invalid-drop', tally: j.tally, escalated, defense: d, rationale: 'jury: invalid by majority' }
  if (j.decision === 'undecided') return { id: c.id, verdict: 'author-required', tally: j.tally, escalated, defense: d, rationale: 'jury undecided after escalation (or context-limited)' }
  const r = await agent(judgePrompt(c, j.votes) + '\n\nStructured output only.', { agentType: panel.sol, label: `judge:${c.id}`, phase: 'Judge', schema: ROUTE, stallMs: 600000 })
  if (!r) return { id: c.id, verdict: null, tally: j.tally, escalated, defense: d, rationale: 'judge returned nothing (still in-trial)' }
  return { id: c.id, verdict: r.route, close_criterion: r.close_criterion, tally: j.tally, escalated, defense: d, rationale: r.rationale }
}

const verdicts = (await parallel((A.charges || []).map((c) => () => tryCharge(c)))).filter(Boolean)
log(`trial round ${A.round}: ${verdicts.map((v) => `${v.id}=${v.verdict}`).join(' · ')}`)
return { round: A.round, verdicts }
