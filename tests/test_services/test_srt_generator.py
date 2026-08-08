"""Tests for SRTGenerator."""
from __future__ import annotations

import os

import pytest

from lfo.assembly.schema import AssemblyClip, AssemblyInputSnapshot
from lfo.core.database import Database
from lfo.services.srt_generator import SRTCue, SRTGenerator
from lfo.storyboard.storyboard import Beat, Panel, ProjectInfo, Storyboard
from tests.helpers.storyboard_fixtures import make_panel_storyboard


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
    return db


@pytest.fixture
def storyboard() -> Storyboard:
    return make_panel_storyboard(
        3,
        project_id="proj-1",
        title="Test",
        dialogue_fn=lambda n: "第一段旁白" if n == 1 else ("第二段旁白" if n == 2 else ""),
    )


@pytest.fixture
def snapshot() -> AssemblyInputSnapshot:
    return AssemblyInputSnapshot(
        edl_id="edl-1",
        project_id="proj-1",
        clips=[
            AssemblyClip(shot_id="panel_001", selected_clip_id="c1", output_asset_id="a1",
                         file_path="/tmp/c1.mp4", duration_sec=5.0),
            AssemblyClip(shot_id="panel_002", selected_clip_id="c2", output_asset_id="a2",
                         file_path="/tmp/c2.mp4", duration_sec=5.0),
            AssemblyClip(shot_id="panel_003", selected_clip_id="c3", output_asset_id="a3",
                         file_path="/tmp/c3.mp4", duration_sec=3.0),
        ],
    )


class TestSRTCue:
    def test_time_formatting(self):
        cue = SRTCue(index=1, start_sec=0.0, end_sec=5.5, text="Hello")
        assert cue.to_srt_time(0.0) == "00:00:00,000"
        assert cue.to_srt_time(5.5) == "00:00:05,500"
        assert cue.to_srt_time(3661.123) == "01:01:01,123"

    def test_srt_format(self):
        cue = SRTCue(index=1, start_sec=0.0, end_sec=5.0, text="Test subtitle")
        srt = cue.to_srt()
        assert "1\n" in srt
        assert "00:00:00,000 --> 00:00:05,000" in srt
        assert "Test subtitle" in srt


class TestSRTGenerator:
    def test_generate_creates_srt_file(self, db, storyboard, snapshot, tmp_path):
        gen = SRTGenerator(db=db, output_dir=str(tmp_path / "srt"))
        result = gen.generate("edl-1", storyboard, snapshot)

        assert result.success
        assert result.cue_count == 2
        assert result.file_path.endswith(".srt")
        assert os.path.exists(result.file_path)

        with open(result.file_path, encoding="utf-8") as f:
            content = f.read()

        assert "第一段旁白" in content
        assert "第二段旁白" in content
        assert "00:00:00,000 --> 00:00:05,000" in content
        assert "00:00:05,000 --> 00:00:10,000" in content

    def test_generate_no_clips(self, db, storyboard, tmp_path):
        gen = SRTGenerator(db=db, output_dir=str(tmp_path / "srt"))
        empty_snapshot = AssemblyInputSnapshot(edl_id="edl-1", project_id="proj-1")
        result = gen.generate("edl-1", storyboard, empty_snapshot)
        assert not result.success
        assert "No clips" in result.error

    def test_generate_no_narration(self, db, tmp_path):
        gen = SRTGenerator(db=db, output_dir=str(tmp_path / "srt"))
        sb = Storyboard(
            project=ProjectInfo(project_id="proj-1"),
            beats=[Beat(beat_id="beat_001", sequence=1, scene_id="s1", dialogue="")],
            panels=[Panel(panel_id="panel_001", sequence=1, beat_ids=["beat_001"])],
        )
        snap = AssemblyInputSnapshot(
            edl_id="edl-1",
            project_id="proj-1",
            clips=[AssemblyClip(shot_id="panel_001", selected_clip_id="c1", output_asset_id="a1",
                                file_path="/tmp/c1.mp4", duration_sec=5.0)],
        )
        result = gen.generate("edl-1", sb, snap)
        assert not result.success
        assert "No subtitle text" in result.error

    def test_register_srt_asset(self, db, storyboard, snapshot, tmp_path):
        db.execute(
            """INSERT INTO edit_decision_lists
               (edl_id, project_id, revision, content_json, content_hash,
                dependency_hash, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("edl-1", "proj-1", 1, "{}", "ch", "dh", "approved", "2026-01-01T00:00:00Z"),
        )

        gen = SRTGenerator(db=db, output_dir=str(tmp_path / "srt"))
        result = gen.generate("edl-1", storyboard, snapshot)

        asset_id = gen.register_srt_asset("edl-1", "proj-1", result.file_path, result.cue_count)
        assert asset_id != ""

        row = db.fetchone(
            "SELECT asset_type, metadata FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        assert row is not None
        assert row[0] == "subtitle"
        import json
        meta = json.loads(row[1])
        assert meta["cue_count"] == 2
