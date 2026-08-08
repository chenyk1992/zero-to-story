# Provider-Agnostic Visual Production Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement LFO Provider-Agnostic Visual Production Mode (Mode Complete M0–M13) per design spec v8.2, without binding to a specific image model.

**Architecture:** Visual tasks reuse the existing `tasks` table and real `TaskStatus` enum. Domain detail lives in `visual_task_contracts.visual_stage`. Manual/Delegated use `visual_exchange_executions`; Managed uses `attempt_kind='visual_managed'` + `visual_provider_executions`. Results import to assets → tech QC (`QC_PENDING`) → human review → `AssetBindingService` current binding → video readiness. Video `provider_jobs` stay untouched.

**Tech Stack:** Python 3.12, SQLite WAL (`core/database.py`), existing LFO-CJ1/WFJ1 hashing, pytest, flat package imports from repo root.

**Spec:** `docs/superpowers/specs/2026-08-07-provider-agnostic-visual-production-design.md` (v8.2)

## Global Constraints

- Never invent TaskStatus values; never persist visual happy-path as `SUCCEEDED` (use `QC_PENDING` → `WAITING_USER`/`AWAITING_REVIEW` → `APPROVED`)
- Never delete/rename/merge `provider_jobs`
- Asset types only: `image|video|audio|subtitle|document`
- Profile/Provider/Contract/Manifest hashes: LFO-CJ1; workflow JSON: LFO-WFJ1; file bytes: SHA-256
- Use `AssetBindingService`, `invalidate_upstream`, column `assets.metadata`
- Default profile policy: `allow_t2va_fallback`
- `from __future__ import annotations` in all new modules
- TDD: failing test → implement → pass → commit
- Branch from `master`; conventional commits (`feat:`/`fix:`/`test:`/`refactor:`/`docs:`)

---

## File Structure

### Create

```text
visual/
  __init__.py
  stages.py
  errors.py
  capabilities.py
  purpose.py
  hashing.py
  task_compiler.py
  task_contract.py
  result_manifest.py
  routing.py
  profile.py
  provider_config.py
  providers/
    __init__.py
    base.py
    registry.py
    manual.py
    delegated.py
    fake_managed.py
application/
  visual_profile_service.py
  visual_provider_service.py
  visual_task_service.py
  visual_result_service.py
  visual_routing_service.py
  visual_readiness.py
services/
  visual_technical_qc_service.py
cli/
  visual_cmd.py
  project_cmd.py
tests/test_visual/
scripts/
  mode_complete_gates.py
  production_proof_3shot.py
```

### Modify

```text
core/database.py
application/asset_service.py          # validate_asset_type where assets are inserted if needed
services/prompt_generation_service.py
services/storyboard_graph_service.py
services/task_readiness_service.py
services/continuity_service.py
planning/workflow_selector.py
config/defaults.py
cli/__init__.py                       # export new commands
AGENTS.md
```

### Delete

```text
services/visual_asset_service.py
tests/test_services/test_visual_asset_service.py
```

---

### Task 1: Phase 0 — Baseline + delete VisualAssetService + rename keyframe.image

**Files:**
- Delete: `services/visual_asset_service.py`
- Delete: `tests/test_services/test_visual_asset_service.py`
- Modify: `config/defaults.py`
- Modify: `services/prompt_generation_service.py`
- Modify: `services/storyboard_graph_service.py`
- Modify: `tests/test_services/test_prompt_generation_service.py`
- Modify: `AGENTS.md`
- Test: full `tests/` + local E2E scripts

**Interfaces:**
- Consumes: none new
- Produces: `SUPPORTED_TASK_TYPES` includes `visual.generate` / `visual.edit`; `ShotGenerationPlan.requires_visual_input`; `GenerationPlan.visual_tasks_needed`

- [ ] **Step 1: Record baseline**

```bash
cd E:/ideaProjects/zero-to-story
mkdir -p artifacts
python -m pytest tests/ --collect-only -q | tee artifacts/phase0_collect.txt
python -m pytest tests/ -q --tb=no | tee artifacts/phase0_baseline.txt
```

Expected: all tests passed. Note exact count for the commit body.

