"""lfo doctor command — run diagnostic checks."""
from __future__ import annotations

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.config.machine_profile import load_machine_profile
from lfo.services.doctor_service import DoctorService


def cmd_doctor(
    machine_id: str = "",
    workflow_id: str = "",
) -> dict:
    """lfo doctor: Run diagnostic checks.

    Args:
        machine_id: Machine identifier
        workflow_id: If provided, run checks for specific workflow

    Returns:
        dict with diagnostic results
    """
    if not machine_id:
        import platform
        machine_id = f"{platform.node()}-default"

    profile = load_machine_profile(machine_id)
    if profile is None:
        return {
            "success": False,
            "error": f"Machine profile not found: {machine_id}. Run 'lfo setup' first.",
        }

    doctor = DoctorService(profile)

    if workflow_id:
        results = doctor.run_for_workflow(workflow_id)
    else:
        results = doctor.run_full_check()

    passed = sum(1 for r in results if r.status.value == "passed")
    failed = sum(1 for r in results if r.status.value == "failed")
    skipped = sum(1 for r in results if r.status.value == "skipped")
    blockers = sum(
        1 for r in results
        if r.status.value == "failed" and r.severity.value == "blocker"
    )

    return {
        "success": blockers == 0,
        "machine_id": machine_id,
        "total_checks": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "blockers": blockers,
        "results": [
            {
                "check_id": r.check_id,
                "severity": r.severity.value,
                "status": r.status.value,
                "message": r.message,
                "remediation": r.remediation,
            }
            for r in results
        ],
    }


@CommandRegistry.register
class DoctorCommand:
    """CLI adapter for cmd_doctor."""

    name = "doctor"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("--machine-id", default="", help="Machine identifier (default: auto)")
        parser.add_argument("--workflow-id", default="", help="Run checks for specific workflow")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_doctor(
            machine_id=args.machine_id,
            workflow_id=args.workflow_id,
        )
        ok = result.get("success", False)
        if ok:
            return CommandResult(ok=True, command="doctor", data=result)
        return CommandResult(
            ok=False,
            command="doctor",
            data=result,
            error={"code": "E_DOCTOR", "message": result.get("error") or "; ".join(
                item["message"] for item in result.get("results", [])
                if item["status"] == "failed" and item["severity"] == "blocker"
            )},
        )
