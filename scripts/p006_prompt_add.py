# -*- coding: utf-8 -*-
"""h3_prompts.md 追加 P006 段（I2V · 教室醒来 · 切黑归属管线 + 黑板留白负约束）。"""
import io

PATH = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\h3_prompts.md'

NEW = '''

---

## P006 · 切黑·课堂醒来（i2v · 14.0s · C006 · B026–B031）

- 参考输入：**I2V**。首帧 = `scene_keyframe.P006`（master 确认资产：暖黄教室、**黑板完全干净**、沈默 16 岁低头靠窗前排、老师背影贴黑板、林燃前景左侧；画布 `asset_kf_P006 → video_P006 first_frame` 已接线）；`asset_card_shenmo_16` + `asset_card_teacher` 走 related。
- **两项口径裁决（蓝图已手术，validator PASS，brief 五处同步）**：① **切黑 0.5s 归属管线**——I2V 首帧机制下黑板区从黑场生成不可控，生成段不含黑屏；成片管线在 P006 头部前置 0.5s 黑场 + 音频静默，「光刺进来」由生成段开场眩光脉冲恢复承担（EV011.visible_proof 已注记）。② **黑板字归属后期**——生成保持黑板干净留白（负约束禁板书），日期「高一(3)班 2017 年 9 月」由后期叠字 UI-001 承担（EV012.visible_proof 已注记；C006.text_strategy prompt→post + post_asset=UI-001）。
- 机位：**fixed 起手（0–10s 完全不动）→ push-in（10–12s 缓慢匀速推近黑板右上角叠字区）→ 停住（12–14s）**；除该段推近外无任何运镜无切镜。
- 对白：D009@6.5–8.5s 显式窗「沈默！上课睡着，你还想不想念了？」= 老师 (S1) 侧影发声（on-camera，**老师仅背影/侧影不露正脸**）；全片唯一语音 + 8.5s 后无人声负约束（对冲 ~1.5s 系统性后移：实测可能落 8–10s，与 push-in 衔接可接受）。
- 人物：沈默 16 岁清瘦少年深蓝校服（露脸：猛然坐起瞪眼环顾→被斥责低头）；老师低发髻深色套装侧影。
- 声音：0–1s 环境声骤然涌入（教室嘈杂底）；~1.5s 椅腿摩擦+急促喘气（非语音）；~5.0–6.5s 粉笔敲黑板 3 次；6.5–8.5s D009；无音乐。
- 末态锁定（12–14s）：推近停住在黑板右上角留白区（后期叠字位），沈默低头虚焦前景。
- **成片管线工序（入库版）**：① 调色 `eq=saturation=1.6:contrast=1.03`（P005 v2 定版参数，全集标准）；② 头部前置 0.5s 黑场 + 音频静默；成片 ≈14.5s（设计内：14.0 含黑屏 0.5s）。
- 依赖：不依赖 P005 尾帧（scene_keyframe 独立）；P007 起依赖本 run 真实尾帧。

<!-- P006 PROMPT START -->

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic drama style. The shot holds the exact framing of <Picture 1>: a warm golden high-school classroom in September 2017, sunlight slanting in from the tall windows on the left, dust motes drifting in the light beams, worn wooden desks in the foreground, and a large clean dark-green blackboard at the front. In the center a female teacher seen from behind - a low bun, a dark suit - stands at the blackboard with a piece of white chalk in her raised hand. On the left side a slim 16-year-old boy in a dark-blue school uniform, Shen Mo, sits at a front-row desk by the window, head lowered on his folded arms as if asleep; closer to the camera on the far left another boy in a red-and-white jacket sits with his back to us. The blackboard is completely clean: no text, no writing, no chalk marks appear on it at any moment; its upper-right corner stays empty and reserved. The camera starts completely locked and static. At the very beginning a harsh glare of sunlight pulses across the room from the windows - the light flares bright for a moment, washing the frame, then quickly settles back to normal exposure, the dust igniting in the beams. At about 1.2 seconds Shen Mo jerks upright from his desk, gasping for air, eyes wide, disoriented, one hand braced against the desk edge - he looks around the classroom without saying a word. At about 4.5 seconds the teacher raps her chalk knuckles against the blackboard three times, sharp and hard, still facing the board. At about 6.5 seconds she turns halfway - still only her side profile, never showing her full face - and points her chalk toward Shen Mo as the teacher (S1) says in a sharp, stern female voice: <d>[Chinese] 沈默！上课睡着，你还想不想念了？</d> - this line is the only speech in the entire video, spoken between 6.5 and 8.5 seconds; there is no other voice, no whisper, no murmur at any other moment, and after 8.5 seconds there is no speech at all. Shen Mo lowers his head under the scolding, silent, his hands flat on the desk. At about 10.0 seconds the camera begins one slow, steady push-in toward the upper-right corner of the clean blackboard - the framing tightens gradually on the empty reserved corner while everything else stays unchanged - and the push stops at about 12.0 seconds. From 12.0 seconds to the end at 14.0 seconds everything holds: the empty upper-right corner of the blackboard in clear focus, Shen Mo's lowered head soft in the foreground, the teacher's side profile by the board, sunlight and dust unmoving; no further movement, no further sound of any kind.

overall_soundscape:
The clip opens as the room's sound floods in abruptly after the cut: classroom murmur, pages turning, a distant cough, the low hum of a ceiling fan. At about 1.5 seconds a chair leg scrapes the floor as Shen Mo jerks upright, followed by his quick breaths - breathing only, never words. At about 5.0 seconds the chalk raps the blackboard three times, sharp and dry. Between 6.5 and 8.5 seconds the teacher's sharp stern voice carries the single scolding line - the only speech in the video. After 8.5 seconds no voice at all: only the quiet classroom ambience thinning out under the sunlight.

non_diegetic_music:
No music at any point in this video.
```

<!-- P006 PROMPT END -->'''

with io.open(PATH, 'a', encoding='utf-8') as f:
    f.write(NEW)
print('P006 段已追加 | 文档总长:', len(NEW))
