# Hub 体验对齐：Panel 密度 + 动态 Ref2VA 参考包 — Design Spec

**Status:** Approved — implementation plan at `docs/superpowers/plans/2026-08-09-hub-parity-panel-r2v.md`  
**Date:** 2026-08-09  
**Related:** `docs/plans/visual_quality_improvement_plan.md`, zero-to-story skill, `h3_standard_r2v`  
**Decision source:** 用户确认（动态 2–9 参考包 + Hub 式提示词编译）；方案 C（密度与多参考一体）；**不做 shot 级视频执行兼容，直接移除**

---

## 1. Goal

让 LFO 在「拆镜密度」和「视频多参考调用」上对齐 MiniMax Hub / zero-to-story 的成功体验：

1. 按时长生成连续 2×4 黑白分镜 Panel，而不是被压成少量长镜头。
2. 每一段视频按 Panel 动态组装 Ref2VA（r2v）参考包：角色 / 环境 / 道具 + 本段黑白分镜板。
3. 提示词编译为 Hub 同构结构：图片 N 用途绑定 + 动作链 + 声音 + Medium Lock。
4. 有完整参考包时优先走 **r2v/Ref2VA**，避免被 `start_frame` 错误降级为 **i2v/FL2VA**。

**非目标（本规格不一次做完）：**

- 不重做整个 Provider-Agnostic Visual Mode。
- 不强制第一期就把本地 Comfy 工作流扩到 9 槽（见 §9 分期）。
- 不把 Hub 画布 GUI 搬进 Cursor；文档/资产以 workspace 文件 + agent 执行为准。

**明确不做：**

- **不做 shot 级视频执行的历史兼容 / 过渡期双轨。** 不为「旧 DAG 还能按 shot 跑视频」保留 shim。执行粒度只有 Panel；相关旧路径删除（见 §8.2）。

---

## 2. Why（问题根因）

### 2.1 体验落差不是「模型更差」，而是契约不一致

| Hub（用户验证可用） | LFO 现状 |
|---|---|
| 多张 2×4 连续分镜板，叙事铺满 | intake/decompose 常压到约 6 镜 / 30s，或 handoff 锁 45s/22 镜后仍可能被进一步压扁 |
| 每段视频绑定「本段角色设定图 + 本段黑白板」 | 常缺 `composition_ref`；有 `start_frame` 时易走 i2v |
| Hub 式长提示词明确写图片 N 用途 | `compile_r2v_blueprint` 仅弱插入 `Guided by references: <Picture N>` |
| 走多模态参考（Ref2VA） | 名义有 r2v，实际经常落到 FL2VA-i2v |

### 2.2 模式命名澄清（已核实）

| 名称 | H3 官方 / 权重 | 语义 | 图像上限 |
|---|---|---|---|
| **FL2VA**（LFO：`t2va` / `i2v` / `first_last`） | `fl2va` | 文本，或首帧 / 首尾帧驱动运动 | 最多 2（首+尾） |
| **Ref2VA**（LFO：`r2v`） | `ref2va` | 文本 + 多模态参考（角色/分镜/场景/道具等） | 图 ≤9；视频 ≤3；音频 ≤3；合计 ≤12 |

用户在 Hub 上感受到的「角色卡 + 黑白分镜板一起进视频」属于 **Ref2VA / r2v**，不是「多张图的 i2v」。

本地 `h3_standard_r2v` 已使用 `MiniMaxH3ReferenceToVideo` + `ref2va` 权重，manifest 约定 `<Picture N>` ↔ `LFO.Reference0N`，但当前工作流 **只接了 3 个 LoadImage 槽**（capability：`Fixed 3 reference slots`）。官方/API 上限为 9。

### 2.3 旧计划纠偏

`visual_quality_improvement_plan.md` 曾建议「后续 shot 的 composition_ref 用上一镜末帧」。该做法把 **Ref2VA 构图参考** 与 **FL2VA 首帧** 混用，会强化错误的 i2v 路径。

**新约定：**

- `composition_ref` = 本 Panel 黑白分镜板（或明确构图板）
- 上一镜末帧 = 可选连续性辅助，**不得顶替**黑白分镜板，也 **不得单独否决** r2v

---

## 3. Benefits

