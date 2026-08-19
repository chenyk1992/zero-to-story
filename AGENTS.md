# AGENTS.md

LFO — Local Film Orchestrator. 本地视频实施运行时。上游 Creative Skill 负责故事、角色图、黑白分镜、Panel/Clip 提示词与用户审批，并交付 `lfo.video-execution.v1`；LFO 负责素材导入、后端选择、MiniMax H3/ComfyUI 视频生成、标准化、QC、音频、字幕、时间线、导出、重试与恢复。

- LFO 是执行运行时，不是创作工具；不要在 LFO 核心中生成故事、图片、分镜或其他创作决策。
- Runtime 只理解公共执行包和素材，不理解故事板语义；创作侧可以把 PanelPack 映射为 Clip。
- 上游 Skill 与 LFO 的公共边界是 `VideoExecutionPackage` 和素材文件；上游 Skill 不应操作 LFO 数据库、ComfyUI 节点或内部素材 ID。

## Agent operating boundaries

- 默认代码改动放在 `src/lfo/`，并为行为变化补充或更新 `tests/`；`scripts/`、`docs/`、`pyproject.toml` 和 CI 配置只在任务需要时修改。
- 不要把 `workspace/` 当作源码目录或临时工作目录；遵守下面的 workspace 数据规则。
- 不要修改外部 ComfyUI 安装目录、模型文件或 ComfyUI 提供方缓存来解决 LFO 代码问题；通过 LFO 的 ComfyUI 交互层和配置解决。
- 不要修改 `.env*`、凭据、`.git/` 或缓存目录；不要手工改写、移动或删除生成媒体和无关的用户改动。
- 保留已有未提交改动；开始修改前检查相关 diff，不覆盖或重排与当前任务无关的工作。
- 只做与当前任务直接相关的最小改动；不要顺手重构、清理旧代码或引入新依赖，除非任务明确需要并说明理由。
- 未经明确要求，不提交、推送、删除数据或执行不可逆的批量清理。

## Setup commands

- Install dependencies: `python -m pip install -e ".[dev]"` (editable install with dev extras)
- Run CLI: `python -m lfo.cli.main <command>`
- CLI command details and operational examples: see [`docs/cli-guide.md`](docs/cli-guide.md).
- If the package is not installed in editable mode, use PowerShell: `$env:PYTHONPATH = "src"`
- Run all tests: `python -m pytest tests/ -v`
- Run single module tests: `python -m pytest tests/test_runtime.py -v`
- Run live Package E2E when the task requires ComfyUI integration: `python scripts/live_e2e_execution_package.py <execution-package.json> --approve`
- Local ComfyUI setup, doctor, preflight and machine-specific details: see [`docs/local-windows.md`](docs/local-windows.md).

## Workspace user data and maintenance

`workspace/` 是持久化的用户数据目录，默认被 Git 忽略，不是 agent 的 scratch space。任何 agent 都必须把其中的数据视为用户资产，优先保护已有内容、引用关系和可恢复性。

以 [`workspace/README.md`](workspace/README.md) 中的运行时布局为准。新数据只能进入已有的语义目录，不要在 `workspace/` 根部随意创建新目录：

- `workspace/projects/<project_id>/execution-package.json`：执行包和项目资产。
- `workspace/projects/<project_id>/outputs/<run_id>/`：Run 中间产物。
- `workspace/projects/<project_id>/final/<output.directory>/`：最终视频、SRT 和 manifest。
- `workspace/assets/sha256/`：内容寻址素材副本。
- `workspace/db/runtime-v1.sqlite3`：运行状态与审计日志。
- 已有的 `workspace/spikes/` 仅用于明确要求的实验，不是通用临时目录；不要为普通任务新建类似 scratch 目录。

- 新的执行包、Run 中间产物和最终产物必须写入对应的 `workspace/projects/<project_id>/`；Run 产物必须使用 `RunArtifactLayout`。
- 不得创建或重新接入 `workspace/runs/`、`workspace/exports/`，也不得把生成媒体、日志、下载文件或临时文件直接放在 `workspace/` 根部。
- 素材导入必须使用 LFO 的素材导入/CAS 机制，不要手工复制、改名或删除 `assets/sha256/` 下的内容。
- 数据库和 CAS 文件是相互关联的持久化数据。除非任务明确是数据维护或迁移，不要直接编辑、移动或删除 `workspace/db/`、`workspace/assets/` 中的文件。
- 测试使用 `tmp_path` 或临时 workspace；不得让测试写入真实的仓库 `workspace/`。`tests/conftest.py` 已负责隔离默认 workspace。
- 已存在但不符合当前布局的项目目录、历史目录或用户自定义目录一律视为用户数据：不要为了“整理目录”而自动重命名、合并或删除。发现问题时先报告路径、用途和引用风险，再等待明确的维护任务。
- 在 `workspace/` 下创建、移动或删除任何内容前，先阅读 `workspace/README.md`，确认目标目录和生命周期；无法判断时不要猜测。

