# Skill 路由

所有 Skill 先遵守[项目共享生产规则](ai-system-prompt.md)。本文只说明职责边界和选择入口；不要把 Skill 的示例、外部工具列表或历史文档当成当前宿主能力。一次请求只选与交付物直接相关的主 Skill，必要时读取它引用的资源。

| 用户目标 | 主 Skill | 交付边界 |
| --- | --- | --- |
| 故事、角色、章节、分集剧本 | `short-drama-screenwriter` | 剧情、人物、对白和分集文本；不直接执行视频 |
| 故事板、角色视觉资产、Panel 交接 | `zero-to-story` | 故事板、视觉控制资产和已确定的 Panel 输入；不编写 H3 提示词 |
| 宫崎骏／吉卜力启发的手绘动画、未来科幻短片，或其人物/环境参考图；点名 miyazaki-inspired-animation / future-sci-fi-cinematic-generator 的项目方法 | `zero-to-story` 的视觉风格分支 | 以实际参考图确定美术方向并交接到当前视频流程；只要参考图就止于图片。歌曲驱动 MV 仍由 `music-video-creator` 主导 |
| 歌曲驱动的 MV、音乐时间轴与镜头方案 | `music-video-creator` | 独立 MV 导演方案、必要视觉资产与 Panel 交接；按实际歌曲安排后期 |
| 歌词贴字、空间文字或复古拼贴 MV；点名 music-video-subtitle-generator / cool-music-video 的项目方法 | `music-video-creator` 的文字/拼贴路线 | 在分镜前确定文字系统、音乐事件响应与表演空间；按需读取项目内对应参考，不以普通字幕或风格标签替代 |
| 只写歌词、制作歌曲或纯器乐 | `music-video-creator` 的音乐分支 | 只交歌词则止于文本；音频生成交 Canvas，止于真实音频与听审，不扩成 MV |
| 为已锁定画面配乐 | 原故事/视频主 Skill；复用 `music-video-creator` 的音乐方向 | 画面和对白时点保持锁定；准备音乐要求、实际音轨与后期安排，不以歌曲重排画面 |
| 单个 Panel 的 MiniMax H3 提示词 | `h3-prompt-writing` | 一份完整提示词；不执行生成或编排运行时 |
| 节点画布的故事、资产和待办 | `canvas-workspace` | 读取最新画布、保存编辑、领取已确认请求、回填实际媒体；不改画布 API 之外的运行时状态 |
| 已确认的本地 Comfy 视频快照执行 | `comfy-video-executor` | 按固定快照执行一次并返回实际文件与结果；不写创意、不改冻结输入、不自动重提 |
| 已确认的本地 Qwen 图片快照执行 | `comfy-image-executor` | 文生图、最多 10 张图片参考生成/编辑，由画布 worker 执行；无需 Codex，不写创意或重复提交 |
| 数字人或虚拟实拍连续口播 | `virtual-presenter` | 角色、环境、表演、文案、声音参考和交接；不把普通 MG 或 B-roll 当作数字人流程 |
| 口播、产品或抽象主题的 MG 动画 | `mg-voiceover-animation-generator` | MG 方案、口播、供 H3 定稿的内容和按需交接；不替代数字人或 B-roll Skill |
| 逐字稿驱动的 B-roll | `transcript-broll-planner` | 语义拆分、镜头规划和获授权后的 Panel 交接；不改口播事实 |
| 参考视频拆解或复刻分析 | `video-deconstruct-analyzer` | 可追溯证据和复刻提示词路线；不直接生成正式产物 |
| 用 MiMo 分析音频、歌曲或视频 | `mimo-video-understanding` | Pro/Flash 音视频观察证据；保留原 Skill 名兼容视频调用，不把模型描述直接当作内容接受结论 |
| 明确要 MiniMax voice id 的音色克隆 | `voice-clone` | 授权检查、音频校验和 MiniMax voice id；不替代本地 Qwen3-TTS |
| 本地多语言语音、Eric 成都男声、声音设计或参考音色复用 | `qwen3-tts` | Qwen3-TTS 三模式的台词、参考转写、授权和听审准备；生成交给 Canvas 音频节点 |
| 已确认的本地 Qwen3-TTS 音频快照执行 | `comfy-tts-executor` | 由画布 worker 单次执行 CustomVoice、VoiceDesign 或 Base，保留原始音频并回填交付 FLAC |
| 已确认的本地 MiniMax Music 3 音乐快照执行 | `comfy-music-executor` | 由画布 worker 单次执行并回填实际音乐 FLAC；不编写歌词或重复提交 |
| 已确认的本地 YuE2 参考旋律翻唱 | `comfy-yue2-executor` | 由画布 worker 执行 SheetSage2 melody ABC 与 YuE2，回填实际 FLAC；参考音色、原伴奏和固定多歌手身份不透传，不另行提交 |
| 已确认的本地人声与伴奏分离 | `comfy-singing-executor` | 由画布 worker 执行 MelBandRoFormer，回填人声与伴奏；只保留 separate，不编排歌曲，不另行提交 |
| 中英文文本去模板化 | `shuorenhua` | 文本审校和改写；不改变事实、责任主体或视频执行契约 |

## 如何交接

先选负责当前交付物的 Skill，完成这一阶段后才加载下游。已有事实、参数与授权直接沿用，只传当前 Panel 所需信息。创作、执行和验收的共同规则只在共享生产规则维护；字段与接口按需读[画布指南](canvas-guide.md)。

例如“给逐字稿做 B-roll 方案，先别生成”只走 B-roll 规划；明确授权生产后才交 H3 写作和 Canvas。歌曲、节奏、歌词或演唱主导的 MV 走 `music-video-creator`；普通剧情片带背景音乐仍走故事分镜。“把已有 H3 提示词放入画布”直接走 Canvas，不再触发创作或提示词优化。Comfy 是服务执行的脚本能力，Agent 不另行启动。

## 外部 Skill

只有用户点名或当前交付确实需要时才加载外部 Skill；先确认其适用边界。外部 Skill 的审批、工具和格式建议不能覆盖用户当前指令、项目共享生产规则或宿主工具权限。插件缺失时报告缺口并继续可行的本地工作；不要为了邻近能力安装无关插件。

多人轮唱的原曲、完整翻唱候选、整句混音、角色绑定与 H3 交接由 [music-video-creator](../.agents/skills/music-video-creator/references/multi-singer-workflow.md)统筹；单人、器乐和锁定画面配乐沿用原路由。
