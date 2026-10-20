# 现有正式后期清单扩展

影视、MV、广告复用同一确定性媒体工具；正式 MV 仍调用 `music_tools.py render`，schema 保持 `lfo.mv.edit.v1`。本页只说明新增可选字段；创作主责、Canvas 生成/采用、当前媒体版本和最终视听检查沿用[共同交接](../../canvas-workspace/references/creative-handoff.md)。旧清单不填这些字段时保持原有渲染行为，不新增生产入口。

## 对白窗口内压低主歌曲

顶层 `music_ducking` 是数组，时间使用**成片从零开始的毫秒**，不是原歌时间。先依据实际对白确定窗口；ASR/VAD 可定位候选，不能把估计时码称为已听审。

```json
"music_ducking": [
  {"start_ms": 1200, "end_ms": 2400, "gain_db": -12, "attack_ms": 100, "release_ms": 200}
]
```

从 `start_ms - attack_ms` 开始逐渐压低，`start_ms` 至 `end_ms` 保持指定相对增益，随后在 `release_ms` 内恢复到原音量；渐变裁在成片边界内。默认 -12 dB、100 ms 压低、200 ms 恢复，可按内容改；0 ms 渐变表示直接切换。多个窗口重叠取当时更强的压低值，不叠加 dB；窗口及渐变之外回到原歌曲增益。包络由 FFmpeg 按音频块更新，不是自动声源检测或逐样本口型控制。

窗口必须满足 `0 <= start_ms < end_ms <= 成片总长`，时间和渐变为整数毫秒且渐变非负，增益为有限非正数；字段错误或越界会报错。处理只作用于主歌曲轨，原声和独立对白/音效不被此字段压低，也不会分离混在同一轨的歌声与对白。若对白已混在主歌曲中，该字段会同时压低它，须先取得可独立处理的声源。

通用 `AudioMixer` 的 `AudioTrack.ducking_windows` 使用同样的 `DuckingWindow`。`None` 保持旧 `duck_group=background` 的整轨压低行为，显式 `[]` 关闭该轨自动压低，非空列表按窗口处理并代替整轨压低；其他增益/淡入淡出照常应用。窗口需要明确的 `clip_duration_ms`。MV 的 `music_ducking` 默认空数组，不会因为增加音效而压低整首歌。

## 正式静态图片段与片尾

`segments` 中原视频条目可保持不写 `kind`；静态图片明确写 `kind: image`，使用 `duration_ms`，不携带视频 `source_in_ms/source_out_ms`：

```json
{"kind":"image","path":"ABSOLUTE_IMAGE","sha256":"FILE_SHA256",
 "source_note":"用户提供的片尾图，记录其选定版本和用途证据",
 "timeline_start_ms":3000,"duration_ms":1000,"transition":"cut"}
```

使用实际单帧 PNG/JPEG/WebP/BMP/TIFF，按已有画面分段工具等比适配输出画幅并补边；动画图片、视频伪装成图片与占位类型会被拒绝。图片与视频一起保持连续时间轴，以累计帧边界排布并复用分段缓存。

默认段落合计仍等于采用歌曲窗口。需要在歌曲结束后新增片尾时，顶层显式填写 `postroll_duration_ms`，并让完整 segments 合计等于“采用歌曲窗口 + 片尾延长”；不能只追加段落而不说明总长变化。原歌完整播放原窗口，额外画面默认补静音，不循环、拉伸或更改源歌；明确列出的音效或保留原声仍按其成片位置处理。片尾用字幕时选 `kind: visual`，时码仍沿文字事件的原歌坐标延伸，歌词不能延长到歌曲后的静音区。

## 定时 Logo 与图片叠加

顶层 `image_overlays` 按数组顺序从下向上叠加，最后再渲染已有文字事件：

```json
"image_overlays": [
  {"path":"ABSOLUTE_LOGO_PNG","sha256":"FILE_SHA256",
   "source_note":"已选定的品牌 Logo 与实际用途",
   "start_ms":500,"end_ms":2500,"x":24,"y":24,
   "width":160,"height":80,"opacity":1}
]
```

`start_ms/end_ms` 是成片半开窗口 `[start,end)`，按输出帧时刻显示。`x/y` 是左上角像素位置；`width/height` 为等比缩放的最大框，图片从该位置起放置，不强拉比例。位置/尺寸必须完整在输出画幅内；`opacity` 默认为 1，可取 0～1，与图片自身 alpha 相乘。保留透明背景；不提供人物遮挡、空间跟踪、透视或任意动效。

## 来源、采用与输出

正式视频、图片段和 Logo 都须有实际绝对路径和 SHA-256。Canvas 生成素材记录真实 `run_id`，导入/拍摄素材用 `source_note` 记录来源、选定版本与用途，不伪造 run；视频仍记录真实源片裁切范围。带 `--canvas-id` 时，所有带 run_id 的生成素材核对当前成功 run 的 ACCEPT 路径/摘要；导入素材的视听与用途证据由调用方保存，文字备注本身不证明接受。已知为生成素材时不能改填 source_note 绕过当前 review。

生产统计的画面段数量只计算 `segments`，采用来源同时包含 `image_overlays` 并按当前匹配的 run 去重。按节点范围统计时，条目沿用实际 `node_id`；缺少范围依据或导入来源没有 Canvas review 时，采用来源计数保留 partial，不因此伪造 run，也不据此否定已有导入素材的人工采用证据。

旧回执字段继续保留，新增实际段落类型/图片来源、`music_ducking`、`image_overlays` 和 `postroll_duration_ms`。正式成片仍验证视频帧数与完整音轨时长，输出和回执不得覆盖源文件或已有结果。图片是正式静态内容也不等于人物/动作已生成；技术完成不升级 listening_status，最终核对对白窗内外、Logo 可读性、实际片尾与接缝。

分段缓存须使用独立目录，不得包含输入媒体、编辑清单、音乐时间轴、回执或输出文件；路径冲突在缓存写入前报错，避免缓存文件覆盖来源。

`lfo.mv.preview.v1` 仍是结构预览，拒绝上述非空正式后期字段；需要这些效果时使用同一 `render` 链输出新的候选正式渲染文件并实际审查，不能以预览静帧代替正式后期。
