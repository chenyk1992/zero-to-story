# 原 Skill 方法的项目适配

本轮另按需复用[通用反转](../../short-drama-screenwriter/references/reversal-design.md)、[表演](../../zero-to-story/references/performance-direction.md)、[时间效果](../../zero-to-story/references/time-effects-direction.md)、[对称风格](../../zero-to-story/references/symmetric-storybook-style.md)、[资产/布局方法](../../visual-design-creator/SKILL.md)。对应十三来源取舍在各方法source-notes维护；MV保留实际歌窗口和原文字/拼贴要求，不新增商品/影视六Beat。完整广告的歌曲委托只交音乐成果，不抢全片。

以下材料由用户提供，作为创作方法来源；当前生产以本项目规则、实际能力和用户指令为准。所需方法已保存在本 Skill 内，运行不需要原目录、外部 MV workflow 或故事 Skill 的创作文件。

| 来源 | 保留的方法 | 项目落点与可审阅证据 |
| --- | --- | --- |
| music-video-subtitle-generator | 实际主音轨时间轴、逐镜 Vocal Line / Typography / Action / Camera / Transition；文字作为空间图层；角色/场景/字样参考分工；跨镜文字动能 | music-timeline、mv-direction、typography-direction、visual-assets、production-handoff；计划能定位唱词、声音触发、文字可读时刻与转场 |
| cool-music-video | 复古印刷拼贴、Hero/Print/Action 字层、先可读后变化；动作族、空间路径与惯性；设计主导静点；主字族回收 | style-library、mv-direction、typography-direction 及文字方案模板；具体镜头有图层和动作过程，不止一个风格标签 |
| cool-music-video 的 music.md | 音乐先行、完整实际歌词、Hook/问答动机、groove、低频与鼓组、flow/押韵、编曲反差、人声层次及收尾 | music-direction 与音乐创作模板；前期创意简报完成创作稿，Music 3 生成主歌曲，采用后建立实际时间轴 |
| anime-game-pv | 角色轮廓与色块、空间和画风参考分工、动作与视觉高潮 | style-library、视觉资产模板；按歌曲组织，不把完整 MV 改成固定角色宣传 PV |

## 来源反查入口

| 原方法所在位置 | 项目内承接位置与检查重点 |
| --- | --- |
| subtitle-generator STEP 1–2：格式、时长、音乐窗口、歌词锁定与创意合约 | [音乐方向](music-direction.md)、[时间轴](music-timeline.md)、[创作计划](../assets/mv_plan.template.md)：交付意图与真实采用音频分开，选窗有依据，演唱原文不擅改 |
| subtitle-generator STEP 3–5：参考分工与逐镜模板 | [视觉资产](visual-assets.md)、[文字导演](typography-direction.md)、创作计划：独立卡职责、准确原文、人物动作、镜头与文字共同设计 |
| subtitle-generator STEP 6–9：五类衔接、画布完整脚本与主音轨合成 | [导演方法](mv-direction.md)、[生产交接](production-handoff.md)、[后期验收](finishing-and-review.md)：前后镜衔接、全局锚点、版本化完整脚本、真实采用媒体与最终视听证据 |
| cool-music-video typography.md / methods.md | 文字导演、[风格方法](style-library.md)、[文字方案](../assets/typography_plan.template.md)：字体骨架、版式、字腔穿越、A/B/C 层、触发—作用—恢复逐镜落实 |
| cool-music-video performance-and-space.md / style-guide.md | 导演方法、风格方法：动作链、空间支点、相邻镜头变化、设计静点、融合/纯风格与人物媒介区分 |
| cool-music-video music.md / prompt-blueprint.md | 音乐方向、[音乐创作稿](../assets/music_creation.template.md)、生产交接：实际歌词、Hook、flow、编曲反差与收尾；完整创作事实编译为真实 H3 输入，不在执行端压成摘要 |

这是方法对应关系，不是媒体生成通过证明。原模板的固定镜数、动作数、字符预算和色盘改为按作品选择；必须保留的是音乐与视觉的因果关系、可执行逐镜事实、真实参考传递和实际验收。完整 anime-game-pv 的问询与角色宣传流程不属于两份音乐 Skill 的迁移范围。

有意调整的原规则：不强制 15 秒、8–10 镜、固定动作数、英语屏幕字、每个人演唱或三张图片全部输入；时长、语言、主体和参考数量服从任务与真实接口。歌曲以项目 Music 3 或选定音频为主，保留整条主音轨，不改为各 H3 片段独立写歌。

