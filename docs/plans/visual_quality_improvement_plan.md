# LFO 视觉质量提升实施计划（v2 — Agent 生图方案）

> **⚠️ 2026-08-09 更新：** 视频执行已迁移为 Panel-only r2v（`beats[]` + `panels[]` → `PanelPack` → r2v）。`composition_ref` 指 Panel 黑白分镜板，**不等于**上一镜 end frame；per-shot 视频路径已废弃。详见 `docs/superpowers/specs/2026-08-09-hub-parity-panel-r2v-design.md` 与 `docs/superpowers/plans/2026-08-09-hub-parity-panel-r2v.md`。

> 来源：从 `zero-to-story` skill 提取核心机制，适配 LFO 管线
> 日期：2026-08-08
> 变更：P0-B / P2 生图从 ComfyUI T2I 改为 Agent 生图指令方案
> 目标：解决 "效果差、角色一致性差" 的上游问题

---

## 现状诊断

```
Intake → LLM Decompose → Storyboard JSON → 直接生成视频
                                    ↑
                              没有任何视觉锚定
                              每次生成角色重新抽卡
                              风格约束松散
                              没有便宜的视觉审批层
```

关键缺口：
1. **无角色参考图** — decompose 输出文字描述，直接送视频模型，角色长相每次随机
2. **无 Medium Lock** — StyleGuide 只有松散描述，没有排除约束
3. **无空间关系硬约束** — decompose prompt 提了 screen_position 但没要求写进 description
4. **无视觉预览审批** — 从文字直接跳到视频，中间没有便宜的画面确认

## 核心架构决策：Agent 生图指令模式

LFO 不直接调生图模型。LFO 生成**结构化的生图指令文件**（JSON），写入 workspace。Agent 工具（MiniMax Code / Codex）读取指令文件，调用平台生图能力（`image_synthesize`），把图片写回 workspace，LFO 管线继续。

```
LFO Pipeline                    Agent Tool (MiniMax Code / Codex)
─────────                       ─────────────────────────────────
  │
  ├─ 生成生图指令文件 ──────────→  读取指令文件
  │  (workspace/<proj>/           识别 type: character_sheet / storyboard_preview
  │   image_requests/*.json)      调用 image_synthesize(prompt, ...)
  │                               图片写入 workspace/<proj>/ref_images/
  │                          ←──── 回写 image_results/*.json
  │                               (asset_path, status, seed 等)
  ├─ 检测到结果文件
  ├─ 注册 asset，继续管线
  ▼
```

**为什么这样设计**：
- 本地 ComfyUI 生图模型效果差，不值得部署 SDXL
- Agent 平台（MiniMax）生图质量远高于本地方案
- LFO 保持 pipeline 自动化能力，agent 介入点清晰可控
- 指令文件是声明式的，任何 agent 工具都能消费

---

## Phase P0-A: Medium Lock + Style Brief 硬约束

### 目标
让每个生成 prompt 末尾带一句钉死风格的排除语句，防止风格漂移。

### 改动

**1. StyleGuide 新增字段** (`src/lfo/storyboard/storyboard.py`)

```python
@dataclass
class StyleGuide:
    # ... 现有字段 ...
    medium_lock: str = ""          # "Medium: ... NOT X, NOT Y."
    style_keywords: list[str] = field(default_factory=list)
```

- `to_dict()` / `from_dict()` 同步更新

**2. IntakeConstraints 透传** (`src/lfo/storyboard/intake.py`)

新增 `medium_lock: str = ""` 让有明确偏好的用户直接指定。

**3. Decompose prompt 模板更新** (`src/lfo/storyboard/prompts/decompose_v1.j2`)

在 STYLE GUIDE block 后加：

```
MEDIUM LOCK (append verbatim to every shot description):
{{ medium_lock }}

STYLE KEYWORDS: {{ style_keywords | join(", ") }}
```

Description 规则更新：

