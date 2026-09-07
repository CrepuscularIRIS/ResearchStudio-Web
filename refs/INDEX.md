# docs/refs — 原版资产逐字提取（2026-09-06）

原则：整目录拷贝，不删减、不转写、不合并。`diff -rq` 对源目录逐字节一致；`MANIFEST.sha256` 覆盖全部 231 文件。
排除项只有 `.env`、`__pycache__`。后续提示词从这里取材，写提示词时引用路径，不要复制改写。

取代 `docs/prompt-bank/`（那一版把 RS 15+31 卡内联进 workflow 时做了压缩，且 RS 提示词与脚本未入库）。

## 来源与校验

| 目录 | 源 | 文件 | 校验 |
|---|---|---|---|
| rs/ | `~/autoresearch/ResearchStudio/ResearchStudio-Idea/skills/idea_spark` | 99 | diff -rq 一致 |
| rs-eval/ | `~/autoresearch/ResearchStudio/ResearchStudio-Idea/evaluation/idea_quality`（RS 自己的 idea 评分规则：A/B/C 三轴、A≤2 或 C≤2 封顶、provenance-blind） | 5 | diff -rq 一致（2026-09-07；rank 席引用其盲判规则，评分表用 CCF K1 不并用两套） |
| ccf/ | `~/autoresearch/CCFA-Skills/{ccf-common, ccf-experiment-designer, ccf-idea-reviewer, ccf-idea-optimizer, ccf-paper-reviewer}` + AGENT_GUIDE.md | 56 | diff -rq 一致 |
| aris/ | `~/oss/aris/skills/{experiment-plan, ablation-planner, kill-argument, idea-creator, idea-discovery, novelty-check, formula-derivation, experiment-audit, result-to-claim, specification-writing, research-review, paper-claim-audit, analyze-results, run-experiment, shared-references}` | 45 | 整目录同步 |
| paperjury/ | `~/autoresearch/paperjury/{SKILL.md, ClaudeNative/, references/}` | 14 | 整目录同步 |
| papers/ | ARFT `2608.14905v2`（How Do Agents Fail on AutoResearch）、ASI-Bench `2608.17271v1`、`~/oss/ASI-Bench/{README, AGENTS, docs/guide, 一个任务的 prompt_b1–b4 范例}` | 17 | 逐文件复制 |

## RS 相位 → 文件（V9 相位号见 specs/2026-09-06-v9-brain-rs-architecture.md §2）

| V9 步 | RS 提示词 / 脚本 | 参考卡 |
|---|---|---|
| 0a 查询 | `rs/references/intent-recognition.md`、`intake-routing.md`、`source-routing.md` | — |
| 0b 检索 | `rs/scripts/run.py phase0`、`search_{arxiv,openalex,openreview,cvf,semanticscholar,dblp,elsevier}.py`、`dedup_merge.py`、`extract_user_refs.py` | `rs/references/schemas.md`、`scripts/schemas.md` |
| 0c 打标 | `rs/scripts/pattern_summary.py`（rc=10 哨兵） | `rs/references/pattern-summary-rubric.md`、`ideation-patterns/overview.md` |
| 0d 全文 | `rs/scripts/fetch_sections.py`、`run.py phase0_fulltext` | — |
| 1 瓶颈 | `rs/references/system-prompts/bottleneck_identify.txt`；`run.py phase1_fulltext_topup` | `rs/references/regression-directions.md` |
| 2.1 选 gap | `system-prompts/ideate_select.txt`；`run.py phase2_prepare` | `ideation-patterns/overview.md` + 15 张卡、`companion-combos.md` |
| 2.2 生成 | `system-prompts/ideate_generate.txt` | `ideation-sub-patterns/overview.md` + C00–C30、`anti-patterns.md` |
| 2g 引用门 | `scripts/validators/subpattern_citation_consistency.py` | — |
| 2.3 连贯门 | `system-prompts/coherence_trace.txt`；合并用 `run.py phase3_merge_revisions` | — |
| 3.1 碰撞 | `run.py phase3_collision`（signature@10mo / alias@48mo） | — |
| 3.2 审计 | `system-prompts/critique.txt` | `anti-patterns.md` |
| 3.2b 复核 | `system-prompts/refutation_recheck.txt` | — |
| 3.3 补丁 | `system-prompts/revise.txt`；`scripts/merge_revisions.py`；`validators/kill_switch_integrity.py`；`system-prompts/falsification_reaudit.txt` | — |
| 4a 骨架 | `scripts/phase4_skeleton.py` | — |
| 4b 填充 | `system-prompts/expand.txt`；`validators/expansion_completeness.py` | — |
| 4c 组装 | `run.py phase4_assemble / phase4_method_view`；`scripts/regression_check.py` | — |
| （砍）derive / 4.1.5 / render | `derive_plain.txt`、`implementability_audit.txt`、`render_pdf.py`、`validators/implementability_*.py` | 保留供 Worker spec 席取材 |
| 导航器 | `rs/scripts/next_step.py`、`run.py`、`_time_guard.py`、`gen_pipeline.py`、`selftest_routing.py` | `rs/SKILL.md`（上下文纪律三条规则）、`references/design-notes.md`、`setup.md` |

