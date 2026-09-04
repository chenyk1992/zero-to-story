# 单 Panel 运行与失败处理

当前公开执行流程不提供复杂的恢复协议。一次命令只处理一个 Panel，并作为独立的短生命周期执行单元同步等待官方 ComfyUI/comfy-cli 完成。ComfyUI 是单任务队列，因此 Panel 必须严格串行。

## 执行前

1. 确认当前 Panel package 只含一个 Clip；所有 Panel package 和最终 assembly package 都直接放在同一 `workspace/projects/<project_id>/` 根目录并使用唯一文件名，避免前一 Run 的 `outputs/<run_id>/...` 相对 URI 因包子目录而失效。
2. 运行 `validate`，把成功结果中的 `package_sha256`（exact file SHA-256）交给用户批准；只有需要查看路由详情时才运行可选的 `plan`。
3. 将用户批准的 hash 作为 `execute --approved-sha256` 的唯一锁。
4. 确认素材存在、operation 与引用槽位匹配、ComfyUI/FFmpeg 环境可用。

执行时再次计算 package 完整文件字节 hash。任何变化都停止，不修改文件、不自动修订提示词、不提交生成。

## 正常路径

```text
validate → execute → 收集视频 → 调用方最小 QC → ACCEPT → 按下游需要提取真实末帧
```

LFO 将生成视频复制到当前项目的 Run artifact 目录并返回文件路径；调用方只负责最小语义 QC 和 `ACCEPT` 决定。下一 Panel 只有在前一段 `ACCEPT` 后才能启动；确需连续首帧或边界证据时，调用方再从已接受视频提取真实尾帧，而不是文字描述。

## 失败路径

以下任一情况都立即返回 `REJECT` 或 `ERROR` 并结束当前 Panel：

- package hash 不匹配；
- JSON、素材、operation、引用槽位或基本规格无效；
- ComfyUI 不可用、命令失败、超时或没有有效输出；
- LFO 最小技术 QC 发现文件不存在、无视频流、无法解码、时长或分辨率无效；
- 调用方语义 QC 发现明显生成错误，或连续镜头明显倒带、重复收尾、状态跳变。

失败不自动重试，失败候选不导入为正式产物；Attempt、UNKNOWN、lease、heartbeat、recovery 和长篇 QC 审计不属于公开交接协议。底层 SQLite Run/Task/Attempt 基础设施如有内部记录，由 LFO 内部维护，调用方不读取或维护这些恢复记录。需要重做时，创作侧/用户明确决定是否重新准备当前 Panel；若改变了执行内容，生成新 package revision 和新批准 hash。

## 最小 QC

LFO 只做最小技术检查：文件存在、可读取、包含视频流，且探测到的时长和分辨率为正；技术失败返回 `ERROR`。LFO 不判断黑帧、人物/文字质量或镜头连续性。调用方只检查可播放、主要内容无明显错误，以及有前序片时能否自然衔接，结果只有 `ACCEPT` 或 `REJECT`；不评分、不自动修复，也不把轻微偏差转成重试。

## 最终组装

所有 Panel 都 `ACCEPT` 后，由调用方构造一份只含 `video.passthrough` Clip 的 assembly package。该包必须独立执行 `validate`，使用返回的 `package_sha256` 取得用户批准，再运行一次 `execute --approved-sha256` 完成直接 `cut` assembly。最终文件通过一次可播放检查后写入：

```text
workspace/projects/<project_id>/final/<output.directory>/
```

任一 Panel 未接受、已接受视频缺失或 assembly package hash 不一致时，禁止组装；真实尾帧不是最终组装输入，只有下游 Panel 或边界检查需要时才提取。

## 环境问题

如果本地 ComfyUI 或工具不可用，先运行 [`docs/local-windows.md`](local-windows.md) 中的 setup/doctor/preflight。环境修复后由调用方重新执行当前 Panel；LFO 不在后台等待或自动恢复原命令。