1. **叙事完整**：Panel 密度与 Hub / zero-to-story 时长规则对齐。  
2. **人物一致**：本段出场与连续性角色设定图进入参考包，并在 prompt 中钉死用途。  
3. **镜头可控**：黑白板锁定构图与动作链；prompt 明确「不采用线稿画风」。  
4. **模式正确**：完整参考包 → r2v；首帧推演 → i2v；语义不再混淆。  
5. **灵活扩展**：参考张数 2–9 由执行 Agent 按镜头判定，不写死三角色卡。  
6. **后端可演进**：逻辑层统一 `PanelPack`；执行层用 `max_ref_images` 适配 3 或 9。  
7. **无双轨负担**：删除 shot 级视频兼容后，代码与 Agent 决策面只剩 Panel→r2v。

---

## 4. Architecture overview

```text
storyboard_brief / intake
    → PanelPlan（按时长：叙事格数量 + N 张 2×4 板 + N 段视频）
    → 角色设定图 + 黑白分镜板（及可选场景/道具图）资产审批
    → 对每个 Panel：Agent 构建 PanelPack（动态 refs 2–9）
    → HubStylePromptCompiler（图片N用途 + 动作链 + 声音 + Medium Lock）
    → workflow_selector（Panel 级）：参考包完整 → confirmed r2v
    → 执行后端（Comfy r2v 或后续 API）：按 max_ref_images 入槽
```

视频粒度：**一张黑白分镜板 = 一个 Panel = 一段视频任务**（默认约 15s，适配 H3 4–15s）。  
**没有**「一镜一条视频任务」路径。

---

## 5. Panel 密度（Hub / zero-to-story 对齐）

| 总时长 | 目标镜头数 | 2×4 分镜板数 | 视频 Panel 数 |
|---|---:|---:|---:|
| 15s | 8 | 1 | 1 |
| 30s | 15 | 2 | 2 |
| 45s | 22 | 3 | 3 |
| 60s | 29 | 4 | 4 |
| 更长 | `8 + 7×(N−1)` | N | N |

规则：

- 第 1 板：Shot 01–08；第 2 板起第 1 格复用上一板末格（承接，不算新镜头）。
- `shot_count_target`（或等价字段）为硬约束；decompose / brief 扩展不得无故压到远低于目标。
- 竖屏短剧 handoff 默认仍可为 45s/22/9:16；用户或 Hub 级更长项目允许提高 N。
- 若 brief 镜头数不足目标，先扩展分镜表再生成黑白板（对齐 zero-to-story STEP 3.2）。

---

## 6. PanelPack：动态参考包（已确认）

### 6.1 契约

| 规则 | 值 |
|---|---|
| 最少 | **2**：≥1 张身份类参考（通常角色设定图）+ **1 张本 Panel 黑白分镜板** |
| 最多 | **9**（Ref2VA 官方图像上限） |
| 必含 | `composition` = 本 Panel 黑白分镜板 |
| 可选 | 更多角色、场景/环境、道具、风格锚 |
| 张数与选型 | **执行时 Agent/AI** 根据本 Panel 镜头需求判定 |
| 后端适配 | `backend.max_ref_images`（当前本地 Comfy r2v = 3；目标 API/扩槽 = 9） |

当候选数 > `max_ref_images`：按优先级裁剪，prompt 只描述实际入槽的「图片 N」，并记录 `trim_reason`。

### 6.2 裁剪优先级（非写死张数）

1. 本 Panel 黑白分镜板（composition，必留）  
2. 本段主戏角色设定图  
3. 连续性需要的配角设定图（可标明「仅前段人物连续性参考」）  
4. 环境 / 场景参考  
5. 关键道具参考  
6. 风格锚（仅当前序仍有空位）

### 6.3 逻辑结构（实现时可落地为 dataclass / JSON）

```text
PanelPack {
  panel_id: str
  beat_range: [start, end]             # brief 叙事格范围；含承接格语义；非视频任务 ID
  storyboard_bw_asset_id: str          # 必有
  refs: [
    {
      slot: int,                       # 1..K，与提示词「图片N」/<Picture N> 一致
      role: character|scene|prop|style|composition,
      asset_id: str,
      entity_id: str,
      purpose: str                     # 用途句，写入提示词
    },
    ...
  ]                                    # len in [2, min(9, max_ref_images)]
  characters_in_panel: [character_id…]
  trim_reason: str | null
}
```

### 6.4 Agent 判定输入

- 本 Panel 覆盖镜头表（出场角色、场景、道具、空间关系）
- 已审批资产库（角色设定图、场景/道具图、各 Panel 黑白板）
- 上一段末态 / 连续性需求
- `backend.max_ref_images` 与当前 workflow family（必须为 ref2va/r2v）

---

## 7. HubStyle 提示词编译（已确认）

每个 Panel 生成 **一段**（或同序多段拼接）自然语言提示词，结构固定：

