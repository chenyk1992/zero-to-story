# LFO Runtime v1 完整实施计划

**目标设计：** `docs/architecture/2026-08-09-lfo-runtime-v1-design.md`  
**计划性质：** Breaking implementation；不兼容旧业务模型、数据库、CLI 或创作管线  
**执行原则：** 新链路先建立并通过 E2E，再删除旧链路；不长期双轨  
**技术栈：** Python 3.12、SQLite WAL、ComfyUI/H3、FFmpeg/ffprobe、pytest、ruff、pyright

## 1. 最终交付目标

实施完成后，仓库应具备以下能力：

1. 任意 Skill 使用统一的 `VideoExecutionPackage v1` 提交视频执行任务。
2. LFO 可安全导入 Skill 生成或用户提供的图像、视频、音频和字幕。
3. LFO 根据后端能力选择工作流并生成不可变执行快照。
4. Clip 级任务支持幂等、失败重试、崩溃恢复、取消和局部重做。
5. 视频生成结果经过技术 QC、标准化、字幕、音频混合、拼接和导出。
6. 所有产物可追溯到 Package、素材哈希、工作流、模型、环境和 Attempt。
7. `zero-to-story` 只是第一个 Skill Adapter；产品宣传等非故事型 Package 无需修改 LFO。
8. 原有小说分析、项目内部生图和 Panel-only 执行路径从默认产品中删除。

## 2. 全局约束

- 不实现旧 `shots[]`、Storyboard、PanelPack、旧 CLI 或旧数据库迁移。
- 不删除用户当前未提交改动；实施前先确认并隔离工作区状态。
- 新模块统一使用 `from __future__ import annotations` 和完整类型标注。
- 所有新行为先写测试，再实现；每个阶段只运行最窄但充分的验证。
- 任何 Package 输入都视为不可信：路径、媒体类型、文件大小和 JSON 字段必须验证。
- 不把 H3 的帧网格、分辨率、引用槽位和时长限制写入通用代码。
- 不允许静默后端降级、静默删除 required reference 或静默改变输出规格。
- 执行 Task 只读取物化快照，不读取可变的源 Package 或外部素材路径。
- 真实 ComfyUI E2E 只在单元与集成测试通过后执行。
- 删除旧代码前必须满足“切换门槛”；删除后不保留兼容 shim。

## 3. 目标目录结构

计划完成后的主要结构：

```text
src/lfo/
├── contracts/                 # 唯一公开执行契约和 JSON Schema
│   ├── package.py
│   ├── assets.py
│   ├── clips.py
│   ├── timeline.py
│   ├── validation.py
│   └── schemas/video-execution-v1.schema.json
├── assets/                    # 安全导入、CAS、媒体探测、审批
│   ├── importer.py
│   ├── store.py
│   ├── probe.py
│   ├── review.py
│   └── paths.py
├── backends/                  # 通用能力、注册、选择和适配器
│   ├── capabilities.py
│   ├── manifest.py
│   ├── registry.py
│   ├── selector.py
│   └── comfy_h3.py
├── execution/                 # 物化、DAG、Run/Task/Attempt 和执行
│   ├── store.py
│   ├── states.py
│   ├── materializer.py
│   ├── dag.py
│   ├── runtime.py
│   ├── handlers.py
│   ├── invalidation.py
│   └── recovery.py
├── media/                     # QC、标准化、音频、字幕、拼接、导出
│   ├── probe.py
│   ├── normalize.py
│   ├── qc.py
│   ├── audio.py
│   ├── subtitles.py
│   ├── timeline.py
│   └── export.py
├── application/
│   └── video_runtime.py       # Python facade
├── cli/                       # validate/plan/execute/status/... 命令
├── comfy/                     # 保留并适配
├── core/                      # 保留可复用的 hash/CAS/lease 等基础设施
└── environment/               # 保留

tests/
├── contracts/
├── assets/
├── backends/
├── execution/
├── media/
├── application/
├── cli/
└── e2e/

examples/execution-packages/
├── short-story-r2v/
└── product-promo-mixed/
```

目录是目标形态；实施时只有在职责明确且测试需要时才创建文件，不为形式一次性生成空模块。

## 4. 阶段与门槛总览

