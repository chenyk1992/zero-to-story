# EP001 · P001 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P001｜时长 15.0s｜画幅 9:16｜Shot S001-S006｜场景 A 湖州府衙前
> 参考素材：board_P001.jpg + char_su_shi_middle.jpg + char_chaoer_middle.jpg
> 状态：v3 重写（2026-08-27）— 修复镜头/情感/四目相遇

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| 镜头 | 完全静态 | 加入缓慢推镜、摇镜、手持微晃 |
| 木枷 | 轻飘无重量 | 强调"heavy wooden cangue slams down with weight and impact" |
| 四目相遇 | 无 | 新增 Shot 4：苏轼与巢儿四目相遇，情感冲击 |
| 情感 | 平淡 | 每个 shot 加入角色微表情和情感层次 |
| 节奏 | 拖沓 | 压缩 Shot 1-2，给四目相遇留时间 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, and the cold overcast atmosphere of the yamen arrest scene.
<Subject 1> is the middle-aged Su Shi in the character reference card: a tall, lean scholar in his early forties with a short beard, frost-touched temples, and hair tied in a topknot, wearing a plain moon-white cross-collar robe, his posture upright and unafraid.
<Subject 2> is the middle-aged Chao'er in the character reference card: a stocky forty-year-old servant with a weathered face, dark stubble, and grey-brown short servant's clothes cinched with a rough cloth belt, his eyes stubborn and intense.

summary:
[reference generation] The target video is a 10-second live-action cinematic historical-drama sequence set in Northern Song China. An imperial edict is proclaimed, <Subject 1> is formally arrested with a heavy wooden cangue clamped on his shoulders, and in a pivotal moment, his eyes meet <Subject 2>'s desperate gaze across the crowd — a silent exchange that binds their fates. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow, deliberate movements (push-in, subtle pan) to create emotional weight rather than static observation.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, viewpoints, and the cold overcast atmosphere are retained.
<Subject 1> (appears in [Shot 2], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his identity, moon-white robe, upright kneeling posture, and the wooden cangue clamped on his shoulders are retained.
<Subject 2> (appears in [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his weathered face, grey-brown servant's clothes, and desperate intensity are retained.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a cold, desaturated blue-grey palette under heavy overcast lighting. The camera uses slow, deliberate movements to create emotional gravity — no static tripod shots.
[Shot 1] A wide establishing shot slowly pushes in (2.5s) toward the Huazhou government office gate beneath storm clouds: an imperial envoy's procession stands on the stone steps, two rows of guards with long staffs line the passage on both sides, a bright yellow imperial edict is unrolled as a deep official voice (S1) proclaims it aloud from the steps, the exact words blurred by wind and distance, and kneeling civilians form a dark silhouette band across the foreground. The slow push-in creates a sense of inevitable doom.
[Shot 2] At 00:02.500, the camera cuts to a medium shot with subtle handheld tremor: <Subject 1> kneels at the foot of the steps, back perfectly straight. A guard steps forward and strips the official seal from his waist while another pulls off his outer robe and drops it on the stone; the seal lands with a heavy muffled thud. <Subject 1> remains kneeling, unmoved, his jaw tight.
[Shot 3] At 00:05.000, the shot cuts to a high-angle close-up with a slow tilt-down: a rough wooden cangue is clamped onto <Subject 1>'s shoulders — the wood is heavy, thick, and weathered, and it slams down with visible weight and impact, the lock snapping shut with a sharp crack that carries a faint echo. <Subject 1>'s body jolts slightly from the impact, his eyes closing briefly in pain.
[Shot 4] At 00:07.000, the camera cuts to a slow pan across the crowd outside the guard wall, then settles on <Subject 2> (S2) rising on his toes to see over the guards' shoulders, his face draining of color. Their eyes meet — <Subject 1> and <Subject 2> lock gazes across the chaos. <Subject 1>'s expression is calm, almost reassuring, a faint "I'm there" in his eyes. <Subject 2>'s face crumbles, his lips trembling, tears welling. This is the emotional anchor of the scene.
[Shot 5] At 00:09.500, the shot cuts to a shaky handheld medium shot: <Subject 2> shoves forward wildly until two long spears cross to bar his chest, his palms pressing hard against the shafts. <Subject 2> (S2) screams desperately: <d>[Chinese] 他到底犯了什么罪？！你们说他到底犯了什么罪！</d> The crowd behind him surges against the guards.
[Shot 6] At 00:11.000, the shot cuts to a low-angle close-up: the escorting official on the steps slowly turns and looks down from above, a faint pitying sneer forming on his lips as wind snaps the banners behind him.

overall_soundscape: Wind drags across the stone plaza beneath a low rumble of distant thunder. The muffled thud of the seal hitting stone, the sharp crack of the cangue lock, choked gasps from the crowd, and the escort's synchronized footsteps layer over the fading proclamation. In Shot 4, the ambient noise drops to near-silence during the eye contact moment.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长 | 10.0s |
| 画幅 | 9:16 |
| 风格 | 写实古装电影感，冷灰蓝低饱和，阴天顶光，压抑浅景深 |
| 镜头 | 缓慢推镜+摇镜+手持微晃，无静态镜头 |
| Shot 时间轴 | S001 0-3.0 / S002 3.0-6.0 / S003 6.0-9.0 / S004 9.0-11.0 / S005 11.0-13.0 / S006 13.0-15.0 |
| 对白 | S005 巢儿嘶喊逐字保留 |
| 关键约束 | **Shot 4 四目相遇**（苏轼+巢儿眼神交流，情感锚点）；木枷有重量感 |
| 参考素材 | <Picture 1> 分镜板；<Subject 1>/<Subject 2> 角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. 新增 Shot 4 "四目相遇" — 这是整个 EP001 的情感锚点，苏轼与巢儿的视觉连接；
2. 每个 Shot 都加了镜头运动（push-in / pan / handheld / tilt），消除幻灯片感；
3. 木枷描述改为 "heavy, thick, weathered wood slams down with visible weight and impact"；
4. Shot 4 环境音降至近静默，突出眼神交流。
