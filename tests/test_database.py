"""Tests for LFO SQLite Database layer."""

import pytest

from lfo.core.database import SCHEMA_VERSION, Database


class TestDatabaseCreation:
    def test_in_memory_db(self):
        db = Database()
        db.init_schema()
        assert db.schema_version == SCHEMA_VERSION
        db.close()

    def test_file_db(self, tmp_path):
        db_path = tmp_path / "test.lfo.db"
        db = Database(db_path)
        db.init_schema()
        assert db_path.exists()
        db.close()

    def test_file_db_wal_mode(self, tmp_path):
        db_path = tmp_path / "test.lfo.db"
        db = Database(db_path)
        db.init_schema()
        wal = db.fetchone("PRAGMA journal_mode")
        assert wal[0] == "wal"
        db.close()

    def test_foreign_keys_on(self):
        db = Database()
        db.init_schema()
        fk = db.fetchone("PRAGMA foreign_keys")
        assert fk[0] == 1
        db.close()

    def test_all_tables_exist(self):
        db = Database()
        db.init_schema()
        tables = db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = {r[0] for r in tables}
        expected = {
            "tasks", "attempts", "submission_journal", "provider_jobs",
            "approvals", "assets", "asset_relations", "invalidations",
            "qc_reports", "events", "task_leases",
            "environment_snapshots", "preflights", "projects",
            "asset_bindings", "asset_reviews", "visual_bible_revisions",
            "task_materializations", "selected_clips",
            "edit_decision_lists",
        }
        assert expected.issubset(table_names)
        db.close()


class TestTaskMaterializationsTable:
    """Tests for v6 task_materializations table."""

    def test_table_exists_and_has_columns(self):
        db = Database()
        db.init_schema()
        cols = db.fetchall(
            "PRAGMA table_info(task_materializations)"
        )
        col_names = {c[1] for c in cols}
        expected_cols = {
            "materialization_id", "task_id", "project_id", "workflow_id",
            "params", "params_hash", "idempotency_key",
            "environment_snapshot_id", "environment_execution_hash",
            "binding_snapshot", "prompt_snapshot", "created_at", "updated_at",
        }
        assert expected_cols.issubset(col_names)
        db.close()

    def test_insert_and_retrieve(self):
        db = Database()
        db.init_schema()
        # Insert a task first (FK requirement)
        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("task1", "proj1", "h3_i2v", "WAITING_ASSETS", "2026-01-01T00:00:00Z"),
        )
        db.execute(
            """INSERT INTO task_materializations
               (materialization_id, task_id, project_id, workflow_id,
                params_hash, idempotency_key, environment_snapshot_id,
                environment_execution_hash, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("mat1", "task1", "proj1", "h3_standard_i2v",
             "phash123", "idem456", "snap789", "ehash012",
             "2026-01-01T00:00:00Z"),
        )
        row = db.fetchone(
            "SELECT params_hash, idempotency_key FROM task_materializations "
            "WHERE materialization_id = ?",
            ("mat1",),
        )
        assert row is not None
        assert row[0] == "phash123"
        assert row[1] == "idem456"
        db.close()

    def test_foreign_key_to_tasks(self):
        db = Database()
        db.init_schema()
        with pytest.raises(Exception):
            db.execute(
                """INSERT INTO task_materializations
                   (materialization_id, task_id, project_id, workflow_id,
                    params_hash, idempotency_key, environment_snapshot_id,
                    environment_execution_hash, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("mat1", "nonexistent", "proj1", "wf1",
                 "phash", "idem", "snap", "ehash",
                 "2026-01-01T00:00:00Z"),
            )
        db.close()

    def test_index_on_task_id(self):
        db = Database()
        db.init_schema()
        indexes = db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_materializations%'"
        )
        idx_names = {r[0] for r in indexes}
        assert "idx_materializations_task" in idx_names
        assert "idx_materializations_project" in idx_names
        assert "idx_materializations_idempotency" in idx_names
        db.close()