| 阶段 | 目标 | 完成门槛 |
|---|---|---|
| 0 | 基线与隔离 | 当前改动被记录，测试基线明确，实施分支安全 |
| 1 | 公共执行契约 | 两种不同 Skill 示例通过同一 Schema |
| 2 | Runtime Store 与素材导入 | 外部素材安全进入 CAS，审批绑定哈希 |
| 3 | 后端能力与选择 | H3 规则完全来自 Manifest，失败可解释 |
| 4 | 物化与 DAG | Package 可确定性生成不可变 Run Snapshot |
| 5 | 运行时执行 | Fake backend 跑通重试、恢复、取消、局部重做 |
| 6 | 媒体流水线 | 视频、音频、字幕、拼接与最终 QC 跑通 |
| 7 | Python facade 与 CLI | 用户入口完整，无需直接调用内部服务 |
| 8 | 新链路预切换 E2E | 本地 ComfyUI 完成至少一个真实 Package |
| 9 | Skill Adapter | zero-to-story 与非故事型示例都可交付 Package |
| 10 | 删除旧管线 | 无旧 CLI、旧创作执行服务和固定创作枚举 |
| 11 | 全量验收与发布 | 测试、真实 E2E、恢复演练、文档全部通过 |

## 5. Phase 0：基线、工作区隔离与保留清单

### 目标

在不丢失当前工作区改动的前提下，建立可比较、可回退的实施起点。

### 任务 0.1：确认当前改动所有权

**操作：**

- 记录 `git status --short`、当前分支和 HEAD。
- 将当前修改按“用户改动、已完成模板改动、运行日志、待删除旧文档”分类。
- 不使用 reset、checkout 或 clean。
- 与用户确认是否先提交现有改动，或在当前状态创建新分支继续。

**产物：** `docs/reports/lfo-runtime-v1-baseline.md`。

### 任务 0.2：建立测试与环境基线

**检查：**

```powershell
python -m pytest tests/ -v
python -m ruff check src tests
python -m lfo.cli.main doctor --machine-id local-windows
```

- 将失败分为本次重构前已存在或当前改动引入。
- 记录 ComfyUI、模型、FFmpeg 和工作流 revision。
- 不把 live E2E 作为 Phase 0 阻塞项，但保存最近一次成功证据。

### 任务 0.3：模块保留审计

逐模块建立：`keep`、`adapt`、`replace`、`delete-after-cutover` 清单。

重点人工核对：

- `core/database.py`、`runtime.py`、`state_machine.py`。
- `core/retry.py`、`recovery.py`、`invalidation.py`、`hashing.py`。
- `comfy/`、`environment/`、`assembly/`。
- `services/media_service.py`、QC、lineage、report。
- `planning/`、`visual/` 和 `storyboard/` 的调用关系。

**退出条件：** 每个计划删除的模块都已列出当前调用方和替代模块。

## 6. Phase 1：VideoExecutionPackage v1 契约

### 目标

建立唯一、稳定、与创作类型无关的 Skill → LFO 边界。

### 任务 1.1：建立公共数据模型

**创建：**

- `src/lfo/contracts/package.py`
- `src/lfo/contracts/assets.py`
- `src/lfo/contracts/clips.py`
- `src/lfo/contracts/timeline.py`
- `src/lfo/contracts/errors.py`

**必须实现：**

- `VideoExecutionPackage`
- `AssetSpec`、`AssetSource`、`ProvenanceSpec`
- `ClipSpec`、`GenerationSpec`、`ReferenceSpec`、`BindingPolicy`
- `AudioPolicy`、`AudioTrackSpec`
- `SubtitleSpec`、`SubtitleCue`
- `OutputPolicy`、`ApprovalDeclaration`
- 明确的 `from_dict()` / `to_dict()`，拒绝未知核心字段；`extensions` 除外。

**测试：**

- 最小合法 Package round-trip。
- 短剧 R2V Package 和产品 T2V/I2V Package 使用同一模型。
- 重复 ID、非法时长、非法 sequence、缺 required 引用、非法 binding 组合失败。
- `extensions` 可保存未知命名空间字段。

### 任务 1.2：JSON Schema 与规范示例

**创建：**