1. **开场 / 承接状态**（可从上一段动作末态继续）  
2. **图片 N 绑定**（逐张：是什么、用途、负向约束）  
3. **故事动作链**（连续自然段；含空间关系与转场；非表格罗列）  
4. **声音设计**（环境声 / 动作声 / 必要电子提示 / 静默；明确不要 BGM）  
5. **Medium Lock + 质量负向**（画风钉死；防身份漂移、时间闪烁、可读错字等）

### 7.1 与现实现差异

| 现 `compile_r2v_blueprint` | 目标 |
|---|---|
| `Guided by references: <Picture 1>, …` | 中文（或用户语言）「图片N是…」用途句 |
| 单镜短 description 拼装为主 | Panel 级动作链（对齐 `video_prompt_list` Panel 段） |
| 声音 / Medium Lock 弱或不完整 | 强制声音段 + Medium Lock 收尾 |

`<Picture N>` 与「图片 N」必须与 `PanelPack.refs[].slot` 及 Comfy/API 入槽顺序一致。

### 7.2 黑白板用途句（默认）

对 `role=composition` 的默认 purpose（可覆盖）：

> 仅参考构图和动作链，不采用线稿画风。

角色卡默认 purpose 示例：

> 保持身份、发型、服饰、体型与关键道具不变。

连续性配角可标注：

> 仅作为前段人物连续性参考。

---

## 8. Workflow 选择策略（纠偏）

### 8.1 新优先级（Panel / 视频任务）

1. **PanelPack 满足最少契约**（黑白板 + ≥1 身份参考，且资产 approved）→ **`confirmed` r2v**  
2. 用户显式要求首尾帧插值，或策略指定 FL2VA → `first_last` / `i2v`  
3. 参考包不完整且 `visual_required` → `blocked`（补视觉资产），**默认不再静默 t2va 糊弄 Panel 视频**  
4. `start_frame` 仅作可选连续性辅助，**不得**在参考包完整时抢占为 i2v

### 8.2 删除 shot 级视频执行兼容（用户确认）

**决策：** 不为历史兼容保留 shot 级视频规划/选择/提交双轨。过渡期 shim（「Panel 包装 shot 组」）**不做**。

| 层级 | 保留什么 | 删除什么 |
|---|---|---|
| 叙事文档 | `storyboard_brief` 分镜表行（写作用的叙事格，填入 2×4 板） | 把这些行当成可独立提交的视频任务 |
| 运行时模型 | `Panel` / `PanelPack` / Panel 级 prompt / Panel 级 DAG 任务 | 按 `Shot` 选 workflow、按 shot 建 video task、shot 级 i2v 连续性作为主路径 |
| 参考规划 | 读 `PanelPack`；Agent 动态 2–9；后端裁剪 | 固定 3 槽角色塞满、`R2V_INELIGIBLE` 空列表导致静默降级等旧 shot 启发式（以 Panel 版替换） |

**好处（精简 + 降误导）：**

1. **代码面变小**：少一套 shot↔Panel 适配、少双路径分支与「兼容开关」。  
2. **Agent 不易走错**：提示词/工具/文档只描述 Panel→r2v，不会再被「先选 shot 模式 / 先抽 start_frame」带偏。  
3. **效果目标单一**：优化只盯 Hub 同构产物（板 + 参考包 + 一段视频），不为旧短镜头 i2v 产物留后门。  
4. **调试成本低**：失败时只查 PanelPack / 提示词 / r2v 入槽，不在 shot 与 Panel 两套状态机之间排障。

**说明：** brief 里仍可有「镜头 01…22」表格行——那是**写分镜板用的叙事格**，不是 LFO 视频执行单元。实现时应改名或文档标注为 `beat` / `cell` / `分镜格`，避免与已删除的 shot 任务概念混淆（命名清理列入实现计划）。

参考包超限时：按 §6.2 裁剪并在 purpose 中说明，**禁止**用空 bindings 把整段任务打成非 r2v。

---

## 9. 执行后端适配

| 后端 | `max_ref_images` | 说明 |
|---|---:|---|
| 当前本地 `h3_standard_r2v` | 3 | 已支持 `<Picture 1..3>`；第一期可用，Agent 组包后裁到 ≤3 |
| 目标本地扩槽 / API Ref2VA | 9 | 第二期；逻辑契约不变 |

分期建议：

- **P1（本规格实现重点）：** Panel 密度硬约束 + `PanelPack` 动态组包 + HubStyle 提示词 + selector 纠偏；本地先跑 3 槽裁剪路径。  
- **P2：** 扩展 Comfy r2v 工作流槽位至接近官方 9，或增加 mmx API Ref2VA 路由。  
- **P3：** 场景/道具设定图批量进入资产库，丰富 Agent 可选参考。

