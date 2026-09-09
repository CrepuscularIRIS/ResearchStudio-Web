export const meta = {
  name: 'webjudge',
  description: 'The three-judge idea_quality panel over a CONSOLIDATED card set — single-read design (one pre-assembled file, Read-only judges), immune to the Glob/Read retry loop',
  phases: [{ title: 'Assemble' }, { title: 'Judge' }, { title: 'Aggregate' }],
}

// args: { cards: [absolute .md paths] (REQUIRED), judges?: ['opus','sol','k3'], models?: {...} }
// 2026-09-09 fix — measured on the phyagentos run: the K3 judge burned 5054 transcript
// lines (~3 h) cycling Glob/Read while Opus and Sol finished in minutes. A prompt clamp
// cannot stop a tool loop. This version removes the loop surface mechanically:
//   1. ONE deterministic runner concatenates every card into review_set.md (## CARD headers)
//   2. judges get Read and NOTHING else — no Glob, no Grep, no Bash, no enumeration at all
//   3. one named file per judge; K3 runs at effort low with a single-read contract
// Even a misbehaving judge can now only re-read one file — minutes, not hours.

const A = args || {}
const CARDS = (A.cards && A.cards.length) ? A.cards : null
if (!CARDS) throw new Error('args.cards is required: the consolidated card paths (the /rs finish line writes this list; there is no root-scan mode any more)')
const ROOT = A.root || null
const JUDGES = A.judges || ['opus', 'sol', 'k3']
const MODEL = Object.assign({ opus: 'claude-opus-5', glm: 'glm-5.3[1m]', k3: 'k3-256k', sol: 'gpt-5.6-sol' }, A.models || {})
const DIR = ROOT ? ROOT.replace(/\/+$/, '') + '/web' : null
const SET = (DIR || '.') + '/review_set.md'

const NO_AUX = ['TaskCreate', 'TaskUpdate', 'TaskList', 'TaskGet', 'TaskStop', 'Agent', 'SendMessage',
  'ListAgents', 'AskUserQuestion', 'PushNotification', 'Monitor', 'CronCreate', 'CronList', 'CronDelete',
  'ScheduleWakeup', 'EnterPlanMode', 'ExitPlanMode', 'EnterWorktree', 'ExitWorktree', 'Skill', 'SendFeedback',
  'NotebookEdit', 'ToolSearch', 'TodoWrite']
const READ_ONLY = ['Bash', 'Edit', 'Write', 'WebFetch', 'WebSearch', 'Glob', 'Grep'].concat(NO_AUX)  // judges: Read, nothing else
const RUNNER_ONLY = ['Read', 'Edit', 'Write', 'WebFetch', 'WebSearch', 'Glob', 'Grep'].concat(NO_AUX)  // the assembler runner: Bash, nothing else
const RUNNER_SCHEMA = { type: 'object', properties: { rc: { type: 'integer' }, out: { type: 'string' } }, required: ['rc', 'out'] }

phase('Assemble')
const concatSrc = 'import sys, pathlib; out = pathlib.Path(sys.argv[1]); cards = sys.argv[2:]; parts = []\n' +
  'for c in cards:\n' +
  '    p = pathlib.Path(c); parts.append("# CARD " + p.name + "\\n\\n" + p.read_text(encoding="utf-8").strip() + "\\n\\n")\n' +
  'out.write_text("".join(parts), encoding="utf-8"); print("ASSEMBLED", len(cards), "cards,", out.stat().st_size, "bytes ->", out)'
const asm = await agent(
  'You are a shell runner. Execute EXACTLY this one command with the Bash tool, once, in the foreground, and return its exit code and output verbatim. Do nothing else — no edits, no extra commands, no file reading of your own.\n\n' +
  'Bash timeout: 60000 ms\n\n---- COMMAND ----\n' +
  'python3 - ' + JSON.stringify(SET) + ' ' + CARDS.map((c) => JSON.stringify(c)).join(' ') + ' <<\'PYEOF\'\n' + concatSrc + '\nPYEOF' +
  '\n---- END ----',
  { label: 'assemble review_set', phase: 'Assemble', schema: RUNNER_SCHEMA, model: MODEL.glm, effort: 'low', disallowedTools: RUNNER_ONLY })
