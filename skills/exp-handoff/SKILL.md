---
name: exp-handoff
description: "Experiment step 5 — memory and handoff: when an X reaches a terminal state or the window passes ~400k tokens, write the handoff file and the pitfall/finding memories, then open a fresh session (never compact). Use when the user says 交接 / handoff / 记忆."
---

# exp-handoff — 落盘即信仰；聊天不是档案

硬核（≤10 行，每条有出处）
1. 每次事故一个防再犯工件：`anomalies.md` 一行 + 一个测试（Methodology L4）。
2. 三态近似审计：`deviation_notes.json` 每条 ✅一致 / 📋登记带理由 / ❌回炉；无登记的近似 = C.3 blocking（Methodology L4）。
3. 交接不 compact：先 `git status`，再写六节交接文件，再开新会话（worker 设计 §4.9；RS context discipline Rule 1）。
4. 记忆一事一文件，带 frontmatter（type / hook），索引一行（Methodology L3）。

步骤
1. `git -C /tmp/wt-<X> status`；未 commit 的以 `wip:` 标未验证部分。
2. 写 `.research/build/<X>/handoff-<date>.md` 六节：状态（台账 status / gate / level）· 已验证的事实（带 file:line）· 未验证的假设 · 下一步命令（逐字）· 禁区 · 本轮 pitfall。
3. pitfall / finding → `memory/`（一事一文件）+ `MEMORY.md` 一行；仪器变化 → `instruments/README.md`。
4. 新会话从 `/exp-next` 或 `handoff` 文件的"下一步命令"继续。