- `src/lfo/contracts/schemas/video-execution-v1.schema.json`
- `examples/execution-packages/short-story-r2v/package.json`
- `examples/execution-packages/product-promo-mixed/package.json`

**要求：**

- JSON Schema 与 Python validator 使用相同字段和约束。
- CI 中增加 Schema 示例验证，防止模型与 Schema 漂移。
- 示例素材使用测试 fixture，不引用开发者机器绝对路径。

如采用 `jsonschema`，在 `pyproject.toml` 明确运行时依赖；不得依赖开发环境偶然安装。

### 任务 1.3：Canonical hash

**复用：** `src/lfo/core/canonical.py`、`hashing.py` 中稳定部分。

**实现：**

- `package_content_hash(package)`。
- 排除运行时生成字段，包含所有会影响输出的字段。
- 路径在导入前按 Package 逻辑表示参与 hash；导入后另有 materialization hash。
- 数字、Unicode、字典顺序和空值的 canonical 规则写入测试。

### Phase 1 验证

```powershell
python -m pytest tests/contracts -v
python -m ruff check src/lfo/contracts tests/contracts
python -m pyright src/lfo/contracts
```

**阶段门槛：** 两个完全不同的示例 Package 均通过，核心 Schema 中不存在 `character`、`scene`、`prop`、`panel` 必填字段。

## 7. Phase 2：Runtime Store、内容寻址素材库与审批

### 目标

让外部素材从不可信路径安全进入 LFO 管理空间，并建立新的运行时持久化模型。

### 任务 2.1：新 Runtime 数据库 Schema

**策略：** 新建 `workspace/db/lfo-runtime-v1.db`；不迁移旧数据库。

**创建/实现：**

- `src/lfo/execution/store.py`
- 新 schema version 1。
- SQLite WAL、foreign keys、busy timeout、事务边界。

**核心表：**

- `packages`、`package_revisions`
- `blobs`、`assets`、`asset_revisions`
- `reviews`
- `runs`、`run_snapshots`
- `tasks`、`task_dependencies`
- `attempts`、`task_leases`
- `artifacts`、`lineage_edges`
- `invalidations`
- `exports`
- `transition_journal`

**复用原则：** 复用现有 CAS、journal、lease、rowcount 校验代码或算法，但不保留旧表兼容。

### 任务 2.2：安全路径解析

**创建：** `src/lfo/assets/paths.py`。

**实现：**

- Package-relative URI 解析。
- 允许读取根列表。
- `resolve()` 后验证目标在允许根内。
- 检查 symlink/junction 逃逸。
- 禁止设备路径、目录输入和任意输出绝对路径。
- 统一 Windows 大小写、UNC 和长路径处理。

**攻击测试：**

- `../` 越界。
- 符号链接或 junction 越界。
- 同名前缀目录绕过。
- Windows 驱动器切换和 UNC 路径。
- 空文件、目录和不可读文件。

### 任务 2.3：内容寻址存储

**创建：** `src/lfo/assets/store.py`、`importer.py`。

**实现：**

- 流式 SHA-256，避免大文件一次性读入内存。
- 先复制到临时文件，校验后原子移动到 CAS。
- 相同 blob 去重，逻辑 Asset revision 独立存在。
- 文件名清理，但保留原始文件名作为 metadata。
- 源文件被删除后，LFO 仍能执行。

### 任务 2.4：媒体探测和技术校验

**创建：** `src/lfo/assets/probe.py`。

**实现：**

- 按文件头和 ffprobe/图片解码结果确认媒体类型。
- 记录宽、高、帧率、时长、编码、音轨、采样率和声道。
- 设置可配置的文件大小、像素、时长和探测超时。
- 探测失败不登记为可执行 Asset。

### 任务 2.5：审批语义

**创建：** `src/lfo/assets/review.py`。

**实现：**

- Review 绑定 `asset_revision_id + file_hash + metadata_hash`。
- Package 执行审批绑定 package hash、required assets 和 output policy hash。
- Asset 或 Package 内容变化自动生成 INVALIDATED 记录。
- Skill 的 `approval` 字段仅作为来源声明，不直接授予运行权限。

### Phase 2 验证

```powershell
python -m pytest tests/assets tests/execution/test_store.py -v
python -m ruff check src/lfo/assets src/lfo/execution/store.py tests/assets
```

