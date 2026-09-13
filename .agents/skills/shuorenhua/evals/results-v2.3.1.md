# v2.3.1 全量基线结果

> 归档日期：2026-08-21（r4 主基线 2026-08-20，r5 换席补跑 2026-08-21）。规则快照：`0e3796a`（SKILL.md `b24a76ef`、rewrite-prompt `f956b92f`）。完整运行证据在 `tasks/current/eval-runs/2026-08-20-v2.3.1-full-r4/` 与 `tasks/current/eval-runs/2026-08-21-v2.3.1-full-r5-grok/`（gitignored 工作区）。
> 状态：**release-ready（Opus 单席位口径，维护者 2026-08-21 决定）**。r4 Opus 侧达门槛（硬约束失败 0、SNF 误杀 0/50、SF 57/61）；DeepSeek 撤出正式席位（B-74 真实 L1 + run-to-run 方差）；Grok 4.6 换席补跑完成改写与硬判、判分因评测通道不稳定仅闭环 1/7 批，按维护者收敛决定不重试，记为辅助证据。
>
> 复核修正（一）：原判分表中 B-57 的硬约束 ❌ 与 SNF 误杀 ❌ 不成立，已降为 L0 回显不完整。依据见 `tasks/current/eval-runs/2026-08-20-v2.3.1-full-r4/judges/opus-judge-deepseek/REVIEW-B57-correction.md`（脚本对 B-57/B-58/B-62 分类同为 `noop=true, noop_unverified=false`，同一判官豁免两条、判死一条；且 B-57 判定链显式满足 judge-prompt 的 no-op 校验分支）。下表保留判官原始计分，修正值单列。
>
> 复核修正（二）：B-15（SNF-34）所依据的 `references/structures.md` §20 存在计数单位自相矛盾（命中信号按破折号符号数、保留条件按插入语组数），两个独立模型各自按不同子句判定得出相反结论。该缺陷已在本版修复；B-15 从「DeepSeek 单方规则应用缺陷」改判为「规则缺陷导致的判定分歧」。撤席决策不受影响（依据是 B-74 与 run-to-run 方差，均独立于 B-15）。详见 `tasks/current/FINDING-structures-20-counting-unit.md`。

## 1. 本版范围

- 增加 mini / lite / full 三档入口；mini 是 1,500 字符以内的自包含版本。
- 增加 API reference、FAQ 等 Scene Packs，并补相应正反用例。
- benchmark 从 103 条扩到 111 条：61 SF + 50 SNF；blind、map 与 7 批范围同步。
- 增加 HUMAN 长文 residual 对照和严格 manifest 校验；这组数据不进入 rewrite、judge 或 benchmark 分母。
- 加固 plugin / marketplace 元数据结构与版本一致性检查。
- 保真规则强化（`0e3796a`）：事实/关系账本按子句/事实要素判断（不整句整行一刀切），输出前双向核对（输入→输出逐项可追溯，输出→输入回指依据）。
- 修复 `references/structures.md` §20 计数单位缺陷（见顶部复核修正二）。

## 2. 冻结输入与席位决定

| 输入 | SHA256 |
|------|--------|
| `SKILL.md` | `b24a76ef95bae3e1bd7cdb3a2b5b9be4c7fd5b1bf1eb9ecf1cded8e87bde5dac` |
| `references/scene-packs.md` | `dcda3b11b03193b0de2537f452bed9c3e330b99c533b995db59da302f4fbfe74` |
| `evals/benchmark-blind.md` | `79dedd4247e0df8a292a883a282e1d80214e0f6cc829a5855348b6a7e063acdd` |
| `automation/eval/rewrite-prompt.md` | `f956b92f4d2fbf90a20ea623264824d46f7b71ecfd10e288f280f6a217f03f9d` |

席位（维护者 2026-08-20 / 08-21 决定）：

- **Claude Opus 5：正式席位，达门槛**。Cindy Orca worker 通道（本机 claude CLI 未登录，维护者 2026-08-20 批准）；Host 完成消息路由回执 `claude-opus-5[1m]`，仅此一个模型。
- **DeepSeek V4 Pro：撤出正式席位，r4 成绩原样保留为辅助证据**。依据：B-74 真实 L1（与规则缺陷无关）+ 同条件复跑存在真实 run-to-run 方差（见 §9）。
- **Grok 4.6：第二席位补跑（r5），证据部分**。改写与硬判完整，判分仅 1/7 批闭环（见 §5）。
- Codex 5.6 Sol 因额度耗尽记“未参与”，没有用其他 Codex 模型替代。

