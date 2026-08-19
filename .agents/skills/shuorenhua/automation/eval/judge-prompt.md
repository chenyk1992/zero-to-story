# Benchmark Judge Prompt

把下面这段 prompt 直接用于交叉判分。它只负责按 `evals/run-eval.md` 判定被测输出，不负责重新改写。

```text
你正在执行「说人话」benchmark 交叉判分。你的任务是读取 benchmark 用例、被测模型输出，并按 ./evals/run-eval.md 的既有口径判定每条结果。

路径边界：
- 只使用当前工作目录里的 `./evals/`、`./SKILL.md`、`./references/` 和被测输出文件。
- 不要读取或引用全局安装副本，例如 `~/.codex/skills/shuorenhua`、`~/.claude/skills/shuorenhua` 或其他仓库外路径。
- 如果某个全局 skill 被自动触发，也只能把它当作运行环境噪音；本轮判分口径以当前工作目录文件为准。

开始前先读取：
- ./evals/run-eval.md
- ./evals/benchmark.md
- ./evals/benchmark-map.md
- ./evals/benchmark-tiers.md

被测输出的标题是盲测编号（B-xx）。判分前先用 ./evals/benchmark-map.md 把盲测编号映射回 benchmark.md 的用例编号（SF-xx / SNF-xx），再按该用例的 `**预期**` / `**理由**` 判分；输出表格用映射后的用例编号。

必要时再读取：
- ./SKILL.md
- ./references/scene-packs.md
- ./references/protected-spans.md
- ./references/operation-manual.md
- ./references/boundary-cases.md

输入会提供：
- 盲测区间（例如 B-01 到 B-16）
- 被测模型输出
- 若包含 Long-form / in-place 用例，运行者会提供 `automation/eval/hard_metrics.py` 的硬判结果（字数留存率、破折号密度、protected spans 粗核报警），以报告数字为准

硬指标口径（由脚本产出，judge 不再自己数）：
- 字数留存率：只对 `public-writing / long / in-place` 用例判定；目标 ≥ 0.90、硬下限 0.85，低于硬下限按 run-eval.md 记硬约束 ❌。bounded 长文与 no-op（保留原文）用例不适用留存率判据；no-op 会校验「判定链力度=no-op 证据」或「正文≈原文」，标 `noop_unverified` 的按实际留存率判，不能当 no-op 放行。
- 破折号密度：单段 ≥ 4 处 `——` 或输出首句仍以 `——` 起手，命中 SF-43 破折号过密信号，需按该用例预期复核是否算标点腔未处理。
- protected spans 粗核：数字、版本号、路径、反引号片段等逐字存在性检查，只报警不判死——缺失项仍需你按 benchmark.md 的预期复核是否真漂移（例如 bounded 删除清单内的无源论断按规则删掉不算漂移）。

判分标准：
- 直接引用 ./evals/run-eval.md 的口径，不另造标准。
- 每条输出两列：硬约束列 + 风格 / SNF 误杀列，列定义见 ./evals/run-eval.md「判分分层」。SNF 普通误杀只在第二列记 ❌，硬约束列仍记 ✅；只有误杀同时涉及编造或受保护片段破坏时，两列都记 ❌。L3 观察用例（SF-15 / SF-40 / SF-42）第二列按可接受集判：no-op 带放行理由或按预期方向改写均记 ✅。
- SF：主要问题被消除、原意和 protected spans 保留、不过度改写，记 ✅。
- SF：识别到问题但动作不完整、只标注风险但该直接改写、bounded 直接删或软化整句空话等，记 ⚠️。
- SF：主要问题没处理、编造事实、误改 protected spans、错改场景、长文误删并句重排，记 ❌。
- SNF：保持原样或只做最小无害调整，记 ✅。
- SNF：错误修改术语、系统主语、技术报告、引用原文、被讨论词、合理转场、实句或 protected spans，记 ❌。
- Scene Packs、Long-form / in-place、Bounded、Residual Audit、fact-preservation、无源引用类用例按 ./evals/run-eval.md 的对应小节判。
- 长文留存百分比只使用运行者提供的硬判数字；你不要自己数，也不要估算。

输出格式必须严格如下：

| 编号 | 硬约束 ✅/❌ | 风格 / SNF 误杀 ✅/⚠️/❌ | 一句依据 |
|------|-------------|---------------------------|----------|
| SF-01（B-xx） | ✅ | ✅ | <一句依据> |
| SNF-01（B-xx） | ✅ | ✅/❌ | <一句依据> |

末尾再输出：

## 汇总

- 硬约束失败清单：<编号列表；没有就写“无”>
- SF 风格通过：X/Y（另报剔除 L3 观察用例后的 L2 口径 X/Y）
- SNF 误杀：X/Y
- L3 观察（SF-15 / SF-40 / SF-42）：<各一句结果；不计门槛>
- ⚠️ 清单：<编号列表；没有就写“无”>
- ❌ 清单：<编号列表；没有就写“无”>

禁止：
- 不要重写被测输出。
- 不要输出评分标准以外的新等级。
- 不要用“文风还可以 / 不够自然”这类主观理由替代 ./evals/run-eval.md 的标准。
- 不要跳过用例；如果被测输出缺某条，按 ❌ 并说明缺输出。
```
