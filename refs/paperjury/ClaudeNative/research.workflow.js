/**
 * research — V8 v2: Speculative DeepResearch × RS transformation priors
 * (docs/PIPELINE-V8-RESEARCH-V2.md — replaces the v1 12-phase gate chain).
 *
 * RS is a SEARCH PRIOR, not a pipeline. Expensive models never wait on each other:
 * t=0 fires Opus+K3 reframes ∥ GLM foundation searches simultaneously; Sol joins AFTER
 * evidence to formalize routes (asymmetric priors, not same-task×3). DR runs as ROUTE
 * COMPETITION: every query carries {route_id, if_yes, if_no}; a route changes state only
 * with evidence_ids or a Sol formal kill — never by opinion. Kills are evidence (EXACT
 * collision) or formal (Sol's six hard-kill classes) only; K3 is prosecutor, not judge.
 * 15 parent cards / 31 sub-pattern cards are READ VERBATIM from the RS skill files by the
 * seats that need them (bounded reads of named files only); free tool use is for search
 * seats alone. Numbers live in documents; every seat absence is {error} (infra), never a
 * verdict.
 * Run: Workflow({ name: "research", args: { frozen, substrate?, round?, strategy?,
 *   local_digest?, redo?, prev_queries?, search_cmd?, fetch_cmd?, lit_count?, budget? } })
 */

export const meta = {
  name: 'research',
  description: "Speculative DeepResearch with RS transformation priors: Opus+K3 reframes and GLM foundation searches fire at t=0; Sol formalizes live routes; DR proceeds as route competition ({query, route_id, if_yes, if_no}); GLM sketch swarm → portfolio prune → top-4 full Claims ∥ collision; K3 prosecutes (with the corpus's Reject-lesson negative knowledge) and Sol hard-kills on formal grounds; JS composes verdicts deterministically — no cross-model scores.",
  whenToUse: "One round of V8 idea research against the FROZEN anchor: produce ONE Claim (statement + strategy + contract rows + premises + naive + falsifier) ready for the experiment ladder.",
  phases: [
    { title: "Reframe", detail: "t=0: Opus deepest reframe + K3 adversarial reframe (both read the 15-pattern overview) ∥ GLM baseline/closest/contrary foundation searches" },
    { title: "Routes", detail: "Sol formalizes live routes (formal object / naive / kill observation); GLM planner emits decision-bound queries; waves update route states until live≤2 | budget | zero change" },
    { title: "Digest", detail: "GLM bottleneck digest (failure-not-cure contract) + negative-knowledge slice from the surviving parent cards; one call matches the 31-card index (lazy: survivors only)" },
    { title: "Factory", detail: "GLM sketch swarm (smallest-runnable-mechanism bias) → mechanical portfolio prune → top-4 full Claims ∥ collision (signature/alias/github)" },
    { title: "Verdict", detail: "K3 prosecutes (Reject lessons + anti-patterns injected) ∥ Sol formal review (PASS/FORMAL_RISK/HARD_KILL); JS deterministic composition; Opus tie-break only on a real tie" },
  ],
}

const MODEL = { opus: 'claude-opus-5', sol: 'gpt-5.6-sol', k3: 'k3-256k', glm: 'glm-5.3[1m]' }
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
A.search_cmd = A.search_cmd || "python3 /home/lingxufeng/cli/research-harness/skills/paper-search/scripts/search_papers.py"
A.fetch_cmd = A.fetch_cmd || "python3 /home/lingxufeng/workspace/.research/tools/fetch_text.py"
const BUD = Object.assign({ waves: 3, perWave: 4, sketches: 10, keep: 4 }, A.budget || {})
const RSREF = "/home/lingxufeng/autoresearch/ResearchStudio/ResearchStudio-Idea/skills/idea_spark/references"

// ─── RS verbatim prompt constants ───
const FOUR_CHAIN =
  "TRIGGER TEST: a pattern matches ONLY if you can state the four-link chain — " +
  "failure → pattern operation → method artifact → keep-rule metric. Example: the real difficulty " +
  "is X → recast X as the mature object Y → apply Y's machinery Z → produce runnable artifact A → " +
  "A directly moves the primary metric. If any link is vague, it is NOT a match."
const BOTTLENECK_DISCIPLINE =
  "BOTTLENECK = FAILURE, not the absence of a cure: state what breaks, under what condition, and why " +
  "the current machinery cannot produce the needed quantity. Litmus: if one named mechanism would " +
  "'close' it by definition, it is solution-shaped — rewrite so several distinct cures could each " +
  "address it. Cite >=2 paper_ids from the pool inline; never a category label."
const NAIVE_CONTRACT =
  "NAIVE FIRST: state, in one concrete runnable-in-principle sentence, the most naive/obvious version; " +
  "then exactly ONE honest branch — (i) the naive version silently relies on a FALSE premise here " +
  "(name it; the confrontation IS the contribution) / (ii) the naive version works and the field knows " +
  "it (an incremental signal) / (iii) the naive version works but the field believes it does not " +
  "(name the evidence of disbelief). If candidate ≈ naive baseline → kill; do not write a story around it."
const FALSIFY_MIN =
  "FALSIFIER minimum: (a) the minimal experiment as a procedure; (b) the downstream outcome metric AND " +
  "its direction; (c) ONE named load-bearing variable; (d) a negative control whose predicted effect is " +
  "the OUTCOME metric returning to baseline — 'intervene on X → X becomes 0' is tautological and void."
