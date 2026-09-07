# V9 Brain trajectory audit

Date: 2026-09-07  
Scope: first_run_3h36.tsv versus ccf_leg1.tsv + ccf_leg2.tsv, with the CCF journals, driver log, named raw agent transcripts, the earlier-run transcripts, brain.logic.js, and next_step.py.  
Time convention: agent timestamps below are UTC, as recorded in the JSONL and TSV files. ccf_auto.log is America/New_York time, four hours behind.

## Executive finding

The CCF run did repeat substantial work, but four different mechanisms caused it:

1. ResearchStudio deliberately discarded the first candidate after the 16:58 Phase 3.2 audit returned abandon, then regenerated Phase 2.1+2.2 and re-entered the Phase 2–3 gauntlet.
2. The harness/workflow repeatedly launched an over-context Sol second auditor. Seven agents consumed 28.6 agent-minutes; because K3 finished after 11.8 minutes, the failure chain added 16.7 minutes to the critical path.
3. Two user interruptions killed the new candidate's two Phase 2.3 attempts after 24.4 and 19.9 minutes. Resume-by-prompt caching then replayed an archived Phase 3.2 result without recreating its file, so the workflow briefly bypassed the missing coherence gate and ran an orphan Sol audit.
4. Phase 6, which did not exist in the earlier 3.6-hour trajectory, spent 53.4 minutes producing six specs that failed the deterministic checker, then 50.3 minutes re-reading and rewriting them.

“Every agent ran at max effort” is a real multiplier on individual Opus calls, especially Phase 2.1+2.2, but it does not explain the new Phase 6, the second auditor, the abandon-to-retry cycle, the user interruptions, the resume-cache correctness bug, or the rejected merge.

The comparison is also not same-version versus same-version. The earlier run on 2026-09-06 had no Phase 6 and no Sol second auditor. Both were added on 2026-09-07 shortly before CCF. The current brain.logic.js has since received post-mortem fixes; the run-time behavior must therefore be reconstructed from the trajectories, not inferred solely from the current source.

## Top-level accounting

The footer of first_run_3h36.tsv mishandles the midnight rollover. The rows themselves run from 20:32:29 on September 6 to 00:09:01 on September 7: 216.5 minutes, or 3 h 36.5 min.

| Metric | Earlier run | CCF run | Comparison |
|---|---:|---:|---:|
| Delivered ideas | 2 | 1 | Half the output |
| Wall time | 216.5 min | leg 1 99.1 + leg 2 314.7 min | 413.8 min across the two workflow legs |
| Explicit pause inside leg 2 | 0 | 7.2 min, 18:57:48–19:05:02 | Exclude this to match the owner's approximately 5 h 05 min active leg |
| Active workflow time | 216.5 min | 406.6 min | 1.88 times the latency |
| Wall minutes per delivered idea | 108.3 | 406.6 | 3.76 times worse throughput |
| Agents | 74 | 89 | +15 |
| Seat calls | 21 | 35 | +14 despite k=1 |
| Runner calls | 53 | 54 | Essentially unchanged count |
| Seat agent-minutes | 327.5 | 427.6 | +100.1 |
| Runner agent-minutes | 34.2 | 22.8 | CCF runners were faster, not the blow-up |
| Total agent-minutes per idea | 180.9 | 450.4 | 2.49 times |

The earlier k=2 run obtained its throughput by running the two idea legs in parallel. Each old idea's Phase 2–5 critical chain was roughly 159 minutes, but the two chains overlapped. CCF had only one run, then serially paid for a rejected first candidate, a second Phase 2–3 cycle, and Phase 6.

## 1. Seat-by-seat comparison

The table reports observed per-invocation means. “Tools” is the sum of the tool counts in the TSV. Thinking is in thousands of tokens. CCF's Phase 2.3 mean is artificially low because two of its three calls were interrupted before producing the report; the completed CCF call is analyzed separately below.

This is not a pure same-model benchmark. In the earlier run, requested GLM/K3 seats were silently served by claude-fable-5-1: that includes tagging, Phase 2.3, Phase 3.2, and Phase 4.1.5. CCF served tagging/derive/4.1.5 with GLM, Phase 2.3 with Opus, and the primary audit with K3. The most useful like-for-like evidence is therefore the Opus author seats plus the t1 effective-max control, not the raw average of every phase.

