# AGENTS.md

LFO — Local Film Orchestrator. 本地视频实施运行时。上游 Creative Skill 负责故事、角色图、黑白分镜、Panel/Clip 提示词与用户审批，并交付 `lfo.video-execution.v1`；LFO 只负责素材导入、后端选择、MiniMax H3/ComfyUI 视频生成、标准化、QC、音频、字幕、时间线、导出、重试与恢复。核心不得生成故事、图片或创作决策。

## Setup commands

- Install deps: `pip install -e ".[dev]"` (editable install with dev extras)
- Run CLI: `python -m lfo.cli.main <command>` (or `set PYTHONPATH=src` first, or `pip install -e .`)
- Run all tests: `python -m pytest tests/ -v`
- Run single module tests: `python -m pytest tests/test_runtime.py -v`
- Run live Package E2E (requires ComfyUI at :8188): `python scripts/live_e2e_execution_package.py execution-package.json --approve`
- Bootstrap environment (one-time after ComfyUI install/reinstall): `python -m lfo.cli.main setup --machine-id local-windows`
- Doctor check: `python -m lfo.cli.main doctor --machine-id local-windows`
- Preflight check: `python -m lfo.cli.main preflight --machine-id local-windows`

## ComfyUI environment

- Local ComfyUI is `D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI` (ComfyUI Desktop, 0.30.2, Electron + bundled Python 3.12).
- `comfy-cli` 1.13.0 is installed in the system Python; default workspace is set to the path above.
- All models live under `D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\models\` (no separate `D:\cyuiEnv\models\`).
- H3 model set: `minimax_h3_fl2va_pruned_int8_convrot.safetensors`, `minimax_h3_ref2va_pruned_int8_convrot.safetensors`, `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, `minimax_h3_video_vae_fp16.safetensors`, `minimax_h3_audio_vae_fp32.safetensors`.
- LFO machine profile: `%APPDATA%\LFO\machines\local-windows.json`. Re-run `python -m lfo.cli.main setup --machine-id local-windows` after any ComfyUI path change.

## Project layout

src layout — all system code lives under `src/lfo/`, user data under `workspace/` (gitignored).

- `src/lfo/cli/` — argparse CLI 入口。`main.py` 分发，`registry.py` 注册，各 `*_cmd.py` 对应子命令
- `src/lfo/contracts/` — `VideoExecutionPackage` 公共契约、Schema 与 Builder SDK
- `src/lfo/assets/` — 路径安全、媒体探测、内容寻址存储与素材导入
- `src/lfo/backends/` — 能力 Manifest、选择器与真实 ComfyUI H3 Handler
- `src/lfo/execution/` — SQLite Store、物化快照、任务 DAG、持久化 Runtime、恢复与失效
- `src/lfo/media/` — FFmpeg 标准化/QC/音频/字幕/时间线/原子导出
- `src/lfo/skill_adapter/` — 上游 Skill 到公共执行包的纯转换适配器
- `src/lfo/comfy/` — ComfyUI 交互层。`client.py`、`workflow.py`、`submit.py`、`monitor.py` 等
- `src/lfo/config/` — 4 层配置合并
- `src/lfo/environment/` — 环境发现与校验
- `src/lfo/application/` — `VideoRuntime` Facade 与运行报告
- `src/lfo/registry/` — 捆绑的工作流 manifest（t2v/i2v/r2v JSON）
- `workspace/` — 用户数据（gitignored）。`novels/`、`projects/`、`db/`、`ref_images/`、`spikes/`
- `scripts/` — Live E2E 脚本
- `tests/` — pytest 测试套件（按模块分子目录）
- `.agents/skills/zero-to-story/assets/` — zero-to-story 可复用项目骨架与生成 Prompt（与 Skill 一起维护，git-tracked）

## Code style

- Python 3.12，`from __future__ import annotations` 在所有模块中使用
- 类型标注为主（项目有 mypy 意图但无配置）
- 命名：snake_case 函数/变量，PascalCase 类，UPPER_CONST
- 错误处理：自定义异常层次（`comfy/exceptions.py`），CAS 状态转换用 `rowcount` 验证
- 时间戳统一 UTC ISO 8601
- 不写死代码：发现更好的方法直接用，及时清理废弃逻辑

## Testing

- Framework: pytest（无配置文件，直接从项目根运行）
- 测试结构：`tests/test_<module>.py` 单元测试 + `tests/test_<module>/` 子目录分组
- 共享 fixtures：`tests/conftest.py` 含 `isolate_process_state`（自动隔离 env vars 和 cwd）
- Live E2E：`scripts/live_e2e_execution_package.py`（需本地 ComfyUI，时长取决于 Package）
- 新增功能必须带测试；所有测试通过才能合并

## CLI commands

```
lfo validate <execution-package.json>
lfo plan <execution-package.json>
lfo execute <execution-package.json> --approve
lfo status <run_id>
lfo retry <run_id> [--clip-id <clip_id>]
lfo cancel <run_id>
lfo review <run_id> <target> approved|rejected
lfo export <run_id>
lfo doctor                  # 全量环境校验
lfo preflight               # 子集预检
lfo setup                   # 初始化环境
```

## Architecture notes

- **公共边界**：Skill 只能写 `VideoExecutionPackage` 和素材文件；不得操作数据库、ComfyUI 节点或内部素材 ID
- **包导入**：从 `lfo` 包导入，`tests/conftest.py` 自动注入 `src/` 到 `sys.path`
- **SQLite 运行时**：WAL 模式，CAS 状态机，`rowcount` 不用 `total_changes`
- **工作流 hash**：LFO-WFJ1 规范（float 归一化 + NFC + SHA-256），算法标识 `lfo-wfj1-sha256-v1`
- **三级验证**：STATIC_VALID → RUNTIME_COMPATIBLE → SMOKE_TESTED
- **ComfyUI**：本地 `http://127.0.0.1:8188`，RTX 5080 16GB，fl2va int8 路径
- **素材导入**：Package 相对路径在导入时解析；之后只读取 CAS 内不可变副本
- **产物布局**：所有新 Run 的中间/最终媒体必须使用 `RunArtifactLayout` 写入
  `workspace/projects/<project_id>/outputs/<run_id>/` 和
  `workspace/projects/<project_id>/final/<output.directory>/`；不得创建 workspace 根部
  的 `runs` 或 `exports` 目录。ComfyUI 输出仅作提供方缓存，必须复制到项目 Run 目录后
  才记录为 LFO artifact。
- **Video execution**：每个 `clips[]` 是可独立重做的执行单元；创作侧可将 PanelPack 映射为 Clip，但 Runtime 不理解故事板语义

## PR & commit conventions

- Branch from `master`; never push to it directly
- Commit message: conventional commits (`feat:` / `fix:` / `docs:` / `refactor:` / `test:`)
- CI green before merge

## Security

- No `.env` committed (add to `.gitignore` if not present)
- API keys / credentials in config, never in code or logs
- SQLite DB paths resolved via config layer, not hardcoded
