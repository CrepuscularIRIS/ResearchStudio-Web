# Codex 独立审计：Brain 第一次 live run（wf_00a3a165-dcd，2026-09-06）

> 来源：Codex CLI 只读线程 01a07a57-fd57-7cd2-ab60-fecd18c84011，2026-09-07 落地；原文照录，未删改。分诊见 `2026-09-06-v9-brain-rs-architecture.md` §9e。

Audit complete: all 74 trajectories were reviewed—21 seats segment-by-segment and 53 runner calls against their raw Bash and structured outputs. No file was modified.

Historical-source boundary: `brain.workflow.js` was edited after this run. Contrary to the supplied path note, `workflows/scripts/` contains only `model-probe-wf_4b08a2ce-50e.js`; no archived Brain script exists there. The authoritative executed source is the `.script` field in [wf_00a3a165-dcd.json](/home/lingxufeng/.claude/projects/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/workflows/wf_00a3a165-dcd.json:1). “Executed line” below means the logical line after splitting that field on newlines.

The current [brain.workflow.js](/home/lingxufeng/workspace/.claude/workflows/brain.workflow.js:36) already adds explicit effort, `args.models`, `args.stagger`, `REPOSITORY`, `disallowedTools`, `bashCommandClamp`, stop-before-next execution, exit-aware polling, and a working tagging retry. I identify those fixes as already applied below.

## Findings

1. Unsupported engineering/audit models plus inherited `max` effort dominated the critical path. [A, E]

   - File/agents: executed `brain.workflow.js`; coherence agents `a44ca5ed0086bb59c`, `a588c5b37d6c276d5`; implementability agents `a3473b61133ef2784`, `a814e9b266d6dc725`.
   - Evidence:
     - Executed line 31: `"const MODEL = { opus: 'claude-opus-5', glm: 'glm-5.3[1m]', k3: 'k3-256k' }"`.
     - [`a44…txt`](/tmp/claude-1000/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/scratchpad/traj/r1_Phase_2.3_coherence_gate_dry-run_trace_AND_launch_3.1_collision_in___a44ca5ed0086bb59c.txt) @ 0s: `"requested=glm-5.3[1m] served=['claude-fable-5-1'] duration=73.5min ... output_tokens=258448"`.
     - [`a588…txt`](/tmp/claude-1000/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/scratchpad/traj/r2_Phase_2.3_coherence_gate_dry-run_trace_AND_launch_3.1_collision_in___a588c5b37d6c276d5.txt) @ 0s: `"requested=glm-5.3[1m] served=['claude-fable-5-1'] duration=45.6min"`.
     - [`a814…txt`](/tmp/claude-1000/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/scratchpad/traj/r2_Phase_4.1.5_implementability_audit__a814e9b266d6dc725.txt) @ 0s: `"duration=56.0min ... output_tokens=199507"`.
   - Defect: the script assumed LiteLLM-only IDs would resolve. On this Anthropic session they silently fell back to the session model and effort. The fallback was accepted as success, turning two engineering reviews into frontier-model, maximum-effort generations.
   - Fix: in executed line 31 and `seat()` executed lines 3071–3079, require environment-valid model IDs or fail before spawning. Require explicit effort for every seat and log requested model, served model, and effort. Keep engineering seats at low/medium effort with an elapsed/stall bound.
   - Current status: partially applied at current lines 36 and 3099 via `args.models` and explicit effort. A fail-fast served-model check is still needed; the unsupported IDs remain defaults.

