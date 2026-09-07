# P004 H3 Prompt v02 — 闭扇视觉硬风险最小修订 QC

- 检查时间：2026-08-31（Asia/Shanghai）
- 检查范围：P004 v02 formal/candidate、v01→v02 最小差异、`storyboard_brief.md` 的 P004/B016–B021/C007–C008、`creative_blueprint.json`、`speaker_registry.md`、P003 真实尾帧和 P004 黑白分镜板。
- 执行范围：仅 STEP 4 提示词修订与文件交接 QC；未执行 LFO、ComfyUI 或视频生成；未修改 v01、其他 Panel 文件、分镜或角色资产。
- 修订原因：P004 r001 画面抽查发现 C007 约 2 秒钱翁把已批准的合拢扇展开。v02 只收紧钱翁扇子的画面可见状态，并在 C008 避免钱翁及扇子漂移；不改变时间轴、对白、文字策略、首帧、镜头轴或故事动作。

## 结论

`PROMPT_SELF_QC: PASS`

v02 是针对 C007 闭扇失败的最小提示词修订，可交由独立提示词 QC。该结论只表示文本结构和修订范围通过自检，不代表 P004 视频已生成或视频级语义 QC 已通过。

## 文件与输入 SHA-256

| 文件 / 内容 | SHA-256 | 结果 |
|---|---|---|
| `step4/candidates/P004_h3_prompt_v02.md` | `DA884E90F71C64274523619B71781A82D3662B86653AA6BE3506B5B2ECF800FA` | immutable candidate |
| `step4/P004_h3_prompt_v02.md` | `DA884E90F71C64274523619B71781A82D3662B86653AA6BE3506B5B2ECF800FA` | formal；与 candidate 逐字节一致 |
| formal 与 candidate | 8618 bytes，逐字节一致 | PASS |
| H3 body（UTF-8，从 `integrated_multimodal_description:` 至文件末尾，保留文件尾换行） | `4B1EEDE641FF599A98EB88ECEBCA9CF55FA675CFC793F5A160C7994FCCFE04B5` | PASS |
| v01 formal/candidate SHA（未修改基线） | `CBF8FD3940F9C419FE59DA4067F95EA38154412512BBD13A6FFDCF3F98592917` | 保留 |
| v01 H3 body SHA（未修改基线） | `E36A5631F20441166ED6E08C5B6E4F214AE19EDF88A2ECAC4721E241571C47E0` | 保留 |
| `workspace/projects/yisuo-ep003-codex-director/tails/P003_tail_r002.png` | `06C765A7A19030FB11ACA4F8E221142A434BEA6DFC7B165CEE5A8DC75C50E766` | v01/v02 共用唯一精确 first-frame |
| `assets/boards/board_P004.png` | `C84EB5E68D25FE202AC555DC221370BD8FA304A7B35C72FF68B19BF4DE71E99C` | 仅作创作/分镜输入，未作为 runtime reference |
| `storyboard_brief.md` | `E1ACDEBFEC245D10C849CEB2781A82AF194944B6BD13193E36C102CC4A5C92B1` | v01/v02 对照输入 |
| `creative_blueprint.json` | `79023B430267A6EFC18405523DAF65D6A269258D71CA4A939E95B915AB4AB136` | v01/v02 对照输入 |
| `step4/speaker_registry.md` | `5C499703B3A7C26052F0D1A3DB828BEA925CF3C215EA3640F24B15BF6D895307` | v01/v02 对照输入 |

## v01→v02 最小差异核验 — PASS

- [x] 保持同一首行、I2VA、唯一 `<Picture 1>`、同一 P003 尾帧 SHA、同一 `00:05.500` 切点、同一 A 侧轴线和两个 `[Shot]`。
- [x] 保持 12.0 秒、24 fps、9:16、0.4 MP、北宋写实电影质感；没有改动任何动作时间窗、镜头景别或运镜。
- [x] 保持 D007 与 D008 原文、标点、说话人 `(S5)`、各出现一次及对白顺序；没有新增、删除、重写或移动对白。
- [x] 保持“唤鱼池”只在约 `00:08.500` 以后于唯一关键题笺清晰出现；没有改变其他文字禁门或 B021 末 1 秒。
- [x] 唯一实质修订位于钱翁道具段：C007 加强“扇子全程完全闭合、低于胸口/腰侧或被宽袖自然遮挡、扇手静止、扇骨/扇面不展示、无第二把扇、与单笺分离”；C008 加入“钱翁不入画，若残留仅作虚焦背景且无可辨扇面/扇动/新道具”；环境声补充无扇子运动声。
- [x] v01 仍作为不可变基线保留，v02 未覆盖 `step4/P004_h3_prompt.md`。

## 1. C007 闭扇约束 — PASS

- [x] C007 从 B016 立即释放群笑，其他表演、苏轼 D007、钱翁涨红和苏轼转向笔墨均保持不变。
- [x] 钱翁一只手仍单独持自己的唯一不可读题笺；另一只手始终持同一把完全合拢的扇子，位置限制在胸口以下/腰侧或被宽袖自然遮挡。
- [x] 明确禁止扇子打开、展开扇面、露出扇骨、摆动、挥动、弹动、复制、与题笺融合或变成第二把扇；扇手保持静止，不产生动作诱因。
- [x] 不改变钱翁的 B016 身体姿态，不重演举笺/报题/起身，不引入新的动作或道具。

## 2. C008 避免扇子漂移 — PASS

- [x] C008 的写字、题笺可读文字、D008、停笔、抬手、B021 和 P005 边界全部保持 v01 原样。
- [x] 钱翁优先完全不进入 C008 近景；若构图仍保留边缘/远处一小部分，则仅作为虚焦背景，不显示可辨扇面、不出现扇子运动、不增加新道具。
- [x] C008 仍保持苏轼右手单笔、左手单笺的取笔→蘸墨→悬腕→落笔→停笔→抬手事务逻辑，未引入一手多物。

## 3. 结构与禁门 — PASS

- [x] 提示词仍按 I2VA base form 排列：首行 first-frame instruction，随后 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music`。
- [x] 没有增加第二张运行时图片、角色卡、分镜板标签、LFO 字段或 ComfyUI 操作；`board_P004.png` 只保留在审计输入记录中。
- [x] 没有新增 P003 D003–D006、P005 掌声/唤鱼/鱼群奇观；无字幕、水印、UI、伪文字、现代物件或清宫元素。

## 交接结论

P004 H3 I2V v02 candidate/formal 已落盘且逐字节一致，首帧 SHA、时间轴、对白、文字策略和镜头轴均继承 v01；唯一行为修订为闭扇与 C008 钱翁避开/虚焦约束。可提交独立提示词 QC；独立 QC 通过和用户确认前不得创建或执行 P004 execution package。
