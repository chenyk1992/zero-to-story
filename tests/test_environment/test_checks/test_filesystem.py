"""Tests for filesystem checks that depend on optional ComfyUI paths."""
from __future__ import annotations

from lfo.config.machine_profile import MachineProfile, StorageConfig
from lfo.environment.checks.base import CheckContext, CheckStatus
from lfo.environment.checks.filesystem import (
    check_input_writable,
    check_output_readable,
    check_project_writable,
)


def test_input_check_skips_when_comfy_input_is_not_configured() -> None:
    context = CheckContext(machine_profile=MachineProfile())

    result = check_input_writable(context)

    assert result.status == CheckStatus.SKIPPED
    assert "API upload" in result.message
    assert result.remediation is None


def test_output_check_skips_when_comfy_output_is_not_configured() -> None:
    context = CheckContext(machine_profile=MachineProfile())

    result = check_output_readable(context)

    assert result.status == CheckStatus.SKIPPED
    assert "/view" in result.message
    assert result.remediation is None


def test_configured_comfy_paths_are_still_checked(tmp_path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    context = CheckContext(
        machine_profile=MachineProfile(
            storage=StorageConfig(
                comfy_input=str(input_dir),
                comfy_output=str(output_dir),
            )
        )
    )

    assert check_input_writable(context).status == CheckStatus.PASSED
    assert check_output_readable(context).status == CheckStatus.PASSED


def test_project_check_does_not_create_directories_or_overwrite_probe(tmp_path):
    sentinel = tmp_path / ".lfo_write_probe"
    sentinel.write_text("user data", encoding="utf-8")
    projects = tmp_path / "not-created" / "projects"
    context = CheckContext(machine_profile=MachineProfile(
        storage=StorageConfig(lfo_projects=str(projects)),
    ))
    assert check_project_writable(context).status == CheckStatus.PASSED
    assert not projects.parent.exists()
    context.machine_profile.storage.lfo_projects = str(tmp_path)
    assert check_project_writable(context).status == CheckStatus.PASSED
    assert sentinel.read_text(encoding="utf-8") == "user data"
