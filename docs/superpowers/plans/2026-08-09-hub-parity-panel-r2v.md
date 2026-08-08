# Hub Parity Panel + Ref2VA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LFO video production Panel-centric and Hub-aligned: hard density (beats → 2×4 boards → one r2v clip per board), dynamic 2–9 `PanelPack` refs, Hub-style prompts, and delete per-shot video execution paths.

**Architecture:** Narrative atoms are `Beat`s (brief table rows). Execution atoms are `Panel`s (one 2×4 BW board → one video task). Each Panel gets a `PanelPack` (composition board + identity refs, trimmed to `max_ref_images`) and a Hub-style prompt. Workflow selection runs only on PanelPack completeness → `r2v`. No shot-level video DAG, no start_frame→i2v shim.

**Tech Stack:** Python 3.12, existing LFO storyboard/planning/services, pytest, local Comfy `h3_standard_r2v` (3 LoadImage slots in P1).

**Spec:** `docs/superpowers/specs/2026-08-09-hub-parity-panel-r2v-design.md`

## Global Constraints

- Execution granularity is **Panel only** — delete per-shot video task creation; no dual-path / transition shim
- `composition_ref` = Panel BW storyboard board; previous end-frame must not replace it or veto r2v
- `PanelPack` size ∈ `[2, min(9, max_ref_images)]`; must include composition + ≥1 identity (character) ref
- Default purposes: composition 「仅参考构图和动作链，不采用线稿画风」; character 「保持身份、发型、服饰、体型与关键道具不变」
- Prompt order: 承接 → 图片N用途 → 动作链 → 声音(NO BGM) → Medium Lock
- P1 `max_ref_images = 3` for local Comfy r2v; logic must accept up to 9 for later backends
- `from __future__ import annotations` in all new modules; snake_case / PascalCase per AGENTS.md
- TDD: failing test → implement → pass → commit; conventional commits; branch from `master`
- Breaking change allowed: no read-compat for old `shots[]` video plans

### Locked open-item decisions (from spec §13)

| Item | Decision for this plan |
|---|---|
| PanelPack storage | `workspace/<novel>/<chapter>/panels/panel_{nn:02d}_pack.json` + `Storyboard.panels[].pack` optional in-memory |
| Who builds packs | Deterministic `build_panel_pack(...)` heuristic (testable); Agent may edit JSON; CLI `lfo panels pack` |
| P2 (9 slots / API) | Out of this plan — only plumb `max_ref_images` |
| Skill hub_* rewrite | Out of this plan — one AGENTS.md note only |
| Narrative naming | `Beat` in code; brief markdown may still say 镜头序号 |
| `shots[]` | Remove from execution model; migrate schema to `beats[]` + `panels[]` (breaking) |

---

## File Structure

### Create

```text
src/lfo/planning/panel_density.py          # duration → beat_count, panel_count, beat ranges
src/lfo/planning/panel_pack.py             # PanelPackRef, PanelPack, validate, trim, build_panel_pack
src/lfo/planning/hub_style_prompt.py       # compile_hub_style_panel_prompt(...)
src/lfo/storyboard/panel.py                # Beat, Panel dataclasses (or live in storyboard.py if small)
src/lfo/services/panel_generation_service.py
src/lfo/cli/panels_cmd.py
tests/test_planning/test_panel_density.py
tests/test_planning/test_panel_pack.py
tests/test_planning/test_hub_style_prompt.py
tests/test_planning/test_workflow_selector_panel.py
tests/test_services/test_panel_generation_service.py
```

### Modify

