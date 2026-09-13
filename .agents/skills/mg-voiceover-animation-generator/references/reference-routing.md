# MG Skill 参考与执行路由

共同的角色、授权、Panel ready 和停止规则见[项目共享生产规则](../../../../docs/ai-system-prompt.md)；本文件只索引 MG 专业参考。

本文件是参考资料和 Canvas 交付的轻量索引。只读取当前任务会影响决策的资料。

## 1. 创作资料路由

先读 `h3-mg-prompt-template.md`，再按语义选择：

| 当前需求 | 读取 |
|---|---|
| 所有 MG 口播任务 | `h3-mg-prompt-template.md` |
| 风格、版式、色彩、层级、信息密度 | `visual-style-layout-library.md` |
| 卡片、图标、线条、镜头、转场、桥接 | `element-motion-transition-library.md` |
| 标题、关键词、输入框、动态字形 | `kinetic-typography-motion-library.md` |
| 抽象概念、对比、分流、聚合、波形 | `mg-motion-pattern-library.md` |
| 数字、百分比、增长、排名、KPI、进度 | `data-visualization-motion-library.md` |

不存在的语义映射、桥接或 UI 专用资料不应被引用；用现有资料的语义映射和元素动效规则完成判断。历史 Seedance 资料仅在明确的兼容创作需求下读取，不能替换当前 H3 → Canvas 流程或绕过能力检查。

## 2. 视觉参考路由

在准备执行输入前，由当前指令或已确定的创作方案显式选择生成模式。参考数量只用于核对，不用于自动推断；Canvas 字段按当前能力填写：

| 已确认意图 | H3 / Canvas 路由 |
|---|---|
| 无视觉参考 | T2V / `t2v`，不绑定媒体输入 |
| 单张图片被明确批准为精确首帧 | I2V / `i2v`，绑定唯一 `first_frame` |
| 两张图片被明确批准为精确首帧和尾帧 | FL2V / `fl2v`，绑定 `first_frame` 与 `last_frame` |
| 普通身份/构图/风格参考，或视频参考 | R2V / `r2v`，使用类型匹配的参考输入 |

每个视觉参考都要写清语义用途、保真要求、与 Panel 的绑定、审阅状态和实际来源。产品图由 Skill 生成时同样如此；生成产品图不等于已经生成最终动画。外部口播音频通过音频输入或明确的后期责任登记，不伪装成视觉参考。

## 3. Canvas 交接

方案确定后，先把当前 Panel 的 MG 创作事实交给 [h3-prompt-writing](../../h3-prompt-writing/SKILL.md)，再把其返回的最终 H3 提示词、模式、素材、生成参数、音频/后期责任和验收要求交给 [canvas-workspace](../../canvas-workspace/SKILL.md)：

- 默认建立一个连续生成 Clip；不要把时间线段落误建成多个生成 Panel。只有用户明确要求多条成片或当前 H3 时长上限要求拆分时，才建立多个独立 Panel。
- `pixel_ratio` 写到 Canvas 节点的 `megapixels`；未指定时不从交付尺寸推断。例如用户明确选择 `0.4` 时写成 `megapixels: 0.4`；`1080x1920` 等交付尺寸属于接受输出后的确定性处理规格。
- 有外部口播音频时登记实际素材及其输入或后期用途；无外部口播时记录是否允许 H3 原生音频。音频来源必须在提示词、Canvas 节点和后期责任中一致。
- 普通字幕默认关闭。MG 动态字、UI 标签、标题和数据标签不是字幕。
- 保存节点只是准备草稿；只有页面确认或对话明确授权才冻结 `execution_snapshot`。用户选择 `comfy` 时由 Canvas 服务调用 `comfy-video-executor`，本 Skill 不直接调用 comfy-cli。

## 4. 实际媒体、接力与成片

每个已确认快照只提交一次。调用方查看回填的实际 Clip，记录实际末态和实际音频证据，再输出一次 `ACCEPT`、`REJECT` 或证据不足时的 `INCONCLUSIVE`；拒绝、未知或任一执行失败即停止。请求状态未知时核对同一 Canvas 请求，不重新提交、切换提供方或建立恢复循环。

真实末帧只在下一 Panel 的已确认模式需要精确首帧时从已接受的实际输出提取、导入画布并绑定；R2V 可按连续性计划使用完整 `ACCEPT` 视频作为普通参考，不把普通参考冒充精确首帧；T2V/硬切无需尾帧。全部 Panel 接受后，如用户要求完整成片，只对已接受的 Canvas 输出做确定性媒体处理，落实顺序、最终口播音频、字幕和交付规格，并检查实际文件的可播放性与视听同步。不要把后期处理变成第二条生成入口。
