// Mock runtime for brain.workflow.js: no models, no files. The runner agent is replaced by a
// scripted ResearchStudio state machine (a happy-path port of run.py next over an in-memory
// file set); seats mark their OUTPUT paths as written. Asserts the control flow the TS owns:
// intake → shared Phase 0 → spawn → Phase 1 only on r1 → 2.1+2.2 serialized with the dedup
// line → collision launched before 2.3 and awaited after → Phase 4 chain → DONE → Phase 5 → rank.
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../../.claude/workflows/brain.workflow.js', import.meta.url), 'utf8').replace(/^export /m, '')
const ROOT = '/mock/root', SK = '/mock/rs', SHARED = ROOT + '/_shared', P0 = SHARED + '/phase0'
const RSCMD = `python3 '${SK}/scripts/run.py'`
const F = new Set()
const has = (p) => F.has(p)
const add = (...ps) => ps.forEach((p) => F.add(p))
const calls = []
let validateFailed = false, forceRc = 0, placeholderSent = false
const fail = (m) => { console.error('ASSERTION FAILED: ' + m); process.exit(1) }
const assert = (c, m) => { if (!c) fail(m) }

// ---------------------------------------------------------------- scripted navigator (advance path)
function emit(o) {
  const L = ['━'.repeat(72), `STATE  : ${o.state}`, `STEP   : ${o.step}`, `TYPE   : ${o.kind}`]
  if (o.kind === 'llm_subagent') {
    L.push('DO     : Run in a FRESH sub-agent (never the parent context)')
    if (o.prompt) L.push(`PROMPT : ${o.prompt}`)
    ;(o.inputs || []).forEach((x, i) => L.push(i ? `         ${x}` : `INPUT  : ${x}`))
    if (o.output) L.push(`OUTPUT : ${o.output}`)
  }
  ;(o.run || []).forEach((c, i) => L.push(i ? `         ${c}` : `RUN    : ${c}`))
  if (o.notes) L.push(`NOTES  : ${o.notes}`)
  if (o.kind !== 'terminal') L.push(`THEN   : ${RSCMD} next --dir "${o.rd}"`)
  L.push('━'.repeat(72))
  return L.join('\n')
}
const P = (rd, rel) => `${rd}/${rel}`
function siblingLine(rd) {
  const sibs = ['r1', 'r2', 'r3'].map((x) => `${ROOT}/${x}`).filter((x) => x !== rd && has(P(x, 'phase2_generate/phase2_generate_output.json')))
  if (!sibs.length) return null
  return 'CROSS-RUN DEDUP (soft negative anchors — see the OPTIONAL cross-run input in ideate_select.txt): recent sibling runs already produced these mechanisms; do NOT re-propose the same mechanism family unless this direction demands it AND the delta is stated explicitly: ' + sibs.map((s) => `[${s.split('/').pop()}] "Mock title" (t1, t2)`).join(' | ')
}
function navigate(rd) {
  const ref = `${SK}/references`, pr = `${ref}/system-prompts`, p0 = P(rd, 'phase0')
  const cards = ['idea.std.zh.md', 'idea.std.en.md', 'idea.detail.en.md'].map((c) => P(rd, 'phase4/' + c))
  if (cards.every(has)) return emit({ rd, state: 'DONE — all three idea cards rendered.', step: 'Return the cards inline', kind: 'terminal', notes: 'Read all three files and return them' })
  if (!has(p0 + '/lit_results.json')) return emit({ rd, state: 'Fresh run — no literature retrieved yet.', step: 'Phase 0: produce queries FIRST, then run retrieval', kind: 'llm_subagent', prompt: ref + '/intent-recognition.md (Map mode)', inputs: ['the user query'], output: '4-6 search queries', run: [`${RSCMD} phase0 --query "q" --queries "q1|q2" --out "${p0}/"`] })
  if (!has(p0 + '/lit_table.md')) return emit({ rd, state: 'Papers retrieved; lit_table.md not yet written.', step: 'Phase 0 pattern_summary (host-LLM step)', kind: 'llm_subagent', prompt: ref + '/pattern-summary-rubric.md', inputs: [p0 + '/lit_results.json'], output: p0 + '/lit_table.md' })
  if (!has(p0 + '/fulltext_cache.json')) return emit({ rd, state: 'lit_table.md written; full-text cache missing.', step: 'Phase 0+ full-text fetch', kind: 'bash', run: [`${RSCMD} phase0_fulltext --out "${p0}/"`] })
  const p1 = P(rd, 'phase1/phase1_output.json')
  if (!has(p1)) return emit({ rd, state: 'Phase 0 complete.', step: 'Phase 1 — bottleneck identification', kind: 'llm_subagent', prompt: pr + '/bottleneck_identify.txt', inputs: ['the user query + intake context', p0 + '/lit_table.md', p0 + '/fulltext_cache.json — cheaper access: read ' + p0 + '/fulltext/index.json first', p0 + '/lit_results.json'], output: p1, notes: 'Routing signal to return: `state` (proceed | do_not_generate).' })
  const p2s = P(rd, 'phase2_select/phase2_select_output.json'), p2g = P(rd, 'phase2_generate/phase2_generate_output.json')
  if (!has(p2s) || !has(p2g)) {
    const cross = siblingLine(rd)
    return emit({ rd, state: 'Phase 1 complete (state=proceed).', step: 'Phase 2.1 + 2.2 — ONE sub-agent, TWO output files', kind: 'llm_subagent', prompt: pr + '/ideate_select.txt THEN ' + pr + '/ideate_generate.txt', run: [`${RSCMD} phase2_prepare --dir "${rd}"`], inputs: [p1, ref + '/ideation-patterns/overview.md', ref + '/ideation-patterns/companion-combos.md', p0 + '/lit_table.md', P(rd, 'phase2_generate/closest_abstracts.json') + ' (pre-filtered closest_adjacent slice, materialized by the RUN command)', ref + '/ideation-sub-patterns/overview.md (+ picked C##.md cards)'].concat(cross ? [cross] : []), output: `${p2s} then ${p2g}`, notes: 'Run the RUN command first (deterministic), then the sub-agent. Routing signal: none.' })
  }
  const p2c = P(rd, 'phase2_coherence/phase2_coherence_output.json'), hits = P(rd, 'phase3_collision/collision_hits.json')
  if (!has(p2c)) return emit({ rd, state: 'Citation gate passed; coherence gate not yet run.', step: 'Phase 2.3 — coherence gate (dry-run trace)' + (has(hits) ? '' : ' — AND launch 3.1 collision in parallel'), kind: 'llm_subagent', prompt: pr + '/coherence_trace.txt', inputs: [p2g, p2s], output: p2c, run: has(hits) ? [] : [`${RSCMD} phase3_collision --idea-json "${p2g}" --out "${P(rd, 'phase3_collision')}/"`], notes: 'TWO independent actions. Routing signal to return: `verdict` (pass | patched) + any `unrepaired[]` blocking findings.' })
  if (!has(hits)) return emit({ rd, state: 'Candidate passed the citation gate.', step: 'Phase 3.1 — dual-channel collision retrieval', kind: 'bash', run: [`${RSCMD} phase3_collision --idea-json "${p2g}" --out "${P(rd, 'phase3_collision')}/"`] })
  const p3q = P(rd, 'phase3_critique/phase3_critique_output.json')
  if (!has(p3q)) return emit({ rd, state: 'Collision hits retrieved.', step: 'Phase 3.2 — audit-and-verdict (5 checks)', kind: 'llm_subagent', prompt: pr + '/critique.txt', inputs: [p2g, p2s, p0 + '/lit_table.md', hits, ref + '/anti-patterns.md', ref + '/ideation-sub-patterns/<each cited C##>.md'], output: p3q, notes: 'Routing signal to return: `verdict` (advance | revise | abandon) + verdict_rationale.' })
  const p4 = P(rd, 'phase4')
  if (!has(p4 + '/phase4_expansion.json') && !has(p4 + '/phase4_skeleton.json')) return emit({ rd, state: 'Gauntlet cleared (advance path).', step: 'Phase 4 skeleton (deterministic)', kind: 'bash', run: [`${RSCMD} phase4_skeleton --candidate "${p2g}" --phase1 "${p1}" --phase2-select "${p2s}" --phase3-critique "${p3q}" --phase0-dir "${p0}/" --collision "${hits}" --out "${p4}/"`] })
  if (!has(p4 + '/phase4_expansion.json') && !has(p4 + '/fill_map.json')) return emit({ rd, state: 'Skeleton built.', step: 'Phase 4.fill — author the TECHNICAL prose TODOs', kind: 'llm_subagent', prompt: pr + '/expand.txt', inputs: [p4 + '/phase4_skeleton.json'], output: p4 + '/fill_map.json', notes: 'Flat {TODO-path: prose} map ONLY' })
  if (!has(p4 + '/phase4_expansion.json')) return emit({ rd, state: 'fill_map written.', step: 'Phase 4 assemble — partial (deterministic)', kind: 'bash', run: [`${RSCMD} phase4_assemble --skeleton "${p4}/phase4_skeleton.json" --fill-map "${p4}/fill_map.json" --out "${p4}/"`] })
  if (!has(p4 + '/derive_map.json')) return emit({ rd, state: 'Partial expansion assembled; plain-register fields pending.', step: 'Phase 4.derive — plain-register derivation (fast-tier)', kind: 'llm_subagent', prompt: pr + '/derive_plain.txt', inputs: [p4 + '/phase4_expansion.json'], output: p4 + '/derive_map.json' })
  if (!has(p4 + '/method_view.json')) return emit({ rd, state: 'derive_map written; expansion still partial.', step: 'Phase 4 assemble — final merge + method view (deterministic)', kind: 'bash', run: [`${RSCMD} phase4_assemble --skeleton "${p4}/phase4_skeleton.json" --fill-map "${p4}/fill_map.json" --fill-map "${p4}/derive_map.json" --out "${p4}/"`, `${RSCMD} phase4_method_view --expansion "${p4}/phase4_expansion.json" --out "${p4}/"`] })
  if (!has(p4 + '/phase4_implementability.json')) return emit({ rd, state: 'Expansion assembled.', step: 'Phase 4.1.5 — implementability audit', kind: 'llm_subagent', prompt: pr + '/implementability_audit.txt', inputs: [p4 + '/method_view.json (method-only slice)'], output: p4 + '/phase4_implementability.json' })
  return emit({ rd, state: 'All Phase 4 JSONs present; cards not yet rendered.', step: 'Validate, then render the idea cards', kind: 'bash', run: [`${RSCMD} validate --phase2 "${p2g}" --phase3 "${p3q}" --phase4 "${p4}/phase4_expansion.json" --phase4-impl "${p4}/phase4_implementability.json"`, `${RSCMD} phase4_render --expansion "${p4}/phase4_expansion.json" --out "${p4}/"`] })
}

