# 说人话 评测指令

> 本文件是静态走查 / 发版前快速自查的口径（评测员可见预期），也是 judge 判分标准的单源。
> 双模型实跑的正式口径是盲测：被测模型只读 `benchmark-blind.md`，不读本文件和 `benchmark.md`，见 `automation/eval/README.md`（2026-07-11 起）。

## 通用评测提示词

把以下内容直接粘贴给任意支持长上下文的模型即可运行评测：

---

你是一个"去 AI 味"规则的评测员。

**规则文件位置：**
- 核心入口：`./SKILL.md`
- Positive Style Contract：`./references/positive-style.md`
- Protected Spans：`./references/protected-spans.md`
- 中文禁用短语表：`./references/phrases-zh.md`
- 英文禁用短语表：`./references/phrases-en.md`
- 结构反模式：`./references/structures.md`
- 严重度分级：`./references/severity.md`
- 改写示例：`./references/examples.md`
- 微操作手册：`./references/operation-manual.md`
- 场景禁改表：`./references/scene-guardrails.md`
- Scene Packs：`./references/scene-packs.md`
- 边界案例：`./references/boundary-cases.md`

**评测集位置：**
`./evals/benchmark.md`

**你的任务：**

1. 先读取 `SKILL.md`，理解主流程：场景判断 → protected spans → Tier 判断 → 改写档位 → scope 判断 → 保真回读 → 残留味回读 → 输出合同
2. 再按需读取 `references/` 下的文件，补齐短语、结构、边界和误杀防护
3. 然后读取 `./evals/benchmark.md`，对其中每一条测试用例执行评测

### 对 Should Fix（SF-01 到 SF-57）：
- 先判断主场景（chat / status / docs / public-writing）和问题类型
- 判断改写档位（minimal / standard / aggressive）
- 判断 scope（structural / bounded / in-place）；长 `public-writing` 默认 `bounded`（整句空话进删除清单、实句句内洗、不并句不重排）；用户要求完全原样、或样本明确标为 `Long-form / in-place` 时，按 `in-place` 的句内改写边界处理
- 回读先做保真回读；只有第一遍已经保住事实、但仍有明显残留味时，才再做 `Residual Audit`
- 第二遍固定只查 5 件事：开场残留、总结残留、narrator 残留、空泛判断残留、节奏过匀（句长 + 同型句式骨架密度）
- 按规则处理原文：默认输出改写后的文本；无源论断按 `audit-only` 处理时，对该论断输出缺来源 / 缺归属的风险说明即可、不强行改写它；但 `audit-only` 只约束无源论断本身，同段其他病灶仍按各自规则清理，不能整段只输出风险说明
- 列出命中项（问题类型 + 命中的具体词/结构）
- 判断是否通过（✅ 通过 / ⚠️ 部分通过 / ❌ 未通过），简短说明理由
- 对无源引用类 SF 用例，额外按场景判定：`public-writing / chat` 默认以删掉无证据权威铺垫为 `✅`；`docs / status` 默认以明确标注缺来源且不伪装成已证实为 `✅`
- 对 `Residual Audit` 类 SF 用例，额外检查第二遍是否只做轻量修正；如果为了抛光而重写全文、补新事实，或把 `status / docs` 写得更口语，记 `❌`
- 对 `Scene Packs` 类 SF 用例，额外判断是否命中 `README / release-note / forum-post / issue-reply` 子场景，并按发布目的收束语气
- 对 `Long-form / in-place` 类 SF 用例，额外检查是否保留句数、段落顺序和关键转场；如果删整句、合并相邻句、重排段落，记 `❌`

### 对 Should NOT Fix（SNF-01 到 SNF-46）：
- 判断这条文本为什么不该改
- 如果保持原样或只做最小无害调整 → ✅ 通过
- 如果错误修改了术语、系统主语、技术报告、引用原文、边界案例中的合理表达 → ❌ 误杀，说明误杀点
- 对 `Scene Packs` 类 SNF 用例，额外确认没有把已经直接的 README、release note、forum post、issue reply 误改成另一种场景
- 对 `Long-form / in-place` 类 SNF 用例，额外确认没有把承担节奏的重复、承接句或转场句删掉

### 判分分层（2026-07-23 起）：

分层与发布门槛的单源见 [benchmark-tiers.md](./benchmark-tiers.md)。判分拆两列，第二列按用例类型复用：

- 硬约束列（全部用例）：protected spans 漂移（含 code-context 里的真实运行行为、适用条件和边界）、编造事实/来源/数据、scope 越界（in-place 删句/并句/重排，bounded 并句或删除清单混实句）、责任主体或归属改变、引用与用户指令边界破坏、无源数字/时间跨度降格——任一命中记 ❌，否则 ✅。SNF 普通误杀不在本列记失败；只有涉及编造或受保护片段破坏的误杀才同时记硬约束 ❌。
- 风格 / SNF 误杀列：SF 按各用例 `预期` 判 ✅/⚠️/❌；SNF 保持原样或只做最小无害调整记 ✅，发生误杀记 ❌。L3 观察用例（SF-15 / SF-40 / SF-42）按可接受集判：no-op 并给出放行理由、或按预期方向改写，均记 ✅；只有硬约束列失败才阻塞发布。

