# MV 生产检查与结构预览

本页衔接[生产交接](production-handoff.md)和[后期验收](finishing-and-review.md)。只读检查不生成媒体、不改变采用结论；脚本工具只处理已有媒体。所有路径使用绝对路径，输出写入本项目目录中的新文件，不能覆盖已采用产物。

## 当前 Panel 的提交前检查

新 MV 在 `graph.workspace.mv_production` 保存 `schema_version: 1` 元信息，只对 `panels` 中列出的视频节点启用。普通视频和未登记的旧画布沿用原规则；不得为补元信息重新生成旧镜头。结构与字段以 `src/lfo/canvas/mv_preflight.py` 的当前 schema 为准。

- `script`：画布 document 节点 ID 和创作版本。每个 Panel 保存源正文中确实存在的 `script_excerpt`，只绑定相关镜头片段；其他章节修订不使该镜头自动过期。
- `song`：实际采用音频的节点、来源、SHA-256 与真实时长。生成歌曲引用成功 run 的当前 ACCEPT 文件；导入歌曲绑定音频 asset，并以 `imported_selection` 记录 `decision: ACCEPT`、`asset_sha256`、`source`、`evidence`（选定版本及实际听审依据），不伪造 run。
- `panels[node_id]`：`shot_id`、`song_window_ms: {start,end}`、模式和 `input_bindings`。逐项记录绑定 ID、真实槽位、来源节点/run、SHA-256 与用途。无参考的 T2V 可为空数组；`related` 资料边不算生成输入。
- 人工核对可见演唱或说唱的 Panel：当前模式须为 R2V，确认前核对画布连线与当前输入确有同一歌曲窗口的 `reference_audio`，确认后再核对冻结快照；首帧可另作为 R2V 第 0 帧引导。若缺少音频或窗口不符，该 Panel 不提交；纯动作、空镜和不需张口的镜头不强加此项。当前 `input_bindings` 只枚举图片输入，结构检查不会替代这一音频与镜头语义核对。
- `text_events`：只有交给 H3 生成的上屏原文才要求准确事件图 `binding_id` 和 `visual_check`，其中 `decision: ACCEPT`、`asset_sha256`、原文 UTF-8 的 `text_sha256` 与实际可读性 `evidence` 对应；`post` 后期文字不要求 H3 图片。检查器核对声明及文件，不能读取像素、判断排版或替代人眼验收。
- `continuity`：真实连续动作才引用已 ACCEPT 前片的实际尾帧、来源 run 和摘要，并作为下一段 `first_frame`。换场硬切不建立尾帧依赖。
- 首次代表试片可标 `representative: true`，先生成、检查再记录实际证据；后续同类扩展标 `requires_representative: true`，使用 `representative_evidence` 引用已采用样片，写明模式及 `scope` 的 `shot_ids`、`roles`、`sample_window_ms`，绑定歌曲、相关脚本片段与真实图片版本。不能把一次试片的证据套用于所有新歌词、新构图或新动作。

Canvas 的 `readiness` 返回当前声明与依赖的具体缺口；`confirm` 在创建请求之前再核对真实文件字节及歌曲时长，并冻结 `production_context`。元信息变化或采用文件改变后，历史请求的 `matches_current` 反映过期；不会自动重提。实际字形、连续运动、空间遮挡和音画同步仍按后期验收检查。

```powershell
./.venv/Scripts/python.exe .agents/skills/music-video-creator/scripts/music_tools.py preflight --canvas-id CANVAS_ID --node-id PANEL_ID --output NEW_CHECK_JSON
```

## 先做整曲结构预览

锁定采用歌曲及时间轴后，在大批视频生成之前组织一版整曲结构预览。已有可用视频、构图图片和未生成位置共同覆盖采用窗口；检查段落发展、镜头停留、高潮与留白，再生成相关素材。不是所有镜头必须先生成才能粗剪。

使用独立清单 `schema: lfo.mv.preview.v1`，保存 `music_timeline`、`width/height/fps`、连续排列的 `segments` 和可选 `text_events`。每段写 `timeline_start_ms`、`duration_ms`，并写一种 `media`：

