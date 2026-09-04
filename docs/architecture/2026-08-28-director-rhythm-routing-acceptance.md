# Director 节奏与路由验收记录

**状态：Superseded by the 2026-09-05 simple Panel execution baseline**
**日期：2026-08-28**

早期验收记录验证了 Beat、Camera Setup、I2V/FL2V/T2V 路由和跨 Panel 真实尾帧的创作规则。它不再定义运行时的 retry、审计、分级 QC 或恢复行为。

当前仍有效的创作结论：

- 六个 Beat 表达语义时刻；R2V 分镜板从中选取 2–6 个有控制价值的时刻，Camera Setup 决定实际 H3 Shot；
- 分镜板不是 R2V 选择信号；
- 同场连续镜头优先使用上一段真实尾帧作为 I2V 首帧；
- FL2V 只用于确需同时锁定首尾帧的 Panel；
- H3 原生音频是否保留由已确认的音频策略决定，不把模型自发人声当作台词；
- 每个 Panel 单独交给 LFO，严格串行，`ACCEPT` 后才能提取尾帧并继续下一段。

本文件中的旧分级 QC、`PASS_WITH_REPAIR`、自动重试和复杂 evidence 记录不再适用。当前执行与验收以 [`docs/plans/2026-09-05-simple-panel-execution-plan.md`](../plans/2026-09-05-simple-panel-execution-plan.md) 为准。