| Seat kind | Earlier k=2 run | CCF k=1 run, both legs | Mean minute delta |
|---|---|---|---:|
| runner | n=53; 0.6 min / 2.0 msg / 2.0 tools / 0.0k think | n=54; 0.4 min / 2.6 msg / 2.0 tools / 0.0k think | -0.2 |
| Phase -1 intake | not executed | n=1; 6.3 min / 61.0 msg / 36.0 tools / 0.0k think | new work |
| Phase 0 tagging/repair | n=3; 1.8 min / 5.3 msg / 4.0 tools / 0.0k think | n=10; 2.8 min / 7.2 msg / 3.0 tools / 0.0k think | +1.0 |
| Phase 1 bottleneck | n=1; 9.8 min / 38.0 msg / 20.0 tools / 2.9k think | n=1; 11.4 min / 27.0 msg / 13.0 tools / 35.5k think | +1.6 |
| Phase 2.1+2.2 | n=2; 16.3 min / 32.0 msg / 17.5 tools / 1.2k think | n=2; 33.5 min / 27.0 msg / 16.0 tools / 210.3k think | +17.2 |
| Phase 2.3 coherence | n=2; 59.5 min / 45.5 msg / 22.5 tools / 135.3k think | n=3; 28.5 min / 45.7 msg / 25.3 tools / 126.9k think | misleading: two interrupted |
| Phase 3.2 primary auditor | n=2; 8.8 min / 25.5 msg / 13.5 tools / 0.3k think | n=2; 10.7 min / 20.5 msg / 11.5 tools / 9.5k think | +1.9 |
| Phase 3.2 Sol second auditor | absent | n=9; 6.0 min / 26.3 msg / 16.2 tools / 0 think | new work |
| Phase 3.3 revision | n=2; 2.5 min / 10.5 msg / 5.0 tools / 3.9k think | n=1; 3.2 min / 10.0 msg / 5.0 tools / 13.3k think | +0.7 |
| Phase 4.fill | n=2; 8.5 min / 23.5 msg / 11.0 tools / 9.2k think | n=1; 10.0 min / 24.0 msg / 10.0 tools / 23.3k think | +1.5 |
| Phase 4.derive | n=2; 4.0 min / 4.5 msg / 3.0 tools / 0 think | n=1; 4.9 min / 15.0 msg / 6.0 tools / 0 think | +0.9 |
| Phase 4.1.5 | n=2; 44.5 min / 31.0 msg / 12.0 tools / 129.7k think | n=1; 20.9 min / 9.0 msg / 3.0 tools / 0 think | -23.6 |
| Phase 5 evidence | n=2; 11.1 min / 31.5 msg / 15.5 tools / 0.2k think | n=1; 11.8 min / 23.0 msg / 12.0 tools / 31.2k think | +0.8 |
| Phase 6 spec/repair | absent | n=2; 51.9 min / 152.5 msg / 84.5 tools / 161.9k think | new 103.7 min total |
| Rank | n=1; 2.0 min / 10 msg / 6 tools | not needed for k=1 | -2.0 |

### What actually became slower

- Phase 2.1+2.2 is the largest like-for-like slowdown. The first CCF call, a6c5ba3e at 15:45:25–16:07:35, took 22.2 minutes. The abandon retry, acf8d456 at 17:27:48–18:12:34, took 44.8 minutes. The old calls a252787a and a3339764 took 17.8 and 14.8 minutes.
- Phase 1, the primary Phase 3.2 audit, Phase 3.3, Phase 4.fill, Phase 4.derive, and Phase 5 were only 0.7–1.9 minutes slower per call. These are secondary effects.
- Completed Phase 2.3 did not become slower. CCF's completed a67f23c6 took 41.2 minutes, versus 45.6 and 73.5 minutes for old a588c5b3 and a44ca5ed. CCF became expensive here because the step was invoked again on the retry candidate and both calls were interrupted.
- Phase 4.1.5 was much faster in CCF. ac6adcfa took 20.9 minutes and only three tools, versus 32.9 and 56.0 minutes in the old run. It is conspicuous but not a regression.
- Phase 6 is not a slowdown of an old seat. It is 103.7 minutes of newly added work, plus roughly one minute of checks.

The corresponding old transcript timings reinforce those conclusions. Phase 2.1+2.2 agents a252787a, 21:10:01–21:27:48, and a3339764, 21:28:16–21:43:02, received approximately 81–82 KB prompts and wrote artifacts of comparable size to CCF, but finished in 17.8 and 14.8 minutes. Old completed coherence agents a44ca5ed, 21:28:13–22:41:40, and a588c5b3, 21:43:26–22:29:03, spent 61.6 and 37.4 minutes in explicit thinking and repeatedly developed Python dry-runs; this confirms that Phase 2.3 was already intrinsically heavy. Old primary audits a3c2e72c, 22:29:39–22:38:44, and a57bd95f, 22:42:17–22:50:48, took 9.1 and 8.5 minutes and paged collision_hits.json five and nine times, close to CCF K3 behavior. Old implementability agents a814e9b2, 22:56:50–23:52:49, and a3473b61, 23:06:57–23:39:53, were substantially slower than CCF ac6adcfa.

### The max-effort control

The t1 reference runs help separate model effort from repository/workflow effects:

| Seat | Earlier original repo | t1 original repo at effective max | CCF |
|---|---:|---:|---:|
| Phase 1 | 9.8 min, 2.9k think | aaf9b806: 18.4 min, 125.2k think | aa2e9a07: 11.4 min, 35.5k think |
| Phase 2.1+2.2 | mean 16.3 min, 1.2k think | ae412628: 36.6 min, 97.2k think | a6c5ba3e 22.2 min; acf8d456 44.8 min |
| Phase 2.3 | completed 45.6/73.5 min | three interrupted calls of 26.3/18.3/21.1 min | completed 41.2; interrupted 24.4/19.9 |

