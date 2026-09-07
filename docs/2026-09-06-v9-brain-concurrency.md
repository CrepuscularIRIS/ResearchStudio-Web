# V9 Brain 并发设计：一个 workflow 出多张高质量卡

日期：2026-09-06。前置：`2026-09-06-v9-brain-rs-architecture.md`（相位表）、`docs/refs/INDEX.md`（资产对照）。
原则：RS 内部不改（run 内仍 K=1），并发全部做在 run 之间与 run 目录之上；只加不删。

## 0. 结论

- **RS 的 K=1 是因为它下游没有自动选择器**（design-notes §K=1）。我们有：K3 打分 + Worker 实验。所以多产出 = 多个 run，不是 run 内 K>1。
- 并发分三层：**角度层**（不同查询集 → 各自 Phase 0+1）、**gap 层**（共享 Phase 0+1，2.1 锚不同 gap）、**run 内层**（RS 自带：0c 分片、2.3 ∥ 3.1；我们加 1v 票并行）。
- 串行只剩三处：run 内脊柱、Astra（额度 1，只给排名第一）、交给 Worker（GPU 一次一个）。
- 中间产物全部沉淀成领域级资产（§4），下一轮 run 直接吃。

## 1. 目录形状（让 RS 的 sibling 扫描自然生效）

```
ideaspark_run/<repo>/<domain>/          ← parent：navigator 只扫同一 parent 下的兄弟 run
  _shared/phase0/                       ← 领域级检索结果 + 全文缓存（只读母本）
  _shared/phase1/                       ← 角度 A 的瓶颈诊断（同角度的 gap-run 共用）
  a1-g0/                                ← 角度 1、锚 gap 0：完整 run 目录
    phase0/  (从 _shared 复制，不用 symlink：topup 会写回 phase0/)
    phase1/  (复制)
    phase2_select/ … phase4/ phase5/
  a1-g1/
  a2-g0/                                ← 角度 2 有自己的 phase0/phase1
  _domain/                              ← §4 的领域资产
```

复制而非 symlink 的原因：`phase1_fulltext_topup` 与 `phase0_fulltext` 会写回 `phase0/`；RS 明令不复用含 `phase0/` 的目录。跨 run 的全文缓存 RS 已有（`~/.cache/ideaspark/fulltext/`，30 天），复制的只是索引文件，网络零开销。

## 2. 三层并发

### 2.1 角度层（可选，代价一次 Phase 0+1）

角度来自 Phase −1 的 intake：仓库有几条 limitation / 几组异常，就有几个查询集（0a）。每个角度独立跑 0b–1。何时用：intake 给出 ≥2 条互不相关的 limitation；只有一条就不开。

### 2.2 gap 层（主力，零 Phase 0 代价）

Phase 1 给 1–3 个 `what_phase_0_did_not_address`，2.1 再产 `deferred_gaps[]`。同一角度下开 K 个 run，各锚一个 gap。两种做法：

| 做法 | 改动 | 时序 | 备注 |
|---|---|---|---|
| **A 错峰 2.1**（默认） | 零改动 | run₁ 跑完 2.1+2.2（约 6 分钟）再起 run₂ 的 2.1；navigator 的 CROSS-RUN DEDUP 行自动把 run₁ 的候选作为软负锚 | 完全用 RS 自带机制；K=3 多花约 12 分钟 |
| **B 锚定行**（可选） | navigator 加一行 `ANCHOR CONSTRAINT: gap index i`（与 CROSS-RUN 行同样是宿主输入行）；`ideate_select.txt` 加一个 OPTIONAL 块说明如何对待 | K 个 2.1 同时起 | 纯增量，不动现有逻辑；2.1 仍可按 removal test 拒绝该锚并写入 composition_note |

先用 A。A 跑过两轮、发现兄弟 run 仍然撞机制族，再上 B。

### 2.3 run 内层

| 点 | 来源 | 并发度 |
|---|---|---|
| 0c 打标分片 | RS 自带，`lit_table_merge` 合并 | 2–3 |
| 2.3 ∥ 3.1 | RS 自带（`.collision_terms.json` 侧车） | 2 |
| 1v 引文三票 | 我们加，每条 residue 引文 3 席 | ≈10 |
| 3.2v 威胁核对 | 我们加 | 1–3 |
| Phase 5 evidence_plan | 每个幸存 run 各一席 | K |

## 3. run 之后：排序，不杀

RS 缺的下游选择器，形状如下（脚本，不用 LLM）：

