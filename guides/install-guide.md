# 新环境安装与模型准备指南

本指南**仅用于指导新用户或获用户明确授权的 AI 助手**完成一台新电脑（当前以 Windows 11 / PowerShell 为验证目标）所需的软件、项目依赖、MCP 连接、ComfyUI 自定义节点和模型文件的安装、下载与就绪验证。

- 不包含创作流程、提示词写法或故障恢复，相关规则见 [项目共享生产规则](ai-system-prompt.md)、[画布使用指南](canvas-guide.md) 与 [本机环境](local-windows.md)。
- 干净仓库边界与不迁移旧电脑私有数据的原则见 [Windows 使用指南](windows-setup.md)。

---

## 一、给 AI 助手的执行入口与边界

如果你想直接让 AI 助手帮你完成新环境搭建，可以把下面这段话发给它：

```text
请阅读 guides/install-guide.md，帮我准备当前项目的运行环境。
我计划启用以下层级：[例如：L1 + L2 + L3 + L4 中的 H3 视频与 Qwen 图片]（未列出的先不装）。
请先执行只读预检，列出当前机器缺少的软件、依赖、自定义节点、模型文件及目标路径，
待我确认后再按步骤下载、安装并逐项验证。不要触发任何真实生成，不要修改 Git 跟踪文件。
```

AI 助手执行本指南时必须遵守：

1. **先只读预检，再确认安装**：先运行 `./scripts/check_environment.ps1` 核查现状，向用户汇报缺口与预计磁盘占用，取得明确同意后再下载或安装。
2. **不破坏现有环境**：不静默覆盖已有 `.venv`、不修改外部 ComfyUI 核心代码、不安装全局 Skill、不静默改写系统 `PATH`。
3. **不把本机配置和资产纳入 Git**：`.lfo/comfy-mcp.json`、`.codex/config.toml`、`.env*`、模型权重和 `workspace/` 均属本机私有或忽略范围，严禁提交。
4. **文件名与子目录必须精确匹配**：ComfyUI 执行器在提交前会按精确文件名与 `models/` 子目录预检，不得擅自改名或替换成未验证的量化版本。
5. **安装验证不等于生成验证**：验证命令只确认软件可执行、画布可启动、节点与模型可被发现，不得在安装流程中自动提交真实图片/视频/音频生成。

---

## 二、分层选装总览（按需安装）

不必一次性下载所有模型。按你打算使用的功能从上到下选装即可：

| 层级 | 适用场景 | 核心内容 |
|---|---|---|
| **L1 基础画布（必装）** | 启动画布、编辑/保存项目、纯剧本/分镜/文案创作 | Git、Python 3.12+、Node.js LTS（20.19+ 或 22.12+）、项目 `.venv`、画布前端构建 |
| **L2 剪辑与 MCP（推荐）** | AI 直接读写画布、媒体信息探测、成片剪辑合并 | FFmpeg / FFprobe、宿主 `story_canvas` MCP 配置、可选 `[audio]` 分析依赖 |
| **L3 本地 ComfyUI 底座** | 使用任意本地 Comfy 媒体能力的前置条件 | ComfyUI、官方 `comfy-cli`、隔离安装的官方 `comfy-mcp`、`.lfo/comfy-mcp.json` |
| **L4 Comfy 节点与模型** | 本地 H3 视频 / Qwen 图片 / H3 图片 / Qwen3-TTS / Music 3 / YuE2 / 人声分离 / SeedVR2 超分 | 按需安装对应自定义节点，并将精确文件名的模型放入 `ComfyUI/models/` 对应子目录 |
| **L5 可选外部 API 与扩展工具** | MiMo 视听理解与盲审、MiniMax 音色克隆、热点雷达、画术动效 | 对应环境变量（`MIMO_API_KEY` / `MINIMAX_API_KEY` 等）与少量独立可选工具 |

---

## 三、L1 基础环境与画布必装

### 1. 基础软件要求

| 软件 | 版本要求 | 验证命令 | 安装建议 |
|---|---|---|---|
| **Git** | 任意近期版本 | `git --version` | 官网安装包或用户同意后 `winget install Git.Git` |
| **Python** | **3.12+**（需含 `venv` 与 `ensurepip`） | `python --version` | 官网安装包（勾选 Add to PATH）或 `winget install Python.Python.3.12` |
| **Node.js & npm** | LTS **20.19+** 或 **22.12+**（含更高主版本） | `node -v` / `npm -v` | 官网 LTS 安装包或 `winget install OpenJS.NodeJS.LTS` |