This shows that max effort can roughly double a Phase 2.1+2.2 call even on the original repository. It does not explain why CCF ran Phase 2.1+2.2 twice, added nine Sol calls, added Phase 6, or lost two Phase 2.3 attempts.

## Transcript findings

### Phase 2.1+2.2: extra time was thinking, not larger output

The static prompt was already enormous in the old run:

| Agent | Prompt characters | Duration | Approximate transcript time before explicit thinking emissions | Reads | Actual Write payload |
|---|---:|---:|---:|---:|---:|
| old a252787a | 81,384 | 17.8 min | 13.6 min | 14 | 51,901 chars |
| old a3339764 | 81,906 | 14.8 min | 11.3 min | 12 | 46,314 chars |
| CCF a6c5ba3e | 83,318 | 22.2 min | 18.7 min | 8 | 43,025 chars |
| CCF acf8d456 | 83,653 | 44.8 min | 41.0 min | 18 | 45,498 chars |

acf8d456 did not repeatedly read the same file inside its own seat: all 18 Read calls were to distinct paths. It did, however, re-read the same base inputs already consumed by a6c5ba3e: phase1_output.json, substrate.md, closest_abstracts.json, lit_table.md, and C07/C08/C26. It then opened eleven additional C## cards while reconsidering the gap and pattern.

The turn timing is decisive:

- 17:28:12–17:34:49: 6.6 minutes thinking before the next Read.
- 17:34:50–17:39:28: 4.6 minutes thinking.
- 17:39:28–17:47:37: 8.1 minutes thinking.
- 17:47:39–17:55:16: 7.6 minutes thinking.
- 17:55:16–18:05:35: 10.3 minutes thinking.
- phase2_select_output.json was not written until 18:06:08, 38.3 minutes after the seat started.
- phase2_generate_output.json followed at 18:12:07.

The output was not larger than the old outputs. The extra time was deliberation under effective max effort plus a broader retry search over pattern cards. Each fresh call also received another approximately 83,000-character inlined prompt; the two CCF invocations together re-sent 166,971 prompt characters.

### Phase 2.3: real engineering work, repeated because of interruption

Completed attempt-1 agent a67f23c6 ran from 16:08:22 to 16:49:33:

- 21 Reads, 8 Bash calls, 7 Writes, 3 Edits, and StructuredOutput: 40 tools.
- It read trace.out four times, check_out.out three times, and request_builder.py, task.py, and observation.py twice each.
- It wrote trace.py three full times and phase2_coherence_output.json twice: first 67,259 characters, then 59,293 characters, followed by edits.
- Approximately 26.6 minutes were spent in explicit thinking and 14.0 minutes in generating tool calls/writes.
- It found substantive problems. This was not empty work: the later K3 audit used its two blocking findings to abandon the candidate.

The report's patch entry 2 used append_items for core_mechanism_steps but supplied a string. At 16:50:03–16:50:21, runner a9e4ae34 invoked phase3_merge_revisions and received “append_items: value must be a list, got str.” The run stopped instead of asking the producer seat to repair its shape.

The retry candidate then received two more Phase 2.3 calls:

| Agent | Time | Minutes | Actions | Ending |
|---|---|---:|---|---|
| acd95b48 | 18:13:29–18:37:56 | 24.4 | 15 Reads, 5 Python Bash calls; task.py read 5 times, contracts.py twice; no report Write | Request interrupted by user |
| a4e68c50 | 18:37:56–18:57:48 | 19.9 | 13 Reads, 2 Python Bash calls, one 8,302-char trace.py Write; task.py read 5 times, contracts.py twice | Request interrupted by user |

Across those two calls, the same retry candidate caused 10 Reads of task.py, 4 of contracts.py, and two each of the generated candidate, selection, substrate, session_verifier.py, and observation.py. They consumed 44.3 model-minutes and produced no phase2_coherence_output.json.

The interruptions themselves are incidental. The failure to resume at the missing coherence gate is a workflow correctness defect.

### The seven Sol failures

At 16:58:06, K3 agent a7e54a8b and the Sol second-auditor lane began in parallel. K3 finished at 17:09:56 with a valid abandon verdict. Sol did not finish until the harness/workflow had emitted seven failed agents:

| Agent | Time | Minutes | End |
|---|---|---:|---|
| a62b8b4d | 16:58:06–17:02:09 | 4.1 | Prompt is too long |
| a7b37eec | 17:02:09–17:06:32 | 4.4 | Prompt is too long |
| aae4cbdb | 17:06:32–17:10:34 | 4.0 | Prompt is too long |
| a582e10f | 17:10:34–17:15:24 | 4.8 | interrupted during the same failure chain |
| af81f9f5 | 17:15:24–17:18:52 | 3.5 | Prompt is too long; compaction failed |
| a6e8fa07 | 17:18:52–17:22:56 | 4.1 | Prompt is too long |
| adb3d1c5 | 17:22:56–17:26:39 | 3.7 | Prompt is too long; compaction failed |