**阶段门槛：** 导入源文件后删除源文件，CAS 内容仍可读取；越界路径全部被拒绝；审批在文件变化后失效。

## 8. Phase 3：后端能力模型、Manifest 与工作流选择

### 目标

把 H3、ComfyUI 和未来其他视频后端的限制从通用代码移到版本化能力清单。

### 任务 3.1：通用 CapabilityManifest

**创建：**

- `src/lfo/backends/capabilities.py`
- `src/lfo/backends/manifest.py`

**字段：**

- `operations`
- `accepted_media_types`
- `max_references`、placement/slot 约束
- `duration_constraints`
- `frame_constraints`
- `resolution_constraints`
- `fps_constraints`
- `native_audio_capability`
- `seed_capability`
- `reproducibility_claim`
- `required_models`、`required_nodes`
- `output_signature`

不得出现 `character_multiview`、`storyboard_frame` 等创作枚举。

### 任务 3.2：迁移 H3 Manifest

**适配：** 现有 `core/workflow_registry.py` 和 `src/lfo/registry/*.json`。

**要求：**

- `17k+5`、最小/最大帧数、默认 fps、分辨率和引用槽位来自 Manifest。
- 保留已有 workflow hash 和三级环境验证能力。
- 当前工作区新增的竖屏 H3 manifests 先审计，不覆盖用户修改。

### 任务 3.3：Capability Resolver

**创建：** `src/lfo/backends/selector.py`。

**输出：**

- 选中的 backend/provider/workflow revision。
- 参数对齐结果。
- 每个候选被接受或拒绝的解释。
- required reference 无法绑定时的明确错误。
- optional reference 被裁剪时的结构化原因。

**v1 策略：**

- 不自动降级。
- Package 可指定有序候选，但切换候选不得改变 required input 或 output contract。
- 质量、成本或原生音频能力发生变化时进入 WAITING_REVIEW。

### Phase 3 验证

```powershell
python -m pytest tests/backends tests/test_workflow_registry.py -v
python -m ruff check src/lfo/backends tests/backends
```

**阶段门槛：** 通用 validator 中 grep 不到 H3 的 `17` 帧规则和固定 `864x480/24fps`；R2V 引用超限能给出可解释结果。

## 9. Phase 4：物化、引用绑定和 DAG

### 目标

将已审批 Package 确定性转换为不可变、可执行的 Run Snapshot。

### 任务 4.1：Materializer

**创建：** `src/lfo/execution/materializer.py`。

**流程：**

1. 读取并校验 Package revision。
2. 验证 required assets 和 Package 审批。
3. 解析每个 Clip 的能力要求。
4. 选择 backend/workflow revision。
5. 将逻辑 Asset key 解析为内部 immutable asset revision。
6. 按 BindingPolicy 分配槽位并处理 optional refs。
7. 对齐帧数、分辨率和后端参数。
8. 保存 prompt、模型、环境和输出策略快照。
9. 计算 materialization hash。

相同输入必须生成相同 canonical snapshot；任何影响输出的变化必须改变 hash。

### 任务 4.2：通用 DAG

**创建/适配：** `src/lfo/execution/dag.py`。

**标准 Task 类型：**

- `video.generate`
- `media.qc`
- `audio.mix`
- `subtitle.render`
- `timeline.assemble`
- `export.finalize`

**规则：**

- 一个 Clip 默认一个生成 Task，但后端 Adapter 可在内部拆步骤。
- Clip 之间默认无生成依赖；只有 Package 明确 dependencies 才连边。
- 时间线 assemble 依赖所有被采用 Clip 的已批准或策略允许产物。
- DAG 必须无环，logical task key 在 Run 内稳定。

### 任务 4.3：计划审阅输出

`lfo plan` 所需的只读计划应显示：

- Clip → backend/workflow。
- 实际引用及槽位。
- 被删除的 optional 引用及原因。
- 帧数、分辨率、时长和原生音频策略。
- 预计任务 DAG。
- 所有警告和需要确认的变化。

### Phase 4 验证

```powershell
python -m pytest tests/execution/test_materializer.py tests/execution/test_dag.py -v
```

