export const meta = {
  name: 'rsweb',
  description: 'ONE persistent GLM agent drives the web lite track — watch/seed/send (mode=send) or patrol/capture/collect (mode=patrol) — so the main session only dispatches',
  phases: [{ title: 'Web' }],
}

// The driver pattern applied to the web track: no disposable runners, no main-session browser
// work. ONE agent() call per invocation. Independent-context separation stays where it belongs
// (the local track's seats); this driver is pure orchestration over Bash + the browser tools.

const A = args || {}
const ROOT = A.root
if (!ROOT) throw new Error('args.root is required: the ideaspark run dir')
const MODE = A.mode || 'send'          // 'send' | 'patrol'
const WEB = A.web_py || ''   // zones keep it at <zone>/.research/web/web.py; if unset the driver locates it
const N = A.n || 5

const BROWSER_CAPTURE = `() => {
  const a = [...document.querySelectorAll('[data-message-author-role="assistant"]')].pop();
  if (!a) return JSON.stringify({ state: 'no-answer-yet' });
  const canvas = document.querySelector('[id^="canvas"], .canvas-container [contenteditable], div[data-canvas]');
  const src = (canvas && canvas.textContent && canvas.textContent.length > 200) ? canvas : (a.querySelector('.markdown') || a);
  const text = src.textContent || '';
  return JSON.stringify({ state: 'have-turn', len: text.length,
    done_marker: text.includes('<<END OF IDEA REVIEW>>') || text.includes('<<END OF IDEA CARD>>'),
    streaming: document.querySelectorAll('.result-streaming').length > 0 || !!document.querySelector('[data-testid="stop-button"]'),
    has_copy: !!a.closest('[data-testid^="conversation-turn"]')?.querySelector('[data-testid="copy-turn-action-button"]'),
    from_canvas: src !== (a.querySelector('.markdown') || a), text: text });
}`

const COMMON = [
'You are the WEB-TRACK DRIVER of a two-track research run — ONE agent, this invocation only,',
'mode = ' + MODE + '. The deterministic half is a script; you are its hands and eyes. The ground truth',
'is on disk (manifests, prompts, answers); the script decides what to ask and what counts as done.',
'',
'Run dir: ' + ROOT + '.',
'Script: ' + (WEB ? ('python3 ' + WEB) : '(NOT PASSED — locate it: walk up from the run dir with find until */.research/web/web.py exists, then use that absolute path)') + ' <subcommand> --root ' + ROOT + '',
'',
'TOOLS: Bash (the script only), Read/Write (prompts and answers), and the playwright browser',
'tools (load them via ToolSearch if they are not already in your tool list). Nothing else —',
'no task lists, no web tools of your own.',
'',
'BROWSER RULES (each exists because ignoring it produced a wrong answer):',
'- chatgpt.com, PERSISTENT chats only; one conversation per window, one question per conversation.',
'- After sending, CONFIRM a user turn with your text exists (a composer that silently kept the',
'  text looks exactly like a slow answer).',
'- An answer is complete ONLY when: the end marker is present in the captured text; nothing is',
'  streaming and no stop button; the turn carries a copy button. Otherwise it is unfinished —',
'  keep waiting, never stitch.',
'- CANVAS: if the answer opened a Canvas, the canvas document IS the card — capture ITS text',
'  (the turn body around it is chatter).',
'- Read prompts before sending: you are responsible for what goes into the account.',
'- Never paste local file paths or repository contents into the web app.',
].join('\n')

const SEND = COMMON + '\n\nMODE = send — dispatch everything the run is due:\n' + [
'1. Run the script\'s watch (rc 2 = something due). For EACH due kind, exactly once:',
'   - NEW-BOTTLENECK -> seed --from-run --n <min(' + N + ', gaps printed)>',
'   - NEW-CANDIDATE  -> seed --from-candidate --n ' + N + '',
'   (seed prints the prompt files; --from-run writes web/prompts/, --from-candidate writes',
'    web/candidate_prompts/; both stamp a dispatch fingerprint so re-runs never re-ask)',
'2. Read every prompt file. Open one chatgpt.com tab per prompt (browser_tabs action new),',
'   at most five, sending one at a time.',
'3. Per prompt: browser_snapshot -> locate the composer -> browser_type the WHOLE prompt with',
'   submit true -> confirm the user turn -> browser_evaluate location.href for the conversation',
'   URL -> record it: mark --id NN --sent --url <url>  (+ --candidate for the candidate batch).',
'4. Return: which ids were sent with their URLs, which were skipped and why (rate limits,',
'   dialogs -> screenshot and STOP, never click through).',
].join('\n')

const PATROL = COMMON + '\n\nMODE = patrol — one pass over the due windows:\n' + [
'1. Run the script\'s patrol (rc 2 = windows due; it sweeps BOTH batches and prints which).',
'2. For each due id: read its conversation_url from the manifest (the candidate batch lives in',
'   web/candidate_manifest.json, the gap batch in web/manifest.json). browser_tabs list, match the',
'   tab whose URL equals it (indices shift; never select by index alone); if NO tab matches, open',
'   a new tab AT that URL and wait for it to load. Then browser_evaluate this exact capture:\n' + BROWSER_CAPTURE + '\n',
'3. If the capture is complete (marker + not streaming + copy button): Write the text VERBATIM to',
'   web/answers/<id>.md (gap batch) or web/candidate_answers/<id>.md (candidate batch), then',
'   mark --id <id> --done (+ --candidate for the candidate batch).',
'4. If it stopped early (length frozen, no marker): one re-send in a FRESH window of the same',
'   prompt, mark the new URL, and note it. If it is still streaming or growing: just record the',
'   poll length (mark --id <id> --poll <len>) and move on.',
'5. After processing: collect --root (gap batch) and collect --root --candidate (candidate',
'   batch) — they refuse to call an answer complete without its marker. Trust that refusal.',
'6. Return: per window — complete / unfinished / overdue-resent, the first heading of each new',
'   capture, and whether both batches are fully collected.',
].join('\n')

phase('Web')
const r = await agent(MODE === 'patrol' ? PATROL : SEND, {
  label: 'rsweb-' + MODE, phase: 'Web',
  model: A.driver_model || 'glm-5.3[1m]', effort: A.driver_effort || 'medium',
  schema: { type: 'object', properties: {
    mode: { type: 'string' }, sent: { type: 'array', items: { type: 'string' } },
    completed: { type: 'array', items: { type: 'string' } },
    unfinished: { type: 'array', items: { type: 'string' } },
    all_collected: { type: 'boolean' }, note: { type: 'string' } },
    required: ['mode', 'note'] },
  disallowedTools: ['TaskCreate', 'TaskUpdate', 'TaskList', 'TaskGet', 'TaskStop', 'SendMessage',
    'ListAgents', 'AskUserQuestion', 'PushNotification', 'Monitor', 'CronCreate', 'CronList', 'CronDelete',
    'ScheduleWakeup', 'EnterPlanMode', 'ExitPlanMode', 'EnterWorktree', 'ExitWorktree', 'Skill',
    'SendFeedback', 'NotebookEdit', 'TodoWrite', 'WebFetch', 'WebSearch', 'Glob', 'Grep'],
})

log('rsweb ' + MODE + ': ' + (r ? (r.sent || []).length + ' sent, ' + (r.completed || []).length + ' completed, collected=' + !!r.all_collected : 'no result'))
return r || { mode: MODE, note: 'driver returned no result' }
