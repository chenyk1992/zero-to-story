"""Tests for timeline assembler."""

from __future__ import annotations

from pathlib import Path

import pytest

from lfo.media._ffmpeg import MediaCommandError
from lfo.media.handlers import TimelineHandler
from lfo.media.timeline import ClipSegment, TimelineAssembler, TimelineSpec


class TestTimelineAssembler:
    def test_assemble_single_segment(self) -> None:
        assembler = TimelineAssembler()
        spec = TimelineSpec(
            segments=[
                ClipSegment(clip_id="c1", file_path="/tmp/c1.mp4", duration_ms=5000),
            ]
        )
        result = assembler.assemble(spec)
        assert result.success
        assert result.total_duration_ms == 5000

    def test_assemble_multiple_segments(self) -> None:
        assembler = TimelineAssembler()
        spec = TimelineSpec(
            segments=[
                ClipSegment(clip_id="c1", file_path="/tmp/c1.mp4", duration_ms=5000),
                ClipSegment(clip_id="c2", file_path="/tmp/c2.mp4", duration_ms=3000),
            ]
        )
        result = assembler.assemble(spec)
        assert result.success
        assert result.total_duration_ms == 8000
        assert result.segment_count == 2

    def test_empty_segments_fails(self) -> None:
        assembler = TimelineAssembler()
        result = assembler.assemble(TimelineSpec())
        assert not result.success

    def test_segment_layout(self) -> None:
        assembler = TimelineAssembler()
        layout = assembler.compute_segment_layout([5000, 3000, 2000])
        assert layout == [(0, 5000), (5000, 8000), (8000, 10000)]

    def test_start_times_computed(self) -> None:
        assembler = TimelineAssembler()
        segments = [
            ClipSegment(clip_id="c1", file_path="/tmp/c1.mp4", duration_ms=4000),
            ClipSegment(clip_id="c2", file_path="/tmp/c2.mp4", duration_ms=6000),
        ]
        spec = TimelineSpec(segments=segments)
        assembler.assemble(spec)
        assert spec.segments[0].start_ms == 0
        assert spec.segments[1].start_ms == 4000

    def test_trimmed_segments_use_edited_duration_and_reencode(self) -> None:
        assembler = TimelineAssembler()
        segment = ClipSegment(
            clip_id="c1",
            file_path="/tmp/c1.mp4",
            duration_ms=10_000,
            source_in_ms=2_000,
            source_out_ms=7_000,
        )
        spec = TimelineSpec(segments=[segment])
        result = assembler.assemble(spec)
        assert result.success
        assert result.total_duration_ms == 5_000
        assert result.command is not None
        filter_graph = result.command[result.command.index("-filter_complex") + 1]
        assert "trim=start=2.000:end=7.000" in filter_graph
        assert "atrim=start=2.000:end=7.000" in filter_graph
        assert "-c:v" in result.command

    def test_source_out_zero_is_not_treated_as_unset(self) -> None:
        segment = ClipSegment(
            clip_id="c1",
            file_path="/tmp/c1.mp4",
            duration_ms=10_000,
            source_out_ms=0,
        )
        with pytest.raises(ValueError, match="Invalid source range"):
            segment.edited_duration_ms()

    def test_mixed_audio_input_indices_remain_aligned(self) -> None:
        command = TimelineAssembler().build_command(
            TimelineSpec(
                segments=[
                    ClipSegment("silent-a", "/missing/a.mp4", 1_000, has_audio=False),
                    ClipSegment("audio", "/missing/b.mp4", 1_000, has_audio=True),
                    ClipSegment("silent-b", "/missing/c.mp4", 1_000, has_audio=False),
                ]
            )
        )
        filter_complex = command[command.index("-filter_complex") + 1]
        assert "[0:v]" in filter_complex
        assert "[1:a]" in filter_complex
        assert "[2:v]" in filter_complex
        assert "[2:a]" in filter_complex
        assert "[3:v]" in filter_complex
        assert "[4:a]" in filter_complex

    def test_plan_only_copy_command_cleans_concat_list(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        sources = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
        for source in sources:
            source.touch()

        def fake_probe(path: str | Path) -> dict[str, object]:
            assert Path(path) in sources
            return {
                "duration_ms": 1_000,
                "width": 480,
                "height": 864,
                "fps": 24.0,
                "codec": "h264",
                "has_audio": True,
                "audio_codec": "aac",
                "sample_rate": 48_000,
                "channels": 2,
            }

        monkeypatch.setattr("lfo.media.timeline.probe", fake_probe)
        monkeypatch.chdir(tmp_path)
        result = TimelineAssembler().assemble(
            TimelineSpec(
                segments=[
                    ClipSegment("a", str(sources[0]), 1_000),
                    ClipSegment("b", str(sources[1]), 1_000),
                ],
                output_width=480,
                output_height=864,
                output_fps=24.0,
            )
        )
        assert result.success
        assert not list(tmp_path.glob(".*.concat.txt"))

    def test_fallback_normalizes_video_and_keeps_all_silent_segments_silent(self) -> None:
        command = TimelineAssembler().build_command(
            TimelineSpec(
                segments=[
                    ClipSegment("silent-a", "/missing/a.mp4", 1_000, has_audio=False),
                    ClipSegment("silent-b", "/missing/b.mp4", 2_000, has_audio=False),
                ],
                output_width=1080,
                output_height=1920,
                output_fps=24.0,
            )
        )
        filter_complex = command[command.index("-filter_complex") + 1]
        assert "scale=1080:1920:force_original_aspect_ratio=decrease" in filter_complex
        assert "pad=1080:1920" in filter_complex
        assert "fps=24" in filter_complex
        assert "format=yuv420p" in filter_complex
        assert "concat=n=2:v=1:a=0[outv]" in filter_complex
        assert "anullsrc" not in command

    def test_actual_media_duration_is_used_for_source_range_validation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        source = tmp_path / "clip.mp4"
        source.touch()

        def fake_probe(path: str | Path) -> dict[str, object]:
            assert Path(path) == source
            return {
                "duration_ms": 800,
                "width": 90,
                "height": 160,
                "fps": 12.0,
                "codec": "h264",
                "has_audio": False,
            }

        monkeypatch.setattr("lfo.media.timeline.probe", fake_probe)
        result = TimelineAssembler().assemble(
            TimelineSpec(
                segments=[
                    ClipSegment(
                        "clip",
                        str(source),
                        duration_ms=1_000,
                        source_in_ms=100,
                        source_out_ms=900,
                    )
                ]
            )
        )
        assert not result.success
        assert result.error is not None
        assert "actual media duration" in result.error

    def test_handler_converts_media_exception_to_retryable_result(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        project = workspace / "projects" / "project"
        output = project / "outputs" / "run" / "global" / "timeline.mp4"

        def fail_assembly(*args: object, **kwargs: object) -> object:
            raise MediaCommandError("ffmpeg unavailable")

        monkeypatch.setattr("lfo.media.handlers.TimelineAssembler.assemble", fail_assembly)
        result = TimelineHandler(workspace).execute(
            "timeline-task",
            "timeline.assemble",
            "timeline",
            {
                "segments": [
                    {
                        "clip_id": "clip",
                        "input_task_id": "clip.mix",
                        "duration_ms": 1_000,
                    }
                ],
                "input_artifacts": {"clip.mix": {"file_path": str(tmp_path / "clip.mp4")}},
                "output_path": str(output),
                "artifact_layout": {
                    "workspace_root": str(workspace),
                    "project_root": str(project),
                },
            },
            "attempt",
        )
        assert not result.success
        assert result.retryable
        assert result.error is not None
        assert "ffmpeg unavailable" in result.error