**阶段门槛：** 同一 Package 两次物化 hash 相同；修改一个 prompt、asset 或 output policy 后 hash 改变；DAG 无 Panel/Storyboard 假设。

## 10. Phase 5：Runtime 执行、幂等、重试、恢复和局部重做

### 目标

在 Fake backend 上先完整证明执行语义，再连接真实 ComfyUI。

### 任务 5.1：分层状态模型

**创建：** `src/lfo/execution/states.py`。

分别实现 Run、Task、Attempt、Review、Export 状态和合法转换矩阵。复用现有 CAS 与 transition journal 机制。

**测试：**

- 所有合法转换。
- 非法跳转失败。
- CAS 竞争只有一个写入成功。
- Review 不再混入 Task 状态。

### 任务 5.2：Runtime 调度循环

**创建：** `src/lfo/execution/runtime.py`、`handlers.py`。

**实现：**

- 查找 READY Task。
- 获取 lease。
- 创建 Attempt 和幂等 key。
- 提交后端、监控、收集和登记 Artifact。
- 释放 lease，并推进下游任务。
- 达到 retry budget 后转 terminal failure。

### 任务 5.3：Fake backend 集成测试

Fake backend 必须可模拟：

- 立即成功。
- 提交前失败。
- 提交后响应丢失。
- 运行中崩溃。
- transient failure 后成功。
- terminal failure。
- 输出损坏或 QC 失败。
- 取消成功和取消结果未知。

### 任务 5.4：恢复与幂等

**适配：** 现有 recovery/retry 逻辑。

**关键规则：**

- SUBMITTED/RUNNING Attempt 在崩溃后进入 reconcile，不直接重提。
- 后端 task ID 已存在时先查询。
- 相同 materialization 和幂等 key 的成功 Artifact 可复用。
- 输入变化后不得复用旧 Artifact。

### 任务 5.5：结构化失效和局部重做

**创建/适配：** `src/lfo/execution/invalidation.py`。

实现：

- `regenerate_clip`
- `re_qc_clip`
- `remix_audio`
- `regenerate_subtitles`
- `reassemble_timeline`
- `reexport`

测试修改 Clip 2 只重做 Clip 2 生成和总后处理。

### 任务 5.6：取消传播

- Run cancel 阻止新任务并向活跃 Attempt 发取消请求。
- Clip cancel 只影响该 Clip 和依赖它的下游。
- 已成功 Artifact 保留并可审计。

### Phase 5 验证

```powershell
python -m pytest tests/execution -v
python -m ruff check src/lfo/execution tests/execution
python -m pyright src/lfo/execution
```

**阶段门槛：** Fake backend 故障矩阵全部通过；崩溃恢复不产生重复提交；局部重做范围正确。

## 11. Phase 6：媒体 QC、音频、字幕、拼接与导出

### 目标

完成“视频生成之后”的统一工程化系统能力。

### 任务 6.1：视频标准化和技术 QC

**适配/创建：** `src/lfo/media/probe.py`、`normalize.py`、`qc.py`。

QC 规则来自 materialized output contract：

- 可解码性。
- 时长容差。
- 分辨率、比例、fps。
- 编码、色彩空间和音轨签名。
- 黑帧/空帧等已有可复用检查。

删除 `pipeline_service.py` 中固定 `864×480/24fps` 的默认路径。

### 任务 6.2：字幕

**创建/适配：** `src/lfo/media/subtitles.py`。

支持：

- timed cue → SRT。
- timed cue → WebVTT。
- 外部 SRT/VTT 导入和时间范围校验。
- Clip 局部时间转换为全局时间线。
- sidecar 和 burn-in 两种输出。

不再从 Storyboard beat 自动读取对白。

### 任务 6.3：音频策略与混音

**创建：** `src/lfo/media/audio.py`。

支持：

- `preserve/mute/mix/replace` 原生音频策略。
- 外部音轨 offset、trim、gain、fade。
- dialogue/foreground 对 BGM/ambient 的 ducking。
- 采样率、声道和响度标准化。
- 无音轨 Clip 的确定性静音处理。

使用 FFmpeg filter graph 构建器并对每种策略做 fixture 测试；不通过 shell 字符串执行。

### 任务 6.4：时间线与拼接

**创建/适配：** `src/lfo/media/timeline.py`。

