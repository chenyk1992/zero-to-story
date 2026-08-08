# LFO Provider-Agnostic Visual Production Mode — Design Spec v8.2

**Status:** Frozen for implementation planning  
**Date:** 2026-08-07  
**Supersedes:** v8.1 (post-review), v7

## Changelog from v8.1

1. **Visual happy path never uses `SUCCEEDED` as an intermediate status.** Import lands on `QC_PENDING` + `RESULT_IMPORTED`. Terminal success is `APPROVED` + `APPROVED`. Avoids conflict with `TASK_TERMINAL_STATES` and premature dependency satisfaction in `promote_task_to_ready`.
2. **Naming aligned to current code:** `AssetBindingService` (not AssetService), `invalidate_upstream` in `core/invalidation.py` (not InvalidationService), column `assets.metadata` (not `metadata_json`).
3. **`EXPORTED` is not a persisted `VisualStage`.** Export atomically transitions to `AWAITING_RESULT`. Removed from the persisted stage enum.
4. **`VisualStage.BLOCKED` dual-use documented:** meaning is always disambiguated by `TaskStatus` (`WAITING_ASSETS` vs `FAILED_RETRYABLE`).

---

## 1. Goal

LFO does not bind to a specific image model. It provides provider-agnostic visual task orchestration:

```text
Visual requirement
→ Visual Task Contract
→ Provider routing
→ Manual / Delegated / Managed execution
→ Result Manifest import
→ Technical QC
→ Manual review
→ Asset Binding
→ Video task unblocked
```

**In scope:** Provider-Agnostic Visual Production Mode (Mode Complete = M0–M13).  
**Out of scope for Mode Complete:** built-in Qwen image, aesthetic auto-scoring, identity similarity models, unpaid auto-approve, background probe loops, billing.  
**Separate track:** Production Proof (P1–P5) with real provider + real H3.

---

## 2. Baseline (verified against repo)

```text
Schema Version = 9
Video main chain: Storyboard → Graph → H3 → Collect → Normalize → Selected Clip
                  → Editorial → Level 0 Continuity → EDL → Assembly → SRT → Final QC → Export
```

Existing building blocks to reuse:

- `VisualBibleService` / `visual_bible_revisions`
- `TaskReadinessService` + `AssetBindingService`
- `invalidate_upstream` (`core/invalidation.py`)
- `provider_jobs` (video/Comfy — **keep**)
- `asset_bindings`, `asset_reviews`, `qc_reports`
- `TaskStatus` (15 values) and `SubmissionState` (separate machine)

Delete without compatibility layer:

- `services/visual_asset_service.py`
- `tests/test_services/test_visual_asset_service.py`

Replace `keyframe.image` with `visual.generate` / `visual.edit` (scan + rename `needs_keyframe` / `keyframes_needed` → `requires_visual_input` / `visual_tasks_needed`).

---

## 3. Clean Break Decisions

| Decision | Rule |
|---|---|
| `VisualAssetService` | Delete; no shim |
| `provider_jobs` | Keep; do not rename, generalize, or merge with visual tables |
| Visual managed jobs | `visual_provider_executions` + `attempt_kind='visual_managed'` |
| Manual/Delegated | `visual_exchange_executions` only; **no** `attempts` row |
| Task types | `visual.generate`, `visual.edit` only for vision |

---

## 4. TaskStatus and VisualStage

### 4.1 TaskStatus (real enum — do not invent values)

```text
PLANNED, WAITING_ASSETS, READY, QUEUED, RUNNING, WAITING_USER,
SUCCEEDED, QC_PENDING, APPROVED, FAILED_RETRYABLE, FAILED_TERMINAL,
STALE, NEEDS_REMATERIALIZATION, CANCELLED, SUPERSEDED
```

`SUBMITTED` / `COLLECTING` are **not** TaskStatus (SubmissionState / visual internals only).

**Visual happy path does not use `SUCCEEDED`.** Video tasks may still end at `SUCCEEDED`; visual tasks terminal success is `APPROVED`.

### 4.2 Persisted VisualStage

```text
UNROUTED, BLOCKED, ROUTED, SUBMITTED, AWAITING_RESULT,
RESULT_IMPORTED, AWAITING_REVIEW, APPROVED, REJECTED,
STALE, SUPERSEDED, CANCELLED
```

### 4.3 Legal combinations

| Scenario | TaskStatus | VisualStage |
|---|---|---|
| Created, not routed | `PLANNED` | `UNROUTED` |
| Missing profile / refs / provider | `WAITING_ASSETS` | `BLOCKED` |
| Routed, runnable | `READY` | `ROUTED` |
| Manual/Delegated awaiting package result | `WAITING_USER` | `AWAITING_RESULT` |
| Managed queued | `QUEUED` | `SUBMITTED` |
| Managed running | `RUNNING` | `SUBMITTED` |
| Result imported, tech QC running/pending | `QC_PENDING` | `RESULT_IMPORTED` |
| Tech QC passed, human review pending | `WAITING_USER` | `AWAITING_REVIEW` |
| Review approved + current binding | `APPROVED` | `APPROVED` |
| Transient provider/exec error | `FAILED_RETRYABLE` | `BLOCKED` |
| Unrecoverable contract/result error | `FAILED_TERMINAL` | `REJECTED` |
| Inputs/config expired | `STALE` | `STALE` |
| Needs new contract | `NEEDS_REMATERIALIZATION` | `STALE` |
| Replaced | `SUPERSEDED` | `SUPERSEDED` |
| Cancelled | `CANCELLED` | `CANCELLED` |

