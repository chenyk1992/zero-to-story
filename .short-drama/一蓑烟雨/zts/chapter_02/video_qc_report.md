# 《一蓑烟雨》第二章·范滂传｜最新创作预检版成片 QC 报告

## 交付结论

**PASS｜可交付观看**

本版先完成创作蓝图静态预检，再按 P001→P012 逐镜生成；同场镜头使用上一镜实际接受尾帧作为下一镜首帧，硬切场景重新绑定角色与分镜板。12 个 Panel 均完成 LFO 生成、音频混合、技术 QC、真实尾帧提取，最终组装完成。

## 成片信息

- 视频：`workspace/projects/yisuo-ep002-codex-director/final/yisuo-ep002-v2-final/yisuo-ep002-v2-assembly-r001-run-b2d3d9008c9b.mp4`
- 字幕旁路文件：同目录下的 `yisuo-ep002-v2-assembly-r001-run-b2d3d9008c9b.srt`
- 导出清单：同目录下的 `yisuo-ep002-v2-assembly-r001-run-b2d3d9008c9b.mp4.manifest.json`
- 总运行：`run-b2d3d9008c9b`
- 时长：136.500 秒（12 个编码 Panel 的自然帧尾增量）
- 画幅：1080×1920，9:16 竖屏
- 帧率：24fps
- 视频：H.264
- 音频：AAC，48kHz，双声道
- 拼接：12 段 cut 硬切，无跨场景溶解

## 创作前置检查

- [x] `creative_blueprint.json` 通过 `validate_creative_blueprint.py` 静态预检
- [x] 以 `episodes/ep002.md` 为唯一剧情源，排除与第一章重复的送笔桥段
- [x] P006 原文顺序固定为“父亲评价 → 苏轼反驳 → 离开 → 最亮的一个”
- [x] 巢儿在全部相关提示词中固定为 17 岁男性 household worker
- [x] P001/P005/P007/P010 使用角色/分镜板 R2V；其余同场段落使用真实尾帧 I2V

## 技术质检

- [x] 12/12 Panel 的 `video.generate`、`audio.mix`、`media.qc`、`subtitle.render` 通过
- [x] 总时间线 `timeline.assemble` 与 `export.finalize` 通过
- [x] `ffprobe` 检查通过：1080×1920、24fps、H.264、AAC、48kHz、双声道
- [x] 全片 FFmpeg 解码检查通过，无解码错误
- [x] 字幕已烧录，同时输出旁路 SRT
- [x] 全片接触表：`outputs/run-b2d3d9008c9b/qc/final_contact.png`
- [x] 11 个相邻边界证据已写入 `outputs/run-b2d3d9008c9b/global/boundaries/`

## 连续性证据

- 同场边界 `P001→P002`、`P003→P004` 达到 exact-frame candidate；其余同场边界均保留高相似度或由下一镜动作自然推进。
- 硬切边界 `P004→P005`、`P006→P007`、`P009→P010` 的低相似度属于预设的书斋→井台、井台→灶房、灶房→廊下场景切换，不将跨场景像素相似度误判为连续性缺陷。
- 真实接力尾帧：`assets/tails/chapter2-v2-tail_P001.png` 至 `chapter2-v2-tail_P012.png`

## Panel 执行记录

| Panel | 运行 ID | 模式 | 接受时长 |
|---|---|---|---:|
| P001 | `run-07c52c687449` | R2V | 10.083s |
| P002 | `run-33008270883d` | I2V | 15.083s |
| P003 | `run-573de4baa19a` | I2V | 13.083s |
| P004 | `run-2ff18f409036` | I2V | 14.083s |
| P005 | `run-1fcf0c299388` | R2V | 10.083s |
| P006 | `run-a3ca4537e077` | I2V | 11.083s |
| P007 | `run-8e334c768593` | R2V | 10.083s |
| P008 | `run-56b567ee6514` | I2V | 11.083s |
| P009 | `run-cf9d25d7b4d7` | I2V | 10.083s |
| P010 | `run-a6da84833034` | R2V | 8.000s |
| P011 | `run-072cd3486a6c` | I2V | 13.083s |
| P012 | `run-dfc79c4c1892` | I2V | 10.083s |

## 复现与资产

- 项目根目录：`workspace/projects/yisuo-ep002-codex-director/`
- 创作蓝图：`.short-drama/一蓑烟雨/zts/chapter_02/creative_blueprint.json`
- 执行包：项目根目录下 `execution-package-v2-p001-r001.json` 至 `execution-package-v2-p012-r001.json`
- 最终组装包：`assembly-package-v2-r001.json`