- 按 Clip sequence 排序。
- 明确处理缺失、拒绝或取消 Clip。
- 支持直接切和 Package 声明的基础转场。
- 计算全局字幕与音频 offset。
- 生成可审计 timeline snapshot。

### 任务 6.5：导出和最终 QC

**创建/适配：** `src/lfo/media/export.py`。

- 临时文件渲染。
- 最终 QC 成功后原子发布。
- 生成最终 MP4、可选 SRT/VTT、manifest 和 provenance 报告。
- Export revision 与输入 Artifact 集合绑定。

### Phase 6 验证

```powershell
python -m pytest tests/media -v
```

Fixture 至少覆盖：有原生音频、无音频、外部对白+BGM、中文字幕、不同 fps 输入和损坏文件。

**阶段门槛：** 生成的媒体通过 ffprobe 契约；字幕时间不越界；四种原生音频策略都有测试。

## 12. Phase 7：Python Facade、CLI 和运行报告

### 目标

让 Skill 和用户只接触稳定入口，不直接操作内部服务或数据库。

### 任务 7.1：VideoRuntime facade

**创建：** `src/lfo/application/video_runtime.py`。

接口：

- `validate(package_path)`
- `plan(package_path)`
- `execute(package_path, approval=None)`
- `status(run_id)`
- `retry(run_id, clip_id=None, scope=None)`
- `cancel(run_id, clip_id=None)`
- `review(run_id, target, decision)`
- `export(run_id, policy_override=None)`

在 `src/lfo/__init__.py` 只公开稳定 facade 和必要 result 类型。

### 任务 7.2：新 CLI

**修改：** `src/lfo/cli/` 注册与命令模块。

实现：

```text
lfo validate
lfo plan
lfo execute
lfo status
lfo retry
lfo cancel
lfo review
lfo export
lfo doctor
```

要求：

- 机器可读 `--json` 输出。
- 默认输出面向非技术用户，错误带 JSON path、Clip ID 和修复建议。
- CLI 调用 facade，不复制业务逻辑。

### 任务 7.3：报告

报告至少包含：

- Run 与 Package revision。
- 每个 Clip 当前状态和 Attempt 历史。
- 后端选择解释。
- 输入输出哈希和 lineage。
- QC、审批和导出状态。
- 可复现性声明和剩余警告。

### Phase 7 验证

```powershell
python -m pytest tests/application tests/cli -v
python -m lfo.cli.main validate examples/execution-packages/short-story-r2v/package.json
python -m lfo.cli.main plan examples/execution-packages/product-promo-mixed/package.json --json
```

**阶段门槛：** 示例用户流程不需要导入任何 `lfo.*.internal` 模块。

## 13. Phase 8：真实 ComfyUI 预切换 E2E

### 目标

在删除旧管线前，证明新链路可调用现有本地环境生成真实视频。

### 任务 8.1：Comfy H3 Adapter

**创建/适配：** `src/lfo/backends/comfy_h3.py` 和现有 `comfy/`。

- Materialized binding → Comfy input 文件。
- Workflow 参数注入只通过 manifest 声明的 binding。
- 保存 prompt ID、workflow hash、模型解析和 Comfy history。
- 收集输出后进入统一 Asset/Artifact 流程。

### 任务 8.2：单 Clip smoke

使用最小 T2V 或 I2V Package 验证：导入 → 物化 → 提交 → 收集 → QC。

### 任务 8.3：多 Clip R2V E2E

至少 2 个 Clip：

- 外部参考图。
- R2V 工作流。
- 原生音频策略。
- 中文字幕。
- 最终拼接和报告。

### 任务 8.4：中断恢复演练

- 提交后终止 LFO 进程。
- 重启后 reconcile Comfy history。
- 确认不重复提交。

### Phase 8 验证

```powershell
python scripts/live_e2e_execution_package.py
```

**切换门槛：** 真实 E2E 成功、恢复演练成功、最终 MP4/SRT/provenance 完整。未达到门槛禁止删除旧代码。

## 14. Phase 9：Skill Adapter 与跨创作类型证明

### 目标

证明创作层确实可以独立变化，LFO 不需要理解创作类型。

### 任务 9.1：PackageBuilder SDK

