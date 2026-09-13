# Local Windows ComfyUI profile

共同的角色、Panel ready、能力选择和实际验收规则见[项目共享生产规则](ai-system-prompt.md)。本文只记录 Canvas Comfy adapter 使用的本机环境，不定义新的授权、重试或恢复流程。

## 当前机器

以下是本项目验证过的一台参考环境，不是安装前提。新用户按实际安装目录、GPU 与模型配置运行，不应照搬盘符或据此假定固定生成时长。

- ComfyUI Desktop：`D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI`
- 服务地址：`http://127.0.0.1:8188`
- `comfy-cli`：独立安装官方版本，并确认支持 `run --wait --json`
- GPU：RTX 5080 16GB
- 模型目录：`D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\models\`

如果当前终端找不到 `comfy`，按官方方式安装到画布服务使用的同一执行环境，并核实实际版本：

```powershell
python -m pip install comfy-cli
comfy --version
comfy env
```

当前 H3 模型包括：

- `minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `minimax_h3_ref2va_pruned_int8_convrot.safetensors`
- `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `minimax_h3_video_vae_fp16.safetensors`
- `minimax_h3_audio_vae_fp32.safetensors`

VDN8 还需要 `ComfyUI-VDN-H3` 节点和模型根目录下的 `vdn/stage-dmd-step-250/` bundle。以 adapter 对运行中 `/object_info` 的本次预检为准，不能用旧检查记录代替。

## Canvas adapter 配置

本地 Comfy 视频在页面确认后进入 `queued`。画布服务内部 worker 启动项目 `.agents/skills/comfy-video-executor/scripts/execute.py`；adapter 通过本地 HTTP 上传固定素材、读取 `/object_info`，再同步调用一次官方 `comfy run --wait --json`。这条路径不经过 Agent claim。

adapter 依次读取以下安全连接配置，显式参数优先：

- 可选配置 JSON；
- `%APPDATA%\LFO` 下已有的全局或机器配置；
- `LFO_COMFY_BASE_URL`、`LFO_COMFY_CLI`、`LFO_COMFY_TIMEOUT`、`LFO_COMFY_OUTPUT_ROOT`、`LFO_FFPROBE`。

只读取服务 URL、CLI 路径、超时、输出根目录和 ffprobe 路径；凭据及无关字段不会输出。默认服务地址为 `http://127.0.0.1:8188`。如果官方 CLI 返回本地绝对路径，adapter 会从该路径复制；否则通过同一 ComfyUI 服务的 `/view` 下载。可以在启动画布服务的同一 PowerShell 会话设置输出根目录，减少下载：

```powershell
$env:LFO_COMFY_OUTPUT_ROOT = "D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\output"
```

该值只用于优先读取实际输出和执行路径边界检查，不写入画布提示词。缺少输出根目录不会阻止通过 `/view` 回收结果。

## 检查与诊断

启动画布前至少核实：

```powershell
comfy --version
ffmpeg -version
ffprobe -version
```

页面能力目录还会检查 `comfy` 与 `ffprobe` 是否可执行；真实提交前 adapter 会检查 ComfyUI `/object_info`、必需节点以及服务声明的模型和枚举值。检查失败会结束当前 run，不会切换模型、删引用或自动重提。

Canvas Comfy 只接受本次 CLI 结果中唯一、明确且可读取的视频。adapter 会把它复制或下载到当前 run 输出目录，并用 ffprobe 检查视频流、时长、尺寸和编码。技术成功后由画布服务回填实际媒体；故事生产仍需基于实际画面和声音作内容验收。

机器级提交由 `VideoSubmissionGuard` 串行保护，互斥覆盖该次提交和整个同步等待周期。持久回执位于应用数据目录 `zero-to-story/video/`，可用 `LFO_VIDEO_STATE` 指定；执行进程丢失后，它继续阻塞未知任务，直到依据原任务证据核实结束。回执编号与对应 Canvas run 的 `request_id` 一致。诊断或核实原任务时运行：

```powershell
python -m lfo.comfy.admission
python -m lfo.comfy.admission --reconcile <canvas-request-id>
```

第二条命令只读取原 Comfy `/history`，不会重新提交，也不会直接改写画布状态。没有远端编号、空队列或本地停止等待都不能证明原任务已经结束。

真实视频生成只在页面已经确认当前 run 且 provider 集成确有需要时执行。环境检查、文档维护和测试不触发生成。