```text
src/lfo/storyboard/storyboard.py           # beats[] + panels[]; remove shots as video unit
src/lfo/storyboard/intake.py               # shot_count_target / beat_count_target helpers
src/lfo/storyboard/prompts/decompose_v1.j2 # beat density hard rules; no per-shot i2v continuity
src/lfo/storyboard/decompose.py            # map LLM output → beats; derive panels via density
src/lfo/planning/schema.py                 # ReferenceBinding.slot 1..9; PromptBlueprint.target_panel_ids
src/lfo/planning/workflow_selector.py      # select_workflow_for_panel(PanelPack, ...)
src/lfo/planning/reference_planner.py      # deprecate shot planner; thin wrapper or delete callers
src/lfo/planning/asset_requirements.py     # panel-level requirements
src/lfo/planning/dag.py                    # panel video task edges
src/lfo/planning/prompt_blueprint.py       # stop using weak Guided-by for panel path
src/lfo/services/storyboard_graph_service.py
src/lfo/services/prompt_generation_service.py  # delete or re-export panel service only
src/lfo/planning/__init__.py
src/lfo/cli/registry.py
AGENTS.md                                  # one paragraph: Panel-only video execution
docs/superpowers/specs/2026-08-09-hub-parity-panel-r2v-design.md  # Status → Approved
```

### Delete / gut (video execution only)

```text
Per-shot loops in storyboard_graph_service that create video/{shot_id} and visual_{shot}_start_frame
ShotGenerationPlan / generate_plan shot iteration (replace with panel service)
Tests that assert per-shot i2v/t2va video tasks as the happy path — rewrite to Panel/r2v
```

Do **not** invent a compatibility layer that still builds `video/shot_*` tasks.

---

### Task 1: Panel density helpers

**Files:**
- Create: `src/lfo/planning/panel_density.py`
- Test: `tests/test_planning/test_panel_density.py`

**Interfaces:**
- Produces:
  - `def beat_count_for_duration_ms(duration_ms: int) -> int`
  - `def panel_count_for_beat_count(beat_count: int) -> int`
  - `def panel_beat_ranges(beat_count: int) -> list[tuple[int, int]]`  # 1-based inclusive; overlap carry rules
  - `def panel_duration_ms(total_duration_ms: int, panel_count: int) -> int`

**Density table (copy from spec):** 15s→8, 30s→15, 45s→22, 60s→29; else `8 + 7*((ceil(duration/15000))-1)` with minimum 8.

- [ ] **Step 1: Write failing tests**

```python
from lfo.planning.panel_density import (
    beat_count_for_duration_ms,
    panel_count_for_beat_count,
    panel_beat_ranges,
    panel_duration_ms,
)

def test_standard_durations():
    assert beat_count_for_duration_ms(15_000) == 8
    assert beat_count_for_duration_ms(30_000) == 15
    assert beat_count_for_duration_ms(45_000) == 22
    assert beat_count_for_duration_ms(60_000) == 29

def test_panel_count_from_beats():
    assert panel_count_for_beat_count(8) == 1
    assert panel_count_for_beat_count(15) == 2
    assert panel_count_for_beat_count(22) == 3
    assert panel_count_for_beat_count(29) == 4

def test_ranges_with_carry():
    # Panel1: 1-8; Panel2: 8-15 (beat 8 carried)
    assert panel_beat_ranges(15) == [(1, 8), (8, 15)]
    assert panel_beat_ranges(22) == [(1, 8), (8, 15), (15, 22)]

def test_panel_duration_splits_evenly():
    assert panel_duration_ms(45_000, 3) == 15_000
```

- [ ] **Step 2: Run tests — expect FAIL (import/module missing)**

Run: `python -m pytest tests/test_planning/test_panel_density.py -v`

- [ ] **Step 3: Implement `panel_density.py`**