为 Skill 提供轻量 builder，但 builder 只创建公共 Package，不访问数据库或 ComfyUI：

```python
builder = VideoPackageBuilder(...)
builder.add_asset(...)
builder.add_clip(...)
builder.write("execution-package.json")
```

### 任务 9.2：zero-to-story Adapter

**修改：** `.agents/skills/zero-to-story/`。

新流程：

1. 故事概要审批。
2. 角色等创作图审批。
3. 黑白分镜审批。
4. 视频提示词审批。
5. 输出 `execution-package.json` 和本地素材。
6. 调用 `lfo validate/plan` 供用户检查。
7. 用户确认后调用 `lfo execute`。

Skill 不构建内部 Asset ID、PanelPack 槽位或 ComfyUI workflow。

### 任务 9.3：非故事型适配证明

创建一个产品宣传 Package 示例：

- 不含 Storyboard、Beat、Panel 或角色。
- 可混合 T2V、I2V/R2V Clip。
- 使用产品图、Logo、外部旁白或字幕。
- 不修改 LFO 核心即可 validate 和 plan。

### Phase 9 验证

- 两个 Skill/示例只依赖公共 Schema 或 PackageBuilder。
- grep Skill 文件，不存在 SQLite、Comfy 节点 ID、模型本地路径和内部 Asset ID。
- 修改 Skill 内部创作步骤不影响 LFO 测试。

## 15. Phase 10：切换默认入口并删除旧创作管线

### 目标

完成 breaking cutover，不留下会误导 Agent 或维护者的双轨逻辑。

### 删除前检查

- Phase 8 和 Phase 9 门槛全部通过。
- 新 CLI 和新 Skill 已覆盖用户主流程。
- `rg` 已生成旧模块调用关系清单。
- 用户工作区数据无需迁移或已明确不支持。

### 任务 10.1：删除旧默认入口

- 删除 `lfo run <storyboard.json>`。
- 删除旧 `images`、`preview`、`panels` 创作命令。
- CLI 帮助和 README 只展示 Package 流程。

### 任务 10.2：删除 Python 创作执行服务

根据 Phase 0 审计删除：

- 小说 intake/decompose 默认执行路径。
- CharacterSheetService。
- StoryboardPreviewService。
- StoryboardGraphService 的创作到任务路径。
- PipelineService 内部 image phase。
- Prompt/Panel generation 中属于 Skill 的部分。

创作文档模板可以迁入 Skill 资源目录；不作为 LFO Runtime 模板。

### 任务 10.3：删除固定创作语义

仓库运行时代码必须清除：

- `_VALID_ROLES={character, scene, prop...}`。
- `character_reference/scene_reference/prop_reference` 固定 purpose。
- `character_multiview/storyboard_frame` capability。
- `characters_in_panel` 等运行时字段。
- 由 Panel 自动推导视频任务的逻辑。

### 任务 10.4：清理旧数据库与文档

- 旧数据库文件不删除用户数据，只停止默认使用并标记 unsupported。
- 删除或重写失效架构文档，不留下相互冲突的执行说明。
- 更新 `AGENTS.md`、README、setup、doctor 和示例。
- `pyproject.toml` 版本提升为新的 breaking 版本。

### 删除后静态检查

```powershell
rg -n "shots\[|CharacterSheetService|StoryboardPreviewService|PanelPack|character_multiview|storyboard_frame" src/lfo
```

预期：除明确的 Skill adapter、迁移说明或测试禁止断言外无匹配。

## 16. Phase 11：全量验收、稳定性演练和发布

### 任务 11.1：测试金字塔

**单元：**

- 契约、canonical hash、路径安全、状态转换、能力匹配、引用绑定、音频/字幕参数。

**集成：**

- Package → Store → Materialization → Fake backend → Export。
- DB 并发 CAS、lease 和恢复。
- FFmpeg fixture 媒体流水线。

**真实 E2E：**

- T2V 单 Clip。
- R2V 多 Clip。
- 外部音轨和字幕。
- 中断恢复。
- 局部重做。

### 任务 11.2：全量验证

```powershell
python -m pytest tests/ -v
python -m ruff check src tests
python -m pyright src/lfo
python -m lfo.cli.main doctor --machine-id local-windows
python -m lfo.cli.main validate examples/execution-packages/short-story-r2v/package.json
python -m lfo.cli.main validate examples/execution-packages/product-promo-mixed/package.json
python scripts/live_e2e_execution_package.py
```

