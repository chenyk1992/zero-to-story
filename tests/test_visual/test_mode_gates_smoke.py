"""Smoke test for Mode Complete gate runner.

Verifies the gate runner script exits 0 when all M0–M13 gates pass.
"""
from __future__ import annotations

import os
import subprocess
import sys


def test_mode_complete_gates_pass():
    """All M0–M13 gates should pass in the current codebase."""
    env = os.environ.copy()
    # src layout: ensure both the project root and <root>/src are on
    # PYTHONPATH so subprocess imports of `lfo.*` resolve correctly.
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    )))
    env["PYTHONPATH"] = (
        project_root + os.pathsep
        + os.path.join(project_root, "src") + os.pathsep
        + env.get("PYTHONPATH", "")
    )
    result = subprocess.run(
        [sys.executable, "scripts/mode_complete_gates.py", "--skip-production"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, (
        f"Gate runner failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    assert "Mode Complete" in result.stdout
    assert "14/14 gates passed" in result.stdout