const RESIDUE_RULE =
  "Residue ('what this paper did NOT do') must come from the method/limitations sections, never the " +
  "abstract — abstracts systematically underestimate residue."
const ALIAS_RULE =
  "alias_terms = how ANOTHER research community would name this same mechanism (parametric knowledge, " +
  "never this domain's own vocabulary); a renamed ancestor is lethal regardless of age."
const SKETCH_BIAS =
  "Bias: do NOT design a grand research program. Find the SMALLEST RUNNABLE MECHANISM that satisfies " +
  "the FROZEN keep rule — one operator substitution, one conditioning variable, one decomposition, one " +
  "estimator, one representation change, one signal — not module-A + module-B + new loss + new dataset " +
  "+ theory + system."

// ─── infra: seat counting, ledger, pool ───
let agentCalls = 0
const byModel = {}
const seat = async (prompt, opts) => {
  agentCalls++; byModel[opts.model] = (byModel[opts.model] || 0) + 1
  return agent(prompt, opts)
}
const STOPW = new Set(["the", "and", "for", "with", "from", "that", "this", "using", "into", "over", "based", "via"])
const normQ = q => String(q).toLowerCase().replace(/[^a-z0-9 ]/g, " ").split(/\s+/)
  .filter(w => w.length > 2 && !STOPW.has(w)).sort().join(" ")
const ledger = new Map()
const ledgerTake = (q, routeId) => {
  const k = normQ(q)
  if (!k || ledger.has(k)) return false
  ledger.set(k, { q: String(q), route: routeId })
  return true
}
const pool = []
const poolLine = () => pool.map(c => "- " + c.id + " [" + (c.on_topic ? "on" : "off") + "] " + c.title + " — " + c.summary).join("\n")

if (!A.frozen) return { error: "No FROZEN block in args — refusing to run rootless." }
const LOCAL = A.local_digest || ""
const PRIOR_ROUTE = A.strategy
  ? { id: "R0", pattern: "(owner-supplied strategy prior)", hypothesis: A.strategy,
      decisive_question: "Is this strategy free (not scooped), grounded (mechanism premise holds), and superior to its naive version?",
      status: "live", evidence_ids: [], owner_prior: true }
  : null

// ═══ PHASE 1: Reframe — t=0, no barriers ═══
phase("Reframe")
const REFRAME_SCHEMA = {
  type: "object",
  required: ["reframes"],
  properties: {
    reframes: {
      type: "array", maxItems: 2,
      items: {
        type: "object",
        required: ["pattern", "trigger", "reframe", "bottleneck_hypothesis", "smallest_artifact", "queries"],
        properties: {
          pattern: { type: "string" },
          trigger: { type: "string", description: "the four-link chain, stated explicitly" },
          reframe: { type: "string", description: "one-sentence worldview" },
          bottleneck_hypothesis: { type: "string" },
          smallest_artifact: { type: "string" },
          queries: { type: "array", maxItems: 2, items: { type: "string" } },
        },
      },
    },
  },
}
const reframePrompt = (role) =>
  role.header + "\n\n## FROZEN anchor\n" + A.frozen + "\n\n" +
  (LOCAL ? "## Local situation (digest — the artifact must be runnable on THIS substrate)\n" + LOCAL + "\n\n" : "") +
  (A.redo ? "## Negative anchors from the dead previous round (do NOT re-walk these)\n" + JSON.stringify(A.redo) + "\n\n" : "") +
  "## Task\nRead EXACTLY this one file (no other files): " + RSREF + "/ideation-patterns/overview.md — " +
  "it holds the 15 patterns with Definition / Operational signature / When to apply.\n" +
  "Then emit up to 2 reframings of this anchor's failure, each as ONE pattern-grounded worldview.\n" +
  FOUR_CHAIN + "\nEach carries 2 discriminating search queries (queries that, answered yes vs no, " +
  "change the worldview's standing). " + role.extra + "\n\nStructured output only."
const FOUND_ANGLES = [
  { key: "baseline", text: "Angle: the FROZEN baselines and their published numbers." },
  { key: "closest", text: "Angle: the closest recent prior art (recent window; ALSO phrase one query in SOLUTION vocabulary — the vocabulary a paper that already fixed this would title itself with)." },
  { key: "contrary", text: "Angle: failure/negative/limitation evidence (wide multi-year window)." },
]
const FOUND_SCHEMA = {
  type: "object",
  required: ["cards"],
  properties: {
    cards: {
      type: "array", maxItems: 4,
      items: {
        type: "object",
        required: ["id", "title", "text_path", "on_topic", "summary", "mechanism_class", "residue", "angle"],
        properties: {
          id: { type: "string" }, title: { type: "string" }, text_path: { type: "string" },
          on_topic: { type: "boolean" }, summary: { type: "string" }, mechanism_class: { type: "string" },
          angle: { enum: ["baseline", "closest", "contrary"] },
          residue: {
            type: "object", required: ["what_not_done", "abstract_level"],
            properties: { what_not_done: { type: "string" }, abstract_level: { type: "boolean" } },
          },
        },
      },
    },
  },
}
const foundPrompt = (ang) =>
  "## Foundation search (" + ang.key + ", t=0 — Bash only, no web tools)\n## FROZEN anchor\n" + A.frozen +
  "\n\n" + ang.text + "\nLocal corpus FIRST (`grep -ril -e '<keywords>' .research/lit/papers/*.txt | head -20`, " +
  (A.lit_count || "many") + " texts), then `" + A.search_cmd + " --query \"<q>\" --start-year <YYYY> --end-year 2026 --max-papers 6 --json`, " +
  "then `" + A.fetch_cmd + " --one <arxiv-id>` for chosen hits without local text; snowball wide windows " +
  "(`python3 /home/lingxufeng/workspace/.research/tools/snowball.py <id> --title \"<t>\" --json --max 8`).\n" +
  "For every paper you settle on, return a card. " + RESIDUE_RULE + "\n\nStructured output only."
