# 画布与视频生产指南

画布是本地故事工作空间。页面、MCP 和 `python -m lfo.canvas` 画布命令操作同一个服务、数据库和媒体目录。保存只是编辑；页面确认或对话明确授权后，才固定输入并执行。共同分工见[项目协作规则](ai-system-prompt.md)，具体字段见[画布操作接口](../.agents/skills/canvas-workspace/references/operations.md)。

## 启动与宿主接入

首次准备项目依赖，在项目根运行：

```powershell
./scripts/bootstrap_dev.ps1
```

在 `web/canvas/` 运行 `npm install`、`npm run build`，然后回到项目根运行：

```powershell
./.venv/Scripts/python.exe -m lfo.canvas open
```

返回的本机地址可以用普通浏览器或宿主浏览器面板打开。默认地址为 `http://127.0.0.1:8765`；前台启动用 `serve`。项目级参数 `--project`、`--data-dir`、`--media-root`、`--port` 放在子命令前。修改后端后重启服务，修改页面后重新构建。重启不会重新提交生成。

支持 MCP 的宿主可启动项目解释器，参数为 `-m lfo.canvas mcp`，工作目录为项目根。Codex 的连接示例在项目 [.codex/config.toml](../.codex/config.toml)。其他宿主使用自己的项目级连接格式，加载同一组 Skills；不复制画布数据库，也不修改项目的主会话/子代理分工。

没有 MCP 时仍可使用相同接口：

```powershell
./.venv/Scripts/python.exe -m lfo.canvas call GET /api/runs?summary=1
./.venv/Scripts/python.exe -m lfo.canvas call POST /api/runs/RUN_ID/claim --body-file REQUEST_JSON
```

`REQUEST_JSON` 是调用方在系统临时目录准备的 JSON 正文文件。模型选择、原生委派、继续执行和空闲唤醒由宿主负责；生产接口不包含语言模型名称或推理档位。MCP 接通不代表该宿主已经具备图片工具或后台唤醒能力。

## 一次工作单元

1. 主会话确定故事、导演要求、准确对白和采用标准，交给用户配置的执行子代理。只交当前单元需要的来源、素材、授权范围和完成条件。
2. 子代理读取当前组件及直接输入，核实能力。必要素材齐全即可推进当前镜头；独立的后续素材可以另行准备。
3. 保存草稿，确认当前版本。服务冻结提示词、参考文件和参数。已存在同一 `request_id` 时返回原请求；不能换编号重发来绕过未完成任务。
4. 本地脚本任务由服务执行；`pending_agent` 任务由具备工具的代理独占领取。领取返回的 `execution_snapshot` 是实际输入，不能用后来编辑的草稿替换。
5. 提交一次。等待由执行进程或宿主工具处理；仅在阶段变化时记录进度和已有提供方任务号，不开监控代理。
6. 回填实际文件并检查技术结果。故事生产或明确有采用要求的任务，再记录实际内容的审片结论；普通组件不新增故事审片门槛。
7. 返回产物、必要证据、实际末态、未核实项和后续依赖。需要下一代理时使用宿主真实的启动/继续执行操作；普通消息送达不代表代理已开始工作。

页面显示最近一次任务的固定输入和当前草稿差异。运行中也可修改草稿，但会标明修改尚未执行。移动组件位置不改变生成输入。一个工作单元只由一个执行者回填；画布编辑发生版本冲突时重读合并，不覆盖用户修改。

持续生产还需登记当前主会话负责的接续范围，避免执行结果返回后无人处理。页面顶部显示只读接续状态，支持查看待处理结果、等待、阻塞、暂停和无进展情况。登记、主会话结束前检查以及宿主空闲接续的启用条件见[画布生产接续](canvas-continuation.md)；未登记时不会自动把历史镜头纳入生产。

## 能力与并行

