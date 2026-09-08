export const meta = {
  name: 'ideaspark',
  description: 'ResearchStudio idea-spark, replicated 1:1 as a workflow: upstream phase graph in JS, upstream prompts verbatim, one idea card',
  phases: [
    { title: 'Phase 0', detail: 'queries → retrieval → relevance partition → tagging → coverage check → full text' },
    { title: 'Gauntlet', detail: 'Phase 1 bottleneck → 2.1+2.2 → citation gate → 2.3 coherence ∥ 3.1 collision → 3.2 audit → revise / retry' },
    { title: 'Phase 4', detail: 'skeleton → fill → derive → implementability audit → validate → render' },
    { title: 'Score', detail: 'idea_quality: three independent judges, absolute + blind pairwise, then aggregate' },
  ],
}

// ═══════════════════════════════════════════════════════════════════════════════
// A 1:1 replica of ResearchStudio's idea_spark skill.
//
//   LOGIC   — scripts/next_step.py's phase graph, ported to JS (section 6). No text
//             emit is parsed: a python probe (STATE_PY) prints ONE json snapshot of
//             the run dir and decide() picks the next step from it.
//   PROMPTS — every system prompt and rubric a seat reads, inlined verbatim from the
//             upstream checkout by gen.py (section 2). Nothing is added to them.
//   TOOLS   — the deterministic half stays upstream's: every phase0/…/phase4/validate
//             subcommand is run as-is out of scripts/run.py.
//
// Deviations from upstream, all of them declared:
//   1. Model routing per seat (upstream has two tiers: host-large and classify-fast).
//   2. Phase 0.5 coverage check runs THREE judges in parallel and unions their
//      nominations (upstream runs one). Each nomination is still connector-verified,
//      so a wider net cannot admit an unverified paper.
//   3. A scoring stage after the cards: the suite's own evaluation/idea_quality skill,
//      three judges, plus a machine-readable echo of each report for aggregation.
//   4. Seats retry once in a fresh context when the first attempt returns nothing.
// ═══════════════════════════════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────────── 1. arguments
const A = args || {}
if (!A.root) throw new Error('args.root is required: absolute run root (one directory per topic, e.g. <ws>/.research/research/ideaspark/<slug>)')
if (!A.direction && !A.query) throw new Error('args.direction is required: the research direction, one sentence of free text')
const ROOT = String(A.root).replace(/\/+$/, '')
const DIRECTION = String(A.direction || A.query).trim()
const K = Math.max(1, parseInt(A.k, 10) || 1)                      // upstream is K=1 by design; K>1 runs fully independent sibling runs
// The ResearchStudio-Idea checkout this run drives. Required: the workflow shells out to its
// scripts/run.py for every deterministic step, and its prompts were packed from it. The plugin
// vendors a copy and its init script writes the absolute path into args.json.
const RS_HOME = String(A.rs_home || '').replace(/\/+$/, '')
const SKILL_DIR = A.skill_dir || (RS_HOME && RS_HOME + '/skills/idea_spark')
if (!SKILL_DIR) throw new Error('args.rs_home is required: the ResearchStudio-Idea checkout to run (the plugin vendors one at <plugin>/vendor/researchstudio). args.skill_dir overrides it directly.')
const ENV_FILE = A.env_file === false ? '' : (A.env_file || (RS_HOME ? RS_HOME + '/.env' : ''))   // connector credentials; sourced into the shell, never printed
const PY = A.python || 'python3'
const COMPUTE = A.compute || ''                                    // IDEASPARK_DEFAULT_COMPUTE — the standing compute profile Phase 1 judges feasibility against
const USER_REFS = Array.isArray(A.user_refs) ? A.user_refs : []    // [{title, id?, raw_match?}] papers the direction names by title
const MAX_STEPS = A.max_steps || 90
const COVERAGE_JUDGES = A.coverage_judges === false ? [] : (A.coverage_judges || ['opus', 'sol', 'k3'])
const SCORE_JUDGES = A.score_judges === false ? [] : (A.score_judges || ['opus', 'sol', 'k3'])
const COVERAGE_UNION_CAP = Math.max(1, parseInt(A.coverage_union_cap, 10) || 16)
const JOBS = ROOT + '/.jobs'
const RUN_IDS = Array.from({ length: K }, (_, i) => 'r' + (i + 1))

// Model ids are claude-kimi routes (LiteLLM :4001). On the official Anthropic API these ids do
// not exist and the harness silently serves the session model instead — run this from a
// `claude-kimi` session. Per-agent effort is currently ignored by the runtime (the launcher's
// CLAUDE_CODE_EFFORT_LEVEL wins); it is set anyway so the intent survives a runtime fix.
const MODEL = Object.assign({ opus: 'claude-opus-5', glm: 'glm-5.3[1m]', k3: 'k3-256k', sol: 'gpt-5.6-sol' }, A.models || {})
const RUNNER_MODEL = A.runner_model || MODEL.glm