Each received the same 63,578-character prompt: 445,046 duplicate prompt characters across the seven attempts. They made 104 Read calls and wrote nothing:

| File | Read calls across seven Sol agents |
|---|---:|
| phase3_collision/collision_hits.json | 52 |
| phase2_coherence/refined_candidate.json | 14 |
| phase2_select/phase2_select_output.json | 10 |
| phase0/lit_table.md | 10 |
| phase2_coherence/blocking_findings.json | 10 |
| C07.md | 7 |

The attempt-1 collision file was 283,451 bytes and 2,347 lines; lit_table.md was about 70 KB; refined_candidate.json was 38.6 KB; blocking_findings.json was 12.3 KB. The static audit prompt was already about 63.6 KB. The lane repeatedly paged the collision file and, after compaction/retry, often restarted at offset zero. This is a design-sized prompt/input problem amplified by harness retry behavior.

The total Sol agent time was 28.6 minutes. Since K3 legitimately needed 11.8 minutes, the parent waited an avoidable additional 16.7 minutes after K3 had finished.

### Resume-cache replay at 19:05

This is the most important correctness bug in leg 2:

1. The first-cycle Sol audit calls used journal key v2:2ee4... at 16:58.
2. After the second interrupted Phase 2.3 and the 7.2-minute pause, a8081db6 started at 19:05:02 with the identical v2:2ee4... key. No new K3 primary audit started.
3. The archived K3 structured result was replayed by prompt identity, but its phase3_critique_output.json had been moved into attempt_1 and was not recreated in the current run directory.
4. a8081db6 found refined_candidate.json and blocking_findings.json absent, fell back to the raw phase2_generate_output.json, made 21 Reads, and wrote only second_opinion.json after 10.4 minutes.
5. Runner a62cfaf5 at 19:15:24 failed AUDIT_MERGE_PY with FileNotFoundError for phase3_critique_output.json.
6. Runner abb3752c then reported the primary output unreadable. Only then did the workflow launch fresh aa7e2a7e and af4bb323 at 19:16:13.

The orphan audit plus the two failure runners cost 11.2 minutes. More seriously, the final candidate never received a completed Phase 2.3 coherence report. Both final auditors explicitly recorded that refined_candidate.json and blocking_findings.json were absent and audited the Phase 2.2 fallback. The run finished, but its final idea did not traverse the intended gate.

### Phase 6: repository crawl, enormous writes, then a full rewrite

Initial spec agent a6573b32 ran from 20:26:54 to 21:20:16:

- 35 Reads, 18 Globs, 21 Greps, 18 Writes, one Edit, and StructuredOutput: 94 tools.
- It searched not just BRIEF.repo, /home/lingxufeng/ccf/Repo/PhyAgentOS-core, but the CCF workspace, Repo/openvla, Repo/LIBERO, bin, .research tools, launchers, instruments, and pre-existing spec files.
- It wrote 541,144 characters. index.json was written twice; B1 and B2 twice; B3, B4, B5, and B6 three times each. The first B1 appeared at 20:41:22, but the seat continued for another 38.9 minutes.
- Its time split was approximately 13.3 minutes explicit thinking, 37.7 minutes generating tool calls and large write payloads, and 2.3 minutes text/other.

At 21:20:16, spec_check runner a6cb548b rejected the result. Most findings were “change file not found” or “run_cmd script not found” for files the proposed block itself was supposed to create, plus arm-name and SMOKE issues.

Repair agent aa09a10b ran from 21:20:37 to 22:10:53:

- 29 Reads, 16 Globs, 20 Greps, 8 Writes, one Edit, and StructuredOutput: 75 tools.
- It re-read the evidence plan, method view, implementability report, substrate, intake, contracts, engine, request builder, session verifier, schema, tools, instruments, launch wrappers, and verdict checker.
- It wrote another 231,230 characters: B1 twice, then B2–B6 and index once each.
- Approximately 31.1 minutes were explicit thinking and 17.0 minutes generated tool/write payloads.

Together the two seats made 169 tool calls and emitted 772,374 characters through Write. The repair's own final note says the root cause: the previous specs treated phantom future files as existing changes. This was a contract/checker mismatch, not a need to rediscover the scientific plan.

The old trajectory has no corresponding Phase 6 seat. This single new stage consumed 103.7 seat-minutes, 24.3% of all CCF seat-minutes and 25.5% of the CCF active wall time.

### Phase 4.1.5 was not the problem

ac6adcfa ran from 19:52:16 to 20:13:12. It received a 15,349-character prompt, read method_view.json once, spent about 19.2 minutes thinking, wrote one 38,708-character phase4_implementability.json, and returned. Its only tools were Read, Write, and StructuredOutput.

That is a long single inference, but the old equivalent seats took 32.9 and 56.0 minutes and used 9 and 15 tools. Changing 4.1.5 is not a priority based on this evidence.

### Global repeated Reads

Across all CCF seats there were 364 Read calls over 90 distinct paths, versus 140 over 56 paths in the earlier run.

