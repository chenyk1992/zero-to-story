# P004 H3 I2V v04 — 口型可见性修订自检

- 检查时间：2026-08-31（Asia/Shanghai）
- 检查范围：P004 v04 candidate/formal、v03→v04 差异、P004/B016–B021/C007–C008 固定输入与 P003 真实尾帧。
- 执行范围：仅提示词文件与交接 QC；未执行 LFO、ComfyUI 或视频生成。

## 结论

`PROMPT_SELF_QC: PASS`

v04 仅修复 v03 C008“只见双手但要求画内口型同步”的构图冲突：保留紧桌面斜侧近景及唯一桌面实体，并让苏轼下半脸与嘴部位于画面上缘或侧缘，在 D008 时清晰可见且口型同步。v03 已有的 C007 钱翁胸口以上站姿/折扇出画或袖遮、C008 单题笺/单砚台/单毛笔、唯一题字与 B021 禁门均保留。

## 文件与输入 SHA-256

| 文件 / 内容 | SHA-256 | 结果 |
|---|---|---|
| `step4/candidates/P004_h3_prompt_v04.md` | `3E89B472A6D610C8A0624D6D78843070D777CB0AE15D281EB24AA2EF5083F4DA` | immutable candidate |
| `step4/P004_h3_prompt_v04.md` | `3E89B472A6D610C8A0624D6D78843070D777CB0AE15D281EB24AA2EF5083F4DA` | formal |
| formal 与 candidate | 9787 bytes，逐字节一致 | PASS |
| H3 body（UTF-8，从 `integrated_multimodal_description:` 至文件末尾，保留尾换行） | `FA2CFA7D62B142DB5CD5F609D65B27FE730E8B1AEEC723E26DAE5D112EC6F5BD` | PASS |
| v03 candidate（未修改基线） | `688816728C9DB834591C98CB5850A00DD8D30D3F649E0837EEB4B8E891B3B125` | 保留 |
| P003 唯一真实首帧 `tails/P003_tail_r002.png` | `06C765A7A19030FB11ACA4F8E221142A434BEA6DFC7B165CEE5A8DC75C50E766` | 唯一精确 first-frame 输入 |

## v03→v04 最小差异核验 — PASS

- [x] 仅修改 C008 开头构图句：主体仍为双手/袖口、题笺、砚台、毛笔、木桌与虚焦池水；新增苏轼下半脸和嘴部在画面上缘或侧缘可见，满足 D008 画内口型同步。
- [x] 仍明确移出其他纸张、册页、散笺、文字区域、扇子、凳椅及其他背景道具；钱翁和折扇不入画或仅不可辨虚焦背景。
- [x] 未改变 12.0 秒、24 fps、9:16、0.4 MP、唯一 `00:05.500` 切点、I2VA 首帧和 A 侧轴线。
- [x] D007/D008 中文原文、说话人 S5、出现次数和顺序未变；D008 仍在 C008 且只出现一次。
- [x] B021 `00:11.000–00:12.000` 仍为双手抬起、掌心分离的待击掌状态；无提前击掌、唤鱼或鱼群。

## 交接结论

提示词层自检通过，可提交主代理独立 gate review。生成前仍须使用上述 P003 真实尾帧作为唯一 `ref_image_0/first_frame`；本报告不代表 LFO、ComfyUI 或视频语义 QC 已通过。