### 2. 获取代码并执行只读预检

```powershell
git clone <仓库地址> zero-to-story
cd zero-to-story
./scripts/check_environment.ps1
```

`[MISSING]` 表示阻止画布启动的必装缺口；`[NOTICE]` 表示可选功能未就绪。

### 3. 安装项目 Python 隔离环境

**推荐（包含运行 + 开发校验依赖 `[dev,canvas]`）**：

```powershell
./scripts/bootstrap_dev.ps1
```

如系统默认 `python` 不是 3.12+，可显式指定解释器：

```powershell
./scripts/bootstrap_dev.ps1 -Python "C:\Path\To\Python312\python.exe"
```

若仅需运行画布而不跑开发测试，也可以手工创建隔离环境并安装最小依赖：

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[canvas]"
```

> 请勿从旧电脑直接复制 `.venv` 目录。

### 4. 构建画布前端页面

前端构建完成后，日常使用画布不再需要运行 Node 开发服务器：

```powershell
cd web/canvas
npm ci
npm run build
cd ../..
```

### 5. 启动画布验证 L1 就绪

```powershell
./scripts/check_environment.ps1 -StartupOnly
./scripts/start_canvas.ps1
```

正常情况下会自动打开本机画布（默认 `http://127.0.0.1:8765`）。

---

## 四、L2 视听剪辑与宿主 MCP 接入

### 1. 安装 FFmpeg 与 FFprobe

视频/音频探测、尾帧提取、TTS 变速交付、字幕压制与成片合并都依赖 **FFmpeg** 和 **FFprobe**。

- 安装方式：下载 Windows 静态构建版并把 `bin` 目录加入系统 `PATH`，或经用户同意后使用 `winget install Gyan.FFmpeg`。
- 若不便改系统 `PATH`，可通过环境变量 `LFO_FFMPEG` 与 `LFO_FFPROBE` 指向各自可执行文件绝对路径（注意部分脚本和工具默认从 `PATH` 调用 `ffprobe`，完整功能仍建议加入 `PATH`）。
- 验证：

```powershell
ffmpeg -version
ffprobe -version
```

### 2. 可选音频分析增强包（按需）

仅当需要更精细的音乐节拍/能量分析时，在项目 `.venv` 中追加安装 `audio` 扩展（包含 `librosa` 与 `numpy`）：

```powershell
./.venv/Scripts/python.exe -m pip install -e ".[audio]"
```

### 3. 在 AI 宿主中接入画布 MCP（`story_canvas`）

项目 Skills 位于 `.agents/skills/`，在支持项目级 Skills 的 AI 宿主中直接打开仓库根目录即可被发现，无需复制到全局目录。

支持 MCP 的宿主可将 `story_canvas` 指向本项目 `.venv` 解释器。以 Codex 项目级配置 `.codex/config.toml` 为例（该文件含本机路径，不随 Git 提交；请将路径替换为你的实际项目目录）：

```toml
[mcp_servers.story_canvas]
command = 'C:\path\to\zero-to-story\.venv\Scripts\python.exe'
args = ["-m", "lfo.canvas", "mcp"]
cwd = 'C:\path\to\zero-to-story'
```

其他支持 MCP 的客户端按各自格式填写相同的 `command`、`args` 和 `cwd`。没有 MCP 的环境也可直接通过 `./.venv/Scripts/python.exe -m lfo.canvas call ...` 操作同一画布服务。详见 [画布使用指南](canvas-guide.md)。

---

## 五、L3 本地 ComfyUI 与官方本地 Comfy MCP 底座

如果你需要使用任何本地图片、视频、配音、音乐、翻唱、人声分离或超分能力，需要准备以下 4 项。

### 1. 安装 ComfyUI

- 安装 **ComfyUI Desktop** 或 **独立版 ComfyUI**（建议使用近期更新版本，以内置原生 MiniMax H3 Video / H3 Image / Qwen Image 2.1 / MiniMax Music 3 / YuE2 / SheetSage2 / SeedVR2 节点）。
- 确认显卡驱动与 PyTorch CUDA 环境正常，且 ComfyUI 在本机回环地址提供服务（默认 `http://127.0.0.1:8188`）。

### 2. 安装官方 `comfy-cli`

