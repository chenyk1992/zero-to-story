"""LFO SQLite Runtime — schema, connection, and migration.

Design:
- WAL mode: concurrent reads + single writer
- Foreign keys enforced (PRAGMA foreign_keys = ON)
- Schema versioned via user_version
- JSON columns for flexible metadata (text stored as UTF-8)
- Timestamps as ISO 8601 text in UTC
"""
from __future__ import annotations

import pathlib
import sqlite3
from contextlib import contextmanager

# Schema version for migrations
SCHEMA_VERSION = 10  # v10: visual production tables + attempt_kind

# The full DDL, executed in order
SCHEMA_SQL = """
-- Enable foreign keys (must be set per connection)
-- PRAGMA foreign_keys = ON;

-- ===========================================================================
-- Core task tracking
-- ===========================================================================

CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    task_type       TEXT NOT NULL,           -- 'keyframe' | 'h3_t2va' | 'h3_i2v' | ...
    status          TEXT NOT NULL DEFAULT 'PLANNED',
    dependencies    TEXT NOT NULL DEFAULT '[]',  -- JSON array of task_ids
    serial_group    TEXT,                    -- group identifier for serial execution
    priority_class  INTEGER NOT NULL DEFAULT 30,
    priority_override INTEGER,
    attempt_ids     TEXT NOT NULL DEFAULT '[]',  -- JSON array of attempt_ids
    latest_attempt_id TEXT,
    error           TEXT,
    content_hash    TEXT,                    -- LFO-CJ1 content hash
    dependency_hash TEXT,                    -- closure hash of upstream
    params_hash     TEXT,                    -- execution params hash
    idempotency_key TEXT UNIQUE,             -- dedup key
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    -- Business rule: READY tasks must have complete fingerprints
    CHECK (
        (status != 'READY') OR
        (dependency_hash IS NOT NULL AND params_hash IS NOT NULL AND idempotency_key IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key);

-- ===========================================================================
-- Generation attempts (one row per execution attempt)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id      TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    idempotency_key TEXT NOT NULL,
    workflow_id     TEXT,                    -- which workflow was used
    attempt_kind    TEXT NOT NULL DEFAULT 'workflow'
                        CHECK (attempt_kind IN ('workflow', 'visual_managed')),
    params          TEXT NOT NULL DEFAULT '{}',  -- JSON: execution params
    content_hash    TEXT NOT NULL,
    dependency_hash TEXT NOT NULL,
    params_hash     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PREPARED',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    machine_id                  TEXT,
    environment_snapshot_id     TEXT,
    execution_environment_hash  TEXT,
    -- workflow attempts require a workflow_id; visual_managed must not have one
    CHECK (
        (attempt_kind = 'workflow')
        OR (attempt_kind = 'visual_managed' AND workflow_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);
CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status);

-- ===========================================================================
-- Submission journal — CAS state transitions
-- ===========================================================================

CREATE TABLE IF NOT EXISTS submission_journal (
    journal_id      TEXT PRIMARY KEY,
    attempt_id      TEXT NOT NULL REFERENCES attempts(attempt_id),
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    state           TEXT NOT NULL DEFAULT 'PREPARED',
    from_state      TEXT,                    -- previous state for CAS verification
    provider_job_id TEXT,                    -- ComfyUI prompt_id
    prompt_id       TEXT,                    -- alias for provider_job_id
    submitted_at    TEXT,
    collected_at    TEXT,
    error           TEXT,
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON: extra context
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_submission_attempt ON submission_journal(attempt_id);
CREATE INDEX IF NOT EXISTS idx_submission_state ON submission_journal(state);

-- ===========================================================================
-- Provider jobs — external job tracking
-- ===========================================================================

CREATE TABLE IF NOT EXISTS provider_jobs (
    provider_job_id TEXT PRIMARY KEY,        -- ComfyUI prompt_id
    attempt_id      TEXT NOT NULL REFERENCES attempts(attempt_id),
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    provider        TEXT NOT NULL DEFAULT 'comfyui',
    status          TEXT NOT NULL DEFAULT 'SUBMITTED',
    queue_position  INTEGER,
    started_at      TEXT,
    completed_at    TEXT,
    error           TEXT,
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_provider_attempt ON provider_jobs(attempt_id);
CREATE INDEX IF NOT EXISTS idx_provider_status ON provider_jobs(status);

-- ===========================================================================
-- User approvals
-- ===========================================================================

CREATE TABLE IF NOT EXISTS approvals (
    approval_id     TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    attempt_id      TEXT REFERENCES attempts(attempt_id),
    asset_id        TEXT,                    -- specific asset being approved
    approval_type   TEXT NOT NULL,           -- 'keyframe' | 'video' | 'storyboard' | ...
    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | APPROVED | REJECTED
    approved_hash   TEXT,                    -- content hash at time of approval
    approved_at     TEXT,
    rejected_at     TEXT,
    feedback        TEXT,                    -- user feedback
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_approvals_task ON approvals(task_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);

-- ===========================================================================
-- Assets — generated output files
-- ===========================================================================

CREATE TABLE IF NOT EXISTS assets (
    asset_id        TEXT PRIMARY KEY,
    task_id         TEXT REFERENCES tasks(task_id),
    attempt_id      TEXT REFERENCES attempts(attempt_id),
    asset_type      TEXT NOT NULL
        CHECK (asset_type IN ('image', 'video', 'audio', 'subtitle', 'document')),
    file_path       TEXT NOT NULL,
    file_hash       TEXT,                    -- SHA-256 of file content
    file_size       INTEGER,
    mime_type       TEXT,
    width           INTEGER,
    height          INTEGER,
    duration        REAL,
    frame_count     INTEGER,
    content_hash    TEXT,                    -- semantic hash
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON: codec, fps, etc.
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_assets_task ON assets(task_id);
CREATE INDEX IF NOT EXISTS idx_assets_attempt ON assets(attempt_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);

-- ===========================================================================
-- Asset relations — provenance / dependency graph
-- ===========================================================================

CREATE TABLE IF NOT EXISTS asset_relations (
    relation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    source_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    target_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    relation_type   TEXT NOT NULL,           -- 'derived_from' | 'input_to' | 'continuity_from'
    metadata        TEXT NOT NULL DEFAULT '{}',  -- JSON
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON asset_relations(source_asset_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON asset_relations(target_asset_id);

-- ===========================================================================
-- Invalidations — dirty scope propagation
-- ===========================================================================

CREATE TABLE IF NOT EXISTS invalidations (
    invalidation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_task_id  TEXT NOT NULL REFERENCES tasks(task_id),
    target_task_id  TEXT NOT NULL REFERENCES tasks(task_id),
    reason          TEXT NOT NULL,           -- 'upstream_changed' | 'manual' | 'scope'
    scope           TEXT NOT NULL DEFAULT '{}',  -- JSON: what exactly changed
    resolved        INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
    resolved_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_invalidations_target ON invalidations(target_task_id);
CREATE INDEX IF NOT EXISTS idx_invalidations_resolved ON invalidations(resolved);

-- ===========================================================================
-- QC reports
-- ===========================================================================

CREATE TABLE IF NOT EXISTS qc_reports (
    report_id       TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    attempt_id      TEXT REFERENCES attempts(attempt_id),
    asset_id        TEXT REFERENCES assets(asset_id),
    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | PASS | FAIL
    checks          TEXT NOT NULL DEFAULT '{}',  -- JSON: check results
    issues          TEXT NOT NULL DEFAULT '[]',  -- JSON array of issues
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_qc_task ON qc_reports(task_id);
CREATE INDEX IF NOT EXISTS idx_qc_status ON qc_reports(status);

-- ===========================================================================
-- Events — audit log
-- ===========================================================================

CREATE TABLE IF NOT EXISTS events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT NOT NULL,
    task_id         TEXT REFERENCES tasks(task_id),
    attempt_id      TEXT REFERENCES attempts(attempt_id),
    event_type      TEXT NOT NULL,
    payload         TEXT NOT NULL DEFAULT '{}',  -- JSON
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);

-- ===========================================================================
-- Task leases — for multi-worker coordination
-- ===========================================================================

CREATE TABLE IF NOT EXISTS task_leases (
    lease_id        TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    worker_id       TEXT NOT NULL,
    acquired_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at      TEXT NOT NULL,
    released        INTEGER NOT NULL DEFAULT 0,
    released_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_leases_task ON task_leases(task_id);
CREATE INDEX IF NOT EXISTS idx_leases_worker ON task_leases(worker_id);
CREATE INDEX IF NOT EXISTS idx_leases_expires ON task_leases(expires_at);

-- ===========================================================================
-- Environment snapshots — traceability + cache key
-- ===========================================================================

CREATE TABLE IF NOT EXISTS environment_snapshots (
    snapshot_id         TEXT PRIMARY KEY,
    machine_id          TEXT NOT NULL,
    captured_at         TEXT NOT NULL,
    snapshot_json       TEXT NOT NULL,       -- Full snapshot including paths
    execution_environment_hash TEXT NOT NULL  -- Path-free hash for cache
);

CREATE INDEX IF NOT EXISTS idx_snapshots_machine
    ON environment_snapshots(machine_id);

-- ===========================================================================
-- Task materializations — execution snapshots for READY tasks
-- ===========================================================================

CREATE TABLE IF NOT EXISTS task_materializations (
    materialization_id     TEXT PRIMARY KEY,
    task_id                TEXT NOT NULL REFERENCES tasks(task_id),
    project_id             TEXT NOT NULL,
    workflow_id            TEXT NOT NULL,
    params                 TEXT NOT NULL DEFAULT '{}',  -- JSON: resolved params
    params_hash            TEXT NOT NULL,
    idempotency_key        TEXT NOT NULL,
    environment_snapshot_id TEXT NOT NULL,
    environment_execution_hash TEXT NOT NULL,
    binding_snapshot       TEXT NOT NULL DEFAULT '{}',  -- JSON: asset bindings at materialization time
    prompt_snapshot        TEXT NOT NULL DEFAULT '{}',  -- JSON: compiled prompt at materialization time
    created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_materializations_task
    ON task_materializations(task_id);
CREATE INDEX IF NOT EXISTS idx_materializations_project
    ON task_materializations(project_id);
CREATE INDEX IF NOT EXISTS idx_materializations_idempotency
    ON task_materializations(idempotency_key);

-- ===========================================================================
-- Preflights — task-specific pre-execution checks
-- ===========================================================================

CREATE TABLE IF NOT EXISTS preflights (
    preflight_id        TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL,
    snapshot_id         TEXT NOT NULL REFERENCES environment_snapshots(snapshot_id),
    status              TEXT NOT NULL,       -- 'passed' | 'warning' | 'blocked'
    context_hash        TEXT NOT NULL,       -- hash of PreflightContext
    results_json        TEXT NOT NULL,       -- JSON array of CheckResult
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_preflights_project
    ON preflights(project_id);

-- ===========================================================================
-- Projects — top-level grouping for tasks and assets
-- ===========================================================================

CREATE TABLE IF NOT EXISTS projects (
    project_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ===========================================================================
-- Asset bindings — revisioned binding of assets to entities
-- ===========================================================================

CREATE TABLE IF NOT EXISTS asset_bindings (
    binding_id      TEXT PRIMARY KEY,
    asset_id        TEXT NOT NULL,
    project_id      TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    asset_role      TEXT NOT NULL,
    revision        INTEGER NOT NULL CHECK (revision >= 1),
    validity        TEXT NOT NULL
        CHECK (validity IN ('current', 'stale', 'superseded')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    superseded_by   TEXT,

    FOREIGN KEY (asset_id)
        REFERENCES assets(asset_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (project_id)
        REFERENCES projects(project_id)
        ON DELETE CASCADE,

    FOREIGN KEY (superseded_by)
        REFERENCES asset_bindings(binding_id)
        ON DELETE SET NULL,

    UNIQUE (
        project_id,
        entity_type,
        entity_id,
        asset_role,
        revision
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_bindings_current
ON asset_bindings (
    project_id,
    entity_type,
    entity_id,
    asset_role
)
WHERE validity = 'current';

CREATE INDEX IF NOT EXISTS idx_asset_bindings_asset
ON asset_bindings(asset_id);

CREATE INDEX IF NOT EXISTS idx_asset_bindings_project
ON asset_bindings(project_id);

-- ===========================================================================
-- Asset reviews — approval / rejection records per asset
-- ===========================================================================

CREATE TABLE IF NOT EXISTS asset_reviews (
    review_id           TEXT PRIMARY KEY,
    asset_id            TEXT NOT NULL,
    dependency_hash     TEXT NOT NULL,
    technical_status    TEXT NOT NULL
        CHECK (technical_status IN (
            'not_checked', 'passed', 'failed'
        )),
    manual_review_status TEXT NOT NULL
        CHECK (manual_review_status IN (
            'not_reviewed', 'pending', 'approved', 'rejected'
        )),
    review_source       TEXT NOT NULL,
    reviewer            TEXT,
    rejection_reason    TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (asset_id)
        REFERENCES assets(asset_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_asset_reviews_asset
ON asset_reviews(asset_id);

CREATE INDEX IF NOT EXISTS idx_asset_reviews_status
ON asset_reviews(manual_review_status);

-- ===========================================================================
-- Visual Bible revisions — visual consistency reference data
-- ===========================================================================

CREATE TABLE IF NOT EXISTS visual_bible_revisions (
    revision_id         TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL,
    content             TEXT NOT NULL,           -- JSON content
    content_hash        TEXT NOT NULL UNIQUE,    -- LFO-CJ1 semantic hash
    parent_revision_id  TEXT,                    -- previous revision (linear history)
    status              TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'pending_review', 'approved', 'rejected', 'superseded')),
    created_by          TEXT NOT NULL,
    approved_by         TEXT,
    approved_at         TEXT,
    rejection_reason    TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (project_id)
        REFERENCES projects(project_id)
        ON DELETE CASCADE,

    FOREIGN KEY (parent_revision_id)
        REFERENCES visual_bible_revisions(revision_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vb_project
    ON visual_bible_revisions(project_id);

CREATE INDEX IF NOT EXISTS idx_vb_status
    ON visual_bible_revisions(status);

CREATE INDEX IF NOT EXISTS idx_vb_hash
    ON visual_bible_revisions(content_hash);

-- ===========================================================================
-- Selected Clips — revisioned, approvable clip selections (v7)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS selected_clips (
    selected_clip_id             TEXT PRIMARY KEY,
    project_id                   TEXT NOT NULL,
    shot_id                      TEXT NOT NULL,

    normalized_asset_id          TEXT NOT NULL,
    output_asset_id              TEXT,

    selected_in_frame            INTEGER NOT NULL,
    selected_out_frame_exclusive INTEGER NOT NULL,
    fps_num                      INTEGER NOT NULL,
    fps_den                      INTEGER NOT NULL,

    render_policy_id             TEXT NOT NULL,
    revision                     INTEGER NOT NULL,
    status                       TEXT NOT NULL,

    content_hash                 TEXT NOT NULL,
    dependency_hash              TEXT NOT NULL,

    created_at                   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    approved_at                  TEXT,
    superseded_by                TEXT,

    FOREIGN KEY (normalized_asset_id)
        REFERENCES assets(asset_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (output_asset_id)
        REFERENCES assets(asset_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (superseded_by)
        REFERENCES selected_clips(selected_clip_id)
        ON DELETE SET NULL,

    UNIQUE(project_id, shot_id, revision)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_selected_clips_current_approved
ON selected_clips(project_id, shot_id)
WHERE status = 'approved';

CREATE INDEX IF NOT EXISTS idx_selected_clips_project
    ON selected_clips(project_id);

CREATE INDEX IF NOT EXISTS idx_selected_clips_status
    ON selected_clips(status);

CREATE INDEX IF NOT EXISTS idx_selected_clips_normalized
    ON selected_clips(normalized_asset_id);

-- ===========================================================================
-- Edit Decision Lists (EDL) — revisioned edit documents (v8)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS edit_decision_lists (
    edl_id              TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL,
    revision            INTEGER NOT NULL,

    content_json        TEXT NOT NULL,
    content_hash        TEXT NOT NULL,
    dependency_hash     TEXT NOT NULL,

    status              TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    approved_at         TEXT,

    UNIQUE(project_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_edl_project
    ON edit_decision_lists(project_id);

CREATE INDEX IF NOT EXISTS idx_edl_status
    ON edit_decision_lists(status);

-- ===========================================================================
-- Continuity States — semantic-level shot continuity (v9)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS continuity_states (
    continuity_id       TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL,
    shot_id             TEXT NOT NULL,

    source_shot_id      TEXT,
    end_frame_asset_id  TEXT,

    state_json          TEXT NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending',

    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    approved_at         TEXT,
    approved_by         TEXT,

    FOREIGN KEY (project_id)
        REFERENCES projects(project_id)
        ON DELETE CASCADE,

    FOREIGN KEY (end_frame_asset_id)
        REFERENCES assets(asset_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_continuity_project
    ON continuity_states(project_id);

CREATE INDEX IF NOT EXISTS idx_continuity_shot
    ON continuity_states(shot_id);

CREATE INDEX IF NOT EXISTS idx_continuity_status
    ON continuity_states(status);

-- ===========================================================================
-- Visual Provider Revisions — scoped provider config (v10)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS visual_provider_revisions (
    revision_id         TEXT PRIMARY KEY,
    provider_id         TEXT NOT NULL,
    scope_type          TEXT NOT NULL,           -- 'project' | 'global'
    scope_id            TEXT NOT NULL,           -- project_id or 'global'
    provider_type       TEXT NOT NULL,           -- 'manual' | 'delegated' | 'managed'
    adapter_name        TEXT NOT NULL,
    config              TEXT NOT NULL DEFAULT '{}',  -- JSON
    capabilities        TEXT NOT NULL DEFAULT '{}',  -- JSON
    serial_group        TEXT,
    max_concurrency     INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'disabled', 'superseded')),
    parent_revision_id  TEXT,
    activated_at        TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (parent_revision_id)
        REFERENCES visual_provider_revisions(revision_id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vpr_active
    ON visual_provider_revisions (provider_id, scope_type, scope_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_vpr_provider ON visual_provider_revisions (provider_id);
CREATE INDEX IF NOT EXISTS idx_vpr_scope ON visual_provider_revisions (scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_vpr_status ON visual_provider_revisions (status);

-- ===========================================================================
-- Visual Generation Profile Revisions — per-project profile (v10)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS visual_generation_profile_revisions (
    revision_id         TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL,
    content             TEXT NOT NULL,               -- JSON
    content_hash        TEXT NOT NULL,               -- LFO-CJ1 (not UNIQUE: clones share content)
    visual_input_policy TEXT NOT NULL DEFAULT 'allow_t2va_fallback',
    status              TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'superseded')),
    parent_revision_id  TEXT,
    created_by          TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_revision_id)
        REFERENCES visual_generation_profile_revisions(revision_id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vgpr_active
    ON visual_generation_profile_revisions (project_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_vgpr_status ON visual_generation_profile_revisions (status);

-- ===========================================================================
-- Visual Task Contracts — domain detail for visual tasks (v10)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS visual_task_contracts (
    task_id             TEXT PRIMARY KEY,
    visual_stage        TEXT NOT NULL DEFAULT 'UNROUTED',
    purpose             TEXT NOT NULL,
    operation           TEXT NOT NULL,
    task_type           TEXT NOT NULL,               -- 'visual.generate' | 'visual.edit'
    prompt              TEXT,                        -- JSON
    reference_list      TEXT,                        -- JSON array
    output_contract     TEXT,                        -- JSON
    technical_checks    TEXT,                        -- JSON
    review_checklist    TEXT,                        -- JSON
    continuity_constraints TEXT,                     -- JSON
    compiler_identity_json TEXT,
    visual_bible_revision_id TEXT,
    provider_id         TEXT,
    provider_revision_id TEXT,
    routing_snapshot_json TEXT,
    content_hash        TEXT,
    dependency_hash     TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (visual_bible_revision_id)
        REFERENCES visual_bible_revisions(revision_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vtc_stage ON visual_task_contracts (visual_stage);
CREATE INDEX IF NOT EXISTS idx_vtc_purpose ON visual_task_contracts (purpose);
CREATE INDEX IF NOT EXISTS idx_vtc_task_type ON visual_task_contracts (task_type);
CREATE INDEX IF NOT EXISTS idx_vtc_provider ON visual_task_contracts (provider_id);
CREATE INDEX IF NOT EXISTS idx_vtc_bible ON visual_task_contracts (visual_bible_revision_id);

-- ===========================================================================
-- Visual Result Manifests — imported result metadata (v10)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS visual_result_manifests (
    manifest_id         TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL,
    content             TEXT NOT NULL,               -- JSON
    content_hash        TEXT NOT NULL,               -- LFO-CJ1
    file_hash           TEXT,                        -- SHA-256 of file bytes
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vrm_task ON visual_result_manifests (task_id);
CREATE INDEX IF NOT EXISTS idx_vrm_status ON visual_result_manifests (status);

-- ===========================================================================
-- Visual Provider Executions — managed provider job tracking (v10)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS visual_provider_executions (
    execution_id        TEXT PRIMARY KEY,
    attempt_id          TEXT NOT NULL,
    task_id             TEXT NOT NULL,
    provider_revision_id TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    result_manifest_id  TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    error               TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (provider_revision_id)
        REFERENCES visual_provider_revisions(revision_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (result_manifest_id)
        REFERENCES visual_result_manifests(manifest_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vpe_attempt ON visual_provider_executions (attempt_id);
CREATE INDEX IF NOT EXISTS idx_vpe_task ON visual_provider_executions (task_id);
CREATE INDEX IF NOT EXISTS idx_vpe_status ON visual_provider_executions (status);

-- ===========================================================================
-- Visual Exchange Executions — manual/delegated exchange tracking (v10)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS visual_exchange_executions (
    execution_id        TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL,
    provider_revision_id TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'exported'
        CHECK (status IN ('exported', 'awaiting_result', 'result_imported', 'cancelled', 'expired')),
    package_json        TEXT,                        -- JSON: exported package
    result_manifest_id  TEXT,
    exchanged_at        TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (provider_revision_id)
        REFERENCES visual_provider_revisions(revision_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (result_manifest_id)
        REFERENCES visual_result_manifests(manifest_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vee_task ON visual_exchange_executions (task_id);
CREATE INDEX IF NOT EXISTS idx_vee_status ON visual_exchange_executions (status);

-- ===========================================================================
-- Attempts table extension (v3 columns)
-- ===========================================================================

-- These ALTER TABLE statements are idempotent — safe to run on existing DBs.
-- On fresh databases, the columns are already included in CREATE TABLE above.
"""


