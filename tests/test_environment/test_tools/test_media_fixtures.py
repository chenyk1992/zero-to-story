"""Tests for dynamic media fixture generation."""
from __future__ import annotations

import shutil

import pytest

from lfo.environment.tools.media_fixtures import (
    MediaFixture,
    generate_corrupted_media,
    generate_temp_fixture,
    generate_test_video,
)

requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="FFmpeg not installed"
)


@pytest.fixture
def ffmpeg_path():
    path = shutil.which("ffmpeg")
    if not path:
        pytest.skip("FFmpeg not installed")
    return path


@requires_ffmpeg
class TestGenerateTestVideo:
    def test_generate_creates_valid_file(self, tmp_path, ffmpeg_path):
        output = tmp_path / "test.mp4"
        fixture = generate_test_video(output_path=output, ffmpeg_path=ffmpeg_path)
        assert fixture.path.exists()
        assert fixture.path.stat().st_size > 0

    def test_generate_respects_dimensions(self, tmp_path, ffmpeg_path):
        output = tmp_path / "test_dims.mp4"
        fixture = generate_test_video(
            output_path=output, width=640, height=360, ffmpeg_path=ffmpeg_path
        )
        assert fixture.width == 640
        assert fixture.height == 360
        assert fixture.path.exists()

    def test_generate_without_audio(self, tmp_path, ffmpeg_path):
        output = tmp_path / "test_no_audio.mp4"
        fixture = generate_test_video(
            output_path=output, with_audio=False, ffmpeg_path=ffmpeg_path
        )
        assert fixture.has_audio is False
        assert fixture.sample_rate is None
        assert fixture.channels is None
        assert fixture.path.exists()

    def test_generate_with_audio(self, tmp_path, ffmpeg_path):
        output = tmp_path / "test_audio.mp4"
        fixture = generate_test_video(
            output_path=output,
            with_audio=True,
            sample_rate=44100,
            ffmpeg_path=ffmpeg_path,
        )
        assert fixture.has_audio is True
        assert fixture.sample_rate == 44100
        assert fixture.channels == 1

    def test_generate_respects_fps(self, tmp_path, ffmpeg_path):
        output = tmp_path / "test_fps.mp4"
        fixture = generate_test_video(
            output_path=output, fps=30, ffmpeg_path=ffmpeg_path
        )
        assert fixture.fps == 30

    def test_generate_respects_duration(self, tmp_path, ffmpeg_path):
        output = tmp_path / "test_duration.mp4"
        fixture = generate_test_video(
            output_path=output, duration=0.5, ffmpeg_path=ffmpeg_path
        )
        assert fixture.duration == 0.5

    def test_return_type_is_media_fixture(self, tmp_path, ffmpeg_path):
        output = tmp_path / "test_type.mp4"
        fixture = generate_test_video(output_path=output, ffmpeg_path=ffmpeg_path)
        assert isinstance(fixture, MediaFixture)


@requires_ffmpeg
class TestGenerateCorruptedMedia:
    def test_corrupted_fixture(self, tmp_path, ffmpeg_path):
        # First generate a valid file
        valid_path = tmp_path / "valid.mp4"
        fixture = generate_test_video(
            output_path=valid_path, ffmpeg_path=ffmpeg_path
        )
        assert fixture.path.stat().st_size > 0

        # Then corrupt it
        corrupted_path = tmp_path / "corrupted.mp4"
        result = generate_corrupted_media(corrupted_path, fixture)
        assert result.exists()
        assert result.stat().st_size < fixture.path.stat().st_size
        assert result.stat().st_size > 0

    def test_corrupted_is_smaller(self, tmp_path, ffmpeg_path):
        valid_path = tmp_path / "valid2.mp4"
        fixture = generate_test_video(
            output_path=valid_path, ffmpeg_path=ffmpeg_path
        )
        original_size = fixture.path.stat().st_size

        corrupted_path = tmp_path / "corrupted2.mp4"
        generate_corrupted_media(corrupted_path, fixture)
        corrupted_size = corrupted_path.stat().st_size

        # Corrupted should be roughly 10% of original
        assert corrupted_size <= original_size * 0.15  # allow some margin


@requires_ffmpeg
class TestGenerateTempFixture:
    def test_temp_fixture_cleanup_by_caller(self, ffmpeg_path):
        fixture = generate_temp_fixture(ffmpeg_path=ffmpeg_path)
        assert fixture.path.exists()
        assert fixture.path.stat().st_size > 0
        # Cleanup
        import shutil as _shutil

        _shutil.rmtree(fixture.path.parent, ignore_errors=True)
