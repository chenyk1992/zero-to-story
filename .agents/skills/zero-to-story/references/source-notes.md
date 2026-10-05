# 来源说明

本目录中的动作与表演参考，是依据 [chenyk1992/manju-laoli-skill](https://github.com/chenyk1992/manju-laoli-skill) 固定版本 [`079df685f7cf2f0de635362bd359c233db38f9fe`](https://github.com/chenyk1992/manju-laoli-skill/tree/079df685f7cf2f0de635362bd359c233db38f9fe) 的导演资料所作的项目内重写。

保留的思路：

- 将动作写成目标、阻力、路径、接触、反馈和稳定结果；
- 从人物目标与刺激选择镜头可见的表演；
- 用景别决定能可靠表达的身体或面部细节。

此外，`storyboard-production.md` 中的三个段缝案例借鉴了外部资料关于真实末态续演、换机位连续性和声音过渡的讨论；`creative-assets.md` 的当前 Panel 素材检查借鉴了存在、用途、绑定、版本四个核对角度。两者均复用本项目既有的 Canvas readiness、`runtime_input_keys`、`ACCEPT` 尾帧和确认快照规则。

本项目主动未采用外部资料中的固定节奏、固定镜头/动作数量、强制换机位、全局 Asset-First 门禁、会话命令和“用户裁定”等流程约束。这里的文字、案例、字段映射和生产边界均按本项目现有契约重新编写，不能替代 Canvas 就绪检查或实际视频验收。

随该来源保留的 MIT 许可证见 [LICENSE.manju-laoli](../LICENSE.manju-laoli)。完整归属也登记在仓库根目录的 `THIRD_PARTY_NOTICES.md`。

## 视觉流程参考

本轮审查了 [ZY / popopo-99 的 zy-cinematic-realism](https://github.com/popopo-99/zy-cinematic-realism/tree/e78c9669d84373e60c2c9d60cf578184ae4b8c3a) 固定版本，参考其将画面风格落实到摄影位置、光源、材质、参考素材用途和结果局部诊断的思路。项目在原有 Style Brief、Medium Lock、Camera Setup、资产用途与 Canvas 交接中重新组织这些通用方法，没有引入该仓库的 Skill、卡片库、模板、模型适配器或代码，也不把非写实画风改成默认摄影写实。

该仓库采用 [CC BY-NC 4.0](https://github.com/popopo-99/zy-cinematic-realism/blob/e78c9669d84373e60c2c9d60cf578184ae4b8c3a/LICENSE)，与上文 MIT 来源不同。若以后需要直接复制或改编其受保护文本、模板或卡片，应单独核对实际用途和授权，不能沿用上文 MIT 声明。

## 开源创作工作台方法说明

以下官方仓库在 2026-10-04 访问并核对 README、实际源码与许可。本项目采用局部创作修改和实体复用的通用方法，自主编写指导与案例，未导入外部代码、提示词、模板或生产链。

| 来源与官方文件 | 核实许可 | 已采纳的方法 | 未采纳 |
| --- | --- | --- | --- |
| [HBAI-Ltd/Toonflow-app：director3dNode/src/agentTools.ts](https://github.com/HBAI-Ltd/Toonflow-app/blob/master/packages/nodes/director3dNode/src/agentTools.ts)、[导演台说明](https://github.com/HBAI-Ltd/Toonflow-app/blob/master/packages/nodes/director3dNode/readme.md) | 当前 master 的 [MIT](https://github.com/HBAI-Ltd/Toonflow-app/blob/master/LICENSE)；旧版许可不按当前分支追溯 | 按稳定 ID 定位局部对象，以草稿保存修订，保留未受影响内容；项目映射为 Panel/Setup 创作事实与当前源版本 | 3D 姿态/轨迹工具、外部团队调度、节点侧工具循环；不将其精确预演参数当作 H3 输入能力 |
| [mblanc/storycraft：app/features/storyboard/components/edit-scene-modal.tsx](https://github.com/mblanc/storycraft/blob/main/app/features/storyboard/components/edit-scene-modal.tsx)、[use-storyboard-actions.ts](https://github.com/mblanc/storycraft/blob/main/app/features/storyboard/hooks/use-storyboard-actions.ts) | [Apache-2.0](https://github.com/mblanc/storycraft/blob/main/LICENSE) | 分开处理构图、动作与对白，选用已有角色/环境事实，局部修改保持其他单元；项目仍由已有故事板编译完整单 Panel 交接 | Google 媒体后端、数组位置充当镜头身份、客户端并行生成及另一套 Scene 结构 |
| [chatfire-AI/huobao-drama：backend/src/agents/tools/extract-tools.ts](https://github.com/chatfire-AI/huobao-drama/blob/master/backend/src/agents/tools/extract-tools.ts)、[storyboard-tools.ts](https://github.com/chatfire-AI/huobao-drama/blob/master/backend/src/agents/tools/storyboard-tools.ts) | [CC BY-NC-SA 4.0](https://github.com/chatfire-AI/huobao-drama/blob/master/LICENSE)，源码公开且有非商业限制 | 查已有实体再找复用候选，将人物身份与镜头资产关联；项目进一步区分别名证据和年龄/服装阶段 | 直接复制其受保护实现或文字、自动按名字合并、删除旧分镜的批量替换、固定镜数/字数与供应商生成链 |

具体方法见[局部改拍](storyboard-production.md#局部改拍)、[角色身份与造型复用](creative-assets.md#角色身份与造型复用)及现有模板、单 Panel 交接；沿用既有蓝图 schema、账本、授权和运行状态。媒体仍由 Canvas 冻结当前输入，按本项目执行链生产并检查实际版本。
