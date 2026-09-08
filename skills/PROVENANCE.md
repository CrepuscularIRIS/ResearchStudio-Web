# Project-local skills — the ARIS experiment track

These are **project-local on purpose**: they belong to this repository's experiment track, and a
copy in `~/.claude/skills` would follow every unrelated session on this machine.

Nothing here is hand-written. Rebuild the whole directory with:

    python3 .research/aris/build_skills.py          # --check verifies and writes nothing
                                                    # --out <project> installs elsewhere

| what | where it comes from |
|---|---|
| `experiment-audit`, `experiment-plan`, `kill-argument`, `result-to-claim` | upstream ARIS `SKILL.md`, **unedited**, with one declared block interleaved into each — see each skill's `DERIVATION.md` |
| `shared-references/` (31 files) | upstream `skills/shared-references/`, copied verbatim; the contracts cite them as `../shared-references/<name>.md`, so they must sit here as siblings |

Upstream: [wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)
@ `0472e530251cdbd3364c33b110063c58f819edd7` (2026-09-07) at `/home/lingxufeng/autoresearch/Auto-claude-code-research-in-sleep` — MIT, Copyright (c) 2026 wanshuiyin. Redistributed under that licence.

Two things to know before running any of these:

1. **The inserted blocks are marked.** Everything between `<!-- ARFT/ASI-BENCH BLOCK: … -->` and
   `<!-- END BLOCK: … -->` is ours (ARFT arXiv 2608.14905 · ASI-Bench arXiv 2608.17271); everything
   else is upstream. `build_skills.py --check` asserts that deleting the blocks restores the
   upstream file byte for byte, so the boundary is verifiable rather than asserted.
2. **The reviewer model default is `gpt-6-astra`** in this upstream revision (it was `gpt-5.6-sol`
   three weeks earlier). Our quota for that model is gone, so any of these skills that calls a
   reviewer needs `REVIEWER_MODEL` overridden before it will get an answer.

`$ARIS_REPO` resolves through `.aris/installed-skills.txt` at the project root, which
`build_skills.py` writes — that is how the helper scripts these contracts shell out to
(`tools/evidence_check.py` and friends) are found.
