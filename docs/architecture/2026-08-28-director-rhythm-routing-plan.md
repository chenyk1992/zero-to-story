# Director 节奏与引用路由（当前边界）

**状态：Current creative guidance**
**日期：2026-09-05**

导演阶段仍由创作 Skill 决定节奏、Camera Setup、operation、首尾帧关系和 H3 提示词；LFO 不理解故事板语义，也不根据分镜板格数自动增加镜头。本文只说明这些创作事实如何交给当前的单 Panel 执行链。

## 创作侧规则

- 一个 Panel 对应一个 Clip；六个 Beat 是语义时刻，R2V 分镜板只选 2–6 个有控制价值的时刻；两者都不等于 H3 Shot 数。
- Camera Setup 的变化才产生真实 cut；Panel 时长服从表演和节奏，不由固定格数推导。
- 先锁定 operation，再决定必要的运行时素材；若选择 R2V，同时在 STEP 1 锁定可变网格布局，分镜板的存在仍不是反向选择 R2V 的信号。
- 同场连续接力优先 I2V + 上一段真实尾帧；同时硬锁首尾才用 FL2V；需要一张可变网格分镜板承载强一致性、多状态控制或明确硬切时使用 R2V。
- R2V 整张分镜板是一张图片、一个 fixed slot 和一个 H3 `<Picture N>`；板内格子不拆成独立引用。
- H3 提示词由 `$h3-prompt-writing` 生成并经用户确认，LFO 逐字消费，不在执行阶段补写。

## 执行交接

创作侧为当前 Panel 输出一个 package，其中 `clips` 恰好只有一个元素；所有 Panel package 和最终 assembly package 都直接放在同一 `workspace/projects/<project_id>/` 项目根目录并使用唯一文件名。通过 `validate` 取得 package 完整文件字节 `package_sha256`（exact file SHA-256）供用户批准。LFO 只接收当前 Panel 的 package 路径、批准 hash 和可选 machine ID；尾帧输出路径是调用方在 `ACCEPT` 后用 ffmpeg 提取的辅助参数，不是 LFO `execute` 参数，上一段尾帧若是生成输入，必须先固化在下一包素材引用中。

LFO 按 `validate → execute --approved-sha256` 同步运行一次 ComfyUI 并返回生成结果；`plan` 仅为可选诊断。调用方做最小 QC 后给出 `ACCEPT` 或 `REJECT`。`REJECT` 即停止；重做由用户显式重新准备当前 Panel，不由运行时自动重试或改写创作计划。

## 接力与组装

只有 `ACCEPT` 的真实尾帧才能传给下一个 Panel。所有 Panel 按顺序 `ACCEPT` 后，才进行一次最终 `cut` assembly。公开执行流程不要求长寿命执行器、复杂边界 evidence、失败候选或恢复记录；调用方不读取或维护恢复记录。
