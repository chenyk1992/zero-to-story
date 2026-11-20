# 本地 MiniMax H3 Image

图片节点选择「本地 MiniMax H3 Image（ComfyUI）」；Qwen 2.1 保留为独立选项。
文生图不连接参考图；参考生成和编辑连接 1～16 张图片，按实际输入顺序使用 `<Picture 1>` 等标记。编辑第一张为目标，其余为辅助参考。
文生图和参考生成填写画幅与 4～20 MP 像素预算；编辑填写像素预算并继承首图比例。建议先用 4 MP，默认 6 步、Euler/simple、CFG 1。高分辨率和多参考的显存、速度及质量仍需实际验证。

沿用官方示例的 H3 Image INT8 模型、Qwen3VL 32B 编码器和专用 FP16 VAE。执行逐字使用冻结提示词，没有接入示例中 Qwen 自动扩写。输入由模型节点内部处理参考缩放；不复制示例中先把参考图放大到 4 MP 的外部步骤，输出尺寸则按所选预算计算并对齐 32。

本地节点接口允许动态多图，项目当前限制 16 张；这不是 16 张实际生成效果已经验收的声明。当前不提供透明背景承诺或遮罩局部重绘。

保存为草稿；确认后进入现有 Canvas worker，单次提交，共用资源锁和未知任务保护。失败不重试或自动切换模型，成功回填实际 PNG。

## 模型文件

- diffusion_models：`minimax_h3_image_pruned_int8_convrot.safetensors`
- text_encoders：`qwen3vl_32b_minimax_h3_int8_convrot.safetensors`
- vae：`minimax_h3_image_vae_fp16.safetensors`

能力列表的“可用”表示项目执行入口与基础工具就绪，不代表模型已安装；提交前仍执行 Comfy 工作流预检。缺模型时停止，不自动下载或使用 `p-h3-image` 代替。
