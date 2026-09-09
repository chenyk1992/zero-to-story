# zero-to-story / LFO

当前新增故事创作工作空间：以一段故事或章节建立一张画布，在当前宿主的画布面板中组织角色参考、故事板、黑白分镜、提示词、图片与视频。支持分类搜索、分区、组件编辑与连线，SQLite 自动保存；点击成品可以预览媒体、查看原始参数并跳转关联资料。默认视频通过项目 Comfy Skill 执行，图片使用当前宿主实际可调用的能力。

所有生产任务先遵守[项目共享生产规则](docs/ai-system-prompt.md)；[Skill 路由](docs/ai-skill-routing.md)只说明职责边界。

从项目根启动：

```powershell
./scripts/start_canvas.ps1
```

首次使用先安装项目依赖并构建页面，步骤、对话操作和已知接入边界见 [画布使用指南](docs/canvas-guide.md)。新增 Skill 和 MCP 配置都限定在当前项目；新入口不加载旧生产数据库，不要求维护旧包或 hash 文件。

以下保留旧 LFO package CLI 入口的说明，只适用于显式调用该入口的工作。

本仓库包含创作侧 Skill 资源和 LFO（Local Film Orchestrator）本地视频执行运行时。创作 Skill 负责故事、素材、Panel 和已确认的 H3 提示词；LFO 只执行当前 Panel，不做创作决策。

旧 LFO package CLI 的公共字段与执行边界见 [`docs/package-v1-reference.md`](docs/package-v1-reference.md)：

- 一个 Panel 对应一个执行包中的一个 Clip；
- 每个 Panel 作为独立的短生命周期执行单元，严格串行同步调用官方 ComfyUI/comfy-cli；
- 执行前锁定用户批准的 package 完整文件字节 SHA-256（exact file SHA-256）；
- ComfyUI 或最小 QC 失败立即停止，不自动重试、不保留失败候选、不做复杂恢复；
- 调用方在 `ACCEPT` 后按下游需要提取真实末帧，作为下一 Panel 的真实接力输入；
- 所有 Panel `ACCEPT` 后只做一次最终 assembly。

画布普通组件按确认后的快照执行，不套用 package、hash 或 assembly 门槛；画布和 package CLI 的完整边界见共享生产规则与[画布使用指南](docs/canvas-guide.md)。技术提交成功不等于内容接受；故事生产或明确要求内容验收的媒体任务，必须依据实际视频的实际末态和实际音频证据判断。

## 快速开始

```powershell
python -m pip install -e ".[dev]"
python -m lfo.cli.main validate path/to/panel-P001.execution-package.json
python -m lfo.cli.main execute path/to/panel-P001.execution-package.json --approved-sha256 <approved-sha256>
```

`validate` 成功时返回 `package_sha256`；将它绑定到已覆盖当前包的用户授权后，再传给 `execute`。已有适用的持续授权时不重复确认；包字节变化或授权范围变化时重新核对。`plan` 仅用于需要时查看后端、工作流和产物位置，不是执行前置步骤。

所有 Panel package 和最终 assembly package 都直接位于 `workspace/projects/<project_id>/` 项目根目录，并使用唯一文件名；不要放进 Panel 子目录，否则 `outputs/<run_id>/...` 无法用包内相对 URI 稳定引用。

项目没有 `lfo` console entry point；始终使用 `python -m lfo.cli.main`。本地 ComfyUI 设置和检查见 [`docs/local-windows.md`](docs/local-windows.md)，完整 CLI 见 [`docs/cli-guide.md`](docs/cli-guide.md)，公共 package 字段见 [`docs/package-v1-reference.md`](docs/package-v1-reference.md)。

源码位于 `src/lfo/`，测试位于 `tests/`，用户视频与素材位于 `workspace/`；不要把用户数据目录当作临时目录。