- [ ] **Step 2: Write failing rename expectations**

Update `tests/test_services/test_prompt_generation_service.py`:

```python
assert plan.shot_plans[1].task_type == "visual.generate"
assert plan.shot_plans[1].requires_visual_input
assert plan.visual_tasks_needed == 2
```

Rename test method names that say `needs_keyframe` / `keyframes_needed` accordingly.

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/test_services/test_prompt_generation_service.py -v
```

Expected: FAIL (AttributeError or assertion on `keyframe.image`).

- [ ] **Step 4: Implement renames and delete old service**

`config/defaults.py`:

```python
SUPPORTED_TASK_TYPES = ["video.h3", "visual.generate", "visual.edit", "audio.tts"]
```

In `prompt_generation_service.py`:

```python
@dataclass
class ShotGenerationPlan:
    shot_id: str
    blueprint: PromptBlueprint | None = None
    requires_visual_input: bool = False
    workflow_mode: str = ""
    task_type: str = ""  # 'video.h3' | 'visual.generate'
    references_needed: list[str] = field(default_factory=list)

@dataclass
class GenerationPlan:
    project_id: str
    shot_plans: list[ShotGenerationPlan] = field(default_factory=list)
    total_shots: int = 0
    visual_tasks_needed: int = 0
```

When `requires_visual_input`, set `task_type = "visual.generate"`.  
In `storyboard_graph_service.py`, replace `needs_keyframe` with `requires_visual_input`.  
Delete `services/visual_asset_service.py` and `tests/test_services/test_visual_asset_service.py`.

- [ ] **Step 5: Grep gate**

```bash
rg -n "keyframe\\.image|VisualAssetService|visual_asset_service|needs_keyframe|keyframes_needed" -g "*.py" -g "*.md" -g "*.json"
```

Expected: no hits outside historical notes in `docs/superpowers/specs/`.

- [ ] **Step 6: Full unit regression**

```bash
python -m pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 7: Local E2E**

```bash
python scripts/local_e2e_3shot.py
python scripts/local_e2e_5shot_multicam.py
python scripts/local_e2e_8shot_audio_subtitle.py
python scripts/local_e2e_16shot_full.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add config/defaults.py services/prompt_generation_service.py services/storyboard_graph_service.py tests/test_services/test_prompt_generation_service.py AGENTS.md
git add -u services/visual_asset_service.py tests/test_services/test_visual_asset_service.py
git commit -m "$(cat <<'EOF'
refactor: remove VisualAssetService and replace keyframe.image with visual.generate

Phase 0 clean break for provider-agnostic visual mode; keep provider_jobs untouched.
EOF
)"
```

---

### Task 2: Schema v10 — migration + fresh equivalence

**Files:**
- Modify: `core/database.py`
- Modify: `tests/test_db_migration_verify.py`
- Create: `tests/test_visual/__init__.py`
- Create: `tests/test_visual/test_schema_v10.py`

**Interfaces:**
- Consumes: existing `Database.init_schema` / `migrate`
- Produces: `SCHEMA_VERSION = 10`; six visual tables; `attempts.attempt_kind`; assets type CHECK on fresh DB; `provider_jobs` retained

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual/test_schema_v10.py
from __future__ import annotations

from core.database import SCHEMA_VERSION, Database

VISUAL_TABLES = (
    "visual_provider_revisions",
    "visual_generation_profile_revisions",
    "visual_task_contracts",
    "visual_result_manifests",
    "visual_provider_executions",
    "visual_exchange_executions",
)

def test_schema_version_is_10():
    assert SCHEMA_VERSION == 10

def test_fresh_has_visual_tables_and_provider_jobs():
    db = Database()
    db.init_schema()
    names = {r[0] for r in db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for t in VISUAL_TABLES:
        assert t in names
    assert "provider_jobs" in names
    db.close()

def test_attempt_kind_default_workflow():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('p1', 'n')")
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) "
        "VALUES ('t1', 'p1', 'video.h3', 'PLANNED')"
    )
    db.execute(
        """INSERT INTO attempts
           (attempt_id, task_id, idempotency_key, workflow_id,
            content_hash, dependency_hash, params_hash)
           VALUES ('a1', 't1', 'k', 'wf', 'c', 'd', 'p')"""
    )
    row = db.fetchone("SELECT attempt_kind FROM attempts WHERE attempt_id='a1'")
    assert row[0] == "workflow"
    db.close()