const [opusR, k3R, ...foundSeats] = await parallel([
  () => seat(reframePrompt({ header: "SEAT (Opus — conceptual prior, taste): propose the DEEPEST useful reframing.",
    extra: "Do NOT inflate a small problem into an architecture; the artifact must run on the local substrate." }),
    { label: "reframe:opus", phase: "Reframe", schema: REFRAME_SCHEMA, model: MODEL.opus }),
  () => seat(reframePrompt({ header: "SEAT (K3 — adversarial prior, prosecutor): attack the anchor's unquestioned assumptions.",
    extra: "Prefer reframes of the form: the field silently assumes A, the FROZEN Measured anomaly shows A fails in regime R → violate/relax A and rebuild the method. You raise fatal possibilities; literature and formal review will adjudicate — you are NOT the judge." }),
    { label: "reframe:k3", phase: "Reframe", schema: REFRAME_SCHEMA, model: MODEL.k3 }),
  ...FOUND_ANGLES.map(ang => () =>
    seat(foundPrompt(ang), { label: "found:" + ang.key, phase: "Reframe", schema: FOUND_SCHEMA, model: MODEL.glm })),
])
const found = { cards: foundSeats.flatMap(f => (f && f.cards) || []) }
const foundAbsent = FOUND_ANGLES.filter((ang, i) => !foundSeats[i])
if (!opusR || !k3R) return { error: "reframe seat absent — infrastructure, not a verdict; retry." }
if (foundAbsent.length === FOUND_ANGLES.length) return { error: "all foundation seats absent — infrastructure, not a verdict; retry." }
if (foundAbsent.length) log("foundation seats absent (continuing with the rest): " + foundAbsent.map(a => a.key).join(", "))
for (const c of (found.cards || [])) pool.push(c)
let routes = []
const addRoutes = (r, src) => (r.reframes || []).forEach((x) => routes.push({
  id: "R" + (routes.length + 1), pattern: x.pattern, hypothesis: x.reframe,
  decisive_question: x.bottleneck_hypothesis, status: "live", evidence_ids: [],
  trigger: x.trigger, artifact: x.smallest_artifact, queries: x.queries || [], src,
}))
addRoutes(opusR, "opus"); addRoutes(k3R, "k3")
if (PRIOR_ROUTE) routes.unshift(PRIOR_ROUTE)
log("reframes: " + routes.length + " routes; foundation pool " + pool.length)

// ═══ PHASE 2: Routes — Sol formalization → decision-bound query waves ═══
phase("Routes")
const FORMAL_SCHEMA = {
  type: "object",
  required: ["routes"],
  properties: {
    routes: {
      type: "array",
      items: {
        type: "object",
        required: ["route_id", "formal_object", "naive_solution", "transformation_changes", "kill_observation", "runnable"],
        properties: {
          route_id: { type: "string" },
          formal_object: { type: "string" },
          naive_solution: { type: "string" },
          transformation_changes: { type: "string" },
          kill_observation: { type: "string" },
          runnable: { type: "boolean" },
          naive_suffices: { type: "boolean" },
        },
      },
    },
  },
}
const formal = await seat(
  "SEAT (sol — formal feasibility prior; no tools, everything is in this prompt)\n\n## Routes\n" +
  JSON.stringify(routes.map(r => ({ id: r.id, hypothesis: r.hypothesis, artifact: r.artifact, trigger: r.trigger }))) +
  "\n## Foundation evidence\n" + poolLine() + "\n\nFor EACH live route: (1) its formal object; (2) the most NAIVE runnable " +
  "solution and which honest branch it falls under — " + NAIVE_CONTRACT + " (3) what the transformation actually changes; " +
  "(4) the single observation that would KILL the route; (5) runnable as a method on this substrate? " +
  "runnable=false or naive_suffices=true is a formal kill — say which in transformation_changes.\n\nStructured output only.",
  { label: "routes:sol", phase: "Routes", schema: FORMAL_SCHEMA, model: MODEL.sol })
