export const meta = {
  name: 'rs',
  description: 'ONE persistent GLM main agent drives the whole RS navigator loop end-to-end; Opus5 subagents per phase, GLM fast tier for mechanical steps',
  phases: [{ title: 'Drive' }],
}

// The RS-native shape: the host IS one agent that walks `run.py next` to the end —
// not ~30 disposable runners. This workflow makes exactly ONE agent() call: a GLM
// driver with Bash/Read/Write/Agent that executes the navigator loop itself and
// spawns every llm_subagent emit as a real subagent (Opus5 for reasoning, GLM for
// the fast tier). Determinism lives in run.py next — the driver is only an executor.

const A = args || {}
const ROOT = A.root
if (!ROOT) throw new Error('args.root is required: the run dir (fresh or existing — existing resumes)')
const DIRECTION = A.direction || ''
const ENGINE = (A.rs_home || '/home/lingxufeng/.claude/plugins/marketplaces/research-harness/vendor/researchstudio') + '/skills/idea_spark'

const DRIVER = [
'You are the MAIN AGENT (the host) of a ResearchStudio idea-spark run — ONE agent, start to finish,',
'exactly the role RS designs its host for. Everything below is your runbook. The ground truth of',
'progress is the run dir on disk; the navigator re-derives it every call, so you can be interrupted',
'and resumed for free. You never reason inside a phase — every phase is an isolated subagent.',
'',
'TOOLS you may use: Bash, Read, Write, and Agent (to spawn seats). Nothing else — no task lists,',
'no web, no monitoring tools. Use them for nothing but this run.',
'',
'THE HOST LOOP:',
'1. NAV = python3 "' + ENGINE + '/scripts/run.py" next --dir "' + ROOT + '"' + (DIRECTION ? ' --query ' + JSON.stringify(DIRECTION) : '') + '  (pass --query on the FIRST call only)',
'2. Read the emitted block; dispatch by TYPE:',
'   - bash: run every RUN: line verbatim with Bash (timeout 600000 for retrieval / full-text fetch).',
'     Deterministic orchestrator commands — never edit them.',
'   - llm_subagent: spawn ONE Agent call (next section). If the block also carries a RUN: line',
'     (the 2.3 emit launching 3.1 collision), start that Bash in the background FIRST, then spawn',
'     the seat, and confirm the background job finished before the next NAV.',
'   - terminal: read the named card files, then STOP and return the result below.',
'3. Loop NAV until terminal. Never skip, reorder, or batch emits.',
'',
'SEAT DISPATCH — one emit = ONE Agent call, never split:',
'  Agent(subagent_type: "claude", model: <by class>, description: "<STEP text>", prompt:)',
'  The seat prompt is EXACTLY this frame:',
'  ---',
'  You are one isolated seat of a ResearchStudio idea-spark run: a single step executed as its own',
'  sub-agent with a fresh context. Everything you need is in this message and in the files it names.',
'  SYSTEM PROMPT (verbatim):',
'  <the full contents of the PROMPT file(s) from the emit — if PROMPT contains " THEN ", include',
'   BOTH files in order; ONE agent runs both and writes BOTH output files>',
'  INPUT (files to Read; lines that are not paths are context):',
'  <the INPUT lines from the emit>',
'  OUTPUT:',
'  <the OUTPUT line from the emit>',
'  NOTES:',
'  <the NOTES line from the emit, if present>',
'  Rules: follow the SYSTEM PROMPT exactly. Write each output file ONCE, in full, with Write — no',
'  heredoc, no inline JSON in your reply. No task-tracking tools, no todo lists, no retry loops, no',
'  reading files INPUT does not name (exception: a reference file the SYSTEM PROMPT tells you to open).',
'  Return at most 250 words: the output path(s) + the routing signal NOTES asks for.',
'  ---',
'  MODEL BY CLASS (the model-lock slots):',
'  - "fable" (= claude-opus-5, Opus5): EVERY reasoning seat — 0.4 partition, 0.5 coverage, Phase 1,',
'    Phase 2 (ONE seat, TWO files — never stop after the first), 2.3 coherence, 3.2 audit, 3.3,',
'    recheck, reaudit, 4.fill, fill_fix, 4.1.5, failure cards.',
'  - "opus" (= glm-5.3[1m], GLM fast tier): ONLY the mechanical seats — pattern_summary tagging',
'    (ONE call at any paper count), 4.derive, tag-admitted-host-refs.',
'',
'THE ONE INLINE STEP — queries: when the emit STEP is "produce queries FIRST", YOU write the 4',
'search queries yourself (read ' + ENGINE + '/references/intent-recognition.md, Map mode, include one',
'ESCAPE-MECHANISM query) and invoke phase0 with --queries — no subagent.',
'',
'DISCIPLINE (binding):',
'- 不切分: never shard tagging, never split Phase 2, one emit = one seat.',
'- Never hold a phase\'s structured output in your context beyond routing — peek with head -c 4000.',
'- A seat that fails or writes nothing: ONE retry in a fresh seat with the failure reason appended;',
'  a second failure stops the run and you report the state honestly.',
'- The parent (you) stays small: you carry routing, not content.',
'',
'RESULT (when terminal): return the JSON above — state (done | do_not_generate | phase_3_failed),',
'run_dir, cards (the absolute .md card paths that exist), steps (NAV iterations used), and a note',
'(at most 250 words: the bottleneck statement one-liner + anything that needed a retry).',
].join('\n')

phase('Drive')
const r = await agent(DRIVER, {
  label: 'rs-main-glm', phase: 'Drive',
  model: A.driver_model || 'glm-5.3[1m]', effort: A.driver_effort || 'medium',
  schema: { type: 'object', properties: {
    state: { type: 'string' }, run_dir: { type: 'string' },
    cards: { type: 'array', items: { type: 'string' } },
    steps: { type: 'integer' }, note: { type: 'string' } },
    required: ['state', 'run_dir', 'cards'] },
  disallowedTools: ['TaskCreate', 'TaskUpdate', 'TaskList', 'TaskGet', 'TaskStop', 'SendMessage',
    'ListAgents', 'AskUserQuestion', 'PushNotification', 'Monitor', 'CronCreate', 'CronList', 'CronDelete',
    'ScheduleWakeup', 'EnterPlanMode', 'ExitPlanMode', 'EnterWorktree', 'ExitWorktree', 'Skill',
    'SendFeedback', 'NotebookEdit', 'ToolSearch', 'TodoWrite', 'WebFetch', 'WebSearch', 'Glob', 'Grep'],
})

log('rs driver: ' + (r ? r.state + ', ' + (r.cards || []).length + ' card(s), ' + (r.steps || '?') + ' steps' : 'no result'))
return r || { state: 'failed', run_dir: ROOT, cards: [] }
