# P003 H3 Prompt v01 — 自检报告

- 检查时间：2026-08-31（Asia/Shanghai）
- 检查范围：P003 v01 candidate、formal prompt、`storyboard_brief.md` 的 P003/B011–B016/C005–C006、`creative_blueprint.json`、`speaker_registry.md`、P002 真实承接尾帧。
- 执行范围：仅检查 STEP4 I2V 提示词与交接约束；不调用外部模型，不执行 LFO、ComfyUI 或视频生成。

## 结论

`PROMPT_SELF_QC: PASS`

该结论只表示提示词层面通过，不代表视频已生成或视频级语义 QC 已通过。

## 文件与输入 SHA-256

| 文件 / 内容 | SHA-256 | 备注 |
|---|---|---|
| `step4/candidates/P003_h3_prompt_v01.md` | `C29A1D20E5B3DE5606B83E259F484DA12894CE9452A30AE44C64711CB985F2EC` | immutable candidate |
| `step4/P003_h3_prompt.md` | `C29A1D20E5B3DE5606B83E259F484DA12894CE9452A30AE44C64711CB985F2EC` | formal prompt；与 candidate 逐字节一致 |
| H3 body（UTF-8，从 `integrated_multimodal_description:` 至文件末尾） | `AAA273FCF38FE05181DC435925D5ECD7769E4316169969A6860CC27414CF627C` | 不含首行 I2V 对齐指令 |
| `workspace/projects/yisuo-ep003-codex-director/tails/P002_tail_r003.png` | `80FC0BC4BA306DE7D2E4B1944364E50BC3E5815F4910D4ED9E9ABA7F060119D3` | 唯一 first-frame；哈希与用户指定一致 |
| `assets/boards/board_P003.png` | `832DE11E7BF39C4E724634910E78401BDBAE39C5834616BBE60C4800887FB484` | 仅作 B011–B016 规划输入，未作为运行时 reference |

## 固定规格与 I2V 结构

- [x] 首行符合 I2VA 结构：`<Picture 1>` 在 `0.00` 秒完全引用；只绑定 P002 真实尾帧，未加入分镜板、角色卡或第二张运行时图片。
- [x] 保留 10.0 秒、24 fps、9:16、0.4 MP、北宋写实电影质感；仅定义两个实际 `[Shot]`，切点为 `00:05.500`，未按六格机械拆镜。
- [x] `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music` 顺序正确；`non_diegetic_music: N/A`。

## 时序与对白检查

- [x] B011 是 `0.00` 秒零时长边界锚点：从承接尾帧已完成姿态立即前进，不回卷、不重演 P002 讥讽或题笺准备。
- [x] C005 对应 `00:00.000–00:05.500`、固定 A 侧 medium two-shot；C006 从 `00:05.500` 切入、对应 `00:05.500–00:10.000`、同轴 fixed medium shot。
- [x] C005 只含两句且按顺序各一次：文士甲 `(S3)` 说 D003 `<d>[Chinese] 藏鱼渊！</d>`，随后王方 `(S1)` 说 D004 `<d>[Chinese] 鱼在渊中是死物。再想想。</d>`。
- [x] C006 只含两句且按顺序各一次：文士乙 `(S4)` 说 D005 `<d>[Chinese] 跃龙潭！</d>`，随后钱翁 `(S2)` 说 D006 `<d>[Chinese] 老夫题的是——聚宝塘！</d>`；无串音、旁白、复述、额外台词或第二 take。
- [x] S3/S4 为独立成年男文士声源；S1 为王方稳定男声；S2 为钱翁稳定成熟男声；没有复合 speaker、`<scenetrans>` 或 `<cutoff>`。

## 人物、道具与边界检查

- [x] 首帧承接时钱翁明确坐在既有右前位置、持自己的唯一不可读题笺；B011 不被分配新动作或台词。
- [x] C005 文士甲从既有席位短距离呈递一张笺，王方一次摇头/拒绝后笺退回原席；苏轼保持坐姿看鱼并静默。
- [x] C006 文士乙不离席呈递独立笺；钱翁仅在 S4 完成 D005 后，从坐姿自然连续起身一次并举起自己的唯一笺；其他人保持既有坐/站状态，不集体站立、不换座、不越桌。
- [x] 钱翁的折扇与唯一题笺分持且不合并；无第二笺、第二扇、毛笔复现或道具复制。所有题笺斜置/失焦、不可读，不生成汉字、伪文字、字幕、标题卡、水印或 UI。
- [x] B016 只锁定钱翁报完 D006、持唯一不可读题笺且得意，众人将笑未笑；笑声爆发和 P004 反击完全留给下一 Panel。

## 声音与交接意见

- [x] 现场声仅保留池水、微风、纸张、衣料、笔触，以及钱翁单次起身的克制座椅/脚步声；对白不在 `overall_soundscape` 重复。
- [x] D006 后保持安静：无笑声、窃笑、掌声、额外说话或现代声音；非叙事音乐为 N/A。

P003 v01 可交由主代理进行审批与后续执行前检查。执行后仍须核验真实首帧、四句口型与声道归属、钱翁单次自然起身、题笺无伪字，以及 B016 无提前笑声。
