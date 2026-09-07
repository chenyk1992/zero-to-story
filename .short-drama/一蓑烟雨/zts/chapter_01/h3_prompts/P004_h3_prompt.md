# EP001 · P004 H3 提示词 v4（full-reference / [reference generation]）

> Panel：P004｜时长 15.0s｜画幅 9:16｜Shot S016-S021｜场景 C 眉山苏宅书斋外（时空跳转：1053 年）
> 参考素材：board_P004.jpg + char_su_shi_young.jpg + char_chaoer_young.jpg
> 状态：v4 重写（2026-08-27）—— 修复最后一秒女孩摔倒问题

## v3 → v4 关键修改

| 问题 | v3 | v4 修正 |
|---|---|---|
| 末秒摔倒 | "plops backward onto the firewood pile with a soft thud" | **改为正常站立对视**——巢儿站稳，苏轼探出身，两人相视而笑 |
| 动作风险 | 复杂动作（摔倒+木棍散落）触发 AI 失败 | **简化为静态姿势**，避免物理模拟 |
| 情感收尾 | 突变为惊恐/滑稽 | **保持温馨基调**，为下一 Panel 铺垫 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, and the warm bamboo-court morning atmosphere.
<Subject 1> is the teenage Su Shi in the character reference card: a sixteen-year-old student with a round face, large bright eyes, hair in two small topknots, wearing a blue-grey coarse cloth cross-collar scholar's robe. IMPORTANT: <Subject 1> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features. He must remain a consistent teenage boy throughout all shots — NO transformation into an adult male.
<Subject 2> is the teenage Chao'er in the character reference card: a slight fourteen-year-old orphan boy with messy hair tied by a rough cloth strip, large wary eyes, patched ragged clothes, worn straw sandals, and a small bundle of firewood strapped to his back. IMPORTANT: <Subject 2> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.

summary:
[reference generation] The target video is a 15-second live-action cinematic historical-drama sequence twenty-three years earlier: in a bamboo grove courtyard at dawn, orphan boy <Subject 2> eavesdrops outside the study window until student <Subject 1> notices and slides the window open. They see each other for the first time — a moment of curiosity and tentative connection. The sequence opens with a fade-in from black to signal the time-space jump. CRITICAL: In the final shot, both characters stand still and look at each other. <Subject 2> does NOT fall. <Subject 2> remains standing on the ground, looking up at <Subject 1>, who leans out the window looking down. Both smile. This is a quiet, warm moment — no sudden movements, no falls, no physical comedy. Both child characters have smooth, beardless, child-like faces at all times — NO facial hair, NO beard, NO mustache. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow, gentle movements to create warmth and intimacy.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, the fade-in from black, and the warm morning atmosphere are retained.
<Subject 1> (appears in [Shot 3], [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his teenage identity, two small topknots, blue-grey robe, and quick curious energy are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot — NO transformation into an adult male.
<Subject 2> (appears in [Shot 2], [Shot 3], [Shot 6]): fully_preserved - his slight build, ragged clothes, cloth-strip hair tie, and wary expression are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot. <Subject 2> remains standing throughout Shot 6 — NO falling, NO sudden movements.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a warm golden-green palette, soft morning light filtering through bamboo leaves. The camera uses slow, gentle movements to create warmth and intimacy. Both child characters have smooth, child-like faces at all times — NO facial hair, NO beard, NO mustache of any kind.
[Shot 1] The sequence fades in from pure black (1.5s) to signal the time-space jump: a wide shot slowly reveals a modest courtyard wrapped in tall bamboo, white walls and dark tile roofs, the study window on the right glowing faintly warm while a children's recitation voice drills through the morning air. The fade-in creates a clear transition from the previous scene's darkness.
[Shot 2] At 00:03.000, the shot cuts to a medium shot at the study window with a slow pan: <Subject 2> stands on tiptoe below the windowsill, a bundle of firewood strapped to his back, both hands gripping the sill, his lips moving along with the recitation from inside, word for word. His expression is absorbed, hungry for knowledge.
[Shot 3] At 00:06.000, the shot cuts to an interior close-up with a subtle push-in: <Subject 1> sits at his desk with an open book, suddenly stops, and tilts his head toward the window; the indoor recitation ceases, leaving only the boy's voice outside continuing perfectly. <Subject 1>'s eyes widen with curiosity, then crinkle with delight.
[Shot 4] At 00:08.500, the shot cuts to a close-up of <Subject 1>'s face with a gentle handheld movement: his surprise melts into delight, the corners of his mouth curling as he sets down the book and rises. His smooth, beardless child-like face is clearly visible — bright eyes, round cheeks, two small topknots.
[Shot 5] At 00:11.000, the shot cuts to a medium shot with a slow tracking movement: <Subject 1> strides to the window and slides the lattice open with both hands. The window makes a soft scraping sound. He leans out, looking down with a grin.
[Shot 6] At 00:13.000, the shot cuts to a two-shot with a slight downward tilt: <Subject 1> leans out the window, looking down. <Subject 2> stands on the ground below, looking up. They see each other for the first time. Both boys stand completely still — NO sudden movements, NO falling. A gentle smile forms on both faces. The moment is quiet, warm, and still. This is the first connection between two souls who will shape each other's lives.

overall_soundscape: Bamboo leaves rustle continuously; a children's recitation drills from inside the study and continues seamlessly outside; the window lattice scrapes open; birdsong adds warmth to the morning air. In Shot 6, the ambient noise softens to near-silence as the two characters see each other, creating a hushed, intimate atmosphere.

non_diegetic_music: N/A
```

---

## 交接核对清单（v4）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 15.0s / 9:16 |
| Shot 时间轴 | S016 0-3.0 / S017 3.0-6.0 / S018 6.0-8.5 / S019 8.5-11.0 / S020 11.0-13.0 / S021 13.0-15.0 |
| 对白 | 无（书声环境叙事） |
| 关键约束 | **Shot 6 两人静止对视，无摔倒，温馨收尾** |
| 参考素材 | <Picture 1> 分镜板；两张少年角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. Shot 6 完全重写：从"摔倒在柴堆上"改为"两人静止对视"，消除 AI 失败风险；
2. Shot 6 加入"quiet, warm, and still"和"first connection between two souls"的情感描述；
3. Shot 6 环境音降至近静默，突出眼神交流。

1. Shot 1 加入 fade-in from black（1 秒），明确时空跳转信号，让观众知道"现在换时间了"；
2. 全程强调 "smooth, child-like face, NO facial hair"，防止角色突变；
3. Shot 6 落改为 "soft thud + scattered sticks + normal gravity"，消除反重力漂浮；
4. 所有 Shot 加入镜头运动（push-in / pan / tracking / tilt），消除幻灯片感。