```
Description (UPDATED — CRITICAL):
- Single dense sentence for the video model's prompt.
- Include: location + main action + camera angle + mood + lighting.
- MUST include spatial relationships: character position in frame
  (foreground/midground/background, left/center/right), relative positions
  to scene elements (doors, windows, furniture, light sources), and
  distances/orientations between characters when multiple are present.
- End with the MEDIUM LOCK sentence verbatim.
```

**4. Prompt Blueprint 编译** (`src/lfo/planning/prompt_blueprint.py`)

`_build_base_parts` 里加 style part：

```python
style = storyboard.style
if style.medium_lock:
    parts.append(PromptPart(
        part_type="style",
        content=style.medium_lock,
        source="storyboard.style.medium_lock",
    ))
if style.style_keywords:
    parts.append(PromptPart(
        part_type="style_keywords",
        content=", ".join(style.style_keywords),
        source="storyboard.style.style_keywords",
    ))
```

**5. Medium Lock 生成器** (新文件 `src/lfo/storyboard/style_brief.py`)

```python
MEDIUM_LOCK_TEMPLATES: dict[str, str] = {
    "3d_render": "Medium: 3D rendered scene with cinematic composition, clean geometry, stylized realism. NOT 2D anime cel-shading, NOT live-action, NOT sketch.",
    "2d_anime": "Medium: 2D hand-drawn animation with painted backgrounds. NOT 3D render, NOT photoreal, NOT live-action.",
    "realistic": "Medium: Photorealistic cinematic footage with natural lighting. NOT animation, NOT illustration, NOT CGI look.",
    "watercolor": "Medium: Watercolor painting with soft edges and visible brushstrokes. NOT 3D render, NOT photoreal, NOT digital art.",
    "cyberpunk": "Medium: Photorealistic cinematic footage with neon-lit cyberpunk aesthetic. NOT anime, NOT cartoon, NOT flat illustration.",
}

def build_medium_lock(visual_style: str, user_override: str = "") -> str:
    """Return Medium Lock. user_override wins if non-empty."""
```

**6. 测试**

- `tests/test_storyboard/test_style_brief.py` — medium_lock 生成逻辑
- `tests/test_storyboard/test_storyboard_schema.py` — 序列化/反序列化
- `tests/test_planning/test_prompt_blueprint.py` — style part 出现在 blueprint 里

### 验收标准
- decompose 输出的每个 shot description 末尾含 medium_lock
- prompt blueprint parts 里有 `part_type="style"` 项
- 序列化 round-trip 不丢字段
- 全量测试通过

---

## Phase P0-B: 角色设定图生成（Agent 生图指令方案）

### 目标
在 decompose 之后、shot 视频生成之前，LFO 输出角色设定图生图指令。Agent 工具识别指令并生图，图片回写后 LFO 管线继续，设定图作为 R2V 的 character_ref。

### 前置条件
- P0-A 完成（medium_lock 用于生图 prompt）
- Agent 工具具备生图能力（MiniMax Code 的 `image_synthesize` 已验证可用）

### 改动

**1. 生图指令 Schema** (新文件 `src/lfo/visual/image_request.py`)

```python
"""Structured image generation request — consumed by agent tools."""

@dataclass
class ImageRequest:
    """A single image generation request written by LFO, executed by an agent."""
    request_id: str           # e.g. "imgreq_char_chenmo_sheet"
    type: str                 # "character_sheet" | "storyboard_preview"
    status: str = "pending"   # "pending" | "in_progress" | "completed" | "failed"
    prompt: str = ""          # fully rendered prompt for the image model
    aspect_ratio: str = "16:9"
    resolution: str = "2K"
    output_path: str = ""     # where the agent should save the image
    character_id: str = ""    # for character_sheet type
    shot_range: list[str] = field(default_factory=list)  # for storyboard_preview
    created_at: str = ""      # ISO 8601
    # Result fields (filled by agent after generation)
    result_asset_path: str = ""
    result_seed: int = 0
    completed_at: str = ""

@dataclass
class ImageRequestBatch:
    """A batch of image requests for one pipeline phase."""
    batch_id: str
    project_id: str
    phase: str                # "character_sheets" | "storyboard_preview"
    requests: list[ImageRequest] = field(default_factory=list)
```