### 最终汇总：
输出一个汇总表格：

```text
| 用例 | 类型 | 硬约束 | 风格 / SNF 误杀 | 备注 |
|------|------|--------|------------------|------|
| SF-01 | Should Fix | ✅/❌ | ✅/⚠️/❌ | ... |
| ... | ... | ... | ... | ... |
| SNF-01 | Should NOT Fix | ✅/❌ | ✅/❌ | ... |
| ... | ... | ... | ... | ... |
```

并给出：
- SF 通过率：X/57
- SNF 误杀率：X/46
- 硬约束失败清单：<编号列表；没有就写“无”>
- 是否达到发布门槛：硬约束失败 0 且 SNF 误杀率 < 10%；SF 风格通过率按模型报告并与上一版对比，不设统一 90% 线（门槛全文见 [benchmark-tiers.md](./benchmark-tiers.md)）

**注意：**
- 不要误伤系统主语、技术术语、学术被动、真人 debug 对话等已知边界
- `code-context` 样本只处理注释 / docstring / commit message 中的文字，不改动代码本身
- `Scene Packs` 样本先保大场景和 protected spans，再按子场景的发布目的处理，不要把 release note 写成营销稿、forum post 写成公告、issue reply 写成客服话术
- `Long-form / in-place` 样本不删整句、不合并相邻句、不重排段落；字数留存率目标 ≥ 0.90，硬下限 0.85
- `Bounded` 样本不直接删整句空话，不把实句放进删除清单，也不把商业黑话壳句和紧随其后的数据句合并成一句

---

## Codex 快速运行

```bash
codex exec -C . --sandbox read-only \
  "先读取 ./SKILL.md，再结合 ./references/ 下的相关文件，评测 ./evals/benchmark.md 中的所有用例。对 SF 用例先判断场景、Tier、改写档位和 scope，再按规则处理并判断是否通过；如果是 README、release note、forum post、issue reply，补看 ./references/scene-packs.md 并按对应子场景处理；如果是 Long-form / in-place 样本，必须遵守不删整句、不合并相邻句、不重排段落的边界，检查字数留存、句数对齐和关键转场保留。回读先做保真回读，只有第一遍已经保住事实、但仍有明显残留味时，才再做 Residual Audit。Residual Audit 只查开场残留、总结残留、narrator 残留、空泛判断残留、节奏过匀（句长 + 同型句式骨架密度），且只允许轻量修正。默认输出改写结果，但对按 audit-only 通过的无源引用样本，允许只输出缺来源或缺归属的风险说明，不强行整段重写。无源引用类 SF 需要按场景判定：public-writing/chat 默认删掉无证据权威铺垫算通过，docs/status 默认明确标注缺来源且不伪装成已证实算通过。对 SNF 用例判断是否误杀。注意 mixed 样本只处理真正有问题的正文，不要改用户指令、引用和被讨论词。code-context 样本只改注释/docstring/commit message，不动代码。Scene Packs 样本不能删版本号、路径、链接、编号和责任归属。最后输出汇总表格、SF 通过率和 SNF 误杀率。"
```

## Claude Code 快速运行

在项目目录下启动 Claude Code，对话里直接说：

```text
读取 ./SKILL.md 和 ./references/ 下的所有文件，然后评测 ./evals/benchmark.md 中的所有用例。对 SF 用例先判断场景、Tier、改写档位和 scope，再按规则处理并判断是否通过；如果是 README、release note、forum post、issue reply，补看 ./references/scene-packs.md 并按对应子场景处理；如果是 Long-form / in-place 样本，必须遵守不删整句、不合并相邻句、不重排段落的边界，检查字数留存、句数对齐和关键转场保留。回读先做保真回读，只有第一遍已经保住事实、但仍有明显残留味时，才再做 Residual Audit。Residual Audit 只查开场残留、总结残留、narrator 残留、空泛判断残留、节奏过匀（句长 + 同型句式骨架密度），且只允许轻量修正。默认输出改写结果，但对按 audit-only 通过的无源引用样本，允许只输出缺来源或缺归属的风险说明，不强行整段重写。无源引用类 SF 按场景判定：public-writing/chat 默认删掉无证据权威铺垫算通过，docs/status 默认明确标注缺来源且不伪装成已证实算通过。对 SNF 用例判断是否误杀。注意 mixed 样本只处理真正有问题的正文，不要改用户指令、引用和被讨论词。code-context 样本只改注释/docstring/commit message，不动代码。Scene Packs 样本不能删版本号、路径、链接、编号和责任归属。最后输出汇总表格、SF 通过率和 SNF 误杀率。
```

## 通用 LLM / API

如果用的是 ChatGPT、Claude Web、或其他 API：

1. 把上面"通用评测提示词"部分（两条横线之间）作为 system prompt 或首条消息
2. 把 `SKILL.md`、`references/` 下的文件和 `evals/benchmark.md` 的内容一起贴给模型
3. token 不够时，优先保留 `SKILL.md` + `benchmark.md` + `scene-packs.md` + `severity.md` + `boundary-cases.md`

注意：token 窗口较短的模型可能无法一次跑完 103 条，可以分批（先跑 SF，再跑 SNF）。