### 任务 11.3：故障演练

至少验证：

- ComfyUI 不可用。
- 模型或节点缺失。
- 磁盘不足。
- 素材在导入前缺失或哈希不匹配。
- 提交后响应丢失。
- FFmpeg 失败。
- QC 不通过。
- 用户取消和审批拒绝。

每种故障必须给出可行动错误，不损坏已有成功产物。

### 任务 11.4：文档与发布

交付文档：

- Package v1 字段参考。
- Skill Adapter 指南。
- CLI 用户指南。
- 后端 Manifest 开发指南。
- 故障恢复与运维指南。
- Breaking release notes。

### 最终 Definition of Done

- [ ] 公共入口只有 VideoExecutionPackage/VideoRuntime。
- [ ] 短剧与产品宣传示例无需修改内核即可执行。
- [ ] 源素材导入后不再依赖源路径。
- [ ] 所有执行基于不可变 Snapshot。
- [ ] 重试和恢复没有重复提交。
- [ ] 单 Clip 局部重做不重做其他 Clip。
- [ ] H3 约束全部来自 Manifest。
- [ ] 视频、音频、字幕、导出和 provenance 完整。
- [ ] 旧创作执行管线和固定创作枚举已删除。
- [ ] 全量测试、静态检查、doctor 和真实 E2E 通过。

## 17. 风险、缓解与停止条件

| 风险 | 缓解 | 停止条件 |
|---|---|---|
| 新状态模型破坏恢复能力 | 先用 Fake backend 做完整故障矩阵，复用现有 CAS 算法 | 出现无法证明幂等的 UNKNOWN Attempt |
| 删除旧代码过早 | Phase 8/9 设强制切换门槛 | 新链路真实 E2E 未通过 |
| Schema 过度设计 | v1 只纳入真实执行需要，扩展字段命名空间化 | 字段没有明确消费者或验收测试 |
| 自由 purpose 失去机械约束 | 使用 BindingPolicy 显式表达 required/priority/placement | 仍需根据“角色/产品”等文本猜槽位 |
| 自动降级损害质量 | v1 默认失败，降级需显式策略和确认 | 候选改变 output contract 或 required input |
| 外部路径带来安全问题 | Package-relative、允许根、CAS copy、媒体探测 | 路径不能证明位于允许读取范围 |
| 音频范围膨胀 | v1 只做已有素材的确定性混音，不做生成 | 需求涉及声音创作或模型选角 |
| 当前工作区改动冲突 | Phase 0 先分类和隔离，不 reset/clean | 文件所有权不明确且会被覆盖 |

## 18. 推荐执行批次

为保持每批都可验证，建议按以下批次实施：

1. **批次 A：** Phase 0–1，冻结公共契约。
2. **批次 B：** Phase 2–4，完成导入、存储、能力选择和物化。
3. **批次 C：** Phase 5，完成可靠执行内核。
4. **批次 D：** Phase 6–7，完成媒体流水线和用户入口。
5. **批次 E：** Phase 8–9，真实验证和 Skill 接入。
6. **批次 F：** Phase 10–11，删除旧链路、全量验收和发布。

每个批次完成后单独审查 diff、测试证据和架构偏差。若发现公共契约必须改变，应在批次 A/B 解决；进入批次 C 后，除修复明确缺陷外不再随意扩展 v1 Schema。

## 19. 粗略工作量

单人连续实施的合理量级约为 4–6 周，主要不确定性来自真实 ComfyUI 恢复语义、音频混合覆盖面以及删除旧管线后的回归范围。若只交付最小执行 MVP，可在 Phase 7 后形成可用版本；但在 Phase 8–11 完成前，不应宣布架构重构最终完成。

## 20. 实施启动条件

开始编码前只需要完成两项确认：

1. 处理或明确保留当前工作区已有未提交改动。
2. 确认设计文档中的 v1 范围，尤其是“LFO 负责已有音轨的混合，但不负责 TTS/BGM 生成”。

其余技术决策均已在本计划中锁定，可以按阶段连续实施，不需要为历史兼容再次停下来决策。