---

## 10. 与 zero-to-story / 短剧 handoff 的衔接

- `storyboard_brief.md` 仍是信息中枢；Panel 镜头表、台词、音效保留在文档中。  
- 短剧 `/桥接` 产物可继续生成 brief + intake；视觉链路改为：审 brief → 设定图 → 黑白 Panel 板 → `video_prompt_list` / `PanelPack` → r2v。  
- Cursor 环境无 Hub 画布时：以 workspace 文件为源，不假装调用 `hub_canvas_*`；skill 文档后续可另开变更说明运行时适配（本规格不强制改 skill 正文）。

---

## 11. Testing / Acceptance

### 11.1 单元 / 契约

- Panel 时长 → 镜头数 / 板数计算正确（含承接格）。  
- `PanelPack`：最少 2、必含 composition；裁剪尊重优先级与 `max_ref_images`。  
- HubStyle 编译：含图片 N 用途、动作链、NO BGM、Medium Lock；slot 顺序一致。  
- selector：参考包完整 → r2v；不得因存在 `start_frame` 降为 i2v。

### 11.2 集成 / 手工验收

- 用一集短剧或「我今天不上班」跑通：≥1 角色设定图 + ≥1 黑白板 → 提交 r2v（非 i2v）。  
- 提示词抽查：接近 Hub 结构（图片用途句 + 动作链 + 声音 + Medium Lock）。  
- `max_ref_images=3` 时：2 角色 + 1 板可完整入槽；更多候选时裁剪可解释。

### 11.3 验收标准（用户可感知）

1. 拆镜密度不再明显短于同时长 Hub 产物。  
2. 视频任务在资产齐全时稳定走 r2v。  
3. 人物一致性与镜头调度同时改善（相对纯 i2v / t2va）。  
4. 参考张数可随镜头变化（2–min(9, backend)），而非固定 3。

---

## 12. Risks

| 风险 | 缓解 |
|---|---|
| 本地仅 3 槽，群戏/多道具被裁 | P1 记录 trim；P2 扩槽或 API |
| Agent 组包不稳定 | 提供默认启发式 + 必含规则；允许用户改 Pack |
| Panel 视频时长超过 H3 15s | Panel 默认 ≤15s；超长拆 Panel 或询问用户 |
| 黑白板被模型当成线稿风格 | purpose 硬编码「不采用线稿画风」+ Medium Lock |
| 旧 shot 级代码残留误导 Agent | P1 直接删除视频执行相关 shot 路径与双轨文档；测试断言不存在 per-shot video task |

---

## 13. Open items（实现计划阶段再细化）

1. `PanelPack` 落库位置（独立 JSON vs storyboard 扩展字段 vs image_requests 旁路）。  
2. Agent 组包是 CLI 子命令、pipeline 钩子，还是 skill 内联步骤。  
3. P2 优先扩本地 Comfy 槽还是走 mmx API。  
4. zero-to-story `SKILL.md` 的 Cursor 运行时适配（hub_* → workspace/mmx）是否同期修改。  
5. 叙事格命名：`beat` / `cell` / 保留 brief 表格序号——实现时统一，避免再出现执行态 `Shot`。  
6. 现有 `storyboard.json` 的 `shots[]` 字段：迁移/删除策略（一次性 breaking，不设兼容读路径）。

---

## 14. Spec self-review

- [x] 无「固定 3 张」作为契约；已改为动态 2–9 + 后端裁剪  
- [x] composition = 黑白板；末帧不顶替  
- [x] i2v vs r2v 术语与官方 Ref2VA/FL2VA 对齐  
- [x] 提示词结构与用户确认的 Hub 样例同构  
- [x] 范围：P1 可落地，P2/P3 标明分期  
- [x] 无 shot 级视频双轨/过渡 shim；明确删除兼容  
- [x] 无未解释占位符

---

## 15. Approval

用户已确认（2026-08-09）：

1. ReferencePack 动态 2–9，必含黑白板 + ≥1 身份参考，执行 Agent 判定。  
2. 提示词编译为「图片 N 用途 + 动作链 + 声音 + Medium Lock」。  
3. **不做 shot 级视频执行历史兼容**；相关逻辑直接移除，执行粒度仅 Panel——为精简代码并减少 Agent 误导。

请审阅本文件（含 §8.2）；若无修改意见，下一步进入 **implementation plan**（`docs/superpowers/plans/`）。
