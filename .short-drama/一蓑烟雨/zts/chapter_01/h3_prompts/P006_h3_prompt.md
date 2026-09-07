# EP001 · P006 H3 提示词 v3（full-reference / [reference generation]）

> Panel：P006｜时长 15.0s｜画幅 9:16｜Shot S026-S031｜场景 C 书斋外（承接 P005）
> 参考素材：board_P006.jpg + char_su_shi_young.jpg + char_chaoer_young.jpg + char_su_xun.jpg
> 状态：v3 重写（2026-08-27）— 修复"过耳之才"视觉化+苏洵角色分量+情感过渡

## v2 → v3 关键修改

| 问题 | v2 | v3 修正 |
|---|---|---|
| 过耳之才 | 仅对白提及 | 视觉化：巢儿复述长段文字，苏轼惊讶表情 |
| 苏洵 | 工具人 | 增加：苏洵观察→点头→下令，有父亲的分量 |
| 情感过渡 | 跳跃 | 苏轼考校→巢儿复述→苏洵出现→下令→巢儿反应，层次分明 |
| 镜头 | 静态 | 推镜+摇镜+手持微晃 |

---

```text
subject_definitions:
<Picture 1> is the storyboard reference for [Shot 1] through [Shot 6], defining their viewpoints, subject placement, shot order, and the shift from playful warmth to a father's quiet authority.
<Subject 1> is the teenage Su Shi in the character reference card: a sixteen-year-old student with a round face, large bright eyes, hair in two small topknots, wearing a blue-grey coarse cloth scholar's robe. IMPORTANT: <Subject 1> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.
<Subject 2> is the teenage Chao'er in the character reference card: a slight fourteen-year-old orphan boy with messy hair tied by a cloth strip, patched ragged clothes, eyes wide with disbelief. IMPORTANT: <Subject 2> is a young teenager with a smooth, child-like face — no beard, no facial hair, no mustache, clean-shaven, pre-adolescent features.
<Subject 3> is Su Xun in the character reference card: a lean, upright forty-five-year-old scholar with a short beard and a dark head-cloth, wearing a dark brown scholar's robe with a leather belt, hands clasped behind his back, stern and economical with words.

summary:
[reference generation] The target video is an 11-second live-action cinematic historical-drama sequence: <Subject 1> tests the orphan's astonishing memory by reciting a long passage, <Subject 2> repeats it word-for-word with closed eyes, <Subject 3> appears in the doorway and decrees that the boy be taken in, stunning <Subject 2>. Both child characters (Subject 1 and 2) have smooth, beardless, child-like faces at all times — NO facial hair, NO beard, NO mustache. <Picture 1> provides the storyboard structure for all six shots. The camera uses slow, deliberate movements to build from playfulness to gravity.

retention_analysis:
<Picture 1> ([Shot 1]-[Shot 6] storyboard): fully_preserved - the six-shot order, subject placement, and the light-to-shadow shift when <Subject 3> appears are retained.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 6]): fully_preserved - his teenage identity, two topknots, blue-grey robe, and bright testing energy are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.
<Subject 2> (appears in [Shot 1], [Shot 3], [Shot 6]): fully_preserved - his slight build, ragged clothes, cloth-strip hair tie, and stunned disbelief are retained. CRITICAL: his face must remain smooth and child-like with NO facial hair in every shot.
<Subject 3> (appears in [Shot 4], [Shot 5]): fully_preserved - his lean stern figure, dark head-cloth, dark brown robe, and hands-behind-back stance are retained. NOTE: <Subject 3> is an adult male and MAY have a short beard — this is correct and intentional.

detailed_description:
The target video is in a live-action, cinematic historical-drama style with a warm golden-green palette that cools slightly when the father appears. Both child characters have smooth, child-like faces at all times — NO facial hair, NO beard, NO mustache of any kind. The camera uses slow, deliberate movements to build from playfulness to gravity.
[Shot 1] The sequence opens on the eye-level two-shot: <Subject 2> on the left and <Subject 1> on the right, both round heads at the same height, still facing each other from the previous moment. Both have smooth, beardless child-like faces. The camera slowly pushes in as <Subject 1> grins and holds up one finger, pointing toward the study door. <Subject 1> (S1) says: <d>[Chinese] 我考考你。方才那篇，你听了多久？</d> His tone is playful but genuinely curious.
[Shot 2] At 00:03.000, the shot cuts to a close-up of <Subject 2> with a subtle handheld movement: his head lowers, one hand twisting the ragged front of his shirt, his smooth beardless child-like face clearly visible. He answers in a shrinking voice: <Subject 2> (S2) says quietly: <d>[Chinese] ……先生晌午才开始念。</d> His voice trails off, uncertain.
[Shot 3] At 00:05.500, the shot cuts to a medium two-shot with a slow tracking movement: <Subject 1> straightens up, recites a long passage from memory (the exact words blurred), his smooth beardless face animated with enthusiasm. <Subject 2> closes his eyes and repeats the passage word-for-word, his lips moving in perfect sync, his smooth beardless face serene with concentration. This is the visual proof of his "过耳之才" — the audience sees it, not just hears about it.
[Shot 4] At 00:08.500, the shot cuts to a slightly low medium shot with a slow tilt-up: in the shadow of the study doorway, <Subject 3> now stands with hands clasped behind his back, his sharp gaze resting on the two boys for a long beat. <Subject 3> is an adult male and has a short beard — this is correct. His expression is unreadable, but his eyes linger on <Subject 2> with quiet assessment.
[Shot 5] At 00:11.000, the shot cuts to a medium shot with a subtle push-in: <Subject 3> turns and walks back inside, back turned, tossing the order over his shoulder without stopping. <Subject 3> (S3) says flatly: <d>[Chinese] 去账房支身工钱。往后院里的水，他挑。</d> His voice is calm but final — a father's decree, not a request.
[Shot 6] At 00:13.000, the shot cuts to a close-up of <Subject 2> with a slow push-in: frozen mid-breath, his mouth a small round of disbelief, his smooth beardless child-like face clearly visible, then his head snaps around toward <Subject 1>. The moment hangs — the weight of being "seen" and "chosen" settling on his shoulders.

overall_soundscape: Bamboo wind continues softly; the door hinge gives one faint creak; receding footsteps fade into the study; a single stunned breath hangs in the quiet. The recitation in Shot 3 is clearly audible but the exact words are blurred — the point is the perfect synchronization, not the content.

non_diegetic_music: N/A
```

