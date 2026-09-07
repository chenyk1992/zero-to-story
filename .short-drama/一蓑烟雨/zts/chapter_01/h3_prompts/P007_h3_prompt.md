# EP001 · P007 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P007｜时长 12.0s｜画幅 9:16｜Shot S031-S036｜场景 C 书斋外→书斋内·黄昏（承接 P006）
> 参考素材：board_P007.jpg + char_su_shi_young.jpg + char_chaoer_young.jpg
> 状态：v3 重写（2026-08-27）— 修复情感过渡+"我们家的人"分量+时光过渡

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| "我们家的人" | 仅一句台词 | 增加：苏轼伸手+巢儿犹豫+握手，情感层次 |
| 时光过渡 | 突兀 | 明确：庭院劳动→时光流逝→书斋剪影 |
| 情感重量 | 不足 | 巢儿从"惊愕"到"感动"到"希望"，完整弧线 |
| 镜头 | 静态 | 推镜+摇镜+手持微晃 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, the handshake beat, the overhead time-passage transition, and the candle-lit study interior.
<Subject 1> is the teenage Su Shi in the character reference card: a sixteen-year-old student with a round face, large bright eyes, hair in two small topknots, wearing a blue-grey coarse cloth scholar's robe. IMPORTANT: <Subject 1> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.
<Subject 2> is the teenage Chao'er in the character reference card: a slight fourteen-year-old orphan boy with messy hair tied by a cloth strip, patched ragged clothes, eyes reddening with held-back tears. IMPORTANT: <Subject 2> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.

summary:
[reference generation] The target video is a 9-second live-action cinematic historical-drama sequence: <Subject 1> welcomes the stunned <Subject 2> into the family with a grin and a handshake, time dissolves across the courtyard, and the scene settles into a candle-lit study at dusk. Both child characters (Subject 1 and 2) have smooth, beardless, child-like faces at all times — NO facial hair, NO beard, NO mustache. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow, gentle movements to create warmth and emotional weight.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, the handshake center-frame, the overhead time-passage transition, and the candle-lit interior are retained.
<Subject 1> (appears in [Shot 2], [Shot 3], [Shot 6] silhouette): fully_preserved - his teenage identity, two topknots, blue-grey robe, and bright grin are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot where visible.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 4]): fully_preserved - his slight build, ragged clothes, cloth-strip hair tie, and moved hesitation are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.

detailed_description:
The target video is in a live-action, cinematic historical-drama style, moving from warm afternoon gold into candle-lit dusk. Both child characters have smooth, child-like faces at all times — NO facial hair, NO beard, NO mustache of any kind. The camera uses slow, gentle movements to create warmth and emotional weight.
[Shot 1] The sequence opens on the stunned close-up carried over from the previous moment: <Subject 2> frozen mid-breath, mouth a small round, his smooth beardless child-like face clearly visible, staring toward where the father vanished. The camera slowly pushes in on his face, capturing the exact moment disbelief begins to crack into something else — hope.
[Shot 2] At 00:02.000, the shot cuts to a close-up of <Subject 1> with a gentle handheld movement: he breaks into a wide, white-toothed grin, his smooth beardless child-like face clearly visible, head tipping back a little with delight. He says warmly, his voice full of genuine welcome: <Subject 1> (S1): <d>[Chinese] 听见没？你以后是我们家的人了。</d> The words land like a gift, not a decree.
[Shot 3] At 00:04.500, the shot cuts to a two-shot with a slow tracking movement: <Subject 1> slaps one palm down on the woodpile and holds his hand out toward <Subject 2>. <Subject 2> stares at the outstretched hand, his smooth beardless face crumbling — his eyes well up, his lower lip trembles — then he grins through it and reaches up. Two hands clasp in the center of the frame. The handshake is firm, warm, a pact.
[Shot 4] At 00:07.000, the shot cuts to an overhead wide shot with a slow crane-up: the two small figures move about their chores as the light patches slide and lengthen across the ground, time slipping forward. The camera rises to emphasize the passage of time, the world continuing around them.
[Shot 5] At 00:09.000, the shot cuts to a medium shot with a subtle push-in: the two boys sit across from each other at a wooden desk, a single candle flame between them, their smooth beardless faces lit by the warm glow. They are reading together, their shoulders almost touching.
[Shot 6] At 00:11.000, the shot dissolves into a silhouette two-shot with a slow fade: the candle steadies over the desk with open scrolls, inkstone and brushes laid out, and the two boys' silhouettes settle facing each other across the table — a new beginning, quiet and sure.

overall_soundscape: Bamboo wind softens into dusk; the woodpile thuds once under a palm; cicadas swell and fade across the time passage; a candle wick crackles as evening settles. The handshake moment is held in near-silence — the sound of two hands meeting, then nothing.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 12.0s / 9:16 |
| Shot 时间轴 | S031 0-2.0 / S032 2.0-4.5 / S033 4.5-7.0 / S034 7.0-9.0 / S035 9.0-11.0 / S036 11.0-12.0 |
| 对白 | S1 少年苏轼"听见没？你以后是我们家的人了。"（逐字） |
| 关键约束 | **Shot 3 握手情感层次（惊愕→感动→希望）+ Shot 4 时光流逝过渡** |
| 参考素材 | <Picture 1> 分镜板；两张少年角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. Shot 3 握手增加情感层次：巢儿"stares→eyes well up→lower lip trembles→grins through it→reaches up"，完整的情感弧线；
2. Shot 4 时光过渡明确：庭院劳动 + 光线变化 + crane-up 镜头，清晰的时间流逝信号；
3. "我们家的人" 从一句台词扩展为 "台词+伸手+犹豫+握手" 的完整场景，情感重量更足；
4. 所有 Shot 加入镜头运动（push-in / tracking / crane-up），消除幻灯片感。
