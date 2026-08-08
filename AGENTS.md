# AGENTS.md

LFO — Local Film Orchestrator. 本地 AI 影视生成编排系统：从创意/剧本输入到 Storyboard 审批、任务 DAG 规划、ComfyUI 生图、MiniMax H3 视频生成（T2V/I2V/首尾帧/R2V）、跨镜头连续性、裁剪标准化、拼接字幕导出。支持局部修改、版本审批、失败重试、崩溃恢复和幂等提交。

## Setup commands

- Install deps: `pip install -e ".[dev]"` (editable install with dev extras)
- Run CLI: `python -m lfo.cli.main <command>` (or `set PYTHONPATH=src` first, or `pip install -e .`)
- Run all tests: `python -m pytest tests/ -v`
- Run single module tests: `python -m pytest tests/test_runtime.py -v`
- Run live E2E (requires ComfyUI at :8188): `python scripts/live_e2e_3shot.py`
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
- `src/lfo/core/` — 运行时内核。`database.py`、`runtime.py`、`workflow_registry.py`、`state_machine.py`、`hashing.py`、`canonical.py`、`recovery.py`、`invalidation.py`
- `src/lfo/services/` — 业务服务层。`pipeline_service.py`、`storyboard_graph_service.py`、`workspace.py` 等
- `src/lfo/visual/` — Provider-Agnostic Visual Production Mode 领域模块
- `src/lfo/storyboard/` — 数据链。`intake.py`、`storyboard.py`、`draft.py`、`render.py`、`validate.py`
- `src/lfo/comfy/` — ComfyUI 交互层。`client.py`、`workflow.py`、`submit.py`、`monitor.py` 等
- `src/lfo/config/` — 4 层配置合并
- `src/lfo/environment/` — 环境发现与校验
- `src/lfo/planning/` — 镜头规划。`dag.py`、`validator.py`、`workflow_selector.py` 等
- `src/lfo/application/` — 应用服务
- `src/lfo/visual_bible/` — Visual Bible hashing/schema/validate
- `src/lfo/rendering/` — Markdown 渲染
- `src/lfo/registry/` — 捆绑的工作流 manifest（t2v/i2v/r2v JSON）
- `workspace/` — 用户数据（gitignored）。`novels/`、`projects/`、`db/`、`ref_images/`、`spikes/`
- `scripts/` — Live E2E 脚本
- `tests/` — pytest 测试套件（按模块分子目录）
- `templates/` — 用户可复用的模板文件（git-tracked）

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
- Live E2E：`scripts/live_e2e_3shot.py`（需本地 ComfyUI，~20min）
- 新增功能必须带测试；所有测试通过才能合并

## CLI commands

```
lfo run <storyboard.json>   # 执行完整管线
lfo status <project_id>     # 查看管线进度
lfo doctor                  # 全量环境校验
lfo preflight               # 子集预检
lfo setup                   # 初始化环境
lfo machine                 # 机器配置管理
lfo workflow                # 工作流管理
lfo config                  # 配置查看/修改
```

## Architecture notes

- **包导入**：从 `lfo` 包导入（`from lfo.core.database import ...`），`tests/conftest.py` 自动注入 `src/` 到 `sys.path`
- **SQLite 运行时**：WAL 模式，CAS 状态机，`rowcount` 不用 `total_changes`
- **工作流 hash**：LFO-WFJ1 规范（float 归一化 + NFC + SHA-256），算法标识 `lfo-wfj1-sha256-v1`
- **三级验证**：STATIC_VALID → RUNTIME_COMPATIBLE → SMOKE_TESTED
- **ComfyUI**：本地 `http://127.0.0.1:8188`，RTX 5080 16GB，fl2va int8 路径
- **Logical URI**：`project://`、`comfy-input://`、`comfy-output://`、`cache://`、`model://`
- **Video execution**：Panel-only — `beats[]` + `panels[]` → `PanelPack` → r2v. No per-shot video tasks; `composition_ref` is the panel BW storyboard (not a previous end frame). Legacy `shots[]` is not read for execution.

## PR & commit conventions

- Branch from `master`; never push to it directly
- Commit message: conventional commits (`feat:` / `fix:` / `docs:` / `refactor:` / `test:`)
- CI green before merge

## Security

- No `.env` committed (add to `.gitignore` if not present)
- API keys / credentials in config, never in code or logs
- SQLite DB paths resolved via config layer, not hardcoded
