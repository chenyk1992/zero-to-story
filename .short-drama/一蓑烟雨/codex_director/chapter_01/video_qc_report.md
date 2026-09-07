# 视频 QC 报告

## 审片规则

- 每个 Panel 先检查文件规格与完整运动，再以 MiMo 做客观描述，最后由导演依据 `storyboard_brief.md` 的硬失败条件裁决。
- 只有 PASS 或经确定性修复后 PASS 的镜头，才提取真实末帧并进入下一 Panel。
- H3 的生成成功不代表创作通过；身份、年龄、因果、关键道具、精确对白和边界连续性优先于局部漂亮画面。

## Panel 记录

| Panel | Run / 成片 | 技术检查 | 语义与表演检查 | 边界检查 | 裁决 |
|---|---|---|---|---|---|
| P001 | `run-87c9adafb7ae` / `workspace/projects/yisuo-ep001-codex-director/final/p001-r001/yisuo-ep001-codex-p001-r001-run-87c9adafb7ae.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 42 岁苏轼身份稳定且始终不笑；摘印、摘帽、褪官袍因果完整；无现代物件或可读伪字；MiMo 客观描述与人工关键帧检查一致 | 末帧为灰白中衣苏轼跪于画面右侧，两差役从左侧将同一副旧木枷送至肩前；可无跳切承接 P002 | **PASS** |
| P002 r002 | `run-7c8ec7336caf` / `workspace/projects/yisuo-ep001-codex-director/final/p002-r002/yisuo-ep001-codex-p002-r002-run-7c8ec7336caf.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 木枷闭合、铁销和白发老吏完成；但最后动作段未生成成年巢儿 | 最后两秒回跳到 P001 的“木枷逼近”状态，已闭合木枷消失，巢儿未进入末帧，无法承接 P003 | **REJECT / 硬失败**；P002 扩为 15 秒，r003 重做 |
| P002 r003 | `run-77a7e3227167` / `workspace/projects/yisuo-ep001-codex-director/final/p002-r003/yisuo-ep001-codex-p002-r003-run-77a7e3227167.mp4` | 15.104s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 同一副双片旧木枷准确闭合并由木槌锁销；白发老吏身份稳定，精确说出“苏学士在任三年，修堤赈粮，他没有罪啊”；巢儿为成熟精瘦成年男性，无幼童化 | 末四秒保持新构图：老吏近前景、巢儿从右侧跨向中轴、戴枷苏轼仍在远处中央；末秒没有回跳，可直接承接 P003 | **PASS** |
| P003 r004 | `run-ddfe53207aca` / `workspace/projects/yisu-ep001-codex-director/final/p003-r004/yisu-ep001-codex-p003-r004-run-ddfe53207aca.mp4` | 13.688s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 成年巢儿身份稳定；两根长枪只以枪杆成 X 拦截、无伤人；两次质问原文准确；御史冷静无笑。单独听辨复核确认原生音为“写诗。”；诏卷仅有不可辨识的抽象纸纹 | 实际尾帧御史闭唇、目光正下、双手持诏卷稳定；可承接 P004 | **PASS** |
| P004 r005 | `run-04fd1f48641b` / `workspace/projects/yisuo-ep001-codex-director/final/p004-r005/yisuo-ep001-codex-p004-r005-run-04fd1f48641b.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 巢儿瞳孔反应、戴枷起身、入囚车、囚车沿中轴离开均完成；但苏轼戴枷特写持续明显微笑，违背角色与导演硬约束 | 囚车尾态本身正确，但中段表演不可用 | **REJECT / 硬失败**；更换种子并强化闭唇、嘴角水平、面颊不抬后以 r006 重做 |
| P004 r006 | `run-2bdb5438bdd1` / `workspace/projects/yisuo-ep001-codex-director/final/p004-r006/yisuo-ep001-codex-p004-r006-run-2bdb5438bdd1.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 巢儿瞳孔、押离、入车和囚车远离均完成；但苏轼木枷近景仍出现连续明显笑容 | 囚车尾态正确，但人物表演硬失败 | **REJECT / 硬失败**；r007 改为木枷上缘遮挡下半脸、用眼神承担反应 |
| P004 r007 | `run-77876277a3af` / `workspace/projects/yisuo-ep001-codex-director/final/p004-r007/yisuo-ep001-codex-p004-r007-run-77876277a3af.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 眼神、押离、入车、囚车远离完成；但木枷特写仍被模型补成明显笑脸 | 尾态正确，角色表演仍违背“克制不笑” | **REJECT / 硬失败**；r008 改为全程不露苏轼嘴部的眼睛/后脑/枷木构图，并移除苏轼角色卡参考 |
| P004 r008 | `run-600caa7779f0` / `workspace/projects/yisuo-ep001-codex-director/final/p004-r008/yisuo-ep001-codex-p004-r008-run-600caa7779f0.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 御史、成年巢儿眼神、戴枷苏轼的枷木/眼神、押离、入车、囚车离开均成立；全程没有苏轼笑脸 | 末帧为囚车沿中轴向城门远去、两侧跪送，可接 P005 | **PASS** |
| P005 r009 | `run-6f36a3a87ab3` / `workspace/projects/yisuo-ep001-codex-director/final/p005-r009/yisuo-ep001-codex-p005-r009-run-6f36a3a87ab3.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 囚车远行、跪送、香火、成年巢儿追车、自然跌倒与立即再起均成立；原生声保留，字幕轴覆盖“先生——！” | 尾帧巢儿仍在右侧奔跑、右手伸向远车，未回跳 | **PASS** |
| P006 r010 | `run-7ae8fd2083d5` / `workspace/projects/yisuo-ep001-codex-director/final/p006-r010/yisuo-ep001-codex-p006-r010-run-7ae8fd2083d5.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 追车、车内枷栏、车轮撞石缝、纯黑均成立；但苏轼车内正面近景出现连续明显笑容 | 纯黑尾态正确，但中段表演硬失败 | **REJECT / 硬失败**；r011 移除苏轼角色卡并改为眼睛/枷木/栏影构图 |
| P006 r011 | `run-ac8abefa229e` / `workspace/projects/yisuo-ep001-codex-director/final/p006-r011/yisuo-ep001-codex-p006-r011-run-ac8abefa229e.mp4` | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 巢儿在车外追视、苏轼被枷木与栏影切割、车轮撞石缝，表情克制无笑；末约两秒纯黑 | 真实尾帧为纯黑，可硬切进入 P007 的年代/地点转场 | **PASS** |
| P007 r012 | `run-77358deac639` / `workspace/projects/yisuo-ep001-codex-director/final/p007-r012/yisuo-ep001-codex-p007-r012-run-77358deac639.mp4` | 13.688s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 先纯黑约一秒，再切入眉山竹院；巢儿为精瘦近成年少年，始终只带一捆柴，贴窗偷听；青年苏轼在书案边抬眼并凝视窗缝。人工接触表确认无可读字、无现代物件；MiMo 对年龄的“中年”判断属保守误判 | 尾帧为成年化青年苏轼坐/倚在窗边的侧脸，窗格与光线稳定；P008 从该坐姿锁定并完成起身 | **PASS** |

