# LFO 运行时 QC 与前置准备度边界

## 原则

镜头、对白、动作、身份、空间、道具和画面文字的“应该是什么”，在进入 LFO 前由 `storyboard_brief.md`、`creative_blueprint.v2`、已确认的选择性视觉控制资产和 H3 prompt manifest 一次性确定。LFO 是执行运行时，不重新理解故事，也不把提示词里的每个形容词变成二元验收合同。

生产锁（`lfo.production_lock.v1`）建立后，故事板、Panel 数量、Panel/Setup 时长、对白顺序和时窗、参考素材、operation 与剪辑关系均不可变。LFO 阶段最多接受同一 Clip 的确定性重试，或由 `$h3-prompt-writing` 提交一次保持 `plan_hash` 不变的完整提示词重写；不因失败退回故事板重排。

## LFO 只保留的三类检查

### 1. 生成质量

`media.qc`（为兼容历史任务仍保留该 task id）只确认生成任务返回了非空文件。它不检查解码、时长、分辨率、帧率、编码、黑帧、冻结帧、中段动作、身份/空间、道具或文字语义。缺少文件属于执行失败，允许 `retry_same`；不要据此重排故事板。

### 2. 音频质量

`audio.mix` 负责按已锁定的 `lfo.audio_acceptance.v1` 检查：

- 是否存在合同要求的音轨；
- 可选的峰值/能量指标；
- 若提供 ASR/说话人分析，逐句文本、说话人和起止时窗是否与前置对白清单一致；
- 说话事件是否意外重叠。

没有分析证据或分析返回 `INCONCLUSIVE` 时，记录为需人工听审的 `inconclusive`，不自动升级为创作失败。确有音频合同不符时，当前 Clip 进入 `WAITING_PROMPT_REVISION`，由提示词 Skill 重写对白/声音表达；达到锁定的修订次数后 `block_for_user`。

### 3. 首尾帧/边界连续性

`media.boundary_evidence` 只生成客观证据：上一 Clip 尾帧、下一 Clip 首帧、尾 2 秒 + 头 3 秒预览、接触表和 metrics。它不自动判定剧情连续性。Creative Skill 结合已确认分镜和视频理解给出 `PASS`、`PASS_WITH_REPAIR` 或 `FAIL`：

- `PASS`：可直接提取真实尾帧接力；
- `PASS_WITH_REPAIR`：完成确定性裁切/重定时/硬切或音频替换并复核，若尾帧变化则重新提取；
- `FAIL`：当前 Clip 不得接入下一 Clip。生产锁后只可重试当前 Clip 或提示词重写，不能重新排 Setup/Panel。

## 不再由 LFO 自动判定的内容

解码/时长/分辨率/帧率/编码/采样率、黑帧/冻结帧、中段对白抢拍、角色换脸/越轴、背景书册/砚台/纸面伪字等，不是 LFO 的自动 QC 类别。需要它们成为硬约束时，必须在 `creative_blueprint.v2`、当前 Panel 的已批准视觉资产或 manifest 中前置规划并由创作侧审阅；普通背景差异不应因为不等于提示词而触发重生成。

## 运行顺序与止损

1. LFO 接收前：`validate_creative_blueprint.py`、`validate_prompt_manifest.py` 和生产锁校验全部通过，并取得用户确认。
2. Clip 生成后：生成质量检查 → 音频混合与音频合同检查 → 由创作侧审阅单片和相邻边界。
3. 执行失败（无文件、服务/文件系统错误）：`retry_same`，遵守运行时重试上限。
4. 已生成内容但音频/边界合同不符：`rewrite_prompt`，只修改完整 H3 提示词，携带相同 Clip `plan_hash`；不修改故事板字段。
5. 修订预算耗尽、锁哈希不匹配或问题需要改变时长/镜头/对白顺序：`block_for_user`，停止当前 Clip 并等待用户决策。

每次重试都保留旧 run、旧提示词、证据和最终采用片段；不覆盖历史产物。只有通过的真实尾帧才能进入下一 Clip 的 `first_frame`。

## 最小记录

```text
Panel / package revision / run id
production plan_hash / prompt_revision
generation quality: PASS | FAIL
audio quality: PASS | INCONCLUSIVE | FAIL
boundary: PASS | PASS_WITH_REPAIR | FAIL
recovery: retry_same | rewrite_prompt | block_for_user
hard blockers: 无或具体原因
approved clip and tail path
```
