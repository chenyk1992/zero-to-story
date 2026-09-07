# STEP 3 黑白分镜板 QC 收口报告

## 结论

- 项目：一蓑烟雨 / 第三章
- 范围：P001–P015，共 15 张正式黑白分镜板
- 当前状态：STEP 3 CLOSED
- STEP 4：尚未进入
- 依据：board_generation_ledger.md、各版本独立 QC 结论及本次正式文件哈希复核

正式板的最终硬门禁均为 PASS。P001 的上游锚点为 N/A；P002–P015 的边界锚点均为 PASS。版本尝试数按 ledger 中已记录的 vNN 候选计算，重试次数为尝试数减一；历史 v00 文件保留，但不计入正式版本链。

## 正式板与不可变通过候选

所有正式板均为 1672×941，比例约 16:9。本次逐一核验正式板与对应不可变通过候选的字节及 SHA-256，15/15 一致。

| Panel | 最终正式路径 | 对应不可变通过候选 | 尺寸 | SHA-256 | 尝试/重试 | 最终硬门禁 |
|---|---|---|---|---|---:|---|
| P001 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P001.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v05.png | 1672×941 | 90A9AFEECB27D10EED8D238F4F14C9EF57F55F0E6CC2C727DBE4D9E850BAB46D | 5 / 4 | PASS（G/S/T/M/B/P；A=N/A） |
| P002 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P002.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v05.png | 1672×941 | 731115F0648D5019A84FD21C77A8303C5CF5A91E1FEB60C7E4EB10C76DA3608E | 5 / 4 | PASS（G/S/T/M/B/A/P） |
| P003 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P003.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v06.png | 1672×941 | 832DE11E7BF39C4E724634910E78401BDBAE39C5834616BBE60C4800887FB484 | 6 / 5 | PASS（G/S/T/M/B/A/P） |
| P004 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P004.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P004_v01.png | 1672×941 | C84EB5E68D25FE202AC555DC221370BD8FA304A7B35C72FF68B19BF4DE71E99C | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P005 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P005.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P005_v01.png | 1672×941 | 845146607B69C897557B118220BE3CB4C5F5EB1A3DCFE568BC215CD8F261CD79 | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P006 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P006.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P006_v01.png | 1672×941 | FECC4AE61653F2471C4281838B0A1B02D8D0B99F9F8736C59570747DF75B0336 | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P007 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P007.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P007_v01.png | 1672×941 | F92A2F4EA6205CE6B4B6805F9DB05781C76141D973940E3682936BD79CBF0129 | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P008 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P008.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P008_v01.png | 1672×941 | A85820B77EF1F0675FDFB557C9AEF14021840F45305A0FEC5C9151E62B643ADB | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P009 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P009.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P009_v01.png | 1672×941 | C59E8AFF152C2FED3149935B49E52379ABD0799F3651750D5D9A3646C66C620C | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P010 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P010.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P010_v01.png | 1672×941 | 92C57BC2068766607660B934FCF443D4FB428EBF23D7D4F0AD4C6189C15E7A07 | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P011 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P011.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P011_v01.png | 1672×941 | FEAEFD7657A3100264B7231FF91B4E1FEBB0F59A9A751D1B022FBF690F34D5DE | 1 / 0 | PASS（G/S/T/M/B/A/P） |
| P012 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P012.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v03.png | 1672×941 | 3C67647F7A6D599D9587BBFD7A10A8BFF7A76E4138A68C89E93824040BCD747A | 3 / 2 | PASS（G/S/T/M/B/A/P） |
| P013 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P013.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v05.png | 1672×941 | 8D8EF0E0B57EDB7140FF11FF9AFD9B27EA0C79A801AD20A5CC8B9F05AD8B535A | 5 / 4 | PASS（G/S/T/M/B/A/P） |
| P014 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P014.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v05.png | 1672×941 | 1F8C891EE89733F66FD578B5AF71B49F4C3BD770B2F3D9B671BF741DCB10F3A7 | 5 / 4 | PASS（G/S/T/M/B/A/P） |
| P015 | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P015.png | E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P015_v01.png | 1672×941 | F99572DE365336EAABE166736159CD4B7C45EF3BE47F1A1F95483D06AE117268 | 1 / 0 | PASS（G/S/T/M/B/A/P） |

