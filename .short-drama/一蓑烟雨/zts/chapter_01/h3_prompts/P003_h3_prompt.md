# EP001 · P003 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P003｜时长 15.0s｜画幅 9:16｜Shot S011-S016｜场景 A→B 州城门外长街（末格黑场）
> 参考素材：board_P003.jpg + char_su_shi_middle.jpg + char_chaoer_middle.jpg
> 状态：v3 重写（2026-08-27）— 增强追踪镜头+黑场冲击力+巢儿追车情感

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| 镜头 | 已较好（跟踪+推镜） | 增强：更流畅的跟踪镜头，背景的"跟拍"感 |
| 黑场 | 仅末格切黑 | 车轮碾过石头→黑场，加入"cut to black"音效冲击 |
| 巢儿追车 | 有但情感不够 | 增加：跌倒→爬起→继续追，三次挣扎，强化绝望 |
| 环境 | 冻结 | 加入：纸钱飘落、香火闪烁、人群低泣的环境动态 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, the funeral-street atmosphere, and the hard cut to black at the end.
<Subject 1> is the middle-aged Su Shi in the character reference card: a tall, lean scholar with a short beard, frost-touched temples, and hair tied in a topknot, wearing a plain moon-white cross-collar robe, a rough wooden cangue clamped on his shoulders, seated inside the prison van.
<Subject 2> is the middle-aged Chao'er in the character reference card: a stocky forty-year-old servant with a weathered face, dark stubble, and grey-brown short servant's clothes, sprinting after the van with desperate, reckless energy.

summary:
[reference generation] The target video is a 10-second live-action cinematic historical-drama sequence: the prison van carries <Subject 1> out through the city gate past kneeling crowds while <Subject 2> sprints after it in a desperate, stumbling chase — falling, picking himself up, and charging on. The sequence ends on the great wheel rolling over a raised stone, the van lurching hard, and the frame plunging rapidly into complete black. <Picture 1> provides the storyboard structure for all six shots. The camera uses fluid tracking shots and intimate close-ups to create visceral chase energy.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, the funeral-street staging, and the closing hard cut to black are retained.
<Subject 1> (appears in [Shot 1], [Shot 3], [Shot 5]): fully_preserved - his identity, moon-white robe, wooden cangue, and restrained grief are retained.
<Subject 2> (appears in [Shot 4]): fully_preserved - his weathered face, grey-brown clothes, and desperate sprint are retained.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a cold, desaturated palette; a single seam of pale daylight breaks through the clouds over the street. The camera uses fluid tracking shots to create visceral chase energy and intimate close-ups to capture raw desperation.
[Shot 1] The sequence opens on a rear-view medium shot with a smooth tracking movement: <Subject 1> and two guards walk three abrest toward the rough wooden prison van waiting at the edge of the frame, chains swaying with each step. The camera tracks alongside them, the cobblestone street blurring beneath.
[Shot 2] At 00:02.500, the shot cuts to a wide establishing shot with a slow crane-up: the van rolls out through the tall city gate arch onto a long flagstone street, both sides dense with kneeling civilians, some burning incense, others covering their faces, a few paper money squares drifting through the air. The slow reveal creates a funeral procession atmosphere.
[Shot 3] At 00:05.500, the shot cuts to a subjective point-of-view framed by the vertical wooden bars of the van: simplified grieving faces slide backward past the gaps, slightly soft-focused, the street unrolling behind them. <Subject 1>'s eyes are visible through the bars — glistening, searching. The POV creates claustrophobia and longing.
[Shot 4] At 00:08.000, the shot cuts to a fast side-tracking medium shot with handheld shake: <Subject 2> sprints along the street after the van, stumbling, his palm slamming onto the flagstones — he pushes himself up and charges on. His face is a mask of grief and desperation, his mouth open in a silent scream. The handheld camera shakes with the impact, creating visceral urgency. He falls once more, picks himself up again — relentless.
[Shot 5] At 00:10.500, the shot cuts to a close-up through the bars: <Subject 1> lifts his eyes toward the running figure, begins to force a reassuring smile, cannot, and lowers his gaze instead. A single tear traces down his cheek — the first and only time he breaks composure.
[Shot 6] At 00:12.000, the shot cuts to a low-angle extreme close-up with a violent jolt: the great wheel rolls over a raised stone, the van lurches hard, and the frame plunges rapidly into complete black. The impact is jarring, final — the last thing we see is the wheel crushing the stone, then nothing.

overall_soundscape: Wooden wheels grind over flagstones beneath a hush of weeping; paper money flutters with a dry whisper; sprinting footsteps slap the stones and a body hits the ground once, twice; the final wheel-strike booms before total silence. Ambient crowd noise continues throughout but drops to nothing in the black.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 10.0s / 9:16 |
| Shot 时间轴 | S011 0-3.0 / S012 3.0-6.0 / S013 6.0-9.0 / S014 9.0-11.0 / S015 11.0-13.0 / S016 13.0-15.0 |
| 对白 | 无（环境叙事） |
| 关键约束 | **Shot 4 巢儿三次跌倒追车 + Shot 5 苏轼唯一一次流泪 + Shot 6 车轮碾石→黑场冲击** |
| 参考素材 | <Picture 1> 分镜板；<Subject 1>/<Subject 2> 角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. Shot 4 巢儿追车增加"跌倒→爬起→继续追"三次挣扎，强化绝望和执着；
2. Shot 5 苏轼唯一一次流泪 — 全片唯一的脆弱时刻，需要特写捕捉；
3. Shot 6 黑场加入"车轮碾过石头→剧烈颠簸→ plunge into black"的视听冲击；
4. 所有 Shot 加入镜头运动（tracking / crane-up / POV / handheld shake），消除幻灯片感。
