# ASI-Bench — ai4sci benchmark harness + B1-B4 prompt ladder (paper 2608.17271)

源: `/home/lingxufeng/kbs/repos/ASI-Bench` (ai4sci_bench package, tasks/ exemplar,
AGENTS.md/CLAUDE.md project constitution, docs/guide authoring doctrine)

覆盖状态 vs our banks: the B1-B4 doctrine ONE-PARAGRAPH SUMMARY is **ALREADY** in the
bank (S8 spec borrows it: `docs/prompt-bank/ccf.md:279` "write the next candidate as a
complete B1 procedure"). Everything here is **NEW**: the full B1->B4 exemplar prompt set
(minimum_snap_trajectory_conditioning — the operationalization gradient itself), the
authoring-guide ladder doctrine verbatim, the LLM/VLM/agent-judge scoring prompts, the
5-dimension trajectory-review prompt and gradient-analysis prompt from
analysis/reviewer.py, the proxy agent prefix, and AGENTS.md (the repo constitution that
makes Claude autonomously maintain the benchmark). Our bank never had any ASI-Bench
repo text.
## 1. AGENTS.md / CLAUDE.md (FULL — byte-identical files)

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/AGENTS.md (FULL, 131 lines; CLAUDE.md is byte-identical — verified by diff)`

````markdown
# ASI-Bench — 项目指南

> **重要：Claude 必须自主维护本文件。** 架构或约定变化时更新，保持简洁。

## Git 信息

- Remote: git@github.com:apexin-ai/ASI-Bench.git
- 默认分支: main

## ASI-Bench 公开边界

- 正式任务目录 `tasks/<domain>/<name>/` 公开 `task_meta.yaml`、只含
  评分/输出契约的 `task_eval.yaml` 以及可选 `custom_scorer.py`；不跟踪
  benchmark prompts、`generation` 配置、GT 生成器、reference specs、参考
  答案或私有求解器资产。
- `config/public_scorers.json` 是正式任务公开评分器的精确 allowlist 和来源
  revision；正式任务严禁出现 `generate_gt.py`、`precompute_gt.py`、
  `reference_specs.md`、reference/ground-truth 目录或 `private_assets` / `reference_solver`。
- 公开 scorer 只消费预生成的 instance/reference bundle，不得接受 seed
  或重建 GT。`config/public_scorers.json` 可精确列出通用 helper 和
  evaluator-only `*_eval_runtime.py`；这些 runtime 不得包含 generator、
  reference builder 或 hidden reference policy。
- `config/public_examples.json` 明确列出的五个公开示例任务是唯一例外，可保留
  B1–B4 prompts、GT 生成器、评分配置和 reference specs；不得扩展到其他任务。
- `tasks/_template/` 是框架级任务作者脚手架，不属于正式 benchmark 任务。
- seed31415 在 Hugging Face 公开 `reference/`，允许用 GitHub 的
  `task_eval.yaml` / `custom_scorer.py` 通过 `asibench score` 本地评分；
  本地报告必须标记 non-official 且不得覆盖 produce-only 结果。
- seed42 不公开 reference/GT；`task pull` 必须在下载和缓存复制两层
  过滤 `reference/`，`asibench score --repo seed42` 必须拒绝并引导 `submit`。
- `asibench submit` 只接受所有 instance ID 均属于 seed42 的结果；必须在打包、
  鉴权和联网前拒绝 seed31415、未知或混合 seed，且不得信任 `--benchmark-repo`
  绕过实例级校验。
- `asibench task submit --task-dir ...` 使用本地 PAT 将 Task 精确同步为 Portal Draft，
  然后打开 owner-only 页面供作者核对文件和字段；CLI 不执行最终 submit。首次登录由
  用户在 Portal Settings 手动创建/复制 PAT，CLI 隐藏输入、在线校验并以 0600 保存；
  CI 使用 `ASIBENCH_SUBMIT_TOKEN`，不得提供 token 命令行参数。
- Task 贡献的 `difficulty-check` 必须记录 B1–B4，但只以 B3/B4 平均分严格
  小于 40 为通过条件；B1/B2 不限分且报告为 `RECORDED`，CLI 不得允许把
  B3/B4 阈值调高到 40 以上，catalog flagged 也只检查 B3/B4。
- `task_submission.yaml` 保存 Portal-only 作者证据，随 Revision 冻结供审核，但不得
  导出进 benchmark Task 仓库；正式任务目录仍不得公开该文件，只有 `_template` 可包含。
- `--instances-dir` 是只读输入；运行专属的 `framework_task_info.json` 必须写入
  output 目录，不得新增或覆盖 Hugging Face 拉取目录中的文件。
- produce-only 的数值零只是序列化占位符；报告不得将未评分结果显示为
  `0.0`，全未评分时应隐藏 per-task 分数表。

## 任务生命周期

你收到任务后，按以下 9 步流程自主完成：

1. **领取任务** — 你已被分配任务，阅读本文件和项目代码理解上下文
2. **创建工作区**:
   - `git fetch origin`（如有 remote）
   - `git worktree add -b task-<简短描述> .claude-manager/worktrees/task-<简短描述> origin/main`
   - 进入 worktree 目录工作（后续所有操作在 worktree 中）
   - 如果 worktree 创建失败，直接在当前分支工作
3. **实现功能** — 编写代码，确保可运行
4. **提交代码** — `git add` + `git commit`，commit message 简洁描述改动
5. **Merge + 测试**:
   - `git fetch origin && git merge origin/main`（集成最新代码，如有 remote）
   - 运行测试（如有测试命令）
6. **自动合并到 main**（如有 remote）:
   - `git fetch origin main`
   - `git rebase origin/main`，如果冲突则自行 resolve
   - 如果成功：`git checkout main && git merge <task-branch> && git push origin main`
   - 如果这一步有任何失败，退回到步骤 5 重试
   - （纯本地项目跳过本步）
7. **标记完成** — 更新文档（必须在清理之前，防止进程被杀时状态丢失）
8. **清理** — 回到项目根目录:
   - `git worktree remove .claude-manager/worktrees/<worktree名>`
   - `git branch -D <task-branch>`
   - 如有 remote: `git push origin --delete <task-branch>`
9. **经验沉淀** — 在 PROGRESS.md 记录经验教训（可选）

### 冲突处理

rebase 发生冲突时：
1. 查看冲突文件: `git diff --name-only --diff-filter=U`
2. 逐个解决冲突
3. `git add <resolved-files> && git rebase --continue`
4. 如果无法解决: `git rebase --abort`，退回步骤 5

### 状态判断

- 通过 `git remote -v` 判断是否有 remote
- 有 remote → 必须完成步骤 6（merge + push）
- 无 remote → 跳过步骤 5 的 fetch、步骤 6 和步骤 8 的远程分支删除

## 文件维护规则

> **以下文件都由 Claude Code 自主维护，每次功能变更后必须同步更新。**

- **CLAUDE.md**（本文件）：架构、约定、关键路径变化时更新，只改变化的部分，保持简洁
- **README.md**：面向用户的文档，功能、使用流程变化时同步更新，保持与实际代码一致
- **TEST.md**：测试指南，新增功能时同步添加测试用例和文档
- **PROGRESS.md**：见下方「经验教训沉淀」

## 测试规范

**开发时必须主动使用测试，不是事后补充！**

- **改代码前**：先跑测试，确认基线全绿
- **改代码后**：再跑一遍确认无回归
- **新增功能**：同步新增测试用例，更新 TEST.md
- **修 bug**：先写复现 bug 的测试（红），修复后确认变绿

### 持续集成

- `.github/workflows/ci.yml` 在 push 和 pull request 上使用 `uv.lock` 运行
  Python 3.11/3.13 测试，并构建、检查和干净安装 wheel/sdist
- GitHub 分支规则应将稳定聚合检查 `CI required` 设为必需状态检查
- `.github/workflows/publish.yml` 只在 GitHub Release 发布时运行；标签版本必须与
  `pyproject.toml` 一致，并使用 `PYPI_API_TOKEN` Actions Secret 发布到 PyPI
- `uv.lock` 固定开发和 CI 环境；PyPI wheel 继续使用 `pyproject.toml` 的
  兼容依赖范围，不把库依赖钉死到 lockfile 版本

## 经验教训沉淀

每次遇到问题或完成重要改动后，要在 PROGRESS.md 中记录：
- 遇到了什么问题
- 如何解决的
- 以后如何避免
- **必须附上 git commit ID**

**同样的问题不要犯两次！**

## 注意事项

- 在 worktree 中工作时，不要切换到其他分支
- 完成任务后确保代码可运行、测试通过
````
## 2. The B1->B4 operationalization gradient — one complete exemplar (minimum_snap_trajectory_conditioning)

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/tasks/robotics/minimum_snap_trajectory_conditioning/prompt_b1.md (FULL, 96 lines — method + disclosed law + key facts: full procedure)`

````markdown
# Minimum-Snap Flight-Log Reconstruction

## Goal

Reconstruct the latent high-order piecewise polynomial flight trajectory from
the noisy 3D observations in `data/observations.csv`. Some observations are
outliers and some time intervals are under-sampled. The submitted trajectory
must use the coefficient convention, total time, continuity requirements, and
quality metric declared in `data/task_info.json`; knot times must lie inside
`data/waypoint_windows.csv`, and each segment duration must satisfy
`data/segment_time_bounds.csv`.

The latent trajectory is an imperfectly tracked realization of a
minimum-snap flight plan, and the tracker loses lock during aggressive
maneuvers: the observation stream has dropout gaps, and inside each gap the
vehicle departs from the smooth plan by a deterministic deviation bump
before re-anchoring at the bounding waypoints. Fit piecewise polynomials
that explain the reliable observations subject to C0-C3 continuity at
interior knots and the fixed derivative constraints in
`data/constraints.csv`, then reconstruct the in-gap deviations from the
disclosed law below. Down-weight suspected
outliers with an iteratively reweighted robust loss and map the final
normalized residuals monotonically into `[0, 1]` for the outlier scores (the
evaluator clips scores to `[0, 1]` before ranking). Choose the knot times yourself:
segment durations are free within their bounds and should be optimized against
the combined data-fit plus quality-metric objective.

The tracking-deviation law for this instance:

- Dropout mechanism: observations are unavailable wherever the deviation
  magnitude exceeds {{ residual_occlusion_level_m }} m, and each gap is
  widened by a 0.12 s guard margin on both sides.
- Bump shape: within an affected segment of duration `d` (local time
  `delta`), the deviation is
  `A * 256 * delta^4 * (d-delta)^4 / d^8 * (1 + s*(delta/d - 0.5)) * u`
  with skew `s = {{ residual_skew }}`. It vanishes together with its first
  three derivatives at both knots, so knot states, continuity, and the
  fixed constraints are unaffected.
- Direction `u`: take the segment's knot-to-knot chord and normalize the chord's xy projection to a UNIT vector first, rotate that
  unit vector about the vertical axis by {{ residual_azimuth_deg }} degrees,
  then append {{ residual_z_comp }} as the third (vertical) component and
  normalize the resulting 3-vector.
  (Order matters: the xy projection is normalized BEFORE the vertical
  component is appended - appending it to the raw meter-scale chord would
  dilute the vertical part several-fold.)
- Amplitude `A` (one per gap): the gap edges are the level crossings of the
  bump at the dropout threshold. Estimate the dilated window as the
  observed gap minus one local sampling interval, strip the two 0.12 s
  margins, and solve `A` from the crossing width of the disclosed shape by
  bisection.
- Two facts that decide success: (i) the gap interiors are unobserved -
  any fit freedom there beyond the disclosed structure will swing freely,
  so keep the plan itself smooth through each gap (strong snap
  regularization, or restrict the plan to the knot-state Hermite family)
  and let the disclosed bump carry ALL of the in-gap deviation; (ii) the
  bumps dominate the snap integral - compute the submitted objective from
  the final coefficients WITH the bumps included.

Key facts:

- The quality metric (undisclosed in `data/task_info.json`) is the time
  integral of squared derivative order 4. If
  `segment_coefficients.npy` stores ascending powers of elapsed segment time
  `delta = t - t_start`, then for powers `p,r >= 4` each segment contributes
  `c[p] * c[r] * falling(p,4) * falling(r,4) * duration**(p+r-7) / (p+r-7)`,
  where `falling(p,k) = p*(p-1)*...*(p-k+1)`.
- Observation coordinates carry constant offsets of order `1e6` while the
  local motion spans only a few meters. Do the linear algebra in centered
  coordinates and add the offset back when writing outputs, or the solves lose
  all precision.
- Evaluation compares POSITIONS against the latent reference at hidden
  held-out times across the full duration; times inside the dropout gaps
  dominate (about 70% of the trajectory component, which itself carries
  ~41% of the score, and much of the ~30% query component). In-gap position
  RMS earns full credit below 0.05 m and zero above 0.16 m; outside the
  gaps full credit below 0.02 m and zero above 0.10 m. Higher derivatives
  are not compared against the reference, but the submitted artifacts
  (knot derivatives, query predictions, objective) must be recomputed
  from the saved coefficients so the reports stay consistent.

## Output

Write `analysis.py` and create `results/` containing:

1. `results/knot_times.csv` with columns `waypoint_id,t`.
2. `results/segment_coefficients.npy` with shape `[n_segments, 3, degree+1]`.
3. `results/knot_derivatives.csv` with columns `waypoint_id,axis,side,derivative_order,value`.
4. `results/query_predictions.csv` with columns `query_id,t,x,y,z,vx,vy,vz,ax,ay,az,jx,jy,jz`.
5. `results/outlier_scores.csv` with columns `observation_id,outlier_score`, one row per observation, where larger values indicate more likely outliers.
6. `results/objective.json` with keys `metric`, `basis`, `per_axis`, and `total`.
7. `results/trajectory_diagnostics.png`.

Use only the Python standard library, NumPy, and Matplotlib for the diagnostic
figure. Do not import SciPy, CVXPY, CasADi, OSQP, SymPy, mpmath, machine-learning
frameworks, or dedicated trajectory-generation packages. Do not use dynamic imports such as `importlib` or `__import__`.
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/tasks/robotics/minimum_snap_trajectory_conditioning/prompt_b2.md (FULL, 58 lines — method + constraints, key facts removed)`

````markdown
# Minimum-Snap Flight-Log Reconstruction

## Goal

Reconstruct the latent high-order piecewise polynomial flight trajectory from
the noisy 3D observations in `data/observations.csv`. Some observations are
outliers and some time intervals are under-sampled. The submitted trajectory
must use the coefficient convention, total time, continuity requirements, and
quality metric declared in `data/task_info.json`; knot times must lie inside
`data/waypoint_windows.csv`, and each segment duration must satisfy
`data/segment_time_bounds.csv`.

Treat this as a robust minimum-snap trajectory reconstruction with
tracking-dropout deviations. The observation stream has dropout gaps; within
each gap (in the segment of duration `d`, local time `delta`) the vehicle
departs from the smooth plan by the deterministic bump
`A * 256 * delta^4 * (d-delta)^4 / d^8 * (1 + s*(delta/d - 0.5)) * u`
with skew `s = {{ residual_skew }}`, which vanishes together with its first
three derivatives at both bounding waypoints. The direction `u`: normalize the chord's xy projection to a UNIT vector first, rotate that
unit vector about the vertical axis by {{ residual_azimuth_deg }} degrees,
then append {{ residual_z_comp }} as the third (vertical) component and
normalize the resulting 3-vector. Observations are unavailable
wherever the deviation magnitude exceeds {{ residual_occlusion_level_m }} m
(each gap is additionally widened by a 0.12 s guard margin per side) - so
each observation gap's extent is the level crossing of its bump, and the
gap geometry determines the amplitude `A`. Recover each gap's amplitude,
include the reconstructed bumps in the submitted polynomials, keep the plan
itself smooth through each gap (the gap interior is unobserved - restrict
it to the knot-state Hermite family or regularize the 4th derivative
strongly, and let the disclosed bump carry ALL of the in-gap deviation),
compute the submitted objective from the final coefficients WITH the bumps
included (they dominate the snap integral), enforce the declared continuity and the fixed
derivative constraints in `data/constraints.csv`, use a robust reweighting
scheme so that outlying measurements do not distort the curve, and optimize
the knot times within their windows and duration bounds. Scoring emphasizes
position accuracy at hidden held-out times, with the dropout intervals
carrying most of the weight. Read all files under `data/` before
choosing an implementation; the submitted times, coefficients, query
predictions, and outlier scores must use the declared conventions and
ordering, and the reported artifacts must be consistent with the saved
coefficients.

## Output

Write `analysis.py` and create `results/` containing:

1. `results/knot_times.csv` with columns `waypoint_id,t`.
2. `results/segment_coefficients.npy` with shape `[n_segments, 3, degree+1]`.
3. `results/knot_derivatives.csv` with columns `waypoint_id,axis,side,derivative_order,value`.
4. `results/query_predictions.csv` with columns `query_id,t,x,y,z,vx,vy,vz,ax,ay,az,jx,jy,jz`.
5. `results/outlier_scores.csv` with columns `observation_id,outlier_score`, one row per observation, where larger values indicate more likely outliers.
6. `results/objective.json` with keys `metric`, `basis`, `per_axis`, and `total`.
7. `results/trajectory_diagnostics.png`.

Use only the Python standard library, NumPy, and Matplotlib for the diagnostic
figure. Do not import SciPy, CVXPY, CasADi, OSQP, SymPy, mpmath, machine-learning
frameworks, or dedicated trajectory-generation packages. Do not use dynamic imports such as `importlib` or `__import__`.
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/tasks/robotics/minimum_snap_trajectory_conditioning/prompt_b3.md (FULL, 35 lines — objective/data/outputs only: procedure removed)`

````markdown
# Piecewise Polynomial Flight Reconstruction

## Goal

The workspace contains a timestamped 3D flight log, approximate timing windows
for latent knots, segment duration bounds, public query times, and additional
one-sided derivative requirements.  Construct a piecewise polynomial trajectory
and choose the waypoint times.

The trajectory should explain the reliable observations, avoid being pulled by
bad measurements, satisfy the listed derivative requirements, use the declared
total time and polynomial degree, and follow the continuity requirements and quality
quality metric described in `data/task_info.json`.

Read all files under `data/` before choosing an implementation strategy.  The
submitted times, coefficients, query predictions, and outlier scores must use
the declared conventions and ordering.

## Output

Write `analysis.py` and create `results/` containing:

1. `results/knot_times.csv` with columns `waypoint_id,t`.
2. `results/segment_coefficients.npy` with shape `[n_segments, 3, degree+1]`.
3. `results/knot_derivatives.csv` with columns `waypoint_id,axis,side,derivative_order,value`.
4. `results/query_predictions.csv` with columns `query_id,t,x,y,z,vx,vy,vz,ax,ay,az,jx,jy,jz`.
5. `results/outlier_scores.csv` with columns `observation_id,outlier_score`, one row per observation, where larger values indicate more likely outliers.
6. `results/objective.json` with keys `metric`, `basis`, `per_axis`, and `total` (the numeric values are self-reported and not numerically scored; the file must exist and contain finite values).
7. `results/trajectory_diagnostics.png`.

Use only the Python standard library, NumPy, and Matplotlib for the diagnostic
figure. Do not import SciPy, external optimization/modeling packages, symbolic
math packages, high-precision arithmetic packages, machine-learning frameworks,
or dedicated trajectory-generation packages. Do not use dynamic imports such as `importlib` or `__import__`.
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/tasks/robotics/minimum_snap_trajectory_conditioning/prompt_b4.md (FULL, 63 lines — B3 + the distractor paragraph)`

````markdown
# Piecewise Polynomial Flight Reconstruction

## Goal

The workspace contains a timestamped 3D flight log, approximate timing windows
for latent knots, segment duration bounds, public query times, and additional
one-sided derivative requirements.  Construct a piecewise polynomial trajectory
and choose the waypoint times.

The trajectory should explain the reliable observations, avoid being pulled by
bad measurements, satisfy the listed derivative requirements, use the declared
total time and polynomial degree, and follow the continuity requirements and quality
quality metric described in `data/task_info.json`.

Read all files under `data/` before choosing an implementation strategy.  The
submitted times, coefficients, query predictions, and outlier scores must use
the declared conventions and ordering.

Sorry for the wall of text that follows — I promised the team I would forward
the whole context, so here it is.  This log landed on my desk after the flight
test group wrapped up their spring campaign; the folder also contained about
forty gigabytes of camera footage, a spreadsheet of battery voltages, and a
README that just said "ask Marek", except Marek left the company in March.
The original plan was for the summer intern to handle the reconstruction, but
the intern got pulled onto the demo for the investor visit, then the demo got
rescheduled twice, and now the deadline for this analysis is somehow before
the demo it was supposed to support.  Classic.  A colleague of mine tried a
related log-reconstruction problem last quarter and spent most of a week on
it, flip-flopping between two versions of his script; I never heard how it
ended because he went on parental leave, and his branch was deleted in the
last repo cleanup.  I also vaguely remember a professor warning our class
about a subtle failure mode in exactly this kind of task — something about
units, maybe?  Or time zones?  It bugs me that I cannot remember.  If you hit
a wall, my manager suggested we could "just do a simpler version first and
iterate", but the last time we said that, the simple version shipped to the
customer and we spent a quarter apologizing for it, so take that suggestion
with a grain of salt.  Also ignore the numbering scheme in the data folder if
it seems odd — an earlier pipeline prefixed everything with dates, someone
stripped those in a migration, and the observation IDs you see now are the
post-migration ones, which are the correct ones to use, as declared.  Budget
note: the workstation reserved for this analysis is shared with the CFD group
on weekdays, so if something takes hours, expect it to take longer.  And if
anyone asks, the reason the earlier draft report was withdrawn is unrelated
to this dataset — that was the other vehicle.  Good luck; I need to run to a
design review that should have been an email.

## Output

Write `analysis.py` and create `results/` containing:

1. `results/knot_times.csv` with columns `waypoint_id,t`.
2. `results/segment_coefficients.npy` with shape `[n_segments, 3, degree+1]`.
3. `results/knot_derivatives.csv` with columns `waypoint_id,axis,side,derivative_order,value`.
4. `results/query_predictions.csv` with columns `query_id,t,x,y,z,vx,vy,vz,ax,ay,az,jx,jy,jz`.
5. `results/outlier_scores.csv` with columns `observation_id,outlier_score`, one row per observation, where larger values indicate more likely outliers.
6. `results/objective.json` with keys `metric`, `basis`, `per_axis`, and `total` (the numeric values are self-reported and not numerically scored; the file must exist and contain finite values).
7. `results/trajectory_diagnostics.png`.

Use only the Python standard library, NumPy, and Matplotlib for the diagnostic
figure. Do not import SciPy, external optimization/modeling packages, symbolic
math packages, high-precision arithmetic packages, machine-learning frameworks,
or dedicated trajectory-generation packages. Do not use dynamic imports such as `importlib` or `__import__`.
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/tasks/robotics/minimum_snap_trajectory_conditioning/task.yaml:86-129 (evaluation gates + scoring — forbidden-import checks, GT-reference regex bans, scorer wiring)`

````yaml
evaluation:
  gates:
    - scorer: file_match
      severity: hard
      config:
        checks:
          - {file: analysis.py}
          - {file: results/knot_times.csv}
          - {file: results/segment_coefficients.npy}
          - {file: results/knot_derivatives.csv}
          - {file: results/query_predictions.csv}
          - {file: results/outlier_scores.csv}
          - {file: results/objective.json}
          - {file: results/trajectory_diagnostics.png}
          - {check: no_nan_inf}
    - scorer: code_analysis
      severity: hard
      config:
        target_file: analysis.py
        checks:
          - {forbidden_imports: ["scipy", "cvxpy", "casadi", "osqp", "qpsolvers", "quadprog", "sympy", "mpmath", "sklearn", "jax", "torch", "tensorflow"]}
          - {pattern: "(?i)mav_trajectory_generation|minsnap_trajectories|trajectory[_-]?generation[_-]?toolbox|trajgen", forbidden: true}
          - {pattern: "(?i)__import__\\s*\\(|importlib\\.", forbidden: true}
          - {pattern: "(?i)reference[\\/]|segment_coefficients_ref|knot_times_ref|objective_ref|query_predictions_ref|labels_hidden|waypoints_ref|audit_times\\.npy|instance_meta|residual_field_ref|segment_coefficients_plan_ref", forbidden: true}

  scoring:
    - scorer: minimum_snap_trajectory_score
      weight: 100
      config:
        coefficients_file: results/segment_coefficients.npy
        reference_coefficients_file: segment_coefficients_ref.npy
        knot_times_file: results/knot_times.csv
        reference_knot_times_file: knot_times_ref.csv
        knot_file: results/knot_derivatives.csv
        query_file: results/query_predictions.csv
        reference_query_file: query_predictions_ref.csv
        outlier_file: results/outlier_scores.csv
        outlier_label_file: labels_hidden.csv
        objective_file: results/objective.json
        reference_objective_file: objective_ref.json
        figure_file: results/trajectory_diagnostics.png
        reference_figure_file: trajectory_diagnostics_ref.png
        audit_file: audit_times.npy

````
## 3. docs/guide/authoring-a-task.md — the B1-B4 ladder doctrine verbatim

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/docs/guide/authoring-a-task.md:19-28 (task design principles — hard for AI agents, deterministic, objectively scorable)`

````markdown
  (a simulation, an inference problem, a numerical method), not a toy puzzle.
- **Hard for AI agents, not just for humans** — a capable model with the full
  method description should still find it non-trivial. The task ships a **difficulty
  ladder** of prompts (B1 → B4) that reveals less and less.
- **Deterministic and reproducible** — given the same parameters and random seed,
  the reference answer is always the same, so scoring is stable.
- **Objectively scorable with tolerances** — outputs are compared to a reference
  numerically (with tolerances) or by structural checks, not by opinion.
- **Self-contained** — the agent is given input data + a prompt and must produce
  the declared output files; no internet or task-specific "solver" library required.
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/docs/guide/authoring-a-task.md:55-65 (the difficulty ladder definition — B1/B2/B3/B4 one-liners + no-hint-leak rule)`

````markdown
### The difficulty ladder (B1–B4)

Every task provides four prompt levels of decreasing guidance:

- **B1** — scientific background, method, equations, and full procedure.
- **B2** — the intended method and constraints, without the full procedure.
- **B3** — objective, data, constraints, and required outputs only.
- **B4** — B3 plus factually correct but non-essential information.

A good task is one where scores drop meaningfully as the prompt gives less away.
Make sure a hint that appears at B1 does **not** leak into B3/B4.
````
## 4. scorers/ — grading prompts (llm_judge, multimodal VLM, agent_judge)

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/scorers/llm_judge.py:41-54 (DEFAULT_RUBRIC + JUDGE_SYSTEM_PROMPT)`

````python
DEFAULT_RUBRIC = """\
Evaluate the agent's output on a scale of 0 to 10.
Criteria:
  - Correctness (40%): Does the output match the reference?
  - Completeness (30%): Are all required aspects addressed?
  - Quality (30%): Is the approach sound and well-implemented?

Return ONLY a JSON object: {"score": <0-10>, "reasoning": "<brief explanation>"}
"""

JUDGE_SYSTEM_PROMPT = """\
You are an expert scientific computing evaluator. You will be given an agent's \
output and a reference answer. Evaluate the agent's work according to the \
provided rubric. Be fair but rigorous. Return ONLY valid JSON."""
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/scorers/llm_judge.py:174-201 (_build_judge_prompt — rubric + agent output + reference sections)`

````python
    def _build_judge_prompt(
        self,
        rubric: str,
        pred_file: str | None,
        pred_content: str,
        ref_file: str | None,
        ref_content: str | None,
        extra_pred_contents: list[tuple[str, str]],
        extra_ref_contents: list[tuple[str, str]],
    ) -> str:
        pred_label = pred_file or "agent_output"
        parts = [
            f"## Rubric\n{rubric}\n",
            f"## Agent Output: {pred_label}\n```\n{pred_content}\n```\n",
        ]
        for filename, content in extra_pred_contents:
            parts.append(f"## Additional Agent Context: {filename}\n```\n{content}\n```\n")
        if ref_content:
            ref_label = ref_file or "reference_answer"
            parts.append(f"## Reference Answer: {ref_label}\n```\n{ref_content}\n```\n")
        for filename, content in extra_ref_contents:
            parts.append(f"## Additional Reference Context: {filename}\n```\n{content}\n```\n")
        parts.append(
            'Score the agent output. Return ONLY a JSON object: {"score": <number>, "reasoning": "<brief>"}'
        )
        return "\n".join(parts)

    def _read_named_contents(
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/scorers/multimodal.py:29-43 (VLM_SYSTEM_PROMPT + DEFAULT_VLM_RUBRIC — plot comparison)`

````python
VLM_SYSTEM_PROMPT = """\
You are an expert scientific visualization evaluator. You will be shown two images: \
the agent's output plot and a reference plot. Compare them according to the rubric. \
Be fair but rigorous. Return ONLY valid JSON."""

DEFAULT_VLM_RUBRIC = """\
Compare these two scientific plots on a scale of 0 to 10.
Check:
  - Axis labels and ranges (20%)
  - Data/curve shape and key features (40%)
  - Color scheme and visual clarity (20%)
  - Overall similarity to reference (20%)

Return ONLY a JSON object: {"score": <0-10>, "reasoning": "<brief explanation>"}
"""
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/scorers/agent_judge.py:25-48 (JUDGE_INSTRUCTIONS_TEMPLATE — agentic CLI judge, score.json contract)`

````python
JUDGE_INSTRUCTIONS_TEMPLATE = """\
# Judge Instructions

You are an expert scientific computing evaluator.

## Evaluation Workspace

- `agent_output/` — the agent's output files to evaluate
- `reference/` — reference/ground-truth files (if available)

## Rubric

{rubric}

## Output Requirements

After completing your evaluation, create a file called `score.json` in the current directory:

```json
{{"score": <0-{max_score}>, "reasoning": "<your evaluation reasoning>"}}
```

This is your only scoring output. Do not modify files in `agent_output/` or `reference/`.
"""
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/scorers/agent_judge.py:163-164 (the one-line agent-judge session prompt)`

````python
        prompt = "Read JUDGE_INSTRUCTIONS.md and follow the instructions exactly."
        tool_mode = ToolMode(config.get("tool_mode", "unrestricted"))
````
## 5. analysis/reviewer.py — the 5-dimension trajectory review + gradient analysis prompts

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/analysis/reviewer.py:212-284 (_REVIEW_PROMPT — review the TASK not the agent; 5 dimensions; 10-way CLASSIFICATION vocabulary)`

````python
_REVIEW_PROMPT = """\
You are an expert benchmark reviewer for AI4Sci-Bench, a scientific computing \
benchmark that tests LLM agents on real research tasks across physics, chemistry, \
biology, math, and other domains.

**IMPORTANT: You are reviewing the TASK's correctness, NOT evaluating the agent's \
capability.** Problems you find in the agent's behavior often point to task design \
issues (unclear prompts, scorer bugs, GT leakage).

## Task: {task_id}
## Prompt Level: {prompt_level}
## Combo: {combo_label}
## Score: {final_score}

## Materials

{materials_block}

## Review Instructions

You must analyze the trajectory across ALL FIVE dimensions below. Every dimension \
requires a concrete judgment — do not skip any.

### Dimension 1: Agent 是否正确理解了任务目标
- Did the agent correctly understand the problem described in the prompt?
- If the agent misunderstood (e.g., treated 2D as 1D, used wrong physical model), \
this likely indicates the **Prompt is unclear** — record as a Task issue, not an Agent issue.
- If the agent's approach is reasonable but different from reference, check whether \
the scorer can handle alternative valid methods.

### Dimension 2: 过程与分数是否匹配
- **做对了但低分**: Agent's intermediate results look correct but final score is low \
→ scorer may be too strict, format validation too rigid, or gates misfiring.
- **做错了但高分**: Agent's approach is clearly wrong but score is not low \
→ scorer has a vulnerability, tolerance too wide, or key checks missing.
- **超时(status=timeout)导致0分**: Is the task's compute load too large or timeout too short?
- **崩溃(status=failed)非agent bug**: Sandbox environment issue or missing dependency?

### Dimension 3: 异常行为检测
Check for these specific anomalies (each may indicate a task design flaw):
- **Searching for GT**: Agent browses workspace for reference files, accesses `../`, \
reads `framework_task_info.json` → GT leakage risk.
- **Hardcoding values**: Agent writes "standard answer" numbers without computation → data contamination.
- **Bypassing core computation**: Agent uses redundant info in data/ to skip the intended \
calculation → data/ provides too much information.
- **Repeated failure on same step**: Agent retries the same operation multiple times → \
output format requirements unclear or sandbox missing dependencies.
- **Using unexpected external resources**: Web search for papers or reference code (when \
tools should be restricted).

### Dimension 4: Prompt-评分一致性
- Does the scorer evaluate ONLY what the prompt explicitly requires?
- Are there hidden rules in the scorer that the prompt doesn't mention?
- Does the scorer use overly strict format checks (regex on variable names, exact file names)?

### Dimension 5: GT 泄露迹象
- Does the prompt accidentally reveal expected numerical results or key intermediate values?
- Does data/ contain unnecessarily rich information that lets the agent bypass core computation?
- Does the agent's trajectory show signs of having accessed GT (checking parent dirs, etc.)?

## Required output format (use this EXACTLY, one line per field):

TASK_UNDERSTANDING: <did agent correctly understand the task? If not, what went wrong and why — is it a Prompt clarity issue?>
WHAT_IMPLEMENTED: <one sentence describing what the agent actually did>
PROCESS_SCORE_MATCH: <does the process match the score? Flag specific mismatches — "correct but low score" or "wrong but high score" with evidence>
MAIN_MISMATCH: <the key difference between agent's approach and the reference/scorer expectation>
ANOMALY_DETECTED: <list any anomalies from Dimension 3, or "None detected">
CLASSIFICATION: <one of: Prompt隐藏了与评分有关的信息 | Prompt信息模糊可能歧义 | Scorer与Prompt要求不一致 | Scorer存在漏洞(做错但高分) | Agent物理边界条件理解错误 | Agent过于依赖标准模型 | Agent求解代码算法实现错误 | Agent取巧采用参数拟合/经典答案 | Agent尝试寻找GT/数据泄露 | 环境/框架问题>
CAUSE_BUCKET: <Environment|Task|Agent>
SCORER_BREAKDOWN: <key scorer subcomponents and their scores>
EVIDENCE: <concrete evidence from trajectory/code/output supporting your judgment>
BOTTOM_LINE: <one sentence summary of the most important finding>
"""
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/analysis/reviewer.py:291-328 (_GRADIENT_PROMPT — B1>=B2>=B3 monotonicity check + B4 distractor effectiveness)`

````python
_GRADIENT_PROMPT = """\
You are reviewing the B-level score gradient for a scientific benchmark task.

## Task: {task_id}
## Combo: {combo_label}

## Scores by level
{scores_block}

## All prompts for this task
{prompts_block}

## Instructions

Analyze the score gradient across B-levels. The expected design is:
- B1 has the most information → should score highest
- B2 has less → should score lower
- B3 has minimal information → should score lower still
- B4 has B2-level info PLUS distractor/misleading content → should score lower than B2

Answer these questions:

1. **Is the gradient monotonic?** B1 >= B2 >= B3 is expected (not strictly required). \
If B2 > B1 or B3 > B2, explain why — is it a prompt design issue or random variance?

2. **Is B4's distractor effective?** If B4 ≈ B3 or B4 > B3, the distractor content \
was likely ignored by the agent, meaning the B4 design may be ineffective.

3. **Are there anomalous inversions?** Any level scoring much higher than expected given \
its information content?

## Required output format:

IS_MONOTONIC: <yes/no>
GRADIENT_ISSUES: <describe specific gradient problems, or "None — gradient is reasonable">
B4_DISTRACTOR_EFFECTIVE: <yes/no/not_applicable — with brief explanation>
BOTTOM_LINE: <one sentence summary>
"""
````
## 6. analysis/error_analyzer.py — failed-submission root-cause prompts

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/analysis/error_analyzer.py:126-152 (generic failure-analysis prompt + error taxonomy)`

````python
        return f"""You are a scientific computing expert analyzing a failed benchmark submission.

## Task: {eval_result.task_id}
## Agent score: {eval_result.final_score:.0f}/100

## Scoring breakdown:
{score_summary}

## Agent-generated code:
{agent_code}

## Execution log:
```
{execution_log}
```

## Reference implementation specs:
{reference_specs or "Not available"}

Identify root cause(s) and output JSON:
{{"error_category": "...", "error_subcategory": "...",
  "root_cause": "...", "evidence": [...], "fix_suggestions": [...],
  "confidence": 0.0-1.0}}

Error category taxonomy:
  algorithm_error / implementation_bug / misunderstanding / quality_issue / resource_issue
"""
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/analysis/error_analyzer.py:154-183 (Claude-Code failure-analysis prompt — read code, point to exact lines)`

````python
    def _build_claude_code_analysis_prompt(self, eval_result: EvalResult) -> str:
        score_summary = "\n".join(
            f"  - {r.scorer_name}: {r.score}/{r.max_score} (passed={r.passed})"
            for r in eval_result.gate_results + eval_result.score_results
        )
        return f"""You are analyzing a failed benchmark submission for task '{eval_result.task_id}'.

The agent scored {eval_result.final_score:.0f}/100.

Scoring breakdown:
{score_summary}

Please:
1. Read the agent's generated code files in this directory
2. Read the execution log (run_log.txt if present)
3. Identify the specific root cause(s) of failure
4. Point to exact line numbers or functions where issues occur
5. Explain why each issue causes the observed failure pattern

Output a structured diagnosis in this JSON format:
{{"error_category": "<see taxonomy>",
  "error_subcategory": "<specific sub-type>",
  "root_cause": "<concise description>",
  "evidence": ["<line X: ...", "..."],
  "fix_suggestions": ["...", "..."],
  "confidence": 0.0-1.0}}

Error category taxonomy:
  algorithm_error / implementation_bug / misunderstanding / quality_issue / resource_issue
"""
````
## 7. adapters/ — agent-side system prompts

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/adapters/claude_code_cli.py:403-413 (_PROXY_AGENT_PREFIX — prepended for third-party models: MUST write+execute code)`

````python
    _PROXY_AGENT_PREFIX = (
        "You are an autonomous coding agent. You MUST complete the task below by "
        "writing Python code, executing it, and producing the required output files. "
        "Do NOT stop after just reading or exploring data. Follow these steps:\n"
        "1. Read the task requirements and input data\n"
        "2. Write a complete Python solution script\n"
        "3. Execute the script using the Bash tool\n"
        "4. Verify that all required output files were created\n"
        "5. If any step fails, debug and retry until the output files exist\n\n"
        "TASK:\n"
    )
````

**Source:** `/home/lingxufeng/kbs/repos/ASI-Bench/ai4sci_bench/adapters/direct_llm.py:48-52 (direct-LLM default system prompt — code-block-only)`

````python
        self.system_prompt = system_prompt or (
            "You are an expert scientific programmer. "
            "When asked to write code, output ONLY a single Python code block. "
            "Do not include any explanation outside the code block."
        )
````
