# 本机 ComfyUI 与画布 MCP

共同的确认、排队、失败和验收规则见[项目共享生产规则](ai-system-prompt.md)。画布服务持有自己的官方本地 Comfy MCP 会话；不读取宿主的 `.codex/config.toml`。

## 当前机器与准备

当前参考安装是 ComfyUI Desktop `D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI`，服务地址 `http://127.0.0.1:8188`，GPU RTX 5080 16GB。新机器应按实际目录配置。官方 `comfy-mcp` 安装在项目隔离环境 `.venv/comfy-mcp/`，它内部调用已安装的官方 `comfy-cli`；具体安装方法见[官方本地 MCP 指南](https://docs.comfy.org/agent-tools/mcp.md#local-comfy-mcp-connection)。项目预检不自动安装或升级依赖。

H3 需要已配置的节点和模型；VDN8 还需要 `ComfyUI-VDN-H3` 与完整 `vdn/stage-dmd-step-250/` bundle。Qwen 图片和 TTS 需要各自节点与模型。每次运行以 MCP 的实时节点、模型文件名及工作流预检为准，不用旧检查记录替代。

项目 VDN 自动内存策略使用 `ComfyUI-VDN-H3` 1.5.2 或更新版本。量化分支可通过快照 `vdn_checkpoint` 明确选择已安装的完整 INT8 ConvRot 8 步 bundle；当前优化不自动下载模型或更新节点。代码与模板不按 GPU 型号分支，换电脑只需同步项目并核对该机的路径、节点和模型，不重新实施优化。具体参数与测量口径见 [VDN8 指南](h3-vdn8.md)。

## 画布服务配置

在项目根目录创建本机专用、Git 忽略的 `.lfo/comfy-mcp.json`：

```json
{"comfy_mcp":{"url":"http://127.0.0.1:8188","command":"<项目>/.venv/comfy-mcp/Scripts/comfy-mcp.exe","comfy_bin":"<本机>/Scripts/comfy.exe","timeout_seconds":7200}}
```

也可用 `LFO_COMFY_MCP_URL`、`LFO_COMFY_MCP_COMMAND`、`LFO_COMFY_MCP_COMFY_BIN`、`LFO_COMFY_MCP_TIMEOUT` 与 `LFO_COMFY_MCP_MODEL_VENV` 指定项目服务环境。目标只能是本机回环 HTTP 地址；若配置中的目标互相冲突，执行器会拒绝连接。媒体检查程序仍可用 `LFO_FFMPEG` 与 `LFO_FFPROBE` 指定。

图片、视频、TTS 均由画布内部 worker 在确认后执行，使用同一 MCP 执行链和机器锁。adapter 以 `upload_file(overwrite=False)` 上传冻结素材，从回执取得实际文件名与子目录；一次 `validate_workflow` 核实完整工作流，不普查所有节点 schema。VDN 额外核实 `ApplyVDNH3` 的策略兼容性，其他能力按自身要求核对模型文件名；完整节点检查供显式诊断使用。先写持久提交意图，再调用一次 `run_workflow(wait=False)`。拿到 `prompt_id` 后立即写入回执，随后用 `job` 查询原任务，以 `fetch_outputs` 将产物取回当前运行目录并检查媒体。保存画布本身不会启动生成。

TTS Base 参考音频要求上传成功回执且源文件在上传前后未变化；不读回服务端文件比较 SHA-256。独立 Tokenizer 只核对 MCP 返回的文件名，不直接检查文件大小。原始 `original.flac` 保留，画布回填按所选语速处理的 `speech.flac`。

## 诊断与恢复

`VideoSubmissionGuard` 的机器互斥覆盖提交与原任务等待。进程丢失后，应用数据目录 `zero-to-story/video/submission.json` 的回执继续阻止未知任务；可用 `LFO_VIDEO_STATE` 指定状态目录。只读检查与原任务核实：

```powershell
./.venv/Scripts/python.exe -m lfo.comfy.admission
./.venv/Scripts/python.exe -m lfo.comfy.admission --reconcile <canvas-request-id>
```

核实只通过 MCP `job` 查询原编号，不重新提交，也不直接改写画布状态。没有远端编号、空队列、断线或等待超时都不能证明任务已经结束。媒体必须来自本次 `fetch_outputs`，路径位于当前运行目录，且通过图片、视频或音频检查后才能回填。

本地 ComfyUI 离线时，共享连接层以 MCP `server_info` 获取既有工作区和启动选项，使用该安装的既有模型 Python 环境调用 `launch_comfyui`，再检查服务就绪。可用 `LFO_COMFY_MCP_MODEL_VENV` 指定环境；否则依次寻找安装内 `.venv`、`venv` 和 Desktop 旁的 `standalone-env`。找不到即停止，不继承画布的虚拟环境。启动超时保留 `startup.json`，阻止重复拉起；在线实例直接复用。

正常连接不额外查询服务状态，也不增加 HTTP/TCP 健康探测。仅提交前的上传、工作流检查等安全操作失败且 `server_info` 证实离线时，才执行上述启动流程并重试该操作一次；若实例在线，直接报告原操作错误。任何一次提交尝试后，都不自动启动恢复或重提原任务。

真实生成只执行已确认且输入明确的画布请求。环境检查、文档维护和自动测试不启动真实媒体生成。
