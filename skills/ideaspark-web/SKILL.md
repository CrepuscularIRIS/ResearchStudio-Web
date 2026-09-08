---
name: ideaspark-web
description: Run ResearchStudio IdeaSpark on the ChatGPT web app through the playwright browser extension — one to five conversations in parallel, each seeded from a research direction or from a local workflow run, captured to disk when the answer is provably complete. Use when the user asks for the web track, for a fast second opinion on a direction or bottleneck, or to seed ideas from a finished ideaspark run. Do not use to drive the local workflow (that is the `ideaspark` workflow) or for general browsing.
---

# IdeaSpark — web track

The same skill, the other surface. The `ideaspark` workflow runs the pipeline locally, gate by
gate, in hours. This one asks the hosted IdeaSpark the same question in **30–60 minutes**, with a
much wider search behind it, and captures the answer. Neither replaces the other: the local track
is auditable and reproducible, the web track is fast and reads more literature. Run both on the
same direction and compare with the same judge.

## The trigger

The hosted skill fires on a prompt that **opens** with the trigger line. Everything after it is
the intake, one field per line:

```
@ResearchStudio IdeaSpark Use IdeaSpark.
Target system: PhyAgentOS.
Research direction: long-horizon agents suffer from context growth and unreliable memory retrieval. I want to investigate a method that makes memory selection causally relevant to future tool decisions.
Contribution type: method.
Compute budget: 8×H100.
```

Rules for composing it:

- `Target system` and `Compute budget` are optional; drop the line rather than writing "unknown".
- `Research direction` is one or two sentences: a direction **or** a named bottleneck. A bottleneck
  is the stronger input — "X fails when Y" beats "I want to work on X".
- Append this as the last line, always:
  `End your answer with the single line <<END OF IDEA CARD>> and nothing after it.`
  That marker is this skill's, not IdeaSpark's. It is what makes "is it finished?" a fact instead
  of a guess.
- Never paste local file paths or repository contents into the web app. Facts you want it to use
  go in as prose you typed.

## Browser protocol

The surface is `chatgpt.com` driven by the `playwright-extension` tools. Observed structure, on
2026-09-08 — re-verify with `browser_snapshot` if anything below does not match:

| what | how |
|---|---|
| composer | `#prompt-textarea`, a contenteditable `div` |
| a turn | `[data-message-author-role="user"\|"assistant"]`, wrapped in `[data-testid^="conversation-turn"]` |
| answer body | `.markdown.prose` inside the assistant turn |
| still generating | `[data-testid="stop-button"]` exists, or `.result-streaming` count > 0 |
| turn finished | the turn carries `[data-testid="copy-turn-action-button"]` |

Seven rules, each of which exists because ignoring it produced a wrong answer before:

1. **Persistent chats only.** Start each window at `https://chatgpt.com/` (a normal new chat), never
   a temporary one. The conversation is the audit trail; a temporary chat leaves nothing to re-read.
2. **One conversation per window, one question per conversation.** Do not follow up in a window that
   already answered — a second question there changes what the first answer meant.
3. **Confirm the send.** After submitting, poll until a `user` turn with your text exists. A composer
   that silently kept the text is the most common failure and it looks like a slow answer.
4. **Truncated capture means unfinished.** Treat the answer as complete only when ALL of these hold:
   the `<<END OF IDEA CARD>>` marker is present; no stop button and no `.result-streaming`; the
   assistant turn carries a copy button; and `textContent.length` is unchanged across two polls at
   least 20 s apart. Any one of them failing means keep waiting.
5. **Read `textContent`, never `innerText`.** `innerText` reflects layout: it drops text clipped by
   overflow and reorders list markers, so a complete answer can read as a truncated one.
6. **Poll on a budget, not in a spin.** Check every 45–60 s, up to 75 minutes per window. A run that
   goes past that is stuck, not slow.
7. **Screenshot before declaring anything dead.** If a window looks broken — no turn, empty body,
   an error banner — take `browser_take_screenshot` and read it before retrying or giving up. Say
   what the screenshot showed.

## Running it

**1. Seed the prompts.** One per window, at most five:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/web/web.py" seed --root <run_root> \
  --direction "<one or two sentences>" [--target "<system>"] [--type method] [--compute "8×H100"] [--n 3]
```

Or seed **from a finished local run** — this is the point of the dual track. The seeder reads the
run's Phase 1 output and turns each unaddressed gap into its own question, and (when the gauntlet
got that far) adds the paper-pointed threat as a differentiation constraint:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/web/web.py" seed --root <run_root> --from-run --n 4
```

Prompts land in `<run_root>/web/prompts/NN.txt` with a `manifest.json`. Read them before sending —
you are responsible for what goes into someone else's chat window.

**2. Open the windows.** `browser_tabs` with `action: "new"` and `url: "https://chatgpt.com/"`, one
per prompt, up to five. Stagger the sends by ~10 s. Record which tab index holds which prompt id;
tab indices shift when a tab closes, so re-`list` before every `select`.

**3. Send.** `browser_snapshot` to get the composer ref, `browser_type` the whole prompt with
`submit: true`. Then rule 3: confirm the user turn exists before you start waiting.

**4. Poll and capture.** Per window, per poll, one `browser_evaluate`:

```js
() => {
  const a = [...document.querySelectorAll('[data-message-author-role="assistant"]')].pop();
  if (!a) return JSON.stringify({ state: 'no-answer-yet' });
  const md = a.querySelector('.markdown') || a;
  const text = md.textContent || '';
  return JSON.stringify({
    state: 'have-turn',
    len: text.length,
    done_marker: text.includes('<<END OF IDEA CARD>>'),
    streaming: document.querySelectorAll('.result-streaming').length > 0
               || !!document.querySelector('[data-testid="stop-button"]'),
    has_copy: !!a.closest('[data-testid^="conversation-turn"]')
                 ?.querySelector('[data-testid="copy-turn-action-button"]'),
    text: text,
  });
}
```

For a long answer pass `filename` to `browser_evaluate` so the body goes to a file instead of
through the conversation. Write the captured text verbatim to
`<run_root>/web/answers/NN.md`, and the conversation URL into the manifest — that URL is the
audit trail and it is the one thing you cannot reconstruct later.

**5. Collect.** `web.py collect --root <run_root>` writes `<run_root>/web/index.json`: per answer
the prompt id, the URL, the length, whether the marker was present, and the first heading. It
refuses to mark an answer complete without the marker, so a half-captured window stays visible.

**6. Score it like the other track.** The web cards and the workflow's cards are judged by the same
skill — `vendor/researchstudio/evaluation/idea_quality/SKILL.md`, three axes plus a blind pairwise.
Judge the two tracks' cards against each other head to head; provenance is not evidence of quality
and the pairwise track is the trustworthy signal.

## When it goes wrong

- **Answer stops mid-sentence, no marker, nothing streaming.** The turn was cut. Do not stitch a
  continuation onto it silently — either re-send in a fresh window, or send `continue` and record in
  the manifest that the answer is two turns.
- **The trigger did not fire** (the answer reads like an ordinary chat reply, no card structure).
  Check the first line is exactly the trigger and that it is the first thing in the message. Report
  it; do not paraphrase the trigger to "help".
- **Rate limited or a model picker dialog.** Screenshot, report, stop. Do not click through dialogs
  in someone's logged-in account beyond selecting the composer and sending.
- **Fewer windows than prompts.** Send what fits, and say which prompt ids were not sent.
