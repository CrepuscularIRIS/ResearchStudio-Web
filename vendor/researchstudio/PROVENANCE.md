# Vendored: ResearchStudio idea_spark

Upstream: https://github.com/microsoft/ResearchStudio — MIT licensed (see `LICENSE`,
Copyright (c) 2026 Happy). This directory is an unmodified copy, redistributed under
that licence.

| | |
|---|---|
| commit | `0597891df1a153b8e4cbdc8c1c685f43a0a6abcf` (2026-09-06) |
| last change to `idea_spark` | `2540dde` (2026-09-03) |
| copied | `ResearchStudio-Idea/skills/idea_spark/`, `ResearchStudio-Idea/evaluation/idea_quality/`, `.env.template`, the repo `LICENSE` |
| omitted | `__pycache__/`, `*.pyc`, `.env` (credentials), and everything outside those two trees |
| modified | nothing — `tests/test_ideaspark_workflow.py::test_prompts_inlined_verbatim` compares every prompt the workflow ships against the file here, byte for byte |

Why it is vendored rather than fetched: the workflow shells out to `scripts/run.py` for
every deterministic step (retrieval, merging, the Phase 4 assembler, the validators), and
the same tree is the oracle the differential test runs `next` from. A version skew between
the prompts the workflow ships and the scripts it calls is exactly the failure this copy
removes.

To move to a newer upstream: replace this directory, re-run `python3 scripts/ideaspark_src/gen.py`,
then `tests/selftest.sh`. The differential test fails loudly if the phase graph moved.

Credentials: copy `.env.template` to `.env` next to this file and fill in the OpenReview
user/password and (recommended) a Semantic Scholar key. `run.py` walks up from the skill
directory and stops at the FIRST `.env` it finds, so keep the keys in ONE file — a second
`.env` deeper in the tree silently shadows this one, which is how the OpenReview connector
went quietly missing for weeks.
