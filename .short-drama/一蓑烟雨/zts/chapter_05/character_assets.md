# 角色设定图资产记录 — 《一蓑烟雨》第五章·第二名的真相

## STEP 2 状态

- 故事板与蓝图：已确认；`creative_blueprint.json` 静态预检为 `CREATIVE PREFLIGHT: PASS`。
- 复用角色：苏轼、苏辙、巢儿、苏洵；仅重新做文件与目视检查，不复制、不改名、不修图。
- 新生成角色：欧阳修、梅尧臣；使用内置 ImageGen，各生成一次，结果均已保存到本章项目资产目录，平台原始文件保留不动。
- 一次性人物：兵士、围观举子甲乙、管家和背景阅卷官使用故事板文本锚点，不建立角色卡。
- 当前结论：6/6 角色卡可承担本章身份一致性用途，STEP 2 已确认。

## 资产清单

| 角色 | 项目引用路径 | 来源 | SHA-256 | 本章用途 | 结论 |
|---|---|---|---|---|---|
| 苏轼 | `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\codex_director\chapter_01\assets\characters\char_su_shi_1056.png` | 跨章复用 | `77e938a33c82c45ca965486e7eaef2e6b95db13717f9545efe3e418df8dfde88` | P001/P003/P016 分镜板身份 | PASS |
| 苏辙 | `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_02\assets\characters\char_su_zhe_1056.png` | 跨章复用 | `824f686fbb8168b45870db55549f07a9e659002a6092db2ba19d55bcd0a9f403` | P016 分镜板与榜下兄弟关系 | PASS |
| 巢儿 | `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\codex_director\chapter_01\assets\characters\char_chaoer_1056.png` | 跨章复用 | `40c7832b1022664c87e5d9bd6ff461bfa29092972bdf0936bd79cbf0129` | P001/P016 分镜板身份 | PASS |
| 苏洵 | `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\codex_director\chapter_01\assets\characters\char_su_xun_1056.png` | 跨章复用 | `033ed842426e6f2456bef6ad43491fee88792daa611494e5e68a865f8921e51e` | P001/P016 分镜板身份 | PASS |
| 欧阳修 | `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_05\assets\characters\char_ouyang_xiu_1057.png` | 内置 ImageGen 新生成 | `ff502665992b457dcab9ab97307dbc36e4e52b71104d7becd8547002612529a5` | P008/P019 分镜板及连续身份 | PASS |
| 梅尧臣 | `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_05\assets\characters\char_mei_yaochen_1057.png` | 内置 ImageGen 新生成 | `4b5171d39441143776024e90aec589229308bb384e02cfed1a4f6dc7f567afd6` | P007/P008 分镜板及连续身份 | PASS |

> 巢儿 SHA-256 以现有跨章角色卡的已登记值为准；进入分镜板生成和执行包素材导入前仍以文件字节重新核对。

## 平台原始生成文件

- 欧阳修：`C:\Users\Administrator\.codex\generated_images\01a06ed1-4612-78e0-b0c4-d4ebc22abe9c\exec-a0969391-25a4-467d-a065-a2209fcef091.png`
- 梅尧臣：`C:\Users\Administrator\.codex\generated_images\01a06ed1-4612-78e0-b0c4-d4ebc22abe9c\exec-20a1e3b1-c631-4888-b334-9678534ac4db.png`

项目引用副本保存在本章 `assets/characters/`；平台原始文件未移动、未覆盖、未删除。

## 新角色生成 Prompt 记录

### 欧阳修

- Use case：`historical-scene`；资产类型：竖屏历史剧制作角色身份参考卡。
- 主体：50 岁北宋资深文臣欧阳修；中等身量、略宽长方脸、敏锐深眼、额纹与眼下纹、短须微灰。
- 服饰：黑色直脚幞头、低饱和深青灰圆领官袍、素暗革带。
- 版式：一张大头肩像、全身正/侧/背和一个克制三分之二表情视图；同一身份、同一服装、双脚完整。
- 参考图用途：苏洵卡只提供角色卡版式、棚拍质感和写实纹理，不继承其身份、脸、发式或服装。
- 排除：文字、标签、UI、水印、多人、身份漂移、清代服饰、现代物件、奇幻盔甲、华丽刺绣、道具、动漫、CG。

### 梅尧臣

- Use case：`historical-scene`；资产类型：竖屏历史剧制作角色身份参考卡。
- 主体：55 岁北宋诗人和阅卷官梅尧臣；清瘦、窄长脸、高颧骨、眼窝略深、灰黑短须，和欧阳修明显不同。
- 服饰：黑色直脚幞头、低饱和深褐灰圆领官袍、素暗革带。
- 版式：一张大头肩像、全身正/侧/背和一个克制三分之二表情视图；同一身份、同一服装、双脚完整。
- 参考图用途：欧阳修卡只提供官员角色卡版式、棚拍质感和幞头结构；明确排除宽脸、蓝袍和相同胡须轮廓。
- 排除：文字、标签、UI、水印、多人、身份漂移、蓝袍、宽方脸、长尖胡须、清代服饰、现代物件、奇幻盔甲、道具、动漫、CG。

## 目视 QC

| 角色 | 单一身份与视图一致 | 全身正/侧/背与双脚 | 年龄 / 脸型 / 发须 | 服饰与 Medium Lock | 无文字 / UI / 多余人物 | 结论 |
|---|---|---|---|---|---|---|
| 苏轼 | 是 | 是 | 青年宽额无须，稳定 | 月白交领长衫 | 是 | PASS |
| 苏辙 | 是 | 是 | 青年窄脸无须，与苏轼可区分 | 灰青交领长衫 | 是 | PASS |
| 巢儿 | 是 | 是 | 瘦削、日晒肤色、低髻 | 补丁土褐短褐 | 是 | PASS |
| 苏洵 | 是 | 是 | 中年长脸、浓眉、较长尖须 | 深褐交领长袍 | 是 | PASS |
| 欧阳修 | 是 | 是 | 约 50 岁、略宽长方脸、灰短须 | 深青灰圆领官袍、黑直脚幞头 | 是 | PASS |
| 梅尧臣 | 是 | 是 | 约 55 岁、窄长脸、高颧骨、灰黑短须 | 深褐灰圆领官袍、黑直脚幞头 | 是 | PASS |

## 跨资产辨识结论

- 欧阳修以深青灰官袍、略宽长方脸、较饱满中等体型为主；梅尧臣以深褐灰官袍、窄长脸、高颧骨和清瘦体型为主，双人在 P008 及后续对话中可稳定区分。
- 欧阳修与苏洵同属中年文士，但欧阳修为圆领官袍和直脚幞头、脸更宽且胡须更短；苏洵为深褐交领长袍、软幞头和更长的尖须，不构成混淆。
- 角色卡不承担剧情动作或道具所有权；考卷、朱笔、茶盏、拜帖、考篮与榜墙均以故事板连续性账本为准。

## 下游引用规则

1. 角色卡只用于生成相应 R2V 分镜板，不直接无条件加入 H3/LFO 参考槽位。
2. P001/P003/P007/P008/P016/P019 分镜板在生成时选择必要角色卡；进入 H3 时默认只传当前整张分镜板。
3. I2V Panel 只传上一段接受版真实尾帧，不再追加角色卡或分镜板。
4. 卡内未出现或偶然出现的物品不获得剧情所有权；所有剧情道具数量按 `storyboard_brief.md` 执行。

