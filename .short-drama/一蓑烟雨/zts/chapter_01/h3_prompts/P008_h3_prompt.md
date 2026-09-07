# EP001 · P008 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P008｜时长 15.0s｜画幅 9:16｜Shot S036-S041｜场景 C 书斋内·黄昏（承接 P007）
> 参考素材：board_P008.jpg + char_su_shi_young.jpg + char_chaoer_young.jpg
> 状态：v3 重写（2026-08-27）— 修复"第一课"仪式感+"天地"视觉化+情感深度

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| "第一课"仪式感 | 缺失 | 增加：开笔礼、研墨、苏轼严肃认真的教学态度 |
| "天地" | 无视觉化 | 增加：苏轼指着字的笔画，解释"天"和"地"的含义 |
| 情感深度 | 浅 | 巢儿从"疑惑"到"领悟"到"希望"，完整弧线 |
| 镜头 | 静态 | 推镜+摇镜+手持微晃 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, and the candle-lit study atmosphere.
<Subject 1> is the teenage Su Shi in the character reference card: a sixteen-year-old student with a round face, large bright eyes, hair in two small topknots, wearing a blue-grey coarse cloth scholar's robe. IMPORTANT: <Subject 1> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.
<Subject 2> is the teenage Chao'er in the character reference card: a slight fourteen-year-old orphan boy with messy hair tied by a cloth strip, patched ragged clothes, eyes reddening with held-back tears. IMPORTANT: <Subject 2> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.

summary:
[reference generation] The target video is an 11-second live-action cinematic historical-drama sequence: <Subject 1> conducts a proper "first lesson" ceremony for <Subject 2> in the candle-lit study, teaching him the characters "天" and "地" with patient gravity. <Subject 2> asks a question about the worth of literacy, and <Subject 1> answers with a truth that reshapes the boy's worldview. Both child characters (Subject 1 and 2) have smooth, beardless, child-like faces at all times — NO facial hair, NO beard, NO mustache. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow, intimate movements to create reverence and emotional depth.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, the candle-lit study staging, and the lesson-to-dialogue progression are retained.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 5], [Shot 6]): fully_preserved - his teenage identity, two topknots, blue-grey robe, and patient teaching demeanor are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.
<Subject 2> (appears in [Shot 1], [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his slight build, ragged clothes, cloth-strip hair tie, and growing wonder are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a warm candlelit palette, soft shadows dancing on the walls. Both child characters have smooth, child-like faces at all times — NO facial hair, NO beard, NO mustache of any kind. The camera uses slow, intimate movements to create reverence and emotional depth.
[Shot 1] The sequence opens on a medium shot with a slow push-in: <Subject 1> sits across from <Subject 2> at a wooden desk, a single candle between them. He carefully grinds the inkstick against the inkstone in slow, deliberate circles — the opening ritual of a first lesson. Both boys have smooth, beardless child-like faces. The camera's push-in emphasizes the gravity of the moment; this is not casual tutoring, it is an initiation.
[Shot 2] At 00:02.500, the shot cuts to an over-the-shoulder close-up with a subtle handheld movement: <Subject 1>'s hand guides the brush, writing two characters on the page — "天" and "地" — each stroke deliberate, his smooth beardless face concentrated and serious. He pronounces each character clearly, his voice patient but firm.
[Shot 3] At 00:05.500, the shot cuts to a close-up of <Subject 2> with a slow tilt-up: he leans forward, lips moving silently as he traces the characters with his eyes, his smooth beardless face shifting from confusion to the first glimmer of understanding. He suddenly looks up, something unspoken in his eyes.
[Shot 4] At 00:08.000, the shot cuts to a two-shot with a gentle push-in: <Subject 2> opens his mouth and asks the question that has been eating at him. <Subject 2> (S2) asks quietly, his voice small: <d>[Chinese] 先生，我家穷，认字……有用吗？</d> The question hangs in the air — vulnerable, honest, the core fear of a poor child.
[Shot 5] At 00:10.500, the shot cuts to a close-up of <Subject 1> with a slow push-in: he sets down the brush, looks directly at <Subject 2>, and speaks with quiet conviction — this is not a platitude, it is a truth he lives by. <Subject 1> (S1) says: <d>[Chinese] 饭管一天，字管一辈子。</d> His smooth beardless face is lit by the candle, his eyes steady and sure.
[Shot 6] At 00:13.000, the shot cuts to a close-up of <Subject 2> with a slow push-in: the words land. His eyes widen, his lips part, and for a beat he is perfectly still — then a slow, wondering smile spreads across his smooth beardless face. He looks down at the characters on the page as if seeing them for the first time. The camera holds on his face as the lesson becomes something more — a door opening.

overall_soundscape: The inkstick grinding against the inkstone provides a soft, rhythmic base. The brush tip scratches faintly on paper. The candle wick crackles. <Subject 2>'s question is held in near-silence — the ambient noise drops as the words land. <Subject 1>'s answer is calm but carries weight, his voice steady and sure.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 14.0s / 9:16 |
| Shot 时间轴 | S036 0-3.0 / S037 3.0-6.0 / S038 6.0-9.0 / S039 9.0-11.0 / S040 11.0-13.0 / S041 13.0-15.0 |
| 对白 | S2 少年巢儿"先生，我家穷，认字……有用吗？"（逐字）；S1 少年苏轼"饭管一天，字管一辈子。"（逐字） |
| 关键约束 | **Shot 1 开笔礼仪式感 + Shot 2 "天地"视觉化 + Shot 4-6 情感弧线（疑惑→领悟→希望）** |
| 参考素材 | <Picture 1> 分镜板；两张少年角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. Shot 1 加入开笔礼仪式感 — 研墨的缓慢圆周运动，强调"第一课"的庄重；
2. Shot 2 "天地"视觉化 — 苏轼写字+念出字音，让观众**看到**教学内容；
3. Shot 4-6 完整情感弧线：巢儿问"有用吗"（脆弱）→ 苏轼回答（确信）→ 巢儿领悟（希望）；
4. 所有 Shot 加入镜头运动（push-in / tilt-up / handheld），消除幻灯片感。
