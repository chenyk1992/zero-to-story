# Handoff 对照表：短剧剧本 → 项目桥接包

本文件供 `/桥接` 使用。目标：让 `episodes/epNNN.md` 伴生出可交给 **zero-to-story** 与 **LFO intake** 的产物，而不改写编剧正文、不生成完整 `storyboard.json`。

---

## 1. 产物分层

| 层 | 路径 | 消费者 | 是否改写 ep 剧本 |
|----|------|--------|------------------|
| 编剧主产物 | `episodes/epNNN.md` | 人类审剧 / 导出 | 否 |
| 桥接包 | `handoff/epNNN/*` | zero-to-story / LFO | 否（只读 ep） |
| 管线 JSON | `workspace/.../storyboard.json` | `lfo run` | 本 skill **不产出** |

---

## 2. 字段对照

| 短剧来源 | handoff 落点 | 规则 |
|----------|--------------|------|
| 集标题 + logline 切片 | `storyboard_brief.md` → 故事梗概 | 2–3 句，只含本集可拍主线 |
| `characters.md` 叙事档案 | `characters_visual.md` + brief 角色列表 | 只留外貌/服饰/标志特征/关键道具；动机弧光可附一行「表演提示」但非必填 |
| 场次标题（地点·时间·内外） | brief「场景列表」 | 3–6 场压成 **1–2** 个场景；合并同地点多场次 |
| △ 镜头描写 | brief「分镜列表」画面描述 | 每条必须补全空间关系（前景/中/远、左/右/中） |
| 景别中文（全景/中景/近景/特写…） | 分镜表「景别」列 | 保持中文；生成 LFO JSON 时再映射英文 enum |
| 角色对白（15–25 句） | 分镜表「角色台词」 | **不逐句上镜**；每镜 0–1 句关键台词，其余写「无」 |
| ♪ 音乐提示 | cut_notes 或分镜「音效设计」 | 默认环境声/动作声；叙事 BGM 不强制进镜 |
| 🎣 钩子 / 下集预告 | **仅** `cut_notes.md` | 禁止写入分镜表与 intake constraints |
| 💰 付费墙信息 | cut_notes | 同上 |
| 情绪强度 / 关键词 | intake `mood` / `custom` + brief 项目信息 | 与本集一致 |
| 全剧类型/基调 | `handoff/project.json` | 剧级默认值 |

---

## 3. 时长与镜头数（对齐 zero-to-story）

| 目标时长 | `target_duration_ms` | 目标镜头数 |
|----------|----------------------|------------|
| 15 秒 | 15000 | 8 |
| 30 秒 | 30000 | 15 |
| 45 秒 | 45000 | 22 |
| 60 秒 | 60000 | 29 |

竖屏短剧默认：**45 秒 / 22 镜 / 9:16**。用户另有指定则覆盖，并同步改 brief 与 intake。

---

## 4. 约束默认值（intake）

| 字段 | 短剧默认 |
|------|----------|
| `aspect_ratio` | `9:16` |
| `delivery_width` / `height` | 1080 / 1920 |
| `max_characters` | 2–3（本集出镜） |
| `max_scenes` | ≤2 |
| `pacing` | 按基调：悬疑偏 `fast`/`medium`，轻喜偏 `medium` |
| `audio_policy` | `full`（对白+音效）；纯画面实验用 `effects_only` |
| `sources[].type` | `screenplay` |
| `sources[].content` | 「本集视觉剪辑版」摘要正文（含精简场次与关键对白），可注明源文件相对路径 |

---

## 5. 场次折叠示例

源剧本 4 场：走廊危机 / 高档大堂 / 骑行接单 / 出租屋。

折叠建议：

1. **场景 A — 夜城跑腿外景+大堂**（社死冲突 + 接单钩子）
2. **场景 B — 老旧公寓走廊**（开场闪回危机，可作片头或片尾镜组）

出租屋若仅作情绪缓冲，可并入场景 A 的「室内中转」2–3 镜，或删镜以保时长。

---

## 6. 角色叙事 → 视觉卡

| 保留 | 丢弃或降级到 cut_notes |
|------|------------------------|
| 年龄外观、发型、体型 | 核心动机长文 |
| 服饰（骑手头盔雨衣、睡袍、相机包） | 人物弧光全文 |
| 标志动作/道具（歪戴头盔、双机位包、两碗面） | 秘密剧透（可一句「表演暗示」） |
| 一句辨识台词（可选） | 反派四阶关系网 |

---

## 7. 复制到 LFO workspace（人工/agent）

对齐 `workspace/<小说名>/<章节名>/`：

| 短剧侧 | workspace 侧 |
|--------|----------------|
| 剧名 `{drama_title}` | `workspace/{drama_title}/`（小说名根目录） |
| 第 N 集 `epNNN` | `chapter_NN/`（如 ep001 → `chapter_01`） |
| intake `project_id` | 必须 `{drama_title}-chapter_NN`（剧级 `handoff/project.json` 只用 `novel_id`，不写章节 project_id） |

```
.short-drama/{drama_title}/handoff/ep001/intake.json
  → workspace/{drama_title}/chapter_01/intake.json

.short-drama/{drama_title}/handoff/ep001/storyboard_brief.md
  → workspace/{drama_title}/chapter_01/storyboard_brief.md
```

示例：《午夜不接单》第 1 集 → `workspace/午夜不接单/chapter_01/`

随后走现有流程：审 brief →（可选）zero-to-story 视觉链路，或 LFO decompose → `storyboard.json` → `lfo run`。
