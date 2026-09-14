# 画布操作接口

## 通用导入、编辑与真实尾帧

完整故事图使用本 Skill 的 `scripts/import_workspace.py` 及 JSON manifest，先 `--dry-run` 验证稳定节点 ID、素材路径和连线，再导入。已有画布使用 `CanvasClient.edit(canvas_id, version, operations)` 精确更新；版本冲突后重新读取完整画布并重新应用本次操作，不用新版本号提交旧图，不以历史 Markdown 覆盖当前提示词。

R2V 图片顺序等于实际 `reference_image` 边顺序与 `<Picture N>` 顺序。项目 `scripts/r2v_wire.py` 要求显式画布 ID，冲突即停止保存；替换图片引用时保留其他组件、视口、选择和工作空间信息。`related` 不参与生成。

查看原运行使用 `python -m lfo.canvas call GET /api/runs/<run_id>`；修改提示词使用版本化 `edit` 的 `update_node` 操作，不再复制章节专用提交脚本。审片辅助使用 `scripts/qc_video.py <video> <新的输出目录>` 提取抽样帧和响度；它不作内容判断，不记录 ACCEPT，不提取接力尾帧。

已 ACCEPT 的视频需要下一镜首帧时，从项目根运行：

```powershell
./.venv/Scripts/python.exe scripts/accepted_tail.py <run_id>
```

工具读取当前运行与采用摘要，完整解码并在该 run 输出目录创建唯一真实尾帧；不提交生成、不自动连线。将返回项追加到源视频节点 `data.derived_outputs`，保留既有项；源边使用 `sourceHandle: "output:<返回的 id>"`，并设置 `source_run_id` 与 `require_accept: true`，连接目标 `first_frame`。保存仍使用最新版本。再次确认时画布核实尾帧及采用源文件摘要；禁止用普通资产边绕过采用来源检查。

优先使用项目 MCP `story_canvas` 的工具。若当前会话尚未加载新增工具，从项目根用 `.venv/Scripts/python.exe -m lfo.canvas open` 启动/找到页面，使用 `python -m lfo.canvas call METHOD /api/... --body-file <JSON文件>` 调用相同服务。这里的 python 指项目解释器；临时 JSON 放系统临时目录，避免占用创作工作区。

宿主连接配置放在对应宿主的项目级配置中；仓库的 `.codex/config.toml` 只是当前 Codex 连接示例，不是其他宿主的必需配置。工具新增后需要宿主重新加载；普通 CLI 交接立即可用。完整启动与字段说明见 [画布使用指南](../../../../guides/canvas-guide.md)。

| 操作 | 接口 |
|---|---|
| 可用能力与字段 | GET /api/capabilities |
| 画布列表、新建 | GET /api/canvases；POST /api/canvases，正文 name |
| 读取当前配置 | GET /api/canvases/{id} |
| 保存配置 | PUT /api/canvases/{id}，正文 version、graph、可选 name |
| 导入本地媒体 | POST /api/assets/import，正文 path |
| 确认生成 | POST /api/canvases/{id}/runs，正文 node_id、version、request_id |
| 查询结果/待办 | GET /api/runs 或 GET /api/canvases/{id}/runs |
| 领取 Agent 请求 | POST /api/runs/{id}/claim，正文 `host_tools:[当前会话实际工具标签]` |
| 回填结果 | POST /api/runs/{id}/complete，正文 `owner_token`、`status`、`outputs`，可选 `error`、`provider_task_id`、`stage`、`evidence` |
| 取消未开始请求 | POST /api/runs/{id}/cancel，正文空对象 |
| 记录进度 | POST /api/runs/{id}/progress，正文 `owner_token`、`stage`，可选 `provider_task_id`、`evidence` |
| 本地关注状态 | POST /api/runs/{id}/attention，正文 `state`、`reason` |
| 接替未知请求核实 | POST /api/runs/{id}/claim-recovery，正文 `reason`；再 POST /api/runs/{id}/reconcile，正文 `owner_token`、`status`、`evidence`，成功时附 `outputs` |
| 领取内容审片 | POST /api/runs/{id}/claim-review，正文空对象；普通组件不要求 |
| 回填内容审片 | POST /api/runs/{id}/review，正文 `owner_token`、`decision`、`output_path`、`evidence`，可选 `end_state`、`unverified` |
| 登记接续范围 | POST /api/continuations，正文 `canvas_id`、`canvas_version`、`session_id`、`node_ids`、`authorization`，变更附当前 `revision` |
| 只读接续检查 | GET /api/continuations，可按 `session_id`、`canvas_id` 同时筛选；返回 `plans[].summary` |
| 记录真实单元交接 | POST /api/continuations/{id}/units，正文 `revision`、`unit_id`、`state`，实际 `agent_id` 与可选 `turn_id`、`node_id`、`run_id`、`reason` |
| 暂停或恢复接续 | POST /api/continuations/{id}/state，正文 `revision`、`state`，暂停附 `reason` |

接续记录不会创建生成请求，也不等于授权或内容接受。主会话在宿主真实派发成功后才登记 `dispatched`，处理返回结果后登记 `handled` 或 `blocked`。当前 Codex hooks 的信任、加载限制和空闲接续条件见[接续指南](../../../../guides/canvas-continuation.md)。

graph 包含 nodes、edges、viewport、selection，以及可选 workspace（story、chapter、summary、source 与扩展元数据）。节点为 `{id,type,position:{x,y},data:{...}}`，类型为 asset、image、video、document、section。边为 `{id,source,target,sourceHandle:"output",targetHandle}`。输入端口为 first_frame、last_frame、reference_image、reference_video、reference_audio。图片参考也使用 reference_image。`output:<派生输出id>` 读取源组件 derived_outputs 内固定的素材；普通 output 读取最新成功成品，没有成功运行时读取 data.asset。

资料关联使用 targetHandle=related，允许连接除 section 外的任意组件；不会成为执行输入。document 的 content 与 section 的 width/height 都保存在 data 中；category、panel_id、description、status、source_path 用于章节资产定位和溯源。MCP/客户端的 workspace 编辑操作为 `{op:"workspace",patch:{story,chapter,summary}}`，仅更新所给字段；设为 null 会移除该字段。

视频节点 data 保存 label、prompt、provider、model、mode、duration、aspect_ratio、megapixels、options；专属选项位于 options[provider]。必填字段和范围以当前能力说明为准。提示词直接属于该媒体组件。data.asset 为 `{path,kind,name}`，使用导入返回值；generation_snapshot 保存原成品实际使用的提示词、参数与输入。history 为 `{id,label,asset,generation_snapshot,status?,source_path?}` 数组，derived_outputs 为 `{id,label,asset,source_version?}` 数组。历史查看不会修改草稿或当前输出。镜头故事板正文可存 data.content。

生成请求 request_id 在一次请求重发时保持不变。新一轮明确生成使用新编号。领取后输出的 execution_snapshot 是实际执行依据；不要再次读取草稿取代它。

成功 outputs 格式为 `[{"path":"实际本地文件路径","kind":"image 或 video","name":"显示名称"}]`。已有成品的 snapshot 是只读生成依据，不是修改入口。未知状态只能通过 `claim-recovery` 后的 `reconcile` 以原任务证据核实，不能用空说明解除，也不自动重提。状态、审片、能力标签和事件语义见[画布与视频生产指南](../../../../guides/canvas-guide.md)。