## 3. targeted 结果

Opus mini 6/6 通过；Scene Pack 7 通过、1 个 L2 警告、0 L1，新增 SNF 误杀 0/4。DeepSeek Scene Pack 同为 7 通过、1 个 L2 警告、0 L1。

共同警告是 B-26 / SF-61：两模型都删除了无源的绝对安全保证，保留升级顺序、硬限制和 `2 小时` 待确认，但正文没有先直接回答“现有材料无法证明一定不会丢数据”。这是 FAQ 信息顺序的 L2 执行弱点，不是事实漂移。r4 全量中 Opus 已改为 audit-only 风险说明（L2 消除），DeepSeek 仍保留该 L2 警告。

## 4. 正式全量基线（r4，新规则）

两模型各 7 批、111/111 完成；双向 judge 14/14 批全部闭环。长文硬下限失败 0。

### Opus judge → DeepSeek（判 DeepSeek 输出）

| 批次 | SF 通过 | ⚠️ | ❌ 风格 | 硬约束 ❌ | SNF 误杀 |
|---|---|---:|---:|---:|---:|
| B-01–16 | 6/7 | B-16 | — | — | 1/9（B-15） |
| B-17–32 | 8/11 | B-19、B-25、B-26 | — | — | 0/5 |
| B-33–48 | 8/13 | B-35、B-38、B-39、B-47 | B-33 | — | 0/3 |
| B-49–64 | 4/5 | B-56 | — | B-57 | 1/11（B-57） |
| B-65–80 | 8/10 | B-70、B-75 | — | B-74 | 0/6 |
| B-81–96 | 7/7 | — | — | — | 0/9 |
| B-97–111 | 7/8 | B-106 | — | — | 0/7 |
| **合计** | **48/61** | **12** | **1** | **2** | **2/50** |

### DeepSeek judge → Opus（判 Opus 输出）

| 批次 | SF 通过 | ⚠️ | ❌ 风格 | 硬约束 ❌ | SNF 误杀 |
|---|---|---:|---:|---:|---:|
| B-01–16 | 7/7 | — | — | — | 0/9 |
| B-17–32 | 10/11 | B-19 | — | — | 0/5 |
| B-33–48 | 12/13 | B-38 | — | — | 0/3 |
| B-49–64 | 4/5 | B-56 | — | — | 0/11 |
| B-65–80 | 9/10 | B-66 | — | — | 0/6 |
| B-81–96 | 7/7 | — | — | — | 0/9 |
| B-97–111 | 8/8 | — | — | — | 0/7 |
| **合计** | **57/61** | **4** | **0** | **0** | **0/50** |

## 5. r5 换席补跑（Grok 4.6，辅助证据）

DeepSeek 撤席后，第二席位改由 Grok 4.6（provider=xai，Host 回执 `xai/grok-4.6`，单模型无 fallback）补跑。冻结输入与 r4 完全相同；Opus 改写直接复用 r4，不重跑。运行合同见 `tasks/current/eval-runs/2026-08-21-v2.3.1-full-r5-grok/run-contract.md`。

**已完成且可信的部分**：

- 改写 7/7 批、111/111 条，无缺号；L0 干净（各批直接以 `## B-xx` 起手，未复现 held-out 中的前言问题）。
- `hard_metrics.py --run`：长文硬下限失败 0、目标下警告 0；保护片段报警仅 1 条（B-77 的 `40%`，系规则允许的整条删除所致）；对照 Opus r4 报警 0 条、DeepSeek r4 报警 17 条。
- 归档保真：经 auto-bridge 转达的批次做过中文弯引号被渲染成直角引号的校正，逐批与本地 DB 原文比对，记录在各批 `host/*.json`。

**未完成的部分（如实记录）**：

