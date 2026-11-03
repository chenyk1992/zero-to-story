---
name: comfy-image-executor
description: 由 Canvas 服务执行已确认的本地 Qwen Image 2.1 图片快照，支持文生图、1～10 张图片参考生成和图片编辑。用于执行适配与故障诊断；不编写创作提示词，不由 Agent 重复启动生成。
---

# 本地 Qwen 图片执行

Canvas 服务冻结图片请求后进入 `queued`，内部 worker 调用 `scripts/execute.py` 单次执行并回填；对话侧通过画布编辑、确认和查询。

使用规范见 [Qwen 图片指南](../../../guides/qwen-image.md)。影视角色卡/分镜模板由 zero-to-story 选择，产品/服装/海报/最终网格模板由[视觉资产专能](../visual-design-creator/SKILL.md)选择；执行器逐字使用冻结提示词。

- create 不接受图片；reference/edit 接受 1～10 张。编辑第 1 张为目标，其余至多 9 张辅助参考。
- 数字编号按实际输入顺序；提示词使用 <image1> 至 <image10>。用途写清楚，不把 related 连线当图片输入。
- 新构图必须给画幅与像素预算；编辑沿用首图处理后尺寸，不接受新画幅或像素预算。参考预算边长 0 保留尺寸并对齐 32；1024 表示约 1024² 像素。
- 去背景使用 edit 并在提示词明确透明要求，启用 transparent 进行真实透明度检查。不是蒙版局部重绘，不保证未修改区域逐像素不变。
- 本地图片与 H3 共用 video 资源键和 VideoSubmissionGuard；旧未知回执继续有效。失败不重试、不换模型或后端、不清空占用。
- 原始运行记录 workflow.json、conditions.json 与真实 PNG 留在当前 run 目录；技术成功不代替角色身份、道具状态和分镜连续性验收。

适配优先复用在线 ComfyUI；本地服务离线时由画布通过官方 Comfy MCP 的 `launch_comfyui` 启动已配置安装并等待就绪。后续上传、节点与工作流预检、单次提交、原任务查询和产物取回均通过同一 MCP 会话；不自动安装、更新、启动备用实例或改写用户数据库。