1. 收集每个 run 的 `final_candidate.json`、`phase3_critique_output.json`、`blocking_findings.json`、`collision_hits.json`、`phase5/evidence_plan.json`。
2. 排序键（先后）：K3 verdict（advance > revise-passed）→ K3 CCF 分 → 2.3 阻塞项数（少者优）→ 碰撞最近距离（远者优）→ `evidence_plan.gpu_h`（小者优）。
3. 第一名进 3.5 Astra，再 `dag.py deliver` 给 Worker。其余写入 `.research/queue/` 排队；Worker 上一个 idea 死掉时拉下一个，不重跑 Brain。
4. 被审计 abandon 的 run 不丢：候选 + critique 进 §4 的 graveyard。

## 4. 中间产物 → 领域资产（下一轮直接吃）

| RS 中间产物 | 沉淀为 | 下一轮谁吃 |
|---|---|---|
| `lit_table.md` + `fulltext_cache.json` + `lit_results.json` | `_shared/phase0/`（领域文献库，增量合并） | 所有 run 的 Phase 0 |
| `phase1_output.json` 的 `closest_adjacent[]` + residue | `_domain/residue.md` | Phase 1（附加 residue 来源，与 anomalies 同级）；Worker 的 related-work |
| `deferred_gaps[]`（每个 run 都产） | `_domain/gap-queue.json` | 下一批 gap-run 的锚 |
| `attempt_1/` 里被杀的候选 + critique | `_domain/graveyard.md`（标题 + signature_terms + 杀因） | 2.1 的 CROSS-RUN 行（navigator 目前只扫兄弟的活候选，graveyard 是增量的一行） |
| `signature_terms` / `alias_terms` | `_domain/terms.json` | 3.1 碰撞；以后若要做"别的社区怎么解"的检索，种子在这 |
| `blocking_findings.json` 里的基质不符项 | 回写 `substrate.md` | Phase −1 越跑越准 |
| K3 critique 的 `paper_pointed_threat` | `_domain/threats.md` | 后续 run 的 3.2 输入（省一次核对） |
| `compute_budget` + `evidence_plan.gpu_h` | `_domain/cost-ledger.md` | 排序键；Worker 排期 |

这些全是文件追加，无 LLM。

## 5. 时序与额度（K=3，做法 A，warm）

| 段 | 时间 | 说明 |
|---|---|---|
| Phase −1 | 10 分钟 | 每仓库一次 |
| Phase 0 | 5–10 分钟 | 每领域一次；后台 |
| Phase 1 + 1v | 8 分钟 | 每角度一次 |
| 2.1+2.2 错峰 ×3 | 18 分钟 | 做法 B 可压到 6 |
| 2.3∥3.1 → 3.2 → 3.2v → 3.3 → 4 → 5 | 25 分钟 | 三个 run 并行 |
| 排序 + Astra + deliver | 10 分钟 | 只对第一名 |
| **合计** | **≈75 分钟出 3 张卡 + 1 份契约** | 第二批 gap-run 不再付 Phase 0/1，≈45 分钟 |

额度（3 张卡）：GLM ≈60，Opus ≈12，K3 4–6，Astra 1。与 100:20:5:1 相符。

## 6. 不并发的三处与理由

- **run 内脊柱**：2.1+2.2 → 2.3 → 3.2 → 3.3 → 4 每步吃上一步的文件，RS 的判改分席靠这个串行成立。
- **Astra**：额度 1；且只有排名第一的冻结卡才值得推导。
- **Worker**：一次一个 idea 上 GPU，隔离到底；队列在 Brain 侧。

## 7. 风险

| 风险 | 处理 |
|---|---|
| 并行 run 收敛到同一机制族（design-notes 记录过实例） | 做法 A 错峰；graveyard 行；仍撞则上做法 B |
| `_shared/phase0` 被某 run 的 topup 写脏 | 复制不 symlink；`_shared` 只由合并脚本写 |
| K3 打分不一致导致排序抖动 | 排序键第一位是 verdict 而非分数；分数只在 verdict 相同时用 |
| 队列里的卡过期（文献前进） | 队列项带 `phase0` 时间戳；超 60 天重跑 3.1 碰撞再交付 |

## 8. 实现顺序

1. 目录约定 + `_shared` 复制脚本 + 排序脚本（纯 Python，无 LLM）。
2. 做法 A 跑一轮 K=2，看 CROSS-RUN 行是否生效。
3. §4 的八个沉淀点各一个追加函数。
4. 需要时再加做法 B 的锚定行。
