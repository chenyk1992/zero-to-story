"""Tests for FFmpeg capability probe."""
from __future__ import annotations

import json
import shutil
from unittest.mock import patch

import pytest

from lfo.environment.tools.ffmpeg_probe import (
    ProbeResult,
    find_executable,
    parse_version,
    probe_ffmpeg,
    probe_ffmpeg_json,
)

requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="FFmpeg not installed"
)


class TestFindExecutable:
    def test_returns_none_for_missing(self):
        result = find_executable("nonexistent_binary_xyz123")
        assert result is None

    def test_finds_system_python(self):
        result = find_executable("python")
        # python should be available in test environment
        assert result is not None
        assert shutil.which(result) is not None


class TestParseVersion:
    def test_extracts_version_string(self):
        output = "ffmpeg version 8.1-full_build-www.gyan.dev Copyright (c) 2000-2026"
        assert parse_version(output) == "8.1-full_build-www.gyan.dev"

    def test_extracts_simple_version(self):
        output = "ffmpeg version 4.4.2"
        assert parse_version(output) == "4.4.2"

    def test_returns_none_for_empty(self):
        assert parse_version("") is None

    def test_returns_none_for_no_version(self):
        assert parse_version("some random output") is None


class TestProbeResult:
    def test_not_available_when_missing(self):
        # Patch find_executable to simulate missing FFmpeg
        with patch("lfo.environment.tools.ffmpeg_probe.find_executable", return_value=None):
            with patch.dict("os.environ", {}, clear=False):
                # Ensure LFO_FFMPEG is not set
                import os

                env = {k: v for k, v in os.environ.items() if k != "LFO_FFMPEG"}
                with patch.dict("os.environ", env, clear=True):
                    result = probe_ffmpeg()
                    assert result.available is False

    def test_has_error_message(self):
        with patch("lfo.environment.tools.ffmpeg_probe.find_executable", return_value=None):
            import os

            env = {k: v for k, v in os.environ.items() if k != "LFO_FFMPEG"}
            with patch.dict("os.environ", env, clear=True):
                result = probe_ffmpeg()
                assert result.error is not None
                assert "not found" in result.error.lower() or "not found" in result.error

    def test_json_serialization(self):
        result = ProbeResult(
            available=False,
            error="test error",
            capabilities={"scale": False},
        )
        json_str = probe_ffmpeg_json()
        # Just verify it's valid JSON
        parsed = json.loads(json_str)
        assert "available" in parsed
        assert "capabilities" in parsed

    def test_dataclass_default_capabilities(self):
        result = ProbeResult(available=True)
        assert result.capabilities == {}
        assert result.ffmpeg_path is None
        assert result.error is None


@requires_ffmpeg
class TestProbeWithFFmpeg:
    def test_probe_detects_ffmpeg_if_installed(self, ffmpeg_result):
        assert ffmpeg_result.available is True
        assert ffmpeg_result.ffmpeg_path is not None
        assert ffmpeg_result.ffmpeg_version is not None

    def test_probe_checks_required_filters(self, ffmpeg_result):
        caps = ffmpeg_result.capabilities
        assert "scale" in caps
        assert "pad" in caps
        assert "crop" in caps
        assert "concat" in caps

    def test_probe_checks_required_encoders(self, ffmpeg_result):
        caps = ffmpeg_result.capabilities
        assert "libx264" in caps
        assert "aac" in caps

    def test_lavfi_check_works(self, ffmpeg_result):
        caps = ffmpeg_result.capabilities
        assert "lavfi" in caps
        # lavfi should be available in standard FFmpeg builds
        assert caps["lavfi"] is True

    def test_ffprobe_also_detected(self, ffmpeg_result):
        # ffprobe usually comes with ffmpeg
        if shutil.which("ffprobe"):
            assert ffmpeg_result.ffprobe_path is not None
            assert ffmpeg_result.ffprobe_version is not None

    def test_explicit_path_overrides(self, ffmpeg_path):
        result = probe_ffmpeg(ffmpeg_path=ffmpeg_path)
        assert result.available is True
        assert result.ffmpeg_path == ffmpeg_path

    def test_env_var_override(self, ffmpeg_path):

        with patch.dict("os.environ", {"LFO_FFMPEG": ffmpeg_path}):
            result = probe_ffmpeg()
            assert result.available is True
            assert result.ffmpeg_path == ffmpeg_path
