"""Shared fixtures for environment tools tests."""

from __future__ import annotations

import shutil

import pytest

from lfo.environment.tools.ffmpeg_probe import probe_ffmpeg

# Skip marker for tests that require FFmpeg to be installed
requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="FFmpeg not installed"
)


@pytest.fixture
def ffmpeg_result():
    """Probe FFmpeg once and share across tests in this module."""
    return probe_ffmpeg()


@pytest.fixture
def ffmpeg_path():
    """Return the FFmpeg path if available, else skip."""
    path = shutil.which("ffmpeg")
    if not path:
        pytest.skip("FFmpeg not installed")
    return path