def test_visual_managed_attempt_requires_null_workflow_id():
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('p1', 'n')")
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) "
        "VALUES ('t1', 'p1', 'visual.generate', 'PLANNED')"
    )
    try:
        db.execute(
            """INSERT INTO attempts
               (attempt_id, task_id, idempotency_key, workflow_id, attempt_kind,
                content_hash, dependency_hash, params_hash)
               VALUES ('a2', 't1', 'k2', 'wf', 'visual_managed', 'c', 'd', 'p')"""
        )
        raised = False
    except Exception:
        raised = True
    assert raised
    db.close()
```

Also update `tests/test_db_migration_verify.py` to expect `SCHEMA_VERSION == 10` and add a v9→v10 migrate case.

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_visual/test_schema_v10.py tests/test_db_migration_verify.py -v
```

Expected: FAIL (`SCHEMA_VERSION == 9` or missing tables).

- [ ] **Step 3: Implement schema v10**

In `core/database.py`:

1. `SCHEMA_VERSION = 10`
2. Extend fresh `attempts` DDL:

```sql
attempt_kind TEXT NOT NULL DEFAULT 'workflow'
    CHECK (attempt_kind IN ('workflow', 'visual_managed')),
-- keep workflow_id TEXT nullable, add:
-- CHECK (
--   (attempt_kind = 'workflow' AND workflow_id IS NOT NULL)
--   OR (attempt_kind = 'visual_managed' AND workflow_id IS NULL)
-- )
```

3. Append CREATE TABLE for all six visual tables + unique indexes from spec §8.3–8.8.
4. Fresh `assets` CHECK allow-list: `image|video|audio|subtitle|document`.
5. `_migrate_v9_to_v10`:
   - create visual tables IF NOT EXISTS
   - add `attempt_kind` column with default `workflow` if missing
   - remap legacy visual `asset_type` values to `image`, merging `{"legacy_visual_purpose": ...}` into `metadata`
   - never drop `provider_jobs`
6. Wire `if current < 10: self._migrate_v9_to_v10()` in `migrate()`.

If SQLite cannot ADD CHECK via ALTER, rebuild `attempts`/`assets` inside the migration transaction so migrated ≡ fresh.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_visual/test_schema_v10.py tests/test_db_migration_verify.py tests/test_database.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/database.py tests/test_visual tests/test_db_migration_verify.py
git commit -m "$(cat <<'EOF'
feat: add schema v10 visual tables and attempt_kind

Forward-migrate from v9; retain provider_jobs for video/Comfy recovery.
EOF
)"
```

---

### Task 3: Domain — stages, capabilities, errors, hashing, compiler

**Files:**
- Create: `visual/__init__.py`
- Create: `visual/stages.py`
- Create: `visual/errors.py`
- Create: `visual/capabilities.py`
- Create: `visual/purpose.py`
- Create: `visual/hashing.py`
- Create: `visual/task_compiler.py`
- Test: `tests/test_visual/test_stages.py`
- Test: `tests/test_visual/test_hashing.py`
- Test: `tests/test_visual/test_compiler.py`
- Test: `tests/test_visual/test_purpose.py`

**Interfaces:**
- Produces:

```python
class VisualStage(str, Enum):
    UNROUTED = "UNROUTED"
    BLOCKED = "BLOCKED"
    ROUTED = "ROUTED"
    SUBMITTED = "SUBMITTED"
    AWAITING_RESULT = "AWAITING_RESULT"
    RESULT_IMPORTED = "RESULT_IMPORTED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"

def assert_legal_pair(status: TaskStatus, stage: VisualStage) -> None: ...

@dataclass(frozen=True)
class VisualCapabilities:
    text_to_image: bool = False
    reference_to_image: bool = False
    multi_reference: bool = False
    image_edit: bool = False
    inpainting: bool = False
    character_multiview: bool = False
    storyboard_frame: bool = False
    transparent_output: bool = False

