export const meta = {
  name: 'brain',
  description: 'V9 Brain: ResearchStudio idea-spark over one repository — Phase -1 intake, one shared Phase 0, K navigator-driven runs in parallel (Opus taste / GLM engineering / K3 audit), an evidence plan per surviving idea, one ranking',
  whenToUse: 'Brain session: Workflow({scriptPath: ".claude/workflows/brain.workflow.js", args: {root, repo, dataset, venue, goal, anomalies, k}}). Resumable: re-run with the same args; every phase reads the run root on disk.',
  phases: [
    { title: 'Intake', detail: 'Phase -1: repository → intake.json + substrate.md + queries.json (GLM, read-only tools)' },
    { title: 'Phase 0', detail: 'RS retrieval → pattern tagging shards (GLM) → lit_table_merge → full-text fetch → spawn r1..rK' },
    { title: 'Runs', detail: 'run.py next drives each run: Phase 1 (Opus, r1 only) → 2.1+2.2 (Opus) → citation gate → 2.3 (Opus+python, fallback GLM) ∥ 3.1 → 3.2 (K3 ∥ Sol second auditor, merged; threat quote checked) → 3.3 (Opus) → Phase 4 → validate (repair ≤2) → cards → regression_check' },
    { title: 'Evidence', detail: 'Phase 5 evidence_plan.json (Opus, fallback GLM) → plan_check → Phase 6 spec/B*.json (Opus, read-only repo, fallback GLM) → spec_check; existing files that pass their check are kept, not regenerated' },
    { title: 'Rank', detail: 'one Opus seat scores the K ideas with the CCF idea-review rubric + calibration (10 dims, fatal gates, tournament) → rank_check — rank, never kill' },
  ],
}

// ═══════════════════════════════════════════════════════════════ 0. arguments
const A = args || {}
if (!A.root) throw new Error('args.root is required: absolute run root, e.g. <workspace>/.research/research/ideaspark/<slug>')
const ROOT = String(A.root).replace(/\/+$/, '')
const K = Math.max(1, parseInt(A.k, 10) || 1)
const WS = A.workspace || (ROOT.includes('/.research/') ? ROOT.slice(0, ROOT.indexOf('/.research/')) : '/home/lingxufeng/workspace')   // harness root: derived from args.root (<ws>/.research/research/ideaspark/<slug>) unless given
const SKILL_DIR = A.skill_dir || WS + '/docs/refs/rs'          // ResearchStudio idea-spark, verbatim copy
const PY = A.python || 'python3'
const MAX_STEPS = A.max_steps || 60                            // navigator steps per run (RS worst case ≈ 45)
const SHARED = ROOT + '/_shared'
const P0 = SHARED + '/phase0'
const JOBS = ROOT + '/.jobs'
const RUN_IDS = Array.from({ length: K }, (_, i) => 'r' + (i + 1))
const BRIEF = { repo: A.repo || '', dataset: A.dataset || '', venue: A.venue || '', goal: A.goal || '', anomalies: A.anomalies || '' }
const USER_REFS = Array.isArray(A.user_refs) ? A.user_refs : []   // [{title, id?, raw_match?}] title-named anchor papers
const COMPUTE = A.compute || ''                                     // IDEASPARK_DEFAULT_COMPUTE (Phase 1 intake context)
const REQUIRED_BASELINES = Array.isArray(A.required_baselines) ? A.required_baselines : []   // keywords the headline block's baselines must contain (FROZEN table)
const FORBIDDEN_PATTERNS = Array.isArray(A.forbidden_patterns) ? A.forbidden_patterns : ['test_half', 'test.txt', 'held_out', 'heldout']   // must not appear in spec run_cmd/arms
const NEGATIVE_ANCHORS = Array.isArray(A.negative_anchors) ? A.negative_anchors.map(String) : []   // failure cards (failures/X-*.json) from the experiment side: mechanisms built and run on this repository that died (L2/L3/L4); retrigger.py fills this on a Brain re-trigger

// Model ids are the claude-kimi routes (LiteLLM :4001): glm-5.3[1m] / claude-opus-5 / k3-256k.
// Run the Brain from a `claude-kimi` session. On the official Anthropic API these ids do not
// exist and the harness silently serves the SESSION model at session effort instead — that is
// what turned the 2026-09-06 run into 3.6 h. Override per environment with
// args.models = {opus, glm, k3} and args.runner_model; effort is set explicitly on every seat.
const MODEL = Object.assign({ opus: 'claude-opus-5', glm: 'glm-5.3[1m]', k3: 'k3-256k', sol: 'gpt-5.6-sol', astra: 'gpt-6-astra' }, A.models || {})   // sol / astra = Codex-OAuth models on LiteLLM :4001 (quota-limited: keep them on one-call seats; a model whose quota is gone hangs in API retries and never reaches the seat fallback)
const RUNNER_MODEL = A.runner_model || MODEL.glm
const SECOND_KILLS = !!A.second_auditor_kills   // false: the second auditor can force `revise` and add revision_targets, never `abandon` alone; true: either auditor's abandon kills
const STAGGER = !!A.stagger   // true: 2.1+2.2 one run at a time so RS's CROSS-RUN DEDUP line sees earlier candidates (+~15 min per extra run)

