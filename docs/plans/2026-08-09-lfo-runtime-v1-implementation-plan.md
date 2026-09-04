# LFO Runtime v1 实施计划（已被当前方案取代）

**状态：Superseded**
**日期：2026-08-09**

这是早期的通用 Runtime 分阶段计划，包含 retry、recovery、lease、Attempt、复杂 DAG、分级 QC 和多 Clip 执行，因此不再反映当前目标。

当前实施只遵循 [`2026-09-05-simple-panel-execution-plan.md`](2026-09-05-simple-panel-execution-plan.md)：单 Panel package、同步 ComfyUI、逐 Panel 隔离串行执行、批准 package 完整文件字节 SHA-256（exact file SHA-256）锁、最小 QC、`ACCEPT/REJECT`、真实尾帧接力和最终一次 assembly。

任何新增代码或文档如果与当前计划冲突，应以当前计划为准；不要为历史入口、旧数据库、自动重试或复杂恢复增加兼容代码。
