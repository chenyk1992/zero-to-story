# Virtual Presenter v1

`virtual-presenter` 是创作侧用于规划自然连续口播镜头的 Skill。它负责角色、环境、文案、声音参考、H3 提示词和用户确认；LFO 只负责执行一个已经确认的 Panel/Clip。

## 创作资产

项目数据放在 `workspace/projects/<project_id>/` 下。角色图、全景图、声音和环境视图是输入素材；执行包只引用当前 Panel 实际需要的文件，不把平台缓存或内部 ID 写入公共契约。

环境辅助工具可从大约 2:1 的 equirectangular 全景图生成四个方向视图。它拒绝不符合比例的输入，不拉伸原图。

## 单 Panel 交付

每个口播 Panel 生成一个只含一个 Clip 的 `lfo.video-execution.v1` package。需要连续接力时，下一条 Presenter Panel 使用上一段完整 `ACCEPT` 视频作为普通 `ref_video_0` 参考；只有其他下游 operation 明确要求精确首帧时，才从接受视频提取真实尾帧并绑定为 `first_frame`。

执行顺序固定为：

```text
创作审批 → package → validate（返回 package_sha256）
→ 用户批准 package 完整文件字节 SHA-256（exact file SHA-256）
→ 当前 Panel 的隔离执行单元 → 同步 ComfyUI/comfy-cli → 最小 QC → ACCEPT/REJECT
```

`plan` 只在需要时用于诊断，不是执行前置步骤。

LFO 不批量执行多个 Shot，不并行调用 ComfyUI，不做语义评分，不自动换 seed、改提示词或重试。ComfyUI/素材失败即停止；调用方做最小 QC 并决定 `ACCEPT/REJECT`，需要重做时由用户显式重新准备当前 Panel。

## 最终组装

所有口播 Panel 都 `ACCEPT` 后，调用方一次性创建只含 `video.passthrough` Clip 的 assembly package，运行 `validate` 取得 `package_sha256`，由用户批准该完整文件字节 SHA-256 后再 `execute` 一次，按顺序直接 `cut` 并做一次可播放检查。最终文件写入项目的 `final/<output.directory>/`。

机器环境检查见 [`docs/local-windows.md`](local-windows.md)，当前执行契约见 [`docs/package-v1-reference.md`](package-v1-reference.md)。