class TestSelectedClipsTable:
    """Tests for v7 selected_clips table."""

    def test_table_exists_and_has_columns(self):
        db = Database()
        db.init_schema()
        cols = db.fetchall("PRAGMA table_info(selected_clips)")
        col_names = {c[1] for c in cols}
        expected_cols = {
            "selected_clip_id", "project_id", "shot_id",
            "normalized_asset_id", "output_asset_id",
            "selected_in_frame", "selected_out_frame_exclusive",
            "fps_num", "fps_den",
            "render_policy_id", "revision", "status",
            "content_hash", "dependency_hash",
            "created_at", "approved_at", "superseded_by",
        }
        assert expected_cols.issubset(col_names)
        db.close()

    def test_current_approved_partial_index(self):
        db = Database()
        db.init_schema()
        db.execute(
            "INSERT INTO projects (project_id, name) VALUES (?, ?)",
            ("proj1", "Test"),
        )
        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("task1", "proj1", "h3_i2v", "SUCCEEDED", "2026-01-01T00:00:00Z"),
        )
        db.execute(
            "INSERT INTO assets (asset_id, task_id, asset_type, file_path, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("norm1", "task1", "video", "/tmp/norm.mp4", "2026-01-01T00:00:00Z"),
        )
        # First approved clip — should succeed
        db.execute(
            """INSERT INTO selected_clips
               (selected_clip_id, project_id, shot_id, normalized_asset_id,
                selected_in_frame, selected_out_frame_exclusive,
                fps_num, fps_den, render_policy_id, revision, status,
                content_hash, dependency_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("clip1", "proj1", "shot1", "norm1",
             0, 120, 24, 1, "selected_clip_v1", 1, "approved",
             "ch1", "dh1", "2026-01-01T00:00:00Z"),
        )
        # Second approved clip for same shot — should fail (partial unique index)
        with pytest.raises(Exception):
            db.execute(
                """INSERT INTO selected_clips
                   (selected_clip_id, project_id, shot_id, normalized_asset_id,
                    selected_in_frame, selected_out_frame_exclusive,
                    fps_num, fps_den, render_policy_id, revision, status,
                    content_hash, dependency_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("clip2", "proj1", "shot1", "norm1",
                 0, 100, 24, 1, "selected_clip_v1", 2, "approved",
                 "ch2", "dh2", "2026-01-01T00:00:00Z"),
            )
        db.close()

    def test_revision_unique_constraint(self):
        db = Database()
        db.init_schema()
        db.execute(
            "INSERT INTO projects (project_id, name) VALUES (?, ?)",
            ("proj1", "Test"),
        )
        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("task1", "proj1", "h3_i2v", "SUCCEEDED", "2026-01-01T00:00:00Z"),
        )
        db.execute(
            "INSERT INTO assets (asset_id, task_id, asset_type, file_path, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("norm1", "task1", "video", "/tmp/norm.mp4", "2026-01-01T00:00:00Z"),
        )
        db.execute(
            """INSERT INTO selected_clips
               (selected_clip_id, project_id, shot_id, normalized_asset_id,
                selected_in_frame, selected_out_frame_exclusive,
                fps_num, fps_den, render_policy_id, revision, status,
                content_hash, dependency_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("clip1", "proj1", "shot1", "norm1",
             0, 120, 24, 1, "selected_clip_v1", 1, "draft",
             "ch1", "dh1", "2026-01-01T00:00:00Z"),
        )
        # Same revision for same shot — should fail
        with pytest.raises(Exception):
            db.execute(
                """INSERT INTO selected_clips
                   (selected_clip_id, project_id, shot_id, normalized_asset_id,
                    selected_in_frame, selected_out_frame_exclusive,
                    fps_num, fps_den, render_policy_id, revision, status,
                    content_hash, dependency_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("clip2", "proj1", "shot1", "norm1",
                 0, 100, 24, 1, "selected_clip_v1", 1, "draft",
                 "ch2", "dh2", "2026-01-01T00:00:00Z"),
            )
        db.close()


class TestTransactions:
    def test_transaction_commits(self):
        db = Database()
        db.init_schema()
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, project_id, task_type, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("t1", "proj1", "keyframe", "PLANNED", "2026-01-01T00:00:00Z"),
            )
        # Data should be committed
        row = db.fetchone("SELECT task_id FROM tasks WHERE task_id = 't1'")
        assert row is not None
        assert row[0] == "t1"
        db.close()

    def test_transaction_rollback(self):
        db = Database()
        db.init_schema()
        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("t1", "proj1", "keyframe", "PLANNED", "2026-01-01T00:00:00Z"),
        )
        try:
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO tasks (task_id, project_id, task_type, status, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("t2", "proj1", "keyframe", "PLANNED", "2026-01-01T00:00:00Z"),
                )
                raise ValueError("forced error")
        except ValueError:
            pass
        # t2 should not exist, t1 should still be there
        assert db.fetchone("SELECT task_id FROM tasks WHERE task_id = 't2'") is None
        assert db.fetchone("SELECT task_id FROM tasks WHERE task_id = 't1'") is not None
        db.close()

    def test_foreign_key_enforcement(self):
        db = Database()
        db.init_schema()
        # Inserting an attempt with non-existent task should fail
        with pytest.raises(Exception):
            db.execute(
                "INSERT INTO attempts (attempt_id, task_id, idempotency_key, "
                "content_hash, dependency_hash, params_hash, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("att1", "nonexistent", "key1", "h1", "h2", "h3", "2026-01-01T00:00:00Z"),
            )
        db.close()