2. The two coherence seats escaped their tool discipline and spent 46–74 minutes doing repository archaeology, reruns, and self-validation. [A, B, C, E]

   - Evidence:
     - Executed line 2969 allowed Bash only for Python scripts under `WORKDIR`.
     - R1 @ 2926s: `"TOOL_USE Bash: ... grep ... docs/refs/rs/scripts/run.py"`.
     - R1 @ 2933s: `"TOOL_USE Bash: sed -n 236,280p /home/lingxufeng/workspace/repos/DFormer/..."`.
     - R1 @ 2933s: `"TOOL_RESULT ERROR ... No such file or directory"`.
     - R1 then searched/read the repository at 2939s, 2941s, 2943s, 3196s, and 3224s.
     - R1 rewrote and reran `t2_dryrun.py` at 3355/3358s, 3515/3520s, and 3785/3792s.
     - R1 @ 4341s: `"Write ... phase2_coherence_output.json content=100952"`.
     - R1 @ 4385s: `"Write ... validate_report.py"`.
     - R2 @ 2345s: `"TOOL_USE Bash: sed -n '31,80p' .../t2_dryrun.out"`.
     - R2 wrote extra validators at 2687s and 2710s and edited the report seven times at 2348, 2351, 2354, 2414, 2446, 2537, and 2679s.
   - Defect: prose-only tool restrictions were not enforced. R1 performed unrelated shell inspection and repo discovery; both seats created validators beyond the requested artifact and produced 100 KB-class reports. R1’s final structured result named only the JSON while admitting scratch files in `note`; R2’s `written` listed five artifacts although the navigator named one output.
   - Fix: in `seat()` executed lines 3071–3079, mechanically deny search/web/Edit and clamp Bash to `python3 <WORKDIR-path>`. Validate `written` against the named output plus an explicitly allowed scratch manifest. Redesign `coherence_trace` to emit a compact finding/patch schema with a hard size cap instead of embedding large scripts and stdout.
   - Current status: mechanical `disallowedTools` and `bashCommandClamp` are now applied at current lines 3099–3100. Output-size and artifact-manifest validation remain unfixed.

3. Implementability seats used the target JSON as an output stream, causing 5–8 minutes of serial Edit churn after already-long model stalls. [B, E]

   - Evidence:
     - Executed line 2978: `"Write each output artifact in full"`.
     - R1 @ 4s read the method view, then had no tool event until 803s and 1399s; first Write at 1498s; Edits at 1658, 1791, 1915, and 1944s; completion at 1976s.
     - R2 @ 4s read the method view, then events only at 809, 1609, 2410, and 3016s; first Write at 3048s.
     - R2 performed ten Edits at 3076, 3101, 3122, 3149, 3177, 3199, 3229, 3257, 3296, and 3319s.
     - R2 @ 3104s: `"Each remaining append replaces the same end marker, so they must go one at a time."`
     - R2 @ 3126s: `"Every append rewrites the same single end marker... one per call."`
   - Defect: the seat violated the one-full-Write contract and serialized ten dependent editing turns. Its raw result explicitly blamed an output cap. Simply denying Edit without shrinking or sharding the required report would convert this waste into a seat failure.
   - Fix: change the implementability prompt/output contract to one bounded record per method step, launch independent step shards, and deterministically merge them; or impose a concise per-step field limit that fits one Write. Reject partial-marker output.
   - Current status: Edit is now mechanically denied, but the oversized output contract still needs redesign.