剪辑按乐句与声音事件选择，不强制全片硬切或机械四分/八分拍网格。调速不能作为口型同步的默认补救；颗粒和调色也不能用来掩盖身份、动作或风格错误。真实连续动作才依赖已接受尾帧，普通换景不建立这种依赖。无可见演唱且精确开场充分时可用 I2V；可见演唱按[生产交接](production-handoff.md#参考用途到真实输入)使用 R2V 与对应歌曲片段，不为首帧控制丢掉音频参考。本地生产仍由 Canvas worker 按机器互斥执行，不照搬外部并行提交。

原 Skill 主要把动态文字、拼贴与人物遮挡写进 H3 逐镜提示词，由模型生成完整画面；它们没有附带一套必须移植的独立空间字幕渲染器。项目保留这条生成式路线，使用已有 H3/Canvas 执行入口，不为这些效果额外规定第三方插件或跟踪服务。后期负责主音轨、实际裁切和已选的独立字幕；只有要求在既有底片上独立新增/修复空间字层时，才需要另行核实合成能力。

原文明确了文字包装卡的样式参考职责；当前用户进一步要求具体上屏歌词先有对应图片。项目据此增加逐事件原文覆盖与实际输入检查，不把这一更明确的逐句图片规则冒称原文已有。通用样式卡与具体词图各有职责；I2V 通过有字首帧传递，普通 R2V 通过真实图片槽传递。图片不保证模型永久保持准确字形，仍须实际验收。

人物卡的原文要求是身份、气质、发型、服装轮廓、比例与姿态；两份音乐 Skill 均未强制正/侧/背三视图。anime-game-pv 也仅把立绘、人物图和三视图列为身份参考，明确三视图不是三个时间关键帧。当前项目按用户提供的角色设定图实例统一规格：每个新建角色单独1张横版16:9，固定正/侧/背视图、1–2张小尺寸半身变化、标志性动作和关键道具，人物描述从本片计划逐字复制。这是项目用户要求，不冒称原音乐Skill规则；既有采用版本与局部修正保留，不据静态完整卡保证整片身份一致。

原文没有完整的 I2V/R2V 模式选择表或提供方槽位协议；明确写出的 I2V 用途包括连续动作的尾帧接续。项目按真实接口补足“多卡制作首帧后 I2V”与“普通 R2V 分槽引用”，区分资料关联、提示词说明和实际输入，沿用用户对精确首帧优先 I2V 的偏好。源模板的全局参考说明与逐镜文字/动作/音乐事实保留，编译成项目 H3 官方格式；不照抄原外壳、固定字符数或未证实的输入上限。

功能迁移的证据包括：原有创作要求能进入完整 H3 输入、对应资产能按真实槽位传递、生成产物能进入主音轨剪辑与路线验收。仅补文档不证明真实成片通过；同时，尚未试生成也不能被误写成“必须先开发空间后期才具备这条路线”。原文提及的调速、全局 LUT/颗粒属于另外的后期操作，是否采用按实际作品决定；需要执行时核实具体工具和效果，不宣称基础编辑清单已支持。

## 音频事件与曲线方法补充

以下公开项目于 **2026-10-04** 查阅作者仓库、说明与相关源码；仅提炼创作方法，未安装、运行或复制外部代码。上面的原 Skill 来源与生成式文字路线继续保留。

| 来源与代码许可 | 采纳的方法及项目落点 | 不采纳的实现或约束 |
| --- | --- | --- |
| [Parseq](https://github.com/rewbs/sd-parseq)，[MIT](https://github.com/rewbs/sd-parseq/blob/master/LICENSE)；[事件、时间序列与关键帧说明](https://github.com/rewbs/sd-parseq#working-with-time--beats-audio-synchronisation) | 带标签事件、分频/音高/振幅候选和可编辑响应曲线的思路；导演方法先挑有作用的事件，再写回已有响应表和逐镜事实 | 不迁入 A1111/Deforum、逐帧 seed/strength/zoom、表达式或固定 BPM 网格；这些不是当前 H3 控制接口，文档也不新增音频分析能力 |
| [Tubeviz](https://github.com/interrupt21h/tubeviz)，[Apache-2.0](https://github.com/interrupt21h/tubeviz/blob/main/LICENSE)；[乐句编排源码](https://github.com/interrupt21h/tubeviz/blob/main/src/tubeviz/choreography.py) | 乐句蓄势、峰值前收住、释放与运动/复杂度分层；导演和后期按实际素材运动选择可用区间，候选曲线可由人工修订 | 不迁入独立素材库、渲染器、自动选片生产入口或评分阈值；局部 tempo、段落及情绪启发式不当作听审或 ACCEPT，自动效果曲线不冒称已接入 |
| [Motif](https://github.com/XinCoLab/motif)，[MIT](https://github.com/XinCoLab/motif/blob/main/LICENSE)；[事件层](https://github.com/XinCoLab/motif/blob/main/audio/key_moments_extractor.py)、[锚点优先规划](https://github.com/XinCoLab/motif/blob/main/planner/planner_v5_simple.py) | 先挑结构转折和少量重要声音落点，再填乐句内过渡；保留选中理由，区分音量与事件密度 | 不照搬固定阈值、事件数量、调速或自动评价；当前规划结果合并丢弃 `clip_offset`，不能据作者描述认定动作瞬间已准确对齐；未迁移其模型与后期链路 |

表中许可仅指仓库代码；外部模型、权重和素材的许可须分别核实。方法写回现有导演事实，不改变音乐时间轴 schema、Canvas 授权/运行/采用状态或 Comfy H3 执行入口。
