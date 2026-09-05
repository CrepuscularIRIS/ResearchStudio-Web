# V8 论文 TS 方案 — 一个 findings-ledger 修订环 × 表先于实验存在的下半场

草稿 2026-09-05。配 PIPELINE-V8-PLAN.md(总)与 EXPERIMENT-PLAN(上游)。必读源已全部读完:

- **leaks 四件**(无现成 paper workflow,规则形状嵌在通用 prompt 里):claude-science.md(结果保真律/
  findings 账本/引用句锚/图门槛/散文律)、claude-for-word.md(双车道编辑/回读验证/渲染复审/诚实范围/
  页数即门槛/逐节起草)、artifact-report.md(三声道/slot-锚点 lint)、deep-research js(claim-quote+quorum,自家惯例)
- **AI-Scientist-v2**(perform_writeup/icbinb/plotting/llm_review/vlm_review):图表聚合器合同、引用环、
  分节 tips+LaTeX bug 清单(逐字)、反思环注入脚本算出的事实、NeurIPS 评审 schema+锚文+正负校准对、
  确定性检查(chktex/图引用审计/pdftotext 页限/标题去重/清理正则)、哨兵早退
- **自家已定**:D0 终稿表格骨架、R4 claim-evidence 矩阵、E 重算表、C.strength 天花板(ARIS scope 用词表)、
  CCFA harvest(§4d 十五偷:storyline 证据阶梯、claim-evidence 矩阵字段、check_prose_quality.py 移植、
  一表一信息、compression 保护清单)、ARIS 横切守卫(偏置守卫/禁环/回据重验)

---

## 0. 定位

paper.workflow.js 吃的是:Claim C(statement+strength)+ D0 的三表骨架(槽已由 T4/T5/T6 回填)+
R4 矩阵(每 row 的 status)+ E 重算表(唯一合法数字来源)。**表先于实验存在,文追表**。
两个原则:①**数字只从重算表回读**(claude-science 结果保真律:报告数值必须 read_file 回读逐字拷贝,
禁凭记忆重打;索引/切片跑代码不目测);②**review findings 进账本、修复经确认不静默**(mark_addressed
只是自报"待复核",下一轮审稿确认或重新浮起)。

## 1. 阶段表 P0-P5