@dataclass(frozen=True)
class ProviderProbeResult:
    available: bool
    checked_at: str
    latency_ms: int | None
    provider_version: str | None
    capabilities: VisualCapabilities
    error_code: str | None
    message: str | None

@dataclass(frozen=True)
class VisualTaskCompilerIdentity:
    name: str
    semver: str
    source_hash: str | None = None

def get_compiler_identity() -> VisualTaskCompilerIdentity: ...
def derive_task_type(purpose: str) -> str: ...
def derive_operation(purpose: str, has_references: bool) -> str: ...
def hash_visual_object(obj: dict) -> str: ...  # LFO-CJ1
```

- [ ] **Step 1: Write failing tests**

```python
from core.state_machine import TaskStatus
from visual.stages import VisualStage, assert_legal_pair

def test_qc_pending_result_imported_ok():
    assert_legal_pair(TaskStatus.QC_PENDING, VisualStage.RESULT_IMPORTED)

def test_succeeded_result_imported_illegal():
    import pytest
    with pytest.raises(ValueError):
        assert_legal_pair(TaskStatus.SUCCEEDED, VisualStage.RESULT_IMPORTED)

def test_approved_pair_ok():
    assert_legal_pair(TaskStatus.APPROVED, VisualStage.APPROVED)
```

Hash test: same dict with reordered keys → identical CJ1 hash.  
Compiler test: `get_compiler_identity().semver == "1.0.0"`.

- [ ] **Step 2: Run tests — expect fail**

```bash
python -m pytest tests/test_visual/test_stages.py tests/test_visual/test_hashing.py tests/test_visual/test_compiler.py tests/test_visual/test_purpose.py -v
```

- [ ] **Step 3: Implement**

Mirror `visual_bible/hashing.py` (canonical serialize + `hash_bytes`).  
`assert_legal_pair` encodes the v8.2 combination table; explicitly reject visual happy-path `SUCCEEDED` pairs.

- [ ] **Step 4: Pass + commit**

```bash
git add visual tests/test_visual
git commit -m "feat: add visual domain stages capabilities and CJ1 hashing"
```

---

### Task 4: Contracts, manifest, provider config, profile schema

**Files:**
- Create: `visual/task_contract.py`
- Create: `visual/result_manifest.py`
- Create: `visual/provider_config.py`
- Create: `visual/profile.py`
- Test: `tests/test_visual/test_task_contract.py`
- Test: `tests/test_visual/test_result_manifest.py`
- Test: `tests/test_visual/test_provider_config.py`
- Test: `tests/test_visual/test_profile.py`

**Interfaces:**
- Produces: `VisualTaskPackage`, `VisualResultManifest`, `validate_provider_config(provider_type: str, config: dict) -> dict`, `validate_profile_content(content: dict) -> dict`, fields `technical_checks` and `review_checklist` (not blended auto gates)

- [ ] **Step 1: Failing validation tests** — missing `file_hash`; profile without `visual_input_policy`; managed config without `endpoint`; delegated allowlist.

- [ ] **Step 2: Implement dataclasses + validators** (`schema_version` checks per spec §9 / §14).

- [ ] **Step 3: Commit** `feat: add visual contracts manifests and provider config schemas`

---

### Task 5: Profile + Provider revision services

**Files:**
- Create: `application/visual_profile_service.py`
- Create: `application/visual_provider_service.py`
- Test: `tests/test_visual/test_profile_service.py`
- Test: `tests/test_visual/test_provider_service.py`

**Interfaces:**

```python
class VisualProviderService:
    def __init__(self, db: Database) -> None: ...
    def create_draft(self, *, provider_id: str, scope_type: str, scope_id: str,
                     provider_type: str, adapter_name: str, config: dict,
                     capabilities: dict, serial_group: str | None = None,
                     max_concurrency: int = 1) -> str: ...
    def activate(self, provider_revision_id: str, *, allow_unavailable: bool = False) -> None: ...
    def disable(self, provider_revision_id: str) -> None: ...
    def resolve_active(self, provider_id: str, *, project_id: str) -> dict | None: ...
    # project scope first, then global/global