4. Multiple seats claimed to read every input but actually consumed only selected portions; downstream outputs were accepted anyway. [B, C]

   - Phase 1:
     - @ 46s: `"Read ... lit_results.json offset=None limit=120"`.
     - Further reads were only offsets 600/260, 1480/300, 548/28, 1320/80, 2430/190, and 574/26. Large ranges were never read.
   - Phase 4.fill:
     - R1 skeleton reads: @ 3s default read ending at line 632, @ 12s offset 2280 ending at 2415, @ 34s offset 1180 ending at 1209. Lines 633–1179 and 1210–2279 were omitted.
     - R2 similarly read lines 1–649, 1200–1249, and 2280–2359 only.
   - Phase 4.derive:
     - R1 @ 5s: `"Read ... phase4_expansion.json offset=None limit=None"`; the raw result ends at line 256, while the artifact has 2,807 lines.
     - R2’s corresponding result ends at line 261 of 2,751.
   - Evidence planning:
     - R1 expansion coverage ended at line 639 of 2,807.
     - R2 covered 1–671 and 2560–2752, omitting 672–2559.
     - R1 implementability first failed at 41s with `"File content (34156 tokens) exceeds maximum allowed tokens (25000)"`, then recovered only through lines 1–79 of the 90-line file.
   - Defect: executed line 2977 required full reads, but ordinary `Read` calls silently returned size-limited prefixes. The prompt supplied giant skeletons/expansions containing bibliography and unrelated sections, making compliance expensive and easy to misjudge. Derive and evidence outputs were therefore based on incomplete source material.
   - Fix: have `run.py next` emit task-specific views:
     - `phase4_fill_view.json`: TODO paths plus only their required context.
     - `derive_view.json`: the seven source fields to translate/re-register.
     - `evidence_view.json`: claims, method flow, falsification, baselines, compute, and reviewer concerns only.
     - Add expected line/record counts to each INPUT and validate read coverage or use structured extraction.
   - Current status: not applied.

5. The retry mechanism never triggers for the failure modes actually observed. [A]

   - Evidence:
     - Executed lines 3076–3079: `"if (!r || !r.ok) ... retrying once"`.
     - Coherence and implementability seats returned `ok:true` despite forbidden tools, incomplete reads, extra artifacts, huge outputs, and 45–74 minute durations.
     - No `"retrying once"` entry appears in the workflow journal.
   - Defect: retry is based solely on the seat’s self-reported boolean. It does not inspect artifact existence, schema, named paths, size, tool history, elapsed time, or whether the file was written completely.
   - Fix: after `agent()` in `seat()`, validate exact output paths, JSON/schema, file size, mtime, allowed tool trace, one-Write policy, and seat deadline. Convert validation failure into a fresh-context retry and reject the second failure.
   - Current status: not applied.

6. Navigator NOTES told seats to run commands that had already been run—or were omitted from their prompt. [C]

   - Evidence:
     - Coherence raw prompts state: `"launch the RUN command in the BACKGROUND first"`, while the seat’s RUN section contained no collision command; executed `runSeat()` had already launched it at lines 3223–3224.
     - Ideation/revision NOTES state `"Run the RUN command first"` although executed `runSeat()` lines 3216–3220 ran the prep commands and did not include those commands in `dyn.run`.
     - R2 coherence’s final note says: `"The NOTES' parallel action ... is outside this seat's tool contract ... and was not performed"`.
   - Defect: the seat received mutually inconsistent instructions. This run succeeded because seats ignored or rationalized the stale NOTES.
   - Fix: in `runSeat()` executed lines 3215–3228, rewrite navigator NOTES after orchestration: “prep completed successfully by workflow” and “collision already launched by workflow.” Do not pass an imperative for an absent command.
   - Current status: not applied.

7. Historical prompts omitted the repository root even though `substrate.md` contained repository-relative paths. [C, B]

   - Evidence:
     - `_shared/substrate.md:26`: `"repos/DFormer/models/encoders/DFormerv2.py"`.
     - R1 coherence @ 2933s resolved this as `/home/lingxufeng/workspace/repos/DFormer/...` and failed.
     - @ 2941s it searched and found `/home/lingxufeng/workspace/ugra-rgbd-robust/repos/DFormer/...`.
     - Executed `runSeat()` line 3226 built `dyn` without `repo`.
   - Defect: seats were told to verify repository-relative claims but were given only `SKILL_DIR` and `RUN_DIR`.
   - Fix: pass `repo: BRIEF.repo` from `runSeat()` and state that substrate-relative paths resolve under `REPOSITORY`.
   - Current status: applied at current lines 3002, 3087, and the current `runSeat()` construction.