```python
from __future__ import annotations

import math

_STANDARD = {15_000: 8, 30_000: 15, 45_000: 22, 60_000: 29}


def beat_count_for_duration_ms(duration_ms: int) -> int:
    if duration_ms in _STANDARD:
        return _STANDARD[duration_ms]
    panels = max(1, math.ceil(duration_ms / 15_000))
    return 8 + 7 * (panels - 1)


def panel_count_for_beat_count(beat_count: int) -> int:
    if beat_count <= 8:
        return 1
    return 1 + math.ceil((beat_count - 8) / 7)


def panel_beat_ranges(beat_count: int) -> list[tuple[int, int]]:
    n = panel_count_for_beat_count(beat_count)
    ranges: list[tuple[int, int]] = []
    for i in range(n):
        if i == 0:
            ranges.append((1, min(8, beat_count)))
        else:
            start = ranges[-1][1]  # carry last beat
            end = min(start + 7, beat_count)
            ranges.append((start, end))
    return ranges


def panel_duration_ms(total_duration_ms: int, panel_count: int) -> int:
    if panel_count <= 0:
        raise ValueError("panel_count must be positive")
    return total_duration_ms // panel_count
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_planning/test_panel_density.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/lfo/planning/panel_density.py tests/test_planning/test_panel_density.py
git commit -m "feat: add Hub-aligned panel density helpers"
```

---

### Task 2: `PanelPack` model, validate, trim, deterministic builder

**Files:**
- Create: `src/lfo/planning/panel_pack.py`
- Test: `tests/test_planning/test_panel_pack.py`

**Interfaces:**
- Consumes: none from Task 1 (standalone)
- Produces:
  - `@dataclass PanelPackRef` with `slot: int`, `role: str`, `asset_id: str`, `entity_id: str`, `purpose: str`
  - `@dataclass PanelPack` with `panel_id`, `beat_range: tuple[int,int]`, `storyboard_bw_asset_id`, `refs`, `characters_in_panel`, `trim_reason`
  - `DEFAULT_PURPOSE_COMPOSITION`, `DEFAULT_PURPOSE_CHARACTER`, `DEFAULT_PURPOSE_CONTINUITY_CHAR`
  - `def validate_panel_pack(pack: PanelPack, *, max_ref_images: int) -> list[str]`  # error messages; empty=ok
  - `def trim_panel_pack(candidates: list[PanelPackRef], *, composition: PanelPackRef, max_ref_images: int) -> tuple[list[PanelPackRef], str | None]`
  - `def build_panel_pack(panel_id, beat_range, bw_asset_id, character_assets: list[tuple[str,str]], scene_assets=..., prop_assets=..., continuity_character_assets=..., max_ref_images=3) -> PanelPack`
  - `def panel_pack_to_dict` / `panel_pack_from_dict`
  - Priority inside `trim_panel_pack`: composition (forced first) → main chars → continuity chars → scene → prop → style

- [ ] **Step 1: Write failing tests**

```python
from lfo.planning.panel_pack import (
    PanelPackRef,
    build_panel_pack,
    validate_panel_pack,
    trim_panel_pack,
    DEFAULT_PURPOSE_COMPOSITION,
)

def test_build_min_two_refs():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="asset_bw_01",
        character_assets=[("char_a", "asset_char_a")],
        max_ref_images=3,
    )
    assert len(pack.refs) == 2
    assert pack.refs[-1].role == "composition"
    assert DEFAULT_PURPOSE_COMPOSITION in pack.refs[-1].purpose or pack.refs[-1].purpose == DEFAULT_PURPOSE_COMPOSITION
    assert validate_panel_pack(pack, max_ref_images=3) == []

def test_trim_to_three_keeps_composition_and_main_chars():
    composition = PanelPackRef(0, "composition", "bw", "panel_01", DEFAULT_PURPOSE_COMPOSITION)
    candidates = [
        PanelPackRef(0, "character", "c1", "char_1", "main"),
        PanelPackRef(0, "character", "c2", "char_2", "main"),
        PanelPackRef(0, "scene", "s1", "scene_1", "env"),
        PanelPackRef(0, "prop", "p1", "prop_1", "prop"),
    ]
    refs, reason = trim_panel_pack(candidates, composition=composition, max_ref_images=3)
    assert len(refs) == 3
    assert any(r.role == "composition" for r in refs)
    assert reason  # non-empty trim reason
    # slots renumbered 1..3
    assert [r.slot for r in refs] == [1, 2, 3]

def test_validate_rejects_missing_identity():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="asset_bw_01",
        character_assets=[],
        max_ref_images=3,
    )
    # builder may still create invalid pack if no chars — validate must catch
    errs = validate_panel_pack(pack, max_ref_images=3)
    assert any("identity" in e.lower() or "character" in e.lower() for e in errs)
```

