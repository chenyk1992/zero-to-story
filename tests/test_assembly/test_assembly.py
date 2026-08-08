"""Tests for AssemblyCompiler and AssemblyService."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from lfo.assembly.compiler import AssemblyCompiler
from lfo.assembly.schema import AssemblyClip, AssemblyInputSnapshot
from lfo.assembly.service import AssemblyService
from lfo.core.database import Database
from lfo.services.edl_service import EDLService


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        ("proj-1", "Test Project"),
    )
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
        ("task-1", "proj-1", "h3_i2v", "SUCCEEDED"),
    )
    # Normalized asset
    db.execute(
        """INSERT INTO assets (asset_id, task_id, asset_type, file_path, file_hash, content_hash, frame_count, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("norm-1", "task-1", "video", "/tmp/norm.mp4", "fh", "ch", 120,
         json.dumps({"fps": 24.0, "has_audio": True})),
    )
    # Output assets (selected clip results)
    db.execute(
        """INSERT INTO assets (asset_id, task_id, asset_type, file_path, file_hash, content_hash, duration, frame_count, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("clip-out-1", "task-1", "video", "/tmp/clip1.mp4", "fh2", "ch2", 5.0, 120,
         json.dumps({"fps": 24.0, "has_audio": True})),
    )
    db.execute(
        """INSERT INTO assets (asset_id, task_id, asset_type, file_path, file_hash, content_hash, duration, frame_count, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("clip-out-2", "task-1", "video", "/tmp/clip2.mp4", "fh3", "ch3", 5.0, 120,
         json.dumps({"fps": 24.0, "has_audio": True})),
    )
    # Selected clips
    db.execute(
        """INSERT INTO selected_clips
           (selected_clip_id, project_id, shot_id, normalized_asset_id,
            output_asset_id, selected_in_frame, selected_out_frame_exclusive,
            fps_num, fps_den, render_policy_id, revision, status,
            content_hash, dependency_hash, created_at, approved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "clip-1", "proj-1", "shot-1", "norm-1",
            "clip-out-1", 0, 120, 24, 1, "selected_clip_v1", 1, "approved",
            "ch", "dh", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z",
        ),
    )
    db.execute(
        """INSERT INTO selected_clips
           (selected_clip_id, project_id, shot_id, normalized_asset_id,
            output_asset_id, selected_in_frame, selected_out_frame_exclusive,
            fps_num, fps_den, render_policy_id, revision, status,
            content_hash, dependency_hash, created_at, approved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "clip-2", "proj-1", "shot-2", "norm-1",
            "clip-out-2", 0, 120, 24, 1, "selected_clip_v1", 1, "approved",
            "ch", "dh", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z",
        ),
    )
    return db


def _make_snapshot(db, tmp_path) -> AssemblyInputSnapshot:
    """Create a snapshot with real temp files."""
    f1 = tmp_path / "clip1.mp4"
    f2 = tmp_path / "clip2.mp4"
    f1.write_bytes(b"fake_clip_data_1")
    f2.write_bytes(b"fake_clip_data_2")
    db.execute("UPDATE assets SET file_path = ? WHERE asset_id = ?", (str(f1), "clip-out-1"))
    db.execute("UPDATE assets SET file_path = ? WHERE asset_id = ?", (str(f2), "clip-out-2"))
    return AssemblyInputSnapshot(
        edl_id="edl-1",
        project_id="proj-1",
        clips=[
            AssemblyClip(
                shot_id="shot-1",
                selected_clip_id="clip-1",
                output_asset_id="clip-out-1",
                file_path=str(f1),
                duration_sec=5.0,
                width=1080,
                height=1920,
                fps=24.0,
                has_audio=True,
            ),
            AssemblyClip(
                shot_id="shot-2",
                selected_clip_id="clip-2",
                output_asset_id="clip-out-2",
                file_path=str(f2),
                duration_sec=5.0,
                width=1080,
                height=1920,
                fps=24.0,
                has_audio=True,
            ),
        ],
        export_profile_id="vertical_h264_v1",
    )


class TestAssemblyCompiler:
    def test_assemble_empty_clips(self, db, tmp_path):
        compiler = AssemblyCompiler(db=db, ffmpeg_path="/usr/bin/ffmpeg", output_dir=str(tmp_path / "out"))
        result = compiler.assemble(AssemblyInputSnapshot(edl_id="edl-1", project_id="proj-1"))
        assert not result.success
        assert "No clips" in result.error

    def test_assemble_file_not_found(self, db, tmp_path):
        compiler = AssemblyCompiler(db=db, ffmpeg_path="/usr/bin/ffmpeg", output_dir=str(tmp_path / "out"))
        snap = AssemblyInputSnapshot(
            edl_id="edl-1",
            project_id="proj-1",
            clips=[AssemblyClip(shot_id="s1", selected_clip_id="c1", output_asset_id="a1",
                                file_path="/nonexistent.mp4")],
        )
        result = compiler.assemble(snap)
        assert not result.success
        assert "not found" in result.error

    def test_assemble_no_ffmpeg(self, db, tmp_path):
        fake_file = tmp_path / "fake.mp4"
        fake_file.write_bytes(b"data")
        snap = AssemblyInputSnapshot(
            edl_id="edl-1",
            project_id="proj-1",
            clips=[AssemblyClip(shot_id="s1", selected_clip_id="c1", output_asset_id="a1",
                                file_path=str(fake_file))],
        )
        compiler = AssemblyCompiler(db=db, ffmpeg_path="", output_dir=str(tmp_path / "out"))
        result = compiler.assemble(snap)
        assert not result.success
        assert "ffmpeg not found" in result.error

    def test_assemble_success(self, db, tmp_path):
        snapshot = _make_snapshot(db, tmp_path)
        output_dir = tmp_path / "out"
        output_dir.mkdir(exist_ok=True)
        compiler = AssemblyCompiler(
            db=db,
            ffmpeg_path="/usr/bin/ffmpeg",
            ffprobe_path="/usr/bin/ffprobe",
            output_dir=str(output_dir),
        )

        output_file = output_dir / "assembly_test.mp4"
        output_file.write_bytes(b"fake_assembly_output")

        def mock_run(cmd, **kwargs):
            m = MagicMock()
            if cmd[0].endswith("ffmpeg"):
                m.returncode = 0
                m.stdout = ""
                m.stderr = ""
            elif cmd[0].endswith("ffprobe"):
                m.returncode = 0
                m.stdout = json.dumps({
                    "format": {"duration": "10.0"},
                    "streams": [
                        {"codec_type": "video", "width": 1080, "height": 1920, "r_frame_rate": "24/1"},
                        {"codec_type": "audio", "codec_name": "aac"},
                    ],
                })
            return m

        with patch("subprocess.run", side_effect=mock_run):
            result = compiler.assemble(snapshot, "assembly_test.mp4")

        assert result.success
        assert result.output_file_path == str(output_file)
        assert result.duration_sec == 10.0


class TestAssemblyService:
    def test_build_from_edl_not_approved(self, db, tmp_path):
        edl = EDLService(db).create_edl("proj-1", ["shot-1"])
        svc = AssemblyService(db)
        result = svc.build_from_edl(edl.edl_id)
        assert not result.success
        assert "must be 'approved'" in result.error

    def test_build_from_edl_resolves_clips(self, db, tmp_path):
        # Create and approve EDL
        edl_svc = EDLService(db)
        edl = edl_svc.create_edl("proj-1", ["shot-1", "shot-2"])
        edl_svc.approve_edl(edl.edl_id)

        # Make sure output files exist and patch FFmpeg
        f1 = tmp_path / "clip1.mp4"
        f2 = tmp_path / "clip2.mp4"
        f1.write_bytes(b"data1")
        f2.write_bytes(b"data2")
        db.execute("UPDATE assets SET file_path = ? WHERE asset_id = ?", (str(f1), "clip-out-1"))
        db.execute("UPDATE assets SET file_path = ? WHERE asset_id = ?", (str(f2), "clip-out-2"))

        output_dir = tmp_path / "assembly"
        output_dir.mkdir(exist_ok=True)

        compiler = AssemblyCompiler(
            db=db,
            ffmpeg_path="/usr/bin/ffmpeg",
            ffprobe_path="/usr/bin/ffprobe",
            output_dir=str(output_dir),
        )

        def mock_run(cmd, **kwargs):
            m = MagicMock()
            if cmd[0].endswith("ffmpeg"):
                m.returncode = 0
                m.stdout = ""
                m.stderr = ""
            elif cmd[0].endswith("ffprobe"):
                m.returncode = 0
                m.stdout = json.dumps({
                    "format": {"duration": "10.0"},
                    "streams": [
                        {"codec_type": "video", "width": 1080, "height": 1920, "r_frame_rate": "24/1"},
                        {"codec_type": "audio", "codec_name": "aac"},
                    ],
                })
            return m

        original_exists = os.path.exists

        def fake_exists(path):
            if str(path).endswith(".mp4") and "assembly" in str(path):
                return True
            return original_exists(path)

        svc = AssemblyService(db, compiler=compiler)

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.path.exists", side_effect=fake_exists), \
             patch("os.path.getsize", return_value=1024):
            result = svc.build_from_edl(edl.edl_id)

        assert result.success
        assert result.output_asset_id != ""
        assert result.output_file_path.endswith(".mp4")