8. `runThenNext()` advanced the navigator after failed commands, and the advertised two-retry validation policy did not exist. [A]

   - Evidence:
     - Executed lines 2959–2960: command bodies are joined with `"; "` and then `"; " + nextCmd(rd)` unconditionally.
     - Failure is checked only later at executed lines 3245–3249.
     - `next_step.py:852–854`: `"On a validate fail: fix only the named contract and re-validate — cap 2 retries, then render as-is with a caveat note"`.
     - Executed line 3249 only assigns `st.validate_rc`; there is no repair seat, retry counter, or caveat artifact.
   - Defect: a failed state-mutating command could still make `next` inspect partial state and emit the wrong subsequent step. Validator failures would immediately proceed to rendering despite the explicit retry contract.
   - Fix: execute each non-validator command with stop-on-failure before invoking `next`. For validation, maintain a per-run retry count, request a bounded contract repair, revalidate up to twice, then create an explicit caveat before render.
   - Current status: stop-before-next is now applied in current `runThenNext()` around line 2977. Validator repair/retry/caveat handling remains absent.

9. The r2 renderer reported two real XeLaTeX failures but returned success, so the workflow marked the run DONE. [A, D]

   - Evidence:
     - [journal.jsonl:144](/home/lingxufeng/.claude/projects/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/subagents/workflows/wf_00a3a165-dcd/journal.jsonl:144): `"⚠️ xelatex failed for idea.std.en.tex:"`.
     - Same line: `"! Double subscript."` and later `"⚠️ xelatex failed for idea.std.zh.tex:"`.
     - Same runner output ends with `"__RC1=0"` and then `"STATE  : DONE — all three idea cards rendered."`
   - Defect: `phase4_render` swallowed child-process failures and returned zero. The runner truthfully returned the wrapper exit code, but the workflow treated partially generated PDFs as successful cards.
   - Fix: make `run.py phase4_render` return nonzero if any required render fails, or emit a machine-readable render manifest with per-format status. In `driveRun()`, require all requested card formats to succeed before accepting terminal DONE.
   - Current status: not applied.

10. Runner output and exit codes were entrusted to an LLM and were not consistently verbatim. [D]

   - Evidence:
     - Executed `sh()` lines 2878–2883 simply return `Number(r.rc)` and `String(r.out)`.
     - `a078…` @ 5s Bash result: `"SHARDS 3 130\nRC=0"`; @ 8s structured output: `{"rc":0,"out":"SHARDS 3 130\n"}`.
     - [agent-a078…jsonl:5](/home/lingxufeng/.claude/projects/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/subagents/workflows/wf_00a3a165-dcd/agent-a078a340329c574ec.jsonl:5) shows it appended `echo "RC=$?"`, which was not in the requested command.
     - [agent-a22…jsonl:5](/home/lingxufeng/.claude/projects/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/subagents/workflows/wf_00a3a165-dcd/agent-a22e38f0989a466a5.jsonl:5) and [agent-a43…jsonl:5](/home/lingxufeng/.claude/projects/-home-lingxufeng-workspace/d629dbc6-a638-4acd-9242-16dfeb067c18/subagents/workflows/wf_00a3a165-dcd/agent-a43c6bfcbc604ae0b.jsonl:5) appended `2>&1; echo "__RC__=$?"`, then omitted the marker from their structured outputs.
   - Defect: mechanical parsing depended on an agent obeying exact command and byte-preservation instructions. Three runners changed commands; 28 returned output differing from the Bash result.
   - Fix: wrap every command in `sh()` with a unique, workflow-generated exit sentinel, capture raw stdout/stderr deterministically, parse the sentinel locally, and reject missing/malformed markers. Do not ask the runner to infer `rc`.
   - Current status: runner tool denial is applied, but `sh()` still trusts agent-normalized `{rc,out}`.