## P001 证据

- 1fps 接触表：`assets/qc/P001_contact_1fps.jpg`
- 首秒检查：`assets/qc/P001_first_second.jpg`
- 尾秒检查：`assets/qc/P001_last_second.jpg`
- MiMo 客观描述：`assets/qc/P001_mimo_description.txt`
- 已批准真实尾帧：`assets/tails/P001_tail.png`

## P002 证据

- 被拒版接触表：`assets/qc/P002_contact_1fps.jpg`
- 通过版接触表：`assets/qc/P002_r003_contact_1fps.jpg`
- 通过版尾秒检查：`assets/qc/P002_r003_last_second.jpg`
- MiMo 客观描述：`assets/qc/P002_r003_mimo_description.txt`
- 已批准真实尾帧：`assets/tails/P002_tail.png`

## P003 证据与修复项

- 接触表：`assets/qc/P003_contact_1fps.jpg`
- 尾秒检查：`assets/qc/P003_last_second.jpg`
- MiMo 客观描述：`assets/qc/P003_mimo_description.txt`
- 已批准真实尾帧：`assets/tails/P003_tail.png`
- P003 音频单镜复核：`assets/qc/P003_audio_check.txt`，确认末句为“写诗。”；诏卷没有可读汉字，因此无需 ADR 或遮罩。
| P008 r013 | run-a8906df67f2e / workspace/projects/yisuo-ep001-codex-director/final/p008-r013/yisuo-ep001-codex-p008-r013-run-a8906df67f2e.mp4 | 12.271s；480×864；24fps；H.264 + 48kHz 双声道 AAC；约 0.415MP | 双扇窗开启、巢儿坐回同一捆柴、三句对白和无散柴均成立；但最后苏轼特写把提示要求的“单角克制微笑”演成明显咧嘴笑 | 尾态动作正确但表演硬失败，不能把宽笑带入 P009 | **REJECT / 硬失败**；r014 改为窗槛与近侧窗格遮住下半脸，只以眉眼完成调侃 |

