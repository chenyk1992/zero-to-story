---
name: comfy-h3-image-executor
description: 由 Canvas worker 执行本地 MiniMax H3 Image 文生图、参考生成与编辑；支持项目范围内 1～16 张参考图，不从对话重复提交。
---

# H3 图片执行

通过画布选择 comfy-h3-image，冻结输入后由 scripts/execute.py 单次执行。
提示词逐字执行，不自动扩写。参考标记使用 <Picture 1> 至 <Picture 16>。
create 不接受参考；reference/edit 接受 1～16 张，edit 第一张为目标。
使用 4～20 MP 显式像素预算，建议从 4 MP 开始；新构图指定画幅，edit 沿用首图比例。
共用本地 Comfy MCP、机器级资源锁、未知回执保护与实际 PNG 检查；不重试、不切换提供方。
16 张为项目接入限制，不代表已完成多图质量或显存验证。不是遮罩局部重绘，不保证背景逐像素不变。
详情见 [H3 图片指南](../../../guides/h3-image.md)。
