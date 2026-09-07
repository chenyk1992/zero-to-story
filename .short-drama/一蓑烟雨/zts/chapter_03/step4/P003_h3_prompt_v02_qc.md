# P003 H3 Prompt v02 — 修订后提示词 QC

- 检查时间：2026-08-31（Asia/Shanghai）
- 检查范围：P003 v02 formal/candidate、P003 v01 独立 QC 指定的 C006 时间密度修复、`storyboard_brief.md` 的 P003/B011–B016/C005–C006、`speaker_registry.md`、P002 真实尾帧与 P003 黑白分镜板。
- 执行范围：仅提示词与文件交接 QC；未执行 LFO、ComfyUI 或视频生成。

## 结论

`PROMPT_V02_QC: PASS`

v02 只修复 v01 独立 QC 指出的 C006 时序密度硬阻断，保留 10 秒总长、00:05.500 切点、I2V 首帧、四句 canonical 对白及顺序、B011 零时长边界、事务逻辑和 B016 无提前笑声约束。v01 candidate、v01 self QC 与 v01 independent QC 均未修改。

## 文件与输入 SHA-256

| 文件 / 内容 | SHA-256 | 结果 |
|---|---|---|
| `step4/candidates/P003_h3_prompt_v02.md` | `C5AFBBB0BA9D0C7AE3ECE25967B232A14149A94CF21E6B6A15D169CA9DC34A5E` | v02 candidate |
| `step4/P003_h3_prompt.md` | `C5AFBBB0BA9D0C7AE3ECE25967B232A14149A94CF21E6B6A15D169CA9DC34A5E` | v02 formal |
| formal 与 candidate | 逐字节一致 | PASS |
| H3 body（UTF-8，从 `integrated_multimodal_description:` 至文件末尾） | `480C028C0AA876B73543CEF33052D67A06134CBE30323BB278499FB75269C3DE` | PASS |
| `step4/candidates/P003_h3_prompt_v01.md` | `C29A1D20E5B3DE5606B83E259F484DA12894CE9452A30AE44C64711CB985F2EC` | 未修改 |
| `step4/P003_h3_prompt_v01_qc.md` | `616B5C472900BF94F5D4B295595D176C816E188B968B750859C8B8010A58269D` | 未修改 |
| `step4/P003_h3_prompt_v01_independent_qc.md` | `A18382CC7FAF7FE8E0F4E2F6671FC1BB2A403B963AB9E857CB7004DC70B629AE` | 未修改 |
| P002 唯一真实首帧 `tails/P002_tail_r003.png` | `80FC0BC4BA306DE7D2E4B1944364E50BC3E5815F4910D4ED9E9ABA7F060119D3` | 保留 |
| `assets/boards/board_P003.png` | `832DE11E7BF39C4E724634910E78401BDBAE39C5834616BBE60C4800887FB484` | 保留 |

## v02 修订核对

- [x] 仍为 I2V；唯一运行时首帧仍是 P002 `tails/P002_tail_r003.png`，位于 00.00 秒；没有加入第二张参考图。
- [x] 仍为 10.0 秒、24 fps、9:16、0.4 MP、北宋写实电影质感；C005/C006 仍只有一个 00:05.500 切点。
- [x] B011 仍是零时长承接锚点，不回放 P002 的讥讽、递笺或起身准备动作。
- [x] 四句对白逐字保留且顺序不变：S3/D003 `藏鱼渊！` → S1/D004 `鱼在渊中是死物。再想想。` → S4/D005 `跃龙潭！` → S2/D006 `老夫题的是——聚宝塘！`；每句仅出现一次，无旁白、复述、串音或第二 take。
- [x] C006 的 D005 明确约束在 00:05.550–00:06.350；呈笺与报题为一次紧凑连续动作，报完立即收笺，不添加无声展示停顿。
- [x] D005 完成后，钱翁仅一次自然连续起身，约 00:06.400–00:07.450 完成前移、落脚、起身并站稳；不要求冗长逐项展示，不瞬移、不重置、不二次起身。
- [x] D006 明确约束在约 00:07.550–00:09.350，起身站稳后才举笺说话，保证不与 D005 重叠。
- [x] B016 hold 后移至约 00:09.450–00:10.000，至少保留 0.50 秒；只允许将笑未笑，无提前笑声、窃笑、掌声或 P004 反应。
- [x] 钱翁仍只持一把折扇和一张自己的不可读题笺，分持两手；题笺无汉字、伪文字、字幕、水印或 UI。只有钱翁起身，其他人、王方和苏轼保持既有状态。

## 交接结论

P003 v02 已消除 v01 独立 QC 唯一指出的 C006 时间密度硬阻断，可交由主代理进行最终 gate review。执行前仍须由运行包确认 `P002_tail_r003.png` 是唯一 `ref_image_0`，执行后核验真实首帧、四句口型与声道归属、钱翁单次起身、题笺无伪字及 B016 无提前笑声。
