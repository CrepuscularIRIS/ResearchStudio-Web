export const meta = {
  name: 'webjudge',
  description: 'Score the web-track bottleneck cards with the three-judge idea_quality panel',
  phases: [{ title: 'Judge' }, { title: 'Aggregate' }],
}

// args: { cards?: [absolute .md paths], root?: <ideaspark run dir>, judges?: ['opus','sol','k3'], models?: {...} }
// The FINAL idea-quality panel, dispatched by the main agent AFTER the lite track and the local
// track are both complete and the cards are consolidated (local idea cards + downloaded web
// canvas cards). cards= judges exactly those files; otherwise root='s web/candidate_answers/*.md.
// Three judges in parallel (the ONLY parallel step), median + Borda aggregate.

const A = args || {}
const CARDS = (A.cards && A.cards.length) ? A.cards : null
const ROOT = A.root || null
if (!CARDS && !ROOT) throw new Error('pass args.cards (the consolidated card paths) or args.root (its web/candidate_answers/ is judged)')
const JUDGES = A.judges || ['opus', 'sol', 'k3']
const MODEL = Object.assign({ opus: 'claude-opus-5', glm: 'glm-5.3[1m]', k3: 'k3-256k', sol: 'gpt-5.6-sol' }, A.models || {})
const DIR = CARDS ? null : ROOT.replace(/\/+$/, '') + '/web/candidate_answers'

const NO_AUX = ['TaskCreate', 'TaskUpdate', 'TaskList', 'TaskGet', 'TaskStop', 'Agent', 'SendMessage',
  'ListAgents', 'AskUserQuestion', 'PushNotification', 'Monitor', 'CronCreate', 'CronList', 'CronDelete',
  'ScheduleWakeup', 'EnterPlanMode', 'ExitPlanMode', 'EnterWorktree', 'ExitWorktree', 'Skill', 'SendFeedback',
  'NotebookEdit', 'ToolSearch', 'TodoWrite']
const DENY = ['Bash', 'Edit', 'Write', 'WebFetch', 'WebSearch', 'Grep'].concat(NO_AUX)   // judges READ + Glob only

const SCHEMA = {
  type: 'object',
  properties: {
    cards: { type: 'array', items: { type: 'object', properties: {
      file: { type: 'string' }, A: { type: 'integer' }, B: { type: 'integer' }, C: { type: 'integer' },
      overall: { type: 'number' }, verdict: { type: 'string' }, why: { type: 'string' } },
      required: ['file', 'A', 'B', 'C', 'overall', 'verdict'] } },
    ranking: { type: 'array', items: { type: 'string' } },
    note: { type: 'string' },
  },
  required: ['cards', 'ranking'],
}

const K3_CLAMP = ' SEAT DISCIPLINE (binding): you have NO task-tracking tools and NO retry loop. Read each card ONCE, score it, move on. Elaborate reasoning happens in thinking; a note per card is ONE line. Any todo list or re-reading loop voids the seat.'

phase('Judge')
const pairs = (await parallel(JUDGES.map((m) => () => agent(
  'You are one of three independent judges of research cards from a two-track run: method IDEA '
  + 'cards from the audited local pipeline, and bottleneck-ANALYSIS cards from the web track (each a '
  + 'detailed mechanism-level analysis of one structural bottleneck or open gap).\n\n'
  + (CARDS
      ? 'Read EVERY one of these card files (paths, verbatim):\n' + CARDS.map((c) => '- ' + c).join('\n') + '\n'
      : 'Use Glob on ' + DIR + '/*.md to enumerate the cards, Read each one,\n')
  + 'and score EVERY card:\n'
  + '- A (1-5): novelty and depth — a structural mechanism insight, not a survey or a restatement\n'
  + '- B (1-5): validity — is the causal chain and its evidence sound; counter-evidence honestly weighed\n'
  + '- C (1-5): significance — do the stakes justify a method paper attacking this\n'
  + '- overall (0-100) and verdict: strong | borderline | weak, with a ONE-line why\n'
  + 'Then "ranking": the card FILES ordered by which line of attack is most worth committing a method '
  + 'paper to, best first.\n'
  + 'Judge blind to file name, order, length and polish — they are not evidence of quality. An honest '
  + 'weak verdict is worth more than a generous one.'
  + (MODEL[m] === MODEL.k3 ? K3_CLAMP : ''),
  { label: ('judge: ' + m).slice(0, 60), phase: 'Judge', schema: SCHEMA, model: MODEL[m],
    effort: MODEL[m] === MODEL.k3 ? 'medium' : 'high', disallowedTools: DENY })))).map((r, i) => ({ judge: JUDGES[i], r })).filter((p) => p.r)

phase('Aggregate')
const ok = pairs.map((p) => p.r)
if (!ok.length) throw new Error('every judge failed')
const med = (xs) => { const v = xs.filter((x) => typeof x === 'number').sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : null }
const files = [...new Set(ok.flatMap((r) => (r.cards || []).map((c) => c.file)))]
const agg = files.map((f) => {
  const per = ok.flatMap((r) => (r.cards || []).filter((c) => c.file === f))
  return { file: f, n_judges: per.length, overall_median: med(per.map((c) => c.overall)),
    A_mean: per.length ? per.reduce((t, c) => t + c.A, 0) / per.length : null,
    B_mean: per.length ? per.reduce((t, c) => t + c.B, 0) / per.length : null,
    C_mean: per.length ? per.reduce((t, c) => t + c.C, 0) / per.length : null,
    verdicts: per.map((c) => c.verdict) }
}).sort((a, b) => (b.overall_median ?? -1) - (a.overall_median ?? -1))
// Borda over the judges' rankings as the cross-check
const borda = {}
for (const r of ok) (r.ranking || []).forEach((f, i) => { borda[f] = (borda[f] || 0) + (r.ranking.length - i) })
const ranking = Object.entries(borda).sort((a, b) => b[1] - a[1]).map(([f]) => f)
log('webjudge: ' + files.length + ' card(s), ' + ok.length + '/' + JUDGES.length + ' judges; top = ' + (ranking[0] || agg[0]?.file || 'none'))

return {
  root: ROOT || null, cards: CARDS, dir: DIR, judges_ok: ok.length, judges_total: JUDGES.length,
  aggregate: agg, ranking_borda: ranking,
  per_judge: pairs.map((p) => ({ judge: p.judge, ranking: p.r.ranking, note: (p.r.note || '').slice(0, 300) })),
}