11. Several workflow branches inspected output text without requiring a successful runner exit. [A, D]

   - Evidence:
     - Executed `launch()` lines 2905–2907 checks only `r.out.includes('LAUNCHED:' + key)`.
     - `nextEmit()` lines 2950–2954 accepts an emit whenever `e.state` parses, even when `r.rc !== 0`.
     - Executed line 3270 runs every short command before a long job as `await sh(c, ...)` and ignores its `rc` and output.
   - Defect: a command could print a recognizable sentinel/emit and still fail. Short prep failures in the long-job branch would be silently followed by a launch.
   - Fix: require `rc===0` plus the workflow-owned sentinel in `launch()` and `nextEmit()`. Apply the same checked helper to every short prep command.
   - Current status: stop-before-next and exit-aware polling improve this area, but `launch()`/`nextEmit()` still need explicit exit enforcement.

12. Polling was expensive, coarse, and historically considered mere file existence sufficient for completion. [A, D, E]

   - Evidence:
     - Executed `waitCmd()` lines 2901–2903 checks `[ -e file ]` before process state or JSON validity.
     - Phase 0 wait agents `a7e87…` and `a6c27…` each returned `"JOB_WAITING"` after approximately 517 seconds.
     - `aec241…` returned `"JOB_DONE"` at 337s in the third round.
     - Executed `waitFor()` line 2918 returns only `{done:false,out:'timeout'}`, discarding the log tail accumulated during prior rounds.
   - Defect: each 8.5-minute wait used a new LLM runner. A writer that created the final path before closing it could be consumed early. Fixed six-round deadlines were not connector-specific, and terminal timeout evidence was discarded.
   - Fix: use a deterministic monitor or process notification. Require process exit plus parseable/nonempty JSON, or write to a temporary file and atomically rename. Preserve the final log tail and derive the deadline from the connector budget.
   - Current status: exit-aware polling is now applied around current `waitCmd()` line 2914. Atomic completeness validation, deterministic monitoring, and timeout evidence preservation remain.

13. Cross-run ideation serialization added about 18 minutes and caused an unnecessary duplicate `next` for r1. [A, E]

   - Evidence:
     - Executed lines 3297–3298: `"if (turn > 0) await ideateTurn[turn - 1].p"` followed by unconditional `"const fresh = await nextEmit(...)"`.
     - Timeline: r1 ideation ran 21:10:01–21:27:48; r2 did not start until 21:28:16 and ran to 21:43:02.
     - Two r1 navigator calls at 21:09:20 and 21:09:37 emitted the same Phase 2.1+2.2 step.
   - Defect: the whole 2.1+2.2 generation was serialized to obtain a cross-run dedup line. For turn zero, rereading `next` could not add earlier-run information.
   - Fix: parallelize selection/generation by default and deduplicate candidates afterward, or serialize only a final selection step. At minimum use `turn > 0 ? await nextEmit(...) : e`.
   - Current status: optional serialization via `args.stagger` is now applied at current line 38 and the ideation branch. With staggering disabled this overhead disappears; the turn-zero duplicate should still be guarded if staggering is enabled.

14. Resume behavior can silently retain stale or partial Phase 0 snapshots. [A]

   - Evidence:
     - Executed metadata line 4 says: `"Resumable: re-run with the same args"`.
     - Executed spawn line 3193 skips copying whenever `rN/phase0` already exists.
     - `next_step.py:863–864` says: `"never reuse a dir that already has a phase0/"`.
   - Defect: a partially copied or older run-local Phase 0 survives without comparison to `_shared/phase0`. Concurrent/resumed runs can therefore use different corpora while appearing to share Phase 0.
   - Fix: write a `_shared/phase0` manifest/hash, copy through a temporary directory and atomic rename, and verify each run-local manifest before reuse.
   - Current status: not applied.

