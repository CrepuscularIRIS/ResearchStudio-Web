// mechanism.workflow.js — stage M, once per claim: A → {B} → {M} → {C} → recipe + precedent (Sparking.md; WORKFLOW.md §1).
//   Fable (scientist): failure modes B grounded in our measured anomalies, and a three-level abstraction M per B.
//   K3 (explorer):     for each M, up to N source domains C with an isomorphism sentence, the mechanism's name, the disanalogy, a search query.
//   Grok (researcher): for each (M, C): the recipe as a procedure-level gene (steps + key number with quote and line), and the precedent
//                      question — has this mechanism already been applied to A? (searched with the A terms).
// args: { prompt_fable, claim, held_out, a_terms, library, search, max_sources_per_mechanism, out }  from `bundle.py M`.
// Returns { failure_modes, mechanisms, sources[], stats }. The orchestrator then runs `step.py mechanism --finish <saved json>`,
// which verifies every quote/line by script and drops sources without a recipe or with a precedent.
export const meta = {
  name: 'mechanism',
  description: 'Fable abstracts the claim into failure modes and mechanisms; K3 diverges into source domains; Grok retrieves each recipe and checks for precedent.',
  phases: [
    { title: 'Abstract', detail: 'scientist (Fable): B grounded in anomalies, M in three levels' },
    { title: 'Diverge', detail: 'explorer (K3): source domains per mechanism, with disanalogy' },
    { title: 'Retrieve', detail: 'researcher (Grok): one recipe gene + precedent check per source' },
  ],
}

const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const N = A.max_sources_per_mechanism || 3
const ISOLATION = 'Use only what this prompt carries and the one command it names. Do not read .research/, plan/, or paper/. Structured output only.'

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
    properties: { mechanism: { type: 'string' }, domain: { type: 'string' }, name: { type: 'string' }, isomorphism: { type: 'string' }, disanalogy: { type: 'string' }, query: { type: 'string' }, naive_in_A: { type: 'string' } } } } },
}
const RECIPE = {
  type: 'object', required: ['recipe', 'precedent'],
  properties: {
    recipe: { type: 'object', required: ['paper', 'title', 'steps', 'key_number', 'text_path', 'avoid'],
      properties: { paper: { type: 'string' }, title: { type: 'string' }, steps: { type: 'array', maxItems: 4, items: { type: 'string' } },
        key_number: { type: 'object', required: ['value', 'quote', 'line'], properties: { value: { type: 'string' }, quote: { type: 'string' }, line: { type: 'number' } } },
        text_path: { type: 'string' }, avoid: { type: 'string' } } },
    precedent: { type: 'object', required: ['found'], properties: { found: { type: 'boolean' }, paper: { type: 'string' }, quote: { type: 'string' } } },
  },
}

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
  ISOLATION,
].join('\n')
const div = await agent(divergePrompt + '\n\nStructured output only.', { agentType: 'explorer', label: 'diverge', phase: 'Diverge', schema: SOURCES, stallMs: 900000 })
if (!div) return { ...fm, sources: [], error: 'explorer returned nothing (infrastructure failure)' }
const seen = new Set()
const candidates = div.sources.filter((s) => { const k = (s.domain + '|' + s.name).toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true })
log(`C: ${candidates.length} source domains (${div.sources.length - candidates.length} duplicates dropped)`)

phase('Retrieve')
const retrievePrompt = (s) => [
  '## Retrieve: one recipe gene + precedent for one source domain',
  `Claim under test (A): "${A.claim}"`, `Mechanism: ${s.mechanism}`, `Source domain C: ${s.domain} — ${s.name}`, `Isomorphism: ${s.isomorphism}`, '',
  `1. Run: python3 ${A.search} --query "${String(s.query).replace(/"/g, '')}" --start-year 2015 --end-year 2026 --max-papers 6 --json`,
  '   Pick the ONE paper that gives the mechanism as a PROCEDURE (equations/steps), not a survey. Text: look in the local library first',
  `   (ls ${A.library} | grep -i for the id or title words; pdftotext -layout <pdf> .research/lit/papers/<id>.txt), else python3 .research/fetch_text.py --one <arxiv-id>.`,
  '   If no text can be obtained, return recipe.steps = [] and text_path = "".',
  '2. From the text extract the recipe gene: ≤4 PROCEDURAL steps (what they actually do), one AVOID (their own stated failure or limitation),',
  '   the single key number that proves the mechanism with its verbatim quote and the LINE NUMBER in the .txt.',
  `3. Precedent: run the search once more with "${String(s.name).replace(/"/g, '')} ${A.a_terms.join(' ')}" (--max-papers 6 --json). precedent.found = true ONLY if a`,
  '   paper already applies this mechanism to A (RGB-D / wrong-depth / multimodal-corruption segmentation); then give the paper id and a quote. Otherwise found = false.',
  ISOLATION,
].join('\n')
const sources = (await parallel(candidates.map((s) => () =>
  agent(retrievePrompt(s), { agentType: 'researcher', label: `recipe:${String(s.domain).slice(0, 18)}`, phase: 'Retrieve', schema: RECIPE, stallMs: 600000 })
    .then((r) => r ? { ...s, recipe: r.recipe, precedent: r.precedent } : { ...s, recipe: null, precedent: null, error: 'researcher returned nothing' })
))).filter(Boolean)
const withRecipe = sources.filter((s) => s.recipe && s.recipe.steps && s.recipe.steps.length).length
const withPrecedent = sources.filter((s) => s.precedent && s.precedent.found).length
log(`recipes: ${withRecipe}/${sources.length} with procedures · ${withPrecedent} with precedent in A · ${sources.filter((s) => s.error).length} infra failures`)
return { failure_modes: fm.failure_modes, mechanisms: fm.mechanisms, sources,
  stats: { failure_modes: fm.failure_modes.length, mechanisms: fm.mechanisms.length, candidates: candidates.length, with_recipe: withRecipe, with_precedent: withPrecedent, infra_failures: sources.filter((s) => s.error).length } }