if (!formal) return { error: "Sol formal seat absent — infrastructure, not a verdict; retry." }
for (const f of (formal.routes || [])) {
  const r = routes.find(x => x.id === f.route_id)
  if (r && (f.runnable === false || f.naive_suffices === true)) {
    r.status = "killed"
    r.formal_kill = f.runnable === false ? "not runnable as method" : "naive suffices (branch ii)"
    r.kill_observation = f.kill_observation
  } else if (r) { r.formal = f }
}
const PLANNER_SCHEMA = {
  type: "object",
  required: ["queries", "routes"],
  properties: {
    queries: {
      type: "array", maxItems: BUD.perWave,
      items: {
        type: "object", required: ["query", "route_id", "if_yes", "if_no"],
        properties: { query: { type: "string" }, route_id: { type: "string" },
                      if_yes: { type: "string" }, if_no: { type: "string" } },
      },
    },
    routes: {
      type: "array",
      items: {
        type: "object", required: ["id", "status"],
        properties: {
          id: { type: "string" }, status: { enum: ["live", "supported", "weakened", "killed"] },
          evidence_ids: { type: "array", items: { type: "string" } }, reason: { type: "string" },
        },
      },
    },
  },
}
let waves = 0
while (waves < BUD.waves) {
  const live = routes.filter(r => r.status === "live" || r.status === "supported")
  if (live.length <= 2 && waves > 0) break
  const plan = await seat(
    "## Route planner (no tools)\n## Routes (current)\n" +
    JSON.stringify(routes.map(r => ({ id: r.id, status: r.status, hypothesis: r.hypothesis, decisive: r.decisive_question, evid: r.evidence_ids }))) +
    "\n## Evidence pool\n" + poolLine() + "\n\nEmit the next wave: up to " + BUD.perWave + " queries. A query exists ONLY to " +
    "change a live route's standing — each carries {route_id, if_yes, if_no}. Do not re-ask anything the pool already " +
    "answers. ALSO return updated route statuses: a route may move to supported/weakened/killed ONLY by citing " +
    "evidence_ids from the pool or a formal reason already on record — status changes without evidence_ids are rejected.\n\nStructured output only.",
    { label: "plan:" + (waves + 1), phase: "Routes", schema: PLANNER_SCHEMA, model: MODEL.glm })
  if (!plan) return { error: "planner seat absent — infrastructure, not a verdict; retry." }
  const routeAlive = id => { const r = routes.find(x => x.id === id); return r && r.status !== "killed" }
  const qs = (plan.queries || []).filter(q => routeAlive(q.route_id) && ledgerTake(q.query, q.route_id))
  if (!qs.length) break
  const wave = await parallel(qs.map(q => () =>
    seat("## Route query (Bash only; local corpus first)\n## Query\n" + q.query +
      "\n## Why (route " + q.route_id + "; if_yes: " + q.if_yes + " / if_no: " + q.if_no + ")\n" +
      "Run it: local `grep -ril .research/lit/papers/*.txt`, then `" + A.search_cmd + " --query \"" + q.query +
      "\" --start-year <per-window> --end-year 2026 --max-papers 5 --json`, `" + A.fetch_cmd +
      " --one <id>` as needed. Return cards that bear on the route's decisive question; " + RESIDUE_RULE +
      "\n\nStructured output only.",
      { label: "q:" + q.route_id, phase: "Routes", schema: {
        type: "object",
        required: ["cards"],
        properties: {
          cards: {
            type: "array", maxItems: 4,
            items: {
              type: "object",
              required: ["id", "title", "text_path", "on_topic", "summary", "mechanism_class", "residue"],
              properties: {
                id: { type: "string" }, title: { type: "string" }, text_path: { type: "string" },
                on_topic: { type: "boolean" }, summary: { type: "string" }, mechanism_class: { type: "string" },
                route_verdict_hint: { enum: ["supports", "weakens", "kills", "neutral"] },
                residue: {
                  type: "object", required: ["what_not_done", "abstract_level"],
                  properties: { what_not_done: { type: "string" }, abstract_level: { type: "boolean" } },
                },
              },
            },
          },
        },
      }, model: MODEL.glm })))
  let newOn = 0
  for (const w of wave.filter(Boolean)) for (const c of (w.cards || [])) {
    if (!pool.some(p => p.id === c.id)) { c.found_via = "route"; pool.push(c); newOn++ }
  }
  let changed = 0
  for (const u of (plan.routes || [])) {
    const r = routes.find(x => x.id === u.id)
    if (!r || r.status === u.status) continue
    const validEvid = (u.evidence_ids || []).filter(e => pool.some(pp => pp.id === e))
    if ((u.status === "killed" || u.status === "weakened") && !validEvid.length && !r.formal_kill) continue
    r.status = u.status; r.evidence_ids = validEvid; r.reason = u.reason || ""
    changed++
  }
  waves++
  log("wave " + waves + ": " + qs.length + " queries, +" + newOn + " cards, " + changed + " route changes")
  if (changed === 0 && newOn === 0) break   // zero state change = stop
}
// post-loop state update: the LAST wave's evidence never got a planner pass — one final
// status-only call (no queries), so late evidence can still move a route
{
  const fin = await seat(
    "## Route status update (final — no queries this time)\n## Routes\n" +
    JSON.stringify(routes.map(r => ({ id: r.id, status: r.status, hypothesis: r.hypothesis, evid: r.evidence_ids }))) +
    "\n## Evidence pool\n" + poolLine() +
    "\nUpdate route statuses ONLY (supported/weakened/killed), citing evidence_ids from the pool; " +
    "changes without evidence_ids are rejected by the orchestrator. Empty routes array if nothing moves.\n\nStructured output only.",
    { label: "routes:final", phase: "Routes", schema: {
      type: "object", required: ["routes"],
      properties: { routes: { type: "array", items: { type: "object", required: ["id", "status"], properties: {
        id: { type: "string" }, status: { enum: ["live", "supported", "weakened", "killed"] },
        evidence_ids: { type: "array", items: { type: "string" } }, reason: { type: "string" } } } } },
    }, model: MODEL.glm })
  if (!fin) return { error: "final route-update seat absent — infrastructure, not a verdict; retry." }
  for (const u of (fin.routes || [])) {
    const r = routes.find(x => x.id === u.id)
    if (!r || r.status === u.status) continue
    const evid = (u.evidence_ids || []).filter(e => pool.some(pp => pp.id === e))
    if ((u.status === "killed" || u.status === "weakened") && !evid.length && !r.formal_kill) continue
    r.status = u.status; r.evidence_ids = evid; r.reason = u.reason || ""
  }
}
const survivors0 = routes.filter(r => r.status !== "killed")
if (!survivors0.length) {
  return { outcome: "all_routes_dead", routes,
    negative_anchors: routes.map(r => r.hypothesis),
    remedial: ["every worldview died on evidence or formal grounds — loosen the anchor or supply a strategy prior"],
    stats: { routes: routes.length, cards: pool.length, agentCalls, byModel } }
}