class Database:
    """SQLite connection manager for LFO runtime.

    Usage:
        db = Database(path)
        with db.transaction() as conn:
            ...
    """

    def __init__(self, path: str | pathlib.Path | None = None):
        if path is None:
            path = ":memory:"
        self.path = pathlib.Path(path) if path != ":memory:" else path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def _connect(self) -> sqlite3.Connection:
        if isinstance(self.path, pathlib.Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(
            str(self.path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None,  # we manage transactions explicitly
        )
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=5000")
        c.row_factory = sqlite3.Row
        return c

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def init_schema(self):
        """Create all tables if they don't exist, then migrate if needed."""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def migrate(self):
        """Run migrations to bring schema up to current version."""
        current = self.schema_version
        if current < 2:
            # v1 → v2: Add CHECK constraint (only effective for new databases)
            # Existing databases enforce this in the application layer
            self.conn.execute("PRAGMA user_version = 2")
        if current < 3:
            # v2 → v3: Add new tables and attempt columns
            self._migrate_v2_to_v3()
        if current < 4:
            # v3 → v4: Add projects, asset_bindings, asset_reviews
            self._migrate_v3_to_v4()
        if current < 5:
            # v4 → v5: Add visual_bible_revisions
            self._migrate_v4_to_v5()
        if current < 6:
            # v5 → v6: Add task_materializations
            self._migrate_v5_to_v6()
        if current < 7:
            # v6 → v7: Add selected_clips
            self._migrate_v6_to_v7()
        if current < 8:
            # v7 → v8: Add edit_decision_lists
            self._migrate_v7_to_v8()
        if current < 9:
            # v8 → v9: Add continuity_states
            self._migrate_v8_to_v9()
        if current < 10:
            # v9 → v10: visual tables + attempt_kind + assets type CHECK
            self._migrate_v9_to_v10()
        # Add future migrations here (v11, v12, ...)

    def _migrate_v2_to_v3(self):
        """Migration v2 → v3: Add environment_snapshots, preflights, attempts columns."""
        # Add columns to attempts table (ignore if already exists)
        try:
            self.conn.execute(
                "ALTER TABLE attempts ADD COLUMN machine_id TEXT"
            )
        except Exception:
            pass  # column already exists
        try:
            self.conn.execute(
                "ALTER TABLE attempts ADD COLUMN environment_snapshot_id "
                "TEXT REFERENCES environment_snapshots(snapshot_id)"
            )
        except Exception:
            pass
        try:
            self.conn.execute(
                "ALTER TABLE attempts ADD COLUMN execution_environment_hash TEXT"
            )
        except Exception:
            pass
        # Create new tables
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS environment_snapshots (
                snapshot_id         TEXT PRIMARY KEY,
                machine_id          TEXT NOT NULL,
                captured_at         TEXT NOT NULL,
                snapshot_json       TEXT NOT NULL,
                execution_environment_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_machine
                ON environment_snapshots(machine_id);
            CREATE TABLE IF NOT EXISTS preflights (
                preflight_id        TEXT PRIMARY KEY,
                project_id          TEXT NOT NULL,
                snapshot_id         TEXT NOT NULL REFERENCES environment_snapshots(snapshot_id),
                status              TEXT NOT NULL,
                context_hash        TEXT NOT NULL,
                results_json        TEXT NOT NULL,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_preflights_project
                ON preflights(project_id);
        """)
        self.conn.execute("PRAGMA user_version = 3")

    def _migrate_v3_to_v4(self):
        """Migration v3 → v4: Add projects, asset_bindings, asset_reviews."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id      TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'active',
                created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );

            CREATE TABLE IF NOT EXISTS asset_bindings (
                binding_id      TEXT PRIMARY KEY,
                asset_id        TEXT NOT NULL,
                project_id      TEXT NOT NULL,
                entity_type     TEXT NOT NULL,
                entity_id       TEXT NOT NULL,
                asset_role      TEXT NOT NULL,
                revision        INTEGER NOT NULL CHECK (revision >= 1),
                validity        TEXT NOT NULL
                    CHECK (validity IN ('current', 'stale', 'superseded')),
                created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                superseded_by   TEXT,

                FOREIGN KEY (asset_id)
                    REFERENCES assets(asset_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (project_id)
                    REFERENCES projects(project_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (superseded_by)
                    REFERENCES asset_bindings(binding_id)
                    ON DELETE SET NULL,

                UNIQUE (
                    project_id,
                    entity_type,
                    entity_id,
                    asset_role,
                    revision
                )
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_bindings_current
            ON asset_bindings (
                project_id,
                entity_type,
                entity_id,
                asset_role
            )
            WHERE validity = 'current';

            CREATE INDEX IF NOT EXISTS idx_asset_bindings_asset
            ON asset_bindings(asset_id);

            CREATE INDEX IF NOT EXISTS idx_asset_bindings_project
            ON asset_bindings(project_id);

            CREATE TABLE IF NOT EXISTS asset_reviews (
                review_id           TEXT PRIMARY KEY,
                asset_id            TEXT NOT NULL,
                dependency_hash     TEXT NOT NULL,
                technical_status    TEXT NOT NULL
                    CHECK (technical_status IN (
                        'not_checked', 'passed', 'failed'
                    )),
                manual_review_status TEXT NOT NULL
                    CHECK (manual_review_status IN (
                        'not_reviewed', 'pending', 'approved', 'rejected'
                    )),
                review_source       TEXT NOT NULL,
                reviewer            TEXT,
                rejection_reason    TEXT,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

                FOREIGN KEY (asset_id)
                    REFERENCES assets(asset_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_asset_reviews_asset
            ON asset_reviews(asset_id);

            CREATE INDEX IF NOT EXISTS idx_asset_reviews_status
            ON asset_reviews(manual_review_status);
        """)
        self.conn.execute("PRAGMA user_version = 4")

    def _migrate_v4_to_v5(self):
        """Migration v4 → v5: Add visual_bible_revisions."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS visual_bible_revisions (
                revision_id         TEXT PRIMARY KEY,
                project_id          TEXT NOT NULL,
                content             TEXT NOT NULL,
                content_hash        TEXT NOT NULL UNIQUE,
                parent_revision_id  TEXT,
                status              TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'pending_review', 'approved', 'rejected', 'superseded')),
                created_by          TEXT NOT NULL,
                approved_by         TEXT,
                approved_at         TEXT,
                rejection_reason    TEXT,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

                FOREIGN KEY (project_id)
                    REFERENCES projects(project_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (parent_revision_id)
                    REFERENCES visual_bible_revisions(revision_id)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_vb_project
                ON visual_bible_revisions(project_id);

            CREATE INDEX IF NOT EXISTS idx_vb_status
                ON visual_bible_revisions(status);

            CREATE INDEX IF NOT EXISTS idx_vb_hash
                ON visual_bible_revisions(content_hash);
        """)
        self.conn.execute("PRAGMA user_version = 5")

    def _migrate_v5_to_v6(self):
        """Migration v5 → v6: Add task_materializations table."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_materializations (
                materialization_id     TEXT PRIMARY KEY,
                task_id                TEXT NOT NULL REFERENCES tasks(task_id),
                project_id             TEXT NOT NULL,
                workflow_id            TEXT NOT NULL,
                params                 TEXT NOT NULL DEFAULT '{}',
                params_hash            TEXT NOT NULL,
                idempotency_key        TEXT NOT NULL,
                environment_snapshot_id TEXT NOT NULL,
                environment_execution_hash TEXT NOT NULL,
                binding_snapshot       TEXT NOT NULL DEFAULT '{}',
                prompt_snapshot        TEXT NOT NULL DEFAULT '{}',
                created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_materializations_task
                ON task_materializations(task_id);
            CREATE INDEX IF NOT EXISTS idx_materializations_project
                ON task_materializations(project_id);
            CREATE INDEX IF NOT EXISTS idx_materializations_idempotency
                ON task_materializations(idempotency_key);
        """)
        self.conn.execute("PRAGMA user_version = 6")

    def _migrate_v6_to_v7(self):
        """Migration v6 → v7: Add selected_clips table."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS selected_clips (
                selected_clip_id             TEXT PRIMARY KEY,
                project_id                   TEXT NOT NULL,
                shot_id                      TEXT NOT NULL,

                normalized_asset_id          TEXT NOT NULL,
                output_asset_id              TEXT,

                selected_in_frame            INTEGER NOT NULL,
                selected_out_frame_exclusive INTEGER NOT NULL,
                fps_num                      INTEGER NOT NULL,
                fps_den                      INTEGER NOT NULL,

                render_policy_id             TEXT NOT NULL,
                revision                     INTEGER NOT NULL,
                status                       TEXT NOT NULL,

                content_hash                 TEXT NOT NULL,
                dependency_hash              TEXT NOT NULL,

                created_at                   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                approved_at                  TEXT,
                superseded_by                TEXT,

                FOREIGN KEY (normalized_asset_id)
                    REFERENCES assets(asset_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (output_asset_id)
                    REFERENCES assets(asset_id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (superseded_by)
                    REFERENCES selected_clips(selected_clip_id)
                    ON DELETE SET NULL,

                UNIQUE(project_id, shot_id, revision)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_selected_clips_current_approved
            ON selected_clips(project_id, shot_id)
            WHERE status = 'approved';

            CREATE INDEX IF NOT EXISTS idx_selected_clips_project
                ON selected_clips(project_id);

            CREATE INDEX IF NOT EXISTS idx_selected_clips_status
                ON selected_clips(status);

            CREATE INDEX IF NOT EXISTS idx_selected_clips_normalized
                ON selected_clips(normalized_asset_id);
        """)
        self.conn.execute("PRAGMA user_version = 7")

    def _migrate_v7_to_v8(self):
        """Migration v7 → v8: Add edit_decision_lists table."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS edit_decision_lists (
                edl_id              TEXT PRIMARY KEY,
                project_id          TEXT NOT NULL,
                revision            INTEGER NOT NULL,

                content_json        TEXT NOT NULL,
                content_hash        TEXT NOT NULL,
                dependency_hash     TEXT NOT NULL,

                status              TEXT NOT NULL,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                approved_at         TEXT,

                UNIQUE(project_id, revision)
            );

            CREATE INDEX IF NOT EXISTS idx_edl_project
                ON edit_decision_lists(project_id);

            CREATE INDEX IF NOT EXISTS idx_edl_status
                ON edit_decision_lists(status);
        """)
        self.conn.execute("PRAGMA user_version = 8")

    def _migrate_v8_to_v9(self):
        """Migration v8 → v9: Add continuity_states table."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS continuity_states (
                continuity_id       TEXT PRIMARY KEY,
                project_id          TEXT NOT NULL,
                shot_id             TEXT NOT NULL,

                source_shot_id      TEXT,
                end_frame_asset_id  TEXT,

                state_json          TEXT NOT NULL DEFAULT '{}',
                status              TEXT NOT NULL DEFAULT 'pending',

                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                approved_at         TEXT,
                approved_by         TEXT,

                FOREIGN KEY (project_id)
                    REFERENCES projects(project_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (end_frame_asset_id)
                    REFERENCES assets(asset_id)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_continuity_project
                ON continuity_states(project_id);

            CREATE INDEX IF NOT EXISTS idx_continuity_shot
                ON continuity_states(shot_id);

            CREATE INDEX IF NOT EXISTS idx_continuity_status
                ON continuity_states(status);
        """)
        self.conn.execute("PRAGMA user_version = 9")

    def _migrate_v9_to_v10(self):
        """Migration v9 → v10: visual tables, attempt_kind, assets type CHECK.

        - Create six visual tables IF NOT EXISTS
        - Rebuild attempts to add attempt_kind + cross-column CHECK
        - Rebuild assets to add type CHECK, remapping legacy visual types
        - Never drop provider_jobs
        """
        import json

        # -- 1. Visual tables (idempotent) -------------------------------
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS visual_provider_revisions (
                revision_id         TEXT PRIMARY KEY,
                provider_id         TEXT NOT NULL,
                scope_type          TEXT NOT NULL,
                scope_id            TEXT NOT NULL,
                provider_type       TEXT NOT NULL,
                adapter_name        TEXT NOT NULL,
                config              TEXT NOT NULL DEFAULT '{}',
                capabilities        TEXT NOT NULL DEFAULT '{}',
                serial_group        TEXT,
                max_concurrency     INTEGER NOT NULL DEFAULT 1,
                status              TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'active', 'disabled', 'superseded')),
                parent_revision_id  TEXT,
                activated_at        TEXT,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (parent_revision_id)
                    REFERENCES visual_provider_revisions(revision_id)
                    ON DELETE SET NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_vpr_active
                ON visual_provider_revisions (provider_id, scope_type, scope_id)
                WHERE status = 'active';
            CREATE INDEX IF NOT EXISTS idx_vpr_provider ON visual_provider_revisions (provider_id);
            CREATE INDEX IF NOT EXISTS idx_vpr_scope ON visual_provider_revisions (scope_type, scope_id);
            CREATE INDEX IF NOT EXISTS idx_vpr_status ON visual_provider_revisions (status);

            CREATE TABLE IF NOT EXISTS visual_generation_profile_revisions (
                revision_id         TEXT PRIMARY KEY,
                project_id          TEXT NOT NULL,
                content             TEXT NOT NULL,
                content_hash        TEXT NOT NULL,
                visual_input_policy TEXT NOT NULL DEFAULT 'allow_t2va_fallback',
                status              TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'active', 'superseded')),
                parent_revision_id  TEXT,
                created_by          TEXT NOT NULL,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
                FOREIGN KEY (parent_revision_id)
                    REFERENCES visual_generation_profile_revisions(revision_id)
                    ON DELETE SET NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_vgpr_active
                ON visual_generation_profile_revisions (project_id)
                WHERE status = 'active';
            CREATE INDEX IF NOT EXISTS idx_vgpr_status ON visual_generation_profile_revisions (status);

            CREATE TABLE IF NOT EXISTS visual_task_contracts (
                task_id             TEXT PRIMARY KEY,
                visual_stage        TEXT NOT NULL DEFAULT 'UNROUTED',
                purpose             TEXT NOT NULL,
                operation           TEXT NOT NULL,
                task_type           TEXT NOT NULL,
                prompt              TEXT,
                reference_list      TEXT,
                output_contract     TEXT,
                technical_checks    TEXT,
                review_checklist    TEXT,
                continuity_constraints TEXT,
                compiler_identity_json TEXT,
                visual_bible_revision_id TEXT,
                provider_id         TEXT,
                provider_revision_id TEXT,
                routing_snapshot_json TEXT,
                content_hash        TEXT,
                dependency_hash     TEXT,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
                FOREIGN KEY (visual_bible_revision_id)
                    REFERENCES visual_bible_revisions(revision_id)
                    ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_vtc_stage ON visual_task_contracts (visual_stage);
            CREATE INDEX IF NOT EXISTS idx_vtc_purpose ON visual_task_contracts (purpose);
            CREATE INDEX IF NOT EXISTS idx_vtc_task_type ON visual_task_contracts (task_type);
            CREATE INDEX IF NOT EXISTS idx_vtc_provider ON visual_task_contracts (provider_id);
            CREATE INDEX IF NOT EXISTS idx_vtc_bible ON visual_task_contracts (visual_bible_revision_id);

            CREATE TABLE IF NOT EXISTS visual_result_manifests (
                manifest_id         TEXT PRIMARY KEY,
                task_id             TEXT NOT NULL,
                content             TEXT NOT NULL,
                content_hash        TEXT NOT NULL,
                file_hash           TEXT,
                status              TEXT NOT NULL DEFAULT 'pending',
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_vrm_task ON visual_result_manifests (task_id);
            CREATE INDEX IF NOT EXISTS idx_vrm_status ON visual_result_manifests (status);

            CREATE TABLE IF NOT EXISTS visual_provider_executions (
                execution_id        TEXT PRIMARY KEY,
                attempt_id          TEXT NOT NULL,
                task_id             TEXT NOT NULL,
                provider_revision_id TEXT NOT NULL,
                status              TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
                result_manifest_id  TEXT,
                started_at          TEXT,
                completed_at        TEXT,
                error               TEXT,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
                FOREIGN KEY (provider_revision_id)
                    REFERENCES visual_provider_revisions(revision_id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (result_manifest_id)
                    REFERENCES visual_result_manifests(manifest_id)
                    ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_vpe_attempt ON visual_provider_executions (attempt_id);
            CREATE INDEX IF NOT EXISTS idx_vpe_task ON visual_provider_executions (task_id);
            CREATE INDEX IF NOT EXISTS idx_vpe_status ON visual_provider_executions (status);

            CREATE TABLE IF NOT EXISTS visual_exchange_executions (
                execution_id        TEXT PRIMARY KEY,
                task_id             TEXT NOT NULL,
                provider_revision_id TEXT NOT NULL,
                status              TEXT NOT NULL DEFAULT 'exported'
                    CHECK (status IN ('exported', 'awaiting_result', 'result_imported', 'cancelled', 'expired')),
                package_json        TEXT,
                result_manifest_id  TEXT,
                exchanged_at        TEXT,
                created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
                FOREIGN KEY (provider_revision_id)
                    REFERENCES visual_provider_revisions(revision_id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (result_manifest_id)
                    REFERENCES visual_result_manifests(manifest_id)
                    ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_vee_task ON visual_exchange_executions (task_id);
            CREATE INDEX IF NOT EXISTS idx_vee_status ON visual_exchange_executions (status);
        """)

        # -- 2. Rebuild attempts to add attempt_kind + CHECK --------------
        # SQLite cannot ADD a table-level CHECK via ALTER, so we rebuild.
        cols = self.conn.execute("PRAGMA table_info(attempts)").fetchall()
        col_names = {c[1] for c in cols}
        if "attempt_kind" not in col_names:
            self.conn.executescript("""
                CREATE TABLE attempts_new (
                    attempt_id      TEXT PRIMARY KEY,
                    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
                    idempotency_key TEXT NOT NULL,
                    workflow_id     TEXT,
                    attempt_kind    TEXT NOT NULL DEFAULT 'workflow'
                        CHECK (attempt_kind IN ('workflow', 'visual_managed')),
                    params          TEXT NOT NULL DEFAULT '{}',
                    content_hash    TEXT NOT NULL,
                    dependency_hash TEXT NOT NULL,
                    params_hash     TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'PREPARED',
                    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    machine_id                  TEXT,
                    environment_snapshot_id     TEXT,
                    execution_environment_hash  TEXT,
                    CHECK (
                        (attempt_kind = 'workflow')
                        OR (attempt_kind = 'visual_managed' AND workflow_id IS NULL)
                    )
                );
                INSERT INTO attempts_new (
                    attempt_id, task_id, idempotency_key, workflow_id,
                    params, content_hash, dependency_hash, params_hash,
                    status, created_at, updated_at,
                    machine_id, environment_snapshot_id, execution_environment_hash
                )
                SELECT
                    attempt_id, task_id, idempotency_key, workflow_id,
                    params, content_hash, dependency_hash, params_hash,
                    status, created_at, updated_at,
                    machine_id, environment_snapshot_id, execution_environment_hash
                FROM attempts;
                DROP TABLE attempts;
                ALTER TABLE attempts_new RENAME TO attempts;
            """)
            # Recreate attempts indexes
            self.conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);
                CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status);
            """)

        # -- 3. Rebuild assets to add type CHECK, remap legacy types ------
        # Legacy visual types (character_map, scene_map, start_frame,
        # end_frame, image_edit) → 'image' with purpose stashed in metadata.
        # Also: task_id made nullable (character sheets aren't tied to a task).
        self.conn.executescript("""
            CREATE TABLE assets_new (
                asset_id        TEXT PRIMARY KEY,
                task_id         TEXT REFERENCES tasks(task_id),
                attempt_id      TEXT REFERENCES attempts(attempt_id),
                asset_type      TEXT NOT NULL
                    CHECK (asset_type IN ('image', 'video', 'audio', 'subtitle', 'document')),
                file_path       TEXT NOT NULL,
                file_hash       TEXT,
                file_size       INTEGER,
                mime_type       TEXT,
                width           INTEGER,
                height          INTEGER,
                duration        REAL,
                frame_count     INTEGER,
                content_hash    TEXT,
                metadata        TEXT NOT NULL DEFAULT '{}',
                created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
        """)
        # Migrate rows, remapping legacy types
        rows = self.conn.execute(
            "SELECT asset_id, task_id, attempt_id, asset_type, file_path, file_hash, "
            "file_size, mime_type, width, height, duration, frame_count, content_hash, "
            "metadata, created_at, updated_at FROM assets"
        ).fetchall()
        allowed = {"image", "video", "audio", "subtitle", "document"}
        for r in rows:
            (asset_id, task_id, attempt_id, asset_type, file_path, file_hash,
             file_size, mime_type, width, height, duration, frame_count, content_hash,
             metadata, created_at, updated_at) = r
            if asset_type not in allowed:
                # Remap to 'image' and stash legacy purpose in metadata
                try:
                    meta = json.loads(metadata) if metadata else {}
                except (json.JSONDecodeError, TypeError):
                    meta = {}
                meta["legacy_visual_purpose"] = asset_type
                asset_type = "image"
                metadata = json.dumps(meta, ensure_ascii=False)
            self.conn.execute(
                "INSERT INTO assets_new VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (asset_id, task_id, attempt_id, asset_type, file_path, file_hash,
                 file_size, mime_type, width, height, duration, frame_count, content_hash,
                 metadata, created_at, updated_at),
            )
        self.conn.executescript("""
            DROP TABLE assets;
            ALTER TABLE assets_new RENAME TO assets;
            CREATE INDEX IF NOT EXISTS idx_assets_task ON assets(task_id);
            CREATE INDEX IF NOT EXISTS idx_assets_attempt ON assets(attempt_id);
            CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
        """)

        self.conn.execute("PRAGMA user_version = 10")

    @property
    def schema_version(self) -> int:
        return self.conn.execute("PRAGMA user_version").fetchone()[0]

    @contextmanager
    def transaction(self):
        """Execute operations in a transaction.

        Commits on success, rolls back on exception.
        """
        self.conn.execute("BEGIN")
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, seq: list) -> sqlite3.Cursor:
        return self.conn.executemany(sql, seq)

    def fetchone(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()
