# Local Windows ComfyUI profile

共同的角色、Panel ready、能力选择和实际验收规则见[项目共享生产规则](ai-system-prompt.md)。本文只记录本机 Comfy 环境，不定义新的审批或恢复流程。

本文只记录本机环境和单 Panel 执行前检查。机器路径、模型和凭据不进入 package，也不写入提示词。

相关工作流说明：

- [H3 工作流约定](workflow-conventions.md)：JSON、绑定、预检、执行和结果记录边界；
- [H3 VDN8](h3-vdn8.md)：VDN8 采样参数、已验证范围和性能口径。

## 当前机器

- ComfyUI Desktop：`D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI`
- `comfy-cli`：独立安装官方 `comfy-cli`，并确认当前版本支持 `run --wait --json`；默认 workspace 应指向上述目录，执行前以 `comfy --version` 和 `comfy env` 的实际结果为准
- 服务地址：`http://127.0.0.1:8188`
- GPU：RTX 5080 16GB，使用 H3 FL2VA int8 路径
- 模型目录：`D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\models\`

如果当前终端找不到 `comfy`，先按官方方式把 CLI 安装到可执行环境，例如：

```powershell
python -m pip install comfy-cli
comfy --version
```

官方 `comfy run --wait --json` 可返回 ComfyUI `/view` URL，某些本地版本也会给出绝对产物路径。LFO 会优先复制可解析的本地文件；只有 URL 时则通过同一 ComfyUI 服务的 `/view` 接口流式下载到 RunArtifactLayout。为避免额外下载，可在启动执行的同一 PowerShell 会话中配置输出根目录：

```powershell
$env:LFO_COMFY_OUTPUT_ROOT = "D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\output"
```

该值属于机器配置，不写入执行包或源码。`setup` 发现 ComfyUI 根目录时会自动把其 `input/` 和 `output/` 填入 machine profile；未配置这两个目录不阻断 H3 或 SeedVR2 路径，因为素材上传和输出下载都可通过同一 ComfyUI 服务的 HTTP API 完成。配置 `output` 目录只用于优先复制本地结果和做路径边界检查，不是 SeedVR2 的前置条件。

LFO 只接受本次 comfy-cli 结果中唯一、明确的视频输出；图片、多个视频候选或越过已配置输出根目录的路径都会直接失败。`timeout_sec` 默认是 7200 秒：既传给 comfy-cli 作为事件静默上限，也由 LFO 再加 300 秒退出余量作为整个 CLI 进程的硬上限。超时后当前 Panel 失败，LFO 只尝试中断一次当前 ComfyUI 执行以释放串行队列，不自动重新提交。

当前没有单独的 `D:\cyuiEnv\models\` 目录。H3 模型包括：

- `minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `minimax_h3_ref2va_pruned_int8_convrot.safetensors`
- `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `minimax_h3_video_vae_fp16.safetensors`
- `minimax_h3_audio_vae_fp32.safetensors`

## LFO machine profile

机器配置位于 `%APPDATA%\LFO\machines\local-windows.json`。ComfyUI 路径或安装变化后重新设置：

```powershell
python -m lfo.cli.main setup --machine-id local-windows
```

`setup` 只做本机能力发现并保存 machine profile；它不创建 `workspace/` 项目目录、SQLite/旧数据库 schema、环境快照，也不提交视频或 smoke 任务。当前公开 `setup` 不接受或依赖 `--smoke-level`；需要确认工具和服务可用性时使用下面的 `doctor`/`preflight`。

单 Panel 执行前检查：

```powershell
python -m lfo.cli.main doctor --machine-id local-windows
python -m lfo.cli.main preflight --machine-id local-windows
```

`doctor` 和 `preflight` 默认检查当前机器的 `comfy`、`ffmpeg`、`ffprobe` 以及 ComfyUI 可达性；不需要手写 `--tool-ids`。失败结果包含检查 ID、失败原因和可执行的修复提示。检查通过后，同步运行当前 Panel 的隔离执行单元，并在 `validate`/`execute` 上继续传入 `--machine-id local-windows`。Runtime 会把 profile 中的 ComfyUI 地址、`comfy` 可执行文件和可选输出根目录传给实际执行器。LFO 不启动并行任务，不在 ComfyUI 失败后自动重试；环境问题修复后由调用方重新执行当前 Panel。

Canvas 和 package CLI 共用机器范围的 Comfy 提交占用和持久提交回执。需要诊断时运行 `python -m lfo.comfy.admission`；`--reconcile <request-id>` 只读取原始 Comfy `/history`，不重新提交。状态目录由应用数据目录或 `LFO_VIDEO_STATE` 决定。

```powershell
python -m lfo.cli.main validate path/to/panel-P001.execution-package.json --machine-id local-windows
python -m lfo.cli.main execute path/to/panel-P001.execution-package.json --approved-sha256 <approved-sha256> --machine-id local-windows
```

真实检查仅在明确需要 provider 集成时运行：

```powershell
python scripts/live_e2e_execution_package.py path/to/panel-P001.execution-package.json --approved-sha256 <approved-sha256> --machine-id local-windows
```
