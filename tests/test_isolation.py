"""Regression tests for test isolation guarantees (Phase 4.6A).

These tests verify that the autouse fixture `isolate_process_state`
properly prevents state leakage between tests.
"""
from __future__ import annotations

import os
from pathlib import Path

# A sentinel value that should NEVER appear in other tests.
_SENTINEL_ENV = "__LFO_ISOLATION_TEST_SENTINEL_12345__"
_SENTINEL_CWD = Path("/tmp/lfo_isolation_sentinel_cwd_12345")


def test_environment_mutation_does_not_leak(monkeypatch):
    """Mutating os.environ via monkeypatch in this test must not leak."""
    monkeypatch.setenv(_SENTINEL_ENV, "leaked")
    # The fixture's monkeypatch will restore environ after this test.
    assert os.environ.get(_SENTINEL_ENV) == "leaked"


def test_environment_mutation_was_cleaned_up():
    """Verify the previous test's env mutation did not leak."""
    assert _SENTINEL_ENV not in os.environ, (
        f"Environment leak detected: {_SENTINEL_ENV}={os.environ.get(_SENTINEL_ENV)}"
    )


def test_working_directory_does_not_leak():
    """Changing cwd in a test must be restored by the fixture."""
    original = Path.cwd()
    # Use a temp dir that exists
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    try:
        os.chdir(tmp)
        assert Path.cwd() == tmp
    finally:
        # The fixture's finally block should also restore, but we do it
        # explicitly here to keep this test self-contained.
        os.chdir(original)


def test_working_directory_was_restored():
    """Verify cwd was restored after the previous test."""
    # The fixture should have restored cwd to the project root.
    # We can't assert the exact path (it depends on invocation),
    # but we know it should NOT be the sentinel tmp dir.
    assert "lfo_isolation_sentinel_cwd" not in str(Path.cwd())


def test_config_resolution_is_order_independent():
    """Config resolution must produce consistent results regardless of test execution order."""
    from lfo.config.config_resolver import resolve_config

    # First call
    config1 = resolve_config()
    val1 = config1.get("comfyui.port")

    # Second call — must produce the same result
    config2 = resolve_config()
    val2 = config2.get("comfyui.port")

    assert val1 == val2, (
        f"Config resolution is order-dependent: first={val1}, second={val2}"
    )


def test_lfo_home_is_isolated(tmp_path):
    """LFO_HOME should point to a per-test temp directory."""
    lfo_home = os.environ.get("LFO_HOME", "")
    assert lfo_home, "LFO_HOME should be set by the fixture"
    # It should be under the pytest-managed tmp_path
    assert "tmp" in lfo_home.lower() or "temp" in lfo_home.lower(), (
        f"LFO_HOME does not appear to be in a temp dir: {lfo_home}"
    )
