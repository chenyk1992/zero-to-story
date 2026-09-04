"""Doctor service — full diagnostic check suite."""
from __future__ import annotations

from lfo.config.machine_profile import MachineProfile
from lfo.environment.checks.base import (
    CheckContext,
    CheckResult,
    CheckRunner,
    CheckStatus,
)
from lfo.environment.checks.comfy_runtime import (
    check_comfyui_correct_instance,
    check_comfyui_reachable,
    check_comfyui_version,
)
from lfo.environment.checks.filesystem import (
    check_disk_space,
    check_output_readable,
    check_project_writable,
)
from lfo.environment.checks.hardware import (
    check_gpu_available,
    check_ram_sufficient,
    check_vram_sufficient,
)
from lfo.environment.checks.models import (
    check_models_hash_verified,
    check_models_present,
)
from lfo.environment.checks.tools import (
    check_comfy_cli,
    check_ffmpeg,
    check_ffprobe,
    check_python,
)
from lfo.environment.checks.workflows import (
    check_workflow_bindings,
    check_workflow_hash_match,
    check_workflow_runtime_compatible,
)


def register_all_checks(runner: CheckRunner) -> None:
    """Register all available checks with a CheckRunner."""
    # ComfyUI runtime
    runner.register(check_comfyui_reachable)
    runner.register(check_comfyui_version)
    runner.register(check_comfyui_correct_instance)

    # Filesystem
    runner.register(check_output_readable)
    runner.register(check_disk_space)
    runner.register(check_project_writable)

    # Hardware
    runner.register(check_gpu_available)
    runner.register(check_vram_sufficient)
    runner.register(check_ram_sufficient)

    # Models
    runner.register(check_models_present)
    runner.register(check_models_hash_verified)

    # Workflows
    runner.register(check_workflow_hash_match)
    runner.register(check_workflow_bindings)
    runner.register(check_workflow_runtime_compatible)

    # Tools
    runner.register(check_comfy_cli)
    runner.register(check_ffmpeg)
    runner.register(check_ffprobe)
    runner.register(check_python)


class DoctorService:
    """Run all checks for installation, migration, or diagnosis."""

    def __init__(self, machine_profile: MachineProfile) -> None:
        self.profile = machine_profile
        self.runner = CheckRunner()
        register_all_checks(self.runner)

    def run_full_check(
        self, context: CheckContext | None = None
    ) -> list[CheckResult]:
        """Run ALL checks."""
        if context is None:
            context = CheckContext(
                machine_profile=self.profile, required_tools={"comfy", "ffmpeg", "ffprobe"},
            )
        return self.runner.run(context)

    def run_for_workflow(
        self,
        workflow_id: str,
        context: CheckContext | None = None,
    ) -> list[CheckResult]:
        """Run checks relevant to a specific workflow."""
        if context is None:
            context = CheckContext(
                machine_profile=self.profile,
                required_workflow_ids={workflow_id},
                required_tools={"comfy", "ffmpeg", "ffprobe"},
            )
        else:
            context.required_workflow_ids.add(workflow_id)
        return self.runner.run(context)

    def has_blockers(self, results: list[CheckResult]) -> bool:
        """Check if any blocker-level issues exist."""
        return any(
            r.status == CheckStatus.FAILED and r.severity.value == "blocker"
            for r in results
        )
