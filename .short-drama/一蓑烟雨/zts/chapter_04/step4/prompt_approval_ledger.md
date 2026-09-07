# 《一蓑烟雨》第四章·出川 — STEP 4 H3 提示词交接台账

更新时间：2026-09-02（Asia/Shanghai）  
范围：P001–P020，共 20 个独立 Clip / Panel  
当前状态：提示词与 manifest 已获用户确认，20/20 通过 H3 manifest 预检；已记录 `0.4 MP`，进入 LFO 逐 Panel 接力执行。

## 交接规则

- 本台账遵循 `.agents/skills/h3-prompt-writing/SKILL.md`：I2VA 使用唯一 `first_frame`；FL2VA 使用成对 `first_frame` / `last_frame`；R2V 使用 typed `ref_image_N` 槽位和 full-reference 六段式。
- 20 个 Panel 各对应一份提示词和一份 `prompt-manifests/Pxxx.json`；六格 Beat 只作为有序可见时刻，不机械拆成 H3 Shot。
- `prompt_path` 与 manifest 同目录，`prompt_hash` 为提示词 UTF-8 字节 SHA-256；`plan_hash` 为对应 Panel、Panel plan、Camera Setup、对白锁定对象的规范 JSON SHA-256。
- 只交接蓝图 `runtime_input_keys`。P002–P004、P006–P011、P013–P014、P016–P020 的 `board.Pxxx` 全部是 `planning_only`，不出现在任何 manifest `references`。
- 用户已确认提示词并选择 `0.4 MP`；本轮创建带 `lfo.production_lock.v1` 的 VideoExecutionPackage，按 P001 → P020 逐 Panel 接力执行。未获单片/边界 QC 通过前不推进下一段的真实尾帧。

## Panel 交接清单

