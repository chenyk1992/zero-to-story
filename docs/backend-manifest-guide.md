# Backend Manifest 指南

Backend Manifest 是 LFO 在单 Panel 执行前读取的能力声明。它只描述“当前 operation 能否执行”和工作流如何绑定，不包含故事、角色或镜头决策。

## Manifest 必须声明

- 稳定的 `backend_id`、revision 和 workflow hash；
- 支持的 operation 与输入媒体类型；
- 引用数量、固定槽位和 placement 能力；
- 时长、帧数、画幅、像素和 FPS 约束；
- 原生音频和 seed 行为；
- 所需模型、节点和本地环境；
- 输出文件的媒体签名。

计划阶段按 package 的显式 operation 和引用过滤能力；不满足时返回明确错误，不静默换模式、删掉必需引用或改变输出规格。分镜板的存在不会自动选择 R2V。

## ComfyUI 工作流

工作流 JSON 放在 `src/lfo/registry/`，可变输入使用稳定的 `_meta.title` 和 class type 绑定。ComfyUI 官方 comfy-cli/本地服务负责真正的节点执行；LFO 对当前 Panel 的 H3 工作流只提交一次并同步等待。package 显式开启 SeedVR2 时，放大是另一个仅提交一次的确定步骤，不做 OOM 后备选重提交。

执行成功必须返回当前 Panel 的可用视频文件；随后由调用方执行最小 QC、决定 `ACCEPT`，并按需提取真实末帧。执行失败直接返回 `ERROR`；公开交接不包含 provider job 恢复、重试预算、lease、heartbeat 或后台任务，调用方不读取或维护恢复记录。

## 检查顺序

```text
Manifest 静态校验 → 本地环境 doctor/preflight → 单 Panel smoke → ACCEPT/REJECT
```

新增 workflow 先通过静态 schema、节点/模型预检和一个单 Panel smoke。需要改变 operation、引用槽位、提示词或输出策略时，创作侧重新确认 package hash；Manifest 不负责决定是否重做。
