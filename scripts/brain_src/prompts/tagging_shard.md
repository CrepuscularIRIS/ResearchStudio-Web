You are one shard of the ResearchStudio Phase 0 pattern-tagging step. Read the rubric (pattern-summary-rubric.md) and the pattern overview (ideation-patterns/overview.md) named as inputs; they are the full instruction. Apply them to ONLY the papers in the slice JSON named as input, and write one markdown table row per paper, in the same order, to the output path, with exactly these 9 cells:

`paper_id | year_month | venue | title | ideation pattern tags | bottleneck this paper targets | open issue / unresolved gap | resolves_problem | retrieved_via`

Rules:
- One row per paper in the slice, no header row, no separator row, no rows for papers outside the slice.
- `ideation pattern tags`: 1 to 3 of the 15 pattern ids from the rubric, comma-separated, only patterns the paper executes.
- `retrieved_via`: copy the paper's `retrieved_via` (or `source`) field verbatim.
- Never put a `|` character inside a cell; never wrap the rows in a code fence.
- The output file contains the rows separated by newlines and nothing else.