15. The advertised second tagging round was unreachable after a merge rejection. [A]

   - Evidence:
     - Executed `phase0Stage()` lines 3175–3179 contains a two-round loop.
     - Executed `tagShards()` lines 3157–3159 renames shards and immediately throws when merge fails.
   - Defect: the throw exits `phase0Stage()`; the second loop iteration never starts. Seat `ok:true` also was accepted before per-shard row/schema validation.
   - Fix: validate each shard before merge and return failure after cleanup, or catch the merge exception inside the loop.
   - Current status: applied at current line 3204 with an in-loop `try/catch`. Per-shard early validation would still improve diagnostics.

16. Smaller seat-level contract violations were widespread even outside the two worst seats. [B]

   - R1 Phase 1:
     - @ 21s attempted the entire fulltext blob and received `"File content (27527 tokens) exceeds maximum..."`, despite the prompt’s cheaper index/per-paper route.
     - @ 93s read unlisted `docs/refs/rs/references/intake-routing.md`.
   - R1 ideation:
     - @ 1001s: `"I added a non-schema field that a strict validator would reject."`
     - It then used Edit at 1019, 1026, and 1034s.
   - R1 audit:
     - After the collision file ended at line 2156, it issued reads at offsets 2621 and 3121; both returned “file is shorter than the provided offset.”
   - R2 audit:
     - @ 530s: `"One cosmetic issue to fix..."`; Edit at 531s despite the Read/Write-only contract.
   - R2 evidence:
     - Wrote at 749s, then Edited at 773s.
   - Phase 4.fill:
     - R1 read unlisted Phase 1, final candidate, and critique files at 12, 23, and 33s.
     - R2 did the same at 11, 15, and 26s and additionally read the lit table at 31s.
   - Defect: the prompt said not to open unnamed inputs and to write complete outputs once, but actual tool capabilities allowed otherwise.
   - Fix: retain the newly applied tool restrictions; replace giant inputs with compact task views; validate exact paths and one-write completion. Do not rely on seats to self-correct schema violations with Edit.
   - Current status: mechanical tool denial is applied; compact input views and output validation are not.

17. Retrieval timeout consequences differed sharply between Phase 0 and collision retrieval. [E]

   - Evidence:
     - `.jobs/phase0.log:14`: `"[dblp_0-36mo] timed out after 1200s"`.
     - Phase 0 launched at 20:32:54 and `lit_results.json` was observed at approximately 20:56:03–20:56:12.
     - Both collision logs contain two `"timed out after 1200s"` entries at lines 14–15.
     - r2 collision launched at 21:43:17 and completed around 22:26:27; r2 coherence finished at 22:29:03.
   - Defect: the Phase 0 timeout contributed almost its full 20 minutes to wall time. Collision timeouts consumed approximately 80 connector-minutes across two runs but were hidden behind the unusually slow coherence seats; once model/seat latency is fixed, collision becomes the next critical-path bottleneck.
   - Fix: at `run.py:252`, use a fast DBLP health probe/circuit breaker and a much shorter per-connector deadline. Cache or skip a connector after the first session-wide 1200-second timeout.
   - Current status: not applied.

## Runner normalization: all 53 calls

No runner Bash result exceeded 5,236 characters, so no 16,000-character truncation occurred. All 53 structured results reported `rc:0`; every observed workflow-owned `__RC0`/`__RC1` marker was zero.

- 25 were byte-verbatim:
  `a11330287c5a16a2b`, `a1550406405cfce54`, `a2cd852f0132e53a6`, `a4632b688390f0d5d`, `a4741b1966999f687`, `a484f62e79a36a8c0`, `a54af53a509546dbb`, `a5d0217a2cfaca7aa`, `a703f0eb737e5966e`, `a78abddf775bef8f5`, `a7d575a0158055750`, `a7ea8886899c4c815`, `a9134e8c5abe86921`, `a9233a1ae9914dafb`, `aa3a72c354eea103c`, `aa51626bd744b9151`, `aa5ae7529f641c8a9`, `abce2063d5cee28a8`, `acd7a96ea235797ed`, `ad42c260b8ac4ad61`, `ad498fc4c92639bc0`, `ad69f4427f766e9a3`, `addfb3f50ece74f05`, `ae4842cc154f4f875`, `ae9a5b55ecc46d2ac`.

