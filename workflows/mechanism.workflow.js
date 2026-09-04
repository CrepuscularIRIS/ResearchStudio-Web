// mechanism.workflow.js — stage M, once per claim: A → {B} → {M} → {C} → recipe gene + precedent (Sparking.md; WORKFLOW-V4 §12.2).
//   Opus (scientist):  failure modes B grounded in our measured anomalies, and a three-level abstraction M per B.
//   K3 (explorer):     for each M, up to N source domains C with an isomorphism sentence, the mechanism's name, the disanalogy, a query.
//   Per source, three waves (v4, 2026-09-04; replaces the single Grok call that had to search, fetch and extract in one go):
//     M3 searcher (GLM):  runs the paper-search script for the source query and for the precedent query (mechanism name + A terms),
//                         obtains the text of ≤K candidate papers (local library → pdftotext, else fetch_text.py for arXiv ids).
//     M4 reader (GLM):    one paper per agent, in parallel → a gene card: procedural steps, key number, AVOID, each with a verbatim
//                         quote and its line in the .txt; a precedent card per precedent candidate.
//     M5 verifier (sol):  a different family re-reads the text for the CHOSEN card only (≤2 cards per source): every quote at its
//                         line, steps are procedures not gist, the number is the mechanism's own evidence → accept | return | drop.
//                         `return` sends the card back to the reader once with the issues.
//   `step.py mechanism --finish` then re-checks every quote/line by script (bundle.cmd_mechanism_finish) and drops sources without
//   a procedure or with a verified precedent. A null agent anywhere is infrastructure (status error), never a drop.
// args: { prompt_fable, claim, held_out, a_terms, library, search, fetch, papers_dir, max_sources_per_mechanism, max_papers_per_source,
//         precedent_max, out }  from `bundle.py M`.
export const meta = {
  name: 'mechanism',
  description: 'Opus abstracts the claim into failure modes and mechanisms; K3 diverges into source domains; per source GLM searches and reverse-engineers the papers, sol verifies the chosen gene and any precedent.',
  phases: [
    { title: 'Abstract', detail: 'scientist (Opus): B grounded in anomalies, M in three levels' },
    { title: 'Diverge', detail: 'explorer (K3): source domains per mechanism, with disanalogy' },
    { title: 'Search', detail: 'searcher (GLM): paper-search script + text for ≤K papers and ≤P precedent candidates per source' },
    { title: 'Reverse', detail: 'reader (GLM): one paper per agent → gene card with quotes and lines' },
    { title: 'Verify', detail: 'verifier (sol): the chosen card and any precedent, quotes re-read at their lines' },
  ],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const N = A.max_sources_per_mechanism || 3
const K = A.max_papers_per_source || 3
const P = A.precedent_max || 2
const ISOLATION = 'Use only what this prompt carries, the commands it names and the text files it names. Do not read .research/ beyond those files, nor plan/ or paper/. Structured output only.'
const q = (s) => String(s || '').replace(/"/g, '')

const FM = {
  type: 'object', required: ['failure_modes', 'mechanisms'],
  properties: {
    failure_modes: { type: 'array', minItems: 2, maxItems: 4, items: { type: 'object', required: ['id', 'text', 'grounded_in'],
      properties: { id: { type: 'string' }, text: { type: 'string' }, grounded_in: { type: 'array', minItems: 1, items: { type: 'string' } } } } },
    mechanisms: { type: 'array', minItems: 2, items: { type: 'object', required: ['id', 'from', 'levels', 'text'],
      properties: { id: { type: 'string' }, from: { type: 'string' }, levels: { type: 'array', minItems: 3, maxItems: 3, items: { type: 'string' } }, text: { type: 'string' } } } },
  },
}
const SOURCES = {
  type: 'object', required: ['sources'],
  properties: { sources: { type: 'array', items: { type: 'object', required: ['mechanism', 'domain', 'name', 'isomorphism', 'disanalogy', 'query'],
    properties: { mechanism: { type: 'string' }, domain: { type: 'string' }, name: { type: 'string' }, isomorphism: { type: 'string' }, disanalogy: { type: 'string' }, query: { type: 'string' }, naive_in_A: { type: 'string' }, pattern: { type: 'string' } } } } },
}
const PAPER = { type: 'object', required: ['id', 'title', 'text_path'], properties: { id: { type: 'string' }, title: { type: 'string' }, year: { type: 'number' }, text_path: { type: 'string' }, why: { type: 'string' } } }
const SEARCH = { type: 'object', required: ['papers', 'precedent_candidates'], properties: { papers: { type: 'array', items: PAPER }, precedent_candidates: { type: 'array', items: PAPER }, notes: { type: 'string' } } }
const QUOTED = { type: 'object', required: ['text', 'quote', 'line'], properties: { text: { type: 'string' }, quote: { type: 'string' }, line: { type: 'number' } } }
const GENE = {
  type: 'object', required: ['paper', 'title', 'is_procedure', 'steps', 'key_number', 'avoid', 'disanalogy_to_A', 'relation_to_claim', 'scooped'],
  properties: {
    paper: { type: 'string' }, title: { type: 'string' }, is_procedure: { type: 'boolean' },
    steps: { type: 'array', maxItems: 4, items: QUOTED },
    key_number: { type: 'object', required: ['value', 'quote', 'line'], properties: { value: { type: 'string' }, quote: { type: 'string' }, line: { type: 'number' } } },
    avoid: QUOTED, disanalogy_to_A: { type: 'string' }, code_url: { type: 'string' }, relation_to_claim: { type: 'string' }, scooped: { type: 'boolean' },
  },
}
const PRECEDENT = { type: 'object', required: ['found', 'quote', 'line', 'why'], properties: { found: { type: 'boolean' }, quote: { type: 'string' }, line: { type: 'number' }, why: { type: 'string' } } }
const VERIFY = { type: 'object', required: ['verdict', 'checks', 'issues'], properties: { verdict: { enum: ['accept', 'return', 'drop'] },
  checks: { type: 'array', items: { type: 'object', required: ['item', 'ok', 'why'], properties: { item: { type: 'string' }, ok: { type: 'boolean' }, why: { type: 'string' } } } },
  issues: { type: 'array', items: { type: 'string' } } } }

phase('Abstract')
const fm = await agent(A.prompt_fable + '\n\nStructured output only.', { agentType: 'scientist', label: 'abstract', phase: 'Abstract', schema: FM, stallMs: 900000 })
if (!fm) return { failure_modes: [], mechanisms: [], sources: [], error: 'scientist returned nothing (infrastructure failure)' }
log(`B: ${fm.failure_modes.length} failure modes · M: ${fm.mechanisms.length} mechanisms`)

phase('Diverge')
const divergePrompt = [
  '## Diverge: source domains for each mechanism (Sparking.md layer 4)',
  `Claim under test: "${A.claim}"`, '',
  '## Mechanisms (abstracted; the last level of each is domain-free)', JSON.stringify(fm.mechanisms, null, 1), '',
  `## Task\nFor EACH mechanism list up to ${N} source domains C from at least two different fields (statistics, control, signal processing, economics, biology, optimisation, ...),`,
  'where a mature mechanism solves a problem isomorphic to M. For each: `isomorphism` = one sentence why M_A ≅ M_C (structure, not vocabulary);',
  '`name` = the mechanism as its own field names it; `disanalogy` = the assumption of C that does NOT hold in A (what an adaptation must change);',
  '`query` = a 6-12 word literature query in C\'s own vocabulary (no RGB/depth/segmentation words). Do not propose methods; do not cite papers from memory.',
  'Divergence vocabulary (use as lenses, not as a checklist): assumption_audit_and_pivot · architectural_operator_substitution · reframe_as_solvable_object · unify_into_shared_representation · structural_prior_encoding · algebraic_equivalence · heterogeneous_decomposition · decompose_and_delegate · relax_discrete_to_continuous · adapt_via_conditioning · characterize_limit_then_surpass · controlled_diagnostic_design.',
  'Structure, not vocabulary: a C that only shares words with M (ARFT B.5) is not a source. For each C also say in one clause what the NAIVE version of the mechanism in A would be, so a later spec must beat it.',
  'Tag each C with the one lens (`pattern`) it mainly uses, and give at most two Cs per pattern per mechanism — six variants of one move are not six sources. Mature, textbook mechanisms (pre-2015, other fields) are wanted; the query must be answerable in C\'s own literature.',
  ISOLATION,
].join('\n')
const div = await agent(divergePrompt + '\n\nStructured output only.', { agentType: 'explorer', label: 'diverge', phase: 'Diverge', schema: SOURCES, stallMs: 900000 })
if (!div) return { ...fm, sources: [], error: 'explorer returned nothing (infrastructure failure)' }
const seen = new Set()
const candidates = div.sources.filter((s) => { const k = (s.domain + '|' + s.name).toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true })
log(`C: ${candidates.length} source domains (${div.sources.length - candidates.length} duplicates dropped)`)

// ── per-source waves ─────────────────────────────────────────────────────────
const head = (s) => [`Claim under test (A): "${A.claim}"`, `Mechanism: ${s.mechanism}`, `Source domain C: ${s.domain} — ${s.name}`, `Isomorphism: ${s.isomorphism}`, `Disanalogy: ${s.disanalogy}`]

const searchPrompt = (s) => [
  'LANE: searcher', 'MODE: SEARCH', '## Search: candidate papers for one source domain, with their text', ...head(s), '',
  `1. Run: python3 ${A.search} --query "${q(s.query)}" --start-year 1950 --end-year 2026 --max-papers 12 --json`,
  `   Choose up to ${K} papers that give the mechanism as a PROCEDURE (equations / algorithm / steps): prefer is_survey=false, high relevance_score, the original or a textbook-grade treatment over follow-ups.`,
  `2. Text for each chosen paper: local library first — ls ${A.library} | grep -i for the id or title words; pdftotext -layout <pdf> ${A.papers_dir}/<id>.txt —`,
  `   else, for an arXiv id only, python3 ${A.fetch} --one <arxiv-id> (writes ${A.papers_dir}/<id>.txt and prints the row). A paper with no obtainable text gets text_path "" (it will be skipped).`,
  `3. Precedent search: python3 ${A.search} --query "${q(s.name)} ${q(A.a_terms.join(' '))}" --start-year 2012 --end-year 2026 --max-papers 8 --json`,
  `   Keep up to ${P} precedent_candidates that could ALREADY apply this mechanism to A (${q(A.a_terms.join(', '))}); obtain their text the same way. None is a valid answer.`,
  'Return the JSON only. `why` = one clause on why the paper is a procedure source. Never rank by taste; never read the texts yourself.',
  ISOLATION,
].join('\n')

const readerPrompt = (s, p, issues) => [
  'LANE: reader', 'MODE: REVERSE', '## Reverse-engineer one paper into a gene card', ...head(s), '',
  `Paper: ${p.id} — ${p.title}`, `Text: ${p.text_path}   (Grep the mechanism words first, then Read in windows of ≤300 lines; read nothing else)`, '',
  'Extract: is_procedure (does the paper state the mechanism as steps/equations one could implement?); ≤4 steps — each `text` is what they actually DO (object, operation, parameters), each with a verbatim `quote` (≥8 words) and the 1-based `line` of that quote in the .txt;',
  'key_number = the single number that proves the mechanism works in C, with its verbatim quote and line (the mechanism\'s own evidence, not a baseline\'s); avoid = their own stated limitation or failure, quoted with line;',
  'disanalogy_to_A = which assumption behind the steps fails in A; code_url if stated; relation_to_claim = one line; scooped = true only if the paper tests the claim itself.',
  'A quote is copied character for character from the .txt; the script checks every line. No procedure in the paper → is_procedure=false, steps=[].',
  ...(issues && issues.length ? ['', '## The verifier returned this card; fix exactly these issues, change nothing else:', ...issues.map((x) => `- ${x}`)] : []),
  ISOLATION,
].join('\n')

const precedentPrompt = (s, p) => [
  'LANE: reader', 'MODE: PRECEDENT', '## Does this paper already apply the mechanism to A?', ...head(s), '',
  `Paper: ${p.id} — ${p.title}`, `Text: ${p.text_path}   (Grep for the mechanism words and the A terms: ${q(A.a_terms.join(', '))}; Read in windows of ≤300 lines)`, '',
  'found = true ONLY if this paper applies THIS mechanism (the same move, not the same words) to A; then give a verbatim quote of ≥8 words that shows it and its line. Sharing vocabulary is not precedent (ARFT B.5). Otherwise found=false with quote "" and line 0.',
  ISOLATION,
].join('\n')

const verifyPrompt = (s, g) => [
  'LANE: verifier', 'MODE: VERIFY', '## Verify one gene card against the paper text (a different family read it)', ...head(s), '',
  `Text: ${g.text_path}   (Grep each quote; Read ±10 lines around each cited line; read nothing else)`, '', '## Card', JSON.stringify(g, null, 1), '',
  'Checks, one entry each in `checks` (item = "step 1", "key_number", "avoid", "procedure"): (1) every quote appears verbatim within ±3 lines of its line; (2) each step is a procedure — an operation on a defined object with its parameters — not a gist or a name;',
  '(3) key_number is the mechanism\'s own evidence (not a baseline, not another method); (4) avoid is a limitation the authors state. verdict: accept = all ok; return = fixable by re-reading (a wrong line, a vague step) — list the issues; drop = the paper does not give this mechanism as a procedure.',
  ISOLATION,
].join('\n')

const verifyPrecedentPrompt = (s, p, pr) => [
  'LANE: verifier', 'MODE: VERIFY', '## Verify a precedent claim', ...head(s), '',
  `Paper: ${p.id} — ${p.title}`, `Text: ${p.text_path}   (Grep the quote; Read ±10 lines around line ${pr.line})`, '', '## Claimed precedent', JSON.stringify(pr, null, 1), '',
  'accept = the quote is verbatim at its line AND the passage shows this mechanism (the same move) applied to A; otherwise drop (a wrong line or a merely similar vocabulary). `return` is not used here.',
  ISOLATION,
].join('\n')

const geneHead = (g) => ({ paper: g.paper, title: g.title, is_procedure: g.is_procedure, n_steps: (g.steps || []).length, key_number: (g.key_number || {}).value, code_url: g.code_url || '', scooped: !!g.scooped })
const EMPTY_RECIPE = { paper: '', title: '', steps: [], key_number: { value: '', quote: '', line: 0 }, text_path: '', avoid: '' }

async function processSource(s, idx) {
  const tag = `${String(s.domain).slice(0, 14)}#${idx + 1}`
  const searched = await agent(searchPrompt(s), { agentType: 'searcher', label: `search:${tag}`, phase: 'Search', schema: SEARCH, stallMs: 900000 })
  if (!searched) return { ...s, recipe: null, precedent: null, error: 'searcher returned nothing (infrastructure; status error, not dropped)' }
  const papers = (searched.papers || []).filter((p) => p.text_path).slice(0, K)
  const precs = (searched.precedent_candidates || []).filter((p) => p.text_path).slice(0, P)
  log(`${tag}: ${papers.length} papers with text · ${precs.length} precedent candidates`)
  const genes = (await parallel(papers.map((p) => () =>
    agent(readerPrompt(s, p), { agentType: 'reader', label: `reverse:${tag}:${String(p.id).slice(0, 12)}`, phase: 'Reverse', schema: GENE, stallMs: 900000 })
      .then((g) => g ? { ...g, paper: g.paper || p.id, text_path: p.text_path, _p: p } : null)))).filter(Boolean)
  const ordered = genes.slice().sort((a, b) => (b.is_procedure - a.is_procedure) || ((b.steps || []).length - (a.steps || []).length))
  let chosen = null
  const verify = []
  for (let g of ordered.slice(0, 2)) {                       // verify the best card, fall back once
    let v = await agent(verifyPrompt(s, g), { agentType: 'verifier', label: `verify:${tag}:${String(g.paper).slice(0, 12)}`, phase: 'Verify', schema: VERIFY, stallMs: 600000 })
    if (v && v.verdict === 'return') {
      const g2 = await agent(readerPrompt(s, g._p, v.issues), { agentType: 'reader', label: `reread:${tag}:${String(g.paper).slice(0, 12)}`, phase: 'Reverse', schema: GENE, stallMs: 900000 })
      if (g2) { g = { ...g2, paper: g2.paper || g.paper, text_path: g.text_path, _p: g._p }; v = await agent(verifyPrompt(s, g), { agentType: 'verifier', label: `reverify:${tag}:${String(g.paper).slice(0, 12)}`, phase: 'Verify', schema: VERIFY, stallMs: 600000 }) }
    }
    verify.push({ paper: g.paper, verdict: v ? v.verdict : 'null', issues: v ? v.issues : ['verifier returned nothing'] })
    if (v && v.verdict === 'accept') { chosen = g; break }
  }
  let precedent = { found: false }
  for (const pc of precs) {
    const pr = await agent(precedentPrompt(s, pc), { agentType: 'reader', label: `precedent:${tag}:${String(pc.id).slice(0, 12)}`, phase: 'Reverse', schema: PRECEDENT, stallMs: 900000 })
    if (!pr || !pr.found) continue
    const v = await agent(verifyPrecedentPrompt(s, pc, pr), { agentType: 'verifier', label: `verify-prec:${tag}:${String(pc.id).slice(0, 12)}`, phase: 'Verify', schema: VERIFY, stallMs: 600000 })
    if (v && v.verdict === 'accept') { precedent = { found: true, paper: pc.id, quote: pr.quote, line: pr.line, text_path: pc.text_path, why: pr.why }; break }
    precedent = { found: false, rejected: (precedent.rejected || []).concat([{ paper: pc.id, why: v ? v.issues : ['verifier returned nothing'] }]) }
  }
  const recipe = chosen
    ? { paper: chosen.paper, title: chosen.title, steps: chosen.steps, key_number: chosen.key_number, text_path: chosen.text_path, avoid: (chosen.avoid || {}).text || '', avoid_quote: chosen.avoid, code_url: chosen.code_url || '', disanalogy_to_A: chosen.disanalogy_to_A, relation_to_claim: chosen.relation_to_claim, scooped: !!chosen.scooped }
    : { ...EMPTY_RECIPE, text_path: '', note: papers.length ? 'no gene card passed verification' : 'no paper text obtained' }
  return { ...s, recipe, precedent, genes: genes.map(geneHead), verify, search: { papers: (searched.papers || []).length, with_text: papers.length, precedent_candidates: precs.length } }
}

phase('Search')
const sources = (await parallel(candidates.map((s, i) => () => processSource(s, i)))).filter(Boolean)
const withRecipe = sources.filter((s) => s.recipe && s.recipe.steps && s.recipe.steps.length).length
const withPrecedent = sources.filter((s) => s.precedent && s.precedent.found).length
const infra = sources.filter((s) => s.error).length
log(`recipes: ${withRecipe}/${sources.length} verified procedures · ${withPrecedent} with verified precedent in A · ${infra} infra failures`)
return { failure_modes: fm.failure_modes, mechanisms: fm.mechanisms, sources,
  stats: { failure_modes: fm.failure_modes.length, mechanisms: fm.mechanisms.length, candidates: candidates.length, with_recipe: withRecipe, with_precedent: withPrecedent, infra_failures: infra } }