Note: For `test_validate_rejects_missing_identity`, implement `build_panel_pack` to allow empty character_assets (for testing) but `validate_panel_pack` fails; production callers must not submit invalid packs.

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_planning/test_panel_pack.py -v`

- [ ] **Step 3: Implement `panel_pack.py`** per interfaces above. Renumber `slot` after trim. Composition purpose default exact string from spec.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/lfo/planning/panel_pack.py tests/test_planning/test_panel_pack.py
git commit -m "feat: add PanelPack validate/trim/build for dynamic Ref2VA refs"
```

---

### Task 3: Hub-style Panel prompt compiler

**Files:**
- Create: `src/lfo/planning/hub_style_prompt.py`
- Test: `tests/test_planning/test_hub_style_prompt.py`

**Interfaces:**
- Consumes: `PanelPack` from Task 2
- Produces:
  - `def compile_hub_style_panel_prompt(*, pack: PanelPack, opening: str, action_chain: str, sound_design: str, medium_lock: str, quality_negatives: str = "") -> str`
  - Output must contain, in order: opening, each `图片{n}是` / purpose, action_chain, sound with `不要背景音乐` or `NO background music`, medium_lock

- [ ] **Step 1: Write failing test**

```python
from lfo.planning.panel_pack import PanelPack, PanelPackRef, DEFAULT_PURPOSE_COMPOSITION, DEFAULT_PURPOSE_CHARACTER
from lfo.planning.hub_style_prompt import compile_hub_style_panel_prompt

def test_hub_style_order_and_picture_bindings():
    pack = PanelPack(
        panel_id="panel_02",
        beat_range=(8, 15),
        storyboard_bw_asset_id="bw2",
        refs=[
            PanelPackRef(1, "character", "a1", "char_linye", DEFAULT_PURPOSE_CHARACTER),
            PanelPackRef(2, "character", "a2", "char_zhao", "仅作为前段人物连续性参考。"),
            PanelPackRef(3, "composition", "bw2", "panel_02", DEFAULT_PURPOSE_COMPOSITION),
        ],
        characters_in_panel=["char_linye", "char_zhao"],
        trim_reason=None,
    )
    text = compile_hub_style_panel_prompt(
        pack=pack,
        opening="林野在画面左侧提着外卖箱、刚刚站稳。",
        action_chain="林野短暂停留在手机上的欠款与订单抽象光块前，随后平稳转入高架桥下旧巷。",
        sound_design="车流和市井声逐渐抽空，只留下脚步、手机震动；不要背景音乐。",
        medium_lock="Medium: 3D rendered suspense, real urban space. NOT 2D anime cel-shading.",
        quality_negatives="避免身份漂移、时间闪烁、错误文字。",
    )
    assert text.index("林野在画面左侧") < text.index("图片1")
    assert "图片1" in text and "图片2" in text and "图片3" in text
    assert DEFAULT_PURPOSE_COMPOSITION in text
    assert "不要背景音乐" in text
    assert "Medium:" in text
    assert text.index("图片3") < text.index("林野短暂停留")
    assert text.index("不要背景音乐") < text.index("Medium:")
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement compiler** — join sections with newlines; for each ref emit `图片{slot}是{entity_label或role}，{purpose}` (entity_label can be `entity_id` for P1).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/lfo/planning/hub_style_prompt.py tests/test_planning/test_hub_style_prompt.py
git commit -m "feat: compile Hub-style Panel prompts with picture bindings"
```

---

### Task 4: Panel-level workflow selector (r2v first)