## 新增相位 → 取材

| V9 步 | 取材 |
|---|---|
| −1 仓库 intake | `rs/references/intake-routing.md`（10 字段）；`ccf/ccf-idea-optimizer/references/idea-intake.md`；`aris/shared-references/compute-env-contract.md`、`evidence-precheck.md` → **2026-09-07 晚已逐字进 intake 席**（算力信封按 env-spec、seed_sd 与来源行、数字必带 file:line） |
| 1 瓶颈 · 关系边 | `ccf/ccf-idea-optimizer/references/literature-grounded-evolution.md`（2026-09-07 深夜逐字进 Phase 1：closest_adjacent 带 `relation` 五枚举，ARFT B.5；rank 席同文件取六问） |
| Rank · 评审会 | `ccf/ccf-idea-reviewer/references/expert-panel.md`、`ccf/ccf-common/references/review-output-standards.md`、`ccf/ccf-idea-optimizer/references/venue-idea-adapters.md`（2026-09-07 深夜逐字进 rank 席：五角色块 + synthesis + Output Quality Gate，rank_check 查 panel） |
| 1v / 3.2v DR 校验 | `paperjury/ClaudeNative/DeepResearch.md`（extract → 三票 verify 段）；`aris/shared-references/citation-discipline.md` |
| 3.5 Astra 推导 | `aris/formula-derivation/SKILL.md`；`aris/kill-argument/SKILL.md`（六轴否决 memo 作为失效条件提示） → **2026-09-07 晚：formula-derivation 逐字进 4b fill 席（KEY EQUATIONS DISCIPLINE：不变量对象 / 假设 / identity-proposition-approximation-interpretation 标签 / 失效条件），独立 Astra 席未建（§10）；kill-argument 留 paper 阶段**；**2026-09-07 深夜：owner 决定不建独立席，2.3 连贯门换 Astra（gpt-6-astra，失败回退 Opus）——2.3 本就是推导席（T1/T2/T4/T5），串行跳数不变** |
| 5 evidence_plan | `ccf/ccf-experiment-designer/references/evidence-design.md`（Baseline Matrix / Ablation Logic / Minimum Convincing Package）、`result-templates.md`；`aris/experiment-plan/SKILL.md`（Claim Map / Blocks / Run Order）；`aris/ablation-planner/SKILL.md`（2026-09-07 晚逐字进 P5：what_it_tests / expected_if_component_matters / 禁 no-op / 组件先于超参，plan_check 机检）。~~`aris/specification-writing/SKILL.md`~~ 是专利说明书 skill（"Write the full patent specification from claims"），与 Phase 6 无关，DROP |
| K3 3.2 打分口径 | `ccf/ccf-idea-reviewer/references/{rubric, strict-idea-review, calibration, expert-panel}.md`；`ccf/ccf-paper-reviewer/references/{universal-review-rubric, calibration-and-rank, desk-checks}.md`；`paperjury/references/{reviewer-personas, review-engine-v3}.md`；`aris/shared-references/{reviewer-independence, taste-calibration}.md` → **2026-09-07 晚落地**：strict-idea-review + ccf-idea-optimizer/problem-method-blueprint 逐字进 3.2（No-Filler 五字段、Coherence Filter 六布尔、Fatal Idea Risks）；rubric + calibration + strict-idea-review 逐字进 rank 席（10 维加权、8 条致命门、tournament，`rank_check` 复算加权分）；expert-panel / ccf-paper-reviewer / paperjury 需独立席位，不进 Brain |
| Worker 判决 | `aris/shared-references/acceptance-gate.md`（DRIVE / ACQUIT）、`experiment-integrity.md`；`aris/experiment-audit/SKILL.md`、`result-to-claim/SKILL.md`、`run-experiment/SKILL.md` |
| Brain→Worker 契约边界 | `papers/asibench-2608.17271v1.txt`（B1/B2）；`papers/asi-bench/task-exemplar/prompt_b1.md … b4.md`、`guide/how-scoring-works.md` → **2026-09-07 深夜：task.yaml + prompt_b1 + how-scoring-works 逐字进 Phase 6 spec 席，spec 加 `gates[]`（evaluation.gates 形式），spec_check 机检** |
| 失败分类检查表 | `papers/arft-2608.14905v2.txt`；`papers/arft_guide.md`（AutoResearchEval agent-as-a-judge 原文，2026-09-07 入库，逐字进 3.2：finding 带 `arft_code`） |
