# Windows 新电脑使用

目标是从干净 Git 仓库获取本项目，在 Windows 上按提醒准备依赖后使用。无需复制旧电脑的 Canvas 数据库、ComfyUI 用户数据、小说、故事、媒体、运行记录、凭据或虚拟环境；新环境从空画布开始。不提供私有数据搬迁或环境复现流程，macOS/Linux 不作为本指南的验证目标。

## 先检查，再自行准备

在项目根运行，无需先安装 Python：

```powershell
./scripts/check_environment.ps1
```

脚本只读检查，不下载安装、不启动 ComfyUI、不调用付费服务、不迁移数据。`MISSING` 阻止画布启动；`NOTICE` 表示对应功能还需准备，不阻止其他功能。退出码 0 只表示画布基础启动条件满足，不代表所有生成能力可用。可执行文件发现、环境变量存在均不代表运行或认证成功。

缺少依赖时由用户自行安装，或用户明确授权后由 Agent 根据实际机器、官方说明和现有环境分析并执行下载、安装与配置。启动、预检或普通创作请求不自动授权安装。不得静默改系统 PATH、安装全局 Skill、修改外部 ComfyUI 或下载模型。

## 首次准备步骤

1. 准备 Python 3.12、受支持的 Node.js LTS（满足 20.19+ 或 22.12+）及 npm。前端构建后，正常打开画布不需要运行 Node 服务。
2. 准备项目独立 Python 环境和依赖。下面是用户主动选择执行的安装命令，预检和启动不会调用它：

   ```powershell
   ./scripts/bootstrap_dev.ps1
   ```

   也可由获授权的 Agent 创建 `.venv` 并安装 `.[canvas]`；开发检查额外使用 `.[dev,canvas]`。不要复制旧机器 `.venv`。
3. 用户确认安装前端依赖后，在 `web/canvas` 运行 `npm ci`、`npm run build`，再回到项目根。
4. 重新运行预检，然后运行 `./scripts/start_canvas.ps1`。启动脚本只检查基础条件并打开画布，不补装依赖。端口冲突时可用 `-Port 8766`。

## 按功能准备

| 功能 | 所需环境与验证 |
|---|---|
| 画布编辑、保存和浏览 | 项目 Python 与构建后的页面；本机应用数据目录和项目工作区可写 |
| 对话创作和画布操作 | 宿主加载项目规则与 `.agents/skills`；MCP 宿主加载项目连接，或通过项目 Python CLI 操作。配置示例见[画布指南](canvas-guide.md) |
| 宿主图片生成 | 接手会话实际可调用图片工具；Skill 或能力选项存在不代表工具可用 |
| 本地 H3 视频 | 官方 comfy-cli、运行中的 ComfyUI、所选工作流的自定义节点及模型、FFprobe；详见[本机环境](local-windows.md)。执行服务必须能找到 CLI；配置 JSON 中的覆盖值由 adapter 检查，通用预检只检查 PATH 和环境变量覆盖 |
| 媒体检查、尾帧和后期 | FFmpeg、FFprobe；分别运行 `ffmpeg -version`、`ffprobe -version` 验证。部分工具直接使用 PATH 中的 ffprobe，完整功能应将其配置在 PATH |
| MiMo 视频理解 | `MIMO_API_KEY`、服务网络访问和可用账户；分析脚本使用 Python 标准库 |
| MiniMax 音色克隆 | `MINIMAX_API_KEY`、服务网络访问、可用账户、FFprobe 和已授权参考音频；脚本使用 Python 标准库 |
| 可选 mmx 视频 | 用户另行接入 mmx CLI、认证及 `mmx-h3-video` Skill；它不随本仓库提供，不是默认本地 H3 的前提 |
| 持续生产与验收 | 宿主的实际委派、视听检查与接续能力；按[接续指南](canvas-continuation.md)核实。普通浏览器打开画布不会自动提供这些 Agent 能力 |

Seedance 当前只是未接入选项，安装环境不能使其变成已实现功能。API 密钥是否有效、远端额度、宿主权限和所选 Comfy 工作流是否可执行，需要对应功能的实际检查；不能把本地预检通过解释为整条生产链验证通过。真实生成仍从画布确认的请求执行。

## 干净仓库边界

代码、通用工作流模板、项目 Skills、测试与公开示例随 Git 分发。`workspace/`、`.short-drama/`、数据库、`.env*`、运行日志、虚拟环境和前端安装/构建产物由忽略规则排除；Canvas 内部状态默认创建在当前电脑的应用数据目录。ComfyUI 安装、模型、账户和用户作品不属于项目代码仓。

不要为解决新电脑启动问题将私有文件加入 Git，也不要清理旧电脑资产。发布前按[仓库发布检查](open-source-release.md)检查实际跟踪文件；忽略规则不会自动移除已跟踪文件。