`BLOCKED` meaning is disambiguated by TaskStatus (`WAITING_ASSETS` vs `FAILED_RETRYABLE`).

### 4.4 WAITING_USER discrimination

```text
WAITING_USER + AWAITING_RESULT  → wait for Manual/Agent result
WAITING_USER + AWAITING_REVIEW  → wait for human approval
```

Delegated `--ready` **must** filter:

```text
tasks.status = WAITING_USER
AND visual_stage = AWAITING_RESULT
AND provider_type = delegated
```

### 4.5 Atomic transition API

```python
class VisualTaskService:
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

Single transaction: CAS `tasks.status` + CAS `visual_task_contracts.visual_stage` + event + COMMIT.  
Do **not** call `update_task_status` and stage update separately.

---

## 5. Purpose → Operation → Task Type

Caller passes `purpose` only; service derives operation and task type.

| Purpose | Default operation | Task type |
|---|---|---|
| `character_reference` | `text_to_image` / `reference_to_image` | `visual.generate` |
| `scene_reference` | `text_to_image` / `reference_to_image` | `visual.generate` |
| `prop_reference` | `text_to_image` / `reference_to_image` | `visual.generate` |
| `shot_start_frame` | based on refs | `visual.generate` |
| `shot_end_frame` | `reference_to_image` | `visual.generate` |
| `continuity_edit` | `image_edit` | `visual.edit` |

---

## 6. Visual Input Policy

Profile top-level:

```json
{ "visual_input_policy": "allow_t2va_fallback" }
```

| Value | Behavior |
|---|---|
| `allow_t2va_fallback` (default) | Missing visuals → WorkflowSelector may choose T2VA; keep 3/5/8/16 E2E green |
| `visual_required` | Create blocking `visual.generate`; video stays `WAITING_ASSETS`; no T2V fallback |

Never bypass when shot forces I2V / first_last / R2V / multi-ref / Level 1 edit / `visual_input_required=true` / explicit start frame.  
Production Proof **requires** `visual_required`.

---

## 7. Asset Type

Allowed globally:

```text
image | video | audio | subtitle | document
```

Forbidden as `asset_type` (use purpose / `asset_role` / `assets.metadata` / `relation_type`):

```text
image_edit, character_reference, scene_reference, shot_start_frame,
shot_end_frame, continuity_edit, character_map, scene_map, start_frame, end_frame
```

App-layer:

```python
ALLOWED_ASSET_TYPES = {"image", "video", "audio", "subtitle", "document"}
```

---

## 8. Schema v10

`SCHEMA_VERSION = 10`. Fresh schema ≡ migrated schema.

### 8.1 assets CHECK

Rebuild table if needed for CHECK. Pre-migrate `SELECT DISTINCT asset_type FROM assets`. Map legacy visual types → `image` and stash `legacy_visual_purpose` in `assets.metadata`. Unknown → fail migration (or wipe in pure test DBs).

### 8.2 attempts

```text
attempt_kind TEXT NOT NULL DEFAULT 'workflow'
  CHECK (attempt_kind IN ('workflow', 'visual_managed'))
workflow_id nullable with CHECK:
  workflow → workflow_id NOT NULL
  visual_managed → workflow_id IS NULL
