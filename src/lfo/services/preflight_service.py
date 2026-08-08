"""Preflight service — task-specific pre-flight checks."""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.config.machine_profile import MachineProfile
from lfo.environment.checks.base import (
    CheckContext,
    CheckResult,
    CheckRunner,
    CheckStatus,
)
from lfo.environment.fingerprint import EnvironmentSnapshot
from lfo.services.doctor_service import register_all_checks


@dataclass
class PreflightContext:
    """Narrow context for current execution plan."""

    project_id: str
    machine_id: str
    required_workflow_ids: set[str] = field(default_factory=set)
    required_model_ids: set[str] = field(default_factory=set)
    required_tools: set[str] = field(default_factory=set)
    required_storage_bytes: int = 0


class PreflightService:
    """Run only checks needed for the current task closure."""

    def __init__(self, machine_profile: MachineProfile) -> None:
        self.profile = machine_profile
        self.runner = CheckRunner()
        register_all_checks(self.runner)

    def preflight(
        self,
        ctx: PreflightContext,
        snapshot: EnvironmentSnapshot | None = None,
    ) -> list[CheckResult]:
        """Run subset of checks based on what's actually needed."""
        check_ctx = CheckContext(
            machine_profile=self.profile,
            env_snapshot=snapshot.to_dict() if snapshot else None,
            required_workflow_ids=ctx.required_workflow_ids,
            required_model_ids=ctx.required_model_ids,
            required_tools=ctx.required_tools,
            required_storage_bytes=ctx.required_storage_bytes,
        )
        return self.runner.run(check_ctx)

    def has_blockers(self, results: list[CheckResult]) -> bool:
        """Check if any blocker-level issues exist."""
        return any(
            r.status == CheckStatus.FAILED and r.severity.value == "blocker"
            for r in results
        )

    def get_status(self, results: list[CheckResult]) -> str:
        """Get overall status from results."""
        if self.has_blockers(results):
            return "blocked"
        has_warnings = any(
            r.status == CheckStatus.FAILED and r.severity.value == "warning"
            for r in results
        )
        if has_warnings:
            return "warning"
        return "passed"