能力目录区分 `installed` 与 `available`。调用 `canvas_capabilities(host_tools=[...])` 或领取任务时，只声明接手会话实际可调用的工具，例如 `image_gen`、`terminal`；这些声明只用于当次检查，不改变其他会话的能力。

| 工作 | 当前规则 |
|---|---|
| 本地 Comfy 视频 | `queued` 脚本任务；服务内部 worker 启动项目执行 Skill，经 HTTP 预检后同步调用官方 comfy-cli；一次提交、串行等待 |
| 宿主图片工具 | 显式选择已安装能力后可排队；有该工具的会话才能领取 |
| mmx 视频 | 用户明确选择，且原有 mmx 能力可用时接手；失败不切换提供方 |
| 独立图片 | 能力声明资源独立时，最多并发 2；`LFO_IMAGE_CONCURRENCY=1` 可收紧到 1 |
| 未知任务 | 继续占用相关资源；已证实独立的资源仍可推进 |
| 提示词、资料、审查、字幕 | 无依赖且资源允许时与生成重叠；依赖实际末态的内容等证据齐全后定稿 |

资源忙时继续检查其他就绪任务。画布内所有视频共用同一串行资源；直接在画布之外使用第三方工具时，调用方仍须遵守项目的视频串行规则。项目不能约束用户在外部应用中单独发起的生成。

新组件只在可用能力唯一时自动选择；多种能力时由用户或授权执行者选择。已安装但需要代理工具的选项显示“需 Agent 接手”。保留历史提供方，不因宿主变化静默换后端。

## 状态与异常核实

恢复领取令牌丢失时，先读取最新完整 run，再用 `canvas_handoff_recovery(run_id, reason, expected_updated_at)`（HTTP `POST /api/runs/{id}/handoff-recovery`）明确交接原因并原样提交 `updated_at`。仅当前可恢复、已有 recovery claim 且未解决的运行可交接；CAS 竞争只允许一次成功，返回 `{run_id, owner_token}`。新令牌用于原 `reconcile` 接口，旧恢复令牌立即失效。原领取原因和时间随 `recovery_handoff` 追加到 evidence，事件中不含令牌；原生成状态、媒体、远端编号及占用不变。它不会重新提交任务，也不放宽原恢复证据要求；`reconcile.evidence` 必须是对象，包含 `request_id`、`remote_status`、`source`、`reason`。未领取应使用 `claim-recovery`，已解决或不可恢复的终态不允许交接。

| 信息 | 字段与含义 |
|---|---|
| 执行结果 | `queued` / `pending_agent` / `running` / `succeeded` / `failed` / `unknown` / `cancelled` |
| 执行阶段 | `stage`：输入校验、上传、提交、生成、结果回收、媒体校验；阶段变化有时间记录 |
| 本地关注 | `attention_state`：`active`、`paused`、`abandoned`，另存原因；不表示远端取消 |
| 内容采用 | `review`：`ACCEPT`、`REJECT`、`INCONCLUSIVE`；绑定实际文件与摘要 |

取消待办只适用于未领取的请求。本地超时、停止等待或服务断线后，不能推断远端已停止。没有可查询任务号时明确保留未知，不伪造查询结果。服务重启将原运行中的任务标为未知，未启动的本地脚本请求停止，不自动重播。

用户明确“停止等待、不再跟进”时，调用 `canvas_attention(run_id, state="abandoned", reason=...)`；明确“暂停、稍后继续”时使用 `state="paused"`。返回记录中的字段是 `attention_state`。两种操作都不修改远端状态，也不要求重复确认同一指令。

核实原请求使用 `canvas_reconcile`。原执行者可复用令牌；接替者先用 `canvas_claim_recovery` 独占领取核实工作。成功补回必须提供同一请求的实际文件，并提交证据：

```json
{
  "request_id": "原请求编号",
  "remote_status": "succeeded",
  "source": "provider_history",
  "reason": "原任务历史记录与结果文件的核实依据"
}
```