## 正式文件完整性核验

- 正式板总数：15
- 正式板缺失：0
- 正式板尺寸异常：0；全部为 1672×941
- 正式板与对应通过候选逐字节一致：15/15
- 正式板 SHA-256 唯一数：15
- 重复正式 SHA-256：0
- 旧失败候选：全部保留，未删除、未覆盖、未重新接入正式链
- 正式板路径范围：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P001.png 至 board_P015.png

## 版本重试与主要失败根因

| Panel | 主要未晋级版本 | 主要根因 / 处理 |
|---|---|---|
| P001 | v01、v02、v03、v04 FAIL；v05 PASS | v01 风格模态失败（STYLE-MODALITY-001：细化古装/环境，不是严格火柴人）；v02 叠加网格方向/面部点问题；v03 为 1536×1024、3:2 画布，违反 16:9 硬门禁；v04 同样未晋级；v05 最终通过。 |
| P002 | v01、v02、v03 FAIL；v04 未晋级；v05 PASS | STYLE-MODALITY-001（细化背景/人物）；COMIC-MARK-001（动作强调短线）；PROP-LIMB-STATE-001（多手、多笺）；v04 继续修订后由 v05 通过。 |
| P003 | v01、v02、v03、v04 FAIL；v05 未晋级；v06 PASS | COMIC-MARK-001；CONTINUITY-ANCHOR-BEAT-001（左上边界及 B016 将笑未笑缺失，v02/v03 连续失败）；PROP-LIMB-STATE-001（v04 复制多手/多笺）；v06 修复禁用漫画符号后通过。 |
| P004 | 无已记录失败版本；v01 PASS | 一次生成通过。 |
| P005 | 无已记录失败版本；v01 PASS | 一次生成通过。 |
| P006 | 无已记录失败版本；v01 PASS | 一次生成通过。 |
| P007 | 无已记录失败版本；v01 PASS | 一次生成通过。 |
| P008 | 无已记录失败版本；v01 PASS | 一次生成通过。 |
| P009 | 无已记录失败版本；v01 PASS | 一次生成通过。 |
| P010 | 无已记录失败版本；v01 PASS | 一次生成通过。 |
| P011 | 历史 v00 作废；v01 PASS | v00 不进入新流程参考链；v01 作为新流程候选通过。v00 文件保留，ledger 未将其作为正式版本。 |
| P012 | v01、v02 未晋级；v03 PASS | TIME-JUMP-STATE-001：B061 时间跳切后未完全清空婚礼装饰/人物/残留；v03 以完整画布编辑修复为素净无人院落。 |
| P013 | v01、v02、v03、v04 未晋级；v05 PASS | STYLE-MODALITY-001；BEAT-POSE-READABILITY-001（B064 同步右转、B066 低头读信）；CHARACTER-ANATOMY-001（巢儿附加圆形/重影及 B066 第五人）；v05 只编辑 B066 删除多余人物后通过。 |
| P014 | v01、v02、v03 未晋级；v04 未晋级；v05 PASS | BEAT-POSE-READABILITY-001（B071 自指指尖不落在头部中心区域）；SHOT-BEAT-DIFFERENTIATION-001（C027 close-up 与 C028 group shot 区分不足）；v05 增强 B068 后景两人反应后通过。P014 v02 明确为 FAIL 候选；v03 ledger 已更正为“失败候选，仅作为完整画布编辑输入”。 |
| P015 | 无已记录失败版本；v01 PASS | 一次生成通过；三 Setup 与两个内部硬切均纳入收口核对。 |

## 14 个边界锚点

每条均为下一 Panel 左上零时长边界，复现上一 Panel 右下完成态；14/14 PASS。

