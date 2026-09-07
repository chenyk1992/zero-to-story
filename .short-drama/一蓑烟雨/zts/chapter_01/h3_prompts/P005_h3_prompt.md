# EP001 · P005 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P005｜时长 12.0s｜画幅 9:16｜Shot S021-S026｜场景 C 书斋外（承接 P004）
> 参考素材：board_P005.jpg + char_su_shi_young.jpg + char_chaoer_young.jpg
> 状态：v3 重写（2026-08-27）— 修复镜头运动+角色情感层次+对白节奏

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| 镜头 | 静态 | 加入推镜+摇镜+手持微晃 |
| 情感 | 单一调侃 | 苏轼：好奇→调侃→认真；巢儿：惊慌→心虚→倔强 |
| 对白节奏 | 连续快速 | 每句对白间加入反应镜头，给观众消化时间 |
| 动作 | 纯说话 | 加入肢体动作（苏轼跳窗、巢儿摆手否认） |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, and the playful window-to-woodpile confrontation.
<Subject 1> is the teenage Su Shi in the character reference card: a sixteen-year-old student with a round face, large bright eyes, hair in two small topknots, wearing a blue-grey coarse cloth scholar's robe, quick and teasing. IMPORTANT: <Subject 1> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.
<Subject 2> is the teenage Chao'er in the character reference card: a slight fourteen-year-old orphan boy with messy hair tied by a cloth strip, patched ragged clothes, and scattered firewood sticks around him. IMPORTANT: <Subject 2> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.

summary:
[reference generation] The target video is a 12-second live-action cinematic historical-drama sequence: <Subject 1> teases the eavesdropping <Subject 2> through the open window, tests his memory, then hops over the doorsill and crouches down to meet his eyes at eye level. The emotional arc moves from playful curiosity to genuine interest. Both child characters have smooth, beardless, child-like faces at all times — NO facial hair, NO beard, NO mustache. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow, gentle movements to create warmth and playful energy.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, the window-woodpile diagonal staging, and the final eye-level two-shot are retained.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 4], [Shot 5], [Shot 6]): fully_preserved - his teenage identity, two topknots, blue-grey robe, and teasing curiosity are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3], [Shot 5], [Shot 6]): fully_preserved - his slight build, ragged clothes, cloth-strip hair tie, and flustered honesty are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a warm golden-green palette and soft dappled bamboo light. Both child characters have smooth, child-like faces at all times — NO facial hair, NO beard, NO mustache of any kind. The camera uses slow, gentle movements to create warmth and playful energy.
[Shot 1] The sequence opens on the frozen moment from the previous scene: <Subject 2> sits stunned on the scattered firewood pile looking up with a smooth, beardless child-like face, while <Subject 1> leans out of the open window above, looking down with a smooth, beardless child-like face. The camera slowly pushes in on the diagonal between them, creating visual tension.
[Shot 2] At 00:02.000, the shot cuts to an over-the-shoulder frame from behind <Subject 2> with a subtle handheld movement: <Subject 1> leans out over the sill, head tilted, his smooth beardless face clearly visible, and says with open curiosity, <Subject 1> (S1): <d>[Chinese] 喂，偷听的。方才那句，你再念念？</d> His tone is light, playful, genuinely curious — not mocking.
[Shot 3] At 00:04.500, the shot cuts to a low-angle close-up of <Subject 2> with a slow tilt-up: his eyes go wide, his mouth opens in a panic, both hands waving in frantic denial, his smooth beardless child-like face clearly visible. <Subject 2> (S2) blurts in a panic: <d>[Chinese] 小人没偷！我就是……路过！</d> His voice cracks with fear and indignation.
[Shot 4] At 00:07.000, the shot cuts back to <Subject 1> at the window with a gentle push-in: one eyebrow arched, a grin spreading across his face, his smooth beardless face clearly visible. He drawls with a teasing lilt: <Subject 1> (S1): <d>[Chinese] 路过还带着嘴？</d> The line is playful, not cruel — he's enjoying this.
[Shot 5] At 00:09.000, the shot cuts to a side medium shot with a slow tracking movement: <Subject 1> hops the doorsill (a light, athletic jump — normal gravity, weighty landing), walks to the woodpile, and crouches down until his eyes are level with the seated boy's. His smooth beardless child-like face is clearly visible. The physical leveling creates intimacy and respect.
[Shot 6] At 00:10.500, the shot cuts to a two-shot at eye level with a subtle push-in: the two round faces side by side in profile, <Subject 2> on the left and <Subject 1> on the right, both with smooth beardless child-like faces, neither blinking, a distant rooster crowing once. The stillness after the back-and-forth creates a moment of connection.

overall_soundscape: Bamboo leaves rustle over packed earth; scattered firewood clatters; a rooster crows once in the distance; two young voices bounce between tease and panic, their tones clearly differentiated — one light and playful, the other cracking with fear.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 12.0s / 9:16 |
| Shot 时间轴 | S021 0-2.0 / S022 2.0-4.5 / S023 4.5-7.0 / S024 7.0-9.0 / S025 9.0-10.5 / S026 10.5-12.0 |
| 对白 | S1 少年苏轼两句（逐字）；S2 少年巢儿一句（逐字） |
| 关键约束 | **情感层次（好奇→调侃→认真 / 惊慌→心虚→倔强）+ 镜头运动 + 对白间反应镜头** |
| 参考素材 | <Picture 1> 分镜板；两张少年角色卡 |
| non_diegetic_music | N/A |

## 取舍说明

1. 每句对白之间加入反应镜头（Shot 3 巢儿惊慌、Shot 4 苏轼调侃），给观众消化时间；
2. 情感层次更丰富：苏轼从"好奇"到"认真"，巢儿从"惊慌"到"倔强"；
3. Shot 5 跳窗改为 "light, athletic jump — normal gravity, weighty landing"；
4. 所有 Shot 加入镜头运动（push-in / tilt-up / tracking），消除幻灯片感。