| Most-read CCF path | Calls | Distinct agents |
|---|---:|---:|
| phase3_collision/collision_hits.json | 73 | 11 |
| phase2_coherence/refined_candidate.json | 21 | 11 |
| phase2_select/phase2_select_output.json | 20 | 15 |
| phase0/lit_table.md | 19 | 15 |
| PhyAgentOS/forge/task.py | 18 | 6 |
| phase2_coherence/blocking_findings.json | 18 | 11 |
| C07.md | 13 | 13 |
| shared/substrate.md | 10 | 10 |
| verification/contracts.py | 8 | 6 |
| phase2_generate/phase2_generate_output.json | 8 | 7 |

Some repeated calls were legitimate pagination. The expensive pattern was fresh-seat duplication: every audit reread the candidate, selection, collision corpus, and blocking findings, and every retry received the entire inlined static prompt again.

## 2. Repeated and wasted work

| Repeated work | Agents and minutes | Cause | Assessment |
|---|---|---|---|
| Phase 0 missing-paper repair | aff9a335, 1.4 min | One shard omitted one paper | Bounded repair; minor |
| Phase 2.1+2.2 twice | a6c5ba3e 22.2 + acf8d456 44.8 = 67.0 min | RS abandon-to-retry policy | Intentional design repetition; second call was the added cost |
| Phase 2.3 across two candidates | a67f23c6 41.2 + acd95b48 24.4 + a4e68c50 19.9 = 85.5 min | First candidate then RS retry candidate | First call useful; later 44.3 min lost to user interrupts |
| Same retry-candidate Phase 2.3 twice | acd95b48 24.4 + a4e68c50 19.9 | seat retry after first interruption | Incidental/user-triggered; workflow should nevertheless resume safely |
| Primary Phase 3.2 twice | a7e54a8b 11.8 + aa7e2a7e 9.6 = 21.4 agent-min | One audit per candidate | Intended by abandon retry |
| Sol second-auditor failure chain | seven agents, 28.6 agent-min | Oversized prompt/files plus harness retries and workflow retry | Avoidable; 16.7 min critical-path penalty |
| Orphan second audit | a8081db6 10.4 + runners 0.8 = 11.2 min | prompt-key replay after archive/resume | Workflow bug and gate-bypass risk |
| Final second audit | af4bb323 14.9 in parallel with aa7e2a7e 9.6 | New dual-auditor design | 5.3 min critical tail in this successful cycle |
| Phase 6 generate then repair | a6573b32 53.4 + aa09a10b 50.3 = 103.7 min | Checker/prompt disagreed about future files; repair instructed whole-file rewrite | Workflow contract bug amplified by repo crawl |
| Initial Phase 2.3 report rewrites | a67f23c6 wrote report twice and trace.py three times | 40 KB guidance versus self-contained evidence requirements | Prompt/output-budget tension |
| Phase 6 intra-seat rewrites | 26 Write calls, 772,374 chars | Agent self-revision plus whole-file repair | Avoidable output churn |
| Merge failure and new leg | failed a9e4ae34 runner 0.3 min; about 6.3 min until new leg, then 1.5 min reprobe | append_items string rejected; no producer self-heal | Workflow bug; direct delay about 7–8 min, plus operational split |
| verify/next runner pattern | 54 calls, 22.8 agent-min total; 10.0 min in leg 2 | one fresh runner seat around every deterministic transition | Designed overhead, but not the primary blow-up |

The ResearchStudio retry deserves a precise distinction. a7e54a8b did not randomly reject the first idea: it upheld two executed blocking findings from a67f23c6 and said the mechanism required redesign. next_step.py lines 599–617 then intentionally archived Phase 2–3 and reran Phase 2.1+2.2. That behavior explains the full second cycle. Whether it is too coarse is a policy question, addressed in the recommendations.

## 3. Design causes versus run-specific incidents

