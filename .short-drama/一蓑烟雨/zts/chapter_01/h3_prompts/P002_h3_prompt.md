# EP001 · P002 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P002｜时长 12.0s｜画幅 9:16｜Shot S006-S011｜场景 A 湖州府衙前（承接 P001）
> 参考素材：board_P002.jpg + char_su_shi_middle.jpg + char_chaoer_middle.jpg
> 状态：v3 重写（2026-08-27）— 修复"写诗"题眼时长+巢儿绝望感+镜头运动

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| "写诗"题眼 | 仅1秒特写 | 延长至2.5秒，御史冷声+苏轼闭眼反应 |
| 巢儿反应 | 无 | 新增：巢儿在人群中绝望嘶哑的面部特写 |
| 镜头 | 静态 | 推镜+摇镜，营造紧张压迫感 |
| 节奏 | 快切 | 给"写诗"和巢儿反应留足时间 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, and the cold overcast atmosphere of the prison-van sequence.
<Subject 1> is the middle-aged Su Shi in the character reference card: a tall, lean scholar in his early forties with a short beard, frost-touched temples, and hair tied in a topknot, wearing a plain moon-white cross-collar robe, a rough wooden cangue clamped on his shoulders.
<Subject 2> is the middle-aged Chao'er in the character reference card: a stocky forty-year-old servant with a weathered face, dark stubble, and grey-brown short servant's clothes cinched with a rough cloth belt, his eyes red-rimmed and desperate.

summary:
[reference generation] The target video is a 9-second live-action cinematic historical-drama sequence continuing the arrest at the Huazhou government office. The escorting official pronounces the two-word charge — "写诗" — with cold finality. <Subject 2> watches in horror from the crowd, his face crumbling. <Subject 1> is then escorted toward the prison van. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow push-ins and subtle pans to build dread.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, viewpoints, and the cold overcast atmosphere are retained.
<Subject 1> (appears in [Shot 2], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his identity, moon-white robe, wooden cangue, and upright bearing under escort are retained.
<Subject 2> (appears in [Shot 3]): fully_preserved - his weathered face, grey-brown servant's clothes, and desperate grief are retained.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a cold, desaturated blue-grey palette under heavy overcast lighting. The camera uses slow, deliberate movements to build tension and dread.
[Shot 1] The sequence opens on the escorting official from the previous scene, standing on the stone steps. The camera slowly pushes in (2.0s) toward his face as he slowly turns his head to look down at the crowd below, his black official's cap silhouetted against the grey sky, his gaze aimed downward with cold authority.
[Shot 2] At 00:02.000, the shot cuts to a frontal close-up of the official's head with a subtle handheld tremor: his mouth opens and forms two deliberate syllables, his voice cold and thin, each word landing like a hammer blow. The official (S1) pronounces: <d>[Chinese] 写诗。</d> The words land in total silence — the ambient noise drops to nothing for a beat, creating a suffocating vacuum.
[Shot 3] At 00:05.000, the shot cuts to a slow pan across the crowd outside the guard wall, then settles on <Subject 2> (S2) in an extreme close-up: his pupils contract, his face drains of color, his lower lip trembles, and his eyes well up with tears. He clutches the garment of the man in front of him, knuckles white. This is the moment the sentence hits him — not <Subject 1>, but <Subject 2> feels the weight of those two words.
[Shot 4] At 00:07.500, the shot cuts to a wide shot with a slow tracking movement: two guards take <Subject 1> by both arms and march him forward along the passage, the kneeling crowd parting to leave a narrow lane. <Subject 1>'s expression is calm, almost resigned, but his eyes briefly flick toward the crowd — searching.
[Shot 5] At 00:09.500, the shot cuts to a near-side profile of <Subject 1> being led along with a subtle push-in, his head turned, his gaze sweeping across the kneeling civilians before settling forward. His jaw is tight, his eyes glistening but unreadable.
[Shot 6] At 00:11.000, the shot cuts to a rear-view medium shot: <Subject 1> and the two guards walk three abrest toward a rough wooden prison van waiting deep in the frame, cangue and chains swaying with each step.

overall_soundscape: Wind drags across the stone plaza under a low overcast rumble. In Shot 2, the ambient noise drops to near-silence during the two-word proclamation, creating a suffocating vacuum. The muffled shuffle of escorted footsteps and the creak of the wooden cangue carry over the hushed crowd. A single tear-drop moment is held in near-silence in Shot 3.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 9.0s / 9:16 |
| Shot 时间轴 | S006 0-2.0 / S007 2.0-5.0 / S008 5.0-7.5 / S009 7.5-9.5 / S010 9.5-11.0 / S011 11.0-12.0 |
| 对白 | S007 御史"写诗"（逐字，冷声） |
| 关键约束 | **"写诗"延长至2.5秒 + Shot 3 巢儿绝望特写 + 环境音静默** |
| 参考素材 | <Picture 1> 分镜板；<Subject 1>/<Subject 2> 角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. Shot 2 "写诗"延长至 2.5 秒（v2 仅 1 秒），给观众接收题眼的时间；
2. Shot 3 新增巢儿绝望特写 — 在"写诗"之后切到巢儿的反应，让观众通过他的眼睛感受判决的重量；
3. Shot 2 环境音降至近静默，营造"真空"感；
4. 所有 Shot 加入镜头运动（push-in / pan / tracking），消除幻灯片感。
