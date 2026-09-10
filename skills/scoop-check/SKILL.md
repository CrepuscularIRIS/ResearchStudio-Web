---
name: scoop-check
description: Check whether a proposed research novelty overlaps with existing published work. Use when the user asks to verify that an idea is new, compare a proposed contribution against prior art, run a prior-art or literature search for a specific claim, or assess whether a paper idea has been scooped. Do not use for general literature reviews unrelated to a specific novelty claim, or for writing the related-work section of an already-validated idea.
---

# ResearchStudio scoop-check — web-search host

Read `references/host-runtime.md` and `references/websearch-retrieval.md`
first. `references/upstream/SKILL.md` is the preserved upstream runbook and the
authority on the **method** — the three-query decomposition, the four overlap
axes, the verdict rubric, and the report format. This file changes only
retrieval and how papers get read.

## Retrieval (upstream Step 2)

Upstream routes the three queries through the `paper-search` skill. Here, run
them as `web_search` yourself, under the four source rules in
`references/websearch-retrieval.md`. Do not run any connector script.

Keep upstream's Step 2.5: add papers you recall that the search missed, marked
`Source: recall`. A recall row is a lead, not evidence — resolve it to a real
URL with one search before it can support any part of the verdict. If it will
not resolve, say so and drop it.

## Reading the papers (upstream Step 5)

Upstream downloads a PDF and shells out to `pdftotext`. Here:

1. **`web_fetch` the paper's HTML page first** — arXiv `/abs/`, ACL Anthology,
   OpenReview, the CVF page. For most 2024+ ML papers the abstract, method
   summary and often the full text are right there, at a fraction of a PDF's
   token cost.
2. **A PDF only when the verdict depends on it.** On claude.ai, read
   `/mnt/skills/public/pdf-reading/SKILL.md` and follow it. Do not build your
   own extraction pipeline.
3. **Skim to the four axes.** Problem, mechanism, claim, evidence — then stop.
   The deep dive exists to test overlap, not to summarize the paper.

Budget honestly: a scoop check that reads three papers properly beats one that
skims twelve.

## Output

State the verdict plainly, then the evidence base:

- which papers you read in full, which you judged from an abstract, and which
  came from recall;
- the URL for every paper named in the verdict;
- what you searched, so the user can see the shape of the sweep.

A collision verdict resting on unread papers is a hypothesis. Say which one you
are giving them.

If the user wants a file, write the report to the run directory
(`references/host-runtime.md` names it per host) and display it inline as well.