| Category | Cause | Evidence and effect |
|---|---|---|
| Workflow design | Fresh context for every seat | Preserves independence, but duplicates all input Reads and static prompts. CCF had 364 Reads; the 83 KB Phase 2 prompt and 63.6 KB audit prompt were resent on retries. |
| Workflow design | verify → next and deterministic steps use runner sub-agents | 54 runner calls and 22.8 agent-minutes. Leg-2 wall contribution was 10.0 minutes, about 3.3% of active time. |
| Workflow design | Phase 3.2 waits for both auditors | K3 finished at 17:09:56, but parallel did not return until the Sol failure chain ended at 17:26:39. |
| Workflow design | Second auditor originally received the full audit input | Seven failures, 104 Reads, 28.6 agent-minutes. The 283 KB collision file dominated. |
| Workflow design | Any first abandon redoes Phase 2.1 and Phase 2.2 | acf8d456 spent 38.3 minutes before writing the new selection, even though the audit's language primarily indicted the mechanism. |
| Workflow design | Phase 6 writes every block eagerly | Six B files plus index, although the experiment launcher immediately claims only B1. First B1 existed after 14.5 minutes; full generate/repair consumed 103.7. |
| Workflow design | Phase 6 exploration was open-ended | a6573b32 used 74 repository-discovery calls before counting Writes. Time grows with repository/workspace breadth and with the number of evidence blocks. |
| Workflow design | Prompt and report contracts are very large | Phase 2.1 prompt approximately 83 KB; audit approximately 63 KB; Phase 6 approximately 28 KB, before Read results. The 2.3 contract also asks for self-contained executed evidence while suggesting 40 KB. |
| Repository/run-specific | The first candidate really failed its executed coherence findings | Legitimately triggered RS's designed retry. |
| Repository/run-specific | PhyAgentOS-core lacks bin, results, configs, gateway, and eval launcher files | Exposed the spec schema's inability to distinguish existing files from block-created files. |
| Repository/run-specific | The substrate spans PhyAgentOS-core plus LIBERO, OpenVLA, workspace launchers, and future gateway code | Caused the Phase 6 seat to escape BRIEF.repo and crawl the whole CCF workspace. |
| Repository/run-specific | Two owner interruptions of Phase 2.3 | Lost 44.3 model-minutes and introduced a 7.2-minute pause. |
| Harness/run-specific | Effective effort=max ignored per-seat effort | Inflated deliberation, particularly acf8d456's 341.6k thinking tokens and Phase 6. |
| Harness/run-specific | Prompt-too-long calls retried repeatedly | Turned one bad Sol request into seven agents. |
| Workflow bug triggered by resume | Cache identity was prompt text while attempt paths were reused | Replayed an archived primary audit result after its file had moved, then ran a second auditor against missing coherence artifacts. |
| Workflow bug triggered by malformed output | Consumer failure aborted instead of repairing producer | Split the run after a simple append_items type error. |

Repository size alone is not the explanation. The old and CCF literature result sets were similar, 130 versus 132 papers, and old collision files were also about 246–266 KB. The blow-up came from feeding those large files to a newly added second auditor, allowing Phase 6 to explore a multi-repository workspace, and serially retrying work.

## 4. Leg 2 critical path

| UTC interval | Wall minutes | What waited on what |
|---|---:|---|
| 16:56:38–16:58:06 | 1.5 | Restart probes and navigator runners |
| 16:58:06–17:26:39 | 28.6 | K3 and Sol started together; K3 ended at 17:09:56, parent waited another 16.7 min for failed Sol retries |
| 17:26:39–17:27:48 | 1.2 | verify, archive attempt_1, rerun next, phase2_prepare |
| 17:27:48–18:12:34 | 44.8 | Serial Phase 2.1+2.2 retry, acf8d456 |
| 18:12:34–18:13:29 | 0.9 | verify, collision launch, stale-output cleanup |
| 18:13:29–18:57:48 | 44.3 | Two serial Phase 2.3 attempts, both interrupted |
| 18:57:48–19:05:02 | 7.2 | Explicit workflow pause before owner resume |
| 19:05:02–19:15:24 | 10.4 | Cache-replayed orphan Sol audit a8081db6 |
| 19:15:24–19:16:13 | 0.8 | failed audit merge, then output verification |
| 19:16:13–19:31:06 | 14.9 | Fresh K3/Sol pair; K3 ended at 19:25:48, parent waited for Sol until 19:31:06 |
| 19:31:06–19:32:06 | 1.0 | audit merge, verify/next, revise-brief prep |
| 19:32:06–20:26:16 | 54.2 | Strict serial chain: 3.3 → 4.fill → 4.derive → 4.1.5 → validation → Phase 5, including runners |
| 20:26:16–20:26:54 | 0.6 | plan_check and empty-spec precheck |
| 20:26:54–21:20:16 | 53.4 | Phase 6 initial spec seat |
| 21:20:16–21:20:37 | 0.3 | spec_check rejects |
| 21:20:37–22:10:53 | 50.3 | Phase 6 repair seat |
| 22:10:53–22:11:19 | 0.4 | final spec_check |

### Critical-path accounting

Leg-2 wall time from the TSV is 314.7 minutes. Subtracting the 7.2-minute pause gives 307.5 active minutes, matching the owner's approximately 5 h 05 min figure within timestamp/rounding differences.

- Critical-path model waits: approximately 297.3 minutes.
- Runner calls: 10.0 minutes.
- Explicit pause: 7.2 minutes.

Within the 297.3 model minutes, 124.8 minutes were known retry/invalidated work:

- 16.7 minutes waiting after K3 for the failed Sol chain.
- 44.3 minutes in the two interrupted Phase 2.3 attempts.
- 10.4 minutes in the orphan cache-replayed Sol audit.
- 53.4 minutes in the initial Phase 6 pass rejected by spec_check.

The remaining 172.5 minutes produced the surviving route's artifacts or its necessary abandon decision: the first K3 verdict, the second Phase 2 generation, final audit pair, Phase 3.3–5, and the valid Phase 6 repair. Even that number is not a clean lower bound, because the final route skipped a required completed Phase 2.3. A semantically correct route would need another completed coherence gate, budgeted by the source at about 25 minutes and observed here at 41.2 minutes.

