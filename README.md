# zero-to-story / LFO

本仓库包含创作侧 Skill 资源和 LFO（Local Film Orchestrator）本地视频执行运行时。创作 Skill 负责故事、素材、Panel 和已确认的 H3 提示词；LFO 只执行当前 Panel，不做创作决策。

当前实施基线是 [`docs/plans/2026-09-05-simple-panel-execution-plan.md`](docs/plans/2026-09-05-simple-panel-execution-plan.md)：

- 一个 Panel 对应一个执行包中的一个 Clip；
- 每个 Panel 作为独立的短生命周期执行单元，严格串行同步调用官方 ComfyUI/comfy-cli；
- 执行前锁定用户批准的 package 完整文件字节 SHA-256（exact file SHA-256）；
- ComfyUI 或最小 QC 失败立即停止，不自动重试、不保留失败候选、不做复杂恢复；
- 调用方在 `ACCEPT` 后按下游需要提取真实末帧，作为下一 Panel 的真实接力输入；
- 所有 Panel `ACCEPT` 后只做一次最终 assembly。

## 快速开始

```powershell
python -m pip install -e ".[dev]"
python -m lfo.cli.main validate path/to/panel-P001.execution-package.json
python -m lfo.cli.main execute path/to/panel-P001.execution-package.json --approved-sha256 <approved-sha256>
```

`validate` 成功时返回 `package_sha256`；用户确认该值后，再把它传给 `execute`。`plan` 仅用于需要时查看后端、工作流和产物位置，不是执行前置步骤。

所有 Panel package 和最终 assembly package 都直接位于 `workspace/projects/<project_id>/` 项目根目录，并使用唯一文件名；不要放进 Panel 子目录，否则 `outputs/<run_id>/...` 无法用包内相对 URI 稳定引用。

项目没有 `lfo` console entry point；始终使用 `python -m lfo.cli.main`。本地 ComfyUI 设置和检查见 [`docs/local-windows.md`](docs/local-windows.md)，完整 CLI 见 [`docs/cli-guide.md`](docs/cli-guide.md)，公共 package 字段见 [`docs/package-v1-reference.md`](docs/package-v1-reference.md)。

源码位于 `src/lfo/`，测试位于 `tests/`，用户视频与素材位于 `workspace/`；不要把用户数据目录当作临时目录。

本次实施的检查结果和真机验收限制见[全流程复查记录](docs/plans/2026-09-05-full-flow-verification.md)。
