"""Wave 1-C: fault injection + idempotency tests.

C1: Repeated operations (idempotency)
C3: Filesystem edge cases (long path, Chinese path, spaces)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lfo.assembly.schema import AssemblyClip, AssemblyInputSnapshot
from lfo.core.database import Database
from lfo.services.editorial_service import EditorialService
from lfo.services.media_service import MediaService, SelectedClipAsset, StreamSignature
from lfo.services.srt_generator import SRTCue, SRTGenerator
from lfo.storyboard.storyboard import Beat, Panel, ProjectInfo, Storyboard


@pytest.fixture
def db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", ("proj-1", "Test"))
    db.execute("INSERT INTO tasks (task_id, project_id, task_type, status) VALUES (?, ?, ?, ?)",
               ("task-1", "proj-1", "h3_i2v", "SUCCEEDED"))
    db.execute("INSERT INTO assets (asset_id, task_id, asset_type, file_path, file_hash, content_hash, frame_count) "
               "VALUES (?, ?, ?, ?, ?, ?, ?)",
               ("norm-1", "task-1", "video", "/tmp/norm.mp4", "fh", "ch", 120))
    return db


@pytest.fixture
def media_service(db, tmp_path) -> MediaService:
    return MediaService(db, ffmpeg_path="/usr/bin/ffmpeg", ffprobe_path="/usr/bin/ffprobe",
                       output_dir=str(tmp_path / "media"))


def _fake_sig(file_path="/tmp/fake.mp4"):
    return StreamSignature(
        file_path=file_path, has_video=True, video_codec="h264",
        video_width=1080, video_height=1920, video_fps=24.0,
        has_audio=True, audio_codec="aac", audio_sample_rate=48000,
        audio_channels=2, duration_sec=2.0)


def _render_clip(svc, clip_id, fake_file, tmp_path):
    """Helper to render a clip with fully mocked media + QC."""
    with patch.object(MediaService, "create_selected_clip",
                      return_value=SelectedClipAsset(
                          asset_id="x", file_path=str(fake_file),
                          in_frame=0, out_frame_exclusive=50,
                          duration_sec=2.0, frame_count=50)), \
         patch.object(MediaService, "get_stream_signature", return_value=_fake_sig(str(fake_file))):
        return svc.render_selected_clip(clip_id)


class TestIdempotency:
    """C1: Repeated operations should be safe."""

    def test_create_selection_creates_new_revision_each_time(self, db, media_service):
        svc = EditorialService(db, media_service=media_service)
        s1 = svc.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        s2 = svc.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        assert s1.revision == 1
        assert s2.revision == 2
        assert s1.selected_clip_id != s2.selected_clip_id

    def test_approve_already_approved_raises(self, db, media_service, tmp_path):
        svc = EditorialService(db, media_service=media_service)
        clip = svc.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        fake_file = tmp_path / "clip.mp4"
        fake_file.write_bytes(b"data")

        rendered = _render_clip(svc, clip.selected_clip_id, fake_file, tmp_path)
        approved = svc.approve_selected_clip(rendered.selected_clip_id)
        assert approved.status == "approved"

        with pytest.raises(ValueError, match="Cannot approve"):
            svc.approve_selected_clip(clip.selected_clip_id)

    def test_reject_already_rejected_raises(self, db, media_service, tmp_path):
        svc = EditorialService(db, media_service=media_service)
        clip = svc.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        fake_file = tmp_path / "clip.mp4"
        fake_file.write_bytes(b"data")

        rendered = _render_clip(svc, clip.selected_clip_id, fake_file, tmp_path)
        svc.reject_selected_clip(rendered.selected_clip_id, "reason")

        with pytest.raises(ValueError, match="Cannot reject"):
            svc.reject_selected_clip(clip.selected_clip_id, "reason")

    def test_render_already_rendered_raises(self, db, media_service, tmp_path):
        """Rendering an already-rendered clip (awaiting_review) should raise."""
        svc = EditorialService(db, media_service=media_service)
        clip = svc.create_selection("proj-1", "shot-1", "norm-1", 0, 50)
        fake_file = tmp_path / "clip.mp4"
        fake_file.write_bytes(b"data")

        _render_clip(svc, clip.selected_clip_id, fake_file, tmp_path)
        with pytest.raises(ValueError, match="Cannot render"):
            _render_clip(svc, clip.selected_clip_id, fake_file, tmp_path)


class TestFilesystemEdgeCases:
    """C3: Filesystem edge cases."""

    def _set_asset_path(self, db, path):
        row = db.fetchone("SELECT file_path FROM assets WHERE asset_id = ?", ("norm-1",))
        db.execute("UPDATE assets SET file_path = ? WHERE asset_id = ?", (path, "norm-1"))
        return row[0]

    def test_long_path_handling(self, db, media_service, tmp_path):
        long_name = "a" * 150 + ".mp4"
        fake_file = tmp_path / long_name
        fake_file.write_bytes(b"data")
        original = self._set_asset_path(db, str(fake_file))

        with patch("subprocess.run") as mock_run, \
             patch.object(MediaService, "get_stream_signature", return_value=_fake_sig(str(fake_file))):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = media_service.create_selected_clip("norm-1", 0, 50)

        assert result.file_path
        self._set_asset_path(db, original)

    def test_chinese_path_handling(self, db, media_service, tmp_path):
        chinese_name = "测试视频_中文路径.mp4"
        fake_file = tmp_path / chinese_name
        fake_file.write_bytes(b"data")
        original = self._set_asset_path(db, str(fake_file))

        with patch("subprocess.run") as mock_run, \
             patch.object(MediaService, "get_stream_signature", return_value=_fake_sig(str(fake_file))):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = media_service.create_selected_clip("norm-1", 0, 50)

        assert result.file_path
        self._set_asset_path(db, original)

    def test_path_with_spaces(self, db, media_service, tmp_path):
        space_name = "my video file with spaces.mp4"
        fake_file = tmp_path / space_name
        fake_file.write_bytes(b"data")
        original = self._set_asset_path(db, str(fake_file))

        with patch("subprocess.run") as mock_run, \
             patch.object(MediaService, "get_stream_signature", return_value=_fake_sig(str(fake_file))):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = media_service.create_selected_clip("norm-1", 0, 50)

        assert result.file_path
        self._set_asset_path(db, original)


class TestSRTEdgeCases:
    """C1/C3: SRT generation edge cases."""

    def test_srt_with_no_narration_produces_no_cues(self, db, tmp_path):
        sb = Storyboard(
            project=ProjectInfo(project_id="proj-1"),
            beats=[
                Beat(beat_id="beat_001", sequence=1, scene_id="s1", dialogue=""),
                Beat(beat_id="beat_002", sequence=2, scene_id="s1", dialogue=""),
            ],
            panels=[
                Panel(panel_id="panel_001", sequence=1, beat_ids=["beat_001"]),
                Panel(panel_id="panel_002", sequence=2, beat_ids=["beat_002"]),
            ],
        )
        snap = AssemblyInputSnapshot(
            edl_id="edl-1", project_id="proj-1",
            clips=[AssemblyClip(shot_id="panel_001", selected_clip_id="c1", output_asset_id="a1",
                                file_path="/tmp/c1.mp4", duration_sec=3.0),
                   AssemblyClip(shot_id="panel_002", selected_clip_id="c2", output_asset_id="a2",
                                file_path="/tmp/c2.mp4", duration_sec=3.0)],
        )
        gen = SRTGenerator(db, output_dir=str(tmp_path / "srt"))
        result = gen.generate("edl-1", sb, snap)
        assert not result.success
        assert "No subtitle text" in result.error

    def test_srt_cue_formatting(self):
        cue = SRTCue(index=1, start_sec=0.0, end_sec=5.5, text="Test")
        srt = cue.to_srt()
        assert "00:00:00,000 --> 00:00:05,500" in srt

    def test_srt_with_mixed_narration(self, db, tmp_path):
        sb = Storyboard(
            project=ProjectInfo(project_id="proj-1"),
            beats=[
                Beat(beat_id="beat_001", sequence=1, scene_id="s1", dialogue="有字幕"),
                Beat(beat_id="beat_002", sequence=2, scene_id="s1", dialogue=""),
                Beat(beat_id="beat_003", sequence=3, scene_id="s1", dialogue="也有字幕"),
            ],
            panels=[
                Panel(panel_id="panel_001", sequence=1, beat_ids=["beat_001"]),
                Panel(panel_id="panel_002", sequence=2, beat_ids=["beat_002"]),
                Panel(panel_id="panel_003", sequence=3, beat_ids=["beat_003"]),
            ],
        )
        snap = AssemblyInputSnapshot(
            edl_id="edl-1", project_id="proj-1",
            clips=[
                AssemblyClip(shot_id="panel_001", selected_clip_id="c1", output_asset_id="a1",
                             file_path="/tmp/c1.mp4", duration_sec=3.0),
                AssemblyClip(shot_id="panel_002", selected_clip_id="c2", output_asset_id="a2",
                             file_path="/tmp/c2.mp4", duration_sec=2.0),
                AssemblyClip(shot_id="panel_003", selected_clip_id="c3", output_asset_id="a3",
                             file_path="/tmp/c3.mp4", duration_sec=4.0),
            ],
        )
        gen = SRTGenerator(db, output_dir=str(tmp_path / "srt"))
        result = gen.generate("edl-1", sb, snap)
        assert result.success
        assert result.cue_count == 2