class VisualProfileService:
    def __init__(self, db: Database) -> None: ...
    def create_draft(self, project_id: str, content: dict) -> str: ...
    def activate(self, revision_id: str, *, allow_unavailable_provider: bool = False) -> None: ...
    def clone(self, revision_id: str) -> str: ...
    def get_active(self, project_id: str) -> dict | None: ...
```

- [ ] **Step 1: Failing tests** — one active per scope; project beats global; clone parent = current active; disable.

- [ ] **Step 2: Implement CAS activate** in a transaction (supersede old active, set new active, `activated_at`).

- [ ] **Step 3: Commit** `feat: add visual profile and provider revision services`

---

### Task 6: VisualTaskService — create + atomic transition

**Files:**
- Create: `application/visual_task_service.py`
- Test: `tests/test_visual/test_visual_task_service.py`

**Interfaces:**

```python
class VisualTaskService:
    def __init__(self, db: Database) -> None: ...

    def create_visual_task(
        self,
        *,
        purpose: str,
        project_id: str,
        shot_id: str | None,
        references: list[dict],
        prompt: dict | None = None,
        provider_override: str | None = None,
    ) -> str: ...

    def transition(
        self,
        task_id: str,
        *,
        expected_task_status: TaskStatus,
        expected_visual_stage: VisualStage,
        new_task_status: TaskStatus,
        new_visual_stage: VisualStage,
        reason: str,
    ) -> None: ...
```

Rules:
- Derive task_type/operation via `visual.purpose`
- Insert `tasks` + `visual_task_contracts` (`UNROUTED`, compiler_identity_json, optional bible FK)
- `transition` single TX: CAS both columns by expected values; `rowcount != 1` → raise; log event
- Reject transitions that land on illegal pairs or visual happy-path `SUCCEEDED`

- [ ] **Step 1: Failing tests** for create, CAS success, CAS conflict, illegal SUCCEEDED target.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit** `feat: add VisualTaskService create and atomic transitions`

---

### Task 7: Result import + technical QC + approve binding

**Files:**
- Create: `application/visual_result_service.py`
- Create: `services/visual_technical_qc_service.py`
- Test: `tests/test_visual/test_result_import.py`
- Test: `tests/test_visual/test_visual_technical_qc.py`

**Interfaces:**

```python
class VisualResultService:
    def import_manifest(self, manifest: dict, *, source_root: str) -> str: ...
    def approve(
        self,
        task_id: str,
        *,
        asset_id: str,
        entity_type: str,
        entity_id: str,
        asset_role: str,
        reviewer: str,
    ) -> None: ...

class VisualTechnicalQCService:
    def run(self, task_id: str, asset_id: str) -> dict: ...
```

Import ends with `transition(..., QC_PENDING, RESULT_IMPORTED)`.  
QC pass → `WAITING_USER` + `AWAITING_REVIEW`.  
Approve uses `AssetBindingService.create_binding` / `create_revision` then `APPROVED` + `APPROVED`.  
Asset rows use `asset_type='image'` and purpose in `metadata` / binding role.

- [ ] **Step 1: Failing tests** — hash mismatch; idempotent re-import; approve creates current binding; never leaves task on `SUCCEEDED`.

- [ ] **Step 2: Implement copy-to `project://assets/visual/<task_id>/...` via existing path resolver patterns.**

- [ ] **Step 3: Commit** `feat: import visual results with QC and binding approval`

---

### Task 8: Providers, routing, exchange, FakeManaged

**Files:**
- Create: `visual/providers/__init__.py`
- Create: `visual/providers/base.py`
- Create: `visual/providers/registry.py`
- Create: `visual/providers/manual.py`
- Create: `visual/providers/delegated.py`
- Create: `visual/providers/fake_managed.py`
- Create: `application/visual_routing_service.py`
- Test: `tests/test_visual/test_routing.py`
- Test: `tests/test_visual/test_fake_managed.py`
- Test: `tests/test_visual/test_exchange.py`

**Interfaces:**