**Files:**
- Modify: `src/lfo/planning/workflow_selector.py`
- Test: `tests/test_planning/test_workflow_selector_panel.py`
- Keep old `select_workflow(shot, ...)` only if still imported by non-video code; **video path must not call it**. Prefer adding `select_workflow_for_panel` and deleting shot-based video uses in later tasks. If nothing else needs shot selector after Task 7, delete `select_workflow` and rewrite `tests/test_planning/test_workflow_selector.py` to panel tests only.

**Interfaces:**
- Produces:
  - `def select_workflow_for_panel(pack: PanelPack, *, force_fl2va: bool = False) -> WorkflowSelection`
  - Rules from spec §8.1: valid pack → `h3_standard_r2v` / `r2v` / `confirmed`; `force_fl2va` → i2v/first_last only when explicitly requested; incomplete pack → `blocked` with missing_requirements (not silent t2va)

- [ ] **Step 1: Write failing tests**

```python
from lfo.planning.panel_pack import build_panel_pack
from lfo.planning.workflow_selector import select_workflow_for_panel

def test_valid_pack_selects_r2v():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="bw",
        character_assets=[("char_a", "asset_a")],
        max_ref_images=3,
    )
    result = select_workflow_for_panel(pack)
    assert result.workflow_mode == "r2v"
    assert result.workflow_id == "h3_standard_r2v"
    assert result.selection_status == "confirmed"

def test_incomplete_pack_blocked_not_t2va():
    pack = build_panel_pack(
        panel_id="panel_01",
        beat_range=(1, 8),
        bw_asset_id="bw",
        character_assets=[],
        max_ref_images=3,
    )
    result = select_workflow_for_panel(pack)
    assert result.selection_status == "blocked"
    assert result.workflow_mode == "r2v"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `select_workflow_for_panel`** using `validate_panel_pack`. Do **not** inspect start_frame.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/lfo/planning/workflow_selector.py tests/test_planning/test_workflow_selector_panel.py
git commit -m "feat: select r2v from PanelPack without start_frame downgrade"
```

---

### Task 5: Storyboard schema — `Beat` + `Panel`, remove `shots` as execution unit

**Files:**
- Modify: `src/lfo/storyboard/storyboard.py`
- Modify: `src/lfo/storyboard/validate.py` (as needed)
- Modify / rewrite tests under `tests/test_storyboard/` that construct `shots=`
- Test: add `tests/test_storyboard/test_panel_schema.py`

**Interfaces:**
- Produces:
  - `@dataclass Beat`: `beat_id`, `sequence: int`, `scene_id`, `description`, `dialogue`, `sound`, `characters: list[CharacterAppearance]`, `framing` (景别 string ok)
  - `@dataclass Panel`: `panel_id`, `sequence: int`, `beat_range: tuple[int,int]`, `beat_ids: list[str]`, `desired_duration_ms: int`, `bw_asset_id: str = ""`, `pack: PanelPack | None = None`, `prompt_text: str = ""`
  - `Storyboard.beats: list[Beat]`, `Storyboard.panels: list[Panel]`
  - **Remove** `Storyboard.shots` (breaking). Grep and fix all in-repo call sites/tests in this task and Task 6–8 — do not leave `shots=` constructors.

Derivation helper (can live in `panel_density` or `storyboard/panel_plan.py`):

```python
def derive_panels_from_beats(beats: list[Beat], total_duration_ms: int) -> list[Panel]:
    ...
```

- [ ] **Step 1: Write failing schema round-trip test for beats+panels**

- [ ] **Step 2: Implement dataclasses + `to_dict`/`from_dict`; remove `shots`**

- [ ] **Step 3: Fix compile errors across tests by migrating fixtures to beats/panels** ( mechanized: any video-related test that used 6 shots should use N beats + derived panels)

- [ ] **Step 4: `pytest tests/test_storyboard/ -v` green for schema tests; note remaining failures fixed in later tasks**

- [ ] **Step 5: Commit**

```bash
git add src/lfo/storyboard tests/test_storyboard
git commit -m "refactor: replace storyboard shots with beats and panels"
```

---

### Task 6: Decompose / intake — hard beat density, no per-shot i2v plan

