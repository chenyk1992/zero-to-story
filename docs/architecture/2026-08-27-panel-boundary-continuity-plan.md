# Panel 边界连续性（当前最小规则）

**状态：Current**
**日期：2026-09-05**

本文件只保留跨 Panel 接力所必需的规则。早期关于边界 evidence、接触表、分级 QC、`PASS_WITH_REPAIR`、复杂 assembly revision 和自动恢复的方案已移除；完整执行顺序见 [`docs/plans/2026-09-05-simple-panel-execution-plan.md`](../plans/2026-09-05-simple-panel-execution-plan.md)。

## 核心规则

- `1 Panel = 1 Clip = 1 次同步生成`。
- Panel 必须严格按顺序执行；ComfyUI 单任务队列不并行提交。
- 当前 Panel 只有在上一 Panel `ACCEPT` 后才启动，且只在 operation 需要时使用上一段真实末帧。
- 下一段从真实尾帧后的新动作继续，不重演上一段收尾，不用文字“脑补”末态。
- 调用方对当前 Panel 输出做最小 QC 后给出 `ACCEPT` 或 `REJECT`；`REJECT` 立即停止链路。
- 不保存失败候选、不自动重试、不做复杂边界审计。

## 接力顺序

```text
生成 P001 → 最小 QC → ACCEPT → 提取真实尾帧
      ↓
生成 P002（需要时将尾帧作为 first_frame）→ 最小 QC → ACCEPT
      ↓
重复直到最后一个 Panel → 一次最终 assembly
```

I2V 使用上一段真实尾帧作为唯一精确 `first_frame`；FL2V 按已确认计划使用真实首帧和尾帧；T2V 或硬切 R2V 只将尾帧用于人工连续性检查。尾帧变化时，依赖它的下一 Panel 重新准备 package 和批准 hash。

## 最小边界判断

只检查当前片段可播放，以及与上一段拼接后没有明显倒带、重复收尾或姿态/视线/道具状态跳变。LFO 不对镜头风格、细节命中率或轻微随机偏差评分；需要语义判断时交给创作侧/用户。

## 禁止事项

- 一次性把所有 Panel 交给一个长寿命执行器；
- 并行提交多个 Clip；
- 把分镜板存在当作 R2V 选择条件；
- 用旧尾帧、文字描述或猜测画面替代实际尾帧；
- 用边界审查结果触发 LFO 自动重试或自动修复。