```python
class VisualProvider:
    @property
    def provider_revision_id(self) -> str: ...
    def declared_capabilities(self) -> VisualCapabilities: ...
    def probe(self) -> ProviderProbeResult: ...

class ExchangeVisualProvider(VisualProvider):
    def export_task(self, task_id: str) -> str: ...
    def import_result(self, manifest: dict) -> str: ...

class ManagedVisualProvider(VisualProvider):
    def submit(self, task_package: dict) -> str: ...
    def collect(self, execution_id: str) -> dict: ...
    def cancel(self, execution_id: str) -> None: ...

class FakeManagedProvider(ManagedVisualProvider):
    def set_next_response(
        self,
        *,
        corrupt: bool = False,
        wrong_size: bool = False,
        timeout: bool = False,
        unavailable: bool = False,
        hash_mismatch: bool = False,
    ) -> None: ...

class VisualRoutingService:
    def route(self, task_id: str) -> dict: ...
    def dry_run(self, *, project_id: str, purpose: str, required_capabilities: list[str]) -> dict: ...
```

Routing order: override → purpose rules → defaults → fallbacks; project scope > global; write `routing_snapshot_json`; transition to `READY`/`ROUTED` or `WAITING_ASSETS`/`BLOCKED`.  
Exchange: insert `visual_exchange_executions`, no `attempts`; transition to `WAITING_USER`/`AWAITING_RESULT`.  
Managed: create `attempts.attempt_kind='visual_managed'` + `visual_provider_executions`.

- [ ] **Step 1–4: TDD routing snapshot, fallback to manual, fake fault consumed once, export restart recovery via exchange row.**

- [ ] **Step 5: Commit** `feat: add visual providers routing and exchange execution`

---

### Task 9: CLI — visual commands + project init

**Files:**
- Create: `cli/visual_cmd.py`
- Create: `cli/project_cmd.py`
- Modify: `cli/__init__.py` (exports)
- Modify: command registration modules as required by `CommandRegistry`
- Test: `tests/test_cli/test_visual_cmd.py`
- Test: `tests/test_cli/test_project_cmd.py`

**Interfaces:**
- Produces CLI entrypoints matching:

```text
lfo visual profile show|create|activate|clone|disable|history
lfo visual provider list|create|probe|disable
lfo visual task list|show|export|cancel
lfo visual result import
lfo visual route --dry-run
lfo project init
```

`visual task list --ready` SQL/filter:

```text
status = WAITING_USER AND visual_stage = AWAITING_RESULT AND provider_type = delegated
```

- [ ] **Step 1: Failing CLI dispatch tests** (follow `tests/test_cli/test_business_cmd.py` patterns).

- [ ] **Step 2: Implement commands calling application services.**

- [ ] **Step 3: Commit** `feat: add visual CLI and project init`

---

### Task 10: DAG integration, dual gate, T2VA policy

**Files:**
- Create: `application/visual_readiness.py`
- Modify: `services/storyboard_graph_service.py`
- Modify: `planning/workflow_selector.py`
- Modify: `services/task_readiness_service.py`
- Test: `tests/test_visual/test_dag_integration.py`
- Test: extend `tests/test_services/test_task_readiness_service.py`

**Interfaces:**

```python
@dataclass
class VisualAssetReadinessResult:
    ready: bool
    missing_roles: list[str]
    details: dict

def check_visual_assets_ready(
    db: Database,
    *,
    project_id: str,
    shot_id: str,
    required_roles: list[str],
) -> VisualAssetReadinessResult: ...
```

Behavior:
- Read active profile `visual_input_policy`
- `allow_t2va_fallback`: preserve current T2VA selection when visuals missing and shot allows
- `visual_required`: insert blocking `visual.generate` tasks and dependencies before `video.h3`
- `TaskReadinessService.promote_to_ready` calls `check_visual_assets_ready` and requires visual dependency tasks in `APPROVED` when present

- [ ] **Step 1: Failing tests for both policies and binding gate.**

- [ ] **Step 2: Implement graph insertion + readiness hook.**

- [ ] **Step 3: Regression**

```bash
python -m pytest tests/test_services/test_storyboard_graph_service.py tests/test_services/test_task_readiness_service.py tests/test_visual/test_dag_integration.py -v
python scripts/local_e2e_3shot.py
```