// ═══ PHASE 3: Digest + lazy 31 ═══
phase("Digest")
const DIGEST_SCHEMA = {
  type: "object",
  required: ["bottleneck_statement", "method_target", "surviving_patterns", "negative_knowledge_slice"],
  properties: {
    bottleneck_statement: { type: "string" },
    method_target: { type: "string" },
    surviving_patterns: { type: "array", maxItems: 3, items: { type: "string" } },
    negative_knowledge_slice: { type: "string", description: "the surviving parent cards' Failure-modes / Oral-vs-Reject-gap lines, quoted" },
  },
}
const digest = await seat(
  "## Bottleneck digest (read ONLY the surviving parent pattern cards named below — no other files)\n" +
  "## Surviving routes\n" + JSON.stringify(survivors0.map(r => ({ id: r.id, pattern: r.pattern, hypothesis: r.hypothesis, evid: r.evidence_ids }))) +
  "\n## Evidence pool\n" + poolLine() +
  "\n## Pattern cards on disk (under " + RSREF + "/ideation-patterns/ — read the 1-3 your surviving routes use)\n" +
  "Produce: ONE bottleneck sentence — " + BOTTLENECK_DISCIPLINE + " — a method target; 0-3 surviving pattern names; " +
  "and the negative-knowledge slice: quote the cards' 'Failure modes (from Reject)' and 'Oral vs Reject gap' lines " +
  "verbatim (these feed the prosecutor later).\n\nStructured output only.",
  { label: "digest", phase: "Digest", schema: DIGEST_SCHEMA, model: MODEL.glm })
if (!digest) return { error: "digest seat absent — infrastructure, not a verdict; retry." }
const SUB_SCHEMA = {
  type: "object",
  required: ["picks"],
  properties: {
    picks: {
      type: "array", maxItems: 3,
      items: {
        type: "object", required: ["parent", "sub_or_none"],
        properties: { parent: { type: "string" },
                      sub_or_none: { type: "string", description: "C## name, or 'none' — no suitable child means stay at parent" } },
      },
    },
  },
}
const sub = await seat(
  "## 31 sub-pattern match (read EXACTLY this index file, no others): " + RSREF + "/ideation-sub-patterns/overview.md\n" +
  "## Surviving parents\n" + JSON.stringify(digest.surviving_patterns) +
  "\nFor each surviving parent pick AT MOST ONE child (C##) by tactical fit; 'none' is a legitimate and common " +
  "outcome — the 31 raise resolution, they are not an ontology to fill. Companion combos (" + RSREF +
  "/ideation-patterns/companion-combos.md): read ONLY if the parent's deliverable is not a runnable method while " +
  "FROZEN demands one.\n\nStructured output only.",
  { label: "sub:match", phase: "Digest", schema: SUB_SCHEMA, model: MODEL.glm })
if (!sub) return { error: "sub-pattern seat absent — infrastructure, not a verdict; retry." }

// ═══ PHASE 4: Factory — sketch swarm → prune → expand ∥ collision ═══
phase("Factory")
const SKETCH_SCHEMA = {
  type: "object",
  required: ["sketches"],
  properties: {
    sketches: {
      type: "array", maxItems: BUD.sketches,
      items: {
        type: "object",
        required: ["statement_stub", "mechanism", "pattern", "naive_baseline", "why_not_naive", "target_row", "signature_terms", "alias_terms"],
        properties: {
          statement_stub: { type: "string" }, mechanism: { type: "string" }, pattern: { type: "string" },
          subpattern: { type: "string" }, naive_baseline: { type: "string" }, why_not_naive: { type: "string" },
          target_row: { type: "string" },
          signature_terms: { type: "array", maxItems: 3, items: { type: "string" } },
          alias_terms: { type: "array", maxItems: 3, items: { type: "string" } },
        },
      },
    },
  },
}
const sketches = await seat(
  "## Idea sketch swarm (no tools)\n## FROZEN\n" + A.frozen + "\n## Bottleneck\n" + digest.bottleneck_statement +
  "\n## Method target\n" + digest.method_target + "\n## Patterns\n" + JSON.stringify(digest.surviving_patterns) +
  "\n## Sub-picks\n" + JSON.stringify(sub.picks) + "\n## Evidence pool\n" + poolLine() +
  "\n\nEmit up to " + BUD.sketches + " SHORT sketches. " + SKETCH_BIAS + " Each: statement stub / mechanism / pattern / " +
  "naive baseline + why not naive (" + NAIVE_CONTRACT + ") / target row / signature terms (own vocabulary) / alias terms (" +
  ALIAS_RULE + ").\n\nStructured output only.",
  { label: "sketch", phase: "Factory", schema: SKETCH_SCHEMA, model: MODEL.glm })
