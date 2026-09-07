# EP001 · P010 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P010｜时长 15.0s｜画幅 9:16｜Shot S046-S051｜场景 C 书斋内·夜（承接 P009）
> 参考素材：board_P010.jpg + char_su_shi_young.jpg + char_chaoer_young.jpg
> 状态：v3 重写（2026-08-27）— 修复大笑闭环+与开头呼应+黑场余韵

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| 大笑闭环 | 突兀 | 增加：苏轼解释"巢"字的意义→巢儿领悟→两人相视大笑 |
| 与开头呼应 | 无 | 末镜：苏轼的手（自由）vs P010 枷锁（束缚），形成对照 |
| 黑场余韵 | 突然 | 增加：笑声渐弱→烛光熄灭→黑场→余音缭绕 |
| 镜头 | 静态 | 推镜+摇镜+手持微晃 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, and the candle-lit study atmosphere.
<Subject 1> is the teenage Su Shi in the character reference card: a sixteen-year-old student with a round face, large bright eyes, hair in two small topknots, wearing a blue-grey coarse cloth scholar's robe. IMPORTANT: <Subject 1> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.
<Subject 2> is the teenage Chao'er in the character reference card: a slight fourteen-year-old orphan boy with messy hair tied by a cloth strip, patched ragged clothes, eyes reddening with held-back tears. IMPORTANT: <Subject 2> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.

summary:
[reference generation] The target video is a 13-second live-action cinematic historical-drama sequence: <Subject 1> explains the meaning of <Subject 2>'s name — "巢" means a nest, a home, a place where birds return — and <Subject 2> grasps the meaning for the first time. They look at each other and burst into genuine, unguarded laughter. The laughter fades, the candle gutters, and the frame slowly fades to black — but the echo of their laughter lingers. Both child characters (Subject 1 and 2) have smooth, beardless, child-like faces at all times — NO facial hair, NO beard, NO mustache. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow, intimate movements to create warmth and a sense of closure that echoes back to the opening arrest.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, the candle-lit study staging, and the fade-to-black ending are retained.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his teenage identity, two topknots, blue-grey robe, and warm laughter are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.
<Subject 2> (appears in [Shot 1], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his slight build, ragged clothes, cloth-strip hair tie, and joyful wonder are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a warm candlelit palette, soft shadows dancing on the walls. Both child characters have smooth, child-like faces at all times — NO facial hair, NO beard, NO mustache of any kind. The camera uses slow, intimate movements to create warmth and a sense of closure that echoes back to the opening arrest.
[Shot 1] The sequence opens on a close-up of the written name with a slow tilt-up: the two characters "巢儿" on the page, the brush strokes still wet. The camera tilts up to reveal both boys' faces — both smooth, beardless, child-like — looking at the name with quiet wonder. The candle flame steadies between them.
[Shot 2] At 00:02.500, the shot cuts to a close-up of <Subject 1> with a gentle push-in: he points at the character "巢" and explains with a warm smile, his smooth beardless face animated. <Subject 1> (S1): <d>[Chinese] 巢，是鸟的家。不管飞多远，最后都要回来的地方。</d> His voice is gentle, his eyes crinkling with delight at the poetry of it.
[Shot 3] At 00:05.000, the shot cuts to a close-up of <Subject 2> with a slow push-in: the meaning lands. His eyes widen, his lips part, and for a beat he is perfectly still — then a slow, wondering smile spreads across his smooth beardless face. He looks up at <Subject 1>, something unspoken passing between them. He has never thought of his name as something beautiful before.
[Shot 4] At 00:07.500, the shot cuts to a two-shot with a subtle handheld movement: <Subject 1> grins, <Subject 2> grins back, and then they both burst into genuine, unguarded laughter — the kind that comes from the belly, that makes your eyes water. Both smooth beardless faces are lit by the candle, their laughter filling the small room. The camera shakes slightly with the energy of their joy.
[Shot 5] At 00:10.000, the shot cuts to a close-up of <Subject 1>'s hand with a slow push-in: his hand, free and unshackled, rests on the desk beside the written name. The camera holds on this image — a hand that will one day write great poetry, now simply resting in friendship. This is the visual echo of the opening: where P001 showed hands in chains, P010 shows hands in freedom.
[Shot 6] At 00:12.000, the shot cuts to a wide shot with a slow pull-back: the laughter fades, the candle gutters and dies, and the frame slowly fades to black. But the echo of their laughter lingers over the black — three seconds of silence with the memory of joy, before the final cut. The slow fade creates a sense of ending that is also a beginning.

overall_soundscape: The candle wick crackles softly. <Subject 1>'s explanation is warm and gentle. <Subject 2>'s moment of understanding is held in near-silence. Their laughter fills the room — genuine, unguarded, the sound of two boys becoming friends. The laughter slowly fades, the candle gutters with a soft hiss, and then silence — three seconds of black with the echo of joy lingering.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 13.0s / 9:16 |
| Shot 时间轴 | S046 0-3.0 / S047 3.0-6.0 / S048 6.0-9.0 / S049 9.0-11.0 / S050 11.0-13.0 / S051 13.0-15.0 |
| 对白 | S1 "巢，是鸟的家..."（逐字） |
| 关键约束 | **"巢"字解释→领悟→大笑→自由之手（与开头枷锁呼应）→黑场余韵** |
| 参考素材 | <Picture 1> 分镜板；两张少年角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. 完整"巢"字解释：苏轼说"巢，是鸟的家。不管飞多远，最后都要回来的地方"；
2. Shot 4 大笑是情感高潮 — 两个男孩成为朋友的瞬间；
3. Shot 5 自由之手与 P001 枷锁形成视觉对照（chains vs freedom）；
4. Shot 6 黑场有余韵 — 笑声渐弱→烛光熄灭→3 秒黑场→余音缭绕；
5. 所有 Shot 加入镜头运动（push-in / tilt-up / pull-back / handheld），消除幻灯片感。
