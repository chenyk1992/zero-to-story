# GPT-6 适配变更说明

2026-09-07：记录本次项目 AI 配置审查的官方依据、实际生效范围、逐项冲突和旧技能状态。此文件是审计记录，不是新增的执行流程或审批要求；日常工作读取根 AGENTS.md 和所需 Skill 即可。

# 项目 AI 配置审查

## 依据与范围

已检索并打开 OpenAI [GPT-6 Astra 官方指南](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra)、[AGENTS.md 加载规则](https://learn.chatgpt.com/docs/agent-configuration/agents-md)和 [Skills 文档](https://learn.chatgpt.com/docs/build-skills)。本次采用的是其中的自主推进、消除指令冲突、明确委派和适度验证原则；下述 LFO hash、串行与素材规则来自本项目契约，并非 OpenAI 对所有项目的通用要求。

第一轮审查覆盖当时会话列出的 **29 个已启用 Skill：10 个项目 Skill、19 个外部 Skill**。逐个读取 SKILL.md；对项目中承载实际流程的引用和提示词进一步定向检查。没有把推荐但未安装插件、历史评测数据或未出现在清单的目录假定为已启用技能，也没有启动被审计技能的媒体生成任务。

后续复审的最新会话清单为 **25 个：10 个项目 Skill、15 个外部 Skill**。Sites 的两个 Skill、Deep research 和 Plugin management 已不在该清单中；下面保留它们的历史审查记录，不表示当前仍已启用，也不推断已卸载。

## 配置生效位置

| 对象 | 原状 | 本次处理 |
| --- | --- | --- |
| 根 [AGENTS.md](../AGENTS.md) | 协作权限不明确，执行/数据/测试规则重复 | 重构为优先级、LFO 契约、数据边界、验证和 Skill 分工；增加外部 Skill 的项目适用边界 |
| [项目系统提示词](ai-system-prompt.md) | 没有独立项目文件 | 新增，由根 AGENTS.md 明确要求读取；统一自主推进、复用授权、沟通、委派与停止条件 |
| `.agents/skills/*/SKILL.md` | 部分入口存在每阶段确认、固定开场访谈或强制扩展流程 | 修改 10 个入口及相关引用、默认提示词、元数据，共 23 个 Skill 文件；保留 YAML frontmatter 与专业工作契约 |
| Codex 内置系统/开发者提示词 | 由宿主提供，没有发现本项目可替换文件 | 没有修改；项目提示词不能替换平台消息或提升实际权限 |
| 全局 `~/.codex/config.toml` | 已选 `gpt-6-astra`；未发现 `developer_instructions` / `model_instructions_file`；全局 AGENTS.md 为空 | 只读核实，未修改模型、推理强度、审批或沙箱 |
| 系统 Skills、个人 mmx 与插件缓存 | 第一轮列出 19 个外部入口；最新清单为 15 个 | 完整只读审查，项目范围内用根规则协调默认流程；未改外部源文件、卸载或宣称已全局修复 |

项目系统提示词是新增的本地指令源，不依赖该文件名的自动发现。AGENTS.md 在新一轮配置加载时进入指令链；如当前任务仍显示旧 Skill 内容，重新开始一次会话即可核对加载。没有创建替换内置提示词的配置键，也没有清缓存。

## 项目 Skills 的处理

| Skill | 冲突或冗余 | 处理边界 |
| --- | --- | --- |
| [zero-to-story](../.agents/skills/zero-to-story/SKILL.md) | 逐阶段确认、包批准复用不明确；并行准备与串行生成容易混淆 | 复用创作授权与具体包批准，明确只暂停受阻步骤；保留现有导演/分镜改动与 LFO 契约 |
| [h3-prompt-writing](../.agents/skills/h3-prompt-writing/SKILL.md) | 对已明确单 Panel 输入的重复门槛 | 输入足够时直接返回提示词，保留模式、引用与时间契约；不承担生成调度 |
| [mimo-video-understanding](../.agents/skills/mimo-video-understanding/SKILL.md) | 分析辅助工具容易被扩成独立评分/生成流程 | 限定证据提取与停止条件，不触发 LFO 重生成；保留两阶段描述/判断分工 |
| [shuorenhua](../.agents/skills/shuorenhua/SKILL.md) | 单文件兜底与全量补读引用的强要求 | 按实际文本问题选择引用，保留事实和语域，不机械扩读或无界自检 |
| [mg-voiceover-animation-generator](../.agents/skills/mg-voiceover-animation-generator/SKILL.md) | 缺口播时强制提问、已有授权仍分阶段停顿 | 按输入与授权决定代写/审稿/生成范围；缺真实产品事实才问，包 hash 批准保留 |
| [transcript-broll-planner](../.agents/skills/transcript-broll-planner/SKILL.md) | 计划完成必停、生成前重复确认 | 用户只要规划就交规划；完整任务复用已有方案授权，具体执行包仍校验批准 |
| [virtual-presenter](../.agents/skills/virtual-presenter/SKILL.md) | 同一口播输入在计划/交接重复确认 | 复用角色、文案、声音与包授权；保留前段完整 ACCEPT 视频作为普通连续性参考 |
| [short-drama-screenwriter](../.agents/skills/short-drama-screenwriter/SKILL.md) | 固定开场问题、逐阶段确认和旧提问工具绑定 | 使用已有信息直接推进用户所需篇幅和阶段，缺关键创作事实才问；保留剧本/handoff 分工 |
| [video-deconstruct-analyzer](../.agents/skills/video-deconstruct-analyzer/SKILL.md) | 拆解与额外复刻路线的交付范围容易混淆 | 默认按用户请求拆解；已指定路线直接使用，不附加未请求的提示词分支 |
| [voice-clone](../.agents/skills/voice-clone/SKILL.md) | 连本地 ffprobe 也要求先逐字确认声明 | 允许本地检查准备，复用已明确的说话人授权；上传、克隆前缺真实授权仍询问 |

## 外部 Skills 逐项审查

下表是第一轮审查结论和当时的项目内适用方式，**不是对外部源文件已完成修改或当前仍已启用的声明**。外部文件位置和可用性以最新会话清单为准；版本化插件缓存不能作为项目源码改写。

| 已完整读取的入口 | 发现与项目处理 |
| --- | --- |
| `imagegen` | 保留图像工具、原始文件和引用要求；已有明确编辑/替换授权直接复用 |
| `openai-docs` | docs-first 与本地检查顺序可能冲突；允许独立本地读取，仍按宿主要求核验时效事实。其他模型路由只在对应任务使用，不因历史名称而删除 |
| `plugin-creator` | 目标 marketplace/覆盖和安装属于具体范围；授权完整则直接做，不为假想审批停下 |
| `skill-creator` | 本身已强调用户意图、渐进加载和按风险验证；保留自动发现，不擅自改成仅显式启用 |
| `skill-installer` | 用户要求安装即是该动作授权；保留真实环境权限，不把审计当安装请求 |
| `mmx-cli` | 示例 `video download --task-id` 与正文 `--file-id` 不一致；实际使用前以已安装 CLI 帮助核实。当前未发现可直接调用的 mmx 命令，未执行下载验证 |
| `mmx-h3-video` | 新付费提交需要授权，但用户已授权的那次重跑不再询问；保留未知状态不重提、下载失败不重生成 |
| `computer-use:computer-use` | `node_repl` / `sky` 与当前可用 `mcp__cua_repl` 入口不同；以实际工具文档为准，原生桌面未开放时不使用旧入口绕过 |
| `visualize:visualize` | “所有工作保持沉默”与宿主进度沟通冲突；采用宿主沟通规则，多方案只在当前目标需要时使用 |
| `sites:sites-building` | 与 hosting 是合理前后分工；用户明确 local-only 时不追加发布 |
| `sites:sites-hosting` | 共享/公开发布的已有具体授权可复用；实际受众变化或不明才询问 |
| `deep-research-work:deep-research` | 仅明确请求 Deep research 时使用；用户指定对话报告时不强加办公文件产物 |
| `plugin-management:plugin-management` | 保留明确目标、现有能力优先和不阻塞建议；本地配置审计不自动装插件 |
| `documents:documents` | 保留 DOCX 真实布局验证；只读提取不启动创作/渲染循环，验证按交付要求与影响执行 |
| `pdf:pdf` | 保留表单/flatten/渲染要求；普通输出路径不等同 LFO Run 路径，临时文件不写真实 workspace |
| `presentations:Presentations` | 已支持输入明确就执行；保留用户模板、事实与真实产物检查 |
| `template-creator:template-creator` | 仅模板创建/更新任务触发；指定唯一模板时直接处理，不改插件缓存或旁及全局技能 |
| `spreadsheets:Spreadsheets` | 保留公式、重算和按风险验证；不把通用输出目录套进 LFO 媒体执行 |
| `spreadsheets:excel-live-control` | 工作簿、登录和会话缺失属于真实阻塞；已指定对象复用，不静默切换到别的工作簿 |

## 旧技能清理结果

全局配置中以下 **12 项已经停用**，本次没有重复停用或删除：`hyperframes-core`、`hyperframes-cli`、`hyperframes-audio`、`hyperframes-animation`、`hyperframes`、`hyperframes-creative`、`music-to-video`、`pr-to-video`、`remotion-to-hyperframes`、`embedded-captions`、`hyperframes-keyframes`、`hyperframes-registry`。

用户级 `.agents/skills` 当前只存在 `mmx-cli` 目录（含 H3 子技能）。未出现在当前会话清单的其他目录不能仅凭物理存在认定为已启用。项目现有 10 个 Skills 职责各有用途，本次清理的是旧门槛、旧工具绑定和重复指令，没有以“旧”为理由删除仍在使用的专业能力。

MG 中的历史 Seedance 参考只用于明确的兼容请求；视频拆解 Skill 的 Seedance 分支仍是用户可选能力，二者不能仅因命名相似一并删除。历史评测结果与已有用户素材保持原状。

## 第一轮验证与当时的限制

已对根配置进行独立的 7 场景行为审阅：直接文案修改、同包同 hash 批准复用、变更包拒用旧 hash、只交审稿、LFO 串行限制、Skill 审计不执行被审材料、超时未知不重提。以上是静态行为复核，没有调用付费生成。

最终检查结果：

- 10 个 Skill 的首部 frontmatter 必填字段、命名与变更说明结构检查通过；23 个修改文件均有 GPT-6 适配说明。Markdown 说明放在正文前部，YAML 使用注释，保留机器可读结构。
- 已检查修改文件中的 84 个本地文件链接，以及根 AGENTS.md、项目系统提示词和本审计文档的文件链接，未发现缺失目标。旧 `AskUserQuestion` 工具绑定及改名的旧章节引用扫描无残留。
- `git diff --check -- AGENTS.md .agents/skills` 通过。23 个写入对象在应用前逐个核对基线 SHA-256、应用后核对新 hash；未列入修改范围的已有 Skill 文件与开始时的 hash 一致。
- 尝试运行 `python -m pytest tests/skills tests/skill_adapter tests/test_mimo_video_skill.py -q`，系统 Python 与应用附带 Python 均报 `No module named pytest`，因此这些测试未运行。Skill Creator 的完整 YAML 校验器也因缺少 `yaml` 未运行；本次使用了不依赖该模块的入口结构、字段、链接及人工检查，不声称完成完整 YAML 解析。
- 未运行全量测试、doctor/preflight 或 live E2E：本次没有更改运行时/ComfyUI 代码，也没有提交媒体生成。本次 7 场景审阅是静态行为复核，不是实际模型回归测试。

没有更改 LFO 运行时代码、数据库、CAS、真实媒体、全局权限或模型设置。已有未提交改动在修改前记录并在其上定点调整；仓库中原有的 MiMo 脚本、ComfyUI 后端和测试改动不是本次产生。没有提交或推送。

## 第二轮：按官方重点继续优化

本轮在第一轮已有修改之上建立快照，再完成真实文字任务评估、Skill 渐进加载、共享规则收敛和本地验证环境准备。官方五个重点对应的实际调整如下：

| 官方重点 | 本项目落地 |
| --- | --- |
| Initiative / follow-through | 保留已授权直接交付；分清只要单集/Brief/分析与完整生产；去掉未指定模型时额外问路线的默认门槛 |
| Instruction following | 通用协作以项目提示词为单一来源；技能入口与实际引用一起改，统一 bounded 删除、独立单集预算和提示词路线选择 |
| Personality / style | 简洁中文、单份可用产物；用户只要成稿时不强加删除清单、系列预告或任务外解释 |
| Subagent delegation | 独立评估与不同文件的改写并行，主 Agent 负责整合、保真和验收；实际 LFO 视频提交继续隔离串行 |
| Testing | 四个固定任务产出真实文本；格式/链接检查与行为观察分开；新校验器测真实错误检测，已有技能适配测试按范围运行 |

三个长入口的 UTF-8 文件大小由 `68,694` bytes 降至 `20,802` bytes，减少约 `69.7%`：短剧 `19,282 → 6,547`，说人话 `27,381 → 5,376`，zero-to-story `22,031 → 8,879`。这只是入口文件字节量，不是 token 用量、全技能总大小或响应速度；复杂任务仍会按需读取新增参考。

- 专业细节分别移入短剧 `workflow-contract.md`、说人话 `rewrite-contract.md`、zero-to-story `storyboard-production.md` 与 `panel-execution.md`。已有专业引用、模板和用户先前导演/分镜修改保留。
- 统一 shuo 的 README、`operation-manual.md` 和 `scene-guardrails.md`；无源数字/预测仍按原有 rewrite-safe/audit-only 规则处理，不借提自主性改掉事实保真边界。README 中 6 处指向本地缺失资料的链接已修正或注明未随副本提供。
- 外部 Skill 的项目例外移到 [按需规则](ai-skill-routing.md)，使用相关能力才读取。19 个外部 Skill 源文件和 12 项已停用旧技能的状态没有改动。
- 项目提示词区分可逆准备错误和实际生成失败；具体包批准复用、hash 改变停止、未知生成状态不重提、QC 与真实尾帧规则保留。
- 创建项目 `.venv`，安装已有开发依赖，新增 PyYAML 开发依赖以解析 Skill YAML；提供可复用的环境准备与配置校验入口。没有修改全局 Python、PATH、模型、审批设置或外部 ComfyUI。

静态格式检查不能证明模型行为改善，实际单次任务也不能替代生产生成验证。固定请求、原始结果和本轮最终检查见 [AI 配置验证](ai-config-evaluation.md)。历史评测、样本入库流程和用户资产不当作普通任务规则；没有删除或改写既有评测结果。

## 第三轮：入口、引用与元数据一致性

复审发现保句数约束被二次润色覆盖、短剧默认创建项目及压缩预算、MG 参考路由/尾帧、视频拆解路线元数据、数字人阶段边界等遗漏，已做定点修正。项目解释器入口和当前启用技能清单也同步核对。具体文件问题、处理及实际验证见 [第三轮复审记录](ai-config-rereview.md)。原有运行时契约和历史评测结论保持原状。