`remote_status` 与核实结果一致，可为 `succeeded`、`failed`、`cancelled`；`source` 可为 `provider_history`、`provider_response`、`operator_confirmation`。不能用无依据的说明代替实际核实。保留原提供方编号和错误，不覆盖已完成任务。已证明提供方结束、但本地结果回收或媒体校验失败时，也可取回同一结果；核实从不生成新媒体。

Comfy 的 `VideoSubmissionGuard` 使用机器级串行互斥，覆盖该次提交和整个同步等待周期。持久回执位于应用数据目录 `zero-to-story/video/`，可通过 `LFO_VIDEO_STATE` 指定位置；执行进程丢失后，它继续阻塞未知任务，直到依据原任务证据核实结束。回执编号与对应 Canvas run 的 `request_id` 一致。诊断命令：

```powershell
./.venv/Scripts/python.exe -m lfo.comfy.admission
./.venv/Scripts/python.exe -m lfo.comfy.admission --reconcile REQUEST_ID
```

第二条只查询原 Comfy 历史，证实结束后释放提交占用；它不修改画布采用结论。空队列、本地放弃、缺失任务号都不能证明原任务结束。画布状态与机器级占用各自核实，不能手工删回执绕过未知任务。

## 摘要与交接事件

日常查询使用 `canvas_run(run_id)` 或 `canvas_runs` 的摘要；排错才用 `canvas_run(run_id, full=True)` 读取完整快照和证据。`canvas_read(..., node_id=...)` 只返回目标组件及直接上游。

`canvas_events(after, canvas_id, wait_seconds)` 最多等待 25 秒，只返回持久变更事件。处理前重读任务状态；用同一消费者标识读取 `canvas_event_cursor`，在工作已被实际接手后用 `canvas_ack_event` 保存断点。消费者标识与画布筛选范围保持一致，不能跨不同范围共用断点。重复事件不会使同一任务被重复领取。通知断点恢复不重放媒体生成。

事件保存不等于后台唤醒。当前活跃会话可用宿主的真实继续执行操作触发下一步；未接入空闲唤醒的宿主保留待交接任务，下一次活跃时接手，不能宣称无人值守执行。

## 实际媒体、连续镜头与后期

故事审查分开视觉和音频证据。关键剧情遗漏、身份/物理关系错误、对白缺失和主体遮挡需要修复；不影响剧情和连续性的自然动作差异可说明后采用。看不清、听不清或 ASR 有歧义时记为 `INCONCLUSIVE` 并局部复核，不把分析器说明当作台词。

有采用要求时，完成必要后期后，通过 `canvas_claim_review` 取得审片令牌，再用 `canvas_review` 记录结论、实际文件、证据、实际末态及 `unverified`。`ACCEPT` 不能带关键未核实项。文件摘要由服务计算。不要把生成成功直接视为采用。

已完成的 `INCONCLUSIVE` 可用 `canvas_reopen_review(run_id, reason, expected_updated_at)`（HTTP `POST /api/runs/{id}/reopen-review`）显式重开：先读取最新 run，把 `updated_at` 原样传入并写明具体复核原因。服务以 CAS 检查版本，竞争只允许一次成功；返回新的独占 `owner_token`，旧令牌失效。完整旧 review、原 reviewed_at、重开原因和时间保存在 run 的 `review_history` 中，新轮当前 review 清空。未完成的审查占用不抢占，`ACCEPT`/`REJECT` 不允许重开。新轮可绑定本 run 输出目录内已核验的实际派生文件，继续由服务计算 SHA-256；原媒体和生成记录保留，不重生成。

已完成 `REJECT` 的视频若有实际后期修复，用 `canvas_review_derived`（HTTP `POST /api/runs/{id}/review-derived`）一次登记新派生的最终审片。正文为 `reason`、最新 `expected_updated_at`、`decision`（仅 `ACCEPT` 或 `REJECT`）、`output_path`、非空 `evidence`，可附 `end_state`、`unverified`；`ACCEPT` 仍不允许关键未核实项。此入口不需要 claim 或令牌，只允许 `succeeded` 且当前完整 `REJECT`，不抢占未完成审查，也不修改原审片入口的终态规则。