const shq = (s) => "'" + String(s).replace(/'/g, "'\\''") + "'"

// Mechanical tool discipline (the runtime enforces these; the prose in TOOLS is the explanation).
// disallowedTools narrows the pool per call; bashCommandClamp allows only python3 for the dry-run seat.
const DENY = {
  readwrite: ['Bash', 'Glob', 'Grep', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
  exec:      ['Glob', 'Grep', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
  repo:      ['Bash', 'Edit', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
  spec:      ['Bash', 'Edit', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
  runner:    ['Read', 'Write', 'Edit', 'Glob', 'Grep', 'WebFetch', 'WebSearch', 'NotebookEdit', 'ToolSearch'],
}
const CLAMP = A.no_clamp ? {} : { exec: ['Bash(python3:*)'] }   // args.no_clamp for a host whose Bash is aliased
const RS = PY + ' ' + shq(SKILL_DIR + '/scripts/run.py')
const ENV = COMPUTE ? 'IDEASPARK_DEFAULT_COMPUTE=' + shq(COMPUTE) + ' ' : ''
let SKIP_ENV = ''   // 'IDEASPARK_SKIP_SOURCES=dblp ' once a connector timed out in Phase 0 (session-wide circuit breaker; run.py honours it)
const base = (p) => String(p).split('/').pop()

// ═══════════════════════════════════════════════════════════════ 1. prompt bank (verbatim)
// Every ResearchStudio system prompt and every reference a seat reads is reproduced here
// unchanged (generated from docs/refs — see docs/refs/INDEX.md). Only the 15 pattern cards
// and the 31 sub-pattern cards stay on disk: the prompts tell each seat which ones to open.
/*__BANK__*/

BANK.rank = { path: 'brain/rank.md', text: `You are the ranking seat of the V9 Brain. K independent ResearchStudio runs each produced one idea card, one evidence plan and (when present) block specs for the same repository and the same FROZEN goal. Score every idea with the CCF idea-review rubric and calibration reproduced verbatim below, then order them. Never discard one: "abandon" is not available here — the weakest idea is ranked last with its rescue route named.

How to score (the inlined references are the standard, not suggestions):
1. rubric.md — score all 10 dimensions 1-5 with a confidence 1-5 each; weighted_score = sum(score * weight) / 100 on the 1-5 scale; every score <= 3 carries the Deduction Format block (Dimension / Deduction / Anchor / Why it matters / Repair condition / Development-potential effect). Score the problem and method only, never the prose of the card.
2. Search basis is "searched": ResearchStudio retrieved the literature (phase0/lit_table.md) and ran the dual-channel collision retrieval for every run, and the 3.2 audit named the paper-pointed threat (phase3_critique_output.json, listed below) — that is the closest-work basis; novelty is scored against it, never from memory.
3. calibration.md — apply the Recommendation Bands, all eight Fatal Gates, the Confidence Labels, Development Potential and the Multi-Idea Tournament rules (normalize, score independently, apply gates, prefer the strongest fixable path over the highest average, keep one backup); strict-idea-review.md — apply the Score Guardrails and the Stage-Aware Verdict rule.
4. Judge blind to provenance: the run id, the order of the inputs and the length or polish of a card are not evidence of quality (ResearchStudio idea_quality rule: judge substance; quote the element of the card that justifies every score).
5. Under the FROZEN goal, "Experimental convincibility" is judged on the evidence plan (does the first block kill the idea cheaply; does the negative control operate on the load-bearing variable) and "Feasibility under resources" on total_gpu_h against the substrate's compute envelope.
6. Before any score, write the five required expert-panel notes per idea (expert-panel.md: Field Expert / Method Expert / Experiment Expert / AC-Venue Expert / Skeptical Prior-Art Expert) in the per-reviewer block of review-output-standards.md, each with a rejection-grade concern or the reason none exists; then the Panel synthesis block. Synthesis never averages away a fatal risk — the stance follows the strongest unresolved decision-relevant concern.
7. "Venue and audience fit" follows venue-idea-adapters.md for the venue family named in the FROZEN goal; "why" answers the six Development Selection questions of literature-grounded-evolution.md (gap grounded, mechanism causal, distinguishable from closest work, one experiment falsifies, resources plausible, teaches something if the headline is modest).
8. Run the Output Quality Gate of review-output-standards.md on ranking.json before writing it: scores, confidence and recommendation internally consistent; no placeholder; no generic filler.

Write ranking.json to the output path (numbers, never prose, in the numeric fields):
{"search_basis": "searched",
 "ranking": [{"run": "r1", "rank": 1, "title": "...", "recommendation": "accept-to-develop|revise|pivot-with-rescue-route|needs-literature-search",
   "scores": {"problem_importance": {"score": 4, "confidence": 4, "evidence": "<quoted element of the card>"}, "novelty": {}, "conceptual_innovation": {}, "method_soundness": {}, "elegance": {}, "feasibility": {}, "experimental_convincibility": {}, "venue_fit": {}, "timeliness": {}, "acceptance_potential": {}},
   "weighted_score": 3.9,
   "fatal_gates_triggered": ["<verbatim gate text from calibration.md, or empty>"],
   "deductions": [{"dimension": "<one of the ten keys>", "deduction": "...", "anchor": "closest work|missing mechanism|missing evidence|venue criterion|internal contradiction", "why_it_matters": "...", "repair_condition": "...", "development_potential_effect": "..."}],
   "development_potential": "high|medium|low", "confidence": "high|medium|low", "current_readiness": "high|medium|low",
   "panel": [{"reviewer": "Field Expert|Method Expert|Experiment Expert|AC / Venue Expert|Skeptical Prior-Art Expert", "lens": "...", "score_tendency": "...", "confidence": "...", "main_positive": "...", "main_negative": "<rejection-grade concern or why none>", "evidence_basis": "...", "score_change_condition": "..."}],
   "synthesis": {"agreement": "...", "disagreement": "...", "decisive_accept_axis": "...", "decisive_reject_axis": "...", "unresolved_evidence": "...", "final_calibrated_stance": "..."},
   "why": "<three sentences citing the card and the plan>", "first_block_to_run": "<block_id>", "biggest_risk": "<one sentence>", "backup": false}],
 "backup_run": "<the run kept as backup per the tournament rule, or null>"}

Rules: every run appears exactly once with ranks 1..K; the ten dimension keys and their weights are exactly rubric.md's (12/14/12/14/8/8/10/8/6/8 — a script recomputes weighted_score from your scores and rejects a mismatch, a missing deduction block for a score <= 3, and a recommendation that ignores a fatal gate); rank order follows the tournament rule (serious-risk-adjusted, strongest fixable path), ties broken toward the cheaper first block; every idea carries the five panel notes and a synthesis (a script rejects fewer than five); do not rewrite, merge, or kill ideas — ranking is advisory for the Worker session.` }

BANK.spec = { path: 'brain/spec.md', text: `You are the Phase 6 seat of the V9 Brain: the block-spec author. The idea has passed ResearchStudio's gauntlet and Phase 5 wrote evidence_plan.json (claims, blocks, arms, keep rules). Your job is the ASI-Bench "B1" level of that plan: for EVERY block in evidence_plan.json write spec/B<k>.json — a specification a coding agent can implement WITHOUT making any scientific decision itself. The plan IS the experiment: steps are file-level and executable as written; run_cmd and smoke_cmd are copy-paste runnable; the implementer may make ENGINEERING decisions only — any SCIENTIFIC decision the spec leaves open is a defect of the spec, so if a decision must be delegated, list it in decision_points with a default value. You read the repository (Read/Glob/Grep only; never run anything, never edit repository files) to name real files, functions, configs, tensor shapes and entry points. You write only under RUN_DIR/spec/.

Each spec/B<k>.json:
{
  "block_id": "B1", "claim_id": "C1",
  "goal": "<one sentence: what this block settles>",
  "tests_premise": "<the premise from the card's PREMISES ledger this block tests>",
  "anti_claim": "<the sentence that, if true, ends the idea — copied from the card's negative control / kill condition>",
  "method": {"equations": ["<the equation(s) this block exercises, copied from method_view.json>"], "steps": ["<method_view step ids in execution order, each with one sentence of what the code does>"]},
  "changes": [{"file": "<repo-relative path that exists>", "function": "<existing function/class or NEW>", "what": "<exact change>", "tensor_shapes": "<in → out>"}],
  "run_cmd": "<the FULL command from the repository's existing launchers, arguments spelled out; NEVER set a SMOKE variable yourself — the Worker's launch wrapper does>",
  "smoke_cmd": "<the smallest NOT_A_RESULT run that proves the wiring: same launcher, minutes not hours, what must print>",
  "arms": [{"name": "...", "config": "<exact config/flag values>", "what_changes": "..."}],
  "baselines": ["<config names from substrate.md>"],
  "negctl_arm": "<name of the arm in arms[] that MUST fail: it operates on the load-bearing variable and predicts the downstream metric returns to baseline>",
  "attribution": "<the control that says WHY it worked (parameter-free / permuted / capacity-matched)>",
  "verdict_rule": {
    "outcome_metric": "<metric + direction, verbatim from the FROZEN goal>",
    "arms": {"candidate": "<arm name>", "control": "<arm name>", "negative_control": "<arm name>"},
    "keep_if_all": [{"key": "<m158 verdict.json key>", "op": "gt|gte|lt|lte|eq", "value": <number or boolean>}],
    "split": "<dev or test half, per FROZEN>", "seeds": [<seed list>], "mde_source": "<where the noise floor comes from>"
  },
  "kill_condition": "<one observable outcome that ends this block, from evidence_plan.kill_conditions>",
  "decision_points": [{"name": "<engineering choice left to the implementer>", "default": "<value to use unless blocked>", "why_engineering": "<why this cannot change which claim the result supports>"}],
  "open_holes": [{"step_id": "S3", "hole": "<from phase4_implementability.json underspecified_points with severity open>", "resolution": "<the choice you make here, with the file:line fact it rests on>", "blocked": null}],
  "forbids": ["<paths, splits, scripts the implementation must never touch or read>"],
  "outputs": [{"file": "...", "schema": "..."}],
  "gates": [{"name": "...", "severity": "hard", "check": "file_exists|no_nan_inf|forbidden_import|forbidden_pattern|key_present", "config": {"file": "<for file_exists / key_present / no_nan_inf>", "key": "<for key_present>", "pattern": "<regex, for forbidden_pattern>", "imports": ["<for forbidden_import>"]}}],
  "gpu_h": <number>
}
Also write spec/index.json: {"blocks": ["B1", ...], "run_order": [...], "first_block": "B1"}.

keep_if_all keys are the keys the repository's verdict instrument writes (see instruments/README.md if present; typical: delta, ci_lo, ci_hi, both_rungs_exclude_zero, per_rung.<rung>.ci_lo, candidate_clean_cost, negctrl_delta, negctrl_ci_lo, networks_keep); ops are gt/gte/lt/lte/eq; every rule is a number or boolean, never prose.

Rules: every path in changes[] and run_cmd must exist in the repository (you verified it with Read/Glob); never invent a launcher — if the repository lacks one, say so in smoke_cmd and name the closest existing script; forbids must include the test half and every protected evaluation script named in substrate.md; every underspecified point with severity "open" in phase4_implementability.json appears in open_holes with a resolution or with "blocked" set; the first block in index.json is the cheapest test that can kill the idea; do not change any scientific decision of the evidence plan — if a block cannot be specified, write it with "blocked": "<why>" instead of guessing. gates follow the ASI-Bench evaluation.gates form (task.yaml inlined below): hard, structural, script-checkable — one file_exists gate per outputs[] entry, one forbidden_pattern or forbidden_import gate per forbids[] entry, no_nan_inf on every numeric result file — never a science check; the B1 prompt inlined below shows the completeness a procedure must reach (every convention, law and constant disclosed); and per how-scoring-works.md self-reported scores are never trusted: the verdict instrument reads result files, never the Worker's summary.` }

// Deterministic checks (run by the runner; they print __PLAN_OK / __PLAN_BAD, __SPEC_OK / __SPEC_BAD, __QUOTE ...).
const PLAN_CHECK_PY = `import json, re, sys
plan_path, req = sys.argv[1], json.loads(sys.argv[2])
bad, warn = [], []
try:
    e = json.load(open(plan_path))
except Exception as ex:
    print("__PLAN_BAD evidence_plan.json unreadable: " + str(ex)[:120]); sys.exit(0)
blocks = e.get("blocks") or []; ids = [b.get("block_id") for b in blocks]
claims = e.get("claim_map") or []
if not claims: bad.append("claim_map empty")
if not blocks: bad.append("blocks empty")
for c in claims:
    if c.get("evidence_block") not in ids: bad.append("claim %s -> unknown block %s" % (c.get("claim_id"), c.get("evidence_block")))
lbv = [str(c.get("load_bearing_variable") or "").strip() for c in claims if c.get("load_bearing_variable")]
for b in blocks:
    bid = b.get("block_id")
    if not b.get("negative_control"): bad.append("%s has no negative_control" % bid)
    elif lbv and not any(t.lower() in str(b["negative_control"]).lower() for v in lbv for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", v)[:3]): warn.append("%s negative_control does not name a load-bearing variable" % bid)
    if not re.search(r"\\d", str(b.get("keep_rule") or "")): bad.append("%s keep_rule has no number" % bid)
    if not (b.get("arms") or []): bad.append("%s has no arms" % bid)
    if not isinstance(b.get("gpu_h"), (int, float)): bad.append("%s gpu_h not numeric" % bid)
    sd, me, ns = b.get("seed_sd"), b.get("min_effect"), b.get("seeds")
    if not isinstance(sd, (int, float)) or not isinstance(me, (int, float)): bad.append("%s seed_sd/min_effect not numeric (Lehr MDE cannot be checked)" % bid)
    elif isinstance(ns, (int, float)) and ns > 0:
        lehr = 2.8 * sd * (2.0 / ns) ** 0.5
        if me < lehr: bad.append("%s min_effect %.3f below Lehr MDE %.3f for %d seeds (sd %.3f)" % (bid, me, lehr, ns, sd))
    else: bad.append("%s seeds not numeric" % bid)
for ab in e.get("ablations") or []:
    nm = str(ab.get("name") or "?")
    if not ab.get("removes"): bad.append("ablation %s removes nothing (no-op ablation)" % nm)
    if not ab.get("what_it_tests") or not ab.get("expected_if_component_matters"): bad.append("ablation %s lacks what_it_tests / expected_if_component_matters" % nm)
roles = {"anchor", "novelty_isolation", "simplicity", "frontier_necessity", "failure_analysis"}
prim = [c for c in claims if c.get("primary") is True]
if claims and not prim: warn.append("no claim marked primary")
if len(prim) > 2: bad.append("MAX_PRIMARY_CLAIMS=2 exceeded: %d primary claims" % len(prim))
present = set()
for b in blocks:
    bid = b.get("block_id"); role = b.get("role")
    if role not in roles: bad.append("%s role missing or not one of %s" % (bid, sorted(roles)))
    else: present.add(role)
    if not str(b.get("failure_interpretation") or "").strip(): bad.append("%s has no failure_interpretation" % bid)
skipped = {str(x.get("role")) for x in (e.get("skipped_roles") or []) if isinstance(x, dict) and x.get("why")}
if blocks and "anchor" not in present: bad.append("no anchor block (main anchor result)")
for role in sorted(roles - present - skipped): warn.append("storyline role %s neither present nor explicitly skipped" % role)
mcp = e.get("minimum_convincing_package") or []
if len(mcp) > 5: bad.append("MAX_CORE_BLOCKS=5 exceeded: minimum_convincing_package has %d blocks" % len(mcp))
fam = {str(x).strip().lower() for b in blocks for x in (b.get("baselines") or [])}
if len(fam) > 6: warn.append("%d distinct baselines across blocks; MAX_BASELINE_FAMILIES=3 prefers one strong family" % len(fam))
order = e.get("run_order") or []
if not order: bad.append("run_order empty")
elif any(o not in ids for o in order): bad.append("run_order names unknown blocks")
elif blocks:
    g = {b.get("block_id"): b.get("gpu_h") for b in blocks}
    first = g.get(order[0])
    if isinstance(first, (int, float)) and any(isinstance(v, (int, float)) and v < first for v in g.values()): warn.append("first block %s (%.1f GPU-h) is not the cheapest" % (order[0], first))
if not (e.get("kill_conditions") or []): bad.append("kill_conditions empty")
if not (e.get("frozen_untouched") or []): bad.append("frozen_untouched empty")
if not isinstance(e.get("total_gpu_h"), (int, float)): bad.append("total_gpu_h not numeric")
if req and order:
    head = next((b for b in blocks if b.get("block_id") == order[-1]), None)
    text = " ".join(str(x) for x in (head or {}).get("baselines") or []).lower()
    miss = [r for r in req if r.lower() not in text]
    if miss: bad.append("headline block %s baselines missing: %s" % (order[-1], ", ".join(miss)))
txt = json.dumps(e).lower()
if "attribution" not in txt and "parameter-free" not in txt: warn.append("no attribution control anywhere in the plan (X.6)")
print(("__PLAN_BAD " if bad else "__PLAN_OK ") + " | ".join(bad + ["warn: " + w for w in warn]))`

const SPEC_CHECK_PY = `import json, os, re, sys, glob
spec_dir, repo, forbidden, impl_path = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
bad, warn = [], []
files = sorted(glob.glob(os.path.join(spec_dir, "B*.json")))
if not files: bad.append("no spec/B*.json")
if not os.path.exists(os.path.join(spec_dir, "index.json")): bad.append("spec/index.json missing")
need = ["block_id", "goal", "method", "changes", "run_cmd", "smoke_cmd", "arms", "baselines", "negctl_arm", "verdict_rule", "kill_condition", "decision_points", "open_holes", "forbids", "outputs", "gates", "gpu_h"]
gk = {"file_exists", "no_nan_inf", "forbidden_import", "forbidden_pattern", "key_present"}
ops = {"gt", "gte", "lt", "lte", "eq"}
open_holes = set()
try:
    impl = json.load(open(impl_path))
    for u in impl.get("underspecified_points") or []:
        if str(u.get("severity")) == "open": open_holes.add(str(u.get("step_id")) + "|" + str(u.get("hole"))[:60])
except Exception:
    pass
covered = set()
for f in files:
    try: d = json.load(open(f))
    except Exception as ex: bad.append(os.path.basename(f) + " unreadable: " + str(ex)[:80]); continue
    n = os.path.basename(f)
    if d.get("blocked"): warn.append(n + " blocked: " + str(d["blocked"])[:100]); continue
    for k in need:
        if k not in d or d[k] in ("", {}, None): bad.append(n + " missing " + k)
    for ch in d.get("changes") or []:
        fp = str(ch.get("file") or "")
        if fp and not os.path.exists(os.path.join(repo, fp)) and not os.path.exists(fp): bad.append(n + " change file not found: " + fp)
    for key in ("run_cmd", "smoke_cmd"):
        cmd = str(d.get(key) or "")
        if re.search(r"(^|\\s)SMOKE=", cmd): bad.append(n + " " + key + " sets SMOKE itself")
        tok = [t for t in re.split(r"\\s+", cmd) if t and not t.startswith("-")]
        scripts = [t for t in tok if t.endswith(".py") or t.endswith(".sh")]
        for sc in scripts[:1]:
            if not os.path.exists(os.path.join(repo, sc)) and not os.path.exists(sc): bad.append(n + " " + key + " script not found: " + sc)
    blob = json.dumps({"run_cmd": d.get("run_cmd"), "smoke_cmd": d.get("smoke_cmd"), "arms": d.get("arms")}).lower()
    for pat in forbidden:
        if pat.lower() in blob: bad.append(n + " mentions forbidden pattern in run_cmd/smoke_cmd/arms: " + pat)
    names = {str(a.get("name")) for a in (d.get("arms") or []) if isinstance(a, dict)}
    vr = d.get("verdict_rule") or {}
    roles = vr.get("arms") or {}
    for role in ("candidate", "control", "negative_control"):
        if str(roles.get(role)) not in names: bad.append(n + " verdict_rule.arms." + role + " is not an arm name")
    if str(d.get("negctl_arm")) not in names: bad.append(n + " negctl_arm is not an arm name")
    kia = vr.get("keep_if_all") or []
    if not kia: bad.append(n + " verdict_rule.keep_if_all empty")
    for r in kia:
        if not isinstance(r, dict) or not r.get("key") or r.get("op") not in ops or not isinstance(r.get("value"), (int, float, bool)) or isinstance(r.get("value"), str):
            bad.append(n + " keep_if_all rule not machine-readable: " + json.dumps(r)[:80])
    if not isinstance(vr.get("seeds"), list) or not vr.get("seeds"): bad.append(n + " verdict_rule.seeds missing")
    if not isinstance(d.get("decision_points"), list): bad.append(n + " decision_points not a list")
    for dp in d.get("decision_points") or []:
        if not isinstance(dp, dict) or dp.get("default") in (None, ""): bad.append(n + " decision_point without default")
    gates = [g for g in (d.get("gates") or []) if isinstance(g, dict)]
    for g in gates:
        if g.get("check") not in gk or g.get("severity") not in ("hard", "soft"): bad.append(n + " gate not machine-readable: " + json.dumps(g)[:80])
    gated = {str((g.get("config") or {}).get("file")) for g in gates if g.get("check") == "file_exists"}
    for o in d.get("outputs") or []:
        if isinstance(o, dict) and str(o.get("file")) not in gated: warn.append(n + " output without a file_exists gate: " + str(o.get("file")))
    if d.get("forbids") and not any(g.get("check") in ("forbidden_pattern", "forbidden_import") for g in gates): bad.append(n + " forbids listed but no forbidden_pattern/forbidden_import gate")
    for h in d.get("open_holes") or []:
        if isinstance(h, dict):
            covered.add(str(h.get("step_id")) + "|" + str(h.get("hole"))[:60])
            if not h.get("resolution") and not h.get("blocked"): bad.append(n + " open hole neither resolved nor blocked: " + str(h.get("step_id")))
if open_holes and files:
    miss = [h for h in open_holes if not any(h.split("|")[0] == c.split("|")[0] for c in covered)]
    if miss: bad.append("implementability open holes not addressed in any spec: " + ", ".join(m.split("|")[0] for m in miss))
print(("__SPEC_BAD " if bad else "__SPEC_OK ") + " | ".join(bad + ["warn: " + w for w in warn]))`

const QUOTE_CHECK_PY = `import json, os, re, sys
doc_path, p0 = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "p1"
extra = sys.argv[4] if len(sys.argv) > 4 else ""
def norm(t): return re.sub(r"[^a-z0-9]+", " ", str(t).lower()).strip()
try:
    doc = json.load(open(doc_path))
    lit = json.load(open(os.path.join(p0, "lit_results.json"))); papers = lit["papers"] if isinstance(lit, dict) and "papers" in lit else lit
except Exception as ex:
    print("__QUOTE error " + str(ex)[:100]); sys.exit(0)
abstract = {str(x.get("paper_id")): norm(x.get("abstract") or "") for x in papers}
index = {}
ip = os.path.join(p0, "fulltext", "index.json")
if os.path.exists(ip):
    try: index = json.load(open(ip))
    except Exception: index = {}
def hay_for(pid):
    hay = abstract.get(pid, "")
    meta = index.get(pid) if isinstance(index, dict) else None
    fn = (meta or {}).get("file") if isinstance(meta, dict) else None
    if fn:
        fp = fn if os.path.isabs(fn) else os.path.join(p0, "fulltext", os.path.basename(fn))
        if os.path.exists(fp):
            try: hay += " " + norm(open(fp, errors="replace").read())
            except Exception: pass
    return hay
n = v = 0
tag = "__QUOTE"
RELS = {"supports", "conflicts-with", "leaves-open", "depends-on", "evaluated-by"}
rn = rv = 0
if mode == "p1":
    for e in doc.get("closest_adjacent") or []:
        rn += 1; rv += 1 if e.get("relation") in RELS else 0
        q = e.get("evidence_quote")
        if not q: e["quote_verified"] = None; continue
        n += 1; ok = len(norm(q)) > 20 and norm(q) in hay_for(str(e.get("paper_id")))
        e["quote_verified"] = bool(ok); v += 1 if ok else 0
else:
    tag = "__QUOTE3"
    t = doc.get("paper_pointed_threat")
    if isinstance(t, dict) and t.get("evidence_quote"):
        n = 1; hay = hay_for(str(t.get("threat_paper_id") or t.get("paper_id")))
        for side in (os.path.join(p0, "lit_table.md"), extra):
            if side and os.path.exists(side):
                try: hay += " " + norm(open(side, errors="replace").read())
                except Exception: pass
        ok = len(norm(t["evidence_quote"])) > 20 and norm(t["evidence_quote"]) in hay
        t["quote_verified"] = bool(ok); v = 1 if ok else 0
    elif isinstance(t, dict): t["quote_verified"] = None
json.dump(doc, open(doc_path, "w"), indent=2, ensure_ascii=False)
print("%s %d/%d verified" % (tag, v, n) + ("; relations %d/%d valid" % (rv, rn) if mode == "p1" else ""))`

// Output verification (same runner call as the navigator): JSON readable / file non-empty, plus the
// CCF review-output-standards placeholder scan (TBD / [fill] / [TODO] / PLACEHOLDER) reported as a warning.
const VERIFY_PY = `import json, re, sys
bad, warn = [], []
PH = re.compile(r"\\bTBD\\b|\\[fill\\]|\\[TODO\\]|<placeholder>|PLACEHOLDER|\\[insert[^\\]]*\\]")
for p in sys.argv[1:]:
    try:
        txt = open(p, errors="replace").read()
        if p.endswith(".json"): json.loads(txt)
        elif not txt.strip(): raise ValueError("empty file")
    except Exception as ex:
        bad.append(p + ": " + str(ex)[:80]); continue
    b = p.rsplit("/", 1)[-1]
    if b.startswith(("phase4_skeleton", "fill_map", "derive_map")): continue
    hits = sorted(set(m.group(0) for m in PH.finditer(txt)))
    if hits: warn.append(b + " placeholders: " + ",".join(hits)[:80])
print("__OUT_BAD " + " | ".join(bad) if bad else "__OUT_OK" + (" warn: " + " | ".join(warn) if warn else ""))`

// ranking.json against rubric.md / calibration.md: recomputed weighted score, deduction blocks, fatal gates.
const AUDIT_MERGE_PY = `import json, sys
a, b, model, kills = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
k3 = json.load(open(a)); s = json.load(open(b))
v1, v2 = k3.get("verdict"), s.get("verdict")
rt = list(k3.get("revision_targets") or []); seen = {(t.get("scope"), t.get("field")) for t in rt if isinstance(t, dict)}; added = 0
for t in (s.get("revision_targets") or []):
    if isinstance(t, dict) and (t.get("scope"), t.get("field")) not in seen:
        rt.append(dict(t, source="second_auditor")); seen.add((t.get("scope"), t.get("field"))); added += 1
final = v1
if v1 == "abandon" or (kills and v2 == "abandon"): final = "abandon"
elif v1 == "advance" and v2 in ("revise", "abandon"): final = "revise"
if final == "revise" and not rt:
    rt = [{"scope": "tactical", "field": "core_mechanism_reasoning", "source": "second_auditor", "what": "address the second auditor's rationale: " + str(s.get("verdict_rationale"))[:400]}]
k3["verdict"] = final; k3["revision_targets"] = rt
k3["second_opinion"] = {"model": model, "verdict": v2, "verdict_rationale": s.get("verdict_rationale"), "added_targets": added,
                        "rule": ("either auditor may abandon" if kills else "K3 owns the verdict; the second auditor can force revise and add targets, never abandon alone")}
if final != v1: k3["verdict_rationale"] = str(k3.get("verdict_rationale") or "") + " [second auditor " + model + " voted " + str(v2) + " -> " + final + "; see second_opinion]"
json.dump(k3, open(a, "w"), indent=2, ensure_ascii=False)
print("AUDIT_MERGE k3=%s second=%s final=%s added_targets=%d" % (v1, v2, final, added))
`
const RANK_CHECK_PY = `import json, sys
p, runs = sys.argv[1], json.loads(sys.argv[2])
W = {"problem_importance": 12, "novelty": 14, "conceptual_innovation": 12, "method_soundness": 14, "elegance": 8, "feasibility": 8, "experimental_convincibility": 10, "venue_fit": 8, "timeliness": 6, "acceptance_potential": 8}
bad, warn = [], []
try: d = json.load(open(p))
except Exception as ex: print("__RANK_BAD ranking.json unreadable: " + str(ex)[:120]); sys.exit(0)
rk = d.get("ranking") or []
seen = [str(r.get("run")) for r in rk]
if sorted(seen) != sorted(runs): bad.append("runs %s != finished %s" % (seen, runs))
if sorted(r.get("rank") for r in rk if isinstance(r.get("rank"), int)) != list(range(1, len(rk) + 1)): bad.append("rank numbers are not 1..n")
for r in rk:
    n = str(r.get("run")); sc = r.get("scores") or {}
    miss = [k for k in W if not isinstance((sc.get(k) or {}).get("score"), (int, float))]
    if miss: bad.append(n + " scores missing: " + ",".join(miss)); continue
    ded = [str(x.get("dimension", "")).lower().replace(" ", "_") for x in r.get("deductions") or [] if isinstance(x, dict)]
    for k in W:
        v = sc[k]["score"]
        if not (1 <= v <= 5): bad.append(n + " " + k + " score out of 1-5")
        if v <= 3 and not any(k in x or x in k for x in ded): bad.append(n + " " + k + "=%s has no deduction block" % v)
        if not str(sc[k].get("evidence") or "").strip(): warn.append(n + " " + k + " has no quoted evidence")
    ws = sum(sc[k]["score"] * w for k, w in W.items()) / 100.0
    if not isinstance(r.get("weighted_score"), (int, float)) or abs(r["weighted_score"] - ws) > 0.06: bad.append(n + " weighted_score %s != recomputed %.2f" % (r.get("weighted_score"), ws))
    rec = str(r.get("recommendation") or "")
    if rec == "abandon": bad.append(n + " abandon is not available to the ranking seat")
    if sc["novelty"]["score"] <= 2 and int(sc["novelty"].get("confidence") or 0) >= 4 and rec in ("accept-to-develop", "revise"): bad.append(n + " novelty<=2 with high confidence caps at pivot-with-rescue-route")
    if sc["method_soundness"]["score"] <= 2 and rec in ("accept-to-develop", "revise"): bad.append(n + " method_soundness<=2 caps at pivot-with-rescue-route")
    band = "accept-to-develop" if ws >= 4.3 else "revise" if ws >= 3.7 else "pivot-with-rescue-route"
    if rec == "accept-to-develop" and band != "accept-to-develop": bad.append(n + " recommendation accept-to-develop above its band (%.2f)" % ws)
    if not r.get("first_block_to_run"): bad.append(n + " first_block_to_run missing")
    if len([x for x in r.get("panel") or [] if isinstance(x, dict) and x.get("main_negative")]) < 5: bad.append(n + " panel has fewer than the five required expert notes")
    if not str((r.get("synthesis") or {}).get("final_calibrated_stance") or "").strip(): warn.append(n + " synthesis.final_calibrated_stance missing")
print(("__RANK_BAD " if bad else "__RANK_OK ") + " | ".join(bad + ["warn: " + w for w in warn]))`

// ═══════════════════════════════════════════════════════════════ 2. schemas
const RUN_SCHEMA = {
  type: 'object',
  properties: { rc: { type: 'integer' }, out: { type: 'string' } },
  required: ['rc', 'out'],
}
const SEAT_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    written: { type: 'array', items: { type: 'string' } },
    signal: { type: 'string' },
    note: { type: 'string' },
  },
  required: ['ok', 'written'],
}
const INTAKE_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    written: { type: 'array', items: { type: 'string' } },
    direction: { type: 'string' },
    queries: { type: 'array', items: { type: 'string' } },
    note: { type: 'string' },
  },
  required: ['ok', 'written', 'direction', 'queries'],
}

// ═══════════════════════════════════════════════════════════════ 3. runner (shell steps)
const RUNNER_FRAME = `You are the shell runner of the V9 Brain workflow. Your only job is to execute the one command between the COMMAND markers exactly as written, once, in the foreground, with the Bash tool and the timeout stated — no edits, no extra commands, no retries, no interpretation of what it does. All paths in it are absolute, so the working directory does not matter. Never read, write, or create any file yourself.

Return the structured result: rc = the command's exit code; out = its stdout followed by its stderr, VERBATIM — every line, in order, unsummarized, untrimmed (the caller parses it mechanically; a dropped or paraphrased line corrupts the run). If the combined output exceeds 16000 characters keep the LAST 16000 characters.`

// Every command is wrapped in a group with a workflow-owned exit sentinel; rc is parsed from the
// sentinel, never taken from the runner's own report (which normalized or invented markers once).
async function sh(cmd, label, opts = {}) {
  const timeout = opts.timeout || 600000
  const wrapped = '{\n' + cmd + '\n}\necho "__SH_RC=$?"'
  const prompt = RUNNER_FRAME + '\n\nBash timeout: ' + timeout + ' ms\n\n---- COMMAND ----\n' + wrapped + '\n---- END ----\n'
  const r = await agent(prompt, { label: ('sh: ' + label).slice(0, 60), phase: opts.phase || 'Runs', schema: RUN_SCHEMA, model: RUNNER_MODEL, effort: 'low', disallowedTools: DENY.runner })
  if (!r) return { rc: -1, out: '', sentinel: false }
  const raw = String(r.out || '')
  const m = /__SH_RC=(\d+)/.exec(raw)
  const out = raw.replace(/\n?__SH_RC=\d+[ \t]*$/, '')   // the sentinel never reaches the emit parser
  return { rc: m ? Number(m[1]) : Number(r.rc), out, sentinel: !!m }
}

// Long RS jobs (retrieval, full-text, collision) run detached under ROOT/.jobs and are polled;
// the Bash tool caps one call at 600 s and RS budgets up to 600 s for openreview alone.
const isLong = (cmd) => /run\.py['"]? (phase0|phase0_fulltext|phase3_collision) /.test(cmd)
function longJob(rd, cmd) {
  if (/ phase3_collision /.test(cmd)) return { key: base(rd) + '-collision', file: rd + '/phase3_collision/collision_hits.json' }
  if (/ phase0_fulltext /.test(cmd)) return { key: base(rd) + '-fulltext', file: rd + '/phase0/fulltext_cache.json' }
  return { key: base(rd) + '-phase0', file: rd + '/phase0/lit_results.json' }
}
function launchCmd(key, cmd) {
  const log = JOBS + '/' + key + '.log', pid = JOBS + '/' + key + '.pid'
  // a job whose pid is still alive (a retry after an interrupted seat, a resumed run) is reused instead of started a second time onto the same output file
  return 'mkdir -p ' + shq(JOBS) + ' && if [ -e ' + shq(pid) + ' ] && kill -0 "$(cat ' + shq(pid) + ')" 2>/dev/null; then echo LAUNCHED:' + key + '; else rm -f ' + shq(pid) + ' && (setsid nohup bash -c ' + shq(cmd) + ' > ' + shq(log) + ' 2>&1 & echo $! > ' + shq(pid) + ') && sleep 1 && echo LAUNCHED:' + key + '; fi'
}
function waitCmd(key, file, then) {
  const pid = JOBS + '/' + key + '.pid', log = JOBS + '/' + key + '.log'
  return 'st=WAITING; for i in $(seq 1 17); do if kill -0 "$(cat ' + shq(pid) + ' 2>/dev/null)" 2>/dev/null; then sleep 30; continue; fi; ' +
    'sleep 2; if [ -e ' + shq(file) + ' ]; then st=DONE; else st=EXITED; fi; break; done; ' +
    'if [ "$st" = DONE ]; then echo JOB_DONE' + (then ? '; ' + then : '') + '; elif [ "$st" = EXITED ]; then echo JOB_EXITED; tail -c 1500 ' + shq(log) + '; else echo JOB_WAITING; tail -c 800 ' + shq(log) + '; fi'
}
async function launch(key, cmd, label, phaseName) {
  const r = await sh(launchCmd(key, cmd), label + ' launch', { phase: phaseName, timeout: 60000 })
  return r.rc === 0 && r.out.includes('LAUNCHED:' + key)
}
// Polls up to `rounds` × 8.5 min; when the file lands, optionally runs `then` in the same call
// (used to fold the navigator call into the last poll). Returns {done, out}.
async function waitFor(key, file, label, phaseName, then, rounds = 6) {
  let last = ''
  for (let i = 0; i < rounds; i++) {
    const r = await sh(waitCmd(key, file, then), label + ' wait ' + (i + 1), { phase: phaseName })
    if (r.out.includes('JOB_DONE')) return { done: true, out: r.out }
    if (r.out.includes('JOB_EXITED')) return { done: false, out: r.out }
    if (r.rc === -1) return { done: false, out: r.out }
    last = r.out
  }
  return { done: false, out: 'timeout after ' + rounds + ' rounds; last log tail: ' + String(last || '').slice(-800) }
}

// ═══════════════════════════════════════════════════════════════ 4. navigator (run.py next) emit parser
function parseEmit(text) {
  const f = { INPUT: [], RUN: [] }
  let last = null
  for (const raw of String(text || '').split('\n')) {
    const line = raw.replace(/\r$/, '')
    if (!line.trim() || line.trim().startsWith('━')) continue
    const m = /^([A-Z]+)\s*: (.*)$/.exec(line)
    if (m) {
      const label = m[1], body = m[2].trimEnd()
      if (label === 'INPUT' || label === 'RUN') f[label].push(body); else f[label] = body
      last = label
    } else if (last === 'INPUT' || last === 'RUN') {
      f[last].push(line.trim())                       // continuation line (9-space indent in RS; indent-agnostic here)
    } else if (last) {
      f[last] = (f[last] || '') + ' ' + line.trim()
    }
  }
  return { state: f.STATE || '', step: f.STEP || '', kind: f.TYPE || '', prompt: f.PROMPT || '',
           inputs: f.INPUT, output: f.OUTPUT || '', run: f.RUN, notes: f.NOTES || '', raw: String(text || '') }
}
// The navigator always runs LAST in a runner call; take the final emit block of the output.
function lastEmit(out) {
  let idx = -1
  for (const m of String(out || '').matchAll(/^STATE\s*: /gm)) idx = m.index
  return parseEmit(idx >= 0 ? String(out).slice(idx) : '')
}
const isTerminal = (e) => /^(TERMINAL|DONE)/.test(e.state)
function nextCmd(rd) { return ENV + RS + ' next --dir ' + shq(rd) }
function verifyCmd(paths) {
  return 'chk=$(' + PY + ' -c ' + shq(VERIFY_PY) + ' ' + paths.map(shq).join(' ') + '); echo "$chk"'
}
// A quote check (Phase 1 evidence quotes / 3.2 threat quote) that runs between verify and `next`; ends with its heredoc terminator.
const quoteCmd = (doc, rd, mode) => PY + ' - ' + shq(doc) + ' ' + shq(rd + '/phase0') + ' ' + mode + ' ' + shq(rd + '/phase3_collision/collision_hits.json') + ' <<\'PYEOF\'\n' + QUOTE_CHECK_PY + '\nPYEOF\n'
// verify: output paths a seat just wrote — checked in the SAME runner call, before the navigator runs;
// `extra` (a quote check) runs only when the outputs are readable. Placeholder findings come back as e.warn.
async function nextEmit(rd, label, phaseName, verify, extra) {
  const cmd = verify && verify.length ? verifyCmd(verify) + '; case "$chk" in __OUT_OK*) ' + (extra || '') + nextCmd(rd) + ' ;; esac' : nextCmd(rd)
  const r = await sh(cmd, label, { phase: phaseName, timeout: 120000 })
  if (/__OUT_BAD/.test(r.out)) return { bad: (/__OUT_BAD ([^\n]*)/.exec(r.out) || [])[1] || 'unreadable output' }
  const e = lastEmit(r.out)
  if (!e.state) throw new Error('navigator emitted nothing (rc=' + r.rc + '): ' + r.out.slice(-400))
  e.warn = (/__OUT_OK warn: ([^\n]*)/.exec(r.out) || [])[1] || ''
  e.fullOut = r.out
  return e
}
const emitOutputs = (e) => e.output.split(' then ').map((x) => x.trim().split(' ')[0]).filter((x) => x.startsWith('/'))
// Run the emitted bash commands, then the navigator, in ONE runner call. Per-command exit
// codes come back as __RC<i>=<n> markers so a failing step is caught without a second call.
// A failing command stops the chain BEFORE the navigator runs (never advance on a half-mutated
// run dir); validators are the one step allowed to fail (RS: render as-is with a caveat).
const isValidate = (c) => / validate /.test(c)
async function runThenNext(rd, cmds, label, phaseName) {
  const parts = ['ok=1']
  cmds.forEach((c, i) => parts.push('if [ "$ok" = 1 ]; then { ' + c + '\n}; rc=$?; echo "__RC' + i + '=$rc"; ' + (isValidate(c) ? '' : '[ "$rc" -eq 0 ] || ok=0; ') + 'fi'))
  parts.push('if [ "$ok" = 1 ]; then ' + nextCmd(rd) + '; else echo __ABORTED; fi')
  const r = await sh(parts.join('; '), label, { phase: phaseName })
  const rcs = cmds.map(() => -1)
  for (const m of r.out.matchAll(/__RC(\d+)=(\d+)/g)) rcs[Number(m[1])] = Number(m[2])
  return { emit: lastEmit(r.out), rcs, out: r.out }
}
async function prep(c, label, phaseName) {           // one deterministic prep command, exit code checked
  const r = await sh('{ ' + c + '\n}; rc=$?; echo "__RC0=$rc"', label, { phase: phaseName })
  if (!/__RC0=0/.test(r.out)) throw new Error('command failed: ' + c.slice(0, 160) + ' :: ' + r.out.slice(-400))
  return r
}

// ═══════════════════════════════════════════════════════════════ 5. seats (LLM steps)
const TOOLS = {
  readwrite: 'Tools for this seat: Read and Write (Edit only to fix a small mistake in a file you just wrote). Bash, Glob, Grep and the web are disabled for this seat; do not open files the RUN section does not name (the sub-pattern cards the system prompt tells you to pick are the one exception). Write each output ONCE in full.',
  exec: 'Tools for this seat: Read, Write, Edit, and Bash clamped to python3 — run the standard-library scripts you write under the WORKDIR named in the RUN section as `python3 /absolute/path/script.py > /absolute/path/script.out 2>&1` (absolute paths, no cd, no pipes, no other programs; the clamp rejects anything else). Paste the script and its printed output into the report exactly as the system prompt asks; never report estimated numbers as measured. Write the report ONCE in full when it is final; do not build it by repeated edits.',
  repo: 'Tools for this seat: Read, Glob, and Grep over the repository named in the RUN section, plus Write for the named outputs only. No Bash, no web.',
  spec: 'Tools for this seat: Read, Glob, and Grep over the repository named in the RUN section (read-only — you never run anything and never edit repository files), plus Write for files under RUN_DIR/spec/ only. No Bash, no web.',
}
const SEAT_FRAME = `You are one isolated seat of the V9 Brain: a ResearchStudio idea-spark step executed as its own sub-agent with a fresh context. Everything you need is in this message and in the files it names; you have no conversation history and need none.

How to work:
- The SYSTEM PROMPT section below is the complete contract for this step, reproduced verbatim from ResearchStudio. Follow it exactly — its input rules, its output schema, its stop conditions.
- Paths: SKILL_DIR and RUN_DIR are given in the RUN section. Every relative "references/..." path in the system prompt resolves under SKILL_DIR; every "$RUN_DIR/..." path resolves under RUN_DIR. REPOSITORY (when given) is the code repository that substrate.md describes: every relative path substrate.md cites (repos/..., scripts/..., diagnostics/...) resolves under REPOSITORY, never under the workspace. Reference files reproduced verbatim in this message are marked "(inlined)" in the INPUT list — do not Read them again.
- Read every other input file in full with the Read tool. The Read tool returns at most about 25k tokens per call: when a result stops before the file's last line, continue from the next offset until the end — never work from a prefix of a file.
- Write each output artifact in full to its exact path with the Write tool (create parent directories; a JSON output contains valid JSON and nothing else). Never a heredoc, never inline JSON in your reply.
- Finish with the structured result only: ok; written (the paths you wrote); signal (the routing signal NOTES names — e.g. "state=proceed", "verdict=revise" — plus at most 250 words); note (problems, if any). If you cannot complete the step, return ok=false with the reason and write no partial artifact.`

// One row per RS/Brain step: model, tool discipline, verbatim prompt(s), verbatim references inlined.
const SEATS = {
  phase1:    { model: MODEL.opus, effort: 'high', tools: 'readwrite', prompts: ['bottleneck_identify'], refs: ['ccf_lit_evolution'] },
  ideate:    { model: MODEL.opus, effort: 'high', tools: 'readwrite', prompts: ['ideate_select', 'ideate_generate'], refs: ['patterns_overview', 'companion_combos', 'subpatterns_overview'] },
  generate:  { model: MODEL.opus, effort: 'high', tools: 'readwrite', prompts: ['ideate_generate'], refs: ['subpatterns_overview'] },
  cite_fix:  { model: MODEL.opus, effort: 'medium', tools: 'readwrite', prompts: [], refs: ['subpatterns_overview'] },
  coherence: { model: MODEL.opus, fallback: MODEL.glm, effort: 'high', tools: 'exec', prompts: ['coherence_trace'], refs: [] },   // 2.3 = derivation seat (T1 formalize / T2 executed dry-run / T4 claim grading / T5 naive) — the heaviest seat (20–30 tool calls, ~25 min); Astra's quota died here twice on 2026-09-07 → Opus (fresh context ≠ the 2.2 author context), GLM if Opus fails
  audit:     { model: MODEL.k3, second: MODEL.sol, effort: 'high', tools: 'readwrite', prompts: ['critique'], refs: ['anti_patterns', 'ccf_strict_review', 'ccf_blueprint', 'arft_guide'] },   // 3.2 kill seat: K3 owns the verdict; Sol (same prompt, own context, in PARALLEL — no extra hop) writes second_opinion.json; AUDIT_MERGE_PY folds it in (owner 2026-09-07: 'K3 + Sol together; if Sol cannot kill, let it review')
  recheck:   { model: MODEL.k3, effort: 'medium', tools: 'readwrite', prompts: ['refutation_recheck'], refs: [] },
  revise:    { model: MODEL.opus, effort: 'high', tools: 'readwrite', prompts: ['revise'], refs: [] },
  reaudit:   { model: MODEL.k3, effort: 'medium', tools: 'readwrite', prompts: ['falsification_reaudit'], refs: [] },
  fill:      { model: MODEL.opus, effort: 'high', tools: 'readwrite', prompts: ['expand'], refs: ['aris_formula_derivation'] },
  derive:    { model: MODEL.glm, effort: 'low', tools: 'readwrite', prompts: ['derive_plain'], refs: [] },
  impl:      { model: MODEL.glm, effort: 'medium', tools: 'readwrite', prompts: ['implementability_audit'], refs: [] },
  terms:     { model: MODEL.glm, effort: 'low', tools: 'readwrite', prompts: [], refs: ['intent_recognition'] },
  writeup:   { model: MODEL.glm, effort: 'low', tools: 'readwrite', prompts: [], refs: [] },
  tagging:   { model: MODEL.glm, effort: 'low', tools: 'readwrite', prompts: ['tagging_shard'], refs: ['rubric', 'patterns_overview'] },
  intake:    { model: MODEL.glm, effort: 'medium', tools: 'repo',      prompts: ['intake'], refs: ['intake_routing', 'intent_recognition', 'ccf_idea_intake', 'aris_compute_env', 'aris_evidence_precheck'] },
  evidence:  { model: MODEL.opus, fallback: MODEL.glm, effort: 'high', tools: 'readwrite', prompts: ['evidence_plan'], refs: ['ccf_evidence_design', 'ccf_result_templates', 'aris_experiment_plan', 'aris_ablation_planner'] },   // Phase 5 evidence contract: Opus, GLM if Opus fails (owner 2026-09-07)
  rank:      { model: MODEL.opus, effort: 'high', tools: 'readwrite', prompts: ['rank'], refs: ['ccf_idea_rubric', 'ccf_idea_calibration', 'ccf_strict_review', 'ccf_expert_panel', 'ccf_review_output_standards', 'ccf_venue_adapters', 'ccf_lit_evolution'] },
  spec:      { model: MODEL.opus, fallback: MODEL.glm, effort: 'high', tools: 'spec', prompts: ['spec'], refs: ['asi_task_yaml', 'asi_prompt_b1', 'asi_how_scoring'] },   // Phase 6 B1 spec against the code (read-only): Opus, GLM if Opus fails (owner 2026-09-07)
}
// args.seat_models = { <seat>: 'opus' | 'glm' | 'k3' | 'sol' | 'astra' } moves a seat to another routed model without regenerating
// (quota is a per-day fact, not a design fact); the seat's fallback is untouched.
for (const [k, v] of Object.entries(A.seat_models || {})) { if (SEATS[k] && MODEL[v]) SEATS[k].model = MODEL[v]; else throw new Error('args.seat_models: unknown seat or model key ' + k + ':' + v) }
// Route a navigator emit to a seat kind by the PROMPT file it names (order matters).
const ROUTES = [
  [/pattern-summary-rubric\.md/, 'tagging'],
  [/bottleneck_identify\.txt/, 'phase1'],
  [/ideate_select\.txt/, 'ideate'],
  [/ideate_generate\.txt/, 'generate'],
  [/ideation-sub-patterns\/overview\.md/, 'cite_fix'],
  [/coherence_trace\.txt/, 'coherence'],
  [/critique\.txt/, 'audit'],
  [/refutation_recheck\.txt/, 'recheck'],
  [/revise\.txt/, 'revise'],
  [/falsification_reaudit\.txt/, 'reaudit'],
  [/expand\.txt/, 'fill'],
  [/derive_plain\.txt/, 'derive'],
  [/implementability_audit\.txt/, 'impl'],
  [/intent-recognition\.md/, 'terms'],
]
function routeKind(e) {
  for (const [re, kind] of ROUTES) if (re.test(e.prompt)) return kind
  return 'writeup'                                     // emits without PROMPT: do_not_generate.md / phase_3_failed.md
}
// Reference files a seat kind carries inline — their INPUT lines are annotated instead of Read.
const INLINED = {
  'ideation-patterns/overview.md': 'patterns_overview',
  'ideation-patterns/companion-combos.md': 'companion_combos',
  'ideation-sub-patterns/overview.md': 'subpatterns_overview',
  'anti-patterns.md': 'anti_patterns',
  'pattern-summary-rubric.md': 'rubric',
  'intent-recognition.md': 'intent_recognition',
  'intake-routing.md': 'intake_routing',
}
function staticBlock(kind) {
  const s = SEATS[kind]
  const parts = [SEAT_FRAME, '', TOOLS[s.tools]]
  s.prompts.forEach((k, i) => {
    const b = BANK[k]
    const text = k === 'intake' ? b.text.replace('{BRIEF}', '(see the BRIEF section at the end of this message)') : b.text
    const order = s.prompts.length > 1 ? ' ' + (i + 1) + ' of ' + s.prompts.length + (i ? ' (run AFTER the previous one has written its output)' : ' (run FIRST)') : ''
    parts.push('', '═══ SYSTEM PROMPT' + order + ' — ' + b.path + ' (verbatim) ═══', '', text)
  })
  s.refs.forEach((k) => {
    const b = BANK[k]
    parts.push('', '═══ REFERENCE — ' + b.path + ' (verbatim; inlined, do not Read) ═══', '', b.text)
  })
  return parts.join('\n')
}
const STATIC = {}
for (const kind of Object.keys(SEATS)) STATIC[kind] = staticBlock(kind)   // built once: identical prefix across runs → prompt cache

function annotateInput(kind, line) {
  const s = SEATS[kind]
  for (const [rel, key] of Object.entries(INLINED)) {
    if (line.includes('/references/' + rel) && s.refs.includes(key)) return line + '  (inlined above — do not Read)'
  }
  return line
}
function seatPrompt(kind, dyn) {
  const lines = [STATIC[kind], '', '═══ RUN ═══', 'SKILL_DIR: ' + SKILL_DIR]
  if (dyn.rd) lines.push('RUN_DIR: ' + dyn.rd)
  if (dyn.repo) lines.push('REPOSITORY: ' + dyn.repo)
  if (dyn.workdir) lines.push('WORKDIR (scripts you run live here; create it): ' + dyn.workdir)
  lines.push('RUN: ' + (dyn.run || '-') + ' | STEP: ' + (dyn.step || kind))
  lines.push('', 'INPUT (files to Read unless marked inlined; literal lines are context):')
  for (const l of dyn.inputs || []) lines.push('  - ' + annotateInput(kind, l))
  lines.push('', 'OUTPUT: ' + (dyn.output || '-'))
  if (dyn.notes) lines.push('', 'NOTES: ' + dyn.notes)
  if (dyn.extra) lines.push('', dyn.extra)
  return lines.join('\n')
}
// One attempt on the seat's model, one retry in a fresh context, then the run reports failure. A seat that
// declares `fallback` takes its retry on that model instead (Astra unavailable → Opus); `forceModel` starts the
// seat on a given model (the verify→retry path forces the fallback when the primary's output was unreadable).
// The result carries `model` (which model produced it) and `fell_back` for the run record.
async function seat(kind, dyn, label, phaseName, schema, forceModel) {
  const s = SEATS[kind]
  const primary = forceModel || s.model
  const opts = { label: label.slice(0, 60), phase: phaseName, schema: schema || SEAT_SCHEMA, model: primary, effort: s.effort, disallowedTools: DENY[s.tools] }
  if (CLAMP[s.tools]) opts.bashCommandClamp = CLAMP[s.tools]
  const prompt = seatPrompt(kind, dyn)
  let r = await agent(prompt, opts)
  let used = primary
  if (!r || !r.ok) {
    const retryModel = (s.fallback && s.fallback !== primary) ? s.fallback : primary
    log((dyn.run || '-') + ' ' + kind + ': first attempt on ' + primary + ' failed (' + ((r && r.note) || 'no result') + ') — retrying once' + (retryModel !== primary ? ' on the fallback model ' + retryModel : ''))
    r = await agent(prompt, Object.assign({}, opts, { model: retryModel }))
    used = retryModel
  }
  if (r && typeof r === 'object') { r.model = used; r.fell_back = used !== s.model }
  return r
}

// Brain-side context RS never had: the frozen goal, the substrate, the measured anomalies.
let DIRECTION = ''
function brainContext(kind, runId) {
  const c = []
  const turn = runId ? RUN_IDS.indexOf(runId) : -1
  if (kind === 'phase1') {
    c.push('EVIDENCE QUOTES (Brain addition, checked mechanically afterwards): for every closest_adjacent entry add the field "evidence_quote" — one verbatim sentence (at most 40 words) copied exactly from that paper\'s full text (phase0/fulltext/<file>.md, see index.json) or from its abstract in lit_results.json, the sentence the residue rests on. Copy, never paraphrase; a residue whose quote cannot be found is downgraded to abstract-level confidence.')
    c.push('RELATION (CCF relation map, inlined below; ARFT B.5 citation decorrelation): every closest_adjacent entry also carries "relation" — exactly one of supports | conflicts-with | leaves-open | depends-on | evaluated-by, the edge between that paper and the bottleneck you state — and "relation_evidence", one line naming what in the paper carries that edge. A residue whose only edge is leaves-open is an absence claim, not evidence for the bottleneck; say so in the residue. Prefer bottlenecks supported by at least two independent entries.')
    c.push('USER QUERY (the research direction): ' + (DIRECTION || '(see ' + SHARED + '/queries.json)'))
    c.push('INTAKE (the ten intake fields, already filled from the repository): ' + SHARED + '/intake.json')
    c.push('SUBSTRATE (measured facts about the repository — task, metric, protocol, operators, baselines, compute): ' + SHARED + '/substrate.md')
    if (BRIEF.anomalies) c.push('MEASURED ANOMALIES (a residue source coequal with the literature: every entry is an experimental fact about this repository that no retrieved paper explains — treat each as a candidate gap with the same standing as a paper residue): ' + BRIEF.anomalies)
    if (NEGATIVE_ANCHORS.length) c.push('NEGATIVE ANCHORS (Brain addition — measured failures on this repository, evidence with the same standing as the anomalies): read every failure card listed here: ' + NEGATIVE_ANCHORS.join(', ') + '. Each card records a mechanism that was built and run on this repository and died — level L2 = the spec left a scientific decision open, L3 = the negative-control arm matched the candidate (mechanism attribution dead), L4 = a premise was refuted — with its ARFT codes, anchors (numbers / log lines / files) and the plan\'s own failure_interpretation. Fold each failure_interpretation into the residue analysis as a measured fact; a bottleneck whose only support was a dead mechanism\'s promise is downgraded; never re-propose a dead mechanism as a gap closure.')
  }
  if (kind === 'ideate' || kind === 'generate') {
    c.push('SUBSTRATE (the repository the idea must run in): ' + SHARED + '/substrate.md — the PREMISES ledger of core_mechanism_reasoning must carry one line starting "substrate:" naming the operator/module from substrate.md the mechanism modifies and the structure it assumes exists there; compute_budget is written against the compute envelope in substrate.md.')
    if (NEGATIVE_ANCHORS.length) c.push('NEGATIVE ANCHORS (hard, unlike the soft cross-run dedup): the failure cards at ' + NEGATIVE_ANCHORS.join(', ') + ' record mechanisms that were built and run on this repository and died, with the anchored reason. A candidate whose core mechanism is one of these, or a variant that does not address the card\'s recorded failure reason (its anchors and failure_interpretation), is disqualified before selection; a candidate that turns a card\'s failure_interpretation into its anchor gap is preferred. State in composition_note which cards you checked and why the chosen mechanism is not one of them.')
    if (kind === 'ideate' && K > 1 && turn >= 0) c.push('RUN DIVERSITY (this is run ' + (turn + 1) + ' of ' + K + ', all runs ideate in parallel from the same Phase 1): rank the gaps by promise under the selection rules, then take the gap at rank ' + (turn + 1) + ' as your anchor (run 1 takes the top gap, run 2 the second, and so on); if that gap is disqualified by the selection rules, take the next one down. State the rank you took in composition_note. This replaces the soft cross-run dedup: the K candidates must start from different anchor gaps.')
  }
  if (kind === 'audit') {
    c.push('SCOPE CHECK (Brain addition, judged like a hard floor): besides the five checks, test the candidate against the FROZEN GOAL below — its contribution type, its "out of scope" list, its protocol and its baselines. A candidate that is out of scope (for example a training-free method, a mechanism/audit/benchmark paper, a change to the protocol or metric) is verdict=abandon with the reason recorded under verdict_rationale as "scope_check"; a candidate that drifts partly is a revision_target with scope=tactical naming the drift.')
    c.push('THREAT QUOTE (Brain addition, checked mechanically afterwards): paper_pointed_threat carries two extra fields — "evidence_quote": one verbatim sentence (at most 40 words) copied exactly from the threat paper\'s abstract as it appears in lit_table.md or in the collision hits, or from its full text under phase0/fulltext/ — the sentence the subsumption argument rests on (for a title-only hit with no abstract, the exact title); and "quote_source": "lit_table" | "collision_hits" | "fulltext". Copy, never paraphrase, never from memory; when no threat is found leave both null.')
    c.push('REVIEW DISCIPLINE (CCF strict-idea-review and problem-method blueprint, inlined below): the No-Filler Rule applies to verdict_rationale and to every revision_target — each material criticism names the exact claim or mechanism under review, the closest prior art or missing evidence, why a strict reviewer would deduct, the concrete repair or pivot, and what would change the verdict; generic phrases without those anchors are not allowed. Add to the output JSON the field "ccf_coherence_filter" — the six Coherence Filter checks of the blueprint as {"check": "<the check>", "pass": true|false, "evidence": "<one line>"} — and "fatal_idea_risks": the Fatal Idea Risks of the blueprint that apply, each with its anchor (empty list when none). These fields inform verdict_rationale; they do not replace the five RS checks or the two-layer verdict.')
    if (NEGATIVE_ANCHORS.length) c.push('NEGATIVE ANCHORS (Brain addition, judged like a hard floor): the failure cards at ' + NEGATIVE_ANCHORS.join(', ') + ' record mechanisms that were built and run on this repository and died. A candidate that re-proposes a carded mechanism, or a variant that does not address the card\'s recorded failure reason, is verdict=abandon with the reason recorded under verdict_rationale as "negative_anchor:<card>"; a candidate that addresses the recorded reason must say how, and that sentence is a revision_target if it is missing.')
    c.push('ARFT CODES (the ARFT operational guide is inlined below): give every blocking finding and every revision_target the field "arft_code" — the failure pattern it instantiates when one applies (ideation-stage codes A.1–A.6, cross-stage X.2 goal drift / X.5 teleological reasoning / X.6 right-for-the-wrong-reason; apply the §3 discrimination rules and the §4 Do-NOT-label list; infrastructure is never a code), null when none fits. The codes travel unchanged into the Worker session\'s failure cards, so precision beats coverage.')
  }
  if (kind === 'revise') {
    c.push('SCOPE (Brain addition): every patch must keep the candidate inside the FROZEN GOAL below — contribution type, protocol, metric, baselines. A revision that would move it out of scope is not applied; say so in the patch entry instead.')
  }
  if (kind === 'coherence') {
    c.push('SUBSTRATE: ' + SHARED + '/substrate.md — additionally check the "substrate:" premise against it: if the named operator or structure does not exist as described, that is a blocking finding (reading_robust).')
    c.push('SIZE DISCIPLINE (Brain addition): the report stays under 40 KB — the executed script and its stdout appear once, verbatim, and nothing else large; write it once when it is final.')
  }
  if (kind === 'spec') {
    c.push('EVIDENCE PLAN: ' + (runId ? ROOT + '/' + runId + '/phase5/evidence_plan.json' : '') + ' — one spec/B<k>.json per block, in run_order.')
  }
  if (kind === 'fill') {
    c.push('SUBSTRATE: ' + SHARED + '/substrate.md — feasibility_validation is judged against this compute envelope and these existing baselines, not against the RS factory default.')
    c.push('KEY EQUATIONS DISCIPLINE (ARIS formula-derivation, inlined below): for every key_equations entry the description states the invariant object the equation is written over and the assumptions it uses, and labels the step as identity / proposition / approximation / interpretation; the linked method_flow step\'s why_this_step names the condition under which the equation stops holding (its failure condition). Never hide a gap with "clearly" or "similarly"; an equation whose assumptions cannot be stated is labelled approximation, not proposition. This is the derivation line the Phase 6 spec copies into tests_premise.')
  }
  if (BRIEF.goal && ['phase1', 'ideate', 'generate', 'audit', 'revise', 'fill', 'evidence', 'spec', 'rank'].includes(kind)) {
    c.push('FROZEN GOAL (verbatim; binding on contribution type, protocol, baselines and keep rule):\n' + BRIEF.goal)
  }
  return c
}

// ═══════════════════════════════════════════════════════════════ 6. shared stage: Phase -1 intake + Phase 0
async function probeShared() {
  const r = await sh('mkdir -p ' + shq(P0) + ' ' + shq(JOBS) + '; cd ' + shq(SHARED) + '; for f in queries.json intake.json substrate.md phase0/lit_results.json phase0/lit_table.md phase0/fulltext_cache.json; do [ -e "$f" ] && echo "HAS $f"; done; for j in phase0 fulltext; do [ -e "../.jobs/$j.pid" ] && kill -0 "$(cat ../.jobs/$j.pid)" 2>/dev/null && echo "ALIVE $j"; done; ls phase0/lit_rows_shard*.md 2>/dev/null | sed "s/^/SHARD /"; [ -e queries.json ] && { echo "QUERIES_JSON_BEGIN"; cat queries.json; echo; echo "QUERIES_JSON_END"; }; true', 'probe shared', { phase: 'Phase 0', timeout: 60000 })
  const has = new Set([...r.out.matchAll(/^HAS (\S+)/gm)].map((m) => m[1]))
  const alive = new Set([...r.out.matchAll(/^ALIVE (\S+)/gm)].map((m) => m[1]))
  const shards = [...r.out.matchAll(/^SHARD (\S+)/gm)].map((m) => m[1])
  let queries = null
  const q = /QUERIES_JSON_BEGIN\n([\s\S]*?)\nQUERIES_JSON_END/.exec(r.out)
  if (q) { try { queries = JSON.parse(q[1]) } catch (err) { queries = null } }
  return { has, alive, shards, queries }
}

async function intakeStage(st) {
  if (st.has.has('queries.json') && st.queries && st.queries.direction) { DIRECTION = st.queries.direction; return st.queries }
  if (!BRIEF.repo) throw new Error('no _shared/queries.json and no args.repo — nothing to intake')
  phase('Intake')
  const brief = ['- repo: ' + BRIEF.repo, '- dataset: ' + BRIEF.dataset, '- venue: ' + BRIEF.venue, '- goal: ' + BRIEF.goal]
  if (BRIEF.anomalies) brief.push('', '### Measured anomalies (ground truth for `limitation`) — read this file in full: ' + BRIEF.anomalies)
  const r = await seat('intake', {
    run: '_shared', step: 'Phase -1 — repository intake', repo: BRIEF.repo,
    inputs: ['the repository itself (README, training entrypoint, model definition, eval script, configs, results tables)'].concat(BRIEF.anomalies ? [BRIEF.anomalies + '  (measured anomalies)'] : []),
    output: SHARED + '/intake.json then ' + SHARED + '/substrate.md then ' + SHARED + '/queries.json',
    notes: 'Write all three artifacts. Return direction (the intake.direction sentence) and queries (the 4-6 Phase 0 queries, one of them the ESCAPE-MECHANISM query) in the structured result as well.',
    extra: '═══ BRIEF (the {BRIEF} the intake prompt refers to) ═══\n' + brief.join('\n'),
  }, '_shared: Phase -1 intake', 'Intake', INTAKE_SCHEMA)
  if (!r || !r.ok || !r.direction || !(r.queries || []).length) throw new Error('intake seat failed: ' + ((r && r.note) || 'no result'))
  DIRECTION = r.direction
  return { direction: r.direction, queries: r.queries }
}

async function tagShards(p0, runName, phaseName) {
  // Contiguous slices of ≤15 papers (as many shards as that takes), tagged in parallel; then a deterministic CLEAN step drops malformed /
  // unknown / duplicate rows and lists the papers still missing; ONE repair seat re-tags only those; RS's validating merger assembles.
  // (The 2026-09-07 t1 run capped shards at 3 → 43 papers each; the GLM seat silently skipped four off-topic papers twice → no lit_table.)
  const split = PY + ' - ' + shq(p0) + ' <<\'PYEOF\'\nimport json, math, sys\np = sys.argv[1]\ndoc = json.load(open(p + "/lit_results.json"))\npapers = doc["papers"] if isinstance(doc, dict) and "papers" in doc else doc\nn = max(1, math.ceil(len(papers) / 15))\nsize = math.ceil(len(papers) / n)\nfor i in range(n):\n    json.dump(papers[i * size:(i + 1) * size], open(p + "/lit_slice%d.json" % i, "w"), indent=1, ensure_ascii=False)\nprint("SHARDS", n, len(papers))\nPYEOF'
  const r = await sh(split, runName + ' split lit_results', { phase: phaseName, timeout: 60000 })
  const m = /SHARDS (\d+) (\d+)/.exec(r.out)
  if (!m) throw new Error('could not slice lit_results.json: ' + r.out.slice(-300))
  const n = Number(m[1])
  log(runName + ': tagging ' + m[2] + ' papers in ' + n + ' shard(s)')
  const NOTES = 'Rows only, 9 cells each, one row per paper of the slice, no header, no fence. EVERY paper of the slice gets a row — an off-topic paper is tagged outside_taxonomy, never skipped; the merger counts rows against lit_results.json.'
  const results = await parallel(Array.from({ length: n }, (_, i) => () => seat('tagging', {
    run: runName, step: 'Phase 0 pattern tagging — shard ' + i + ' of ' + n,
    inputs: [p0 + '/lit_slice' + i + '.json  (the papers of this shard, in order)'],
    output: p0 + '/lit_rows_shard' + i + '.md',
    notes: NOTES,
  }, runName + ': tagging shard ' + i, phaseName)))
  const bad = results.map((x, i) => (x && x.ok ? null : i)).filter((x) => x !== null)
  if (bad.length) log(runName + ': tagging shard(s) ' + bad.join(',') + ' returned no result — their papers go to the repair seat')
  // CLEAN: keep only well-formed rows of known, unseen paper_ids; write the still-missing papers as the repair slice.
  const clean = PY + ' - ' + shq(p0) + ' ' + n + ' <<\'PYEOF\'\nimport json, sys\np, n = sys.argv[1], int(sys.argv[2])\ndoc = json.load(open(p + "/lit_results.json"))\npapers = doc["papers"] if isinstance(doc, dict) and "papers" in doc else doc\nwant = {str(x.get("paper_id") or x.get("id") or "") for x in papers}\nseen, dropped = set(), 0\nfor i in range(n):\n    fn = p + "/lit_rows_shard%d.md" % i\n    try: lines = open(fn, encoding="utf-8").read().splitlines()\n    except FileNotFoundError: lines = []\n    keep = []\n    for ln in lines:\n        s = ln.strip()\n        if not s or s.startswith("|---") or "paper_id | year_month" in s: continue\n        cells = [c.strip() for c in s.strip("|").split("|")]\n        if len(cells) != 9 or cells[0] not in want or cells[0] in seen: dropped += 1; continue\n        seen.add(cells[0]); keep.append(s)\n    open(fn, "w", encoding="utf-8").write("\\n".join(keep) + ("\\n" if keep else ""))\nmissing = [x for x in papers if str(x.get("paper_id") or x.get("id") or "") not in seen]\njson.dump(missing, open(p + "/lit_slice_repair.json", "w"), indent=1, ensure_ascii=False)\nprint("MISSING", len(missing), "dropped", dropped)\nPYEOF'
  const c = await sh(clean, runName + ' clean shards', { phase: phaseName, timeout: 60000 })
  const mm = /MISSING (\d+)/.exec(c.out)
  if (!mm) throw new Error('shard clean step failed: ' + c.out.slice(-300))
  const missing = Number(mm[1])
  let shardFiles = Array.from({ length: n }, (_, i) => p0 + '/lit_rows_shard' + i + '.md')
  if (missing > 0) {
    log(runName + ': ' + missing + ' paper(s) without a valid row — one repair seat re-tags exactly those')
    const rr = await seat('tagging', {
      run: runName, step: 'Phase 0 pattern tagging — repair (' + missing + ' missing papers)',
      inputs: [p0 + '/lit_slice_repair.json  (only the papers whose rows were missing, malformed or duplicated — every one of them needs a row)'],
      output: p0 + '/lit_rows_shard_repair.md',
      notes: NOTES,
    }, runName + ': tagging repair', phaseName)
    if (!rr || !rr.ok) throw new Error('tagging repair seat failed: ' + ((rr && rr.note) || 'no result'))
    shardFiles = shardFiles.concat([p0 + '/lit_rows_shard_repair.md'])
  }
  const shards = shardFiles.map(shq).join(' ')
  const merge = await sh(RS + ' lit_table_merge --out ' + shq(p0) + ' --shards ' + shards + '; echo "__RC0=$?"', runName + ' lit_table_merge', { phase: phaseName, timeout: 120000 })
  if (!/__RC0=0/.test(merge.out)) {
    await sh('cd ' + shq(p0) + ' && for f in lit_rows_shard*.md; do mv "$f" "$f.bad"; done; true', runName + ' discard shards', { phase: phaseName, timeout: 60000 })
    throw new Error('lit_table_merge rejected the shards (renamed *.bad): ' + merge.out.slice(-500))
  }
}

async function phase0Stage(queries) {
  phase('Phase 0')
  let st = await probeShared()
  if (!st.has.has('phase0/lit_results.json')) {
    if (!st.alive.has('phase0')) {
      const cmd = ENV + RS + ' phase0 --query ' + shq(queries.direction) + ' --queries ' + shq((queries.queries || []).join('|')) + ' --out ' + shq(P0 + '/')
      if (!(await launch('phase0', cmd, 'phase0 retrieval', 'Phase 0'))) throw new Error('could not launch phase0 retrieval')
    }
    const w = await waitFor('phase0', P0 + '/lit_results.json', 'phase0 retrieval', 'Phase 0')
    if (!w.done) throw new Error('phase0 retrieval produced no lit_results.json — see ' + JOBS + '/phase0.log: ' + w.out.slice(-600))
    st = await probeShared()
  }
  let rounds = 0
  while (!st.has.has('phase0/lit_table.md')) {
    if (rounds++ >= 2) throw new Error('lit_table.md still missing after 2 tagging rounds')
    try { await tagShards(P0, '_shared', 'Phase 0') } catch (err) { log('tagging round ' + rounds + ' failed: ' + String(err.message || err).slice(0, 200)) }
    st = await probeShared()
  }
  if (!st.has.has('phase0/fulltext_cache.json')) {
    if (USER_REFS.length) {
      const cmds = USER_REFS.map((u) => RS + ' add_user_ref --out ' + shq(P0 + '/') + ' --title ' + shq(u.title || '') + (u.id ? ' --id ' + shq(u.id) : '') + (u.raw_match ? ' --raw-match ' + shq(u.raw_match) : ''))
      await sh(cmds.join(' && '), 'add_user_ref', { phase: 'Phase 0', timeout: 120000 })
    }
    if (!st.alive.has('fulltext')) {
      if (!(await launch('fulltext', RS + ' phase0_fulltext --out ' + shq(P0 + '/'), 'fulltext fetch', 'Phase 0'))) throw new Error('could not launch phase0_fulltext')
    }
    const w = await waitFor('fulltext', P0 + '/fulltext_cache.json', 'fulltext fetch', 'Phase 0')
    if (!w.done) throw new Error('phase0_fulltext produced no fulltext_cache.json — see ' + JOBS + '/fulltext.log: ' + w.out.slice(-600))
  }
  // circuit breaker: a connector that timed out in Phase 0 is skipped by every later retrieval of this session
  const brk = await sh('grep -cE "^\\s*\\[dblp[^]]*\\] timed out" ' + shq(JOBS + '/phase0.log') + ' 2>/dev/null; true', 'dblp breaker probe', { phase: 'Phase 0', timeout: 30000 })
  if (/^[1-9]/.test(brk.out.trim())) { SKIP_ENV = 'IDEASPARK_SKIP_SOURCES=dblp '; log('dblp timed out in Phase 0 — skipped for every later retrieval (session circuit breaker)') }
  // spawn: every run starts from the same Phase 0 (RS convention: one run = one dir with its own phase0/)
  const manifest = 'cd ' + shq(P0) + ' && sha256sum lit_results.json lit_table.md fulltext_cache.json | sha256sum | cut -c1-16 > .manifest && cd - >/dev/null'
  const spawn = RUN_IDS.map((id) => { const d = shq(ROOT + '/' + id + '/phase0'); return '{ if [ -d ' + d + ' ] && cmp -s ' + shq(P0 + '/.manifest') + ' ' + d + '/.manifest; then :; else rm -rf ' + d + ' && mkdir -p ' + shq(ROOT + '/' + id) + ' && cp -r ' + shq(P0) + ' ' + d + '; fi; }' }).join(' && ')
  const r = await sh(manifest + ' && ' + spawn + ' && echo SPAWNED', 'spawn ' + RUN_IDS.join(','), { phase: 'Phase 0', timeout: 120000 })
  if (!r.out.includes('SPAWNED')) throw new Error('spawn failed: ' + r.out.slice(-400))
}

// ═══════════════════════════════════════════════════════════════ 7. one run = the RS navigator loop + cross-run policy
// r2..rK reuse r1's Phase 1 (same corpus, same direction); 2.1+2.2 is serialized across runs so
// RS's own CROSS-RUN DEDUP line (sibling scan inside `next`) sees each earlier candidate.
let phase1Resolve
const phase1Ready = new Promise((res) => { phase1Resolve = res })
// 2.1+2.2 turns are taken in run order: r(i) generates only after r(i-1) has landed (or given up) its
// candidate, so the dedup line each later run receives is deterministic — r1, then r2, then r3.
const ideateTurn = RUN_IDS.map(() => { let res; const p = new Promise((r) => { res = r }); return { p, res } })

async function driveRun(id) {
  const rd = ROOT + '/' + id
  const st = { id, state: 'running', steps: 0, seats: [], fallbacks: [], audit_merge: null, note: '', validate_rc: null, validate_repairs: 0, validate_note: '', regression_rc: null, placeholders: [], cards: [], evidence_plan: null, quote_check: null, quote_check3: null, plan_check: null, spec: null, spec_check: null }
  const lbl = (s) => id + ': ' + s
  const turn = RUN_IDS.indexOf(id)
  let phase1Marked = id !== 'r1'
  const markPhase1 = (ok) => { if (!phase1Marked) { phase1Marked = true; phase1Resolve(ok) } }

  async function runSeat(em, k, forceModel) {
    const long = em.run.filter(isLong), short = em.run.filter((c) => !isLong(c))
    for (const c of short) await prep(c, lbl('prep ' + base((c.split(' ')[2] || '').replace(/['"]/g, ''))), 'Runs')   // phase2_prepare, revise_brief, falsification_view
    // 3.1 collision rides along with 2.3 (background, deterministic); for the signature_terms
    // step the seat must fill the terms first, so the launch waits until after it.
    const job = long.length ? longJob(rd, long[0]) : null
    if (job && k !== 'terms' && !(await launch(job.key, SKIP_ENV + long[0], lbl('collision'), 'Runs'))) throw new Error('could not launch collision')
    const inputs = em.inputs.filter((l) => l !== 'the user query + intake context')
    let notes = em.notes
    if (short.length) notes = notes.replace(/Run the RUN command first \([^)]*\)(, then the sub-agent)?\.\s*/, 'The deterministic RUN command has already been executed by the workflow (its output file is listed under INPUT). ')
    if (job && k !== 'terms') notes = notes.replace(/TWO independent actions: \(1\).*?\(2\) run the 2\.3 sub-agent\.\s*/s, 'The 3.1 collision retrieval has already been launched in the background by the workflow — do only the 2.3 work. ')
    const dyn = { rd, run: id, repo: BRIEF.repo, step: em.step, inputs: inputs.concat(brainContext(k, id)), output: em.output, notes }
    if (k === 'coherence') {
      dyn.workdir = rd + '/phase2_coherence'
      await prep('rm -f ' + shq(rd + '/phase2_coherence/blocking_findings.json') + ' ' + shq(rd + '/phase2_coherence/refined_candidate.json'), lbl('prep 2.3 (clear stale side outputs)'), 'Runs')   // a previous, unfinished attempt must not hand 3.2 stale findings
    }
    let r
    if (k === 'audit' && SEATS.audit.second && !forceModel) {
      // The second auditor runs the SAME audit (prompt, refs, inputs) in parallel on its own model and context, into its own file; the
      // deterministic merge then folds its vote into K3's file: advance + a second challenge → revise (targets appended); K3's abandon stands.
      const out2 = rd + '/phase3_critique/second_opinion.json'
      const dyn2 = Object.assign({}, dyn, { output: out2, notes: (dyn.notes || '') + ' SECOND AUDITOR (Brain addition): you are the second, independent auditor of this candidate — same five checks, same output JSON, written to ' + out2 + ' and nowhere else; the first auditor\'s verdict is not shown to you and the workflow merges the two afterwards.' })
      const [r1, r2] = await parallel([() => seat(k, dyn, lbl(em.step), 'Runs'), () => seat(k, dyn2, lbl(em.step + ' (second auditor)'), 'Runs', undefined, SEATS.audit.second)])
      r = r1
      st.seats.push({ kind: 'audit_second', step: em.step, ok: !!(r2 && r2.ok), signal: (r2 && r2.signal) || '', model: (r2 && r2.model) || SEATS.audit.second })
      if (r && r.ok && r2 && r2.ok) {
        const mg = await sh(PY + ' - ' + shq(em.output) + ' ' + shq(out2) + ' ' + shq(SEATS.audit.second) + ' ' + (SECOND_KILLS ? 1 : 0) + ' <<\'PYEOF\'\n' + AUDIT_MERGE_PY + '\nPYEOF', lbl('audit merge'), { phase: 'Runs', timeout: 60000 })
        const line = /AUDIT_MERGE [^\n]*/.exec(mg.out); st.audit_merge = line ? line[0] : 'merge failed: ' + mg.out.slice(-200)
        log(id + ' 3.2 ' + st.audit_merge)
      } else if (r && r.ok) { st.audit_merge = 'second auditor returned no result — K3 verdict stands alone'; log(id + ' 3.2 ' + st.audit_merge) }
    } else r = await seat(k, dyn, lbl(em.step), 'Runs', undefined, forceModel)
    st.seats.push({ kind: k, step: em.step, ok: !!(r && r.ok), signal: (r && r.signal) || '', model: (r && r.model) || forceModel || SEATS[k].model })
    if (r && r.fell_back) st.fallbacks.push({ kind: k, step: em.step, from: SEATS[k].model, to: r.model })
    if (!r || !r.ok) throw new Error(k + ' seat failed twice: ' + ((r && r.note) || 'no result'))
    lastSeat = { em, k, outputs: emitOutputs(em), retried: false, phase1Ok: k === 'phase1' && !/do_not_generate/.test(r.signal || '') }   // Phase 1 is shared with r2..rK only once its outputs verified readable
    if (job) {
      if (k === 'terms' && !(await launch(job.key, SKIP_ENV + long[0], lbl('collision'), 'Runs'))) throw new Error('could not launch collision')
      const w = await waitFor(job.key, job.file, lbl('collision'), 'Runs')
      if (!w.done) throw new Error('collision retrieval produced no hits file: ' + w.out.slice(-500))
    }
  }

  // RS validate rule: on `fail`, fix ONLY the named contract, re-validate, cap 2 repairs, then render as-is.
  const validateTarget = (out) => {
    const line = out.split('\n').find((l) => /✗/.test(l)) || ''
    if (/\[(expansion_completeness|kill_switch_integrity)\]/.test(line)) return 'fill'
    if (/\[implementability_(completeness|readability)\]/.test(line)) return 'impl'
    return null                                       // citation-guarded fields are never edited to silence a validator
  }
  const rec = (kind, step, r) => {
    st.seats.push({ kind, step, ok: !!(r && r.ok), signal: (r && r.signal) || '', model: (r && r.model) || SEATS[kind].model })
    if (r && r.fell_back) st.fallbacks.push({ kind, step, from: SEATS[kind].model, to: r.model })
  }
  async function repairSeat(kind, out) {
    const file = kind === 'fill' ? rd + '/phase4/phase4_expansion.json' : rd + '/phase4/phase4_implementability.json'
    const findings = out.split('\n').filter((l) => /[✗⚠]/.test(l)).join('\n').slice(0, 3000)
    const inputs = [file + '  (the file to repair, in place)', rd + '/phase4/method_view.json  (method-only slice)']
    if (kind === 'fill') inputs.push(rd + '/phase3_revise/final_candidate.json  (upstream kill-switch values when the revise path ran; if it does not exist use the next file)', rd + '/phase2_generate/phase2_generate_output.json  (upstream kill-switch values)')
    const r = await seat(kind, { rd, run: id, repo: BRIEF.repo, step: 'validate repair — ' + kind, inputs: inputs.concat(brainContext(kind, id)), output: file,
      notes: 'VALIDATE REPAIR (ResearchStudio rule: fix ONLY the named contract; the workflow re-validates; cap 2). The validator findings below name the exact missing or malformed sections of the OUTPUT file. Read it whole, repair exactly those items, keep every other field byte-identical, and write the file whole. The kill-switch fields falsification_prediction and compute_budget may only be restored to their upstream value — never rewritten; citation-guarded fields are never edited. FINDINGS:\n' + findings }, lbl('validate repair ' + kind), 'Runs')
    rec(kind, 'validate repair', r)
    if (!r || !r.ok) throw new Error('validate repair seat failed: ' + ((r && r.note) || 'no result'))
  }

  let e = null
  let pending = null                                  // bash commands to run before the next navigator call
  let lastSeat = null                                 // the seat whose outputs the next navigator call verifies
  try {
    for (let i = 0; i < MAX_STEPS; i++) {
      st.steps = i + 1
      if (!pending && !e && lastSeat) {               // seat just ran: verify its outputs (+ quote check) in the same call as `next`; one fresh retry if unreadable
        const seatDone = lastSeat; lastSeat = null
        const extra = seatDone.k === 'phase1' && id === 'r1' ? quoteCmd(seatDone.outputs[0], rd, 'p1') : seatDone.k === 'audit' && seatDone.outputs[0] ? quoteCmd(seatDone.outputs[0], rd, 'p3') : ''
        const ne = await nextEmit(rd, lbl('verify → next'), 'Runs', seatDone.outputs, extra)
        if (ne.bad) {
          if (seatDone.retried) throw new Error(seatDone.k + ' output still unreadable after retry: ' + ne.bad)
          log(id + ' ' + seatDone.k + ': output unreadable (' + ne.bad + ') — fresh retry' + (SEATS[seatDone.k].fallback ? ' on ' + SEATS[seatDone.k].fallback : ''))
          await runSeat(seatDone.em, seatDone.k, SEATS[seatDone.k].fallback)
          lastSeat.retried = true
          continue
        }
        if (ne.warn) st.placeholders.push(seatDone.k + ': ' + ne.warn.slice(0, 160))
        if (seatDone.phase1Ok) markPhase1(true)
        const qm = /__QUOTE ([^\n]*)/.exec(ne.fullOut || ''); if (qm) st.quote_check = qm[1]
        const qm3 = /__QUOTE3 ([^\n]*)/.exec(ne.fullOut || ''); if (qm3) st.quote_check3 = qm3[1]
        e = ne
      }
      if (pending && pending.some(isValidate)) {      // validators run alone first so a fail can be repaired before rendering
        const vi = pending.findIndex(isValidate), vcmd = pending[vi]
        let vrc = -1, vout = ''
        for (let rep = 0; rep <= 2; rep++) {
          const v = await sh('{ ' + vcmd + '\n}; rc=$?; echo "__RC0=$rc"', lbl('validate' + (rep ? ' after repair ' + rep : '')), { phase: 'Runs', timeout: 300000 })
          vrc = Number((/__RC0=(\d+)/.exec(v.out) || [])[1]); vout = v.out
          if (!Number.isFinite(vrc)) vrc = -1
          if (vrc === 0 || rep === 2) break
          const target = validateTarget(vout)
          if (!target) { log(id + ' validate failed on a contract that is never edited — rendering as-is'); break }
          log(id + ' validate FAIL → repair ' + target)
          await repairSeat(target, vout); st.validate_repairs++
        }
        st.validate_rc = vrc
        if (vrc !== 0) st.validate_note = vout.split('\n').filter((l) => /✗/.test(l)).slice(0, 6).join(' | ').slice(0, 600)
        pending = pending.filter((c, j) => j !== vi)
        if (!pending.length) { pending = null; continue }
      }
      if (pending) {
        const r = await runThenNext(rd, pending, lbl(pending.length + ' cmd → next'), 'Runs')
        const failed = r.rcs.map((rc, j) => (rc !== 0 ? j : null)).filter((x) => x !== null)
        if (failed.length) throw new Error('bash step failed (rc ' + failed.map((j) => r.rcs[j]).join(',') + '): ' + pending[failed[0]].slice(0, 160) + ' :: ' + r.out.slice(-500))
        pending = null
        e = r.emit
        if (!e.state) throw new Error('navigator emitted nothing after a bash step: ' + r.out.slice(-400))
      } else if (!e) {
        e = await nextEmit(rd, lbl('next'), 'Runs')
      }
      log(id + ' [' + (i + 1) + '] ' + e.state + ' → ' + e.step)

      if (isTerminal(e)) {
        markPhase1(true)
        st.state = /^DONE/.test(e.state) ? 'done' : (/do_not_generate/.test(e.state) ? 'do_not_generate' : 'phase_3_failed')
        st.note = e.notes
        break
      }

      // ---- bash steps: long jobs detach + poll (navigator folded into the last poll); the rest runs inline
      if (e.kind === 'bash') {
        markPhase1(true)
        const long = e.run.filter(isLong), short = e.run.filter((c) => !isLong(c))
        if (long.length) {
          for (const c of short) await prep(c, lbl('prep'), 'Runs')
          const job = longJob(rd, long[0])
          if (!(await launch(job.key, SKIP_ENV + long[0], lbl(job.key), 'Runs'))) throw new Error('could not launch: ' + long[0].slice(0, 120))
          const w = await waitFor(job.key, job.file, lbl(job.key), 'Runs', nextCmd(rd))
          if (!w.done) throw new Error(job.key + ' produced no ' + base(job.file) + ': ' + w.out.slice(-500))
          e = lastEmit(w.out)
          if (!e.state) e = null
          continue
        }
        pending = e.run
        continue
      }

      // ---- LLM steps
      const kind = routeKind(e)
      const bottleneckRetry = e.inputs.some((l) => /BOTTLENECK-RETRY MODE/.test(l))
      if (kind === 'phase1' && id !== 'r1' && !bottleneckRetry) {
        if (await phase1Ready) {
          pending = ['rm -rf ' + shq(rd + '/phase1') + ' && cp -r ' + shq(ROOT + '/r1/phase1') + ' ' + shq(rd + '/phase1') + ' && { [ -e ' + shq(ROOT + '/r1/do_not_generate.md') + ' ] && cp ' + shq(ROOT + '/r1/do_not_generate.md') + ' ' + shq(rd + '/') + '; true; }']
          st.seats.push({ kind: 'phase1', step: 'copied from r1', ok: true, signal: '' })
          continue
        }
        // r1 produced no Phase 1 — this run diagnoses on its own
      }
      if (kind !== 'phase1' && kind !== 'writeup') markPhase1(true)
      if (kind === 'tagging') { await tagShards(rd + '/phase0', id, 'Runs'); e = null; continue }
      if (kind === 'ideate' || kind === 'generate') {
        if (STAGGER && turn > 0) await ideateTurn[turn - 1].p
        const fresh = STAGGER ? await nextEmit(rd, lbl('next (dedup line)'), 'Runs') : e   // staggered: re-read so the earlier run's candidate is on disk
        await runSeat(fresh, routeKind(fresh))
        ideateTurn[turn].res()
      } else {
        await runSeat(e, kind)
      }
      e = null
    }
    if (st.state === 'running') { st.state = 'failed'; st.note = 'exceeded ' + MAX_STEPS + ' navigator steps' }
  } catch (err) {
    st.state = 'failed'
    st.note = String(err && err.message ? err.message : err).slice(0, 800)
    log(id + ' FAILED: ' + st.note.slice(0, 200))
  }
  markPhase1(false)                                   // no-op when Phase 1 was already shared
  ideateTurn[turn].res()                              // no-op when this run already took its turn; frees the next run otherwise

  // ---- Phase 5: evidence plan (the one thing RS does not do) → plan_check → Phase 6 block specs → spec_check
  if (st.state === 'done') {
    st.cards = ['idea.std.zh.md', 'idea.std.en.md', 'idea.detail.en.md'].map((c) => rd + '/phase4/' + c)
    // RS's own structural regression check (scripts/regression_check.py; run.py never calls it) — the free sixth validator
    const rg = await sh('{ ' + PY + ' ' + shq(SKILL_DIR + '/scripts/regression_check.py') + ' ' + shq(rd) + '\n}; rc=$?; echo "__RC0=$rc"', lbl('regression_check'), { phase: 'Evidence', timeout: 120000 })
    st.regression_rc = Number((/__RC0=(\d+)/.exec(rg.out) || [])[1]); if (!Number.isFinite(st.regression_rc)) st.regression_rc = -1
    if (st.regression_rc) log(id + ' regression_check rc=' + st.regression_rc + ': ' + rg.out.replace(/__RC0=\d+/, '').trim().slice(-300))
    const out = rd + '/phase5/evidence_plan.json'
    const evidenceInputs = [rd + '/phase4/phase4_expansion.json  (the finished idea; kill-switch fields are locked)',
               rd + '/phase4/method_view.json  (method-only slice)',
               rd + '/phase4/phase4_implementability.json  (buildable spec per step, if present)',
               rd + '/phase4/idea.detail.en.md  (reviewer version of the card)',
               SHARED + '/substrate.md  (every arm must name a config, script or module from here)',
               SHARED + '/intake.json'].concat(brainContext('evidence', id))
    const planCheck = () => sh(PY + ' - ' + shq(out) + ' ' + shq(JSON.stringify(REQUIRED_BASELINES)) + ' <<\'PYEOF\'\n' + PLAN_CHECK_PY + '\nPYEOF', lbl('plan_check'), { phase: 'Evidence', timeout: 60000 })
    let extra = ''
    const pre = await planCheck(), pv = (/__PLAN_(OK|BAD) ?([^\n]*)/.exec(pre.out) || [])   // resumability: an existing evidence_plan.json is judged, never regenerated blindly
    if (pv[1] === 'OK') { st.evidence_plan = out; st.plan_check = 'OK (existing plan kept)' + (pv[2] ? ': ' + pv[2].slice(0, 400) : ''); log(id + ' Phase 5: existing evidence_plan.json passes plan_check — seat skipped') }
    else if (pv[1] === 'BAD' && !/unreadable/.test(pv[2] || '')) extra = ' PLAN_CHECK FINDINGS on the existing file (deterministic; fix every item, rewrite the whole file): ' + (pv[2] || '').slice(0, 1200)
    for (let attempt = 0; attempt < 2 && !(attempt === 0 && st.evidence_plan); attempt++) {
      const r = await seat('evidence', {
        rd, run: id, repo: BRIEF.repo, step: 'Phase 5 — evidence plan' + (attempt ? ' (repair)' : ''), inputs: evidenceInputs, output: out,
        notes: 'Contract for the Worker session; the first block in run_order is the cheapest test that can kill the idea.' + extra,
      }, lbl('Phase 5 evidence plan' + (attempt ? ' repair' : '')), 'Evidence')
      rec('evidence', 'Phase 5', r)
      if (!r || !r.ok) { st.note = 'evidence plan failed: ' + ((r && r.note) || 'no result'); break }
      st.evidence_plan = out
      const c = await planCheck()
      const verdict = (/__PLAN_(OK|BAD) ?([^\n]*)/.exec(c.out) || [])
      st.plan_check = verdict[1] ? verdict[1] + (verdict[2] ? ': ' + verdict[2].slice(0, 400) : '') : 'unknown: ' + c.out.slice(-200)
      if (verdict[1] !== 'BAD') break
      extra = ' PLAN_CHECK FINDINGS (deterministic; fix every item, rewrite the whole file): ' + verdict[2].slice(0, 1200)
      log(id + ' plan_check: ' + verdict[2].slice(0, 200))
    }
    if (st.evidence_plan) {
      const specDir = rd + '/spec'
      const specInputs = [out + '  (the evidence plan — one spec per block)', rd + '/phase4/method_view.json  (equations and steps)',
                          rd + '/phase4/phase4_implementability.json  (per-step engineering notes, if present)',
                          SHARED + '/substrate.md  (file:line facts; every path is repo-relative under REPOSITORY)', SHARED + '/intake.json'].concat(brainContext('spec', id))
      const specCheck = () => sh(PY + ' - ' + shq(specDir) + ' ' + shq(BRIEF.repo) + ' ' + shq(JSON.stringify(FORBIDDEN_PATTERNS)) + ' ' + shq(rd + '/phase4/phase4_implementability.json') + ' <<\'PYEOF\'\n' + SPEC_CHECK_PY + '\nPYEOF', lbl('spec_check'), { phase: 'Evidence', timeout: 60000 })
      let extra2 = ''
      const pre2 = await specCheck(), sv = (/__SPEC_(OK|BAD) ?([^\n]*)/.exec(pre2.out) || [])
      if (sv[1] === 'OK') { st.spec = specDir; st.spec_check = 'OK (existing specs kept)' + (sv[2] ? ': ' + sv[2].slice(0, 400) : ''); log(id + ' Phase 6: existing spec/ passes spec_check — seat skipped') }
      else if (sv[1] === 'BAD' && !/no spec\/B\*\.json|index\.json missing/.test(sv[2] || '')) extra2 = ' SPEC_CHECK FINDINGS on the existing files (deterministic; fix every item, rewrite the affected files whole): ' + (sv[2] || '').slice(0, 1200)
      for (let attempt = 0; attempt < 2 && !(attempt === 0 && st.spec); attempt++) {
        const r = await seat('spec', {
          rd, run: id, repo: BRIEF.repo, step: 'Phase 6 — block specs' + (attempt ? ' (repair)' : ''), inputs: specInputs,
          output: specDir + '/index.json then ' + specDir + '/B<k>.json (one per block)',
          notes: 'Read the repository to name real files, functions and launchers; write only under RUN_DIR/spec/.' + extra2,
        }, lbl('Phase 6 block specs' + (attempt ? ' repair' : '')), 'Evidence')
        rec('spec', 'Phase 6', r)
        if (!r || !r.ok) { st.note = 'spec seat failed: ' + ((r && r.note) || 'no result'); break }
        st.spec = specDir
        const c = await specCheck()
        const verdict = (/__SPEC_(OK|BAD) ?([^\n]*)/.exec(c.out) || [])
        st.spec_check = verdict[1] ? verdict[1] + (verdict[2] ? ': ' + verdict[2].slice(0, 400) : '') : 'unknown: ' + c.out.slice(-200)
        if (verdict[1] !== 'BAD') break
        extra2 = ' SPEC_CHECK FINDINGS (deterministic; fix every item, rewrite the affected files whole): ' + verdict[2].slice(0, 1200)
        log(id + ' spec_check: ' + verdict[2].slice(0, 200))
      }
    }
  }
  return st
}

// ═══════════════════════════════════════════════════════════════ 8. main
const st0 = await probeShared()
const queries = await intakeStage(st0)
await phase0Stage(queries)
phase('Runs')
log('driving ' + K + ' run(s): ' + RUN_IDS.join(', ') + ' — direction: ' + (DIRECTION || '').slice(0, 160))
const runs = (await parallel(RUN_IDS.map((id) => () => driveRun(id)))).filter(Boolean)

let ranking = null, rankCheck = null
const finished = runs.filter((r) => r.state === 'done' && r.evidence_plan)
if (finished.length >= 2) {
  phase('Rank')
  const out = ROOT + '/ranking.json'
  const rankInputs = finished.flatMap((x) => [ROOT + '/' + x.id + '/phase4/idea.detail.en.md', x.evidence_plan, ROOT + '/' + x.id + '/phase3_critique/phase3_critique_output.json  (3.2 audit: paper-pointed threat, verdict)'].concat(x.spec ? [x.spec + '/index.json  (block specs; B1 first)'] : [])).concat([SHARED + '/substrate.md  (compute envelope, baselines)'], brainContext('rank'))
  const rankCheck_ = () => sh(PY + ' - ' + shq(out) + ' ' + shq(JSON.stringify(finished.map((x) => x.id))) + ' <<\'PYEOF\'\n' + RANK_CHECK_PY + '\nPYEOF', 'rank_check', { phase: 'Rank', timeout: 60000 })
  let extra = ''
  const pre = await rankCheck_(), rv = (/__RANK_(OK|BAD) ?([^\n]*)/.exec(pre.out) || [])
  if (rv[1] === 'OK') { ranking = out; rankCheck = 'OK (existing ranking kept)' + (rv[2] ? ': ' + rv[2].slice(0, 400) : ''); log('Rank: existing ranking.json passes rank_check — seat skipped') }
  else if (rv[1] === 'BAD' && !/unreadable/.test(rv[2] || '')) extra = ' RANK_CHECK FINDINGS on the existing file (deterministic; fix every item, rewrite the whole file): ' + (rv[2] || '').slice(0, 1200)
  for (let attempt = 0; attempt < 2 && !(attempt === 0 && ranking); attempt++) {
    const r = await seat('rank', {
      rd: ROOT, run: 'all', repo: BRIEF.repo, step: 'Rank ' + finished.length + ' ideas' + (attempt ? ' (repair)' : ''), inputs: rankInputs, output: out,
      notes: 'Every finished run appears exactly once.' + extra,
    }, 'rank ' + finished.map((x) => x.id).join(',') + (attempt ? ' repair' : ''), 'Rank')
    if (!r || !r.ok) break
    ranking = out
    const c = await rankCheck_()
    const verdict = (/__RANK_(OK|BAD) ?([^\n]*)/.exec(c.out) || [])
    rankCheck = verdict[1] ? verdict[1] + (verdict[2] ? ': ' + verdict[2].slice(0, 400) : '') : 'unknown: ' + c.out.slice(-200)
    if (verdict[1] !== 'BAD') break
    extra = ' RANK_CHECK FINDINGS (deterministic; fix every item, rewrite the whole file): ' + verdict[2].slice(0, 1200)
    log('rank_check: ' + verdict[2].slice(0, 200))
  }
}

return {
  root: ROOT, k: K, direction: DIRECTION,
  runs: runs.map((r) => ({ id: r.id, state: r.state, steps: r.steps, seats: r.seats.length, fallbacks: r.fallbacks, audit_merge: r.audit_merge, cards: r.cards, evidence_plan: r.evidence_plan, plan_check: r.plan_check, spec: r.spec, spec_check: r.spec_check,
    quote_check: r.quote_check, quote_check3: r.quote_check3, validate_rc: r.validate_rc, validate_repairs: r.validate_repairs, validate_note: r.validate_note, regression_rc: r.regression_rc, placeholders: r.placeholders, note: r.note })),
  ranking, rank_check: rankCheck,
}
