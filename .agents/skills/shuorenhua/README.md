<h1 align="center">说人话：中文 AI 味清理 skill</h1>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="说人话：中文 AI 味清理 skill — 先保信息，再谈风格" width="100%">
  </picture>
</p>

<p align="center">
  <strong>别让模型替你装腔。</strong>
</p>

<p align="center">
  给 Codex、Claude Code、Cursor、ChatGPT 和自建 agent 用。
  <br>
  改聊天、技术同步、README、论坛帖和中文长文。压掉那股“一眼 AI”的腔调，事实、版本和责任一个都不动。
</p>

<p align="center">
  <a href="https://github.com/MrGeDiao/shuorenhua/stargazers"><img src="https://img.shields.io/github/stars/MrGeDiao/shuorenhua?style=for-the-badge&amp;label=stars" alt="GitHub stars"></a>
  <a href="https://github.com/MrGeDiao/shuorenhua/releases"><img src="https://img.shields.io/github/v/release/MrGeDiao/shuorenhua?style=for-the-badge&amp;label=release" alt="GitHub release"></a>
  <a href="evals/benchmark.md"><img src="https://img.shields.io/badge/benchmark-103%20cases-2563eb?style=for-the-badge" alt="Benchmark: 103 cases"></a>
  <a href="evals/real-samples.md"><img src="https://img.shields.io/badge/scenario%20samples-20-16a34a?style=for-the-badge" alt="Scenario samples: 20"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/MrGeDiao/shuorenhua?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <a href="#改成什么样">改成什么样</a> ·
  <a href="#30-秒上手">30 秒上手</a> ·
  <a href="#为什么改完敢直接发">保真合同</a> ·
  <a href="#它怎么判断怎么改">怎么改</a> ·
  <a href="#评测">评测</a> ·
  <a href="#安装">安装</a> ·
  <a href="#常见问题">FAQ</a>
</p>

`说人话` 专治那种“每个字都对，但一看就不是你写的”中文。它清理过度承接、工程师腔、小红书 AI 腔、翻译腔和无源权威铺垫，同时锁住版本、命令、责任和证据。它不替你编新事实，也不把空话包装得更漂亮。改完你敢直接发。

它适合这些场景：

| 场景 | 它会做什么 |
|------|------------|
| 日常聊天 | 删掉过度承接、推销式结尾和工程汇报腔，保留口语感 |
| 技术状态同步 | 保住事实、版本、命令、报错和责任归属，压低套话 |
| README / release note | 第一屏说清这是什么、给谁用；变更、验证和限制列全 |
| 论坛帖 / issue 回复 | 像维护者在认真沟通，不像客服公告或营销稿 |
| 中文长文 | 句内清理保住节奏，整句空话列「建议删除」清单交你确认，不让长文越改越短 |

## 改成什么样

### 聊天答疑，先颁奖再推销

**改写前**

> 你说的很对，这个问题一针见血。一句话总结：核心逻辑是先把流程跑通，再谈优化。我可以直接给你一版绝对没问题的最终方案，已经测试通过了，稳得很。要不要我顺手把文档也整理了？你一句话的事。

**改写后**

> 对，问题就在这：先把流程跑通，再谈优化。方案我发你。文档要不要一起弄？