### Workspace maintenance workflow

- 普通编码、测试和文档任务不得顺手创建或整理 `workspace/` 内容。
- 明确的数据维护任务必须先盘点顶层目录、项目路径、数据库和 CAS 引用，再决定移动或删除；先报告分类和风险，不直接执行大范围清理。
- 维护项目目录时保留 `project_id`、执行包相对路径、数据库记录和素材引用的一致性；优先使用 LFO 现有服务/API，避免手工改文件系统。
- 删除或移动用户数据必须有明确范围；可恢复的移动或备份优先于永久删除。清理 CAS 前必须确认数据库没有有效引用。
- 维护完成后报告新增、移动、删除的路径，以及数据库、素材引用和测试检查结果。

## Project layout

src layout — all system code lives under `src/lfo/`；user data lives under `workspace/`，canonical layout 见 `workspace/README.md`。

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
- `workspace/` — 持久化用户数据；不得随意创建顶层目录，详细规则见上文。
- `scripts/` — Live E2E 脚本
- `tests/` — pytest 测试套件（按模块分子目录）
- `.agents/skills/zero-to-story/assets/` — zero-to-story 可复用项目骨架与生成 Prompt（与 Skill 一起维护，git-tracked）

## Code style

- Python 3.12；新建或实质修改的 Python 模块使用 `from __future__ import annotations`。
- 类型检查使用 Pyright，配置位于 `pyproject.toml`；不要把 mypy 当作项目必需工具。
- 命名：snake_case 函数/变量，PascalCase 类，UPPER_CONST
- 错误处理：自定义异常层次（`comfy/exceptions.py`），CAS 状态转换用 `rowcount` 验证
- 时间戳统一 UTC ISO 8601
- 不写死 workspace、数据库、ComfyUI 或其他机器路径；通过配置层和既有路径解析逻辑获取路径。
- 只做与当前任务直接相关的最小改动；不要顺手重构或清理无关的废弃逻辑。

## Testing

- Framework: pytest（配置位于 `pyproject.toml`，从项目根运行）
- 测试结构：`tests/test_<module>.py` 单元测试 + `tests/test_<module>/` 子目录分组
- 共享 fixtures：`tests/conftest.py` 含 `isolate_process_state`（自动隔离 env vars 和 cwd）
- Live E2E：`scripts/live_e2e_execution_package.py`（需本地 ComfyUI，时长取决于 Package）
- 新增或修改行为必须有对应测试；测试应验证真实行为、状态转换、错误处理或公共契约，不要只为提高覆盖率测试常量和内部实现细节。
- 根据改动风险选择验证范围：普通模块改动跑目标测试；公共契约、状态机、数据库、素材导入、产物布局或跨模块改动跑全量测试；ComfyUI 后端或环境改动再运行 doctor/preflight，必要时运行 live E2E。
- 完成任务时报告实际运行的检查和未运行的检查；如果无法运行完整测试，说明原因和剩余风险。

## Architecture notes

项目当前没有配置 `lfo` console entry point；使用 `python -m lfo.cli.main ...`，不要假设 `lfo ...` 命令存在。

- **公共边界**：上游 Skill 只能写 `VideoExecutionPackage` 和素材文件；不得操作数据库、ComfyUI 节点或内部素材 ID
- **包导入**：从 `lfo` 包导入，`tests/conftest.py` 自动注入 `src/` 到 `sys.path`
- **SQLite 运行时**：WAL 模式，CAS 状态机，`rowcount` 不用 `total_changes`
- **工作流 hash**：LFO-WFJ1 规范（float 归一化 + NFC + SHA-256），算法标识 `lfo-wfj1-sha256-v1`
- **三级验证**：STATIC_VALID → RUNTIME_COMPATIBLE → SMOKE_TESTED
- **ComfyUI**：通过配置层访问本地服务；机器路径、模型和环境检查见 [`docs/local-windows.md`](docs/local-windows.md)。
- **素材导入**：Package 相对路径在导入时解析；之后只读取 CAS 内不可变副本
- **产物布局**：所有新 Run 的中间/最终媒体必须使用 `RunArtifactLayout` 写入
  `workspace/projects/<project_id>/outputs/<run_id>/` 和
  `workspace/projects/<project_id>/final/<output.directory>/`；不得创建 workspace 根部
  的 `runs` 或 `exports` 目录。ComfyUI 输出仅作提供方缓存，必须复制到项目 Run 目录后
  才记录为 LFO artifact。
- **Video execution**：每个 `clips[]` 是可独立重做的执行单元；创作侧可将 PanelPack 映射为 Clip，但 Runtime 不理解故事板语义

## PR & commit conventions

- Branch from `main`；never push directly to `main`。
- Commit message: conventional commits (`feat:` / `fix:` / `docs:` / `refactor:` / `test:`)
- CI green before merge

## Security

- No `.env` committed (add to `.gitignore` if not present)
- API keys / credentials in config, never in code or logs
- SQLite DB paths resolved via config layer, not hardcoded