- 25 altered output only by adding one trailing newline:
  `a17fe52b0e6662583`, `a1cc27a3fc5fb7a15`, `a2adaf4626a162c4d`, `a31f6860a9ca5ead4`, `a35955e1a9e6eb607`, `a4d010419ae25113d`, `a60e978be0638a299`, `a6c27cf93cd1faddd`, `a7193a5ede8f8af02`, `a7730010b314e3afa`, `a7e87f4d3616ab201`, `a7fe70f420ae06ef0`, `a95685c823c4ba4ca`, `a9d40706929c0271a`, `aa4266fd165b55185`, `ab2866b3d99e0fc0f`, `ab319ce5c836ea911`, `ab8d0f10e7640370a`, `abe48ee594af88345`, `ac57dc3781ea041c2`, `ade7bdaa631e48a03`, `ae57558d12dd73355`, `aeae19538fe2c64ea`, `aec2412bbafb4bb27`, `af344dff88ea243e1`.

- Three materially violated normalization:
  - `a078a340329c574ec`: appended `echo "RC=$?"`, then dropped `"RC=0"` from returned output.
  - `a22e38f0989a466a5`: appended `2>&1; echo "__RC__=$?"`, then stripped the marker.
  - `a43c6bfcbc604ae0b`: same mutation and stripping.

- Silently failed commands:
  - No top-level runner command or explicit `__RC` marker was nonzero.
  - One nested operation failed silently: r2’s English and Chinese XeLaTeX builds. `phase4_render` emitted both failures but still returned `__RC1=0`, so this is a wrapper/exit-propagation defect rather than a falsely reported runner exit code.
  - R1 coherence’s `sed` exit 2 was a seat Bash violation, not one of the 53 runner calls.

No wrong `parseEmit()` routing or missing navigator state was observed in this run. No poll returned materially later than its 30-second cadence plus runner startup. No seat-level retry fired.

## Critical-path budget

Baseline workflow duration from the persisted record was 12,992,575 ms: 216.5 minutes.

The attribution separates pre-output model latency from post-output Edit/tool churn. Collision timeout overlap means standalone savings are not fully additive.

| Defect class | Actual critical-path excess | Evidence/basis | Runtime if fixed alone |
|---|---:|---|---:|
| Model choice / effort | ~75–85 min | r2 coherence first output at 37.8m; r2 implementability first output at 50.8m; additional max-effort audit/derive/evidence latency | ~152–162 min; collision becomes exposed |
| Retrieval timeouts | ~20 min wall time | Phase 0 DBLP timeout fully critical; collision timeout ~0–3 min critical in this run but ~80 connector-minutes wasted | ~196–197 min |
| Seat misbehaviour | ~12–17 min | coherence post-write edits/validators, implementability Edit chains, redundant reads and cosmetic edits | ~204–209 min; some coherence savings expose collision |
| Workflow overhead | ~20–24 min | ~18m serialized r1 ideation gate plus duplicate navigator/runner/poll transitions | ~192–197 min |
| Irreducible useful work | ~75–85 min | Phase 1, parallel candidate work, bounded audits/revisions/fill/evidence/rank | — |

Counterfactual estimates:

| Fixed set | Estimated wall time |
|---|---:|
| Model IDs and explicit effort only | 152–162 min |
| Retrieval timeouts only | 196–197 min |
| Seat contracts/output sizing only | 204–209 min |
| Workflow serialization/runner overhead only | 192–197 min |
| All four classes, including collision circuit-breaking | **75–95 min** |

The all-fixed estimate is consistent with the intended ~90-minute target. The important interaction is that fixing only the slow models is insufficient: the 40-plus-minute collision jobs immediately become visible on the critical path unless the DBLP timeout behavior is fixed at the same time.