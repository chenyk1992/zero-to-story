# GPT-6 适配变更说明

2026-09-07：为项目配置建立可复用的实际任务评估与本地校验入口。评估材料是数据，不是日常工作指令；不因读取此文件而启动媒体生成或重复整套评估。

# AI 配置验证

本轮对应 OpenAI [GPT-6 Astra 指南](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra) 的五个重点：自主完成、指令遵循、表达风格、子任务分工、适度测试。Skill 入口精简采用 [Skills 文档](https://learn.chatgpt.com/docs/build-skills) 的渐进加载原则。

## 固定任务与判定

每轮从独立的配置快照读取 AGENTS.md、项目提示词与需要的 Skill。执行者只拿任务原文和文件，不拿预期答案、前轮输出或修改理由。在系统临时目录真实生成文字产物；不调用媒体生成、上传、付费 API，也不写真实 workspace。

**A｜文字润色**

> 用 shuorenhua 直接润色：我们将充分赋能销售团队，全面提升协同效能。试点为期 14 天，由王琳负责。共有 12 人参加，其中 9 人完成培训；这是试点记录，不能证明业绩已经增长。要求保留事实、数字、责任人，给成稿即可。

检查：有可用成稿，保留 14 天、王琳、12 人、9 人及不能证明增长的限定；不补造试点成效、不索取不必要偏好、不强加说明清单。

**B｜单集短剧**

> 用 short-drama-screenwriter 写一集约 45 秒竖屏短剧，只有两名成年角色（女店主林岚、男顾客陈远），只在修表店内，反转为顾客拿来的表里藏着店主父亲留下的道歉录音；中文，只要本集可拍剧本，不要季纲/后续集/视频交接。

检查：单集、约 45 秒、两名出镜角色、一个地点、反转能在动作或对白中呈现；父亲的预录音不增加出镜角色。不扩成全季策划或执行包。时长只能审阅估计，不能宣称经过实际演出计时。

**C｜单 Panel H3 提示词**

> 用 h3-prompt-writing 交一个信息已确认的 T2VA 单 Panel H3 提示词：6 秒、16:9、24fps、单连续镜头，无人空厨房，固定机位，清晨暖光，红色搪瓷茶壶从左向右缓慢冒出白色蒸汽，无人物/对白/可读文字/Logo，只有轻微水沸声。不要包、manifest、质检附件。

检查：交完整 H3 提示词，模式与必需章节正确，时间连续覆盖 6 秒，保留视觉/声音约束；无虚构引用标签、附件或生成提交。

**D｜只要分镜 Brief**

> 用 zero-to-story 只交一份单 Panel 黑白分镜设计 Brief，不生成图片、视频或执行包。内容已确认：6 秒，成年修表师在雨夜店内打开旧怀表，听见父亲录音后停住动作。两个 Camera Setup：前 3 秒桌面特写打开怀表，后 3 秒胸部近景看修表师反应。用一个含 2 格的黑白 Storyboard Sheet 表达两个机位；只要该 Brief。

检查：只交 Brief，2 个真实机位对应 2 格而非把语义拍点拆成 6 格；时序、动作和反应可画，保留录音尚无逐字稿这一事实，不伪造已生成图片或执行批准。

记录每项实际产物、拟提问/阻塞、是否越界，以及所读文件。读取次数若为 Agent 自报要明确注明；没有可靠数据时留空。只按可观察结果评价，不把“规则看起来正确”算作实际任务成功。少量单次运行不能证明统计上的速度、token 或总体质量提升。

## 本地检查

首次准备开发环境（选择带 venv、ensurepip 的 Python 3.12+）：

```powershell
./scripts/bootstrap_dev.ps1 -Python <Python可执行文件路径>
```

脚本在项目 `.venv` 中安装项目已有开发依赖及用于完整 YAML 解析的 PyYAML；不需要激活环境，不修改全局 PATH 或 ComfyUI。现有 `.venv` 不会被自动删除或替换；失败时按错误修复，不反复重装。

后续直接运行：

```powershell
./.venv/Scripts/python.exe scripts/validate_ai_config.py
$pytestTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('lfo-ai-checks-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $pytestTemp) { throw 'Expected a new temporary test directory.' }
./.venv/Scripts/python.exe -m pytest tests/test_ai_config_validation.py tests/skills tests/skill_adapter tests/test_mimo_video_skill.py -q --basetemp $pytestTemp -p no:cacheprovider --maxfail=1
./.venv/Scripts/python.exe -m ruff check scripts/validate_ai_config.py tests/test_ai_config_validation.py
```

配置检查解析所有项目 SKILL.md 的 YAML frontmatter、现有元数据 YAML，并检查入口及 references 中的内联本地 Markdown 文件链接。它不验证锚点、引用式链接、远程页面或模型行为；已有历史评测文件不当作活跃指令。Skill Creator 提供的 `scripts/quick_validate.py` 可另外逐个验证项目 Skill，Windows 下使用 `python -X utf8 <校验器路径> <Skill目录>`。

测试每次使用新的系统临时目录，避免本机已有 `pytest-of-Administrator` 的访问限制；关闭测试缓存以避开已有缓存目录的权限问题。不要复用任意已有目录作为 `--basetemp`，因为 pytest 会清理该指定目录。

验证范围随改动选择：入口/引用调整运行配置检查和受影响任务；校验器代码变化运行其测试；LFO 公共契约变化再扩大运行时验证。检查通过就交付，没有新改动或失败时不重复整轮。

## 本轮结果

基线与改写后分别由独立子 Agent 完成 A–D，各得到 4 份真实文字产物，均报告没有额外澄清。另完成一份未指定模型的视频复刻文字报告，以及一次明确动作主体后的 H3 定向复测，共 **10 份实际文字产物**。原文、文件 hash、自报记录和主 Agent 审阅结论保存在 [原始评估记录](evaluations/2026-09-07-ai-config.json)。

| 任务 | 实际观察 |
| --- | --- |
| A：润色 | 两轮保留数字、责任人与结论限制；改写后仍有“全面提升协同效能”等概括措辞，不能视为文风完全优化 |
| B：短剧 | 两轮守住单集、两名出镜角色、单一地点和录音反转；仍有怀表交接/后盖状态的连续性细节需编辑复核，未实演验证 45 秒 |
| C：H3 | 都交出三段 H3 文本；改写后把右向运动分配给茶壶，并加入背景底噪，与评审预期有偏差。此 H3 Skill 本轮未改，不能据此归因于入口精简 |
| C2：定向复测 | 输入明确为“茶壶静止、蒸汽向右飘、唯一水沸声”后，独立生成的提示词保留了这些约束；原始 C 结果照实保留 |
| D：分镜 Brief | 都按一个 6 秒 Panel、两个 Setup、一张 1x2 黑白板交 Brief，未误扩为六格或执行包 |
| 额外路线任务 | 只给 6 秒玻璃杯注入红液的文字描述、未指定模型，直接选择一个 H3 分支并说明依据；没有伪称视频观测或关键帧证据 |

另有 5 场景的独立静态推演：同包同 hash 复用、变更包重新批准、超时未知不重提、只要 Brief 的停止边界、串行生成与并行审查的分工。它们与项目契约一致，但不是实际生成验证。

每轮四个任务共享该轮 Agent 上下文，且未采集宿主 token、延迟或固定随机种子。这是小样本任务观察：确认了按范围交付的行为，也暴露了语义细节；不报告总体成功率、速度提升或“所有内容全绿”。

本地检查已完成：

- 10 个项目 Skill 通过官方 `quick_validate.py`；9 个元数据 YAML 完整解析通过。
- 本轮写入的 11 个 Skill 文件中，101 个内联本地文件链接均可解析；所有写入前后 hash 对应清单，其余快照 Skill 文件未被改动。
- 相关 **117 项测试通过**，包括新校验器 7 项、创作蓝图、Skill adapters 和 MiMo 测试。首次因旧默认临时目录权限而未执行测试主体，换用新唯一目录后通过；旧测试缓存产生 1 条写入警告，后续命令已关闭缓存。
- 新 Python 文件的 Ruff 检查和本轮变更的空白检查通过；环境准备脚本已实际建立可用 `.venv`。
- 未运行全量测试、doctor/preflight 或 live E2E；本轮没有修改运行时实现或提交媒体生成。过程中出现的其他并行运行时源码改动已保留，117 项记录只对应实际测试时的工作区，不作为那些改动的验收。

历史第一轮静态审阅及当时缺少工具的事实保留在 [配置审查记录](ai-config-audit.md)。本轮按必要验证完成后停止，没有用反复润色掩盖原始观察结果。
