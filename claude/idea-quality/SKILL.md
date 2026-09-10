---
name: idea-quality
description: Score the QUALITY of a research idea at the idea stage — given a Markdown file with Title / Motivation / Method sections (no experiments needed), produce a per-axis quality assessment with cited evidence and an overall 0-100 score plus a verdict; or, given two such idea files, a blind head-to-head comparison. TRIGGER when the user asks "how good is this idea", "rate / score / grade this research idea", "review my idea before I write it up", "is this contribution strong enough to pursue", or "which of these two ideas is stronger", or hands over an idea Markdown file and wants a quality judgment. DO NOT trigger for prior-art or novelty-vs-existing-work checks (that is a literature-collision task), for reviews of finished papers that already have results, or for generating the idea itself.
---

# ResearchStudio idea-quality — web host

**Follow `references/upstream/SKILL.md` exactly.** It holds the axes, the
rubric, the scoring bands, the evidence requirements and the output format, and
this skill is self-contained by design: it judges from the idea text alone and
consults no external corpus, dataset, or other skill. Nothing about the method
changes on this host.

This file adds only the three host details.

## 1. Where the idea file comes from

An uploaded file lands read-only at `/mnt/user-data/uploads/` on claude.ai, or
wherever the user names it in Claude Code (`references/host-runtime.md` has the
path map). If the user
pasted the idea into the conversation instead of uploading it, write it to a
file first and judge the file — the rubric is defined over Title / Motivation /
Method sections, and reconstructing them from chat prose is where the judgment
silently drifts.

If a needed section is missing, say which one and score only what the file
actually supports. Do not infer a Method from a Motivation.

## 2. Where the assessment goes

Display the full assessment inline — it is the deliverable, not an attachment.
Also write it to the run directory (`/mnt/user-data/outputs/` on claude.ai) so
the user can keep a copy.

For a head-to-head comparison, keep upstream's blind protocol: judge each idea
on its own before comparing, and never let file order become a tiebreaker.

## 3. No scoring theatre

The score is a judgment with cited evidence from the idea text, not a
calculation. Quote the line that drove each axis. If the idea is thin, the
honest output is a low score with the reason — not a padded rubric that reads
as thorough.

`ORIGIN.md` states the parity boundary; `verify_parity.py` proves the upstream
rubric bytes are intact.