- [ ] **Step 4: Commit** `feat: integrate visual tasks into graph readiness and T2VA policy`

---

### Task 11: Profile switch + invalidation

**Files:**
- Modify: `application/visual_profile_service.py`
- Test: `tests/test_visual/test_profile_switch.py`

Reuse `invalidate_upstream` from `core/invalidation.py`. On activate: stale unstarted visual tasks → `STALE` / `NEEDS_REMATERIALIZATION`; running managed + exported exchange keep old profile revision; approved assets stay valid unless rebuild replaces bindings.

- [ ] **TDD + commit** `feat: profile switch rematerialization via existing invalidation`

---

### Task 12: Level 1 continuity edit

**Files:**
- Modify: `services/continuity_service.py`
- Optional: thin wrapper on `VisualTaskService.create_visual_task(purpose='continuity_edit')`
- Test: `tests/test_visual/test_continuity_edit.py`
- Test: extend `tests/test_services/test_continuity_service.py` if needed

Flow: end frame → `visual.edit` → import/QC/approve → new `start_frame` binding → next video `NEEDS_REMATERIALIZATION`.

- [ ] **TDD + commit** `feat: level 1 continuity visual.edit path`

---

### Task 13: Mode Complete gate runner (M0–M13)

**Files:**
- Create: `scripts/mode_complete_gates.py`
- Create: `tests/test_visual/test_mode_gates_smoke.py`

```bash
python scripts/mode_complete_gates.py --skip-production
python -m pytest tests/test_visual/ -v
python -m pytest tests/ -q
```

Automate Manual + FakeManaged + Hybrid paths in temp DB; print M0–M13 status; exit non-zero on failure.

- [ ] **Commit** `test: add mode complete gate runner for visual production`

---

### Task 14: Production Proof script (P1–P5)

**Files:**
- Create: `scripts/production_proof_3shot.py`

Requires real Delegated or Managed + real H3; forces `visual_required`; asserts lineage P1–P5. Not default CI.

- [ ] **Commit** `feat: add production proof 3-shot script`

---

## Parallel dependency graph

```text
T1 Phase0
  → T2 Schema
    → T3 Domain → T4 Contracts
         → T5 Profile/Provider
           → T6 TaskService
             → T7 Result/QC
               → T8 Providers/Routing/Exchange
                    ├─→ T9 CLI
                    └─→ T10 DAG/Readiness
                         → T11 Profile switch
                           → T12 Continuity L1
                             → T13 Mode gates
                               → T14 Production proof
```

---

## M0–M13 commands

```bash
rg -n "VisualAssetService|keyframe\\.image" -g "*.py"
python -m pytest tests/ -q
python scripts/local_e2e_3shot.py
python scripts/local_e2e_5shot_multicam.py
python scripts/local_e2e_8shot_audio_subtitle.py
python scripts/local_e2e_16shot_full.py
python -m pytest tests/test_visual/ -v
python scripts/mode_complete_gates.py --skip-production
# lab only:
python scripts/production_proof_3shot.py
```

---

## Spec coverage checklist

| Spec area | Tasks |
|---|---|
| Phase 0 clean break | 1 |
| Schema v10 / keep provider_jobs | 2 |
| No SUCCEEDED happy path / stages | 3, 6, 7 |
| CJ1 + compiler identity | 3, 6 |
| Provider/profile revisions + scope | 5, 8 |
| Exchange vs managed | 7, 8 |
| CLI / project init | 9 |
| DAG + policy + dual gate | 10 |
| Profile switch + invalidate_upstream | 11 |
| Continuity L1 | 12 |
| Mode Complete / Production Proof | 13, 14 |
| Asset type allow-list | 2, 7 |

---

## Open implementation notes

1. SQLite CHECK additions may require table rebuild in `_migrate_v9_to_v10` for fresh≡migrated.
2. `task_materializations.workflow_id` stays NOT NULL and video-only; do not materialize visual_managed attempts through the video materialization path.
3. Until Task 10, `PromptGenerationService.task_type='visual.generate'` is a planning marker only.
