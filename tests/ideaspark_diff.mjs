// Differential test: for every fixture run dir, the workflow's decide() must pick the
// SAME step of the phase graph as upstream's own navigator (scripts/run.py next).
//
//   node ideaspark_diff.mjs <fixtures_dir> [workflow.js] [skill_dir]
//
// The workflow is loaded as a module by cutting it before the runtime sections (which
// need agent()/log()/parallel()), so decide() and STATE_PY are exercised exactly as
// generated — no reimplementation, no copy.
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const FX = path.resolve(process.argv[2] || '/tmp/ideaspark_fixtures')
const WF = path.resolve(process.argv[3] || path.join(process.cwd(), '.claude/workflows/ideaspark.workflow.js'))
if (!process.argv[4] && !process.env.RS_HOME) throw new Error('pass the upstream skill dir as argv[4] or set RS_HOME')
const SKILL = path.resolve(process.argv[4] || process.env.RS_HOME + '/skills/idea_spark')
const QUERY = 'operator substitution for long-horizon control'
const CUT = '// ─────────────────────────────────────────────────────────── 8. one run'

// upstream STEP text  →  the workflow step id that must answer it (first match wins)
const EQUIV = [
  [/^Phase 0: produce queries FIRST/, 'queries'],
  [/^Produce queries and re-invoke phase0/, 'queries'],
  [/^Phase 0\.4 — relevance partition/, 'partition'],
  [/^Phase 0\.4 — apply partition/, 'apply_partition'],
  [/^Phase 0 pattern_summary/, 'tagging'],
  [/^Phase 0\.5 — coverage check/, 'coverage'],
  [/^Phase 0\.5 — resolve \+ merge host refs/, 'add_host_refs'],
  [/^Phase 0\.5 — tag the admitted host refs/, 'tag_host'],
  [/^Phase 0\.5 — finalize coverage check/, 'coverage_done'],
  [/^Phase 0\+ full-text fetch/, 'fulltext'],
  [/^Phase 1 — bottleneck identification/, 'phase1'],
  [/^Write do_not_generate\.md/, 'dng'],
  [/^Phase 2\.1 \+ 2\.2/, 'ideate'],
  [/^Phase 2\.2 — sub-pattern picking/, 'generate'],
  [/^Fix the candidate before any Phase 3 work/, 'cite_fix'],
  [/^Redo Phase 2\.3/, 'coherence_redo'],
  [/^Phase 2\.3 — coherence gate/, 'coherence'],
  [/^Phase 2\.3 merger/, 'coherence_merge'],
  [/^Phase 3\.1 — dual-channel collision/, 'collision'],
  [/^Re-run Phase 3\.1 collision/, 'collision_restale'],
  [/^Fill signature_terms/, 'terms'],
  [/^Phase 3\.2 — audit-and-verdict/, 'audit'],
  [/^Re-run Phase 3\.2 WITH the blocking findings/, 'audit_undispositioned'],
  [/^Re-run Phase 3\.2 \(overwrite the report\) — invalidly-refuted/, 'audit_invalid_refutation'],
  [/^Re-run Phase 3\.2 \(overwrite the report\) — verdict must be/, 'audit_inconsistent'],
  [/^Refutation re-check/, 'recheck'],
  [/^Archive attempt 1 /, 'attempt_1'],
  [/^Archive attempt (\d+) and regenerate/, 'attempt_N'],
  [/^Archive attempt (\d+) \(incl\. phase1\)/, 'bottleneck_retry'],
  [/^Write phase_3_failed\.md/, 'p3f'],
  [/^Phase 3\.3 — emit the revision patch/, 'revise'],
  [/^Phase 3\.3 merger/, 'revise_merge'],
  [/^Falsification re-audit/, 'reaudit'],
  [/^Phase 4 skeleton/, 'skeleton'],
  [/^Phase 4\.fill/, 'fill'],
  [/^Fix fill_map/, 'fill_fix'],
  [/^Phase 4 assemble — partial/, 'assemble1'],
  [/^Phase 4\.derive/, 'derive'],
  [/^Phase 4 assemble — final merge/, 'assemble2'],
  [/^Phase 4 method-view extract/, 'method_view'],
  [/^Phase 4\.1\.5/, 'impl'],
  [/^Validate, then render/, 'validate'],
  [/^Return the cards inline/, 'DONE'],
  [/^Surface do_not_generate\.md/, 'TERMINAL_DNG'],
  [/^Surface phase_3_failed\.md/, 'TERMINAL_P3F'],
]

const expectFor = (step) => {
  for (const [re, id] of EQUIV) if (re.test(step)) return id
  return null
}

const src = fs.readFileSync(WF, 'utf8')
const cut = src.indexOf(CUT)
if (cut < 0) throw new Error('section marker not found in the generated workflow: ' + CUT)
const modSrc = 'globalThis.args = ' + JSON.stringify({ root: FX, direction: QUERY, skill_dir: SKILL }) + ';\n' +
  src.slice(0, cut).replace('export const meta', 'const meta') +
  '\nexport { decide, STATE_PY, SEATS, BANK, meta }\n'