```json
{"type":"video","path":"ABSOLUTE_VIDEO","sha256":"FILE_SHA256","source_in_ms":0,"source_out_ms":4000}
{"type":"image","path":"ABSOLUTE_IMAGE","sha256":"FILE_SHA256"}
{"type":"placeholder","label":"副歌：街头全景，尚未生成"}
```

预览在占位时间段烧录“MV 预览 · 待生成”及描述，需要本机 FFmpeg 的 ASS 滤镜和可用中文字体。图片只是静态构图，视频只用于实际已有范围；无素材段不伪造 run ID。使用实际主歌曲，不拉伸或循环歌曲。粗剪文件和回执均标为 preview；字形/运动通过、已生成数量及正式交付不得由占位推断。

```powershell
./.venv/Scripts/python.exe .agents/skills/music-video-creator/scripts/music_tools.py preview --edit PREVIEW_JSON --output NEW_PREVIEW_MP4 --receipt NEW_RECEIPT_JSON
```

## 可恢复的分段后期

正式清单仍为 `lfo.mv.edit.v1`。`render` 先校验实际源文件与哈希，以累计帧边界排列片段，按源片真实帧率裁切，然后拼接画面、处理声音及字幕。源范围不足时报错，不冻结尾帧或自动放慢素材补足。`replace` 不处理无需保留的原音；`mix` 对真实原音与无音片段分别处理。

默认缓存位于输出文件旁的隐藏分段目录，或通过 `--cache-dir` 指定本项目中间产物目录。缓存键绑定文件内容、裁切、输出规格及效果；命中时还核对缓存文件与技术规格。重跑复用有效片段，损坏片段重建。末次拼接失败不会删除有效分段；缓存不构成素材 ACCEPT，也不能覆盖已有媒体。当前源片帧序按真实名义帧率计算，变帧率素材尚未独立验证；遇到这类素材先核实时间戳或制作可追溯的恒定帧率派生版，不宣称毫秒剪辑已精确验证。

```powershell
./.venv/Scripts/python.exe .agents/skills/music-video-creator/scripts/music_tools.py render --edit EDIT_JSON --output NEW_VIDEO --canvas-id CANVAS_ID --receipt NEW_RECEIPT_JSON
```

`--canvas-id` 核对视频清单与当前成功 run 的 ACCEPT 路径和哈希。主歌曲、音效及最终文件的视听采用仍由调用方核对。回执记录输出规格、实际帧区间、缓存复用与媒体摘要，不能把技术通过标成全片内容通过。修改字幕、声音或切点产生新版本，检查受影响接缝后再交付。

## 有证据的进度与交付

`GET /api/canvases/{id}/production` 与 `canvas_production_summary` 返回同一只读统计，页面制作进度也使用它。区分运行请求、接受来源与成片片段；接受来源只有实际编辑清单与当前 review 匹配时可计数，同一来源多次剪辑只算一个来源。

清单引用登记到 `graph.workspace.production_summary` 的 `edit_manifest_path` 与必填 `edit_manifest_sha256`，文件须位于当前项目媒体目录且不超过 4 MiB。缺少、越界或变更的清单不能给出已核实采用数量，页面显示原因。此接口统计当前整张画布，接续提示来自最近更新的计划，并非全画布完成结论；页面原接续面板仍展示各计划。

耗时从持久事件边界推导，区分整段墙钟跨度和任务累计跨度。缺少事件边界显示 unknown，只有部分任务可计显示 partial；资源等待须有明确记录，不能从任务空闲或 `updated_at` 推断。审片领取至登记只表示观察到的跨度，不宣称模型计算时间；不显示虚构完成时间。

```powershell
./.venv/Scripts/python.exe .agents/skills/music-video-creator/scripts/music_tools.py production --canvas-id CANVAS_ID --output NEW_STATS_JSON
```

正式交付核对：全片视听反馈绑定最终实际文件/摘要；Canvas 中已有交付节点指向正式文件；计划、歌词方案、编辑清单与回执可访问；接续范围已结束或有明确等待项。清理只针对已核实无引用的临时文件，不删除仍被采用的源片、真实尾帧或用户资产。