**2. Character Sheet Prompt 模板** (新文件 `src/lfo/storyboard/prompts/character_sheet_v1.j2`)

从 zero-to-story skill 移植：

```
Character reference sheet for a single character, 16:9 horizontal composition.
No text, labels, numbers, or watermarks in the image.

CHARACTER: {{ character.name }}
FULL DESCRIPTION: {{ character.description }} {{ character.distinguishing_features }}

Show:
- Front view: full body, {{ character.description }}
- Side view: full body, same character in profile
- Back view: full body, same character from behind
- 1-2 small expression variants: face close-up showing emotion range
- Signature pose: {{ character.signature_action or "natural standing pose" }}
{% if character.key_prop %}- Key prop: {{ character.key_prop }}{% endif %}

Requirements:
- All views must show identical clothing, hairstyle, body type, and distinguishing features
- Expression variants must maintain the same character identity
- Clean white or neutral background
- No text, labels, numbers, or UI marks

{{ style_keywords | join(", ") }}
{{ medium_lock }}
```

**3. Character 新增字段** (`src/lfo/storyboard/storyboard.py`)

```python
@dataclass
class Character:
    # ... 现有字段 ...
    signature_action: str = ""     # 标志性动作
    key_prop: str = ""             # 关键道具（无则空）
    ref_asset_id: str = ""         # 生成的设定图 asset_id（回填）
    ref_image_path: str = ""       # agent 生图后的文件路径（回填）
```

**4. CharacterSheetService** (新文件 `src/lfo/services/character_sheet_service.py`)

```python
class CharacterSheetService:
    """Generate character sheet image requests for agent execution."""

    def build_requests(
        self,
        storyboard: Storyboard,
        project_id: str,
    ) -> ImageRequestBatch:
        """Build image requests for all characters needing reference sheets.

        For each character in storyboard.project.reference_character_order
        that doesn't have ref_image_path yet:
        1. Render character_sheet_v1.j2 prompt
        2. Create ImageRequest with output_path
        3. Return batch
        """

    def collect_results(
        self,
        batch: ImageRequestBatch,
        storyboard: Storyboard,
    ) -> list[CharacterSheetResult]:
        """After agent writes result images, collect and register as assets.

        For each completed request:
        1. Verify image file exists at result_asset_path
        2. Register as asset with role="character_ref"
        3. Backfill Character.ref_image_path and Character.ref_asset_id
        """
```

**5. 指令文件 I/O 约定**

LFO 写指令文件到：
```
workspace/<novel>/<chapter>/image_requests/
    batch_character_sheets_001.json
```

Agent 生图后写结果到：
```
workspace/<novel>/<chapter>/ref_images/
    char_chenmo_sheet.png
    char_laoren_sheet.png
workspace/<novel>/<chapter>/image_requests/
    batch_character_sheets_001_results.json   # agent 回写
```

**指令文件示例**（`batch_character_sheets_001.json`）：

```json
{
  "batch_id": "batch_cs_001",
  "project_id": "我今天不上班-chapter_01",
  "phase": "character_sheets",
  "requests": [
    {
      "request_id": "imgreq_char_chenmo_sheet",
      "type": "character_sheet",
      "status": "pending",
      "prompt": "Character reference sheet for a single character...",
      "aspect_ratio": "16:9",
      "resolution": "2K",
      "output_path": "workspace/我今天不上班/chapter_01/ref_images/char_chenmo_sheet.png",
      "character_id": "char_chenmo"
    }
  ]
}
```

**结果文件示例**（`batch_character_sheets_001_results.json`）：

```json
{
  "batch_id": "batch_cs_001",
  "results": [
    {
      "request_id": "imgreq_char_chenmo_sheet",
      "status": "completed",
      "result_asset_path": "workspace/我今天不上班/chapter_01/ref_images/char_chenmo_sheet.png",
      "completed_at": "2026-08-08T14:30:00Z"
    }
  ]
}
```