const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'isdiff-')), 'mod.mjs')
fs.writeFileSync(tmp, modSrc)
const M = await import('file://' + tmp)

const dirs = fs.readdirSync(FX).filter((d) => fs.statSync(path.join(FX, d)).isDirectory()).sort()
let pass = 0
const fails = []
for (const name of dirs) {
  const dir = path.join(FX, name)
  let mine, theirs
  // a fixture may pin the two Phase 0 host-channel switches; both sides see the same environment
  const envFile = path.join(dir, '_ENV')
  const env = { ...process.env }
  if (fs.existsSync(envFile)) for (const l of fs.readFileSync(envFile, 'utf8').split('\n')) {
    const m = /^([A-Z_]+)=(.*)$/.exec(l.trim()); if (m) env[m[1]] = m[2]
  }
  try {
    const raw = execFileSync('python3', ['-', dir, SKILL], { input: M.STATE_PY, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env })
    const m = /__STATE__(\{[\s\S]*)$/.exec(raw)
    if (!m) throw new Error('no snapshot: ' + raw.slice(-300))
    const S = JSON.parse(m[1].trim())
    fs.writeFileSync(path.join(dir, '_snap.json'), m[1].trim())
    const step = M.decide(S, dir)
    mine = step.t === 'terminal' ? (/^DONE/.test(step.state) ? 'DONE' : (/do_not_generate/.test(step.state) ? 'TERMINAL_DNG' : 'TERMINAL_P3F')) : step.id
    if (step.t !== 'terminal') {
      if (!step.step) throw new Error('step has no STEP text: ' + JSON.stringify(step).slice(0, 200))
      if (step.t === 'seat' && !step.output) throw new Error('seat step has no OUTPUT: ' + step.id)
      if (step.t === 'seat' && !M.SEATS[step.seat]) throw new Error('unknown seat kind: ' + step.seat)
    }
  } catch (e) {
    fails.push([name, 'decide() threw', String(e.message).slice(0, 300)])
    continue
  }
  try {
    const out = execFileSync('python3', [path.join(SKILL, 'scripts/run.py'), 'next', '--dir', dir, '--query', QUERY],
      { encoding: 'utf8', timeout: 90000, maxBuffer: 64 * 1024 * 1024, env })
    const line = out.split('\n').find((l) => l.startsWith('STEP'))
    if (!line) throw new Error('upstream printed no STEP')
    theirs = line.replace(/^STEP\s*:\s*/, '').trim()
  } catch (e) {
    fails.push([name, 'upstream navigator failed', String(e.message).slice(0, 300)])
    continue
  }
  const want = expectFor(theirs)
  // upstream names one STEP for several distinct routes into it; normalize those families
  let got = mine
  if (/^attempt_\d+$/.test(mine) && want === 'attempt_N') got = 'attempt_N'
  if (/^(p3f|gate_failed)/.test(mine)) got = 'p3f'         // budget exhausted / bottleneck used / falsification / broken gate
  if (want === null) fails.push([name, 'no equivalence entry for upstream step', theirs])
  else if (want !== got) fails.push([name, 'DIVERGED', 'upstream="' + theirs + '" → expected id ' + want + ', workflow chose ' + got])
  else { pass++; console.log('  ok  ' + name.padEnd(30) + want.padEnd(24) + theirs.slice(0, 60)) }
}
// unit checks on decisions the fixtures cannot express (pool size drives the tagging fan-out)
const baseS = JSON.parse(fs.readFileSync(path.join(FX, '02_retrieved', '_snap.json'), 'utf8'))
for (const [n, want] of [[8, 0], [39, 0], [40, 2], [90, 3], [200, 3]]) {
  const S = JSON.parse(JSON.stringify(baseS))
  S.p0.n_papers = n
  S.p0.partition_applied = true            // skip 0.4 so the tagging step is the one under test
  const step = M.decide(S, path.join(FX, '02_retrieved'))
  const got = step.shards || 0
  if (step.id !== 'tagging') fails.push(['unit:shards', 'wrong step', 'n=' + n + ' → ' + step.id])
  else if (got !== want) fails.push(['unit:shards', 'wrong shard count', 'n=' + n + ' → ' + got + ', want ' + want])
  else { pass++; console.log('  ok  unit:shards n=' + String(n).padEnd(24) + 'shards=' + got) }
}
fs.rmSync(path.dirname(tmp), { recursive: true, force: true })
for (const [name, kind, detail] of fails) console.log('  FAIL ' + name + ': ' + kind + ' — ' + detail)
console.log((fails.length ? '[RED]' : '[GREEN]') + ' ideaspark_diff: ' + pass + '/' + (dirs.length + 5) + ' checks agree with the upstream navigator (' + dirs.length + ' fixtures + 5 unit)')
process.exit(fails.length ? 1 : 0)
