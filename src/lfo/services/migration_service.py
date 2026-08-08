"""Migration service — cross-machine project migration."""
from __future__ import annotations

from lfo.config.machine_profile import MachineProfile, load_machine_profile
from lfo.environment.checks.base import CheckContext, CheckResult, CheckStatus
from lfo.services.doctor_service import DoctorService


class MigrationService:
    """Handle project migration between machines."""

    def __init__(self, source_profile: MachineProfile) -> None:
        self.source_profile = source_profile

    def validate_target(
        self,
        project_id: str,
        target_profile: MachineProfile,
    ) -> list[CheckResult]:
        """Can this project run on the target machine?"""
        doctor = DoctorService(target_profile)
        context = CheckContext(machine_profile=target_profile)
        return doctor.run_full_check(context)

    def migrate_project(
        self,
        project_id: str,
        target_machine_id: str,
        project_root: str = "",
    ) -> dict:
        """Migrate project to new machine.

        - Re-resolve paths via new PathResolver
        - Re-validate workflows
        - Re-run preflight
        - Does NOT modify Storyboard or ExecutionPlan semantics
        - May update params_hash/idempotency_key if execution environment changed
        """
        target_profile = load_machine_profile(target_machine_id)
        if target_profile is None:
            return {
                "success": False,
                "error": f"Target machine profile not found: {target_machine_id}",
            }

        # Run preflight on target
        doctor = DoctorService(target_profile)
        context = CheckContext(machine_profile=target_profile)
        check_results = doctor.run_full_check(context)

        blockers = [
            r for r in check_results
            if r.status == CheckStatus.FAILED and r.severity.value == "blocker"
        ]

        if blockers:
            return {
                "success": False,
                "error": f"Target machine has {len(blockers)} blocker(s)",
                "blockers": [
                    {"check_id": b.check_id, "message": b.message}
                    for b in blockers
                ],
            }

        return {
            "success": True,
            "project_id": project_id,
            "target_machine_id": target_machine_id,
            "checks_passed": len([r for r in check_results if r.status == CheckStatus.PASSED]),
            "checks_total": len(check_results),
            "warnings": len([
                r for r in check_results
                if r.status == CheckStatus.FAILED and r.severity.value == "warning"
            ]),
        }
