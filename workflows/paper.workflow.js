/**
 * paper — V8: Claim supported → one-shot manuscript (WORKFLOW.md §10-12).
 *
 * Claim first, paper second. Written ONCE after experiments finish, not incrementally
 * (avoids narrative lock). CCFA writer assets provide the prompt contracts.
 * Grok CLI does ONE final audit.
 *
 * Flow:
 *   assemble (GLM: Claim + E[] + research evidence → structured inputs)
 *   → draft (GLM: section-by-section, CCFA discipline in prompt)
 *   → compile check (GLM: LaTeX lint / prose lint, deterministic)
 *   → Grok audit (CLI: one final read-only review)
 *   → written
 *
 * Run: Workflow({ name: "paper", args: { claim, evidence[], substrate?, frozen? } })
 */

export const meta = {
  name: 'paper',
  description: "One-shot manuscript: Claim supported + E[] → CCFA-discipline draft (GLM sections) → deterministic lint → Grok CLI final audit.",
  whenToUse: "dag offers WORKFLOW: paper after claim.strength === 'supported'.",
  phases: [
    { title: "Assemble", detail: "GLM: Claim + E[] + research evidence → structured writing inputs (evidence ladder, table skeleton)" },
    { title: "Draft", detail: "GLM: section-by-section draft under CCFA discipline (claim-evidence matrix, one-table-one-claim, evidence ladder order)" },
    { title: "Lint", detail: "GLM: deterministic prose check (no TBD, no placeholder, claim-evidence alignment)" },
    { title: "Audit", detail: "Grok CLI: one final read-only review" },
  ],
}

const MODEL = { opus: 'claude-opus-5', glm: 'glm-5.3[1m]' }
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const GROK_CLI = (A.paths || {}).grok_cli || "grok"

// CCFA verbatim contracts
const EVIDENCE_LADDER =
  "EVIDENCE LADDER ORDER: (1) establish phenomenon/failure mode (2) main effect vs strong baselines " +
  "(3) mechanism via ablation/proof/diagnostic (4) generalization/robustness/scale/transfer " +
  "(5) boundary conditions/failure cases."
const CLAIM_ACTION =
  "CLAIM-ACTION RULES: Supported claims may be sharpened. Weakly supported claims must be narrowed. " +
  "Unsupported claims must be removed. Evidence hidden only in appendix must be signposted in main text."
const ONE_TABLE =
  "ONE TABLE ONE CLAIM: every table has exactly one message; if two messages, split. Caption triple: " +
  "what + setting + takeaway. Same decimal places per column. Bold best, one convention."
const PROSE_DISCIPLINE =
  "PROSE: No TBD, no placeholder, no 'needs more experiments' without naming the exact gap. " +
  "Distinguish measured / inferred / speculated — never in the same voice. " +
  "Lead each section with its conclusion. No banned hype words (significant, novel, first, dramatically) " +
  "without evidence. No em-dash abuse."
const TABLE_FROM_E =
  "TABLE from E: every number in every table must trace to a specific E's recompute_table entry. " +
  "No number appears in the paper that doesn't exist in the evidence. Missing = TBD or omitted."

let agentCalls = 0
const byModel = {}
const seat = async (prompt, opts) => {
  agentCalls++; byModel[opts.model] = (byModel[opts.model] || 0) + 1
  return agent(prompt, opts)
}

if (!A.claim || !A.claim.statement) return { error: "No claim in args." }
if (!A.evidence || !A.evidence.length) return { error: "No evidence array — paper needs at least one valid E." }
const C = A.claim
const Es = A.evidence

// ═══ Phase 1: Assemble ═══
phase("Assemble")
const ASSEMBLE_SCHEMA = {
  type: "object",
  required: ["sections", "tables", "evidence_map"],
  properties: {
    sections: { type: "array", items: { type: "object", required: ["name", "content_hint"], properties: {
      name: { type: "string" }, content_hint: { type: "string" } } } },
    tables: { type: "array", items: { type: "object", required: ["name", "columns", "rows"], properties: {
      name: { type: "string" }, columns: { type: "array", items: { type: "string" } },
      rows: { type: "array", items: { type: "object", required: ["label", "values"], properties: {
        label: { type: "string" }, values: { type: "array", items: { type: "string" } } } } } } } },
    evidence_map: { type: "string", description: "which E fills which table cell / section claim" },
  },
}
const assembled = await seat(
  "## Assemble writing inputs (no tools)\n## Claim\n" + C.statement +
  "\n## Strategy\n" + (C.strategy || "") + "\n## Margin rule\n" + (C.margin_rule || "") +
  "\n## Evidence (" + Es.length + " experiments)\n" +
  Es.map((e, i) => "### E" + i + " (" + e.test_id + ")\n" + JSON.stringify({
    row_evidence: e.row_evidence, recompute: (e.recompute_table || []).slice(0, 8) })).join("\n") +
  "\n## Research bottleneck\n" + JSON.stringify(C.bottleneck || {}) +
  "\n\n" + EVIDENCE_LADDER + "\n" + TABLE_FROM_E +
  "\n\nProduce: section plan (Intro/Related/Method/Experiments/Results/Discussion/Conclusion) + table skeletons " +
  "(fill from recompute tables; TBD for gaps) + evidence map.\n\nStructured output only.",
  { label: "assemble", phase: "Assemble", schema: ASSEMBLE_SCHEMA, model: MODEL.glm })
