---
description: Ask the hosted IdeaSpark the same question on chatgpt.com, 1-5 windows in parallel
argument-hint: "<topic-slug> [--from-run | \"<research direction>\"] [--n 3]"
---

Run the IdeaSpark **web track** for the run named by `$ARGUMENTS`.

Use the `ideaspark-web` skill — it carries the trigger format, the browser protocol, and the completion rule. In short: seed the prompts with `scripts/web/web.py seed`, open one `chatgpt.com` tab per prompt (at most five, staggered ~10 s), send, then poll each window until the answer is provably finished — end marker present, nothing streaming, the copy button on the turn, and the length unchanged across two polls. A truncated capture is an unfinished answer, never a short one.

Save each answer verbatim to `<root>/web/answers/NN.md`, put the conversation URL in the manifest, then `web.py collect`. Report per window: complete or not, the first heading, and the URL.

If a local run already exists for this slug, prefer `--from-run`: the seeder turns each unaddressed Phase 1 gap into its own question and adds the audit's paper-pointed threat as a differentiation constraint. That is the point of running two tracks.
