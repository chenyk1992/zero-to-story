"""lfo setup command — bootstrap environment."""
from __future__ import annotations

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry


def cmd_setup(
    machine_id: str = "",
) -> dict:
    """lfo setup: Bootstrap environment.

    Args:
        machine_id: Machine identifier (default: auto-detect)

    Returns:
        dict with setup results
    """
    if not machine_id:
        import platform
        machine_id = f"{platform.node()}-default"

    from lfo.services.environment_service import EnvironmentService

    service = EnvironmentService()
    try:
        discovery, _profile = service.discover_and_create_profile(
            machine_id, save=True
        )

        return {
            "success": True,
            "machine_id": machine_id,
            "comfyui_running": discovery.comfyui_running,
            "comfyui_pid": discovery.comfyui_pid,
            "gpu_name": discovery.gpu_name,
            "vram_mib": discovery.vram_mib,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@CommandRegistry.register
class SetupCommand:
    """CLI adapter for cmd_setup."""

    name = "setup"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument(
            "--machine-id",
            default="",
            help="Machine identifier (default: auto-detect from hostname)",
        )

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_setup(
            machine_id=args.machine_id,
        )
        ok = result.get("success", False)
        if ok:
            return CommandResult(ok=True, command="setup", data=result)
        return CommandResult(
            ok=False,
            command="setup",
            error={"code": "E_SETUP", "message": result.get("error", "unknown")},
        )