A clean leg 2 that retains the abandon retry but removes the observed incidents would therefore still be roughly 3 h 25 min to 3 h 45 min: K3 abandon, 44.8-minute regeneration, one 25–41-minute coherence gate, a 15-minute audit, about 101 minutes for Phase 3.3 through one valid Phase 6 pass, and runners. This is the design-level reason the run can remain long even after bugs are fixed.

The runner architecture is worth optimizing, but it is not a plausible primary explanation: it was 10 minutes out of 307.5 active leg-2 minutes.

## 5. Ranked recommendations

Savings estimates are wall minutes per k=1 Brain run. They overlap and should not be summed mechanically.

| Rank | Recommendation | Specific code/prompt | Estimated saving | Status and rationale |
|---:|---|---|---:|---|
| 1 | Make Phase 6 two-stage: Brain emits index + B1 only; materialize B2–B6 lazily when the experiment navigator reaches them. Keep full evidence_plan coverage in index. | BANK.spec around brain.logic.js lines 95–129; Phase 6 loop around lines 1118–1145 | 20–35 min normally; about 50 min in this run | First B1 existed after 14.5 min, while full initial generation took 53.4. The repair spent about 18 more minutes after its final B1 to write B2–B6/index. This is the largest remaining structural cut. |
| 2 | Add typed retry_scope to the Phase 3.2 verdict: mechanism_only reruns Phase 2.2 using the existing Phase 2.1 selection; gap_invalid reruns 2.1+2.2; bottleneck_invalid follows the existing higher-level path. | next_step.py lines 599–617 and critique output schema; route ideate_generate separately in driveRun | 25–35 min on mechanism-only abandons; 0 on clean runs | The first audit said the mechanism required redesign, not that the bottleneck was wrong. acf8d456 spent 38.3 min before rewriting Phase 2.1 selection and only about 6 min on Phase 2.2 afterward. Preserve full reselection when the audit explicitly indicts the gap. |
| 3 | Enforce, rather than merely request, mapped Phase 6 tools: deny Glob/Grep for spec and provide a typed map covering the primary repo, allowed external repos, workspace launchers, and NEW outputs. | DENY.spec line 52, TOOLS.spec line 584, repo-map construction around line 1120, SPEC_CHECK_PY lines 200–268 | 8–20 min per spec pass; more on large workspaces | Current source says “never Glob/Grep” but still grants both tools. Also, the current map is rooted only at BRIEF.repo while the CCF substrate legitimately spans OpenVLA, LIBERO, bin, and .research. |
| 4 | Keep the compact one-file second-auditor packet and no-retry behavior; fail open to K3 when the second lane cannot fit or return. Cap the packet by tokens, not only characters. | SECOND_PACKET_PY around line 364; SEATS.audit_second line 604; parallel call around lines 916–928 | 16.7 min in the first CCF audit; about 5.3 min in the successful second audit; 28.6 agent-min | This has already landed in current brain.logic.js. It should be retained and validated in the next trajectory. Do not restore full lit_table/fulltext access to Sol. |
| 5 | Make seat cache identity attempt-safe and make gate completion a filesystem invariant: an audit may not run unless the current attempt has a verified phase2_coherence_output.json/refined_candidate.json or an explicit pass marker. Never silently fall back to raw Phase 2.2 after an interrupted 2.3. | seatPrompt around line 678; driveRun lastSeat verification around lines 970–985; Phase 3.2 entry in next_step.py | 11.2 min in this run; potentially 40+ min and a correctness failure on interrupted resumes | The SEAT #n position stamp has landed. Add attempt UUID/content hash and assert current output existence before accepting any cached structured result. |
| 6 | Give Phase 2.3 a deterministic scaffold: pre-extract cited repository slices, provide a standard trace template and typed patch builder, require one script/one execution/one final report, and validate patch operand types before the RS merge. | SEATS.coherence around line 602; TOOLS.exec line 582; consumer self-heal around line 1010 | 10–20 min per completed 2.3; 6–8 min incident avoidance | a67f23c6 used 40 tools, rewrote trace.py/report repeatedly, then failed on a simple list-versus-string shape. The post-run consumer self-heal is good; pre-merge shape validation is cheaper. |
| 7 | Run deterministic commands directly in the workflow runtime, or batch adjacent commands, instead of allocating a model runner seat for every verify/next/check transition. Preserve the exact rc sentinels and validators. | nextEmit line 548, runThenNext line 564, prep line 573 | 6–10 min on a clean k=1 run; upper bound 22.8 min in the full CCF run | Runner overhead was small but entirely infrastructural. The checks should remain; only the LLM shell wrapper should disappear or be batched. |
| 8 | Enforce effective effort at launch and record requested versus effective effort in the workflow result. Default the launcher to high; reserve max for explicitly selected seats. | seat function around line 695 plus launcher environment/preflight | roughly 20–45 min on Opus-heavy clean runs, overlapping other savings | t1 shows Phase 2.1+2.2 at max taking 36.6 min on the old repo versus 16.3 min in the earlier run. This is a multiplier, not the root cause. |
| 9 | Add hard output budgets and patch-only repair schemas for large artifacts. A repair seat should receive a machine-readable finding list and only the affected JSON files, not the original full upstream input set. | Phase 5/6 repair loops around lines 1097–1145; BANK.spec | 10–25 min when a check fails | Current prompt text now says PATCH, but Write still sends full files. A deterministic JSON patch application layer would make the constraint real and avoid 772 KB of rewrite traffic. |

