# P004 H3 Prompt v01 — 自检 QC

- 检查时间：2026-08-31（Asia/Shanghai）
- 检查范围：P004 v01 formal/candidate、`storyboard_brief.md` 的 P004/B016–B021/C007–C008、`creative_blueprint.json`、`speaker_registry.md`、P003 真实尾帧和 P004 黑白分镜板。
- 执行范围：仅 STEP 4 提示词编译与文件交接 QC；未执行 LFO、ComfyUI 或视频生成；未修改其他 Panel 文件。
- 规范依据：已完整读取 `h3-prompt-writing/SKILL.md` 及 I2VA 所用 `references/base-en.txt`，并按 `zero-to-story` 的 Panel/Camera Setup/边界锚点交接规则检查。

## 结论

`PROMPT_SELF_QC: PASS`

P004 v01 可交由主代理做最终提示词 gate review。该结论只表示提示词结构、创作输入、对白、时序、唯一首帧和边界约束已通过自检，不代表 P004 视频已经生成或视频级语义 QC 已通过。

## 文件与输入 SHA-256

| 文件 / 内容 | SHA-256 | 结果 |
|---|---|---|
| `step4/candidates/P004_h3_prompt_v01.md` | `CBF8FD3940F9C419FE59DA4067F95EA38154412512BBD13A6FFDCF3F98592917` | immutable candidate |
| `step4/P004_h3_prompt.md` | `CBF8FD3940F9C419FE59DA4067F95EA38154412512BBD13A6FFDCF3F98592917` | formal；与 candidate 逐字节一致 |
| formal 与 candidate | 8144 bytes，逐字节一致 | PASS |
| H3 body（UTF-8，从 `integrated_multimodal_description:` 至文件末尾，保留文件尾换行） | `E36A5631F20441166ED6E08C5B6E4F214AE19EDF88A2ECAC4721E241571C47E0` | PASS |
| `workspace/projects/yisuo-ep003-codex-director/tails/P003_tail_r002.png` | `06C765A7A19030FB11ACA4F8E221142A434BEA6DFC7B165CEE5A8DC75C50E766` | 唯一精确 first-frame 资产 |
| `assets/boards/board_P004.png` | `C84EB5E68D25FE202AC555DC221370BD8FA304A7B35C72FF68B19BF4DE71E99C` | 仅作创作/分镜输入，未作为 runtime reference |
| `storyboard_brief.md` | `E1ACDEBFEC245D10C849CEB2781A82AF194944B6BD13193E36C102CC4A5C92B1` | 对照输入 |
| `creative_blueprint.json` | `79023B430267A6EFC18405523DAF65D6A269258D71CA4A939E95B915AB4AB136` | 对照输入 |
| `step4/speaker_registry.md` | `5C499703B3A7C26052F0D1A3DB828BEA925CF3C215EA3640F24B15BF6D895307` | 对照输入 |

## 1. 模式、规格与引用 — PASS

- [x] 使用 I2VA，首行严格为 `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`。
- [x] 运行时只有唯一标签 `<Picture 1>`，绑定 P003 通过版真实尾帧 `P003_tail_r002.png` 的 00.00 秒；未把 `board_P004.png`、角色卡或其他图片写成第二个 runtime reference。
- [x] 目标规格固定为 12.0 秒、24 fps、竖屏 9:16、用户已确认的 0.4 MP、北宋写实电影质感；未加入 H3 之外的执行包、ComfyUI 或 LFO 字段。
- [x] 只有两个实际 Camera Setup：C007 为 `[Shot 1]`，C008 在 `00:05.500` 切入 `[Shot 2]`；没有按六格机械拆镜。
- [x] 两个 Setup 均保持同一池畔 A 侧轴线；C007 固定 medium，C008 为侧上方 medium close-up 并小幅慢速 dolly in，符合已批准 Camera Setup 表。

## 2. B016→C007 边界与 C007 事务逻辑 — PASS

- [x] B016 被明确为 P003 已完成的零时长边界锚点；P004 从钱翁刚说完“聚宝塘”、持一张题笺与一把合拢扇、众人将笑未笑的状态立即推进。
- [x] 没有重演 D003–D006、钱翁举笺/报题、递笺或起身；没有回卷、重置、换座、越轴、反打或新地点。
- [x] 笑声所有权归 P004：群体笑声从半拍后的自然释放开始，身体仅作普通小幅晃动；D007 前后笑声自然收放，台词段无人物抢词。
- [x] D007 只由注册的苏轼 `(S5)` 逐字说一次：`钱翁，您这不是给鱼取名，是给自己家账本取名。`；钱翁只做窘迫/涨红反应，不羞辱升级，不新增台词。
- [x] 苏轼仍坐在既有池畔位置并转向钱翁后再转向案上笔墨；钱翁的一只手持唯一自己的不可读题笺，另一只手持同一把合拢扇；不生成第二扇、第二笺、扇面文字、合并道具或一手多物。
- [x] C007 末态锁定钱翁涨红、苏轼转向笔墨；不提前写字、揭示“唤鱼池”、击掌、鱼群或 P005 奇观。

## 3. C008 动作、对白与 B021 边界 — PASS

- [x] `00:05.500` 仅切换到同一 A 侧池畔书案的侧上方近景；不是空间硬切，不改变人物左右关系。
- [x] 动作顺序完整且遵循事务逻辑：苏轼坐/俯身 → 右手取一支毛笔 → 蘸墨 → 悬腕 → 在唯一关键题笺落笔 → 停笔并放回毛笔 → 双手抬起待击；左手只稳住题笺，避免一手多物。
- [x] 关键题笺在约 `00:08.500` 前不出现可读字；约 `00:08.500` 以后同一张笺只清晰显示准确的 `"唤鱼池"`，持续到片尾；其他纸张、扇子、服装、背景和画面不出现汉字、伪字、字幕、标题卡、水印或 UI。
- [x] D008 只由同一注册苏轼 `(S5)` 逐字说一次：`就叫——唤鱼池。方才我拍手为号，诸位请看。`；口型同步，语音平稳，台词不被笑声或其他说话覆盖；D008 是本片第二句且最后一句对白。
- [x] 苏轼写完后双手为空、抬起但掌心不接触；`00:11.000–00:12.000` 固定 B021，三次击掌、唤鱼、鱼群、涟漪和 P005 内容全部归下一 Panel。
- [x] D008 后无新对白；钱翁与众人只看题笺/苏轼并安静收束，不群体起身，不产生新的表演事件。

## 4. 声音与全片禁门 — PASS

- [x] `overall_soundscape` 覆盖池水、微风、群体笑声、衣料/纸张、取笔蘸墨、笔触和收束静默；笑声在 D008 前后自然退下。
- [x] `non_diegetic_music: N/A`，符合本段无非叙事音乐原则。
- [x] 禁止旁白、额外发声源、额外对白、字幕声、掌声、鱼跃水声、魔法音效、开扇脆响和扇面摩擦声；没有现代物件或清宫元素。

## 交接结论

P004 H3 I2V v01 的 candidate/formal 已封存且逐字节一致，H3 body SHA 已记录。可提交主代理进行最终 gate review；在用户确认前不得创建或执行 P004 execution package。用户确认后仍须由 LFO 逐 Panel 运行 `validate`、`plan` 和经批准的 `execute`，再对 P003 尾 2 秒 + P004 头 3 秒完成成对语义 QC；本报告不替代视频级证据。