const shq = (s) => "'" + String(s).replace(/'/g, "'\\''") + "'"
const base = (p) => String(p).split('/').pop()
const ENVSRC = ENV_FILE ? 'if [ -f ' + shq(ENV_FILE) + ' ]; then set -a; . ' + shq(ENV_FILE) + ' >/dev/null 2>&1 || true; set +a; fi; ' : ''
const ENV = COMPUTE ? 'IDEASPARK_DEFAULT_COMPUTE=' + shq(COMPUTE) + ' ' : ''
const RS = ENV + PY + ' ' + shq(SKILL_DIR + '/scripts/run.py')
const SUBPAT = SKILL_DIR + '/references/ideation-sub-patterns'

// ─────────────────────────────────────────────────────────── 2. prompt bank (verbatim, packed by gen.py)
// __BANK__

// ─────────────────────────────────────────────────────────── 3. seats
// tier: how upstream classifies the step — 'large' (host reasoning model), 'own' (open-ended
// judgment, explicitly must not be downgraded), 'fast' (mechanical classification against a
// written rubric), 'host' (upstream lets the host do it inline).
const SEATS = {
  queries:   { model: MODEL.glm,  effort: 'medium', tools: 'readwrite', tier: 'host', prompts: ['intent_recognition'], refs: ['intake_routing'] },
  partition: { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'own',  prompts: ['relevance_partition'], refs: [] },
  tagging:   { model: MODEL.glm,  effort: 'low',    tools: 'readwrite', tier: 'fast', prompts: ['pattern_rubric'], refs: [] },
  coverage:  { model: MODEL.opus, effort: 'high',   tools: 'web',       tier: 'own',  prompts: [], refs: [] },
  phase1:    { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['bottleneck_identify'], refs: [] },
  ideate:    { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['ideate_select', 'ideate_generate'], refs: ['patterns_overview', 'companion_combos', 'subpatterns_overview'] },
  generate:  { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['ideate_generate'], refs: ['subpatterns_overview'] },
  cite_fix:  { model: MODEL.glm,  effort: 'medium', tools: 'readwrite', tier: 'host', prompts: [], refs: ['subpatterns_overview'] },
  coherence: { model: MODEL.opus, effort: 'high',   tools: 'exec',      tier: 'large', prompts: ['coherence_trace'], refs: [] },
  terms:     { model: MODEL.glm,  effort: 'low',    tools: 'readwrite', tier: 'host', prompts: [], refs: ['intent_recognition'] },
  audit:     { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['critique'], refs: ['anti_patterns'] },
  recheck:   { model: MODEL.opus, effort: 'high',   tools: 'exec',      tier: 'large', prompts: ['refutation_recheck'], refs: [] },
  revise:    { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['revise'], refs: [] },
  reaudit:   { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['falsification_reaudit'], refs: [] },
  fill:      { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['expand'], refs: [] },
  derive:    { model: MODEL.glm,  effort: 'low',    tools: 'readwrite', tier: 'fast', prompts: ['derive_plain'], refs: [] },
  impl:      { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'large', prompts: ['implementability_audit'], refs: [] },
  writeup:   { model: MODEL.glm,  effort: 'medium', tools: 'readwrite', tier: 'host', prompts: [], refs: [] },
  judge:     { model: MODEL.opus, effort: 'high',   tools: 'readwrite', tier: 'own',  prompts: ['idea_quality'], refs: [] },
}
for (const [k, v] of Object.entries(A.seat_models || {})) {
  if (SEATS[k] && MODEL[v]) SEATS[k].model = MODEL[v]
  else throw new Error('args.seat_models: unknown seat or model key ' + k + ':' + v)
}
const PHASE_OF = { queries: 'Phase 0', partition: 'Phase 0', tagging: 'Phase 0', coverage: 'Phase 0',
  fill: 'Phase 4', derive: 'Phase 4', impl: 'Phase 4', judge: 'Score' }
const phaseOf = (kind) => PHASE_OF[kind] || 'Gauntlet'

const DENY = {
  readwrite: ['Bash', 'Glob', 'Grep', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
  exec:      ['Glob', 'Grep', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
  web:       ['Bash', 'Edit', 'Glob', 'Grep', 'WebFetch', 'NotebookEdit', 'ToolSearch'],
  runner:    ['Read', 'Write', 'Edit', 'Glob', 'Grep', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
}
const CLAMP = A.no_clamp ? {} : { exec: ['Bash(python3:*)'] }
const TOOLS = {
  readwrite: 'Tools for this seat: Read and Write (Edit only to fix a small mistake in a file you just wrote). Bash, Glob, Grep and the web are disabled. Do not open files the INPUT section does not name — the one exception is a file the SYSTEM PROMPT itself tells you to pick and open, such as the sub-pattern card for a gap. Write each output ONCE, in full.',
  exec: 'Tools for this seat: Read, Write, Edit, and Bash clamped to python3 — run the standard-library scripts you write as `python3 /absolute/path/script.py > /absolute/path/script.out 2>&1` (absolute paths, no cd, no pipes, no other program; the clamp rejects anything else). Paste the script and its printed output into your report exactly as the system prompt asks, and never report an estimated number as measured. Write the report ONCE, in full, when it is final.',
  web: 'Tools for this seat: Read, Write, and WebSearch. WebSearch is permitted for this step only, and only to find the TITLE of a paper you already have reason to believe exists — never to fabricate a record. No Bash, no Glob, no Grep, no page fetching.',
}
const SEAT_FRAME = 'You are one isolated seat of a ResearchStudio idea-spark run: a single step of the pipeline, executed as its own sub-agent with a fresh context. Everything you need is in this message and in the files it names; you have no conversation history and need none.\n\nHow to work:\n- The SYSTEM PROMPT section below is the complete contract for this step, reproduced verbatim from ResearchStudio. Follow it exactly: its input rules, its output schema, its stop conditions.\n- A REFERENCE section below is already in this message — never re-open those files. Read the files listed under INPUT; lines there that are not paths are context.\n- Write the file named under OUTPUT with your file-write tool, once, in full. No heredoc, no inline JSON in your reply.\n- Return the structured result: ok, written (the absolute paths you wrote), signal (the routing signal NOTES asks for; empty when it asks for none), note (at most 250 words).\n- Do not do another step\'s work, do not edit a file the OUTPUT line does not name, and never report a number you did not compute.'

function staticBlock(kind) {
  const s = SEATS[kind]
  const parts = [SEAT_FRAME, '', TOOLS[s.tools]]
  s.prompts.forEach((k, i) => {
    const b = BANK[k]
    const order = s.prompts.length > 1 ? ' ' + (i + 1) + ' of ' + s.prompts.length + (i ? ' (run AFTER the previous one has written its output)' : ' (run FIRST)') : ''
    parts.push('', '═══ SYSTEM PROMPT' + order + ' — ' + b.path + ' (verbatim) ═══', '', b.text)
  })
  s.refs.forEach((k) => {
    const b = BANK[k]
    parts.push('', '═══ REFERENCE — ' + b.path + ' (verbatim; inlined, do not Read) ═══', '', b.text)
  })
  return parts.join('\n')
}
const STATIC = {}
for (const kind of Object.keys(SEATS)) STATIC[kind] = staticBlock(kind)

let SEAT_SEQ = 0
function seatPrompt(kind, dyn) {
  const lines = [STATIC[kind], '', '═══ RUN ═══', 'SKILL_DIR: ' + SKILL_DIR, 'RUN_DIR: ' + dyn.rd,
    'STEP: ' + dyn.step + ' | SEAT #' + (++SEAT_SEQ) + ' of this workflow run']
  if (dyn.workdir) lines.push('WORKDIR (scripts you run live here; create it): ' + dyn.workdir)
  lines.push('', 'INPUT (files to Read unless marked inlined; lines that are not paths are context):')
  for (const l of dyn.inputs || []) lines.push('  - ' + l)
  lines.push('', 'OUTPUT: ' + (dyn.output || '-'))
  if (dyn.notes) lines.push('', 'NOTES: ' + dyn.notes)
  return lines.join('\n')
}

const SEAT_SCHEMA = { type: 'object', properties: { ok: { type: 'boolean' }, written: { type: 'array', items: { type: 'string' } }, signal: { type: 'string' }, note: { type: 'string' } }, required: ['ok', 'written'] }
const RUN_SCHEMA = { type: 'object', properties: { rc: { type: 'integer' }, out: { type: 'string' } }, required: ['rc', 'out'] }

async function seat(kind, dyn, label, forceModel) {
  const s = SEATS[kind]
  const opts = { label: label.slice(0, 60), phase: dyn.phase || phaseOf(kind), schema: dyn.schema || SEAT_SCHEMA,
    model: forceModel || s.model, effort: s.effort, disallowedTools: DENY[s.tools] }
  if (CLAMP[s.tools]) opts.bashCommandClamp = CLAMP[s.tools]
  const prompt = seatPrompt(kind, dyn)
  let r = await agent(prompt, opts)
  if (!r || !r.ok) {
    log(kind + ': first attempt returned ' + ((r && r.note) || 'no result') + ' — one retry in a fresh context')
    r = await agent(prompt, opts)
  }
  return r
}

// ─────────────────────────────────────────────────────────── 4. shell runner
const RUNNER_FRAME = 'You are the shell runner of this workflow. Your only job is to execute the one command between the COMMAND markers exactly as written, once, in the foreground, with the Bash tool and the timeout stated — no edits, no extra commands, no retries, no interpretation of what it does. Every path in it is absolute, so the working directory does not matter. Never read, write, or create any file yourself.\n\nReturn the structured result: rc = the command\'s exit code; out = its stdout followed by its stderr, VERBATIM — every line, in order, unsummarized, untrimmed (the caller parses it mechanically; a dropped or paraphrased line corrupts the run). If the combined output exceeds 16000 characters keep the LAST 16000 characters.'
let SH_SEQ = 0
async function sh(cmd, label, opts) {
  const o = opts || {}
  const timeout = o.timeout || 600000
  const wrapped = '{\n' + ENVSRC + cmd + '\n}\necho "__SH_RC=$?"'
  const prompt = RUNNER_FRAME + '\n\nBash timeout: ' + timeout + ' ms\nCALL #' + (++SH_SEQ) + ' of this workflow run\n\n---- COMMAND ----\n' + wrapped + '\n---- END ----\n'
  const r = await agent(prompt, { label: ('sh: ' + label).slice(0, 60), phase: o.phase || 'Gauntlet', schema: RUN_SCHEMA, model: RUNNER_MODEL, effort: 'low', disallowedTools: DENY.runner })
  if (!r) return { rc: -1, out: '', sentinel: false }
  const raw = String(r.out || '')
  const m = /__SH_RC=(\d+)/.exec(raw)
  return { rc: m ? Number(m[1]) : Number(r.rc), out: raw.replace(/\n?__SH_RC=\d+[ \t]*$/, ''), sentinel: !!m }
}
async function shOk(cmd, label, opts) {
  const r = await sh('{ ' + cmd + '\n}; rc=$?; echo "__RC0=$rc"', label, opts)
  if (!/__RC0=0/.test(r.out)) throw new Error('command failed: ' + cmd.slice(0, 200) + ' :: ' + r.out.slice(-500))
  return r
}
// Long RS jobs (retrieval, full text, collision) exceed one Bash call, so they run detached
// under ROOT/.jobs and are polled. A job whose pid is still alive is reused, never restarted.
function launchCmd(key, cmd) {
  const log_ = JOBS + '/' + key + '.log', pid = JOBS + '/' + key + '.pid'
  return 'mkdir -p ' + shq(JOBS) + ' && if [ -e ' + shq(pid) + ' ] && kill -0 "$(cat ' + shq(pid) + ')" 2>/dev/null; then echo LAUNCHED:' + key +
    '; else rm -f ' + shq(pid) + ' && (setsid nohup bash -c ' + shq(ENVSRC + cmd) + ' > ' + shq(log_) + ' 2>&1 & echo $! > ' + shq(pid) + ') && sleep 1 && echo LAUNCHED:' + key + '; fi'
}
function waitCmd(key, file) {
  const pid = JOBS + '/' + key + '.pid', log_ = JOBS + '/' + key + '.log'
  return 'st=WAITING; for i in $(seq 1 17); do if kill -0 "$(cat ' + shq(pid) + ' 2>/dev/null)" 2>/dev/null; then sleep 30; continue; fi; ' +
    'sleep 2; if [ -e ' + shq(file) + ' ]; then st=DONE; else st=EXITED; fi; break; done; ' +
    'if [ "$st" = DONE ]; then echo JOB_DONE; elif [ "$st" = EXITED ]; then echo JOB_EXITED; tail -c 1500 ' + shq(log_) + '; else echo JOB_WAITING; tail -c 800 ' + shq(log_) + '; fi'
}
async function launch(key, cmd, label, phaseName) {
  const r = await sh(launchCmd(key, cmd), label + ' launch', { phase: phaseName, timeout: 60000 })
  return r.rc === 0 && r.out.includes('LAUNCHED:' + key)
}
async function waitFor(key, file, label, phaseName, rounds) {
  let last = ''
  const n = rounds || 6
  for (let i = 0; i < n; i++) {
    const r = await sh(waitCmd(key, file), label + ' wait ' + (i + 1), { phase: phaseName })
    if (r.out.includes('JOB_DONE')) return { done: true, out: r.out }
    if (r.out.includes('JOB_EXITED')) return { done: false, out: r.out }
    if (r.rc === -1) return { done: false, out: r.out }
    last = r.out
  }
  return { done: false, out: 'timeout after ' + n + ' polls; last log tail: ' + String(last || '').slice(-800) }
}

// ─────────────────────────────────────────────────────────── 5. state probe
// One python pass over the run dir prints a single json snapshot. Everything decide() needs
// is in it, including the two citation-gate validators (run in-process, exactly as upstream's
// navigator does) and the archived-attempt lesson sets the retry rule is computed from.
const STATE_PY = `import json, os, re, sys
d, root = sys.argv[1], sys.argv[2]
J = os.path.join
def ex(p): return os.path.exists(p)
def rj(p):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return None
def rt(p):
    try:
        return open(p, encoding='utf-8').read()
    except Exception:
        return ''
def mt(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0.0
def on(k):
    return os.environ.get(k, '').lower() not in ('off', '0', 'false')

def attempts(dd):
    out = []
    if os.path.isdir(dd):
        for n in os.listdir(dd):
            if n.startswith('attempt_') and n[8:].isdigit() and os.path.isdir(J(dd, n)):
                out.append(n)
    return sorted(out, key=lambda n: int(n[8:]))

def rejected(pd):
    if not os.path.isdir(pd):
        return 0
    return len([x for x in os.listdir(pd) if x.startswith('rejected_') and os.path.isdir(J(pd, x))])

def lessons(doc):
    ls = []
    if not isinstance(doc, dict):
        return ls
    for dd in doc.get('blocking_findings_disposition') or []:
        if isinstance(dd, dict) and dd.get('status') == 'upheld':
            ls.append(['finding', str(dd.get('finding_ref', ''))[:40]])
    t = doc.get('paper_pointed_threat') or {}
    if isinstance(t, dict) and t.get('addressable_via') == 'unaddressable':
        ls.append(['threat', str(t.get('threat_paper_id') or t.get('subsumption_argument') or '')[:60]])
    for e in (doc.get('gap_closure_reject_check') or {}).get('entries') or []:
        for l in (e.get('reject_lessons_evaluated') or []):
            if str(l.get('candidate_match', '')).lower() in ('yes', 'true'):
                ls.append(['reject', str(l.get('lesson_quoted', ''))[:60]])
    ap = doc.get('anti_pattern_check') or {}
    mp = ap.get('matched_pattern_id')
    if mp and str(mp).lower() not in ('none', 'null') and str(ap.get('mitigation_substantively_delivered', '')).lower() not in ('yes', 'true'):
        ls.append(['anti', str(mp)[:40]])
    rc = doc.get('recipe_application_check') or {}
    if rc.get('verdict') == 'bypassed':
        tagged = False
        for e in rc.get('entries') or []:
            if str(e.get('verdict', '')).lower() == 'bypassed':
                ls.append(['recipe', str(e.get('sub_pattern', ''))[:40]]); tagged = True
        if not tagged:
            ls.append(['recipe', 'bypassed'])
    return ls

p0 = J(d, 'phase0')
S = {'dir': d, 'exists': os.path.isdir(d)}
S['flags'] = {'partition': on('IDEASPARK_RELEVANCE_PARTITION'), 'coverage': on('IDEASPARK_COVERAGE_CHECK'), 'crossrun': on('IDEASPARK_CROSS_RUN_DEDUP')}
S['terminal'] = {'dng': ex(J(d, 'do_not_generate.md')), 'p3f': ex(J(d, 'phase_3_failed.md')),
                 'cards': all(ex(J(d, 'phase4', c)) for c in ('idea.std.zh.md', 'idea.std.en.md', 'idea.detail.en.md'))}

lit_txt = rt(J(p0, 'lit_table.md'))
host_refs = rj(J(p0, 'host_refs.json')) or []
lit_res = rj(J(p0, 'lit_results.json'))
papers = (lit_res or {}).get('papers') if isinstance(lit_res, dict) else lit_res
S['p0'] = {
    'queries': ex(J(d, '.ideaspark_queries.json')),
    'lit_results': ex(J(p0, 'lit_results.json')),
    'n_papers': len(papers or []) if isinstance(papers, list) else 0,
    'partition_file': ex(J(p0, 'relevance_partition.json')),
    'partition_applied': ex(J(p0, '.partition_applied')),
    'lit_table': ex(J(p0, 'lit_table.md')),
    'noms': ex(J(p0, 'host_refs_nominations.json')),
    'host_refs': ex(J(p0, 'host_refs.json')),
    'coverage_done': ex(J(p0, '.coverage_check_done')),
    'host_rows': ex(J(p0, '_host_rows.md')),
    'new_host_ids': [r.get('paper_id') for r in host_refs if isinstance(r, dict) and r.get('paper_id') and r.get('paper_id') not in lit_txt],
    'fulltext': ex(J(p0, 'fulltext_cache.json')),
    'fulltext_index': ex(J(p0, 'fulltext', 'index.json')),
    'intent_pending': ex(J(p0, '.intent_extraction_pending')),
    'degraded': ex(J(p0, '.connectors_degraded')),
    'mode': rt(J(p0, '.lit_grounding_mode')).strip(),
}
rows = [ln for ln in lit_txt.splitlines() if ln.strip().startswith('|') and 'paper_id' not in ln and '---' not in ln]
S['p0']['on_topic_rows'] = sum(1 for ln in rows if 'outside_taxonomy' not in ln)

p1doc = rj(J(d, 'phase1', 'phase1_output.json'))
S['p1'] = {'exists': ex(J(d, 'phase1', 'phase1_output.json')),
           'state': (p1doc or {}).get('state') if isinstance(p1doc, dict) else None,
           'closest_adjacent': len((p1doc or {}).get('closest_adjacent') or []) if isinstance(p1doc, dict) else 0}

p2s, p2g = J(d, 'phase2_select', 'phase2_select_output.json'), J(d, 'phase2_generate', 'phase2_generate_output.json')
S['p2'] = {'select': ex(p2s), 'generate': ex(p2g), 'slim': ex(J(d, 'phase2_generate', 'closest_abstracts.json'))}

gate = []
if ex(p2g):
    try:
        sys.path.insert(0, root)
        from scripts.validators import validate_subpattern_citation_consistency, validate_alias_collateral_coverage
        gate = validate_subpattern_citation_consistency(p2g)
        if ex(J(d, 'phase1', 'phase1_output.json')):
            gate = gate + validate_alias_collateral_coverage(p2g, J(d, 'phase1', 'phase1_output.json'))
    except Exception as e:
        gate = [{'validator': 'gate', 'severity': 'warn', 'message': 'citation gate could not run: ' + str(e)[:200]}]
S['gate'] = {'fail': [f.get('message', '') for f in gate if f.get('severity') == 'fail'],
             'warn': [f.get('message', '') for f in gate if f.get('severity') == 'warn'],
             'alias': any(f.get('validator') == 'alias_collateral_coverage' and f.get('severity') == 'fail' for f in gate)}

p2c_dir = J(d, 'phase2_coherence')
p2c = J(p2c_dir, 'phase2_coherence_output.json')
p2cdoc = rj(p2c) if ex(p2c) else None
blocking = [u for u in ((p2cdoc or {}).get('unrepaired') or []) if isinstance(u, dict) and u.get('severity') == 'blocking']
S['p23'] = {'exists': ex(p2c), 'verdict': (p2cdoc or {}).get('verdict') if isinstance(p2cdoc, dict) else None,
            'refined': ex(J(p2c_dir, 'refined_candidate.json')), 'rejected': rejected(p2c_dir),
            'blocking_n': len(blocking), 'blocking_text': [str(u.get('finding', ''))[:400] for u in blocking],
            'blocking_file': ex(J(p2c_dir, 'blocking_findings.json'))}

p3q_dir = J(d, 'phase3_critique')
p3q = J(p3q_dir, 'phase3_critique_output.json')
S['legacy_past_gate'] = ex(p3q)
canonical = J(p2c_dir, 'refined_candidate.json') if (S['p23']['verdict'] == 'patched' and S['p23']['refined']) else p2g
S['canonical'] = canonical
cand = rj(canonical) or {}

p3c_dir = J(d, 'phase3_collision')
side = rj(J(p3c_dir, '.collision_terms.json')) or {}
def tset(v):
    return sorted([t for t in (v or []) if t])
S['p31'] = {'hits': ex(J(p3c_dir, 'collision_hits.json')), 'sidecar': ex(J(p3c_dir, '.collision_terms.json')),
            'sig_pending': ex(J(p3c_dir, '.signature_extraction_pending')),
            'stale': ex(J(p3c_dir, '.collision_terms.json')) and (tset(side.get('signature_terms')) != tset(cand.get('signature_terms')) or tset(side.get('alias_terms')) != tset(cand.get('alias_terms')))}

p3qdoc = rj(p3q) if ex(p3q) else None
disp = [x for x in ((p3qdoc or {}).get('blocking_findings_disposition') or []) if isinstance(x, dict)]
refuted = [x for x in disp if x.get('status') == 'refuted']
upheld = [x for x in disp if x.get('status') == 'upheld']
rk = rj(J(p3q_dir, 'refutation_recheck.json')) or {}
rrefs = [str(x.get('finding_ref', ''))[:40] for x in refuted]
invalid = [r for r in (rk.get('rechecks') or []) if isinstance(r, dict) and r.get('refutation_valid') is False
           and any(ref and (str(r.get('finding_ref', ''))[:40].startswith(ref[:20]) or ref.startswith(str(r.get('finding_ref', ''))[:20])) for ref in rrefs)]
S['p32'] = {'exists': ex(p3q), 'verdict': (p3qdoc or {}).get('verdict') if isinstance(p3qdoc, dict) else None,
            'dispositions': len(disp), 'upheld': len(upheld), 'refuted': len(refuted),
            'recheck': ex(J(p3q_dir, 'refutation_recheck.json')), 'invalid_refutations': len(invalid),
            'rejected': rejected(p3q_dir),
            'targets_falsification': any(isinstance(t, dict) and t.get('scope') == 'falsification' for t in ((p3qdoc or {}).get('revision_targets') or []))}

p3r_dir = J(d, 'phase3_revise')
p3r = J(p3r_dir, 'phase3_revise_output.json')
p3rdoc = rj(p3r) if ex(p3r) else None
ra = rj(J(p3q_dir, 'falsification_reaudit.json')) or {}
S['p33'] = {'exists': ex(p3r), 'final': ex(J(p3r_dir, 'final_candidate.json')),
            'merged': ex(J(p3r_dir, 'final_candidate.json')) or bool((p3rdoc or {}).get('final_candidate')),
            'rewritten': bool((p3rdoc or {}).get('falsification_rewritten')),
            'brief': ex(J(p3r_dir, 'revise_brief.json')),
            'view': ex(J(p3q_dir, 'falsification_view.json')),
            'reaudit': ex(J(p3q_dir, 'falsification_reaudit.json')), 'reaudit_verdict': ra.get('verdict')}

atts = attempts(d)
S['attempts'] = []
for a in atts:
    doc = rj(J(d, a, 'phase3_critique', 'phase3_critique_output.json'))
    S['attempts'].append({'name': a, 'critique': doc is not None, 'lessons': lessons(doc),
                          'blocking_file': ex(J(d, a, 'phase2_coherence', 'blocking_findings.json'))})
S['lessons_now'] = lessons(p3qdoc)
S['retry_used'] = ex(J(d, '.retry_used'))
S['bottleneck_retry_used'] = ex(J(d, '.bottleneck_retry_used'))

p4 = J(d, 'phase4')
exp = J(p4, 'phase4_expansion.json')
todos = re.findall(r'<TODO\\[([^\\]]+)\\]', rt(exp)) if ex(exp) else []
fill_keys = set((rj(J(p4, 'fill_map.json')) or {}).keys())
derive_keys = set((rj(J(p4, 'derive_map.json')) or {}).keys()) if ex(J(p4, 'derive_map.json')) else set()
missing = [p for p in todos if p not in fill_keys | derive_keys]
S['p4'] = {'skeleton': ex(J(p4, 'phase4_skeleton.json')), 'fill_map': ex(J(p4, 'fill_map.json')),
           'expansion': ex(exp), 'derive_map': ex(J(p4, 'derive_map.json')),
           'method_view': ex(J(p4, 'method_view.json')),
           'view_stale': ex(J(p4, 'method_view.json')) and mt(J(p4, 'method_view.json')) < mt(exp),
           'impl': ex(J(p4, 'phase4_implementability.json')),
           'todos': len(todos),
           'missing_tech': [p for p in missing if p != 'title_zh' and not p.startswith('plain_')],
           'missing_plain': [p for p in missing if p == 'title_zh' or p.startswith('plain_')]}

sib = []
if S['flags']['crossrun']:
    try:
        parent = os.path.dirname(d.rstrip('/'))
        cands = [s for s in os.listdir(parent) if os.path.isdir(J(parent, s)) and J(parent, s) != d.rstrip('/') and ex(J(parent, s, 'phase0'))]
        for s in sorted(cands, key=lambda s: -mt(J(parent, s))):
            c = None
            for rel in ('phase3_revise/final_candidate.json', 'phase2_coherence/refined_candidate.json', 'phase2_generate/phase2_generate_output.json'):
                if ex(J(parent, s, rel)):
                    c = rj(J(parent, s, rel)) or {}
                    break
            if not c or not c.get('title'):
                continue
            sib.append('[' + s + '] "' + str(c.get('title')) + '"' + ((' (' + ', '.join([str(t) for t in (c.get('signature_terms') or [])[:4]]) + ')') if c.get('signature_terms') else ''))
            if len(sib) >= 5:
                break
    except Exception:
        pass
S['siblings'] = sib
print('__STATE__' + json.dumps(S))
`

async function probe(rd, phaseName) {
  const r = await sh(PY + ' - ' + shq(rd) + ' ' + shq(SKILL_DIR) + ' <<\'PYEOF\'\n' + STATE_PY + '\nPYEOF', base(rd) + ' state', { phase: phaseName, timeout: 180000 })
  const m = /__STATE__(\{[\s\S]*)$/.exec(r.out)
  if (!m) throw new Error('state probe produced no snapshot (rc=' + r.rc + '): ' + r.out.slice(-500))
  try { return JSON.parse(m[1].trim()) } catch (e) { throw new Error('state snapshot is not json: ' + m[1].slice(0, 300)) }
}

// ─────────────────────────────────────────────────────────── 6. the phase graph (port of scripts/next_step.py)
// One function, same order of checks as upstream, returning the ONE next step.
function decide(S, rd) {
  const d = rd
  const p0 = d + '/phase0'
  const p1 = d + '/phase1/phase1_output.json'
  const p2s = d + '/phase2_select/phase2_select_output.json'
  const p2g = d + '/phase2_generate/phase2_generate_output.json'
  const p2cDir = d + '/phase2_coherence'
  const p2c = p2cDir + '/phase2_coherence_output.json'
  const p3cDir = d + '/phase3_collision'
  const hits = p3cDir + '/collision_hits.json'
  const p3qDir = d + '/phase3_critique'
  const p3q = p3qDir + '/phase3_critique_output.json'
  const p3rDir = d + '/phase3_revise'
  const p3r = p3rDir + '/phase3_revise_output.json'
  const finalCand = p3rDir + '/final_candidate.json'
  const p4 = d + '/phase4'
  const canonical = S.canonical
  const bf = p2cDir + '/blocking_findings.json'
  const T = (state, note) => ({ t: 'terminal', state: state, note: note })

  // ---- terminal states --------------------------------------------------------
  if (S.terminal.dng) return T('TERMINAL — Phase 1 routed to do_not_generate.', d + '/do_not_generate.md')
  if (S.terminal.p3f) return T('TERMINAL — Phase 3 audit abandoned (retry budget exhausted).', d + '/phase_3_failed.md')
  if (S.terminal.cards) return T('DONE — all three idea cards rendered.', p4)

  // ---- Phase 0 ----------------------------------------------------------------
  if (!S.p0.lit_results) {
    if (!S.p0.queries) {
      return { t: 'seat', id: 'queries', seat: 'queries', state: 'Fresh run — no literature retrieved yet.',
        step: 'Phase 0 — produce the search queries (intent-recognition Map mode)',
        inputs: ['the user\'s research direction, verbatim: "' + DIRECTION + '"',
          BANK.intent_recognition.path + '  (inlined above — do not Read)',
          BANK.intake_routing.path + '  (inlined above — do not Read)'],
        output: d + '/.ideaspark_queries.json',
        notes: 'Write {"queries": [...], "named_papers": [...], "ood": null|"too_broad"|"no_anchor"}. Produce 4 search queries (3-5 only with a stated reason) — including one ESCAPE-MECHANISM query phrased in solution vocabulary, and apply the VOCABULARY-OWNERSHIP and CONCRETE-OBJECT tests to EVERY query. named_papers: every paper or system the direction NAMES but gives no link for (a bare name is invisible to the URL/ID regex and would never become an anchor); [] when it names none. Also apply the OOD short-circuit from the intake-routing reference: set ood to the trigger name when the direction is too broad or has no anchor, else null. Routing signal to return: the number of queries, and ood when it fired.' }
    }
    return { t: 'bash', id: 'phase0', state: 'Queries written; running retrieval.',
      step: 'Phase 0 — literature grounding (4 connectors)',
      long: { key: base(d) + '-phase0', file: p0 + '/lit_results.json' },
      buildLong: true, out: p0 + '/' }
  }
  if (S.flags.partition && !S.p0.partition_applied && !S.p0.lit_table) {
    if (!S.p0.partition_file) {
      return { t: 'seat', id: 'partition', seat: 'partition', state: 'Papers retrieved; running the relevance partition before tagging.',
        step: 'Phase 0.4 — relevance partition (core / adjacent / off_topic)',
        inputs: [p0 + '/user_query.txt  (the USER\'S ORIGINAL research question, verbatim)', p0 + '/lit_results.json'],
        output: p0 + '/relevance_partition.json',
        notes: 'Read every record\'s title+abstract and label each paper_id core|adjacent|off_topic (+ one-line reason). BE CONSERVATIVE: when unsure between core and adjacent pick core; hard-label off_topic ONLY when the paper is clearly outside the research direction (cross-domain keyword false positives, pure surveys, unrelated fields). Write a JSON list [{paper_id, relevance, reason}]; every record appears exactly once (' + S.p0.n_papers + ' records). This is the one precision pass — off_topic is dropped from the corpus next. Routing signal: N core / M adjacent / K off_topic.' }
    }
    return { t: 'bash', id: 'apply_partition', state: 'Relevance partition written; applying it.',
      step: 'Phase 0.4 — apply partition (deterministic)',
      run: [RS + ' apply_partition --out ' + shq(p0 + '/') + ' --partition ' + shq(p0 + '/relevance_partition.json') + ' && touch ' + shq(p0 + '/.partition_applied')] }
  }
  if (!S.p0.lit_table) {
    // Upstream: "Rows are per-paper independent, so for 40+ papers the tagging MAY be sharded across
    // 2-3 parallel fast-tier sub-agents (contiguous slices; assemble with lit_table_merge — it validates
    // 9-column shape, row count == paper count, and paper_id coverage)". Below 40 papers it stays one seat.
    const nShards = S.p0.n_papers >= 40 ? Math.min(3, Math.max(2, Math.ceil(S.p0.n_papers / 40))) : 0
    const common = 'Tag each paper with 1-3 of the 15 patterns + bottleneck + open_issue + retrieved_via per the rubric. EVERY paper you are given gets exactly one row — a paper that fits no pattern is tagged outside_taxonomy, never skipped or dropped.'
    if (!nShards) {
      return { t: 'seat', id: 'tagging', seat: 'tagging', state: 'Papers retrieved; lit_table.md not yet written.',
        step: 'Phase 0 — pattern tagging (' + S.p0.n_papers + ' papers)',
        inputs: [p0 + '/lit_results.json', BANK.pattern_rubric.path + '  (inlined above — do not Read)'],
        output: p0 + '/lit_table.md',
        notes: common + ' Write the 9-column table with its header row. Routing signal: the number of rows written.' }
    }
    return { t: 'seat', id: 'tagging', seat: 'tagging', shards: nShards,
      state: 'Papers retrieved; lit_table.md not yet written.',
      step: 'Phase 0 — pattern tagging (' + S.p0.n_papers + ' papers, ' + nShards + ' parallel shards)',
      inputs: [p0 + '/lit_slice<i>.json  (the contiguous slice of papers for this shard, in order)',
        BANK.pattern_rubric.path + '  (inlined above — do not Read)'],
      output: p0 + '/lit_rows_shard<i>.md',
      merge: p0,
      notes: common + ' Rows ONLY — nine cells each, one row per paper of YOUR slice, no header row, no code fence: the workflow assembles the shards with the validating merger, which rejects the whole set if any row is malformed or any paper is missing. Routing signal: the number of rows written.' }
  }
  if (S.flags.coverage && !S.p0.coverage_done && !S.p0.fulltext) {
    if (!S.p0.noms) {
      return { t: 'seat', id: 'coverage', seat: 'coverage', fanout: COVERAGE_JUDGES,
        state: 'lit_table.md written; running the coverage check before fulltext.',
        step: 'Phase 0.5 — coverage check (name load-bearing work the pool missed)',
        inputs: [p0 + '/user_query.txt  (the USER\'S ORIGINAL research question, verbatim)', p0 + '/lit_table.md'],
        output: p0 + '/host_refs_nominations.json',
        notes: 'Read the whole table against the user\'s direction and list up to 8 clearly load-bearing works that are ABSENT. PRIORITIZE the last ~12 months: recent/frontier work the dated retrieval windows likely under-sampled is the primary target — recovering it is why this channel exists, and it is what keeps the diagnosed gap current. Older foundational papers (canonical base policies, >12-month landmarks) are mostly Phase 1 lineage\'s job, not the corpus: nominate one ONLY when it is a load-bearing backbone/baseline the candidate will literally build on or be measured against, and keep such older picks to a small minority of the list. WebSearch is allowed HERE ONLY, and only to find TITLES — never to fabricate a record. Write a JSON list [{title, id_hint?(arxiv/DOI/URL), why(one line — state the recency, or the load-bearing-baseline reason if older), relevance(core|adjacent: core = a recent mechanism paper worth deep-reading; adjacent = a foundational backbone/baseline to cite but NOT deep-read), source: parametric|websearch}]. An empty list [] is a valid, honest output (the pool was already complete). Every nomination is verified by a connector next — unresolvable titles are rejected, not trusted. Routing signal: the number of nominations.' }
    }
    if (!S.p0.host_refs) {
      return { t: 'bash', id: 'add_host_refs', state: 'Coverage nominations written; resolving them via the connectors.',
        step: 'Phase 0.5 — resolve + merge host refs (deterministic)',
        run: [RS + ' add_host_refs --out ' + shq(p0 + '/') + ' --refs ' + shq(p0 + '/host_refs_nominations.json')] }
    }
    if (S.p0.new_host_ids.length && !S.p0.host_rows) {
      return { t: 'seat', id: 'tag_host', seat: 'tagging',
        state: S.p0.new_host_ids.length + ' host-recall paper(s) admitted; tag them into lit_table.',
        step: 'Phase 0.5 — tag the admitted host refs',
        inputs: [p0 + '/lit_results.json  (tag ONLY these newly-admitted paper_ids: ' + S.p0.new_host_ids.join(', ') + ')',
          BANK.pattern_rubric.path + '  (inlined above — do not Read)'],
        output: p0 + '/_host_rows.md',
        notes: 'Produce one lit_table row per newly-admitted paper_id (the same 9 columns, rows only — no header, no fence). The workflow merges them into lit_table.md next. Routing signal: the number of rows.' }
    }
    if (S.p0.new_host_ids.length) {
      return { t: 'bash', id: 'merge_host_rows', state: 'Host-recall rows written; merging them into lit_table.',
        step: 'Phase 0.5 — merge the admitted rows (deterministic)',
        run: [RS + ' lit_table_merge --out ' + shq(p0 + '/') + ' --shards ' + shq(p0 + '/lit_table.md') + ' ' + shq(p0 + '/_host_rows.md') + ' && touch ' + shq(p0 + '/.coverage_check_done')] }
    }
    return { t: 'bash', id: 'coverage_done', state: 'Coverage check complete (no new admissions); marking done.',
      step: 'Phase 0.5 — finalize coverage check', run: ['touch ' + shq(p0 + '/.coverage_check_done')] }
  }
  if (!S.p0.fulltext) {
    const pre = USER_REFS.map((u) => RS + ' add_user_ref --out ' + shq(p0 + '/') + ' --title ' + shq(u.title || '') + (u.id ? ' --id ' + shq(u.id) : '') + (u.raw_match ? ' --raw-match ' + shq(u.raw_match) : ''))
    return { t: 'bash', id: 'fulltext', state: 'lit_table.md written; full-text cache missing (Phase 1 hard-gates on it).',
      step: 'Phase 0+ — full-text fetch (mandatory)', pre: pre,
      long: { key: base(d) + '-fulltext', file: p0 + '/fulltext_cache.json' },
      cmd: RS + ' phase0_fulltext --out ' + shq(p0 + '/') }
  }

  // ---- Phase 1 ----------------------------------------------------------------
  if (!S.p1.exists) {
    const inputs = [p0 + '/user_query.txt  (the user question, verbatim) + intake context']
    if (COMPUTE) inputs.push('standing user compute default (IDEASPARK_DEFAULT_COMPUTE, overrides the factory default; the user query still wins): "' + COMPUTE + '"')
    inputs.push(p0 + '/lit_table.md')
    inputs.push(p0 + '/fulltext_cache.json' + (S.p0.fulltext_index ? ' — cheaper access: read ' + p0 + '/fulltext/index.json first (per-paper split view with tier/source_used/warning), then open only the candidate-pool papers\' .md files; the .json blob stays canonical' : ''))
    inputs.push(p0 + '/lit_results.json')
    if (S.bottleneck_retry_used) {
      const arch = S.attempts.length ? S.attempts[S.attempts.length - 1].name : 'attempt_1'
      inputs.push('BOTTLENECK-RETRY MODE (see the OPTIONAL bottleneck-retry input in the system prompt) — negative anchors: ' +
        d + '/' + arch + '/phase1/phase1_output.json (the RETIRED bottleneck_statement + anchor; do not re-frame it), plus ' +
        S.attempts.filter((a) => a.critique).map((a) => d + '/' + a.name + '/phase3_critique/phase3_critique_output.json').join(' and ') +
        ' (read ONLY paper_pointed_threat from each — the papers that killed the archived attempts define occupied ground)')
    }
    return { t: 'seat', id: 'phase1', seat: 'phase1', state: 'Phase 0 complete.', step: 'Phase 1 — bottleneck identification',
      inputs: inputs, output: p1,
      notes: 'Routing signal to return: `state` (proceed | do_not_generate).' }
  }
  if (S.p1.state === 'do_not_generate') {
    return { t: 'seat', id: 'dng', seat: 'writeup', state: 'Phase 1 routed to do_not_generate.',
      step: 'Write do_not_generate.md', inputs: [p1], output: d + '/do_not_generate.md',
      notes: 'Render the Phase 1 OOD rationale + remedial_steps as markdown; that file is the run\'s final output. Routing signal: none.' }
  }

  // ---- Phase 2 (2.1 + 2.2 in ONE seat) -----------------------------------------
  if (!S.p2.select || !S.p2.generate) {
    const slim = d + '/phase2_generate/closest_abstracts.json'
    const slimLine = slim + '  (pre-filtered closest_adjacent slice, materialized by the workflow; if it is missing, fall back to filtering ' + p0 + '/lit_results.json yourself)'
    let notes = 'The deterministic phase2_prepare command has already been executed by the workflow (its output file is listed under INPUT). Routing signal: none.'
    if (S.p0.on_topic_rows >= 20 && S.p1.closest_adjacent < 3) {
      notes += ' WARNING: only ' + S.p1.closest_adjacent + ' closest_adjacent entries against ~' + S.p0.on_topic_rows + ' on-topic papers — thin anchor grounding in a crowded lane.'
    }
    if (S.attempts.length) {
      const parts = []
      for (const a of S.attempts) {
        if (a.critique) parts.push(d + '/' + a.name + '/phase3_critique/phase3_critique_output.json')
        parts.push(d + '/' + a.name + '/phase2_select/phase2_select_output.json')
      }
      notes += S.bottleneck_retry_used
        ? ' RETRY MODE (new bottleneck, ONE candidate attempt): also read ' + parts.join(' and ') + ' as negative constraints — their paper_pointed_threat papers must not be re-collided with. The archived phase2 selections belong to the RETIRED bottleneck: context only, not binding.'
        : ' RETRY MODE: also read ' + parts.join(' and ') + ' as negative constraints (see the OPTIONAL retry input in the selection prompt); upheld blocking findings in ANY archived audit are POSITIVE directives the new mechanism must confront, and their `structural_requirement` (in the archived blocking_findings.json) names the identifying condition, the excluded sources, and the salvage — read it before re-selecting.'
    }
    const cross = S.siblings.length
      ? ['CROSS-RUN DEDUP (soft negative anchors — see the OPTIONAL cross-run input in the selection prompt): recent sibling runs already produced these mechanisms; do NOT re-propose the same mechanism family unless this direction demands it AND the delta is stated explicitly: ' + S.siblings.join(' | ')]
      : []
    const pre = [RS + ' phase2_prepare --dir ' + shq(d)]
    if (S.p2.select) {
      return { t: 'seat', id: 'generate', seat: 'generate', state: 'Phase 2.1 selection done; candidate not yet generated.',
        step: 'Phase 2.2 — sub-pattern picking + candidate generation', pre: pre,
        inputs: [p2s, p1, slimLine, SUBPAT + '/<picked C##>.md  (open the ONE card you pick per gap)'].concat(cross),
        output: p2g, notes: notes }
    }
    return { t: 'seat', id: 'ideate', seat: 'ideate', state: 'Phase 1 complete (state=proceed).',
      step: 'Phase 2.1 + 2.2 — ONE seat, TWO output files', pre: pre,
      inputs: [p0 + '/user_query.txt  (the user question, verbatim — phase1_output.json.intake is a summary of it, not a substitute)', p1,
        BANK.patterns_overview.path + '  (inlined above — do not Read)',
        BANK.companion_combos.path + '  (inlined above — do not Read)',
        p0 + '/lit_table.md', slimLine,
        BANK.subpatterns_overview.path + '  (inlined above — do not Read; then open the picked ' + SUBPAT + '/C##.md cards)'].concat(cross),
      output: p2s + ' then ' + p2g, notes: notes }
  }

  // ---- citation gate (deterministic; already run inside the state probe) --------
  if (S.gate.fail.length) {
    return { t: 'seat', id: 'cite_fix', seat: 'cite_fix', state: 'Phase 2.2 candidate FAILS the deterministic citation gate.',
      step: 'Fix the candidate before any Phase 3 work',
      inputs: [p2g].concat(S.gate.alias ? [p1] : []).concat([BANK.subpatterns_overview.path + '  (inlined above — do not Read)']),
      output: p2g + '  (edited in place)',
      notes: 'Validator findings: ' + S.gate.fail.join('; ').slice(0, 900) + '. ' + (S.gate.alias
        ? 'Add one alias_terms[] entry per collateral node named in phase1_output.json method_lineage, phrased in that field\'s vocabulary. Collision has not run yet — fixing now costs nothing.'
        : 'Fix the citation to a real C## cluster row from the inlined overview (or regenerate the entry with the card actually open).') +
        ' Change nothing else in the file. Routing signal: the fields you changed.' }
  }

  // ---- Phase 2.3 coherence gate ------------------------------------------------
  if (!S.p23.exists && !S.legacy_past_gate) {
    return { t: 'seat', id: 'coherence', seat: 'coherence', state: 'Citation gate passed; coherence gate not yet run.',
      step: 'Phase 2.3 — coherence gate (dry-run trace)' + (S.p31.hits ? '' : ' — 3.1 collision runs in parallel'),
      workdir: p2cDir,
      pre: ['rm -f ' + shq(bf) + ' ' + shq(p2cDir + '/refined_candidate.json')],
      launch: S.p31.hits ? null : { key: base(d) + '-collision', cmd: RS + ' phase3_collision --idea-json ' + shq(p2g) + ' --out ' + shq(p3cDir + '/'), file: hits },
      inputs: [p2g, p2s], output: p2c,
      notes: 'You are a FRESH context that did not author the candidate.' + (S.p31.hits ? '' : ' The 3.1 collision retrieval has already been launched in the background by the workflow — do only the 2.3 work.') +
        ' Routing signal to return: `verdict` (pass | patched) + the number of blocking unrepaired[] findings.' }
  }
  if (S.p23.exists && S.p23.verdict !== 'pass' && S.p23.verdict !== 'patched') {
    if (S.p23.rejected >= 2) {
      return { t: 'seat', id: 'gate_failed', seat: 'writeup',
        state: 'Coherence gate produced an invalid verdict ' + (S.p23.rejected + 1) + ' times — it cannot complete, and it is MANDATORY.',
        step: 'Write phase_3_failed.md (coherence gate could not complete)',
        inputs: [p2c + '  (the latest malformed output)', p2cDir + '/rejected_*  (the earlier ones)'],
        output: d + '/phase_3_failed.md',
        notes: 'Record that the blocker is the GATE, not the candidate: state the invalid verdict values seen, that Phase 2.3 is mandatory and cannot be bypassed, and the user-side options. Do NOT present the candidate as having failed on its merits. Routing signal: none.' }
    }
    return { t: 'seat', id: 'coherence_redo', seat: 'coherence',
      state: 'Coherence output exists but its verdict is invalid (' + String(S.p23.verdict) + ') — the gate did not complete.',
      step: 'Redo Phase 2.3 — coherence gate (dry-run trace)', workdir: p2cDir,
      pre: ['mkdir -p ' + shq(p2cDir + '/rejected_' + (S.p23.rejected + 1)) + ' && mv ' + shq(p2c) + ' ' + shq(p2cDir + '/rejected_' + (S.p23.rejected + 1) + '/')],
      inputs: [p2g, p2s], output: p2c,
      notes: 'The malformed file has been archived by the workflow (redo ' + (S.p23.rejected + 1) + ' of 3). Run the gate in a FRESH context. Valid verdicts: pass | patched. Routing signal: `verdict`.' }
  }
  if (S.p23.verdict === 'patched' && !S.p23.refined) {
    return { t: 'bash', id: 'coherence_merge', state: 'Coherence gate emitted repairs; merger not yet run.',
      step: 'Phase 2.3 merger (deterministic)',
      run: [RS + ' phase3_merge_revisions --phase2 ' + shq(p2g) + ' --revisions ' + shq(p2c) + ' --out ' + shq(p2cDir + '/') + ' --out-name refined_candidate.json'] }
  }

  // ---- Phase 3.1 collision -----------------------------------------------------
  if (S.p31.hits && S.p31.sidecar && !S.legacy_past_gate && S.p31.stale) {
    return { t: 'bash', id: 'collision_restale', state: 'Collision hits were retrieved with terms a 2.3 patch has since changed.',
      step: 'Re-run Phase 3.1 collision with the repaired terms',
      long: { key: base(d) + '-collision', file: hits }, force: true,
      cmd: RS + ' phase3_collision --idea-json ' + shq(canonical) + ' --out ' + shq(p3cDir + '/') }
  }
  if (S.p31.sig_pending && !S.p31.hits) {
    return { t: 'seat', id: 'terms', seat: 'terms', state: 'Phase 3.1 stalled: candidate lacks signature_terms[].',
      step: 'Fill signature_terms and re-invoke collision',
      inputs: [canonical, BANK.intent_recognition.path + '  (inlined above — do not Read; use its Collision mode)'],
      output: canonical + '  (add signature_terms[] — 3-5 tight terms, 3-7 words each — and alias_terms[] if absent)',
      after: { key: base(d) + '-collision', cmd: RS + ' phase3_collision --idea-json ' + shq(canonical) + ' --out ' + shq(p3cDir + '/'), file: hits },
      notes: 'Edit ONLY those two array fields in the candidate; change nothing else. Routing signal: the terms you added.' }
  }
  if (!S.p31.hits) {
    return { t: 'bash', id: 'collision', state: 'Candidate passed the citation gate.',
      step: 'Phase 3.1 — dual-channel collision retrieval (signature@10mo + alias@48mo)',
      long: { key: base(d) + '-collision', file: hits },
      cmd: RS + ' phase3_collision --idea-json ' + shq(canonical) + ' --out ' + shq(p3cDir + '/') }
  }

  // ---- Phase 3.2 audit ---------------------------------------------------------
  const blockingLine = S.p23.blocking_file
    ? bf + '  (the 2.3 gate\'s blocking findings — a self-contained executed-evidence slice; disposition each one)'
    : '2.3 unrepaired BLOCKING findings (verbatim, inline fallback): ' + S.p23.blocking_text.join(' | ')
  const auditInputs = () => [canonical, p2s, p0 + '/lit_table.md']
    .concat(S.p23.blocking_n ? [blockingLine] : [])
    .concat([hits, BANK.anti_patterns.path + '  (inlined above — do not Read)', SUBPAT + '/<each cited C##>.md'])
  const dispositionNote = ' The report MUST contain blocking_findings_disposition[] with one entry per blocking finding (refute only via a concrete modeling/arithmetic flaw); while any entry is upheld, advance is forbidden.'
  if (!S.p32.exists) {
    return { t: 'seat', id: 'audit', seat: 'audit', state: 'Collision hits retrieved.', step: 'Phase 3.2 — audit-and-verdict (5 checks)',
      inputs: auditInputs(), output: p3q,
      notes: 'Routing signal to return: `verdict` (advance | revise | abandon) + verdict_rationale.' + (S.p23.blocking_n ? dispositionNote : '') }
  }
  let verdict = S.p32.verdict
  let auditNoncompliant = false
  const arch = p3qDir + '/rejected_' + (S.p32.rejected + 1)
  const archiveCmd = 'mkdir -p ' + shq(arch) + ' && mv ' + shq(p3q) + ' ' + shq(arch) + '/ && { mv ' + shq(p3qDir + '/refutation_recheck.json') + ' ' + shq(arch) + '/ 2>/dev/null || true; }'
  if (S.p23.blocking_n && (verdict === 'advance' || verdict === 'revise') && S.p32.rejected >= 2) {
    auditNoncompliant = true
    verdict = 'abandon'
  }
  if (S.p23.blocking_n && (verdict === 'advance' || verdict === 'revise')) {
    if (S.p32.dispositions >= S.p23.blocking_n && S.p32.refuted && !S.p32.recheck) {
      return { t: 'seat', id: 'recheck', seat: 'recheck',
        state: 'Phase 3.2 verdict = ' + verdict + ' with ' + S.p32.refuted + ' blocking finding(s) marked REFUTED.',
        step: 'Refutation re-check (single bounded call)',
        inputs: [S.p23.blocking_file ? bf : '2.3 blocking findings (verbatim): ' + S.p23.blocking_text.join(' | '),
          p3q + '  (read ONLY blocking_findings_disposition[])', canonical + '  (ONLY to verify quoted step text)'],
        output: p3qDir + '/refutation_recheck.json',
        notes: 'Routing signal: per-finding `refutation_valid` (true|false). When in doubt, the executed finding stands (refutation_valid=false). This call judges the refutation, not the candidate.' }
    }
    if (S.p32.refuted && S.p32.invalid_refutations) {
      return { t: 'seat', id: 'audit_invalid_refutation', seat: 'audit',
        state: 'Phase 3.2 verdict = ' + verdict + ', but the refutation re-check judged ' + S.p32.invalid_refutations + ' refutation(s) INVALID.',
        step: 'Re-run Phase 3.2 (overwrite the report) — invalidly-refuted findings count as upheld',
        pre: [archiveCmd],
        inputs: auditInputs().concat([p3qDir + '/refutation_recheck.json  (the re-check verdicts — these refutations are invalid and must not be repeated)']),
        output: p3q,
        notes: 'The rejected report has been archived by the workflow (rejection ' + (S.p32.rejected + 1) + ' of 2; after that the un-cleared findings route to abandon). Regenerate the FULL audit. The re-checked findings count as UPHELD: the verdict is capped at revise (targets confronting each) or abandon. Routing signal: `verdict`.' }
    }
    if (S.p32.dispositions < S.p23.blocking_n) {
      return { t: 'seat', id: 'audit_undispositioned', seat: 'audit',
        state: 'Phase 3.2 verdict = ' + verdict + ', but the 2.3 gate holds ' + S.p23.blocking_n + ' BLOCKING executed finding(s) and the report dispositioned only ' + S.p32.dispositions + '.',
        step: 'Re-run Phase 3.2 WITH the blocking findings (overwrite the report)',
        pre: [archiveCmd], inputs: auditInputs(), output: p3q,
        notes: 'The rejected report has been archived by the workflow (rejection ' + (S.p32.rejected + 1) + ' of 2). Regenerate the FULL audit including blocking_findings_disposition[] (one entry per finding; refute only via a concrete modeling/arithmetic flaw — executed evidence outranks unexecuted reasoning). While any finding is upheld, advance is forbidden. Routing signal: `verdict`.' }
    }
    if (verdict === 'advance' && S.p32.upheld) {
      return { t: 'seat', id: 'audit_inconsistent', seat: 'audit',
        state: 'Phase 3.2 verdict = advance, but the audit itself UPHELD ' + S.p32.upheld + ' blocking finding(s) — advance is forbidden while one stands.',
        step: 'Re-run Phase 3.2 (overwrite the report) — the verdict must be revise or abandon',
        pre: [archiveCmd], inputs: auditInputs(), output: p3q,
        notes: 'The rejected report has been archived by the workflow (rejection ' + (S.p32.rejected + 1) + ' of 2). Keep the five checks; fix the verdict layer: upheld blocking findings cap the verdict at revise (fix_direction confronts the obstacle) or abandon. Routing signal: `verdict`.' }
    }
  }

  // ---- abandon → information-gain retry ----------------------------------------
  if (verdict === 'abandon') {
    const key = (l) => l[0] + ' ' + l[1]
    const seen = new Set()
    for (const a of S.attempts) for (const l of a.lessons) seen.add(key(l))
    const now = new Set(S.lessons_now.map(key))
    if (auditNoncompliant) for (const t of S.p23.blocking_text) now.add('finding' + ' ' + t.slice(0, 40))
    const fresh = [...now].filter((x) => !seen.has(x))
    const cyclesUsed = S.attempts.length + 1
    const framingIndicted = [...now].some((x) => x.startsWith('threat ')) && [...seen].some((x) => x.startsWith('threat '))
    const nextIdx = S.attempts.length ? (parseInt(S.attempts[S.attempts.length - 1].name.slice(8), 10) + 1) : 1
    const archDir = d + '/attempt_' + nextIdx
    const candDirs = ['phase2_select', 'phase2_generate', 'phase2_coherence', 'phase3_collision', 'phase3_critique', 'phase3_revise']
    const failInputs = [p3q].concat(S.attempts.filter((a) => a.critique).map((a) => d + '/' + a.name + '/phase3_critique/phase3_critique_output.json'))
    const failStep = { t: 'seat', id: 'p3f', seat: 'writeup', step: 'Write phase_3_failed.md', inputs: failInputs, output: d + '/phase_3_failed.md',
      notes: 'Include EVERY attempt\'s verdict_rationale + triggering checks + the user-side options (drop the direction / change the framing / re-run with a different direction). That file is the run\'s final output. Routing signal: none.' }

    if (S.bottleneck_retry_used) {
      return Object.assign({}, failStep, { id: 'p3f_bottleneck', state: 'Phase 3.2 verdict = abandon — retry budget exhausted (bottleneck retry already used; its one candidate attempt failed).' })
    }
    if (!S.attempts.length) {
      return { t: 'bash', id: 'attempt_1',
        state: 'Phase 3.2 verdict = abandon' + (auditNoncompliant ? ' (the audit could not produce a compliant report in 3 tries — the executed blocking findings stand un-cleared)' : '') + ' — internal retry available.',
        step: 'Archive attempt 1 and regenerate Phase 2.1+2.2 under negative constraints',
        run: ['mkdir -p ' + shq(archDir) + ' && for x in ' + candDirs.join(' ') + '; do [ -d ' + shq(d) + '/"$x" ] && mv ' + shq(d) + '/"$x" ' + shq(archDir) + '/; done; touch ' + shq(d + '/.retry_used')] }
    }
    if (framingIndicted) {
      return { t: 'bash', id: 'bottleneck_retry',
        state: 'Abandon with a REPEATED unaddressable-subsumption lesson across attempts — the occupied space binds at the framing level.',
        step: 'Archive attempt ' + nextIdx + ' (incl. phase1) and re-diagnose the bottleneck',
        run: ['mkdir -p ' + shq(archDir) + ' && for x in phase1 ' + candDirs.join(' ') + '; do [ -d ' + shq(d) + '/"$x" ] && mv ' + shq(d) + '/"$x" ' + shq(archDir) + '/; done; touch ' + shq(d + '/.bottleneck_retry_used')] }
    }
    if (fresh.length && cyclesUsed < 3) {
      return { t: 'bash', id: 'attempt_' + nextIdx,
        state: 'Phase 3.2 verdict = abandon, but this attempt produced ' + fresh.length + ' NEW binding lesson(s) — a directed retry is justified by information gain.',
        step: 'Archive attempt ' + nextIdx + ' and regenerate Phase 2.1+2.2 under the accumulated lessons',
        run: ['mkdir -p ' + shq(archDir) + ' && for x in ' + candDirs.join(' ') + '; do [ -d ' + shq(d) + '/"$x" ] && mv ' + shq(d) + '/"$x" ' + shq(archDir) + '/; done; touch ' + shq(d + '/.retry_used')] }
    }
    return Object.assign({}, failStep, { id: 'p3f_exhausted',
      state: 'Phase 3.2 verdict = abandon — retry budget exhausted (' + (fresh.length ? 'candidate-cycle cap (3) reached under this framing' : 'no NEW binding information — this attempt\'s lessons repeat what the generation already had') + ').' })
  }

  // ---- revise path --------------------------------------------------------------
  if (verdict === 'revise') {
    if (!S.p33.exists) {
      return { t: 'seat', id: 'revise', seat: 'revise', state: 'Phase 3.2 verdict = revise.', step: 'Phase 3.3 — emit the revision patch',
        pre: [RS + ' phase3_revise_brief --critique ' + shq(p3q) + ' --out ' + shq(p3rDir + '/')],
        inputs: [canonical, p2s, p3rDir + '/revise_brief.json  (the revision brief, materialized by the workflow; its _brief_note says when to consult the full report at ' + p3q + ')'],
        output: p3r,
        notes: 'The deterministic brief command has already been executed by the workflow. Patch-only: applied_revisions[] — never echo the candidate.' +
          (S.p32.targets_falsification ? ' One revision_target has scope=falsification — emit ONE rewrite_falsification entry for it (same experiment/metric/claim, structure repaired).' : '') +
          ' Routing signal: the number of applied revisions.' }
    }
    if (!S.p33.merged) {
      return { t: 'bash', id: 'revise_merge', state: 'Revision patch written; merger not yet run.', step: 'Phase 3.3 merger (deterministic)',
        run: [RS + ' phase3_merge_revisions --phase2 ' + shq(canonical) + ' --revisions ' + shq(p3r) + ' --critique ' + shq(p3q) + ' --out ' + shq(p3rDir + '/')] }
    }
    if (S.p33.rewritten && !S.p33.reaudit) {
      return { t: 'seat', id: 'reaudit', seat: 'reaudit', state: 'falsification_prediction was rewritten (audited exception) — re-audit REQUIRED before Phase 4.',
        step: 'Falsification re-audit (single-check)',
        pre: [RS + ' phase3_falsification_view --candidate ' + shq(finalCand) + ' --out ' + shq(p3qDir + '/')],
        inputs: [p3qDir + '/falsification_view.json  (the falsification slice, materialized by the workflow)'],
        output: p3qDir + '/falsification_reaudit.json',
        notes: 'The deterministic view command has already been executed by the workflow. Routing signal: `verdict` (advance | abandon). Exactly one rewrite attempt per run — deficient again means abandon.' }
    }
    if (S.p33.rewritten && S.p33.reaudit_verdict === 'abandon') {
      return { t: 'seat', id: 'p3f_falsification', seat: 'writeup', state: 'Falsification re-audit verdict = abandon (rewrite still deficient).',
        step: 'Write phase_3_failed.md', inputs: [p3q, p3qDir + '/falsification_reaudit.json'], output: d + '/phase_3_failed.md',
        notes: 'Name the original structural deficiency AND why the one permitted rewrite still fails. That file is the run\'s final output. Routing signal: none.' }
    }
  }

  // ---- Phase 4 -------------------------------------------------------------------
  const onRevise = verdict === 'revise' && S.p33.merged
  const candidatePath = onRevise ? (S.p33.final ? finalCand : p3r) : canonical
  if (!S.p4.expansion && !S.p4.skeleton) {
    let cmd = RS + ' phase4_skeleton --candidate ' + shq(candidatePath) + ' --phase1 ' + shq(p1) + ' --phase2-select ' + shq(p2s) + ' --phase3-critique ' + shq(p3q) + ' '
    if (onRevise) cmd += '--phase3-revise ' + shq(p3r) + ' '
    cmd += '--phase0-dir ' + shq(p0 + '/') + ' --collision ' + shq(hits) + ' --out ' + shq(p4 + '/')
    return { t: 'bash', id: 'skeleton', state: 'Gauntlet cleared (' + verdict + ' path).', step: 'Phase 4 skeleton (deterministic)', run: [cmd], phase: 'Phase 4' }
  }
  if (!S.p4.expansion && !S.p4.fill_map) {
    return { t: 'seat', id: 'fill', seat: 'fill', state: 'Skeleton built.', step: 'Phase 4.fill — author the TECHNICAL prose TODOs',
      inputs: [p4 + '/phase4_skeleton.json'], output: p4 + '/fill_map.json',
      notes: 'Flat {TODO-path: prose} map ONLY — the assembler refuses kill-switch roots. SKIP the derive-owned paths (title_zh + all plain_* — see the exclusion list in the system prompt): a separate step authors them from your finished prose. Routing signal: the number of paths authored.' }
  }
  if (!S.p4.expansion) {
    return { t: 'bash', id: 'assemble1', state: 'fill_map written.', step: 'Phase 4 assemble — partial (deterministic)', phase: 'Phase 4',
      run: [RS + ' phase4_assemble --skeleton ' + shq(p4 + '/phase4_skeleton.json') + ' --fill-map ' + shq(p4 + '/fill_map.json') + ' --out ' + shq(p4 + '/')] }
      // the assembler exits 0 with a WARN about the derive-owned placeholders — that WARN is expected here
  }
  if (S.p4.todos) {
    if (S.p4.missing_tech.length) {
      return { t: 'seat', id: 'fill_fix', seat: 'fill', state: 'fill_map is missing technical TODO paths.',
        step: 'Fix fill_map — author the missing technical paths',
        inputs: [p4 + '/phase4_skeleton.json', p4 + '/fill_map.json'],
        output: p4 + '/fill_map.json  (edited in place — add the missing keys)',
        notes: 'Missing: ' + S.p4.missing_tech.slice(0, 8).join(', ') + '. Add ONLY these keys to the existing fill_map (derive-owned paths stay excluded). Routing signal: the keys added.' }
    }
    if (!S.p4.derive_map || S.p4.missing_plain.length) {
      return { t: 'seat', id: 'derive', seat: 'derive', state: 'Partial expansion assembled; plain-register fields pending.',
        step: 'Phase 4.derive — plain-register derivation',
        inputs: [p4 + '/phase4_expansion.json'], output: p4 + '/derive_map.json',
        notes: 'Mechanical register derivation + translation, NO new facts.' +
          (S.p4.derive_map && S.p4.missing_plain.length ? ' REGENERATION: the existing derive_map does not cover ' + S.p4.missing_plain.slice(0, 6).join(', ') + ' — rewrite the FULL map including them.' : '') +
          ' Routing signal: none.' }
    }
    return { t: 'bash', id: 'assemble2', state: 'derive_map written; expansion still partial.', phase: 'Phase 4',
      step: 'Phase 4 assemble — final merge + method view (deterministic)',
      run: [RS + ' phase4_assemble --skeleton ' + shq(p4 + '/phase4_skeleton.json') + ' --fill-map ' + shq(p4 + '/fill_map.json') + ' --fill-map ' + shq(p4 + '/derive_map.json') + ' --out ' + shq(p4 + '/'),
        RS + ' phase4_method_view --expansion ' + shq(p4 + '/phase4_expansion.json') + ' --out ' + shq(p4 + '/')] }
  }
  if (!S.p4.impl) {
    if (!S.p4.method_view || S.p4.view_stale) {
      return { t: 'bash', id: 'method_view', state: 'Expansion complete; method view missing or stale.', phase: 'Phase 4',
        step: 'Phase 4 method-view extract (deterministic)',
        run: [RS + ' phase4_method_view --expansion ' + shq(p4 + '/phase4_expansion.json') + ' --out ' + shq(p4 + '/')] }
    }
    return { t: 'seat', id: 'impl', seat: 'impl', state: 'Expansion assembled.', step: 'Phase 4.1.5 — implementability audit',
      inputs: [p4 + '/method_view.json  (the method-only slice; fall back to ' + p4 + '/phase4_expansion.json only if the view is missing)'],
      output: p4 + '/phase4_implementability.json',
      notes: 'Fresh skeptical-engineer persona (a separate call from the 4.fill author). Compute-agnostic by design. Routing signal: the number of underspecified_points.' }
  }
  return { t: 'validate', id: 'validate', state: 'All Phase 4 JSONs present; cards not yet rendered.', phase: 'Phase 4',
    step: 'Validate, then render the idea cards',
    validate: RS + ' validate --phase1 ' + shq(p1) + ' --phase2 ' + shq(canonical) + ' --phase2-select ' + shq(p2s) +
      ' --phase3 ' + shq(onRevise ? p3r : p3q) + ' --phase4 ' + shq(p4 + '/phase4_expansion.json') + ' --phase4-impl ' + shq(p4 + '/phase4_implementability.json'),
    render: RS + ' phase4_render --expansion ' + shq(p4 + '/phase4_expansion.json') + ' --out ' + shq(p4 + '/') }
}

// ─────────────────────────────────────────────────────────── 7. deterministic helpers run as python
const UNION_PY = `import json, re, sys, os
out, cap = sys.argv[1], int(sys.argv[2])
files = sys.argv[3:]
def norm(t):
    return re.sub(r'[^a-z0-9]+', ' ', str(t or '').lower()).strip()
seen, rows = {}, []
for f in files:
    try:
        doc = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    if not isinstance(doc, list):
        continue
    for r in doc:
        if not isinstance(r, dict) or not r.get('title'):
            continue
        k = norm(r.get('title'))[:90]
        if not k:
            continue
        if k in seen:
            seen[k]['n'] += 1
            continue
        seen[k] = {'n': 1, 'row': r}
        rows.append(k)
ranked = sorted(rows, key=lambda k: (-seen[k]['n'], rows.index(k)))
keep = [seen[k]['row'] for k in ranked[:cap]]
drop = len(ranked) - len(keep)
json.dump(keep, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('UNION kept=%d dropped=%d agreed=%d sources=%d' % (len(keep), drop, sum(1 for k in ranked[:cap] if seen[k]['n'] > 1), len(files)))
`
const SPLIT_PY = `import json, math, sys
p, n = sys.argv[1], int(sys.argv[2])
doc = json.load(open(p + '/lit_results.json', encoding='utf-8'))
papers = doc['papers'] if isinstance(doc, dict) and 'papers' in doc else doc
size = math.ceil(len(papers) / n)
for i in range(n):
    json.dump(papers[i * size:(i + 1) * size], open(p + '/lit_slice%d.json' % i, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('SPLIT %d %d' % (n, len(papers)))
`
const VERIFY_PY = `import json, os, sys
bad = []
for p in sys.argv[1:]:
    if not os.path.exists(p):
        bad.append(os.path.basename(p) + ': missing'); continue
    if os.path.getsize(p) == 0:
        bad.append(os.path.basename(p) + ': empty'); continue
    if p.endswith('.json'):
        try:
            json.load(open(p, encoding='utf-8'))
        except Exception as e:
            bad.append(os.path.basename(p) + ': unparseable json (' + str(e)[:80] + ')')
print('__OUT_BAD ' + '; '.join(bad) if bad else '__OUT_OK')
`
const SCORE_PY = `import json, os, sys, statistics
out = sys.argv[1]
files = sys.argv[2:]
reports, axes = [], {}
for f in files:
    try:
        doc = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    doc['_judge'] = os.path.basename(f).replace('.json', '')
    reports.append(doc)
agg = {'judges': [r['_judge'] for r in reports], 'ideas': {}, 'pairwise': [], 'divergence': []}
for r in reports:
    for it in (r.get('ideas') or []):
        rid = str(it.get('run') or it.get('idea') or '?')
        a = agg['ideas'].setdefault(rid, {'A': [], 'B': [], 'C': [], 'overall': [], 'verdict': []})
        for k in ('A', 'B', 'C', 'overall'):
            v = it.get(k)
            if isinstance(v, (int, float)):
                a[k].append(v)
        if it.get('verdict'):
            a['verdict'].append(it['verdict'])
    if r.get('pairwise'):
        agg['pairwise'].append({'judge': r['_judge'], 'winner': r['pairwise'].get('winner'), 'why': str(r['pairwise'].get('why', ''))[:300]})
for rid, a in agg['ideas'].items():
    summ = {}
    for k in ('A', 'B', 'C', 'overall'):
        if a[k]:
            summ[k] = {'mean': round(statistics.fmean(a[k]), 2), 'min': min(a[k]), 'max': max(a[k]), 'n': len(a[k])}
    summ['verdicts'] = a['verdict']
    for k in ('A', 'B', 'C'):
        if a[k] and (max(a[k]) - min(a[k])) >= 2:
            agg['divergence'].append(rid + ' axis ' + k + ': ' + ', '.join(str(x) for x in a[k]) + ' (spread ' + str(max(a[k]) - min(a[k])) + ')')
    if len(set(a['verdict'])) > 1:
        agg['divergence'].append(rid + ' verdict split: ' + ', '.join(a['verdict']))
    a.clear(); a.update(summ)
if agg['pairwise'] and len(set(p['winner'] for p in agg['pairwise'])) > 1:
    agg['divergence'].append('pairwise winner split: ' + ', '.join(p['judge'] + '=' + str(p['winner']) for p in agg['pairwise']))
json.dump(agg, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('SCORE judges=%d ideas=%d divergences=%d' % (len(reports), len(agg['ideas']), len(agg['divergence'])))
`
const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    written: { type: 'array', items: { type: 'string' } },
    signal: { type: 'string' },
    note: { type: 'string' },
  },
  required: ['ok', 'written'],
}

// ─────────────────────────────────────────────────────────── 8. one run
async function driveRun(id) {
  const rd = K > 1 ? ROOT + '/' + id : ROOT
  const st = { id: id, dir: rd, state: 'running', steps: 0, seats: [], note: '', validate_rc: null, validate_repairs: 0, validate_note: '', cards: [], history: [] }
  let repaired = null                     // the seat a deterministic step just rejected (self-heal target, once)
  try {
    let S = await probe(rd, 'Phase 0')
    for (let i = 0; i < MAX_STEPS; i++) {
      st.steps = i + 1
      const step = decide(S, rd)
      st.history.push(step.id || step.t)
      log(id + ' [' + (i + 1) + '] ' + step.state + ' → ' + (step.step || step.note || ''))
      if (step.t === 'terminal') {
        st.state = /^DONE/.test(step.state) ? 'done' : (/do_not_generate/.test(step.state) ? 'do_not_generate' : 'phase_3_failed')
        st.note = step.state
        if (st.state === 'done') st.cards = ['idea.std.zh.md', 'idea.std.en.md', 'idea.detail.en.md'].map((c) => rd + '/phase4/' + c)
        break
      }
      const phaseName = step.phase || (step.seat ? phaseOf(step.seat) : (i < 8 ? 'Phase 0' : 'Gauntlet'))

      // ---- validate + render (upstream: fix only the named contract, cap 2, then render as-is)
      if (step.t === 'validate') {
        let rc = -1, out = ''
        for (let rep = 0; rep <= 2; rep++) {
          const v = await sh('{ ' + step.validate + '\n}; rc=$?; echo "__RC0=$rc"', id + ' validate' + (rep ? ' after repair ' + rep : ''), { phase: phaseName, timeout: 300000 })
          rc = Number((/__RC0=(\d+)/.exec(v.out) || [])[1]); out = v.out
          if (!Number.isFinite(rc)) rc = -1
          if (rc === 0 || rep === 2) break
          const line = out.split('\n').find((l) => /✗/.test(l)) || ''
          const target = /\[(expansion_completeness|kill_switch_integrity|chinese_word_order)\]/.test(line) ? 'fill'
            : (/\[implementability_(completeness|readability)\]/.test(line) ? 'impl' : null)
          if (!target) { log(id + ' validate failed on a contract that is never edited to silence a validator — rendering as-is'); break }
          log(id + ' validate FAIL → repair ' + target)
          const file = target === 'fill' ? rd + '/phase4/phase4_expansion.json' : rd + '/phase4/phase4_implementability.json'
          const findings = out.split('\n').filter((l) => /[✗⚠]/.test(l)).join('\n').slice(0, 3000)
          const inputs = [file + '  (the file to repair, in place)', rd + '/phase4/method_view.json  (method-only slice)']
          if (target === 'fill') inputs.push(rd + '/phase3_revise/final_candidate.json  (upstream kill-switch values when the revise path ran; if it does not exist use the next file)', rd + '/phase2_generate/phase2_generate_output.json  (upstream kill-switch values)')
          const r = await seat(target, { rd: rd, step: 'validate repair — ' + target, inputs: inputs, output: file, phase: phaseName,
            notes: 'VALIDATE REPAIR (upstream rule: fix ONLY the named contract; the workflow re-validates; cap 2). The findings below name the exact missing or malformed sections of the OUTPUT file. Read it whole, repair exactly those items, keep every other field byte-identical, and write the file whole. The kill-switch fields falsification_prediction and compute_budget may only be RESTORED to their upstream value, never rewritten; citation-guarded fields are never edited. FINDINGS:\n' + findings },
            id + ': validate repair ' + target)
          st.seats.push({ kind: target, step: 'validate repair', ok: !!(r && r.ok) })
          st.validate_repairs++
          if (!r || !r.ok) break
        }
        st.validate_rc = rc
        if (rc !== 0) st.validate_note = out.split('\n').filter((l) => /✗/.test(l)).slice(0, 6).join(' | ').slice(0, 600)
        await shOk(step.render, id + ' render', { phase: phaseName, timeout: 300000 })
        S = await probe(rd, phaseName)
        continue
      }

      // ---- deterministic steps
      if (step.t === 'bash') {
        for (const c of step.pre || []) await shOk(c, id + ' prep', { phase: phaseName })
        if (step.buildLong || step.long) {
          let cmd = step.cmd
          if (step.buildLong) {                        // Phase 0 retrieval: built from the queries the seat wrote
            const q = await sh('cat ' + shq(rd + '/.ideaspark_queries.json'), id + ' read queries', { phase: phaseName, timeout: 60000 })
            let doc = null
            try { doc = JSON.parse((/\{[\s\S]*\}/.exec(q.out) || [''])[0]) } catch (e) { doc = null }
            if (!doc || !(doc.queries || []).length) throw new Error('queries file unreadable: ' + q.out.slice(-300))
            if (doc.ood) { log(id + ' OOD short-circuit at intake: ' + doc.ood) }
            const named = (doc.named_papers || []).filter(Boolean)
            cmd = RS + ' phase0 --query ' + shq(DIRECTION) + ' --queries ' + shq(doc.queries.join('|')) +
              (named.length ? ' --named-papers ' + shq(named.join('|')) : '') + ' --out ' + shq(step.out)
          }
          const job = step.long
          if (step.force) await shOk('rm -f ' + shq(JOBS + '/' + job.key + '.pid'), id + ' clear job', { phase: phaseName, timeout: 60000 })
          if (!(await launch(job.key, cmd, id + ' ' + job.key, phaseName))) throw new Error('could not launch ' + job.key)
          const w = await waitFor(job.key, job.file, id + ' ' + job.key, phaseName)
          if (!w.done) throw new Error(job.key + ' produced no ' + base(job.file) + ': ' + w.out.slice(-600))
        } else {
          let healed = false
          for (const c of step.run) {
            const r = await sh('{ ' + c + '\n}; rc=$?; echo "__RC0=$rc"', id + ' ' + step.id, { phase: phaseName })
            if (!/__RC0=0/.test(r.out)) {
              // the deterministic consumer rejected the last seat's output (e.g. the merger on a malformed
              // patch): send that seat back ONCE with the rejection, then let decide() re-emit this step whole.
              if (!repaired) throw new Error('command failed: ' + c.slice(0, 160) + ' :: ' + r.out.slice(-500))
              log(id + ' ' + repaired.seat + ': deterministic step rejected its output — one repair pass')
              const why = 'PREVIOUS ATTEMPT REJECTED: the deterministic step that consumes your output failed — `' + c.slice(0, 200) + '` :: ' + r.out.replace(/__RC0=\d+/g, '').trim().slice(-900) + ' — read your output file, fix exactly what the error names, and write it again in full.'
              const rr = await seat(repaired.seat, Object.assign({}, repaired.dyn, { notes: (repaired.dyn.notes || '') + ' ' + why }), id + ': repair ' + repaired.seat)
              repaired = null                       // one repair per producer; a second failure raises
              if (!rr || !rr.ok) throw new Error('repair pass failed on ' + c.slice(0, 120))
              healed = true
              break
            }
          }
          if (healed) { S = await probe(rd, phaseName); continue }
        }
        repaired = null
        S = await probe(rd, phaseName)
        continue
      }

      // ---- seats
      for (const c of step.pre || []) await shOk(c, id + ' prep ' + step.id, { phase: phaseName })
      if (step.launch) {
        if (!(await launch(step.launch.key, step.launch.cmd, id + ' collision', phaseName))) throw new Error('could not launch collision')
      }
      const dyn = { rd: rd, step: step.step, inputs: step.inputs, output: step.output, notes: step.notes, workdir: step.workdir, phase: phaseName }
      let r
      if (step.shards) {
        // upstream's sanctioned parallel tagging: contiguous slices → rows-only shards → validating merger
        const sp = await sh(PY + ' - ' + shq(step.merge) + ' ' + step.shards + ' <<\'PYEOF\'\n' + SPLIT_PY + '\nPYEOF', id + ' split slices', { phase: phaseName, timeout: 120000 })
        if (!/SPLIT \d+ \d+/.test(sp.out)) throw new Error('could not slice lit_results.json: ' + sp.out.slice(-300))
        let complaint = ''
        for (let round = 0; round < 2; round++) {
          const rs = await parallel(Array.from({ length: step.shards }, (_, j) => () => seat(step.seat, Object.assign({}, dyn, {
            step: step.step + ' — shard ' + j + ' of ' + step.shards,
            inputs: [step.merge + '/lit_slice' + j + '.json  (the papers of this shard, in order)'].concat(step.inputs.slice(1)),
            output: step.merge + '/lit_rows_shard' + j + '.md',
            notes: step.notes + complaint,
          }), id + ': tagging shard ' + j)))
          const bad = rs.map((x, j) => (x && x.ok ? null : j)).filter((x) => x !== null)
          if (bad.length) log(id + ' tagging shard(s) ' + bad.join(',') + ' returned no result')
          const files = Array.from({ length: step.shards }, (_, j) => shq(step.merge + '/lit_rows_shard' + j + '.md')).join(' ')
          const mg = await sh('{ ' + RS + ' lit_table_merge --out ' + shq(step.merge + '/') + ' --shards ' + files + '\n}; rc=$?; echo "__RC0=$rc"', id + ' lit_table_merge', { phase: phaseName, timeout: 120000 })
          if (/__RC0=0/.test(mg.out)) { complaint = ''; break }
          if (round) throw new Error('lit_table_merge rejected the shards twice: ' + mg.out.slice(-600))
          complaint = ' PREVIOUS ATTEMPT REJECTED by the validating merger — rewrite your shard whole, one row per paper of your slice: ' + mg.out.replace(/__RC0=\d+/g, '').trim().slice(-700)
          log(id + ' lit_table_merge rejected the shards — one re-tag round')
        }
        r = { ok: true, written: [step.merge + '/lit_table.md'], signal: step.shards + ' shards merged' }
      } else if (step.fanout && step.fanout.length) {
        // Phase 0.5: three independent judges nominate, then a deterministic union.
        const outs = step.fanout.map((m) => step.output.replace(/\.json$/, '') + '.' + m + '.json')
        const rs = await parallel(step.fanout.map((m, j) => () => seat(step.seat,
          Object.assign({}, dyn, { output: outs[j], notes: dyn.notes + ' You are one of ' + step.fanout.length + ' independent judges answering this question; judge from the table and your own knowledge, not from any other judge.' }),
          id + ': ' + step.id + ' ' + m, MODEL[m])))
        const okOuts = rs.map((x, j) => (x && x.ok ? outs[j] : null)).filter(Boolean)
        if (!okOuts.length) throw new Error('every coverage judge failed')
        const u = await sh(PY + ' - ' + shq(step.output) + ' ' + COVERAGE_UNION_CAP + ' ' + okOuts.map(shq).join(' ') + ' <<\'PYEOF\'\n' + UNION_PY + '\nPYEOF', id + ' union nominations', { phase: phaseName, timeout: 120000 })
        const line = (/UNION [^\n]*/.exec(u.out) || [])[0]
        if (!line) throw new Error('nomination union failed: ' + u.out.slice(-300))
        log(id + ' 0.5 ' + line + ' (judges: ' + step.fanout.join(', ') + ')')
        r = { ok: true, written: [step.output], signal: line }
      } else {
        r = await seat(step.seat, dyn, id + ': ' + step.step)
      }
      st.seats.push({ kind: step.seat, step: step.step, ok: !!(r && r.ok), signal: (r && r.signal) || '', model: SEATS[step.seat].model })
      if (!r || !r.ok) throw new Error(step.seat + ' seat failed twice: ' + ((r && r.note) || 'no result'))
      repaired = step.shards ? null : { seat: step.seat, dyn: dyn, id: step.id }   // a sharded step is already guarded by the validating merger
      if (step.after) {
        if (!(await launch(step.after.key, step.after.cmd, id + ' collision', phaseName))) throw new Error('could not launch collision')
        const w = await waitFor(step.after.key, step.after.file, id + ' collision', phaseName)
        if (!w.done) throw new Error('collision retrieval produced no hits file: ' + w.out.slice(-500))
      }
      // verify the seat's outputs are readable before the next decision
      const outs = step.shards ? [] : String(step.output || '').split(' then ').map((x) => x.trim().split(' ')[0]).filter((x) => x.startsWith('/'))
      if (outs.length) {
        const v = await sh(PY + ' - ' + outs.map(shq).join(' ') + ' <<\'PYEOF\'\n' + VERIFY_PY + '\nPYEOF', id + ' verify ' + step.id, { phase: phaseName, timeout: 120000 })
        if (/__OUT_BAD/.test(v.out)) {
          const why = (/__OUT_BAD ([^\n]*)/.exec(v.out) || [])[1] || 'unreadable output'
          log(id + ' ' + step.seat + ': output unreadable (' + why + ') — one fresh retry')
          const rr = await seat(step.seat, Object.assign({}, dyn, { notes: (dyn.notes || '') + ' PREVIOUS ATTEMPT UNREADABLE: ' + why + ' — write the whole file again, valid and complete.' }), id + ': retry ' + step.step)
          if (!rr || !rr.ok) throw new Error(step.seat + ' output still unreadable: ' + why)
        }
      }
      S = await probe(rd, phaseName)
    }
    if (st.state === 'running') { st.state = 'failed'; st.note = 'exceeded ' + MAX_STEPS + ' steps' }
  } catch (err) {
    st.state = 'failed'
    st.note = String(err && err.message ? err.message : err).slice(0, 800)
    log(id + ' FAILED: ' + st.note.slice(0, 200))
  }
  return st
}

// ─────────────────────────────────────────────────────────── 9. main
log('ResearchStudio idea-spark replica — skill: ' + SKILL_DIR + ' | root: ' + ROOT + ' | K=' + K)
log('direction: ' + DIRECTION.slice(0, 200))
await shOk('mkdir -p ' + shq(JOBS) + ' ' + RUN_IDS.map((id) => shq(K > 1 ? ROOT + '/' + id : ROOT)).join(' '), 'mkdir run dirs', { phase: 'Phase 0', timeout: 60000 })
const runs = (await parallel(RUN_IDS.map((id) => () => driveRun(id)))).filter(Boolean)

// ---- scoring: the suite's own evaluation/idea_quality skill, three independent judges ----
let score = null
const done = runs.filter((r) => r.state === 'done')
if (done.length && SCORE_JUDGES.length) {
  const dir = ROOT + '/score'
  await shOk('mkdir -p ' + shq(dir), 'mkdir score', { phase: 'Score', timeout: 60000 })
  const cards = done.map((r) => ({ run: r.id, file: r.dir + '/phase4/idea.std.en.md' }))
  const pairwise = cards.length >= 2
  const rs = await parallel(SCORE_JUDGES.map((m) => () => seat('judge', {
    rd: ROOT, step: 'Score ' + cards.length + ' idea card(s) — judge ' + m, phase: 'Score',
    inputs: cards.map((c) => c.file + '  (idea ' + c.run + ': Title / Motivation / Method)'),
    output: dir + '/' + m + '.md then ' + dir + '/' + m + '.json',
    notes: 'Run the absolute track for every idea' + (pairwise ? ', then the pairwise track over the two ideas (pairwise is the trustworthy signal)' : '') +
      '. Write the report exactly in the system prompt\'s output format to the .md path. Then write a machine-readable echo of the SAME judgments to the .json path — no new judgments, just the numbers you already justified: {"ideas": [{"run": "<the idea id from INPUT>", "A": 1-5, "B": 1-5, "C": 1-5, "overall": 0-100, "verdict": "strong|borderline|weak"}]' +
      (pairwise ? ', "pairwise": {"winner": "<run id>|tie", "why": "one line"}' : '') + '}. Judge blind to source: the run id, the input order and the length or polish of a card are not evidence of quality. Routing signal: the overall score per idea.',
  }, 'score: ' + m, MODEL[m])))
  const okJudges = SCORE_JUDGES.filter((m, j) => rs[j] && rs[j].ok)
  if (okJudges.length) {
    const agg = await sh(PY + ' - ' + shq(dir + '/aggregate.json') + ' ' + okJudges.map((m) => shq(dir + '/' + m + '.json')).join(' ') + ' <<\'PYEOF\'\n' + SCORE_PY + '\nPYEOF', 'score aggregate', { phase: 'Score', timeout: 120000 })
    const line = (/SCORE [^\n]*/.exec(agg.out) || [])[0] || 'aggregate failed: ' + agg.out.slice(-200)
    log('Score ' + line)
    score = { dir: dir, judges: okJudges, aggregate: dir + '/aggregate.json', summary: line }
  }
}

return {
  root: ROOT, skill_dir: SKILL_DIR, direction: DIRECTION, k: K,
  runs: runs.map((r) => ({ id: r.id, dir: r.dir, state: r.state, steps: r.steps, seats: r.seats.length,
    cards: r.cards, validate_rc: r.validate_rc, validate_repairs: r.validate_repairs, validate_note: r.validate_note,
    note: r.note, history: r.history })),
  score: score,
}