| 序号 | 下一板 / 左上锚点 | 必须复现的上一板 / 右下态 | 状态 |
|---:|---|---|---|
| 1 | P002 / B006 | P001 / B006：文士们已开始挥毫；王方仍在中央；钱翁右侧已转头看左侧池边苏轼、尚未开口 | PASS |
| 2 | P003 / B011 | P002 / B011：苏轼看水、题笺待呈、钱翁一手扇一手持笺准备起身 | PASS |
| 3 | P004 / B016 | P003 / B016：钱翁持笺、众人将笑未笑 | PASS |
| 4 | P005 / B021 | P004 / B021：题名动作完成、苏轼双手抬起待击 | PASS |
| 5 | P006 / B026 | P005 / B026：青衣丫鬟右后来路站定，双手托唯一空白题笺，尚未交接 | PASS |
| 6 | P007 / B031 | P006 / B031：苏轼独自怔住，朝王方手中唯一空白题笺 | PASS |
| 7 | P008 / B036 | P007 / B036：竹径中王弗先停一拍后自然笑起 | PASS |
| 8 | P009 / B041 | P008 / B041：王弗头部/躯干已转向池水，尚未回答 | PASS |
| 9 | P010 / B046 | P009 / B046：竹径稳定双人构图，王弗左、苏轼右、丫鬟后景 | PASS |
| 10 | P011 / B051 | P010 / B051：苏轼手停纸边完成反问，苏辙持唯一毛笔 | PASS |
| 11 | P012 / B056 | P011 / B056：两前臂两手叠合、两烛、墙上两影 | PASS |
| 12 | P013 / B061 | P012 / B061：数月后素净无人院落、零婚礼残留、石桌中央 | PASS |
| 13 | P014 / B066 | P013 / B066：恰好四人，巢儿前俯低头双手持唯一信，三人直立空手 | PASS |
| 14 | P015 / B071 | P014 / B071：恰好四人，巢儿左手持信、右手自指脸/鼻部区域，尚未开口 | PASS |

## 硬切与 Setup 核对

| 位置 | 切点 | 视觉/事务逻辑 |
|---|---|---|
| P007 | B031 → B032 | 从文会中苏轼凝望王方手中唯一题笺的尾态，硬切到同日竹径中王弗与丫鬟等候、苏轼随后进入；左右轴线与人物距离保持。 |
| P010 | B046 → B047 | 从竹径双人回应硬切至夜书房兄弟对坐，场景、光线、桌案和道具逻辑明确变化。 |
| P012 | B056 → B057 | 从夜书房两手/两烛锚点硬切至北宋婚礼院落；夜间桌案、纸笔不带入院落。 |
| P012 | B060 → B061 | 同一 Clip 内跳切至数月后；婚绸、人物、鞭炮纸、烟全部消失，只留裸院墙/屋檐、普通地面和石桌。 |
| P015 | B074 → B075 | C029 院落群像硬切至 C030 夕阳院中苏轼独处北望；群体完全消失。 |
| P015 | B075 → B076 | C030 夕阳独处硬切至 C031 廊下；程夫人压抑咳嗽与三名青年背影建立新空间，苏洵不混入背影组。 |

## P012 与 P015 收束硬门禁

### P012 “数月后”末态

P012 v03 的 B061 已通过：右下格为同一院落数月后的完全素净空场，零绸带、零花结、零灯笼、零宾客、零新人、零人物、零鞭炮纸、零烟、零婚礼残留；仅保留裸露院墙/屋檐几何线、清楚石桌和普通地面。时间字样“数月后”不在分镜图内，留给后期叠加。

### P015 收束

P015 v01 已通过：C029 覆盖 B071–B074 的院落群像，C030 由 B075 以低位夕阳圆盘表现苏轼独自北望，C031 由 B076 切到廊下程夫人一手压抑咳嗽与苏轼、苏辙、巢儿三名不回头的北向背影；不吐血、不倒下，苏洵不进入三青年背影。P015 完成全章 STEP 3 的收束，不进入 STEP 4。

## 归档保全

所有旧失败候选、未晋级候选和原始生成缓存均保留。未删除、未覆盖候选，未将失败版本重新接入正式锚点链。本报告只收口 STEP 3 的板级 QC 与文件完整性，不包含 STEP 4 提示词或 LFO 视频生产。
