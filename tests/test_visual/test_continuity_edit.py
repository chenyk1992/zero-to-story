"""Tests for Level 1 continuity edit (Task 12).

Flow: end frame -> visual.edit task -> import/QC/approve -> new start_frame
binding for next shot.
"""
from __future__ import annotations

import json

from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.services.continuity_service import ContinuityService
from lfo.visual.stages import VisualStage


def _fresh_db() -> Database:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    return db


def _create_end_frame(db: Database) -> str:
    """Create a video task + asset to act as the source end frame."""
    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status,
                             dependencies, idempotency_key,
                             created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("vid-task-1", "proj1", "h3_i2v", TaskStatus.APPROVED.value,
         "[]", "ek-1", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    db.execute(
        """INSERT INTO assets (asset_id, task_id, asset_type, file_path,
                               content_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("end-frame-1", "vid-task-1", "image", "/tmp/end_frame.png",
         "hash-abc", "2026-01-01T00:00:00Z"),
    )
    return "end-frame-1"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_continuity_edit_returns_task_id():
    db = _fresh_db()
    frame_id = _create_end_frame(db)
    svc = ContinuityService(db)

    tid = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-1",
        target_shot_id="shot-2",
        end_frame_asset_id=frame_id,
    )
    assert tid is not None
    db.close()


def test_continuity_edit_creates_visual_edit_task():
    db = _fresh_db()
    frame_id = _create_end_frame(db)
    svc = ContinuityService(db)

    tid = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-1",
        target_shot_id="shot-2",
        end_frame_asset_id=frame_id,
    )

    # Verify the task row
    row = db.fetchone(
        "SELECT task_type, status FROM tasks WHERE task_id = ?", (tid,)
    )
    assert row["task_type"] == "visual.edit"
    assert row["status"] == TaskStatus.PLANNED.value

    # Verify the contract
    row = db.fetchone(
        "SELECT purpose, operation, task_type, visual_stage "
        "FROM visual_task_contracts WHERE task_id = ?",
        (tid,),
    )
    assert row["purpose"] == "continuity_edit"
    assert row["operation"] == "image_edit"
    assert row["task_type"] == "visual.edit"
    assert row["visual_stage"] == VisualStage.UNROUTED.value
    db.close()


def test_continuity_edit_has_end_frame_reference():
    db = _fresh_db()
    frame_id = _create_end_frame(db)
    svc = ContinuityService(db)

    tid = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-1",
        target_shot_id="shot-2",
        end_frame_asset_id=frame_id,
    )

    row = db.fetchone(
        "SELECT reference_list FROM visual_task_contracts WHERE task_id = ?",
        (tid,),
    )
    refs = json.loads(row["reference_list"])
    assert len(refs) == 1
    assert refs[0]["asset_id"] == frame_id
    db.close()


def test_continuity_edit_creates_continuity_record():
    db = _fresh_db()
    frame_id = _create_end_frame(db)
    svc = ContinuityService(db)

    tid = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-1",
        target_shot_id="shot-2",
        end_frame_asset_id=frame_id,
    )

    row = db.fetchone(
        "SELECT shot_id, source_shot_id, end_frame_asset_id, "
        "state_json, status FROM continuity_states WHERE "
        "project_id = ? AND shot_id = ?",
        ("proj1", "shot-2"),
    )
    assert row is not None
    assert row["source_shot_id"] == "shot-1"
    assert row["end_frame_asset_id"] == frame_id
    state = json.loads(row["state_json"])
    assert state["edit_task_id"] == tid
    assert state["kind"] == "continuity_edit"
    assert row["status"] == "pending"
    db.close()


def test_continuity_edit_with_prompt():
    db = _fresh_db()
    frame_id = _create_end_frame(db)
    svc = ContinuityService(db)

    prompt = {"instruction": "Make the background darker", "style": "cinematic"}
    tid = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-1",
        target_shot_id="shot-2",
        end_frame_asset_id=frame_id,
        prompt=prompt,
    )

    row = db.fetchone(
        "SELECT prompt FROM visual_task_contracts WHERE task_id = ?",
        (tid,),
    )
    stored_prompt = json.loads(row["prompt"])
    assert stored_prompt == prompt
    db.close()


def test_continuity_edit_multiple_shots():
    db = _fresh_db()
    frame_id = _create_end_frame(db)
    svc = ContinuityService(db)

    tid1 = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-1",
        target_shot_id="shot-2",
        end_frame_asset_id=frame_id,
    )
    tid2 = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-2",
        target_shot_id="shot-3",
        end_frame_asset_id=frame_id,
    )

    assert tid1 != tid2
    rows = db.fetchall(
        "SELECT shot_id FROM continuity_states WHERE project_id = ? "
        "ORDER BY shot_id",
        ("proj1",),
    )
    assert len(rows) == 2
    assert rows[0]["shot_id"] == "shot-2"
    assert rows[1]["shot_id"] == "shot-3"
    db.close()