派生必须位于原 run 输出目录，路径及 SHA-256 均不同于历次被拒绝文件，也不能覆盖原生成输出；改名但同内容不算新派生。服务验证被拒绝源文件仍完整，校验派生元数据并完整解码视频及音轨，确认文件在检查期间未变化后，在确认锁和事务 CAS 内将旧 review、原审片时间、具体原因及新文件绑定写入已有 `review_history`，原子登记新 review。当前 review 绑定新文件，旧媒体、生成 snapshot、outputs 和 provider ID 均保留；不会新建生成请求、重新生成或自动替换画布草稿。旧版本并发请求失败后须重新读取，不能无依据反复提交。

需要连续性时，在连线上指定 `source_run_id` 和 `require_accept: true`，绑定已采用的具体运行。实际末态记录人物位置、朝向、姿态、物品、接触和已完成动作，只写可观察事实。需要精确尾帧时，接受后从实际采用版本提取，调用 `canvas_import_media` 取得文件引用与 `sha256`，保存为该视频的 `derived_outputs`，记录 `source_run_id`，通过 `output:<id>` 连接下一镜。已在工作区中的文件会原位引用。普通连线仍可读取最近成功结果。

`canvas_readiness` 检查当前镜头的输入与采用条件，不冻结输入、不提交生成。采用文件或其来源发生变化会阻止后续确认；已确认请求继续使用原固定文件。不要原地覆盖已采用媒体。

准确汉字、字幕、题签和说明插页在导演方案中分配给后期或独立静态卡片。生成画面的多余文字遮挡主体时按采用标准处理，不能把加强提示词当作保证。

已有视频可使用通用语音保护剪辑入口。所有时间均为实际源文件的毫秒值；例子仅说明格式，不是当前素材的剪辑依据：

```json
{
  "source_path": "original.mp4",
  "output_path": "edited.mp4",
  "confirmed_silent_intervals": [{"start_ms": 0, "end_ms": 300}],
  "protected_speech_intervals": [{"start_ms": 500, "end_ms": 5710, "tail_margin_ms": 400}],
  "subtitle_cues": [{"start_ms": 500, "end_ms": 5710, "text": "已核实的对白"}]
}
```

```powershell
./.venv/Scripts/python.exe -m lfo.media.edit_cli EDIT_JSON
./.venv/Scripts/python.exe -m lfo.media.edit_cli EDIT_JSON --apply
```

默认只探测实际时长并返回时间映射；`--apply` 使用同一映射剪切音画并写出对应字幕。执行者需先核实可删除区间，保护对白及句尾余量；不依据 VAD 或 ASR 自动删音，不改变人声速度。`--apply` 是写出开关，不增加新的用户审批。后期结果仍需检查实际音画和字幕。

## 数据与验证范围

内部 SQLite、快照、事件和临时输入位于配置的应用数据目录；媒体位于 `workspace/assets/uploads/` 与 `workspace/projects/<canvas_id>/outputs/<run_id>/`。数据库通过增量迁移保留历史请求、媒体路径和状态；旧成功记录不自动变成 `ACCEPT`。不整理或重建用户数据来完成升级。

事件记录阶段和接手时间，固定快照记录后端、参数与引用，Comfy 成品保存探测到的时长和尺寸。资源状态、模型用量只记录实际取得的数据；普通等待秒数不能换算成 token，单次成功不能证明性能原因。

后端测试使用隔离数据和模拟提供方；前端运行 `npm test`、`npm run build`。跨宿主协议测试不能替代另一产品的原生委派与唤醒实测；真实音画剪辑需要本机 FFmpeg/FFprobe。测试与文档整理不触发图片、视频或付费分析请求。