if (!assembled) return { error: "assemble seat absent — infra; retry." }

// ═══ Phase 2: Draft ═══
phase("Draft")
const DRAFT_SCHEMA = {
  type: "object", required: ["manuscript"],
  properties: {
    manuscript: { type: "string", description: "full paper in Markdown (tables as MD tables)" },
    title: { type: "string" }, abstract: { type: "string" },
  },
}
const draft = await seat(
  "## Write the manuscript (no tools)\n## Section plan\n" + JSON.stringify(assembled.sections) +
  "\n## Tables\n" + JSON.stringify(assembled.tables) +
  "\n## Evidence map\n" + assembled.evidence_map +
  "\n## Claim\n" + C.statement + "\n## Margin rule\n" + (C.margin_rule || "") +
  "\n\n" + EVIDENCE_LADDER + "\n" + CLAIM_ACTION + "\n" + ONE_TABLE + "\n" + PROSE_DISCIPLINE + "\n" + TABLE_FROM_E +
  "\n\nWrite a complete paper in Markdown. Every number traces to an E. No fabrication. " +
  "Results section only states what the evidence shows — no story beyond the data.\n\nStructured output only.",
  { label: "draft", phase: "Draft", schema: DRAFT_SCHEMA, model: MODEL.glm })
if (!draft) return { error: "draft seat absent — infra; retry." }

// ═══ Phase 3: Lint ═══
phase("Lint")
const LINT_SCHEMA = {
  type: "object", required: ["issues"],
  properties: { issues: { type: "array", maxItems: 10, items: { type: "object", required: ["type", "detail"], properties: {
    type: { enum: ["tbd_or_placeholder", "untraced_number", "hype_word", "claim_evidence_mismatch", "table_issue", "missing_section"] },
    detail: { type: "string" } } } } },
}
const lint = await seat(
  "## Prose lint (no tools)\n## Manuscript\n" + (draft.manuscript || "").slice(0, 15000) +
  "\n## Evidence map\n" + assembled.evidence_map +
  "\n\nCheck: (1) any TBD/placeholder/unfilled slot? (2) any number that doesn't trace to an E? " +
  "(3) any hype word (significant/novel/first/dramatically) without evidence? " +
  "(4) any claim stronger than its evidence? (5) every table has one message? " +
  "(6) every section from the plan present?\n\nStructured output only.",
  { label: "lint", phase: "Lint", schema: LINT_SCHEMA, model: MODEL.glm })
if (!lint) return { error: "lint seat absent — infra; retry." }
const lintIssues = (lint.issues || []).filter(i => i.type !== "missing_section") // missing_section is advisory
if (lintIssues.length) {
  // one revision pass
  const revised = await seat(
    "## Revise (fix these issues)\n## Issues\n" + JSON.stringify(lintIssues) +
    "\n## Manuscript\n" + (draft.manuscript || "").slice(0, 15000) +
    "\n\nFix ONLY the listed issues. Do not rewrite unaffected sections.\n\nStructured output only.",
    { label: "revise", phase: "Lint", schema: DRAFT_SCHEMA, model: MODEL.glm })
  if (revised && revised.manuscript) draft.manuscript = revised.manuscript
}

// ═══ Phase 4: Grok audit ═══
phase("Audit")
const grokR = await seat(
  "Run this Bash command and return stdout:\n" +
  "`echo '" + (draft.manuscript || "").slice(0, 8000).replace(/'/g, "'\\''") + "' | " + GROK_CLI + " task --read-only \"Audit this paper: every number traces to evidence? no fabrication? claims match evidence? no counterargument ignored?\"`\n" +
  "If it fails, return {unavailable: true}.",
  { label: "grok:audit", phase: "Audit", schema: {
    type: "object", required: ["output"],
    properties: { output: { type: "string" }, unavailable: { type: "boolean" },
      verdict: { type: "string" }, issues: { type: "array", items: { type: "string" } } },
  }, model: MODEL.glm })

return {
  outcome: "written",
  claim: C.id,
  title: draft.title || C.statement.slice(0, 80),
  manuscript: draft.manuscript,
  lint_clean: lintIssues.length === 0,
  grok_audit: grokR && !grokR.unavailable ? (grokR.verdict || grokR.output || "").slice(0, 500) : "unavailable",
  stats: { agentCalls, byModel, evidence_used: Es.length, lint_issues: lintIssues.length },
}