**6. Pipeline 集成** (`src/lfo/services/pipeline_service.py`)

```python
def execute(self, storyboard: Storyboard) -> PipelineResult:
    # ...

    # Phase 0: Character reference sheets (via agent)
    if self._needs_character_sheets(storyboard):
        print("[Pipeline] Phase 0: Building character sheet requests...")
        batch = self.character_sheet_service.build_requests(
            storyboard, storyboard.project.project_id,
        )
        # Write instruction file for agent
        request_path = self._write_image_request_batch(batch)
        print(f"[Pipeline] Image requests written to: {request_path}")
        print("[Pipeline] Waiting for agent to generate images...")

        # If agent results already exist, collect them
        results_path = self._find_results(batch.batch_id)
        if results_path:
            results = self.character_sheet_service.collect_results(batch, storyboard)
            self._backfill_character_refs(results, storyboard)
        else:
            # Pause pipeline — agent needs to generate images first
            print("[Pipeline] PAUSED: Run agent image generation, then re-run pipeline")
            result.success = False
            result.errors["phase_0"] = "Waiting for agent image generation"
            return result

    # Continue with task graph...
    graph = self.graph_service.build_graph(storyboard)
```

**管线暂停/恢复机制**：LFO 检测到指令文件无结果时暂停，用户跑 agent 生图后重新 `lfo run`。CLI 也支持 `lfo run --skip-character-sheets` 跳过。

**7. CLI 支持**

```bash
lfo images <storyboard.json>              # 只生成生图指令文件
lfo images <storyboard.json> --collect    # 收集 agent 生图结果，注册 asset
lfo run <storyboard.json>                 # 完整管线（自动检测是否需要生图）
lfo run <storyboard.json> --skip-images   # 跳过所有 agent 生图步骤
```

**8. Workflow Selector 更新** (`src/lfo/planning/workflow_selector.py`)

现有逻辑已支持：有 approved character refs → R2V。`Character.ref_asset_id` 回填后自然触发。

R2V 还需要 `composition_ref` 或 `scene_ref`。方案：
- 第一个 shot：composition_ref 用 scene 描述生成的场景参考图（另一个 image_request）
- 后续 shot：composition_ref 用前一个 shot 的末帧

**9. 测试**

- `tests/test_visual/test_image_request.py` — schema 序列化/反序列化
- `tests/test_services/test_character_sheet_service.py` — prompt 构建、asset 注册
- `tests/test_storyboard/test_storyboard_schema.py` — Character 新字段
- 集成测试：build_requests → 模拟 agent 回写 → collect_results → ref_asset_id 回填

### 验收标准
- LFO 能生成结构化的角色设定图指令文件（JSON）
- Agent 能识别指令文件并调用 `image_synthesize` 生图
- 生图结果回写后，LFO 能 collect 并注册 asset
- `Character.ref_asset_id` 正确回填
- Workflow selector 在有 ref 时选择 R2V
- 管线支持暂停/恢复（等待 agent 生图）
- 全量测试通过

---

## Phase P1: Decompose Prompt 空间关系强化

### 目标
让 LLM 拆镜时把空间位置关系写进每个 shot 的 description，直接影响画面构图质量。

### 改动

**1. decompose_v1.j2 模板更新**

Description 规则（与 P0-A 合并）：

```
Description:
- Single dense sentence for the video model's prompt.
- Include: location + main action + camera angle + mood + lighting.
- MUST include spatial relationships:
  * Character position: foreground/midground/background + left/center/right
  * Relative to scene elements: near/far from doors, windows, furniture, light sources
  * Between characters: distance, facing direction, occlusion when applicable
- Example GOOD: "wide shot, 陈默站在超市中央货架旁(中景偏左)，面对镜头，
  右侧收银台方向一只丧尸从前景爬过，荧光灯在头顶闪烁"
- Example BAD: "陈默在超市里" (no spatial info)
- End with the MEDIUM LOCK sentence verbatim.
```

**2. decompose_schema.py 校验增强**