开头发奖状、结尾追着卖，中间「一句话总结」「核心逻辑」轮着上——这条姿态链社区早就逐个点过名（[Linux.do 句式征集帖](https://linux.do/t/topic/1898176)、[「对象说我说话一股子AI味」](https://linux.do/t/topic/1765637)）。文本为合成示例，把被点名最多的口癖压进了一段。

### 发版感言，不见变更

**改写前**

> ## v1.8.0 Release Highlights
>
> 本次版本是一次面向真实场景的系统性升级。我们不仅全面优化了改写体验，更通过全新的能力矩阵稳稳兜住了用户在 README、release note、论坛长帖和 issue 回复里的核心表达诉求。感谢所有用户的持续支持，让我们共同见证中文 AI 写作体验的全新跃迁。

**改写后**

> ## v1.8.0
>
> - 新增 `references/scene-packs.md`，覆盖 README、release note、forum post 和 issue reply
> - `evals/benchmark.md` 增加 8 条 scene pack 回归用例
> - `evals/real-samples.md` 增加 4 条整段样本，继续按自然 / 保真 / 可直接发评分
>
> 这版不做 Voice Calibration；相关方向推迟到 v1.9 评估。

release note 的读者要的是变更清单，不是发布宣言。上面这条改写保住了版本号，拆掉了发布宣言那层，还把「这版不做 Voice Calibration」这种没做的事也写了出来。完整样本见 [evals/real-samples.md](evals/real-samples.md) RS-16。

### 删掉渲染词，数字不能跟着丢

**改写前**

> 本次优化在性能方面取得了显著成效，有效改善了接口响应问题，p95 延迟从 480ms 降到 160ms，充分体现了团队持续优化的能力。

**改坏示范**

> 这次优化明显降低了接口延迟。

渲染词是没了，但 p95、480ms、160ms 也跟着没了——空话只是换成了更泛的空话。

**改写后**

> 这次优化把接口 p95 延迟从 480ms 降到 160ms。

清完落在哪是有合同的：原文给了具体信息，改写后就得把它落回去，不能拿更泛的说法顶替。这条对应评测集里的硬约束用例（[evals/benchmark.md](evals/benchmark.md) SF-46）。更多例子见 [references/examples.md](references/examples.md) 和 [evals/real-samples.md](evals/real-samples.md)。

## 30 秒上手

**先试效果，什么都不用装** — [说人话 GPT](https://chatgpt.com/g/g-6a5829b1163481919e1e45851f6bc709-shuo-ren-hua)（ChatGPT，需 Plus / Pro），完整规则已内置，贴文本就能改。

**Claude Code** — 对话里两条命令装完，之后自动触发：

```text
/plugin marketplace add MrGeDiao/shuorenhua
/plugin install shuorenhua@shuorenhua
```

装好后在对话里说「把这段去 AI 味」就会命中。手动安装（cp / 软链跟随更新）见 [install/claude-code.md](install/claude-code.md)。

**Codex** — clone 后单次使用：

```bash
git clone https://github.com/MrGeDiao/shuorenhua.git && cd shuorenhua
codex exec -C . "读取 ./SKILL.md，按其中规则改写以下文本：……"
```

**其他 agent / skill CLI** — 支持 `skills` 命令时可以直接安装完整包：

```bash
npx skills add MrGeDiao/shuorenhua
```

更多安装选项见 `npx skills add --help`。

项目内长期使用建议把 skill 文件拷进项目并在 `AGENTS.md` 写明触发条件，见 [install/codex.md](install/codex.md)。

**只想先看问题、不要改稿**：指令里加一句「按 annotation mode 只标注不改写」。它逐条标问题族；一段文本要是本身没什么可写、只是被套话撑长了，会标成 `材料不足`，直说删完还剩什么，不拿换说法把篇幅填回去。

Cursor、OpenClaw 和自建 agent 见[安装](#安装)。

## 为什么改完敢直接发

去 AI 味工具最常见的翻车不是没清干净，是清完事实变了：数字漂了、关系换了、原文没有的补出来了。`说人话` 把这些“不许变”写成可以逐条判分的合同：

- **数字和修饰对象一起保**：`p95 从 480ms 降到 160ms` 删掉渲染词后必须原样在，不许概括成“明显降低”。
- **关系不许改写**：`展示了云原生架构的潜力` 不能改成 `采用了云原生架构`（潜力不是实现）；`两个团队` 不能扩成“换过两个团队”（先后关系是原文没有的）。
- **时间跨度不漂移**：`未来十年` 不能缩成“未来几年”，也不能糊成“未来”。
- **抽象不许擅自具体化**：原文只说“提升效率”，不能改成“省时间”“降成本”。
- **缺信息不许编**：原文没给数据，允许输出更短更直白，但不补数字、工具名或来源；`status / docs` 缺依据时标注“原文缺具体依据”，不硬填。

每条合同在评测集里都有对应的硬约束用例（SF-07、SF-08、SF-46、SNF-36 等），双模型盲测逐条判分。规则细节见 [references/positive-style.md](references/positive-style.md) 的「清理后的落点」和 [references/protected-spans.md](references/protected-spans.md)。

## 它怎么判断怎么改

`说人话` 不是见词就替换。

> **先保信息，再谈风格。**

完整流程固定六步：

1. 判场景：`chat / status / docs / public-writing`；命中 README、release note、论坛帖、issue 回复时，再进对应的 Scene Pack
2. 划保护片段：数字、版本、命令、路径、报错、引用原文、人名和责任归属先锁住，同时记一份事实关系账本——谁对什么做了什么、数字修饰哪个对象（完整清单见 [references/protected-spans.md](references/protected-spans.md)）
3. 判命中强度（`Tier 1 / 2 / 3`），再分别定改写力度（`minimal / standard / aggressive`）和 scope（`structural / bounded / in-place`）；Tier 只描述问题命中多重，不直接等于力度
4. 先按模式改，词表只兜底
5. 保真回读：事实、术语、语域、保护片段逐项过
6. 仍有残味才做第二遍 Residual Audit，只允许轻量修正

### 模式地图

| 识别信号 | 默认动作 | 例 |
|------|------|------|
| 开场套话、总结提示（“好问题”“结论先说”） | 删提示层，直接进入事实或回答 | `好问题！让我来解释` → 直接回答 |
| 商业黑话、价值拔高（“赋能”“闭环”“系统性升级”） | 换成普通动作；没有具体信息就删空壳 | `赋能开发者` → `帮开发者` |
| 工程师姿态腔（“收口”“兜住”“落盘”） | 按宾语判断；姿态层换成确认、核对、写入等动作 | `把结论落盘` → `把结论写进文档` |
| 过度接住、心理判断、身份认证 | 去掉抚慰和发证书，只保留低承诺回应 | `你不是敏感，你只是……` → 具体回应 |
| 翻译腔、句式过满 | 缩短主语和动作，保留术语和责任主体 | `基于……通过……来……` → 直接说动作 |
| 名词化、同义词躲避 | 还原成直接动词；同一对象统一回最具体的说法，不轮换近义词 | `进行了优化` → `改了`；`木工 → 这门手艺 → 这项技能` → 统一写 `木工` |
| 装饰性细节、多套借喻混用 | 细节要同时满足“无来源 + 删后文不变”才删；借喻先还原本义 | 凉咖啡、窗外小雨只负责造现场 → 删；`赛道 + 护城河 + 浪潮` → 说清实际变化 |
| 标点腔（破折号密集或首句起手） | 按密度和位置改回逗号、冒号或断句；单次合理用法放行 | 连续 `——` → 分句 |
| 无源权威（“研究表明”“业内人士认为”） | `chat / public-writing` 删除无法独立成立的整条论断；`docs / status` 标注缺来源 | 不把裸 `40%` 留成事实，也不降格成“会更快” |

详细边界见 [references/](references/)、[场景规则](references/scene-packs.md) 和 [评测集](evals/benchmark.md)。

英文去 AI 味已经有 [stop-slop](https://github.com/hardikpandya/stop-slop) 和 [humanizer](https://github.com/blader/humanizer)。`说人话` 补的是中文这一层：这些腔调在中文里长什么样、按发布场景分档处理、改写前先锁住事实。

### 场景与力度

四个场景的默认力度：

| 大场景 | 默认强度 | 处理策略 |
|--------|----------|----------|
| `chat` | 轻 | 只砍明显套话，不把聊天改成公文 |
| `status` | 中 | 保留动作、状态、阻塞点和下一步 |
| `docs` | 中 | 技术表达优先，二次回读更保守 |
| `public-writing` | 重 | 全规则扫描，并按需要触发 Scene Packs |

### 按发布目的细分（Scene Packs）

可发布文本再按「发到哪里」细分。这不是换语气，是按发布目的决定改法：README 第一屏要说清这是什么、给谁用；release note 要列清变更、验证和限制；论坛帖像维护者分享观察和取舍，不像公司公告；issue 回复先确认问题和下一步。每个子场景的目标和常见病灶见 [references/scene-packs.md](references/scene-packs.md)。

### 长文不缩水：三档 scope

长文按默认动作改写，删句、并句会叠加，1800 字可能被压到 1000 字；反过来一句不删，整句的空话又留在文里。所以长文把「删到什么程度」单独分成三档，和力度档位正交：

| scope | 删整句吗 | 适用 |
|-------|----------|------|
| `structural` | 自由删并重排 | 短文、明确要重写 |
| `bounded`（长文默认） | 整句空话列成「建议删除（待确认）」清单，删多少你拍板 | `public-writing` 长文 |
| `in-place` | 一句都不删，只句内降调 | 明确要求「完全原样」 |

三档的取舍过程见 [#4](https://github.com/MrGeDiao/shuorenhua/issues/4)，`structural` 缩水不可控的双模型对照实跑见 [evals/results-v1.8.6.md](evals/results-v1.8.6.md)。后续各版的 scope 回归结果登记在 [evals/run-manifest.md](evals/run-manifest.md)。最近一轮是合并版 v2.3.0 的新增 8 条 + 第一阶段 11 条影响面回归（[evals/results-v2.3.0.md](evals/results-v2.3.0.md) §9）：Codex `gpt-5.6-sol` 与 Claude `opus` 独立盲改写、双向交叉判分，硬约束失败 0、SNF 误杀 0，无 `❌`。SF-55 在两模型上都留有较淡的抽象隐喻，按 L2 风格警告记录，不阻塞发布。

### 改完往哪个方向靠

清理不只是删词，它也会把文本往这些方向拉：

- 具体动作优先于抽象拔高
- 真主语和真动作优先于姿态层
- 允许轻微不对称，不把每句都抛光成同一种腔
- 按场景校准，聊天和文档不套同一种腔

## 评测

规则层覆盖 210+ 中文短语、96 条英文短语、25 类结构反模式。

当前评测集共 103 条：

| 类型 | 数量 | 目标 |
|------|------|------|
| SF | 57 | 应该改的文本必须命中并改掉主要问题 |
| SNF | 46 | 不该误杀的文本必须放行或轻提示 |
| 场景样本 | 20 | 整段样本按自然、保真、可直接发三项评分，长文加 `长度节奏` |
| Scene Packs | 8 | README / release note / forum post / issue reply 的正反样本 |
| Long-form In-place | 4 | 长文保长度场景，检查字数留存、句数对齐和关键转场 |
| Bounded | 3 | 长文整句空话进删除清单，但不误删实句和节奏句 |

怎么算及格：v2.1.0 起发布门槛分三层（判据单源：[evals/benchmark-tiers.md](evals/benchmark-tiers.md)）：

| 层 | 管什么 | 进不进门槛 |
|----|--------|------------|
| L1 硬约束 | 编造事实、受保护片段漂移、责任归属改变、scope 越界 | 进：失败 0 才允许发布 |
| SNF 误杀 | 不该改的文本被改了 | 进：误杀率 < 10% |
| L2 风格目标 | 明显套路清没清干净 | 按模型分别报告趋势，不设统一线 |
| L3 风格观察 | 两位合格编辑可能合理分歧的用例 | 不进，只记录 |

v2.1.0 实跑（82 条全量盲测、双模型交叉判分，完整归档见 [evals/results-v2.1.0.md](evals/results-v2.1.0.md)）：

| 被测输出 | L1 硬失败 | SNF 误杀 | 门槛 |
|----------|-----------|----------|------|
| Codex 最终全量 | 0 | 2/36 | 通过 |
| Claude 最终全量首轮 | 1（SF-07） | 3/36 | 未通过 |
| Claude 完整确认轮 | 0 | 1/36 | 通过 |

Claude 首轮那 1 个 L1 不是规则缺口：判定链已经写明“不得补实现关系”，输出还是补了，属分析—输出自相矛盾。按事先声明不改规则、只做一次完整确认复跑；失败轮与确认轮并列归档，不宣称所有运行全绿。旧口径 SF 通过率继续并列报告（Codex 87.0%、Claude 84.8%），保持历史可比，不再作为发布依据。

评测怎么跑：被测模型只看匿名乱序、不含预期的 [evals/benchmark-blind.md](evals/benchmark-blind.md)，judge 按映射表判分；每次实跑的评测集版本、模型和口径登记在 [evals/run-manifest.md](evals/run-manifest.md)。完整用例集见 [evals/benchmark.md](evals/benchmark.md)，整段场景样本（高拟真合成）见 [evals/real-samples.md](evals/real-samples.md)。

v2.2.0 起，改写输出落盘后先用零依赖硬判脚本 `python3 automation/eval/hard_metrics.py --run <批次目录>/` 批量算出字数留存率、破折号密度和 protected spans 粗核（自动配对 `evals/benchmark-blind.md` 原文），judge 不再自己数长文留存，缺失报警仍由 judge 复核；使用口径见 [automation/eval/README.md](automation/eval/README.md)。

## 安装

| 平台 | 文档 |
|------|------|
| Codex | [install/codex.md](install/codex.md) |
| Claude Code | [install/claude-code.md](install/claude-code.md) |
| Cursor / Windsurf | [install/cursor.md](install/cursor.md) |
| OpenClaw | [install/openclaw.md](install/openclaw.md) |
| ChatGPT / Custom GPT | [install/chatgpt.md](install/chatgpt.md) |

核心只需要 `SKILL.md` 一个文件（lite）；长期项目、公开文本和需要误杀防护的场景，建议带上 `references/` 完整包（full）。

项目内长期使用时，可以在 `AGENTS.md` 加一段触发规则：

```markdown
## 写作风格
当任务涉及“去 AI 味”“说人话”“自然一点”“别像模板”这类改写时，遵循 `shuorenhua/SKILL.md`。
对外文本优先按它处理；代码、日志、配置和命令输出不套这个 skill。
```

## English

**shuorenhua (说人话)** is a Chinese-first AI writing humanizer for Codex, Claude Code, Cursor, and ChatGPT. It removes AI-flavored patterns in Chinese text — sycophantic openers, performative engineer-speak, translationese, unsourced authority claims — under a fidelity contract: numbers stay attached to what they measure, relations and attribution never drift, and missing facts are never invented. It ships with a 103-case benchmark (blind inputs, dual-model judging, false-positive guards) and a long-form mode that cleans text without shrinking it.

Claude Code: `/plugin marketplace add MrGeDiao/shuorenhua`, then `/plugin install shuorenhua@shuorenhua`. Other agents: `npx skills add MrGeDiao/shuorenhua`. More guides: [install/](install/). Everything else in this repo is written in Chinese.

<sub>关键词 / keywords：中文 AI 写作、中文 humanizer、去 AI 味、AI writing humanizer、Chinese writing style</sub>

## 常见问题

### 这是不是拿来骗 AI 检测器的？

不是。目标是减少模板感、表演感和语域漂移，让文本更自然、更可发布，不是绕过检测。

### 英文能不能用？

可以，但这是一个中文优先项目。英文支持主要用于清理常见英文套话和中英混写里的模板感。

### 为什么改完有时还是有 AI 味？

“去掉明显套路”不等于“拥有具体作者的个人表达”。当前版本更擅长清理模板感和表演感，还不负责拟合某个具体人的长期写作习惯。

### 会不会把技术文档改坏？

正常不会按聊天口吻去改技术文档。`docs`、`status`、`code-context` 都有更保守的保护策略，命令、路径、版本、报错和指标优先保真。

## 贡献：bad case 比 star 有用

欢迎提交新的评测样本、边界案例、真实问题案例、改写前后样本和误杀防护。

如果你遇到“改完还是像 AI”的具体文本，可以用 [bad case 模板](.github/ISSUE_TEMPLATE/bad-case.md) 提交。请先脱敏，不要贴未授权私聊全文、密钥、内部链接或真实个人身份信息。也可以直接贴到[征集 issue](https://github.com/MrGeDiao/shuorenhua/issues/5)。

在提交新词之前，先想一件事：

> 这是一个“新模式”，还是只是“现有模式的变体”？

详细规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 相关项目

- [stop-slop](https://github.com/hardikpandya/stop-slop)：英文 AI slop 规则和评分框架
- [humanizer](https://github.com/blader/humanizer)：英文 AI 模式分类
- [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)：AI 写作问题分类和严重度参考
- [speak-human-tw](https://github.com/Raymondhou0917/speak-human-tw)：繁体中文去 AI 味，覆盖电子报、社群贴文、销售页和客服信

## Star 增长

[![「说人话」star 增长曲线](https://raw.githubusercontent.com/MrGeDiao/shuorenhua/star-data/star-growth.svg)](https://github.com/MrGeDiao/shuorenhua/stargazers)

## 许可

[MIT](LICENSE)