- Opus judge → Grok 的 7 批中仅 B-65–80 批闭环：硬约束失败 0、SNF 误杀 0/6、SF 风格通过 7/10（⚠️ 3：B-66 首句改写越界、B-69 下一步动作不完整、B-70 骨架处理不完整）。该批判分表在 `judges/opus-judge-grok/judge-B65-80.md`。
- 其余 6 批 judge 因评测通道不稳定（7 个 Opus worker 并发时 6 个异常终止，重派一轮再次终止）未产出；Grok judge → Opus 的 7 批未启动。维护者 2026-08-21 决定收敛，不再重试。
- 因此 Grok 不作为发布门槛席位，本批结果只作辅助证据引用；后续版本如需第二正式席位，须完整重跑双向 judge。

## 6. 发布判断

按维护者 2026-08-21 收敛决定，v2.3.1 以 **Opus 单席位口径**收口：

- **Opus 5：达门槛**。硬约束失败 0；SNF 误杀 0/50；SF 通过 57/61，余 4 条均为 L2 警告。
- **DeepSeek V4 Pro：撤席**（主线程复核后口径）：
  - B-74（SF-08）：改写把「一个目标」替换成「这个产品」，指代对象漂移。benchmark 预期逐字写明「不能把『一个目标』改成『一个产品』或其他对象」，判定成立，**真实 L1**。
  - B-15（SNF-34）：**改判为规则缺陷导致的判定分歧**（见顶部复核修正二）。规则修复后该动作定性为 SNF 误杀（预期逐字写明「机械替换算误杀」），判定结论不变，归因从模型缺陷改为规则文本缺陷。
  - B-33（SF-38）：只删后半句，主病灶词「掰扯清楚」原样保留，**真实 SF ❌**。
  - B-57（SNF-49）：**判定不成立，已撤销**，降为 L0 回显不完整（见顶部复核说明）。
  - 修正后合计：硬约束失败 **1**、SNF 误杀 **1/50**、SF ❌ **1**；另有同条件复跑 run-to-run 方差（见 §9）。
- **HUMAN 代表性门禁**：direct 场景仍缺 docs/status（`check_repo` 唯一 FAIL）。维护者决定如实记录、随版发布，继续日常收集，收齐后关闭门禁。
- **mini 6 条**：Opus 侧 r3 6/6 有效沿用；DeepSeek 侧 3/6 格式失败随撤席不再补跑。

### 旧 L1 的修复验证（r3 → r4）

旧规则 r3 全量的两条 L1 均已被新规则修复，r4 两模型通过：

- B-39（SF-27）：`fallback` 适用条件「高峰期流量」两模型均保留（旧：Opus 删除致 L1）。
- B-95（SF-07）：两模型均保留 "potential" 抽象层级，未写成平台基于 cloud-native architecture 构建（旧：DeepSeek 新增已实施关系致 L1）。

L1 泛化侧测（held-out H-01–14 两模型 14/14 + 历史失败题 X-01/X-02 2/2）与全量结果一致。

r4 的新失败全部落在 DeepSeek 执行侧，Opus 同用例全过，属模型执行漂移而非规则缺口（held-out 已覆盖对应病灶类型）。

### §20 规则修复的基线影响

修复方向是「按插入处计数」。Opus r4 对 B-15 的实际行为（放行、按组数判定）在修复前后同为正确，**r4 Opus 侧全量基线不受影响，无需重跑**。偏离行为只出现在非门槛席位（DeepSeek 已撤席、Grok 辅助证据），修复后其 B-15 替换动作归档口径改为 SNF 误杀，不影响发布判定。SNF-34 的 benchmark 预期与修复后规则一致，SF 侧标点腔用例（SF-43 等）在按组计数下仍命中，预期均不变。

## 7. HUMAN 长文对照与许可

本轮 HUMAN 为 8 篇分层公开文本：3 篇现代中文公开年度/报道回顾、2 篇现代英译中公开采访、3 篇历史中文原作。正文从固定 MediaWiki revision wikitext 机械抽取；manifest 保留原作者/贡献者、固定来源与日期、CC BY / CC BY-SA 4.0、逐篇许可证据、抽取说明、原始语言和 AI 依据。正文及其改编不适用根目录 MIT。

代表性边界：覆盖 7 个作者组、3 个功能场景、3 篇历史 + 5 篇现代、6 篇中文原作 + 2 篇英译中；`representation_role=direct` 仅 public-writing 2 篇，docs/status 的 direct 代表性不足（代表性门禁未过，维护者决定随版发布并继续收集）。它是分层 residual 切片，不代表现代中文职场写作，也不能单独支撑“人味”阈值。