Soft validation — 缺空间关键词时 warning 但不 reject：

```python
SPATIAL_KEYWORDS = {
    "foreground", "midground", "background",
    "前景", "中景", "远景",
    "left", "right", "center",
    "左", "右", "中央", "旁", "远", "近",
}
```

**3. action_beats 空间约束**

```
Action beats:
- Each beat's description should include spatial context when the
  character moves: "走向左侧货架" not just "走向货架".
```

**4. 测试**

- `tests/test_storyboard/test_decompose_schema.py` — 空间关键词 warning
- `tests/test_storyboard/test_decompose.py` — mock LLM 输出含空间描述

### 验收标准
- decompose 输出的 description 包含空间关系
- 缺少空间关键词时 warning 不 block
- 全量测试通过

---

## Phase P2: 黑白分镜预览层（Agent 生图指令方案）

### 目标
在视频生成前，LFO 输出黑白分镜预览生图指令，Agent 生成预览图，用户在文字审批之外多一层便宜的视觉审批。

### 依赖
- P0-A（medium_lock 用于预览图 prompt）
- P0-B（agent 生图指令通道已建立）
- P1（空间描述质量影响预览图 prompt）

### 改动

**1. Storyboard Preview Prompt 模板** (新文件 `src/lfo/storyboard/prompts/storyboard_preview_v1.j2`)

从 zero-to-story skill 移植核心 prompt（已验证可用，见上方测试）。

**2. StoryboardPreviewService** (新文件 `src/lfo/services/storyboard_preview_service.py`)

```python
class StoryboardPreviewService:
    """Build storyboard preview image requests for agent execution."""

    PANELS_PER_SHEET = 8  # 2x4 grid

    def build_requests(
        self,
        storyboard: Storyboard,
        project_id: str,
    ) -> ImageRequestBatch:
        """Build preview sheet requests.

        Groups shots into 8-per-sheet with continuity chaining:
        - Sheet 1: Shot 01-08
        - Sheet 2: Shot 08-15 (panel 1 = shot 08, bridging from sheet 1)
        - Sheet 3: Shot 15-22 (panel 1 = shot 15)
        """
```

**3. Shot 分组逻辑**

| 预览图 | 覆盖分镜 | 说明 |
|---|---|---|
| Sheet 1 | Shot 01-08 | 完整使用前 8 个分镜 |
| Sheet 2 | Shot 08-15 | Panel 1 复用 Sheet 1 最后一格（动作承接） |
| Sheet 3 | Shot 15-22 | Panel 1 复用 Sheet 2 最后一格 |

**4. 审批流程**

```
Storyboard JSON 审批（文字级）
  ↓
LFO 输出预览生图指令 → Agent 生成黑白分镜预览图
  ↓
用户确认画面 / 要求修改
  ↓
（可选）修改 storyboard → 重新生成预览
  ↓
确认后 LFO 继续管线（视频生成）
```

**5. CLI 支持**

```bash
lfo preview <storyboard.json>              # 只生成预览指令
lfo preview <storyboard.json> --collect    # 收集预览图
lfo run <storyboard.json>                  # 管线自动在预览阶段暂停
lfo run <storyboard.json> --skip-preview   # 跳过预览
```

**6. 测试**

- `tests/test_services/test_storyboard_preview_service.py` — 分组、prompt 构建、连续链接

### 验收标准
- 8 个 shot 生成 1 张预览指令
- 15 个 shot 生成 2 张，第 2 张 Panel 1 承接第 1 张
- Agent 生图后 LFO collect 并展示
- 管线支持在预览阶段暂停/恢复
- 全量测试通过

---

## 实施顺序与依赖

```
P0-A (Medium Lock)          ── 独立，可立即开始
P1 (Spatial Relations)      ── 独立，与 P0-A 并行（同一个 decompose 模板）
    │
P0-B (Character Sheets)     ── 依赖 P0-A 的 medium_lock
    │                          不依赖 ComfyUI T2I（改用 agent 生图）
    │
P2 (Storyboard Preview)     ── 依赖 P0-B 的 agent 生图通道
                               依赖 P0-A 的 medium_lock
                               依赖 P1 的空间描述
```

