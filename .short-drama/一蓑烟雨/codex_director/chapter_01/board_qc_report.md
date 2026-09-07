# 2×3 黑白分镜板 QC — 《一蓑烟雨》第一章·Codex 导演竞赛版

## 生成与判定

- 生成方式：built-in `image_gen`，每个 Panel 一次直出一张 2 行 × 3 列六镜板。
- 生成日期：2026-08-27。
- 目标：12 Panel = 12 分镜板 = 12 Clip；P002 起左上格承接上一板右下格。
- 判定依据：`storyboard_brief.md` 的 Panel 映射、角色锚点、连续性账本和硬失败条件。
- 审批依据：用户授权导演代理常规审批；导演逐板直接目检。

## 正式板清单

| Panel | 项目资产 | 平台原始路径 | 网格/镜序 | 角色与道具 | 边界承接 | 文字/媒介 | 结论 |
|---|---|---|---|---|---|---|---|
| P001 | `assets/boards/board_P001.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-be9c16b5-2cbe-48a0-ac9b-e7c2794888f2.png` | 恰好 2×3；S001–S006 顺序正确 | 摘印、剥袍、木枷入画；苏轼身份正确 | 项目开场；右下锁住灰白中衣跪姿与左前景木枷 | 黑白铅笔线稿；无文字 | `PASS` |
| P002 | `assets/boards/board_P002.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-779f7573-cb07-4bc1-a76c-2851fa123aa9.png` | 2×3；S006–S011 | 单一木枷完成抬起、合拢、铁销；白发老吏与成年巢儿正确 | 左上复现 P001 右下；右下巢儿从右后方入场 | 无文字、无彩色 | `PASS` |
| P003 | `assets/boards/board_P003.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-eaa78d0a-c166-41c3-97eb-7f21379d64bb.png` | 2×3；S011–S016 | 成年巢儿精瘦；双枪交叉不伤人；御史无笑、持空白诏卷 | 左上复现巢儿入场；右下御史近景锁定 | 无文字、无现代手势 | `PASS` |
| P004 | `assets/boards/board_P004.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-8deb60d1-7cc9-4cbd-b6c1-ec1465e8f7eb.png` | 2×3；S016–S021 | 戴枷者为无头巾苏轼；押离、入车、启程完整 | 第三版左上恢复上一板御史同景别近景；右下囚车远离 | 空白牌匾与诏卷 | `PASS`（v3） |
| P005 | `assets/boards/board_P005.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-02b14aaf-5f13-45ee-91ac-a27b46a3e425.png` | 2×3；S021–S026 | 单车、跪送人群、单炷香；巢儿追车、跌倒、再起顺序正确 | 左上复现囚车远离；右下巢儿伸手追车 | 无字门面 | `PASS` |
| P006 | `assets/boards/board_P006.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-219dcf4f-e83c-4fc5-8e76-f003bcc26265.png` | 2×3；S026–S031 | 苏轼木枷/车栏一致，无持续笑；车轮压缝清楚 | 左上复现追车；右下为无文字纯黑 | 纯黑格无字符 | `PASS` |
| P007 | `assets/boards/board_P007.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-60f1afa0-36b7-454b-b793-7163e59e12fb.png` | 2×3；S031–S036 | 青年巢儿为近成年比例；一捆柴；青年苏轼身份明确 | 左上纯黑；右下青年苏轼向右窗起身 | 黑白线稿、空白书页 | `PASS` |
| P008 | `assets/boards/board_P008.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-facdc61b-512a-40c5-b5de-d423ecdd4770.png` | 2×3；S036–S041 | 推双窗、跌坐柴捆、上下对话空间成立；巢儿双掌解释、无 V 手势 | 左上同景别复现苏轼起身；右下苏轼靠窗、巢儿背景 | 无文字 | `PASS` |
| P009 | `assets/boards/board_P009.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-9b925ed9-16de-40b7-acd7-e18c52709c54.png` | 2×3；S041–S046 | 苏洵、苏轼、巢儿三身份区分；门槛、柴捆和蹲下平视正确 | 左上复现窗边苏轼；右下巢儿转看苏洵 | 无文字 | `PASS` |
| P010 | `assets/boards/board_P010.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-fc3e4ea9-adc3-4165-b28e-9a6d9557a350.png` | 2×3；S046–S051 | 苏洵判断/转身/背影决定顺序正确；青年二人握手可读 | 左上复现巢儿视线；右下握手起身锁定 | 无文字 | `PASS` |
| P011 | `assets/boards/board_P011.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-1f1d82e8-7f6f-46e3-b38a-53078abd80d6.png` | 2×3；S051–S056 | 握手匹配递笔；道具明确为中国毛笔而非铅笔；单笔、空白纸 | 左上复现握手；右下笔尖触空白纸 | 纸、书均无字 | `PASS` |
| P012 | `assets/boards/board_P012.png` | `C:\Users\Administrator\.codex\generated_images\01a03f35-be37-7e33-a41d-2031a4bb864f\exec-08927b8f-a098-466e-aca4-a4cede50e9df.png` | 2×3；S056–S061 | 掌心描迹无字；问名、望山、转身、同笑顺序成立；两只麻雀 | 左上复现空白纸笔尖；右下窗内二人仍可辨、飞雀收束 | 无字、无现代手势 | `PASS` |

## 失败与修正记录

| Panel / 版本 | 归档路径 | 失败根因 | 处理 |
|---|---|---|---|
| P004 attempt 1 | `assets/boards/rejected/board_P004_attempt1_identity-fail.png` | S018–S020 把巢儿布头巾继承给戴枷者，苏轼身份被替换 | 硬失败；移除巢儿身份参考并明确“木枷只属于无头巾苏轼”，整板重做 |
| P004 attempt 2 | `assets/boards/rejected/board_P004_attempt2_boundary-framing-fail.png` | 戴枷者身份已修复，但新板左上把上一板右下御史近景拉成全景 | 连续性失败；把御史腰部以上、诏卷占下半、宽翼幞头贴边的构图写成边界锁，整板重做 |
| P004 attempt 3 | `assets/boards/board_P004.png` | 身份与边界构图均修复 | 采用 |

两个失败根因不同，未进行同根因盲目换 seed；每次都改变引用或构图策略后再生成。

## 总结

- 正式板：12/12 `PASS`。
- 网格：12/12 恰好 2 行 × 3 列、6 个等大格；无标题区、并格、跨格或额外小格。
- 镜序：12/12 与 Panel 映射一致。
- 跨板左上承接：11/11 通过；P004 经两次返工后通过。
- 角色年龄与身份：青年 19/17 岁均为近成年比例；1079 与 1056 无年龄融合。
- 关键道具：木枷、囚车、柴捆、旧毛笔、空白纸数量与归属通过。
- 文字：无可读文字、伪文字、数字、标签、UI 或水印；黑场、宣纸与掌心保留后期跟踪面。
- 媒介：统一黑白铅笔/炭笔制作分镜；细节高于火柴人草图但未进入写实照片或彩色成片风格。

结论：2×3 黑白分镜板阶段 `PASS`，可进入逐 Panel `$h3-prompt-writing` 阶段。