### Fixes already present in the current source

The current brain.logic.js is post-run code. At inspection time it already includes:

- one producer-repair pass when a deterministic consumer rejects its output;
- compact one-file audit_second input and retry=false;
- a repository map, function=NEW handling, patch-oriented repair notes, and medium requested effort for Phase 6;
- a seat position stamp intended to defeat prompt-only resume replay;
- brain.done.json so experiment launch does not mistake a mid-repair spec/index.json for completion.

These are directionally correct. They do not yet prove the next run will be fast, especially because DENY.spec still allows Glob/Grep, the map covers only BRIEF.repo, and Phase 6 still eagerly writes every block.

## What not to change

1. Do not merge Phase 2.3 into the Phase 2.1+2.2 author context. Fresh adversarial context found real, load-bearing defects in the first candidate.
2. Do not remove deterministic verify/next, plan_check, spec_check, or merge validation. Move them out of LLM runner seats or batch them, but keep fail-closed checks.
3. Do not weaken spec_check to accept arbitrary nonexistent paths. Represent block-created files explicitly as NEW and validate their parent/output contracts.
4. Do not eliminate the Phase 3.2 audit or allow the second auditor to abandon alone by default. K3 ownership with a compact second opinion is the sound design.
5. Do not delete abandon-to-retry wholesale. Make its scope typed so mechanism failures do not automatically redo gap selection, while true gap/bottleneck failures still get the larger retry.
6. Do not prioritize Phase 4.1.5 optimization. The CCF seat was faster than both old equivalents.
7. Do not treat lower effort as sufficient remediation. It reduces inference time but leaves all structural repetition and correctness bugs intact.

## Bottom line

The run did not merely “think harder.” It ran a materially larger workflow than the old comparison: a second auditor and Phase 6 had been added, the first candidate was intentionally abandoned, the second candidate's coherence gate was interrupted twice, resume caching replayed the wrong logical seat, and the spec contract forced a full repository crawl plus full rewrite. The largest direct observed costs were Phase 6 at 103.7 minutes, the second Phase 2–3 cycle, 44.3 minutes of interrupted coherence work, and the Sol/replay failures.

After the already-landed fixes, the next high-value design changes are lazy B1-only Phase 6, typed retry scope, hard tool restrictions plus a multi-root repository map, and a filesystem-enforced coherence-gate invariant. Those changes preserve the research quality controls while removing the work that was demonstrably duplicated.

## 20-line summary

1. The earlier run delivered two ideas in 216.5 minutes; CCF used 406.6 active minutes to deliver one.
2. Per delivered idea, wall-clock throughput became 3.76 times worse.
3. CCF used 35 seat calls versus 21 in the old k=2 run.
4. Runner overhead was only 22.8 agent-minutes total and 10.0 wall minutes in leg 2.
5. Max effort materially slowed Opus calls, but it cannot explain the repeated stages or new stages.
6. Phase 2.1+2.2 rose from a 16.3-minute old mean to 22.2 and 44.8 minutes in CCF.
7. acf8d456 spent about 41 of 44.8 minutes thinking and did not write Phase 2.1 until minute 38.
8. Completed CCF Phase 2.3 took 41.2 minutes, faster than the old 45.6/73.5-minute calls.
9. The retry candidate's two Phase 2.3 calls, acd95b48 and a4e68c50, lost 44.3 minutes to user interrupts.
10. The first CCF candidate was legitimately abandoned after a7e54a8b upheld two executed blocking findings.
11. ResearchStudio then intentionally reran Phase 2.1+2.2 and the Phase 2–3 gauntlet.
12. Seven Sol agents from 16:58 to 17:26 made 104 Reads and failed on prompt length.
13. Those failures added 16.7 critical-path minutes after K3 had already finished.
14. Resume replay at 19:05 ran orphan a8081db6 and bypassed the missing coherence artifact.
15. The surviving idea was audited from raw Phase 2.2 because no completed retry-cycle Phase 2.3 output existed.
16. Phase 6 was absent from the old run and cost 53.4 + 50.3 = 103.7 minutes in CCF.
17. Its two seats made 169 tool calls and wrote 772,374 characters across repeated full files.
18. Phase 4.1.5 was not a regression: ac6adcfa took 20.9 minutes versus the old 32.9/56.0.
19. Highest-value remaining cuts are lazy B1-only Phase 6, typed retry scope, hard mapped spec tools, and gate-safe resume identity.
20. Keep fresh adversarial seats and deterministic validators; remove duplicated inputs, whole-file repairs, and model-wrapped shell overhead.
