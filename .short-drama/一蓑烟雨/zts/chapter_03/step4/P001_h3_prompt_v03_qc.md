# P001 H3 Prompt v03 — 独立自检报告

- 检查时间：2026-08-30 23:17:36 +08:00
- 检查范围：仅检查 H3 提示词重编译与 v02→v03 的单点修复；不代表视频生成或视频语义通过。
- 结论：`PROMPT_SELF_QC: PASS`

## 不可变版本与哈希

| 文件 | SHA-256 | 备注 |
|---|---|---|
| `step4/candidates/P001_h3_prompt_v01.md` | `58417D1C964EE14863ECADEFB8E06374A8492F5AA00461F0CEEAA452874F6C67` | 历史失败候选，未改写 |
| `step4/candidates/P001_h3_prompt_v02.md` | `11EA710A96D954ED1002E7528BAC680D49A995C2B4A24F284F6590E5F7F368E1` | 历史正式候选，未改写 |
| `step4/candidates/P001_h3_prompt_v03.md` | `905A0D701537F7F95C234F7FCB357F0B0DE0B183EA5924FFCE5CDBFC13271821` | 本次 immutable 候选 |
| `step4/P001_h3_prompt.md` | `905A0D701537F7F95C234F7FCB357F0B0DE0B183EA5924FFCE5CDBFC13271821` | 正式文件，与 v03 候选逐字节一致 |

## 结构与固定输入检查

- [x] 正式文件与 `candidates/P001_h3_prompt_v03.md` SHA-256 相同，逐字节一致。
- [x] 保留 `R2V / video.reference_to_video`，没有伪造精确首帧或尾帧。
- [x] 保留 10.0 秒、9:16、已批准的 0.4 MP 输出 profile。
- [x] 保留 `<Picture 1>` 苏轼卡、`<Picture 2>` 王方卡、`<Picture 3>` P001 黑白分镜板及其原顺序；没有新增角色卡或参考标签。
- [x] 仍只有两个实际 Camera Setup：C001 00:00.000–00:04.000，C002 00:04.000–00:10.000。
- [x] `subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music` 六段顺序保持不变。
- [x] 王方仍使用全章注册表的 `S1`，D001 原文、顺序和一次性发声约束保持不变。

## 单点修复覆盖

- [x] C001 和 C002 都把钱翁固定在右前最近席位，并要求胸部至右手完整留在竖幅安全构图内。
- [x] C002 改为稳定、略宽的 medium group framing；明确禁止右侧裁切、推近越过钱翁、摇移/焦点变化或前景遮挡导致折扇/右手消失。
- [x] 钱翁全程右手仅持一把清晰可辨的折扇；左手远离纸面和笔；不得拿笔、碰题笺或落笔。
- [x] 只有其他文士在宣告后取笔并接触空白题笺，纸面保持不可读。
- [x] 最后一秒保持钱翁胸部、右手和折扇连续可见；仅轻转头侧眼苏轼，闭口、不发声、不开始讥讽；尾态明确保留唯一折扇。

## v02→v03 最小差异

除版本/输出 profile 元数据和本次变更说明外，仅改动 C001/C002 的钱翁构图、折扇/笔纸互斥状态与末秒尾态约束。未改故事板 Beat、对白、人物卡、参考顺序、生成模式、时长或镜头切点。v01/v02 immutable candidates 保持原样。

## 交接意见

提示词层自检通过，可以交由根代理做独立 H3/执行包 QC。必须在 LFO 生成后重新审查头帧、中段和真实尾帧：本报告不替代视频语义 QC；在钱翁折扇、右手完整构图、闭口侧眼和其他文士落笔状态均可视证之前，不得把 P001 尾帧交给 P002。
