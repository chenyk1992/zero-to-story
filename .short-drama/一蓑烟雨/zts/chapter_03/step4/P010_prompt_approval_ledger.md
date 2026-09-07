# 《一蓑烟雨》第三章《唤鱼池》

## STEP 4 · P010 prompt approval ledger

| 项目 | 记录 |
|---|---|
| Panel | P010｜文章要不要稳｜11.0s |
| 生成模式 | R2V；苏轼/苏辙角色卡与 board_P010 作为语义参考。 |
| v01 Prompt SHA-256 | `1C648B790DB822E7348D22DD6DA3DFDA851CC97196B6AEE677F1A5385BF2238F`；formal/candidate 逐字节一致。 |
| v01 LFO run | `run-a4e1abd571d4`；输出 `final/p010-r001/yisuo-ep003-p010-r001-run-a4e1abd571d4.mp4`。 |
| v01 QC | `SEMANTIC_QC: FAIL`；第三名左缘残影/手臂、额外书页道具、政策纸伪文字。 |
| 处置 | 不登记尾帧；v02 仅强化人数、道具与空白纸面锁，其他叙事约束保持不变。 |

## v02 执行与 QC

- v02 Prompt SHA-256：`4C72BCDAABCBE553D4D9520534F365E486BC7FCEB27498197909A1DCE7FEF24B`；formal/candidate 逐字节一致。
- 执行包：`workspace/projects/yisuo-ep003-codex-director/packages/execution-package-p010-r002.json`；revision 2；LFO run `run-b1e99f32997c`。
- 成片：`workspace/projects/yisuo-ep003-codex-director/final/p010-r002/yisuo-ep003-p010-r002-run-b1e99f32997c.mp4`；SHA-256：`C2F27B0666F8B8B5265AED39E218174605251B7BD3E044EEBA33154A116E9303`。
- `SEMANTIC_QC: FAIL`；两人和轴线通过，但纸面伪字、叠放书册、砚台/墨池仍存在；不登记尾帧。
- 证据：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p010-r002-root.md`；密集抽帧 `qc/semantic-p010-r002-dense-contact.png`。

## 标准纠偏与重审

- 上述 v02 的三项失败理由中，书册/叠页、砚台/墨池和自然不可读文章墨迹均被确认为符合 canonical 场次三的环境语义，原失败结论对这些项目撤回。
- 重审记录：`workspace/projects/yisuo-ep003-codex-director/qc/semantic-p010-r002-reassessment.md`。
- 当前唯一待定项是后墙人形阴影是否提前启动 P011 墙影 tableau；未完成此项前不登记尾帧。

## v03 处置

- 原 v03 “裸桌/空白纸面”方案已因标准纠偏作废，不执行、不作为 QC 基准。
- v03 LFO 任务在采样中止，未形成可用成片；不纳入候选链。
- 如墙影被确认提前进入 P011，只允许一次 v04 定向重生：保留书册、叠页、砚台和自然文章墨迹，只清除提前墙影；保持 C019/C020、D017/D018、一次轻敲、B051 和 P011 边界不变。

## v02 根控与执行

- `ROOT_PROMPT_GATE: PASS_WITH_SEMANTIC_QC_REQUIRED`（见 `P010_h3_prompt_v02_root_gate.md`）。
- v02 必须重新 R2V 生成并完成密集画面、音频时序和 B051 尾态 QC；通过后才能解锁 P011。
- P011 仍拥有刷笔释放、承诺、叠手和墙影，不得提前进入 P010。