总体分布：句长 CV `n=8 / min=0.43 / median=0.52 / p90=0.61 / max=0.61`；连词密度 `n=8 / min=0.00 / median=1.20 / p90=5.22 / max=8.94`。HUMAN、SF、SNF 在同场景没有稳定分离证据（各场景 HUMAN 仅 2–3 篇），保留 report-only，不设产品阈值。目标 12 篇，继续收集中。

## 8. 仓库门禁状态

- `python3 automation/check_repo.py`：blind 111 条检查通过；HUMAN direct 场景缺 `docs`、`status`，报为已知缺口（known-gap，不阻塞退出码；维护者 2026-08-21 决定随版发布，收齐 12 篇后关闭门禁）。
- `python3 automation/eval/hard_metrics.py --human-stats evals/human-corpus.jsonl`：OK。
- `python3 automation/eval/hard_metrics.py --calibrate`：61 SF / 50 SNF / 8 HUMAN，OK；没有新增阈值。
- 22 条单测、Python 编译、blind 同步、链接与 diff 门禁见最终工作区验证记录。

## 9. 漂移说明与已知限制

- 硬判 protected spans 粗核报警均经 judge 复核：no-op 声明式写法（写「保留原文」未逐字回显）所致，非内容漂移；B-62 的破折号过密信号源于多段合并回显的格式问题。
- mini 6 条（`dist/shuorenhua-mini.md` `83f917c4` 未变）：Opus 侧 r3 6/6 有效沿用；DeepSeek 侧 r3 有 3/6 格式合同失败（只写「保留原文」未逐字交付），随撤席不再补跑。
- 本机 claude CLI 未登录，Opus 席位经 Cindy worker 通道运行；Host 回执 `claude-opus-5[1m]` 为等价第一方路由证据，费用为参考价估算（合计约 ¥125）；DeepSeek 侧实际计费合计约 ¥80；Grok r5 改写 7 批为 Host 估算口径（value-estimate），不可与 DeepSeek 的 actual-cost 混同。
- r5 判分通道不稳定（Opus judge worker 并发异常终止）为 Cindy Orca 基础设施问题，与 skill 规则无关；记录在 r5 `run-state.md`，供后续版本评测时规避（小并发或单批串行）。

## 10. DeepSeek 撤席依据（受控诊断）

受控诊断（`tasks/current/eval-runs/2026-08-20-v2.3.1-ds-capability-probe/`，两次同条件独立复跑，不进正式分母）：

- B-15 / SNF-34：3/3 失败。**归因更正**：r4 那次的理由（「两处破折号承接插入」）不是自造，是 §20 命中信号的字面读法（见复核修正二）；该条改判为规则缺陷导致的判定分歧，已在本版修复规则。修复后 DeepSeek 的动作仍属误杀，但不再单独归为模型能力缺陷。
- B-33 / SF-38：2/3 失败，其中一次输出内部自相矛盾（同一份命中项里先判「删姿态层」再判「保留，是正常口语」）。
- B-74 / SF-08：1/3 失败，两次复跑均保住三要素。
- **同条件两次运行输出不同** ⇒ 该模型在本 benchmark 上存在真实 run-to-run 方差，单次全量结果不可复现。对要求 L1=0 的正式基线，这比任何单条失败更关键，也是撤席的主要依据（独立于 B-15）。

另注：r4 两模型推理预算差 3.7 倍（Opus 16.54M token vs DeepSeek 4.47M）；诊断显示负载可能是影响因素之一，但不能解释同负载下的方差。Opus 同用例全过。

## 11. 结论

v2.3.1 **release-ready（Opus 单席位口径）**，版本号 2.3.1：

1. 新规则修复旧两条 L1（B-39、B-95 两模型均通过），并修复 §20 计数单位缺陷；规则修复方向经 held-out 与全量双重验证。
2. 发布门槛席位为 Claude Opus 5：硬约束失败 0、SNF 误杀 0/50、SF 57/61（余 4 条 L2 警告）。Grok r5 改写与硬判干净、1/7 批判分零失败，作为辅助证据记录；第二正式席位的完整补跑留给后续版本。
3. HUMAN direct 代表性缺口（docs/status）如实记录随版发布，继续收集。
4. 双模型门槛的完整重走不再作为本版阻塞项（维护者 2026-08-21 收敛决定）。