| 相 | 内容 | 席 | 判据/合同 |
|---|---|---|---|
| P0 prewrite | 装配:R4 矩阵→表计划;图表聚合器脚本(每个 plot 独立 try-catch、dpi300、标签无下划线、数据路径逐字来自重算表、**禁编数据**);引用候选**先取 lit 表**(S2 只补缺,轮 ≤5,标题级去重,bib 注入) | GLM×2 + 脚本 | AI-S2 聚合器合同逐字;图引用白名单与 legend 名从脚本源读出(AI-S2:writeup prompt 里放聚合器源码) |
| P1 draft | 逐节起草(for-word 协议:先全大纲→一次一节→每轮重读大纲对照);模板骨架定节序;每句数字带 `%C-n` 行标记;method/公式节 sol;三声道(测得/推断/猜测分声);每节结论先行 | GLM 逐节 + sol(方法节) | 分节 tips + LaTeX bug 清单逐字(未闭数学/重复标签/未转义 &%$#_{}~^\\/ / 表图闭合/**禁编造日志外结果**/禁占位残留);claim 锚到支撑句 span;C.strength 用词天花板 |
| P2 verify | 全确定性,模型零参与 | **脚本** | 编译硬门(pdflatex→bibtex→pdflatex×2,无 PDF=blocked——修 AI-S2 吞异常之病);chktex;图引用正则审计(includegraphics 基名 vs figures/*);slot/TOC 锚点 lint(无 TODO/占位、TOC 条条有节);页限(pdftotext 清行计数,三级反馈);**精确串数字门**(正文每个数字 ∈ 重算表,%C-n 标记条条可解析) |
| P3 review | 裁判席:NeurIPS schema(Summary/Strengths/Weaknesses/三维 1-4/Overall 1-10/Confidence/Decision)+ 锚文校准 + **正负校准对**(bad-or-unsure→reject vs good-or-unsure→accept,各跑一份);外族 Grok;findings 入账本(带锚:节/行/数字) | Opus + K3 + Grok(+sol 数字复核) | 每 finding ≥1 锚;THOUGHT+JSON 两段协议;"不许用平均抹掉致命伤";VLM 图审三对齐(图/说明/引用) |
| P4 revise | 双车道:机械(错字/编号/转义)直改;实质(语义)staged 补丁提案;每笔后回读;修完查附带损伤;**mark_addressed 只标待复核** | GLM + Opus 仲裁 | 偏置守卫(每轮 fresh context,禁"since last round"——AI-S2/ARIS 实证灌分);禁环条款(删带锚跨度≠修复);修订台账 done 需 artifact |
| P5 stop | 两轮无 high 未决或轮帽 ≤2(AI-S2 实证:轮1 结构 4→6,轮2 表述 6→7,再后边际递减) | 脚本 | 收敛=账本无 high 未决且 P2 全绿;strength 用词复核(robust/extensive 仅 T5+T6 完成后允许) |

## 2. 与上游的接口(dag)

- 触发:experiment 侧 T6 完成或 C.strength ∈ {adequate,strong}(dag 已在 ladder 完成处 STOP,改派 paper)。
- draft 条件 = 稿中无 `%C-n` 行(重跑安全);paper 轮帽 2,收敛即 STOP: DONE。
- E 枚举→行 status 映射:supports→supported / partial→needs-qualifier(收窄句进 limitations)/
  refutes→row 撤回(C.strength=refuted 时整个 paper STOP 不写)。
- 图表:每表一信息、caption 三件(what+setting+takeaway)、表值精度一致(不暗示假精度)——CCFA §4d 已载。

## 3. 席位账(每稿)

GLM:P0×2 + 逐节起草(≤8)+ 修订 ≤2 轮;sol:方法节 1 + 数字复核 1;K3:裁判 1;Opus:meta/AC 1
(集成分数=有效域内均值,AI-S2 确定性覆盖);Grok:外族裁判 1。昂贵 ≈ sol 2 / K3 1 / Opus 1 / Grok 1。
渲染复审:pdftotext+chktex 全脚本;VLM 图审走 GLM 图卡(同 RS 前置纪律)。

## 4. 确定性检查清单(P2 脚本,一次跑全)

编译四连硬门 | chktex -q -n2 -n24 -n13 -n1 | 图引用审计 | slot/TOC 锚点 | 页限(pdftotext,
icml 8 页级) | **精确串数字门**(逐数字 grep 重算表,numeric-token 相等) | %C-n 标记全解析 |
标题级 bib 去重 | 清理正则(/end→\end、弯引号、`\d+%`→`\d\%`)。

## 5. 偷/不偷(AI-S2 裁决)

偷:反思环注入脚本事实的形状;哨兵早退;THOUGHT+JSON;评审 schema+锚文+校准对;ensemble→AC 均值;
引用环(降轮 ≤5、lit 表优先);聚合器源码进写作 prompt(legend 保真);try-catch 每图;页限行计数;
LaTeX bug 清单逐字。
不偷:**整文件重写式反思**(O(全文)/轮,我们补丁);**吞编译异常**(改为硬门);**review 终端化**
(v2 浪费了它的裁判——我们 findings 回流修订);20 轮引用/3 次全文重试(预算);单发全文生成
(骨架带结构,但节必须 claim 锚定从记录生长)。

## 6. 待定

1. 模板:icml 骨架(AI-S2 blank_icml_latex)起手还是 venue 无关骨架?2. VLM 图审进 P3 还是 P0 生成时?
3. sol 方法节的边界(公式推导 vs GLM 全写)?4. S2 补引的工具通道(GLM Bash 既有 search 脚本复用)。
