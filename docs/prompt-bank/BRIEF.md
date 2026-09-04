# Prompt-fragment harvest — brief (shared by three readers)

Goal: lift the LOAD-BEARING prompt sentences, rules, check definitions and keywords from ONE source family, verbatim, so they can be
inserted into our research loop's prompts (context bundles built by python scripts). Not a design review; a quotation harvest.

Our prompt slots (name the slot each fragment belongs to; a fragment may fit several):
  S1  abstract   — Opus: claim + anomalies → failure modes B (grounded in measurements) → mechanisms M (three abstraction levels, domain-free)
  S2  diverge    — K3: for each mechanism, source domains C from other fields with isomorphism, disanalogy, query, naive_in_A, pattern lens
  S3  search     — GLM: run the paper-search script, choose procedure-grade papers, get their text; precedent query with the A terms
  S4  reverse    — GLM: one paper → gene card (steps with quote+line, key number, AVOID, disanalogy_to_A, scooped)
  S5  verify     — sol: re-read the paper for one card: quotes at lines, steps are procedures not gist, number is the mechanism's own evidence
  S6  critique-sources — panel (sol/K3/GLM): four checks per source (naive baseline · recipe-not-gist · graveyard/precedent · falsifiable at our scale), anchored fails, rank
  S7  critique-spec    — panel: five checks on one spec (recipe_application · falsification_structure · naive_equivalence · collision · feasibility), two-layer verdict advance/revise/abandon
  S8  spec       — Opus: write the next candidate as a complete B1 procedure (steps/files/conditions/held-out/schedule/canary/kill_cmd/naive_baseline/rationale_line/method_prose)
  S9  build-review-focus — the focus text given to the external diff reviewer (what counts as critical/high: unimplemented step, held-out leak, hardcoded result, extra mechanism, eval entry touched)
  S10 write-review     — Grok: final manuscript review (numbers vs records, selective narrative, claim–evidence, must-discuss comparisons, register as style:)
  S11 pivot      — K3: after the stop rule: why each tried source failed, what remains falsifiable, ship / revise claim / new sources
  S12 readers/jury (future outer loop) — manuscript readers producing anchored weaknesses; jurors; recall

Rules:
1. VERBATIM. Copy the sentence(s) exactly; put each fragment in a fenced block; ≤ 8 lines per fragment. Give `path:line-line`.
2. Prefer: check definitions, verdict rules, hard rules / NEVER lists, "iron rules", anti-patterns, forcing sentences (e.g. "Cannot quote = do not file"),
   schema field descriptions that constrain content, keyword lists the source uses to steer a model. Skip marketing, install docs, examples of output.
3. 25–45 fragments. Rank within each slot by how load-bearing you judge it (one line why). Note when a fragment is already in our loop
   (check /home/lingxufeng/workspace/.research/bundle.py, .research/critique.py, .claude/workflows/*.workflow.js) — mark `already: yes/partial/no`.
4. Write the report to the OUT path in your prompt (Write tool). Return the OUT path and a ≤10-line summary. Nothing else.