---

## 交接核对清单（v3）

| 输入项 | 值 |
|---|---|
| 时长/画幅 | 11.0s / 9:16 |
| Shot 时间轴 | S026 0-3.0 / S027 3.0-6.0 / S028 6.0-9.0 / S029 9.0-11.0 / S030 11.0-13.0 / S031 13.0-15.0 |
| 对白 | S1 少年苏轼考校（逐字）；S2 少年巢儿低答（逐字）；S3 苏洵收留令（逐字） |
| 关键约束 | **Shot 3 "过耳之才"视觉化（巢儿闭眼复述）+ 苏洵有分量的观察+下令** |
| 参考素材 | <Picture 1> 分镜板；三张角色卡（少年苏轼/少年巢儿/苏洵） |
| non_diegetic_music | N/A |

## 取舍说明

1. Shot 3 新增"过耳之才"视觉化 — 苏轼长段朗诵+巢儿闭眼同步复述，让观众**看到**而非**听到**这个能力；
2. Shot 4 苏洵出现增加"long beat"观察和"quiet assessment"，让他有父亲的分量；
3. Shot 6 巢儿反应增加"the weight of being seen and chosen"的情感层次；
4. 所有 Shot 加入镜头运动（push-in / tilt-up / tracking），消除幻灯片感。