官方 `comfy-mcp` 内部会调用 `comfy-cli`。先在系统 Python 或独立工具环境中安装它，并记下 `comfy.exe` 的完整路径：

```powershell
pip install comfy-cli
comfy --version
(Get-Command comfy).Source
```

### 3. 在项目隔离环境中安装官方 `comfy-mcp`

按 [Comfy 官方本地 MCP 指南](https://docs.comfy.org/agent-tools/mcp.md#local-comfy-mcp-connection)，推荐将 `comfy-mcp` 隔离安装到项目的 `.venv/comfy-mcp/` 目录，避免与画布主环境依赖冲突：

```powershell
python -m venv .venv/comfy-mcp
./.venv/comfy-mcp/Scripts/python.exe -m pip install comfy-mcp
./.venv/comfy-mcp/Scripts/comfy-mcp.exe --help
```

### 4. 创建本机专用 `.lfo/comfy-mcp.json`

在项目根目录创建 `.lfo/comfy-mcp.json`（已被 `.gitignore` 忽略），将以下路径替换为当前电脑的实际路径：

```json
{
  "comfy_mcp": {
    "url": "http://127.0.0.1:8188",
    "command": "C:/path/to/zero-to-story/.venv/comfy-mcp/Scripts/comfy-mcp.exe",
    "comfy_bin": "C:/path/to/Scripts/comfy.exe",
    "timeout_seconds": 7200
  }
}
```

可选补充字段：
- `model_venv`：若希望画布在本地 ComfyUI 离线时自动用既有模型 Python 环境拉起服务，且该环境不在默认探测位置（ComfyUI 目录下的 `.venv`、`venv` 或 Desktop 旁的 `standalone-env`），可在此指定其目录路径（也可通过环境变量 `LFO_COMFY_MCP_MODEL_VENV` 指定）。
- 目标 `url` 仅允许本机回环 HTTP 地址（如 `http://127.0.0.1:8188`）。

验证画布能否正确发现 Comfy MCP 配置：

```powershell
./.venv/Scripts/python.exe -c "from lfo.comfy.transport import load_runtime_config; print(load_runtime_config())"
```

---

## 六、L4 ComfyUI 自定义节点与模型下载清单（按需选装）

下表汇总所有本地 Comfy 能力对应的节点来源与模型目录。**只安装和下载你打算使用的能力即可**；模型文件必须放进 ComfyUI 对应的 `models/<子目录>/` 下（或通过 ComfyUI `extra_model_paths.yaml` 映射到对应模型类型目录），并保持**完全一致的文件名**。

> 注意：执行器每次提交前都会通过 Comfy MCP 预检实时节点和模型文件名，缺失时会直接报错停止，不会静默替你下载或替换模型。自定义节点安装到 `<ComfyUI>/custom_nodes/` 后，需在其所使用的 ComfyUI Python 环境中安装对应 `requirements.txt` / 依赖并重启 ComfyUI。

### 能力总览

| 能力 | 画布 Provider | 节点来源 | 所需模型子目录 | 专项说明 |
|---|---|---|---|---|
| 本地 H3 视频（原生） | `comfy-h3` (`native`) | ComfyUI 原生节点 | `diffusion_models/`、`text_encoders/`、`vae/` | [工作流约定](workflow-conventions.md) |
| 本地 H3 视频（VDN8 加速） | `comfy-h3` (`vdn_turbo`) | 原生 + `ComfyUI-VDN-H3` | 同上 + `vdn/stage-dmd-step-250/` | [VDN8 指南](h3-vdn8.md) |
| 本地 Qwen 图片 | `comfy-qwen-image` | ComfyUI 原生节点 | `diffusion_models/`、`text_encoders/`、`vae/` | [Qwen 图片指南](qwen-image.md) |
| 本地 H3 图片 | `comfy-h3-image` | ComfyUI 原生节点 | `diffusion_models/`、`text_encoders/`、`vae/` | [H3 图片指南](h3-image.md) |
| 本地 Qwen3-TTS 配音/克隆 | `comfy-qwen-tts` | 自定义节点 `ComfyUI-Qwen-TTS` | `qwen-tts/` | [Canvas TTS](canvas-tts.md) |
| 本地 Music 3 音乐/器乐 | `comfy-minimax-music` | ComfyUI 原生节点 | `diffusion_models/`、`text_encoders/`、`vae/` | [Canvas Music](canvas-music.md) |
| 本地 YuE2 旋律翻唱 | `comfy-yue2-music` | ComfyUI 原生节点 | `checkpoints/`、`audio_encoders/` | [YuE2 Skill](../.agents/skills/comfy-yue2-executor/SKILL.md) |
| 本地人声与伴奏分离 | `comfy-singing` | 自定义节点 `ComfyUI-MelBandRoFormer` | `diffusion_models/` | [分离 Skill](../.agents/skills/comfy-singing-executor/SKILL.md) |
| 本地 SeedVR2 视频超分 | `comfy-upscale` | 原生 SeedVR2 + 配套有界分窗节点 | `diffusion_models/`、`vae/` | [超分 Skill](../.agents/skills/comfy-upscale-executor/SKILL.md) |

---

### 1. 本地 MiniMax H3 视频（`comfy-h3`）

- **原生节点**：依赖新版 ComfyUI 内置的 `MiniMaxH3ImageToVideo`、`MiniMaxH3ReferenceToVideo`、`MiniMaxH3SigmaShift`、`ResolutionSelector`、`ComfyMathExpression` 等节点。
- **可选加速节点（启用 `vdn_turbo` 8 步模式时必装）**：
  - 仓库：[`ComfyUI-VDN-H3`](https://github.com/Saganaki22/ComfyUI-VDN-H3)（要求 **1.5.2 或更高版本**，提供 `ApplyVDNH3` 节点）。
  - 安装到 `<ComfyUI>/custom_nodes/comfyui-vdn-h3`。
- **模型文件清单**：

| ComfyUI 目录 | 精确文件名 / 目录名 | 用途 |
|---|---|---|
| `models/diffusion_models/` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 文生/图生/首尾帧视频（T2VA / I2VA / FL2VA） |
| `models/diffusion_models/` | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 多参考生视频（Ref2VA / R2V） |
| `models/text_encoders/` | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | H3 视频文本/多模态编码器（`type=minimax`） |
| `models/vae/` | `minimax_h3_video_vae_fp16.safetensors` | H3 视频 VAE |
| `models/vae/` | `minimax_h3_audio_vae_fp32.safetensors` | H3 音频 VAE |
| `models/vdn/` | `stage-dmd-step-250/`（完整 bundle 目录） | 仅 `vdn_turbo` 8 步加速需要；权重见 [OpenVDN/vdn-minimax-h3](https://huggingface.co/OpenVDN/vdn-minimax-h3) |

> 使用 VDN-H3 权重前请自行核对上游的 MiniMax H3 社区许可及适用地域说明。

---

### 2. 本地图片：Qwen Image 2.1（`comfy-qwen-image`）

- **节点**：ComfyUI 原生 Qwen Image 2.1 节点（`TextEncodeQwenImage21` 等），无需额外第三方自定义节点。
- **参考来源**：[Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1)、[Comfy-Org/workflow_templates](https://github.com/Comfy-Org/workflow_templates)。
- **模型文件清单**：

| ComfyUI 目录 | 精确文件名 | 用途 |
|---|---|---|
| `models/diffusion_models/` | `qwen_image_2.1_int8_convrot.safetensors` | Qwen Image 2.1 主模型 |
| `models/text_encoders/` | `qwen3vl_8b_int8_convrot.safetensors` | 文本/视觉编码器（`type=qwen_image`） |
| `models/vae/` | `qwen_image_2.1_vae_bf16.safetensors` | Qwen Image 2.1 VAE |

---

### 3. 本地图片：MiniMax H3 Image（`comfy-h3-image`）

- **节点**：ComfyUI 原生 H3 Image 节点（`MiniMaxH3ImageConditioning`），无需额外第三方自定义节点。
- **模型文件清单**：

| ComfyUI 目录 | 精确文件名 | 用途 |
|---|---|---|
| `models/diffusion_models/` | `minimax_h3_image_pruned_int8_convrot.safetensors` | MiniMax H3 Image 主模型 |
| `models/text_encoders/` | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 文本/视觉编码器（`type=minimax`） |
| `models/vae/` | `minimax_h3_image_vae_fp16.safetensors` | MiniMax H3 Image 专用 VAE |

---

### 4. 本地 Qwen3-TTS 配音 / 声音设计 / 音色克隆（`comfy-qwen-tts`）

- **自定义节点（必装）**：[`ComfyUI-Qwen-TTS`](https://github.com/flybirdxx/ComfyUI-Qwen-TTS)（提供 `FB_Qwen3TTSCustomVoice`、`FB_Qwen3TTSVoiceDesign`、`FB_Qwen3TTSVoiceClone`）。
  - 在 ComfyUI 所用 Python 环境中安装其依赖；注意上游要求 `transformers==4.57.3` 或 `transformers>=5.0`。
- **模型目录清单**（全部放在 `models/qwen-tts/` 下）：

| ComfyUI 目录 | 精确目录名 | 适用模式 |
|---|---|---|
| `models/qwen-tts/` | `Qwen3-TTS-Tokenizer-12Hz/` | **三种模式均必装**（独立 Tokenizer 目录） |
| `models/qwen-tts/` | `Qwen3-TTS-12Hz-1.7B-CustomVoice/` | 预置多语言音色（`tts`） |
| `models/qwen-tts/` | `Qwen3-TTS-12Hz-1.7B-VoiceDesign/` | 文本声音设计（`design`） |
| `models/qwen-tts/` | `Qwen3-TTS-12Hz-1.7B-Base/` | 参考音频音色克隆（`clone`） |

每个 1.7B 模型目录内部须包含完整文件，执行器会预检以下全部文件，缺一不可：
`config.json`、`generation_config.json`、`model.safetensors`、`tokenizer_config.json`、`vocab.json`、`merges.txt`、`preprocessor_config.json`、`speech_tokenizer/config.json`、`speech_tokenizer/model.safetensors`、`speech_tokenizer/preprocessor_config.json`。

---

### 5. 本地 MiniMax Music 3 歌曲与器乐（`comfy-minimax-music`）

- **节点**：ComfyUI 原生节点（`MiniMaxMusic3TextEncode`、`EmptyMiniMaxMusic3LatentAudio`）。
- **模型文件清单**：

| ComfyUI 目录 | 精确文件名 | 用途 |
|---|---|---|
| `models/diffusion_models/` | `minimax_music3_dit_fp16.safetensors` | Music 3 DiT 主模型 |
| `models/text_encoders/` | `minimax_music3_text_encoder_pruned_int8_convrot.safetensors` | Music 3 文本编码器（`type=minimax`） |
| `models/vae/` | `minimax_music3_dav.safetensors` | Music 3 音频 VAE |

---

### 6. 本地 YuE2 旋律翻唱（`comfy-yue2-music`）

- **节点**：ComfyUI 原生节点（`YuE2GenerateMusic`、`EmptyYuE2LatentAudio`、`SheetSage2AudioToABC`、`AudioEncoderLoader`）。
- **参考来源**：[Comfy-Org/YuE2](https://huggingface.co/Comfy-Org/YuE2)（注意权重采用 **CC BY-NC 4.0**，商用须另行核实许可）。
- **模型文件清单**：

| ComfyUI 目录 | 精确文件名 | 用途 |
|---|---|---|
| `models/checkpoints/` | `yue2_3b_int8_convrot.safetensors` | YuE2 3B 主检查点 |
| `models/audio_encoders/` | `sheetsage2_bf16.safetensors` | SheetSage2 旋律提取音频编码器 |

---

### 7. 本地 MelBandRoFormer 人声与伴奏分离（`comfy-singing`）

- **自定义节点（必装）**：[`ComfyUI-MelBandRoFormer`](https://github.com/kijai/ComfyUI-MelBandRoFormer)（提供 `MelBandRoFormerModelLoader`、`MelBandRoFormerSampler`）。
- **模型文件清单**：

| ComfyUI 目录 | 精确文件名 | 用途 |
|---|---|---|
| `models/diffusion_models/` | `MelBandRoformer_fp16.safetensors` | 默认人声/伴奏分离权重 |

---

### 8. 本地 SeedVR2 3B INT8 视频超分（`comfy-upscale`）

- **模型文件清单**：

| ComfyUI 目录 | 精确文件名 | 用途 |
|---|---|---|
| `models/diffusion_models/` | `seedvr2_3b_int8_convrot.safetensors` | SeedVR2 3B INT8 主模型 |
| `models/vae/` | `seedvr2_ema_vae_fp16.safetensors` | SeedVR2 EMA VAE |

- **节点说明**：除 ComfyUI 原生 SeedVR2 节点外，该项目超分工作流当前依赖配套有界分窗自定义节点 `CanvasSeedVR2BoundedUpscale`（该节点暂未随本公开仓库自动分发）。新环境如暂未安装该自定义节点，仅影响本地超分功能，不影响画布与 H3 视频主链路。

---

## 七、L5 可选外部 API、扩展 Skill 与工具

以下能力完全按需配置，不配置不影响本地画布与 ComfyUI 链路：

| 功能 / Skill | 所需配置或工具 | 说明 |
|---|---|---|
| **MiMo 视听理解 / 成片盲审**<br>（`mimo-video-understanding`、`zero-to-story` 盲审） | 环境变量 `MIMO_API_KEY`<br>（可选 `MIMO_VIDEO_BASE_URL`、`MIMO_AUDIO_BASE_URL`） | 仅使用 Python 标准库；默认接口 `https://api.xiaomimimo.com/v1/chat/completions` |
| **MiniMax 在线音色克隆**<br>（`voice-clone`） | 环境变量 `MINIMAX_API_KEY`<br>（可选 `MINIMAX_API_BASE_URL`）+ FFprobe | 仅使用 Python 标准库；上传克隆前须具备明确说话人授权 |
| **热点采集与选题雷达**<br>（`hot-collect`、`topic-scout`） | 基础功能仅需 Python 标准库；可选 `LFO_HOTSPOT_DATA` | 仅在启用 TikTok 对标语料面时需 `pip install pyarrow pandas`；可用 `hot-collect/scripts/doctor.py` 自检 |
| **画术动效渲染**<br>（`huashu-art-motion`） | `uv`、Playwright（`uv run --with playwright ...`）与 FFmpeg | 仅做编程/参数化动效渲染时需要 |
| **宿主自带图片工具 / 外部 `mmx` CLI** | 由当前 AI 宿主或用户另行安装认证 | 不随本仓库分发；`Seedance` 当前为未接入占位选项 |

---

## 八、常用环境变量速查

| 环境变量 | 作用 | 是否必填 |
|---|---|---|
| `LFO_COMFY_MCP_URL` | 覆盖 `.lfo/comfy-mcp.json` 中的本机 ComfyUI 地址 | 否 |
| `LFO_COMFY_MCP_COMMAND` | 覆盖 `comfy-mcp.exe` 路径 | 否 |
| `LFO_COMFY_MCP_COMFY_BIN` | 覆盖 `comfy.exe` 路径 | 否 |
| `LFO_COMFY_MCP_MODEL_VENV` | 指定离线拉起 ComfyUI 时使用的模型 Python 虚拟环境 | 否 |
| `LFO_COMFY_MCP_TIMEOUT` | Comfy MCP 单次调用超时秒数（默认 `7200`） | 否 |
| `LFO_FFMPEG` / `LFO_FFPROBE` | 指定 `ffmpeg` / `ffprobe` 可执行文件路径 | 否（在 `PATH` 中时无需设置） |
| `LFO_CANVAS_DATA` | 指定画布应用数据目录（默认本机 AppData） | 否 |
| `LFO_WORKSPACE` | 指定项目媒体工作区目录（默认仓库内 `workspace/`） | 否 |
| `LFO_VIDEO_STATE` | 指定本机视频串行锁与持久回执目录 | 否 |
| `MIMO_API_KEY` | MiMo 音频/视频理解 API 密钥 | 否（仅用 MiMo 时填） |
| `MINIMAX_API_KEY` | MiniMax 在线音色克隆 API 密钥 | 否（仅用音色克隆时填） |

---

## 九、安装完成验收清单

按已安装的层级运行以下只读检查命令，全部通过即可开始使用：

```powershell
# 1. 项目基础环境与可选工具只读预检（L1 / L2 / L3 / L5）
./scripts/check_environment.ps1

# 2. 仓库 Skills、指南与本地链接校验
./.venv/Scripts/python.exe scripts/validate_ai_config.py

# 3. 媒体工具可执行性（L2）
ffmpeg -version
ffprobe -version

# 4. 本机视频准入与 Comfy MCP 状态只读检查（L3）
./.venv/Scripts/python.exe -m lfo.comfy.admission

# 5. 启动画布并确认页面可访问（L1）
./scripts/start_canvas.ps1
```

> **提醒**：上述检查通过仅证明环境与配置就绪；各 Comfy 能力的实际模型与自定义节点会在对应工作流首次预检时由 Comfy MCP 实时核对，API 密钥的有效性与额度需在实际调用该功能时确认。
