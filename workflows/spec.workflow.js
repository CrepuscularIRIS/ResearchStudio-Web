// spec.workflow.js — stage C1: the scientist (Fable) writes the next B1 spec for one chain (one single-shot call).
// args (JSON string or object): { qid, spec_path, prompt } — prompt from `python3 .research/bundle.py spec --chain <name> [--retry]`
//   (the bundle is inline = isolation). Returns { qid, spec_path, spec }. The orchestrator then runs `gate.py spec <qid>`.
export const meta = {
  name: 'spec',
  description: 'One single-shot Fable call: the context bundle in, a B1 candidate spec out (also written to spec_path).',
  phases: [{ title: 'Spec', detail: 'scientist (Fable), one call, no tool loop' }],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}

const SPEC = {
  type: 'object',
  required: ['source', 'method', 'steps', 'files', 'conditions', 'held_out', 'schedule', 'network', 'kill_cmd', 'canary', 'rationale_line', 'naive_baseline', 'method_prose'],
  properties: {
    source: { type: 'string' },
    method: { type: 'string' },
    rationale_line: { type: 'string' },
    naive_baseline: { type: 'string' },
    steps: { type: 'array', minItems: 3, items: {
      type: 'object', required: ['id', 'file', 'change'],
      properties: { id: { type: 'string' }, file: { type: 'string' }, change: { type: 'string' }, new: { type: 'boolean' } },
    } },
    files: { type: 'array', items: { type: 'string' } },
    conditions: { type: 'array', items: { type: 'string' } },
    held_out: { type: 'string' },
    schedule: { type: 'object', required: ['gpu_h'], properties: { epochs_or_iters: { type: 'number' }, gpu_h: { type: 'number' } } },
    expected_gain: { type: 'number' },
    network: { type: 'string' },
    kill_cmd: { type: 'string' },
    canary: { type: 'object', required: ['what', 'expected', 'tol'], properties: { what: { type: 'string' }, expected: { type: 'number' }, tol: { type: 'number' } } },
    method_prose: { type: 'string' },
    notes: { type: 'string' },
  },
}

const spec = await agent(A.prompt + '\n\nStructured output only.', { agentType: 'scientist', label: `spec:${A.qid}`, phase: 'Spec', schema: SPEC, stallMs: 900000 })
// the returned object is authoritative: `step.py propose --finish <qid> <saved output>` writes it to spec_path when Fable's own Write did not happen
if (!spec) {
  log(`${A.qid}: scientist returned nothing (infrastructure failure, not a verdict)`)
  return { qid: A.qid, spec_path: A.spec_path, spec: null, error: 'scientist returned nothing' }
}
log(`${A.qid}: ${spec.method} · ${spec.schedule.gpu_h} GPU-h · ${spec.steps.length} steps`)
return { qid: A.qid, spec_path: A.spec_path, spec }