// ---------------------------------------------------------------- scripted shell
function runSub(cmd) {
  let m
  if (/print\("__QUOTE/.test(cmd)) return '__QUOTE 3/3 verified'
  if ((m = /run\.py'? next --dir '([^']+)'/.exec(cmd))) return navigate(m[1])
  if ((m = /lit_table_merge --out '([^']+)'/.exec(cmd))) { add(m[1] + '/lit_table.md'); return 'merged 2 shards' }
  if (/print\("SHARDS"/.test(cmd)) return 'SHARDS 2 20'
  if ((m = /phase2_prepare --dir "([^"]+)"/.exec(cmd))) { add(m[1] + '/phase2_generate/closest_abstracts.json'); return 'prepared' }
  if ((m = /phase4_skeleton .* --out "([^"]+)\/"/.exec(cmd))) { add(m[1] + '/phase4_skeleton.json'); return 'skeleton' }
  if ((m = /phase4_assemble .* --out "([^"]+)\/"/.exec(cmd))) { add(m[1] + '/phase4_expansion.json'); return 'assembled' }
  if ((m = /phase4_method_view .* --out "([^"]+)\/"/.exec(cmd))) { add(m[1] + '/method_view.json'); return 'view' }
  if (/regression_check\.py/.test(cmd)) return 'regression: 0 fail'
  if (/ validate /.test(cmd)) {
    if (process.env.MOCK_VALIDATE_FAIL && !validateFailed) { validateFailed = true; forceRc = 1; return '  ✗ [expansion_completeness] method_flow.steps[2] missing linked_falsification\n\n3 pass, 0 warn, 1 fail' }
    return '  ✓ [kill_switch_integrity] All 2 kill-switch fields byte-identical\nvalidate: all pass'
  }
  if ((m = /phase4_render .* --out "([^"]+)\/"/.exec(cmd))) { ['idea.std.zh.md', 'idea.std.en.md', 'idea.detail.en.md'].forEach((c) => add(m[1] + '/' + c)); return 'rendered' }
  if ((m = /cp -r '([^']+)\/r1\/phase1' '([^']+)\/'/.exec(cmd))) { add(m[2] + '/phase1/phase1_output.json'); return 'copied' }
  if (/cp -r '[^']*_shared\/phase0'/.test(cmd)) {
    assert(/sha256sum .* > \.manifest/.test(cmd) && /cmp -s/.test(cmd), 'spawn writes and compares the phase0 manifest')
    for (const mm of cmd.matchAll(/cp -r '[^']+' '([^']+\/phase0)'/g)) for (const f of ['lit_results.json', 'lit_table.md', 'fulltext_cache.json']) add(mm[1] + '/' + f)
    return 'SPAWNED'
  }
  return ''
}
function runCommand(cmd) {
  let m
  if (cmd.includes('__OUT_OK')) {                       // verify seat outputs, then next
    const head = cmd.slice(0, cmd.indexOf('); echo "$chk"'))
    const paths = [...head.matchAll(/ '(\/[^']+)'/g)].map((x) => x[1]).filter((x) => !x.includes('run.py'))
    const missing = paths.filter((x) => !has(x))
    if (missing.length) return '__OUT_BAD ' + missing.join(' | ')
    let pre = '__OUT_OK'
    if (process.env.MOCK_PLACEHOLDER && !placeholderSent) { placeholderSent = true; pre += ' warn: phase1_output.json placeholders: TBD' }
    pre += '\n'
    if (/ p1 '/.test(cmd)) pre += '__QUOTE 3/3 verified\n'
    if (/ p3 '/.test(cmd)) pre += '__QUOTE3 1/1 verified\n'
    return pre + runSub(cmd.slice(cmd.lastIndexOf('run.py')))
  }
  if (/__PLAN_(OK|BAD)/.test(cmd)) return '__PLAN_OK warn: none'
  if (/__SPEC_(OK|BAD)/.test(cmd)) return '__SPEC_OK '
  if (/__RANK_(OK|BAD)/.test(cmd)) return '__RANK_OK '
  if (/grep -cE .*dblp/.test(cmd)) return process.env.MOCK_DBLP_TIMEOUT ? '2' : '0'
  if (cmd.includes('QUERIES_JSON_BEGIN')) {
    const L = []
    for (const f of ['queries.json', 'intake.json', 'substrate.md', 'phase0/lit_results.json', 'phase0/lit_table.md', 'phase0/fulltext_cache.json']) if (has(SHARED + '/' + f)) L.push('HAS ' + f)
    if (has(SHARED + '/queries.json')) L.push('QUERIES_JSON_BEGIN', JSON.stringify({ direction: 'mock direction', queries: ['q1', 'q2', 'q3', 'q4'] }), 'QUERIES_JSON_END')
    return L.join('\n')
  }
  if ((m = /setsid nohup bash -c '((?:[^']|'\\'')*)'/.exec(cmd))) {
    const inner = m[1].replace(/'\\''/g, "'"), key = /LAUNCHED:(\S+)/.exec(cmd)[1]
    let out
    if ((out = /phase3_collision .* --out "([^"]+)\/"/.exec(inner))) add(out[1] + '/collision_hits.json')
    else if ((out = /phase0_fulltext --out '([^']+)\/'/.exec(inner))) add(out[1] + '/fulltext_cache.json')
    else if ((out = / phase0 .* --out '([^']+)\/'/.exec(inner))) add(out[1] + '/lit_results.json')
    else fail('unknown long job: ' + inner)
    return 'LAUNCHED:' + key
  }
  if (cmd.includes('JOB_DONE')) {
    const file = /\[ -e '([^']+)' \]/.exec(cmd)[1]
    if (!has(file)) return 'JOB_EXITED'
    const then = /echo JOB_DONE; (.*?); elif/.exec(cmd)
    return 'JOB_DONE' + (then ? '\n' + runSub(then[1]) : '')
  }
  const segs = [...cmd.matchAll(/\{ ([\s\S]*?)\n\}; rc=\$\?; echo "__RC(\d+)=\$rc"/g)]
  if (segs.length) {
    let out = ''
    for (const s of segs) { out += runSub(s[1]) + `\n__RC${s[2]}=${forceRc}\n`; forceRc = 0 }
    if (/ next --dir /.test(cmd)) out += runSub(cmd.slice(cmd.lastIndexOf('run.py')))
    return out
  }
  return runSub(cmd)
}

// ---------------------------------------------------------------- stub agent
let astraFailed = false
const stub = async (prompt, opts) => {
  const i = calls.length
  const rec = { i, label: opts.label, model: opts.model, effort: opts.effort, deny: opts.disallowedTools, clamp: opts.bashCommandClamp, prompt }
  calls.push(rec)
  if (prompt.includes('---- COMMAND ----')) {
    assert(opts.model === 'glm-5.3[1m]' && opts.effort === 'low', 'runner must be GLM/low: ' + opts.label)
    const wrapped = /---- COMMAND ----\n([\s\S]*?)\n---- END ----/.exec(prompt)[1]
    assert(wrapped.startsWith('{\n') && wrapped.endsWith('\n}\necho "__SH_RC=$?"'), 'runner command carries the workflow-owned exit sentinel')
    const cmd = wrapped.slice(2, -('\n}\necho "__SH_RC=$?"'.length))
    rec.kind = 'sh'; rec.cmd = cmd
    return { rc: 0, out: runCommand(cmd) + '\n__SH_RC=0' }
  }
  rec.kind = 'seat'
  if (process.env.MOCK_ASTRA_FAIL && opts.model === 'gpt-6-astra' && !astraFailed) { astraFailed = true; return null }   // terminal API error: agent() resolves null
  if (process.env.DUMP) console.log('#### SEAT ' + opts.label + '\n' + prompt.slice(prompt.indexOf('═══ RUN ═══')))
  const out = /^OUTPUT: (.*)$/m.exec(prompt)[1]
  const outs = out.split(' then ').map((s) => s.trim().split(' ')[0]).filter((s) => s.startsWith('/'))
  outs.forEach((p) => add(p))
  if (/Phase -1/.test(opts.label)) return { ok: true, written: outs, direction: 'mock direction', queries: ['q1', 'q2', 'q3', 'q4'] }
  if (/Phase 6/.test(opts.label)) { add(...outs); return { ok: true, written: outs, signal: 'specs written' } }
  if (/Phase 1 —/.test(opts.label)) return { ok: true, written: outs, signal: 'state=proceed' }
  if (/3\.2/.test(opts.label)) return { ok: true, written: outs, signal: 'verdict=advance' }
  return { ok: true, written: outs, signal: 'done' }
}
const par = async (t) => Promise.all(t.map((f) => f()))
const AF = Object.getPrototypeOf(async function () {}).constructor
const main = new AF('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', src)
const result = await main({ root: ROOT, k: 2, repo: '/mock/repo', dataset: 'NYU', venue: 'PR', goal: 'FROZEN mock goal text', anomalies: '/mock/anomalies.md', skill_dir: SK, stagger: true, negative_anchors: process.env.MOCK_NEG_ANCHORS ? ['/mock/failures/X-001.json'] : undefined }, stub, par, par, (t) => console.log('── ' + t), (m) => console.log('  ' + m))

// ---------------------------------------------------------------- assertions
const seats = calls.filter((c) => c.kind === 'seat')
const sh = calls.filter((c) => c.kind === 'sh')
const find = (re, list = calls) => list.find((c) => re.test(c.label))
const idx = (re, list = calls) => { const c = find(re, list); if (!c) fail('missing call ' + re); return c.i }

assert(result.runs.length === 2 && result.runs.every((r) => r.state === 'done'), 'both runs done: ' + JSON.stringify(result.runs))
assert(result.runs.every((r) => r.evidence_plan && r.validate_rc === 0 && r.cards.length === 3 && r.regression_rc === 0), 'evidence plan + validate + cards + regression_check per run: ' + JSON.stringify(result.runs))
assert(result.ranking === ROOT + '/ranking.json', 'ranking written')
assert(result.direction === 'mock direction', 'direction from intake')

const intake = find(/Phase -1 intake/, seats)
assert(intake && intake.model === 'glm-5.3[1m]' && intake.prompt.includes('brain/intake.md (verbatim)') && intake.prompt.includes('BRIEF') && intake.prompt.includes('- repo: /mock/repo'), 'intake seat: GLM, verbatim prompt, brief at the end')
assert(intake.prompt.includes('references/intake-routing.md (verbatim; inlined') && intake.prompt.includes('references/intent-recognition.md (verbatim; inlined') && intake.prompt.includes('compute-env-contract.md (verbatim; inlined') && intake.prompt.includes('idea-intake.md (verbatim; inlined') && intake.prompt.includes('evidence-precheck.md (verbatim; inlined'), 'intake refs inlined (RS + CCF idea-intake + ARIS compute-env / evidence-precheck)')
assert(idx(/phase0 retrieval launch/) < idx(/phase0 retrieval wait 1/), 'phase0 launched then polled')
assert(seats.filter((c) => /tagging shard/.test(c.label)).length === 2, 'two tagging shards')
assert(idx(/lit_table_merge/) > idx(/tagging shard 1/), 'merge after shards')
assert(idx(/fulltext fetch launch/) > idx(/lit_table_merge/), 'fulltext after lit_table')
assert(find(/^sh: spawn r1,r2/), 'spawn')

const p1 = seats.filter((c) => /Phase 1 —/.test(c.label))
assert(p1.length === 1 && p1[0].label.startsWith('r1:') && p1[0].model === 'claude-opus-5', 'Phase 1 runs once, on r1, on Opus')
assert(p1[0].prompt.includes('bottleneck_identify.txt (verbatim)') && p1[0].prompt.includes('MEASURED ANOMALIES') && p1[0].prompt.includes('FROZEN GOAL') && !p1[0].prompt.includes('the user query + intake context'), 'Phase 1 gets the Brain context lines')
assert(find(/^sh: r2: 1 cmd → next/) && /cp -r '\/mock\/root\/r1\/phase1'/.test(find(/^sh: r2: 1 cmd → next/).cmd), 'r2 copies r1 Phase 1')

const ide = seats.filter((c) => /Phase 2\.1 \+ 2\.2/.test(c.label))
assert(ide.length === 2 && ide.every((c) => c.model === 'claude-opus-5'), 'two ideate seats on Opus')
const ideR1 = ide.find((c) => c.label.startsWith('r1:')), ideR2 = ide.find((c) => c.label.startsWith('r2:'))
assert(ideR1.i < ideR2.i, 'r1 ideates before r2 (lock)')
const runSec = (c) => c.prompt.slice(c.prompt.indexOf('═══ RUN ═══'))
assert(runSec(ideR2).includes('CROSS-RUN DEDUP') && !runSec(ideR1).includes('CROSS-RUN DEDUP'), 'r2 sees the dedup line; r1 does not')
const selAt = ideR1.prompt.search(/SYSTEM PROMPT 1 of 2[^\n]*ideate_select\.txt \(verbatim\)/), genAt = ideR1.prompt.search(/SYSTEM PROMPT 2 of 2[^\n]*ideate_generate\.txt \(verbatim\)/)
assert(selAt >= 0 && genAt > selAt, 'both 2.x prompts inlined in order')
assert(/ideation-patterns\/overview\.md  \(inlined above/.test(ideR1.prompt) && ideR1.prompt.includes('references/ideation-patterns/companion-combos.md (verbatim; inlined'), 'ideate refs inlined and annotated')
assert(ideR1.prompt.includes('"substrate:"') && ideR1.prompt.includes('FROZEN GOAL'), 'ideate carries the substrate premise + goal')
assert(find(/^sh: r1: prep phase2_prepare/), 'phase2_prepare ran before the ideate seat')
assert(idx(/^sh: r1: prep phase2_prepare/) < ideR1.i, 'prep precedes seat')
assert(ideR1.prompt.indexOf('═══ RUN ═══') > Math.max(ideR1.prompt.lastIndexOf('(verbatim) ═══'), ideR1.prompt.lastIndexOf('do not Read) ═══')), 'static block precedes the dynamic RUN block')

const coh = seats.filter((c) => /Phase 2\.3/.test(c.label))
assert(coh.every((c) => c.prompt.includes('WORKDIR') && c.prompt.includes('coherence_trace.txt (verbatim)') && c.effort === 'high'), 'coherence seats: WORKDIR + verbatim prompt, effort high')
if (process.env.MOCK_ASTRA_FAIL) {
  const r1c = coh.filter((c) => c.label.startsWith('r1:')), r2c = coh.filter((c) => c.label.startsWith('r2:'))
  assert(r1c.length === 2 && r1c[0].model === 'gpt-6-astra' && r1c[1].model === 'claude-opus-5' && r2c.length === 1 && r2c[0].model === 'gpt-6-astra', 'Astra down on r1 → the retry runs on the Opus fallback; r2 stays on Astra: ' + coh.map((c) => c.label.slice(0, 14) + '=' + c.model).join(','))
  const fb = Object.fromEntries(result.runs.map((r) => [r.id, r.fallbacks]))
  assert(fb.r1.length === 1 && fb.r1[0].kind === 'coherence' && fb.r1[0].from === 'gpt-6-astra' && fb.r1[0].to === 'claude-opus-5' && fb.r2.length === 0, 'the fallback is recorded in the run record: ' + JSON.stringify(fb))
} else {
  assert(coh.length === 2 && coh.every((c) => c.model === 'gpt-6-astra'), 'coherence seats on Astra (gpt-6-astra)')
  assert(result.runs.every((r) => r.fallbacks.length === 0), 'no fallbacks on the happy path')
}
const cohR1 = coh.find((c) => c.label.startsWith('r1:'))
assert(idx(/^sh: r1: collision launch/) < cohR1.i && cohR1.i < idx(/^sh: r1: collision wait 1/), 'collision launched before 2.3 and awaited after')

const aud = seats.filter((c) => /Phase 3\.2/.test(c.label))
assert(aud.length === 2 && aud.every((c) => c.model === 'k3-256k' && c.prompt.includes('critique.txt (verbatim)') && c.prompt.includes('references/anti-patterns.md (verbatim; inlined') && c.prompt.includes('<each cited C##>.md')), 'audit seats: K3, anti-patterns inlined, card marker passed through')
assert(seats.filter((c) => /Phase 4\.fill/.test(c.label)).every((c) => c.model === 'claude-opus-5' && c.prompt.includes('expand.txt (verbatim)') && c.prompt.includes('formula-derivation/SKILL.md (verbatim; inlined') && c.prompt.includes('KEY EQUATIONS DISCIPLINE')), 'fill on Opus with the ARIS derivation discipline')
assert(seats.filter((c) => /Phase 4\.derive/.test(c.label)).every((c) => c.model === 'glm-5.3[1m]' && c.effort === 'low'), 'derive on GLM low')
assert(seats.filter((c) => /Phase 4\.1\.5/.test(c.label)).every((c) => c.model === 'glm-5.3[1m]'), 'implementability on GLM')
const ev = seats.filter((c) => /Phase 5/.test(c.label))
assert(ev.length === 2 && ev.every((c) => c.model === 'claude-opus-5' && c.prompt.includes('brain/evidence_plan.md (verbatim)') && c.prompt.includes('evidence-design.md (verbatim; inlined') && c.prompt.includes('ablation-planner/SKILL.md (verbatim; inlined') && c.prompt.includes('Lehr') && c.prompt.includes('FROZEN GOAL')), 'evidence seats on Opus with CCF + ARIS refs and the Lehr rule')
const sp = seats.filter((c) => /Phase 6/.test(c.label))
assert(sp.length === 2 && sp.every((c) => c.model === 'claude-opus-5' && c.deny.includes('Bash') && c.deny.includes('Edit') && !c.deny.includes('Glob') && c.prompt.includes('brain/spec.md (verbatim)') && c.prompt.includes('FROZEN GOAL') && c.prompt.includes('task.yaml (verbatim; inlined') && c.prompt.includes('prompt_b1.md (verbatim; inlined') && c.prompt.includes('"gates"')), 'Phase 6 spec seats: Opus, read-only repo, FROZEN, ASI gates form')
assert(sh.filter((c) => /__PLAN_/.test(c.cmd)).length === 2 && sh.filter((c) => /__SPEC_/.test(c.cmd)).length === 2, 'plan_check and spec_check ran once per run')
assert(sh.filter((c) => / p1 '/.test(c.cmd) && /__QUOTE3/.test(c.cmd)).length === 1, 'Phase 1 quote check once (r1)')
assert(sh.filter((c) => / p3 '/.test(c.cmd) && /__QUOTE3/.test(c.cmd)).length === 2, '3.2 threat quote check once per run')
assert(result.runs.every((r) => r.quote_check3 === '1/1 verified') && result.runs.find((r) => r.id === 'r1').quote_check === '3/3 verified', 'quote results recorded: ' + JSON.stringify(result.runs.map((r) => [r.quote_check, r.quote_check3])))
assert(sh.filter((c) => /__OUT_OK/.test(c.cmd)).length >= 10, 'seat outputs are verified in the navigator call')
assert(aud.every((c) => c.prompt.includes('SCOPE CHECK') && c.prompt.includes('FROZEN GOAL') && c.prompt.includes('THREAT QUOTE') && c.prompt.includes('REVIEW DISCIPLINE') && c.prompt.includes('strict-idea-review.md (verbatim; inlined') && c.prompt.includes('problem-method-blueprint.md (verbatim; inlined') && c.prompt.includes('ARFT CODES') && c.prompt.includes('arft_guide.md (verbatim; inlined')), 'audit seats get FROZEN + scope check + threat quote + CCF review discipline + ARFT codes')
assert(seats.filter((c) => /Phase 3\.3/.test(c.label)).every((c) => c.prompt.includes('FROZEN GOAL')), 'revise seats get FROZEN')
assert(p1[0].prompt.includes('evidence_quote') && p1[0].prompt.includes('RELATION') && p1[0].prompt.includes('literature-grounded-evolution.md (verbatim; inlined'), 'Phase 1 asks for evidence quotes + relation edges (CCF relation map inlined)')
assert(ideR2.prompt.includes('RUN DIVERSITY') && ideR2.prompt.includes('rank 2'), 'r2 ideate takes the second-ranked anchor gap')
assert(result.runs.every((r) => r.plan_check && r.plan_check.startsWith('OK') && r.spec && r.spec_check && r.spec_check.startsWith('OK')), 'plan/spec checks recorded: ' + JSON.stringify(result.runs.map((r) => [r.plan_check, r.spec_check])))
const rk = seats.filter((c) => /^rank/.test(c.label))
assert(rk.length === 1 && rk[0].model === 'claude-opus-5' && rk[0].effort === 'high' && rk[0].prompt.includes('/mock/root/r1/phase4/idea.detail.en.md') && rk[0].prompt.includes('/mock/root/r2/phase5/evidence_plan.json') && rk[0].prompt.includes('/mock/root/r2/phase3_critique/phase3_critique_output.json'), 'one rank seat over both runs')
assert(rk[0].prompt.includes('references/rubric.md (verbatim; inlined') && rk[0].prompt.includes('references/calibration.md (verbatim; inlined') && rk[0].prompt.includes('strict-idea-review.md (verbatim; inlined') && rk[0].prompt.includes('Fatal Gates') && rk[0].prompt.includes('weighted_score') && rk[0].prompt.includes('expert-panel.md (verbatim; inlined') && rk[0].prompt.includes('review-output-standards.md (verbatim; inlined') && rk[0].prompt.includes('venue-idea-adapters.md (verbatim; inlined') && rk[0].prompt.includes('"panel"'), 'rank seat carries the CCF rubric + calibration + panel + output standards verbatim')
assert(sh.filter((c) => /__RANK_/.test(c.cmd)).length === 1 && result.rank_check && result.rank_check.startsWith('OK'), 'rank_check ran once: ' + result.rank_check)
const vr = sh.filter((c) => / validate /.test(c.cmd))
assert(vr.length === 2 + (process.env.MOCK_VALIDATE_FAIL ? 1 : 0) && vr.every((c) => !/phase4_render/.test(c.cmd)), 'validate runs alone (repairable), once per run + one re-validate after a repair')
const rn = sh.filter((c) => /phase4_render/.test(c.cmd))
assert(rn.length === 2 && rn.every((c) => / next --dir /.test(c.cmd)), 'render + next in one runner call')
const rep = seats.filter((c) => /validate repair/.test(c.label))
if (process.env.MOCK_VALIDATE_FAIL) {
  assert(rep.length === 1 && rep[0].model === 'claude-opus-5' && rep[0].prompt.includes('VALIDATE REPAIR') && rep[0].prompt.includes('expand.txt (verbatim)') && rep[0].prompt.includes('[expansion_completeness]'), 'validate fail → one fill repair seat with the findings')
  assert(result.runs.some((r) => r.validate_repairs === 1) && result.runs.every((r) => r.validate_rc === 0), 'repair then re-validate passes: ' + JSON.stringify(result.runs.map((r) => [r.validate_rc, r.validate_repairs])))
} else assert(rep.length === 0 && result.runs.every((r) => r.validate_repairs === 0), 'no repair on the happy path')
const col = sh.filter((c) => /phase3_collision/.test(c.cmd) && /LAUNCHED/.test(c.cmd))
assert(col.length === 2, 'two collision launches')
if (process.env.MOCK_DBLP_TIMEOUT) assert(col.every((c) => c.cmd.includes('IDEASPARK_SKIP_SOURCES=dblp')), 'breaker: later retrievals skip dblp')
else assert(col.every((c) => !c.cmd.includes('IDEASPARK_SKIP_SOURCES')), 'no breaker by default')
if (process.env.MOCK_PLACEHOLDER) assert(result.runs.some((r) => r.placeholders.length === 1 && /TBD/.test(r.placeholders[0])), 'placeholder warning recorded: ' + JSON.stringify(result.runs.map((r) => r.placeholders)))
else assert(result.runs.every((r) => r.placeholders.length === 0), 'no placeholders on the happy path')
assert(seats.every((c) => !/Phase 0: produce queries/.test(c.label)), 'runs never see the Phase 0 query step')
if (process.env.MOCK_NEG_ANCHORS) {
  const na = seats.filter((c) => /Phase 1 —|2\.1 \+ 2\.2|Phase 3\.2/.test(c.label))
  assert(na.length === 5 && na.every((c) => /NEGATIVE ANCHORS \((Brain addition|hard)/.test(c.prompt) && c.prompt.includes('/mock/failures/X-001.json')), 'negative anchors reach Phase 1, both ideate seats and both audit seats: ' + na.map((c) => c.label.slice(0, 24)).join(','))
  assert(seats.filter((c) => /Phase 4|Phase 5|Phase 6|rank/.test(c.label)).every((c) => !c.prompt.includes('/mock/failures/')), 'negative anchors stay out of the card / plan / spec / rank seats')
} else assert(seats.every((c) => !c.prompt.includes('/mock/failures/') && !/NEGATIVE ANCHORS \((Brain addition|hard)/.test(c.prompt)), 'no negative-anchor line without args.negative_anchors')
const ALLOWED = new Set(['claude-opus-5', 'glm-5.3[1m]', 'k3-256k', 'gpt-6-astra'])
assert(calls.every((c) => ALLOWED.has(c.model)), 'every agent call pins one of the routed model ids: ' + [...new Set(calls.map((c) => c.model))].join(','))
assert(calls.every((c) => ['low', 'medium', 'high'].includes(c.effort)), 'every agent call sets effort explicitly (never inherits the session effort)')
assert(calls.every((c) => Array.isArray(c.deny) && c.deny.length > 0), 'every agent call narrows its tool pool (disallowedTools)')
assert(calls.filter((c) => /Phase 2\.3/.test(c.label)).every((c) => Array.isArray(c.clamp) && c.clamp[0] === 'Bash(python3:*)'), 'coherence seats clamp Bash to python3')
assert(calls.filter((c) => c.kind === 'sh').every((c) => c.deny.includes('Write') && c.deny.includes('Read')), 'runner cannot read or write files')
assert(seats.filter((c) => /^r\d: /.test(c.label)).every((c) => c.prompt.includes('REPOSITORY: /mock/repo')), 'run seats carry the repository root')

console.log(`\nOK — ${calls.length} agent calls: ${sh.length} runner, ${seats.length} seats (` +
  Object.entries(seats.reduce((a, c) => { a[c.model] = (a[c.model] || 0) + 1; return a }, {})).map(([k, v]) => `${k}=${v}`).join(', ') + ')')
