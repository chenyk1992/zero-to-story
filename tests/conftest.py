"""Shared pytest configuration for LFO tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# src-layout: tests/ lives at the project root while the actual package
# lives at src/lfo/. Inject <root>/src onto sys.path so `import lfo`
# resolves without requiring `pip install -e .` for the test suite.
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


@pytest.fixture(autouse=True)
def isolate_process_state(monkeypatch, tmp_path):
    """Isolate each test from global state mutations.

    - Redirects application, workspace and submission state to tmp_path.
    - Saves and restores os.chdir() to prevent cwd leaks.
    """
    original_cwd = Path.cwd()

    # Isolate environment variables to per-test temp dirs
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    monkeypatch.setenv("LFO_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("LFO_VIDEO_STATE", str(tmp_path / "video-state"))
    monkeypatch.setenv("LFO_CANVAS_DATA", str(tmp_path / "canvas-state"))

    try:
        yield
    finally:
        os.chdir(original_cwd)