**建议执行顺序**：P0-A + P1 → P0-B → P2

理由：
- P0-A 和 P1 都是 prompt/schema 层改动，一起改 decompose 模板
- P0-B 建立 agent 生图指令通道，是 P2 的前置
- P2 复用 P0-B 的通道，只需新增 prompt 模板和分组逻辑

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| Agent 生图结果质量不稳定 | 角色设定图不理想 | 指令文件里支持 `retry_count`；agent 可以多次生图选最佳 |
| R2V workflow 从未 smoke test | P0-B 集成时可能发现 workflow 问题 | P0-B 第一步先单独 smoke test R2V（用已生成的设定图） |
| Medium Lock 导致 prompt 过长 | H3 模型可能截断 | Medium Lock 控制在 2-3 句；监控 prompt token 数 |
| 管线暂停/恢复机制不够健壮 | 用户在 agent 生图后忘记重跑 | CLI 输出清晰的下一步指引；`lfo status` 显示当前暂停原因 |
| 2x4 分镜图格子太小 | 预览不清晰 | 可切换到 2x2（4 格）或更大分辨率 |

---

## 文件变更清单

### 新增文件
| 文件 | 说明 |
|---|---|
| `src/lfo/storyboard/style_brief.py` | Medium Lock 生成器 + 模板映射 |
| `src/lfo/visual/image_request.py` | 生图指令 schema（ImageRequest / ImageRequestBatch） |
| `src/lfo/storyboard/prompts/character_sheet_v1.j2` | 角色设定图 prompt 模板 |
| `src/lfo/storyboard/prompts/storyboard_preview_v1.j2` | 黑白分镜预览 prompt 模板 |
| `src/lfo/services/character_sheet_service.py` | 角色设定图指令生成 + 结果收集 |
| `src/lfo/services/storyboard_preview_service.py` | 分镜预览指令生成 + 结果收集 |
| `tests/test_storyboard/test_style_brief.py` | Medium Lock 测试 |
| `tests/test_visual/test_image_request.py` | 指令 schema 测试 |
| `tests/test_services/test_character_sheet_service.py` | 角色设定图测试 |
| `tests/test_services/test_storyboard_preview_service.py` | 分镜预览测试 |

### 修改文件
| 文件 | 改动 |
|---|---|
| `src/lfo/storyboard/storyboard.py` | StyleGuide +medium_lock/style_keywords; Character +signature_action/key_prop/ref_asset_id/ref_image_path |
| `src/lfo/storyboard/intake.py` | IntakeConstraints +medium_lock |
| `src/lfo/storyboard/prompts/decompose_v1.j2` | +medium_lock/style_keywords 传递; 空间关系规则 |
| `src/lfo/storyboard/decompose_schema.py` | +空间关键词 soft validation |
| `src/lfo/planning/prompt_blueprint.py` | +style/medium_lock PromptPart |
| `src/lfo/services/pipeline_service.py` | +Phase 0 character sheet 集成 + 预览阶段暂停/恢复 |
| `src/lfo/cli/main.py` | +`lfo images` / `lfo preview` 命令注册 |
| `src/lfo/cli/run_cmd.py` | +`--skip-images` / `--skip-preview` flags |

---

## 验证计划

1. **单元测试**：每个新模块独立测试
2. **全量回归**：所有现有测试继续通过
3. **Agent 生图链路验证**：
   - LFO 生成角色设定图指令 → MiniMax Code 执行 `image_synthesize` → 图片回写 → LFO collect（已在本次会话验证可行 ✅）
   - LFO 生成预览图指令 → MiniMax Code 执行 → 图片回写 → LFO collect（已验证 ✅）
4. **Live E2E**：用「我今天不上班」chapter_01 完整跑一遍含角色设定图 + R2V 的管线
5. **主观质量对比**：同一 storyboard，改动前后各跑一次，对比角色一致性和风格一致性
