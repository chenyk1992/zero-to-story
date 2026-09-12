# -*- coding: utf-8 -*-
"""P005 提示词 v2：视线揭示版 + 色彩指令 + 音频显式窗/负约束。整段替换 h3_prompts.md 的 P005 段。"""
import io, re

PATH = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\h3_prompts.md'

NEW = '''## P005 · 你父母在外面等你（i2v · 14.0s · C005 · B021–B026）· v2

- 参考输入：**I2V，无板，v2**。首帧 = `assets/first_frames/P005_first_frame_v2_mother_ambient.png`（= P004 末帧 + 母亲反光 patch 合成：取 P005 run d9d786c5 末帧反光区，高斯模糊 2px + alpha 0.35 + 14px 羽化贴入——母亲反光**开场即隐约在场**；合成脚本 `scripts/p005_first_frame_v2.py`，目视无重影无硬边）；角色卡 `asset_card_coach` + `asset_card_mother` 走 `related`。
- **v2 变更（master 两项验收反馈）**：① 母亲反光突兀 → **视线揭示版**：反光开场隐约在场（首帧合成）+ D008 后 ~7.2s 教练侧头瞥向玻璃、焦点随视线转移——她「一直在，顺着教练的视线才看见」，rack focus 由此获得叙事动因；蓝图四处手术（EV010.visible_proof / C005.actions / C005.camera_moves / P004→P005 bridge 消「反打」遗留），validator **PASS**，brief 六处同步。② 色彩饱和不足（成片实测 S_mean≈0.10、中位 0.05，P004 Shot1 仅 0.02）→ 提示词加 vivid natural color grading + warm-cool contrast + never desaturated 指令；brief 增**全集色彩规范**（S_mean ≥ 0.18 / S_p90 ≥ 0.30 验收线）；管线级轻量调色兜底待本版出片评估。
- 机位（**单镜 fixed，无切镜**）：承接首帧双人中景，全程 fixed 不动；唯一变化是 ~7.8–10.5s 焦点随教练视线从面部转移到玻璃门反光。禁推近/禁切镜。
- 对白：D008@**5.9–8.4s 显式窗** + 「全片唯一语音、8.4s 后无人声」负约束（治 v1 语音漂移后移 1.7s）。
- 母亲硬约束：仅玻璃反光中的深色外套侧影、不露正脸、不与门接触、无对白、无声音。
- 声音：空调 hum + 回放低语；~4.3s 叹气；~5.4s 摆手衣料声；8.4s 后无人声；~9.8s **钢琴单音 + 雨**渐入（全集首段音乐，S002→S003 情绪转场）。
- 末态锁定（12.0–14.0s）：焦点停在玻璃反光，母亲侧影手停眼角，教练/沈默虚化静止，钢琴雨保持。
- 依赖：P004 INCONCLUSIVE 挂起——首帧源取自其末帧（v2 合成同源）；若 P004 REJECT 重出，首帧需基于新末帧重合成（脚本可复用，改源路径即可）。

<!-- P005 PROMPT START -->

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic drama style, rich natural color grading with vivid saturated tones and strong warm-cool contrast - warm natural skin tones standing out against the cool teal-grey glass room; never washed-out, never desaturated, never black-and-white at any point. The shot holds the exact framing of <Picture 1>, the final frame of the previous shot: a cold white backstage glass coaching room at night, an interior medium shot with the coach on the left side of the frame and Shen Mo in the right foreground. The coach, a lean slightly stooped 40-year-old East Asian man with a thin stern face and a dark short-sleeved polo shirt, holds the exact posture of <Picture 1>, slightly bent forward with his right hand just withdrawn from the round ceramic ashtray on the low table, where the dead cigarette now rests. Behind him the wall screen keeps playing its abstract textless replay, and beyond the low table a glass door with dark frames closes off the back of the room; in that dark glass, the faint blurred reflection of a middle-aged woman in a dark coat has been standing outside in the corridor the whole time, barely noticeable, her side profile facing the room with one hand raised toward her eyes - she has been waiting there all along. Shen Mo, the 24-year-old mid-laner in the black esports jersey with orange trim, stays in the right foreground with his back three-quarters to the camera, head lowered, never turning. The camera stays completely locked and static for the entire video: no push, no pull, no pan, no cut, no reframe of any kind - only the focus changes once, late in the shot. For the first three and a half seconds nothing moves except the faint replay light: the two figures hold a long, heavy stillness, and the woman's reflection stays faint and still in the glass. At about 4.3 seconds the coach slowly straightens up and lets out a long, quiet sigh, his shoulders and chest sinking as his head lowers. At about 5.4 seconds he lifts his right hand in one small, dismissive wave, as if waving the whole question away. At 5.9 seconds the coach (S1), his stern face softening into tired resignation, says in a low, tired, gravelly voice: <d>[Chinese] 算了。你父母在外面等你。</d> - this line is the only speech in the entire video, spoken between 5.9 and 8.4 seconds; there is no other voice, no whisper, no murmur of words at any other moment, and after 8.4 seconds there is no speech at all. Shen Mo keeps his head lowered through the line and does not move. At about 7.2 seconds, right after his last word, the coach turns his head slightly to glance back over his shoulder toward the glass door - a natural, tired glance toward the people waiting outside. The camera still does not move; only the focus follows his gaze: between 7.8 and 10.5 seconds the focus gradually shifts from the coach's face to the dark glass of the door, the coach softening into a blur in the left foreground while the glass grows sharp, and the woman's reflection, which has been faintly there the whole time, now becomes clearly visible - her dark-coated side profile standing in the corridor outside, motionless, one hand raised to her eyes, quietly wiping them; she never touches the door, never turns her face to the camera, and makes no sound. From about 9.8 seconds a single soft piano note and the gentle sound of rain against the night outside fade in. From 12.0 seconds to the end at 14.0 seconds everything holds: the focus rests on the glass door with the woman's reflection, her hand at her eyes, while the coach and Shen Mo remain motionless; no further movement, no further sound of any kind.

overall_soundscape:
The cool hum of the air-conditioner and the faint unintelligible murmur of the looping replay run under the first half. A long quiet sigh around 4.3 seconds, one small rustle of fabric as the coach lifts his hand around 5.4 seconds, and then his low tired voice carrying the single resigned line between 5.9 and 8.4 seconds - the only speech in the video; Shen Mo stays silent throughout. After 8.4 seconds no voice is heard at all: at most a faint slide of the coach's shoes as he glances back, then the room's sounds thin out as a single soft piano note and gentle rain fade in around 9.8 seconds and hold to the end.

non_diegetic_music:
Silence for the first nine and a half seconds. At about 9.8 seconds a single soft piano note enters with the faint sound of rain, quiet and sparse, and both hold unchanged until the video ends; no other music at any point.
```

<!-- P005 PROMPT END -->'''

with io.open(PATH, 'r', encoding='utf-8') as f:
    doc = f.read()

start = doc.index('## P005 ·')
end = doc.index('<!-- P005 PROMPT END -->') + len('<!-- P005 PROMPT END -->')
doc = doc[:start] + NEW + doc[end:]

with io.open(PATH, 'w', encoding='utf-8') as f:
    f.write(doc)

prompt_len = NEW.index('```text')  # 校验输出
print('P005 段 v2 已替换 | prompt 块字符数（含中文）:', len(NEW) - NEW.index('```text\n') - 9 - len('\n```\n\n<!-- P005 PROMPT END -->'))
print('文档总长:', len(doc))