if (!asm || asm.rc !== 0 || !/ASSEMBLED \d+ cards/.test(asm.out || '')) {
  throw new Error('review_set.md assembly failed: ' + ((asm && asm.out) || 'no result').slice(0, 400))
}
const cardNames = CARDS.map((c) => c.replace(/.*\//, ''))
log('webjudge: assembled ' + cardNames.length + ' card(s) -> ' + SET)

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

const K3_CLAMP = ' SEAT DISCIPLINE (binding, mechanically enforced): your ONLY tool is Read, and you may call it ONCE — on ' + SET + '. That single file contains every card under "# CARD <name>" headers. Read it once, score from what you hold, and never call any tool again. A second Read of any kind voids your seat.'

phase('Judge')
const pairs = (await parallel(JUDGES.map((m) => () => agent(
  'You are one of three independent judges of research cards from a two-track run: method IDEA '
  + 'cards from the audited local pipeline, and bottleneck-ANALYSIS cards from the web track. They are '
  + 'ALL in one file, each under a "# CARD <name>" header:\n  ' + SET + '\n'
  + 'Read that file (once). Score EVERY card:\n'
  + '- A (1-5): novelty and depth — a structural mechanism insight, not a survey or a restatement\n'
  + '- B (1-5): validity — is the causal chain and its evidence sound; counter-evidence honestly weighed\n'
  + '- C (1-5): significance — do the stakes justify a method paper attacking this\n'
  + '- overall (0-100) and verdict: strong | borderline | weak, with a ONE-line why\n'
  + 'In "cards", "file" is the card NAME from its "# CARD" header (all of them: '
  + cardNames.join(', ') + ').\n'
  + 'Then "ranking": the card NAMES ordered by which line of attack is most worth committing a method '
  + 'paper to, best first.\n'
  + 'Judge blind to card order, name and length — they are not evidence of quality. An honest weak '
  + 'verdict is worth more than a generous one.'
  + (MODEL[m] === MODEL.k3 ? K3_CLAMP : ''),
  { label: ('judge: ' + m).slice(0, 60), phase: 'Judge', schema: SCHEMA, model: MODEL[m],
    effort: MODEL[m] === MODEL.k3 ? 'low' : 'high', disallowedTools: READ_ONLY })))).map((r, i) => ({ judge: JUDGES[i], r })).filter((p) => p.r)

phase('Aggregate')
const ok = pairs.map((p) => p.r)
if (!ok.length) throw new Error('every judge failed')
const med = (xs) => { const v = xs.filter((x) => typeof x === 'number').sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : null }
const names = [...new Set(ok.flatMap((r) => (r.cards || []).map((c) => c.file)))]
const agg = names.map((f) => {
  const per = ok.flatMap((r) => (r.cards || []).filter((c) => c.file === f))
  return { card: f, n_judges: per.length, overall_median: med(per.map((c) => c.overall)),
    A_mean: per.length ? per.reduce((t, c) => t + c.A, 0) / per.length : null,
    B_mean: per.length ? per.reduce((t, c) => t + c.B, 0) / per.length : null,
    C_mean: per.length ? per.reduce((t, c) => t + c.C, 0) / per.length : null,
    verdicts: per.map((c) => c.verdict) }
}).sort((a, b) => (b.overall_median ?? -1) - (a.overall_median ?? -1))
const borda = {}
for (const r of ok) (r.ranking || []).forEach((f, i) => { borda[f] = (borda[f] || 0) + (r.ranking.length - i) })
const ranking = Object.entries(borda).sort((a, b) => b[1] - a[1]).map(([f]) => f)
log('webjudge: ' + names.length + ' card(s), ' + ok.length + '/' + JUDGES.length + ' judges; top = ' + (ranking[0] || agg[0]?.card || 'none'))

return {
  root: ROOT, cards: CARDS, review_set: SET, judges_ok: ok.length, judges_total: JUDGES.length,
  aggregate: agg, ranking_borda: ranking,
  per_judge: pairs.map((p) => ({ judge: p.judge, ranking: p.r.ranking, note: (p.r.note || '').slice(0, 300) })),
}