| Panel | Operation | 时长 | Setup 窗口 | 运行时引用 | 对白 | 提示词 | Manifest | 状态 |
|---|---|---:|---|---|---|---|---|---|
| P001 | `video.reference_to_video` / R2V | 7.0s | C001 0–3 / C002 3–7 | board.P001 + character.chaoer + character.su_zhe | — | `prompt-manifests/P001_h3_prompt_v01.md` | `prompt-manifests/P001.json` | 待确认 |
| P002 | `video.image_to_video` / I2V | 9.0s | C003 0–9 | boundary.P001.last_frame | D001 | `prompt-manifests/P002_h3_prompt_v01.md` | `prompt-manifests/P002.json` | 待确认 |
| P003 | `video.image_to_video` / I2V | 8.0s | C004 0–5 / C005 5–8 | boundary.P002.last_frame | D002 | `prompt-manifests/P003_h3_prompt_v01.md` | `prompt-manifests/P003.json` | 待确认 |
| P004 | `video.image_to_video` / I2V | 10.0s | C006 0–3 / C007 3–10 | boundary.P003.last_frame | D003 | `prompt-manifests/P004_h3_prompt_v01.md` | `prompt-manifests/P004.json` | 待确认 |
| P005 | `video.reference_to_video` / R2V | 5.0s | C008 0–2 / C009 2–5 | character.su_shi + character.chaoer + board.P005 | — | `prompt-manifests/P005_h3_prompt_v01.md` | `prompt-manifests/P005.json` | 待确认 |
| P006 | `video.image_to_video` / I2V | 10.0s | C010 0–10 | boundary.P005.last_frame | D004 | `prompt-manifests/P006_h3_prompt_v01.md` | `prompt-manifests/P006.json` | 待确认 |
| P007 | `video.image_to_video` / I2V | 7.0s | C011 0–3 / C012 3–7 | boundary.P006.last_frame | D005 | `prompt-manifests/P007_h3_prompt_v01.md` | `prompt-manifests/P007.json` | 待确认 |
| P008 | `video.image_to_video` / I2V | 12.0s | C013 0–4 / C014 4–12 | boundary.P007.last_frame | D006 | `prompt-manifests/P008_h3_prompt_v01.md` | `prompt-manifests/P008.json` | 待确认 |
| P009 | `video.image_to_video` / I2V | 5.0s | C015 0–2 / C016 2–5 | boundary.P008.last_frame | — | `prompt-manifests/P009_h3_prompt_v01.md` | `prompt-manifests/P009.json` | 待确认 |
| P010 | `video.image_to_video` / I2V | 9.0s | C017 0–2 / C018 2–9 | boundary.P009.last_frame | D007 | `prompt-manifests/P010_h3_prompt_v01.md` | `prompt-manifests/P010.json` | 待确认 |
| P011 | `video.image_to_video` / I2V | 12.0s | C019 0–12 | boundary.P010.last_frame | D008, D009 | `prompt-manifests/P011_h3_prompt_v01.md` | `prompt-manifests/P011.json` | 待确认 |
| P012 | `video.reference_to_video` / R2V | 6.0s | C020 0–3 / C021 3–6 | character.chaoer + character.su_shi + board.P012 | — | `prompt-manifests/P012_h3_prompt_v01.md` | `prompt-manifests/P012.json` | 待确认 |
| P013 | `video.image_to_video` / I2V | 13.0s | C022 0–4 / C023 4–13 | boundary.P012.last_frame | D010, D011 | `prompt-manifests/P013_h3_prompt_v01.md` | `prompt-manifests/P013.json` | 待确认 |
| P014 | `video.image_to_video` / I2V | 9.0s | C024 0–9 | boundary.P013.last_frame | D012 | `prompt-manifests/P014_h3_prompt_v01.md` | `prompt-manifests/P014.json` | 待确认 |
| P015 | `video.reference_to_video` / R2V | 12.0s | C025 0–12 | character.su_shi + character.su_zhe + board.P015 | D013 | `prompt-manifests/P015_h3_prompt_v01.md` | `prompt-manifests/P015.json` | 待确认 |
| P016 | `video.image_to_video` / I2V | 10.0s | C026 0–10 | boundary.P015.last_frame | D014 | `prompt-manifests/P016_h3_prompt_v01.md` | `prompt-manifests/P016.json` | 待确认 |
| P017 | `video.image_to_video` / I2V | 13.0s | C027 0–8 / C028 8–13 | boundary.P016.last_frame | D015, D016 | `prompt-manifests/P017_h3_prompt_v01.md` | `prompt-manifests/P017.json` | 待确认 |
| P018 | `video.first_last_frame` / FL2V | 6.0s | C029 0–3 / C030 3–6 | boundary.P017.last_frame + keyframe.P018.last | — | `prompt-manifests/P018_h3_prompt_v01.md` | `prompt-manifests/P018.json` | 待确认 |
| P019 | `video.image_to_video` / I2V | 8.0s | C031 0–8 | boundary.P018.last_frame | D017 | `prompt-manifests/P019_h3_prompt_v01.md` | `prompt-manifests/P019.json` | 待确认 |
| P020 | `video.first_last_frame` / FL2V | 9.0s | C032 0–9 | boundary.P019.last_frame + keyframe.P020.last | D018 | `prompt-manifests/P020_h3_prompt_v01.md` | `prompt-manifests/P020.json` | 待确认 |

## 预检结果

| 检查 | 结果 |
|---|---|
| H3 manifest schema / prompt_path / prompt_hash | 20/20 PASS |
| Setup 时间窗与 creative_blueprint 对齐 | 32/32 Setup PASS |
| 对白事件、speaker_id、原文和时间窗 | 18/18 PASS |
| operation 与引用能力 | 20/20 PASS |
| planning-only 分镜板误入运行时引用 | 0 个 |
| 蓝图静态预检 | `CREATIVE PREFLIGHT: PASS` |

## 用户确认闸门

用户已确认视觉控制资产、H3 提示词，并明确选择 `0.4 MP`；已将 manifest 与已确认素材编译为 `lfo.video-execution.v1`，交给 LFO 选择 H3 后端。任何提示词修订必须保持相同 Setup 窗口、对白事件、引用槽位和 `plan_hash`，只更新 `prompt_hash`。
