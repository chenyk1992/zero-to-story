# LFO Runtime v1 设计（已被当前方案取代）

**状态：Superseded**
**日期：2026-08-09**

本文记录早期的通用运行时设计，曾包含持久化 Run、DAG、Attempt、retry、recovery、lease、复杂 QC 和多 Clip 执行。它不再是当前实现或文档依据。

当前唯一有效设计见 [`docs/plans/2026-09-05-simple-panel-execution-plan.md`](../plans/2026-09-05-simple-panel-execution-plan.md)。当前规则为：

- breaking redesign，不兼容旧执行入口；
- 每个 execution package 只含一个 Panel/Clip；
- 每 Panel 一个独立的短生命周期执行单元，严格串行；
- 同步调用官方 ComfyUI/comfy-cli；
- 批准的 package 完整文件字节 SHA-256（exact file SHA-256）是唯一锁；
- 失败即停，无自动重试、失败候选或复杂恢复；
- 只做最小 QC，结果为 `ACCEPT` 或 `REJECT`；
- `ACCEPT` 后提取真实尾帧，全部 Panel 通过后一次性组装。

历史文本中的状态机、恢复 API、旧 CLI、production lock 扩展和多 Clip DAG 不应继续实现或引用。