```

Note: current fresh `attempts.workflow_id` is already nullable; migration still adds `attempt_kind` + CHECK.

### 8.3–8.8 New tables

Exactly as v8.1:

- `visual_provider_revisions` (scope_type/scope_id; unique active on provider_id+scope)
- `visual_generation_profile_revisions` (unique active per project)
- `visual_task_contracts` (incl. `visual_bible_revision_id` nullable FK, `compiler_identity_json`)
- `visual_result_manifests`
- `visual_provider_executions` (managed only)
- `visual_exchange_executions` (manual/delegated; statuses: exported|awaiting_result|result_imported|cancelled|expired)

Retain `provider_jobs` unchanged.

---

## 9. Provider Config Schema

Validate before CJ1 hash. Manual / Delegated / Managed schemas as in v8.1 (`lfo.visual-provider.*.v1`). Secrets only as refs (`auth_ref`, env name) — never raw secret in config or hash input.

---

## 10. Hash and Compiler Identity

| Object | Algorithm |
|---|---|
| Provider/Profile/Contract/Manifest/Routing/Exchange meta/Compiler Identity | **LFO-CJ1** |
| Comfy workflow JSON | **LFO-WFJ1** only |
| Media bytes / package file digests | **SHA-256** (`file_hash`) |

`visual/task_compiler.py` exposes `get_compiler_identity()` → persisted in `compiler_identity_json`.

Content hash includes: purpose, operation, prompt, output_contract, technical_checks, review_checklist, continuity_constraints.  
Dependency hash includes: profile, provider (after route), visual bible, storyboard, reference file hashes, compiler identity. Draft dependency hash allowed pre-route; recompute after route.

---

## 11. Visual Bible

On create: bind current approved bible revision when applicable; continuity-only edit may omit. Bible change → unstarted tasks `STALE`/`NEEDS_REMATERIALIZATION`; running keep old; approved assets stay valid until rebuild scope replaces bindings.

---

## 12–13. Provider scope and revision lineage

Resolve Active revision: **project scope > global scope**. Snapshot records `provider_revision_id`, `scope_type`, `scope_id`.

App-enforced linear parents: new draft `parent_revision_id = current active` (first = NULL). Rollback = clone history → new draft → activate. No GC in v10.

---

## 14. Profile

v8.1 profile JSON plus `visual_input_policy`. V1 routes by **purpose only**.

---

## 15–17. Provider interfaces, capabilities, routing

Interfaces as v8.1 (`VisualProvider`, `ManagedVisualProvider`, `ExchangeVisualProvider`, registry by revision id).

Routing order: override → purpose rules → defaults → fallbacks.  
Filters: active → capability superset → max_concurrency (count rows in `visual_provider_executions` with status in queued/running/submitted) → `serial_group` + existing `ResourcePolicy`. **No second scheduler.**

---

## 18. DAG integration

Modify `services/storyboard_graph_service.py` (and prompt planning) to insert visual tasks per policy. Continuity Level 1 edits created from continuity flow, not initial graph. Dependencies via existing `tasks.dependencies` JSON.

---

## 19. Dual gate

Video READY requires:

1. Dependencies terminal **and** for visual deps prefer `APPROVED` (do not treat mid-flight visual as done — visual never sits on `SUCCEEDED`), and  
2. `check_visual_assets_ready` / existing `AssetBindingService.get_current_approved_asset` for required roles.

Hook into `TaskReadinessService` before promote.

---

## 20. Exchange vs Managed execution

```text
Exchange: READY/ROUTED → export → WAITING_USER/AWAITING_RESULT
          → import → QC_PENDING/RESULT_IMPORTED → …
Managed:  READY/ROUTED → visual_managed attempt + visual_provider_execution
          → QUEUED/RUNNING/SUBMITTED → collect → QC_PENDING/RESULT_IMPORTED → …
```

---

## 21–22. Idempotency and file hash

As v8.1 (task / managed attempt / exchange package keys). `file_hash` = SHA-256 bytes; semantic `content_hash` = CJ1. Mismatch → `RESULT_HASH_MISMATCH`.

Canonical asset path: `project://assets/visual/<task_id>/<asset_id>.<ext>`.

---

## 23. Import and QC

Import sequence as v8.1, ending in **`QC_PENDING` + `RESULT_IMPORTED`** (not `SUCCEEDED`).

`VisualTechnicalQCService` auto: decodable, hash, mime, dimensions, count, alpha, orientation, refs current.  
Human checklist: identity, costume, character count, composition, scene — **not** auto-gated.

On approve: create/revise current binding → `APPROVED` + `APPROVED`.

---

## 24. CLI layering

- `lfo setup` — machine (ffmpeg, Comfy, models, machine managed adapter config)
- `lfo project init` — project profile/providers/policy  
Visual CLI group: profile / provider / task / result / route dry-run.

---

## 25. Profile switch / invalidation

Reuse `invalidate_upstream` + `STALE` / `NEEDS_REMATERIALIZATION`. No visual-only invalidation engine. Binding replace propagates video rematerialization chain.

---

## 26. Phases and gates

**Phase 0** — baseline, delete VisualAssetService, rename keyframe.image, freeze contracts, update AGENTS.md; video + local E2E green.  
**V1** Schema v10 · **V2** Domain · **V3** Task/Result/QC + atomic transition · **V4** Providers/routing/exchange · **V5** CLI · **V6** DAG/policy · **V7** Profile switch · **V8** Level 1 continuity · **V9** Mode Complete M0–M13 · **V10** Production Proof P1–P5.

Mode Complete = M0–M13. Production Proven = P1–P5 (separate).

---

## 27. Explicit non-goals (Mode Complete)

Built-in Qwen Image; commercial multiview; auto inpaint; aesthetic/identity auto scores; unattended visual approve; periodic background probe; paid-provider billing adapters; agent-private skill adapters beyond exchange format.

---

## 28. Implementation plan requirements

The implementation plan must include: file-level change list; v10 migration order; exact service interfaces; every CAS transition; commit scopes; test add/remove lists; parallel dependency graph; M0–M13 commands; Production Proof script outline; per-phase done definition.