**Files:**
- Modify: `src/lfo/storyboard/prompts/decompose_v1.j2`
- Modify: `src/lfo/storyboard/decompose.py`
- Modify: `src/lfo/storyboard/intake.py` (expose `beat_count_target` from `constraints.custom.shot_count_target` or new field; keep JSON key `shot_count_target` in handoff for now as alias → beat count)
- Test: `tests/test_storyboard/test_decompose_density.py` (unit-test template rendering / post-process that enforces count; mock LLM if needed)

**Rules to put in `decompose_v1.j2` (replace old “Usually 3-6 shots” and i2v continuity block):**

```text
BEAT COUNT (HARD CONSTRAINT):
- You MUST emit exactly {{ beat_count_target }} beats.
- Beats are narrative cells for 2x4 storyboard boards, NOT independent video jobs.
- Do NOT emit per-beat preferred_mode i2v/t2va/r2v. Video mode is chosen later per Panel.

FORBIDDEN:
- start_frame_needed / previous_shot_id chains for video execution
- Collapsing the story into fewer than {{ beat_count_target }} beats
```

Post-process in `decompose.py`: after LLM parse, if beat count ≠ target, fail validation (or pad/trim only if you already have a tested strategy — prefer **fail loud**).

Then call `derive_panels_from_beats`.

- [ ] **Step 1: Failing test — rendered prompt contains HARD beat count and forbids i2v continuity instructions**

- [ ] **Step 2: Update j2 + decompose mapping to `Beat`**

- [ ] **Step 3: Test pass; commit**

```bash
git commit -m "feat: enforce Hub beat density in decompose; drop shot i2v planning"
```

---

### Task 7: `PanelGenerationService` replaces shot prompt generation

**Files:**
- Create: `src/lfo/services/panel_generation_service.py`
- Delete or gut: `src/lfo/services/prompt_generation_service.py` (re-export deprecated alias **not allowed** per spec — delete and fix imports)
- Test: `tests/test_services/test_panel_generation_service.py`
- Delete/rewrite: `tests/test_services/test_prompt_generation_service.py`

**Interfaces:**
- Produces:
  - `@dataclass PanelGenerationPlan` with `panel_id`, `workflow_mode`, `workflow_id`, `selection_status`, `prompt_text`, `pack: PanelPack`, `task_type="video.h3"`
  - `@dataclass GenerationPlan` with `project_id`, `panel_plans: list[PanelGenerationPlan]`
  - `class PanelGenerationService: def generate_plan(self, storyboard, project_id, *, max_ref_images: int = 3, available_assets: dict | None = None) -> GenerationPlan`
  - For each `storyboard.panels`: build/validate pack (from panel.pack or `build_panel_pack` using approved character refs + `panel.bw_asset_id`), `select_workflow_for_panel`, `compile_hub_style_panel_prompt` using beat descriptions joined as action_chain and sounds joined as sound_design

- [ ] **Step 1: Failing test — one panel with char+bw → plan mode r2v and Hub prompt contains 图片1**

- [ ] **Step 2: Implement service; remove shot service**

- [ ] **Step 3: Grep `PromptGenerationService` / `ShotGenerationPlan` — zero references**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: PanelGenerationService emits r2v Hub prompts per panel"
```

---

### Task 8: Graph / DAG — one video task per Panel; delete shot video tasks

**Files:**
- Modify: `src/lfo/services/storyboard_graph_service.py`
- Modify: `src/lfo/planning/dag.py`
- Modify: `src/lfo/planning/asset_requirements.py`
- Modify: `src/lfo/planning/schema.py` (`logical_task_key` examples `video/panel_01`; `PromptBlueprint.target_panel_ids`)
- Rewrite tests: `tests/test_services/test_storyboard_graph_service.py`, `tests/test_visual/test_dag_integration.py`, related pipeline tests

**Behavior:**

```text
For each Panel in storyboard.panels:
  logical_task_key = f"video/{panel.panel_id}"
  workflow from select_workflow_for_panel
  reference_bindings from pack.refs → ReferenceBinding(slot, asset_id, entity_id, role)
  params include prompt_text, duration_ms=panel.desired_duration_ms, max_ref_images
