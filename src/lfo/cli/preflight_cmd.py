"""lfo preflight command — check before run."""
from __future__ import annotations

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.config.machine_profile import load_machine_profile
from lfo.services.preflight_service import PreflightContext, PreflightService


def cmd_preflight(
    project_id: str = "",
    machine_id: str = "",
    workflow_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
    tool_ids: list[str] | None = None,
) -> dict:
    """lfo preflight: Check before run.

    Args:
        project_id: Project identifier
        machine_id: Machine identifier
        workflow_ids: Required workflow IDs
        model_ids: Required model IDs
        tool_ids: Required tools

    Returns:
        dict with preflight results
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

    ctx = PreflightContext(
        project_id=project_id,
        machine_id=machine_id,
        required_workflow_ids=set(workflow_ids or []),
        required_model_ids=set(model_ids or []),
        required_tools=set(tool_ids) if tool_ids is not None else {"comfy", "ffmpeg", "ffprobe"},
    )

    service = PreflightService(profile)
    results = service.preflight(ctx)

    return {
        "success": not service.has_blockers(results),
        "status": service.get_status(results),
        "machine_id": machine_id,
        "project_id": project_id,
        "total_checks": len(results),
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
class PreflightCommand:
    """CLI adapter for cmd_preflight."""

    name = "preflight"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("--machine-id", default="", help="Machine identifier (default: auto)")
        parser.add_argument("--project-id", default="", help="Project identifier")
        parser.add_argument("--workflow-ids", nargs="*", default=[], help="Required workflow IDs")
        parser.add_argument("--model-ids", nargs="*", default=[], help="Required model IDs")
        parser.add_argument("--tool-ids", nargs="*", default=[], help="Required tool IDs")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_preflight(
            project_id=args.project_id,
            machine_id=args.machine_id,
            workflow_ids=args.workflow_ids or None,
            model_ids=args.model_ids or None,
            tool_ids=args.tool_ids or None,
        )
        ok = result.get("success", False)
        if ok:
            return CommandResult(ok=True, command="preflight", data=result)
        return CommandResult(
            ok=False,
            command="preflight",
            data=result,
            error={"code": "E_PREFLIGHT", "message": result.get("error") or "; ".join(
                item["message"] for item in result.get("results", [])
                if item["status"] == "failed" and item["severity"] == "blocker"
            )},
        )