if (!sketches || !(sketches.sketches || []).length) return { error: "sketch seat absent or empty — infrastructure, not a verdict; retry." }
const PRUNE_SCHEMA = {
  type: "object", required: ["keep"],
  properties: { keep: { type: "array", maxItems: BUD.keep, items: { type: "number" } } },
}
const pruned = await seat(
  "## Portfolio prune — MECHANICAL ONLY (no taste)\n## Sketches (by index)\n" +
  sketches.sketches.map((s, i) => "[" + i + "] " + s.statement_stub + " | mech: " + s.mechanism + " | row: " + s.target_row).join("\n") +
  "\n\nDrop ONLY for: duplicate/near-duplicate mechanism; no plausible link to any keep-rule row; more than two " +
  "sketches sharing one mechanism (keep the two most distinct). Preserve mechanistic diversity. Return indices to " +
  "keep (max " + BUD.keep + ").\n\nStructured output only.",
  { label: "prune", phase: "Factory", schema: PRUNE_SCHEMA, model: MODEL.glm })
if (!pruned) return { error: "prune seat absent — infrastructure, not a verdict; retry." }
const topIdx = (pruned.keep || []).filter(i => Number.isInteger(i) && i >= 0 && i < sketches.sketches.length).slice(0, BUD.keep)
const top = topIdx.length >= 2 ? topIdx.map(i => sketches.sketches[i])
  : sketches.sketches.slice(0, Math.max(2, Math.min(BUD.keep, sketches.sketches.length)))

const CLAIM_SCHEMA = {
  type: "object",
  required: ["statement", "strategy", "target_metric", "margin_rule", "contract_rows", "premises", "naive_baseline", "steps", "falsification_prediction", "signature_terms", "alias_terms", "compute_budget"],
  properties: {
    statement: { type: "string", description: "the problem being solved, one sentence, problem-level" },
    strategy: { type: "string", description: "score-boosting mechanism: what it takes in, what it changes, how it computes" },
    target_metric: { type: "string" },
    margin_rule: { type: "string" },
    contract_rows: {
      type: "array", minItems: 3, maxItems: 5,
      items: {
        type: "object", required: ["id", "metric", "threshold", "direction"],
        properties: {
          id: { type: "string" }, metric: { type: "string" }, threshold: { type: "string" },
          direction: { enum: ["higher_better", "lower_better", "within_tol"] },
        },
      },
    },
    premises: {
      type: "array",
      items: {
        type: "object", required: ["statement", "kind"],
        properties: {
          statement: { type: "string" }, evidence_id: { type: "string" },
          kind: { enum: ["evidence_backed", "bet_untested"] },
        },
      },
    },
    advantages: { type: "array", items: { type: "string" } },
    naive_baseline: {
      type: "object", required: ["version", "branch"],
      properties: { version: { type: "string" }, branch: { enum: ["false_premise", "incremental", "minimalism"] } },
    },
    steps: { type: "array", minItems: 3, maxItems: 10, items: { type: "string" } },
    falsification_prediction: { type: "string" },
    signature_terms: { type: "array", items: { type: "string" } },
    alias_terms: { type: "array", items: { type: "string" } },
    compute_budget: { type: "string" },
  },
}
const COLLISION_SCHEMA = {
  type: "object",
  required: ["verdicts"],
  properties: {
    verdicts: {
      type: "array",
      items: {
        type: "object", required: ["index", "collision"],
        properties: { index: { type: "number" }, collision: { enum: ["NONE", "ADJACENT", "EXACT"] }, evidence: { type: "string" } },
      },
    },
  },
}
const expandAndCollide = await parallel(top.map((s, i) => () => parallel([
  () => seat(
    "## Claim expansion (no tools except ONE card file if named below)\n## Sketch\n" + JSON.stringify(s) +
    "\n## Sub-card\n" + (((sub.picks || []).find(p => p.parent === s.pattern) || {}).sub_or_none || "none") +
    (String(((sub.picks || []).find(p => p.parent === s.pattern) || {}).sub_or_none || "").toLowerCase() === "none"
      ? " — no sub-pattern card; stay at the parent pattern, do NOT read any file"
      : " — read EXACTLY " + RSREF + "/ideation-sub-patterns/" + ((sub.picks || []).find(p => p.parent === s.pattern) || {}).sub_or_none + ".md, no others") +
    "\n## Bottleneck\n" + digest.bottleneck_statement + "\n## FROZEN protocol/keep lines\n" + A.frozen.slice(0, 2500) +
    "\n\nExpand into a FULL Claim born consumable by the experiment ladder. " + FALSIFY_MIN + " Every load-bearing premise " +
    "marked evidence_backed (pool id) or bet_untested. " + NAIVE_CONTRACT + "\n\nStructured output only.",
    { label: "claim:" + i, phase: "Factory", schema: CLAIM_SCHEMA, model: MODEL.glm }),
  () => seat(
    "## Collision (Bash only — search seat; Bash, no web tools)\n## Sketch\n" + JSON.stringify({ s: s.signature_terms, a: s.alias_terms }) +
    "\nLocal corpus first (`grep -ril .research/lit/papers/*.txt`), then `" + A.search_cmd +
    " --query \"<term>\" --start-year <per-window> --end-year 2026 --max-papers 5 --json`, `" + A.fetch_cmd +
    " --one <id>` as needed. signature → recent window (~24 mo); alias → WIDE multi-year (10+y) — " + ALIAS_RULE +
    " Also `python3 /home/lingxufeng/workspace/.research/tools/search_github.py --query \"<mechanism words>\" --json` " +
    "(implementation-first prior work).\nReturn ONE verdict object: {index: 0, collision: NONE|ADJACENT|EXACT, evidence}.\n\nStructured output only.",
    { label: "coll:" + i, phase: "Factory", schema: COLLISION_SCHEMA, model: MODEL.glm }),
])))
// index alignment: a collision seat returns verdicts for ITS OWN sketch; the seat-reported
// index is unreliable — key by the OUTER sketch index. An absent pair (claim seat died) drops
// both halves so claims/collisions never misalign.
const claims = []
const collBy = {}
expandAndCollide.forEach((pair, i) => {
  if (!pair || !pair[0]) return
  claims.push(pair[0])
  if (pair[1] && pair[1].verdicts && pair[1].verdicts.length) collBy[claims.length - 1] = pair[1].verdicts[0]
})
if (!claims.length) return { error: "all claim-expansion seats absent — infrastructure, not a verdict; retry." }