Do NOT create visual_{shot}_start_frame tasks for the happy path.
Do NOT create video/{shot_id} tasks.
```

DAG: optional dependency `panel_n` after `panel_{n-1}` for serialization only (not i2v frame edge). Prefer independent panels unless continuity asset truly required — **default: sequential panel order edges** to match Hub narrative order.

- [ ] **Step 1: Failing test — graph for 15 beats / 2 panels creates exactly 2 `video/panel_*` tasks and 0 `video/shot_*`**

- [ ] **Step 2: Implement; delete shot loops**

- [ ] **Step 3: Full planning/service tests related to graph green**

Run: `python -m pytest tests/test_services/test_storyboard_graph_service.py tests/test_planning/ tests/test_services/test_panel_generation_service.py -v`

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: panel-only video DAG; remove per-shot video tasks"
```

---

### Task 9: CLI `lfo panels` + workspace pack I/O

**Files:**
- Create: `src/lfo/cli/panels_cmd.py`
- Modify: `src/lfo/cli/registry.py`
- Test: `tests/test_cli/test_panels_cmd.py`

**Commands:**

```text
lfo panels plan --storyboard <path>     # print beat/panel counts + ranges
lfo panels pack --storyboard <path> [--max-ref-images 3]
    # write workspace/.../panels/panel_XX_pack.json for each panel
lfo panels prompt --storyboard <path>   # write/update video_prompt_list.md Hub-style sections
```

Pack JSON schema = `panel_pack_to_dict`. Agent edits JSON then re-runs prompt.

- [ ] **Step 1: Failing CLI test with tmp storyboard fixture (beats+panels+fake asset ids)**

- [ ] **Step 2: Implement commands**

- [ ] **Step 3: Pass + commit**

```bash
git commit -m "feat: add lfo panels plan/pack/prompt CLI"
```

---

### Task 10: Docs + kill misleading shot video docs; green suite

**Files:**
- Modify: `AGENTS.md` — Architecture notes: video execution is Panel→PanelPack→r2v only
- Modify: spec status to `Approved for implementation`
- Modify: `docs/plans/visual_quality_improvement_plan.md` — add banner at top: composition_ref≠end frame; shot video path obsolete; see new spec/plan
- Fix remaining broken tests repo-wide from `shots` removal

- [ ] **Step 1: Update docs**

- [ ] **Step 2: Run**

```bash
python -m pytest tests/ -v
```

Expected: all pass (or only pre-existing unrelated failures documented in commit message — prefer zero failures).

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: Panel-only r2v execution; close Hub parity P1 docs"
```

---

## Out of scope (follow-up plans)

- Expand Comfy `h3_standard_r2v` from 3 → 9 LoadImage slots
- mmx API Ref2VA provider route
- zero-to-story `SKILL.md` hub_* → Cursor/workspace/mmx runtime rewrite
- Batch scene/prop sheet generation (P3)

---

## Spec coverage checklist

| Spec section | Task |
|---|---|
| §5 Panel density | Task 1, 6 |
| §6 PanelPack 2–9 + trim | Task 2, 9 |
| §7 Hub-style prompt | Task 3, 7, 9 |
| §8.1 selector r2v | Task 4 |
| §8.2 delete shot video compat | Task 5, 7, 8, 10 |
| §9 max_ref_images P1=3 | Task 2, 7, 9 |
| §11 acceptance tests | Tasks 1–10 |

## Placeholder / consistency self-review

- No TBD steps; open items locked in Global Constraints
- Names consistent: `PanelPack`, `select_workflow_for_panel`, `PanelGenerationService`, `video/panel_*`
- `ReferenceBinding.slot` documented as 1..9 (update schema comment in Task 8)

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-09-hub-parity-panel-r2v.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with executing-plans checkpoints  

Which approach?