## P007 与 P008 证据

- P007 接触表：assets/qc/P007_contact_1fps.jpg
- P007 尾秒检查：assets/qc/P007_last_second.jpg
- P007 MiMo 客观描述：assets/qc/P007_mimo_description.txt
- P007 已批准真实尾帧：assets/tails/P007_tail.png
- P008 r013 接触表：assets/qc/P008_contact_1fps.jpg
- P008 r013 尾秒检查：assets/qc/P008_last_second.jpg
- P008 r013 MiMo 客观描述：本轮复核确认对白与动作成立，但最后表情为明显宽笑，故拒片；重跑 r014。
- P008 r014 接触表：assets/qc/P008_r014_contact_1fps.jpg
- P008 r014 尾秒检查：assets/qc/P008_r014_last_second.jpg
- P008 r014 MiMo 客观描述：动作、对白、窗扇与柴捆成立，但尾秒仍为明显宽笑，故拒片；重跑 r015，进一步提高窗槛遮挡并移除所有“笑”诱因。
- P008 r015 成片：run-5249b023d173 / workspace/projects/yisuo-ep001-codex-director/final/p008-r015/yisuo-ep001-codex-p008-r015-run-5249b023d173.mp4
- P008 r015 接触表：assets/qc/P008_r015_contact_1fps.jpg
- P008 r015 尾秒检查：assets/qc/P008_r015_last_second.jpg
- P008 r015 真实尾帧：assets/tails/P008_tail.png
- P008 r015 裁决：**PASS**；窗洞、柴捆、三句对白和年龄锁成立，尾秒仅见眉眼，接受侧角造成的主扇视觉偏差。
- P009 r016 成片：run-2b431b839cce / workspace/projects/yisuo-ep001-codex-director/final/p009-r016/yisuo-ep001-codex-p009-r016-run-2b431b839cce.mp4
- P009 r016 接触表：assets/qc/P009_contact_1fps.jpg
- P009 r016 尾秒检查：assets/qc/P009_last_second.jpg
- P009 r016 真实尾帧：assets/tails/P009_tail.png
- P009 r016 裁决：**PASS**；三人身份/年龄区分清晰，苏洵以深色须发和门槛位置独立成立；巢儿右手抓衣角、柴捆完整，苏轼完成平视蹲姿，尾帧保留巢儿向门槛侧的目光。
- P010 r017 成片：run-68a0ac1b1e1a / workspace/projects/yisuo-ep001-codex-director/final/p010-r017/yisuo-ep001-codex-p010-r017-run-68a0ac1b1e1a.mp4
- P010 r017 接触表：assets/qc/P010_contact_1fps.jpg
- P010 r017 尾秒检查：assets/qc/P010_last_second.jpg
- P010 r017 真实尾帧：assets/tails/P010_tail.png
- P010 r017 裁决：**PASS**；苏洵须发与深色衣着足以区分，背身决定与两名青年纵深成立；尾帧右手握手清楚，巢儿已从柴捆起身。MiMo 对背景景深与动作时点的保守描述不改变人工逐帧结论。
- P011 r018 成片：run-f9d2e98d2d4c / workspace/projects/yisuo-ep001-codex-director/final/p011-r018/yisuo-ep001-codex-p011-r018-run-f9d2e98d2d4c.mp4
- P011 r018 接触表：assets/qc/P011_contact_1fps.jpg
- P011 r018 尾秒检查：assets/qc/P011_last_second.jpg
- P011 r018 真实尾帧：assets/tails/P011_tail.png
- P011 r018 裁决：**PASS**；握手→递笔匹配切成立，单支传统毛笔与手部归属稳定，宣纸无可读/伪可读汉字；尾秒仅留不可辨识的笔尖接触痕，保留给 P012 的确定性“天地”合成。
- P012 r019 接触表：assets/qc/P012_contact_1fps.jpg
- P012 r019 尾秒检查：assets/qc/P012_last_second.jpg
- P012 r019 裁决：**REJECT / 硬失败**；掌心出现可辨汉字样笔画，尽管名字/千金对白、檐雀和暖窗收束成立；r020 清除所有诱发文字的视觉提示并改掌心离焦悬空描划。
- P012 r020 接触表：assets/qc/P012_contact_1fps.jpg
- P012 r020 尾秒检查：assets/qc/P012_last_second.jpg
- P012 r020 裁决：**REJECT / 硬失败**；纸面与掌心继续出现可辨字样，保留为失败证据。
- P012 r021 成片：run-079e9b2d556e / workspace/projects/yisuo-ep001-codex-director/final/p012-r021/yisuo-ep001-codex-p012-r021-run-079e9b2d556e.mp4
- P012 r021 接触表：assets/qc/P012_r021_contact_1fps.jpg
- P012 r021 尾秒检查：assets/qc/P012_r021_last_second.jpg
- P012 r021 真实尾帧：assets/tails/P012_tail.png
- P012 r021 裁决：**PASS**；纸面与掌心无可读/伪可读文字，单支毛笔、人物转窗、两只檐雀和暖窗剪影成立；MiMo 复核确认画面无文字、对白清晰（逐句以人工提示词与字幕表为准）。

## 总片母版 QC

- 执行包：`workspace/projects/yisuo-ep001-codex-director/assembly-package.json`，revision 4；LFO run：`run-0ee59bce1f06`。
- 成片：`workspace/projects/yisuo-ep001-codex-director/final/chapter-01-final/yisuo-ep001-codex-chapter-01-assembly-r004-run-0ee59bce1f06.mp4`。
- 技术探针：162.126563s；480×864；9:16；约 0.415MP；24fps；H.264；48kHz 双声道 AAC；实测响度 -16.0 LUFS、LRA 12.3 LU、真峰值 -1.0 dBFS。
- 字幕：同目录 SRT 与烧录字幕一致；抽检 16.77s、31.38s、79.5s、148.5s、160.0s，开场刑场、黑场年代卡、握手→毛笔匹配切、片尾屋脊麻雀与暖窗均连续。
- 画面接触表：`assets/qc/final_r004_contact_5s_4x9.jpg`；关键帧：`assets/qc/final_r004_t79.jpg`、`assets/qc/final_r004_t160.jpg`。
- 总片裁决：**PASS / FINAL MASTER**。未发现现代物件、可读生成伪字、断轴跳回或未授权转场；P003“写诗”已用单镜音频听辨复核确认，未做不必要 ADR。