// ═══ PHASE 5: Verdict — K3 prosecute ∥ Sol formal review → JS composition ═══
phase("Verdict")
const PROSECUTE_SCHEMA = {
  type: "object",
  required: ["verdicts"],
  properties: {
    verdicts: {
      type: "array",
      items: {
        type: "object", required: ["index", "call"],
        properties: {
          index: { type: "number" }, call: { enum: ["CLEAR", "CHALLENGE", "SEARCH_REQUIRED"] },
          reason: { type: "string" }, search_query: { type: "string" },
        },
      },
    },
  },
}
const SOLVER_SCHEMA = {
  type: "object",
  required: ["verdicts"],
  properties: {
    verdicts: {
      type: "array",
      items: {
        type: "object", required: ["index", "verdict"],
        properties: { index: { type: "number" }, verdict: { enum: ["PASS", "FORMAL_RISK", "HARD_KILL"] }, reason: { type: "string" } },
      },
    },
  },
}
const claimsBlock = claims.map((c, i) => "### [" + i + "]\n" + JSON.stringify({
  statement: c.statement, strategy: c.strategy, target_metric: c.target_metric,
  margin_rule: c.margin_rule, contract_rows: c.contract_rows, naive: c.naive_baseline,
  falsifier: c.falsification_prediction, premises: c.premises, steps: c.steps.length })).join("\n\n")
const [pros, solv] = await parallel([
  () => seat(
    "## Prosecutor (K3 — you raise fatal possibilities; you do NOT judge; read ONE file below, no others)\n" +
    "## Candidates\n" + claimsBlock +
    "\n## Negative knowledge (the corpus's Reject lessons)\n" + digest.negative_knowledge_slice +
    "\nAlso read EXACTLY " + RSREF + "/anti-patterns.md (3 reject-favored compositions with n_O/n_R).\n" +
    "Per candidate: CLEAR / CHALLENGE(+reason anchored in the quoted failure modes — e.g. 'gain confounded with " +
    "co-introduced components', 'true bottleneck untouched → silent ceiling', 'preservation asserted not proven') / " +
    "SEARCH_REQUIRED(+query — a fatal_if_true that GLM search must convert to evidence). A CHALLENGE without external " +
    "evidence does NOT kill — the candidate survives carrying your flag.\n\nStructured output only.",
    { label: "prosecute", phase: "Verdict", schema: PROSECUTE_SCHEMA, model: MODEL.k3 }),
  () => seat(
    "## Formal review (sol — hard power; no tools)\n## Candidates\n" + claimsBlock +
    "\nSix HARD-KILL classes: equivalent_to_naive / formal contradiction / the algorithm cannot produce the claimed " +
    "estimand / falsification tautological / the negative control moves the variable, not the downstream metric / " +
    "impossible compute dependency. Otherwise PASS or FORMAL_RISK (named, repairable). " + FALSIFY_MIN +
    "\n\nStructured output only.",
    { label: "formal", phase: "Verdict", schema: SOLVER_SCHEMA, model: MODEL.sol }),
])
if (!pros || !solv) return { error: "prosecutor/formal seat absent — infrastructure, not a verdict; retry." }
const proBy = {}, solBy = {}
for (const v of (pros.verdicts || [])) proBy[v.index] = v
for (const v of (solv.verdicts || [])) solBy[v.index] = v
// K3 SEARCH_REQUIRED → one GLM search round → EXACT check
const needSearch = Object.keys(proBy).filter(i => proBy[i].call === "SEARCH_REQUIRED" && proBy[i].search_query)
for (const i of needSearch) ledgerTake(proBy[i].search_query, "prosecute")
const searched = needSearch.length ? await parallel(needSearch.map(i => () =>
  seat("## Fatal-if-true search (Bash only)\nQuery: " + proBy[i].search_query + "\nCandidate strategy: " + claims[i].strategy +
    "\nLocal corpus first, then the search script. Is there an EXACT prior (same mechanism, any age, any vocabulary)? " +
    "Answer EXACT with the paper, or NONE/ADJACENT.\n\nStructured output only.",
    { label: "fatal:" + i, phase: "Verdict", schema: {
      type: "object", required: ["collision"],
      properties: { collision: { enum: ["NONE", "ADJACENT", "EXACT"] }, evidence: { type: "string" } },
    }, model: MODEL.glm }))) : []
// JS deterministic composition — evidence kills or formal kills, never opinion
const rows = claims.map((c, i) => {
  const coll = collBy[i] ? collBy[i].collision : "NONE"
  const si = needSearch.indexOf(String(i))
  const fatalColl = si >= 0 && searched[si] ? searched[si].collision : null
  const sol = solBy[i] ? solBy[i].verdict : "PASS"
  const pro = proBy[i] ? proBy[i].call : "CLEAR"
  let status = "survivor", why = []
  if (sol === "HARD_KILL") { status = "killed"; why.push("Sol hard kill: " + (solBy[i].reason || "")) }
  if (coll === "EXACT" || fatalColl === "EXACT") { status = "killed"; why.push("EXACT collision") }
  if (status === "survivor" && pro === "CHALLENGE") why.push("flag: " + (proBy[i].reason || ""))
  return { i, claim: c, status, sol, pro, coll, flags: why }
})
const survivors = rows.filter(r => r.status === "survivor")
if (!survivors.length) {
  return { outcome: "all_killed", kill_reasons: rows.map(r => ({ why: r.why, statement: r.claim.statement })),
    negative_anchors: rows.filter(r => r !== picked).map(r => ({ statement: r.claim.statement, signature: r.claim.signature_terms })),
    routes, digest, queries: Array.from(ledger.values()).map(l => l.q),
    stats: { cards: pool.length, claims: claims.length, agentCalls, byModel } }
}
// mechanical compare: smaller method (steps) → fewer untested premises → Sol grade → fewer flags
const grade = { PASS: 0, FORMAL_RISK: 1, HARD_KILL: 2 }
survivors.sort((a, b) => (a.claim.steps.length - b.claim.steps.length) ||
  ((a.claim.premises || []).filter(p => p.kind === "bet_untested").length -
   (b.claim.premises || []).filter(p => p.kind === "bet_untested").length) ||
  (grade[a.sol] - grade[b.sol]) || (a.flags.length - b.flags.length))
let picked = survivors[0]
if (survivors.length > 1) {
  const a = survivors[0], b = survivors[1]
  const tied = a.claim.steps.length === b.claim.steps.length &&
    (a.claim.premises || []).filter(p => p.kind === "bet_untested").length ===
    (b.claim.premises || []).filter(p => p.kind === "bet_untested").length && a.sol === b.sol &&
    a.flags.length === b.flags.length
  if (tied) {
    const pick = await seat(
      "SEAT (Opus — taste, pairwise only)\n## Candidate A\n" + JSON.stringify({ s: a.claim.statement, strat: a.claim.strategy, margin: a.claim.margin_rule }) +
      "\n## Candidate B\n" + JSON.stringify({ s: b.claim.statement, strat: b.claim.strategy, margin: b.claim.margin_rule }) +
      "\n## FROZEN\n" + A.frozen.slice(0, 2000) +
      "\nAll mechanical axes tied. Pick ONE: whose margin_rule does the FROZEN evidence most support, and whose mechanism " +
      "survives its own naive confrontation harder. One sentence why.\n\nStructured output only.",
      { label: "pick", phase: "Verdict", schema: {
        type: "object", required: ["index", "rationale"],
        properties: { index: { type: "number" }, rationale: { type: "string" } },
      }, model: MODEL.opus })
    if (pick && (pick.index === 0 || pick.index === 1)) picked = pick.index === 0 ? a : b
  }
}
return {
  round: A.round || 1,
  outcome: "selected",
  // dag compatibility: v1 put the one-liner under title/claim_statement; keep both
  title: picked.claim.statement,
  claim_statement: picked.claim.statement,
  selected: Object.assign({}, picked.claim, { flags: picked.flags, sol_verdict: picked.sol,
    title: picked.claim.statement, claim_statement: picked.claim.statement }),
  others: survivors.filter(s => s !== picked).map(s => ({ statement: s.claim.statement, strategy: s.claim.strategy, signature: s.claim.signature_terms })),
  bottleneck: digest, sub_picks: sub.picks, routes,
  negative_anchors: rows.map(r => ({ statement: r.claim.statement, signature: r.claim.signature_terms })),
  pool: { cards: pool.length, ids: pool.map(c => c.id) },
  queries: Array.from(ledger.values()).map(l => l.q),
  stats: { waves, routes: routes.length, routes_alive: survivors0.length, cards: pool.length,
    sketches: sketches.sketches.length, claims: claims.length, killed: rows.length - survivors.length,
    agentCalls, byModel },
}
