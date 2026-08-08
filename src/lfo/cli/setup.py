"""lfo setup command — bootstrap environment."""
from __future__ import annotations

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.config.defaults import SMOKE_LEVELS


def cmd_setup(
    smoke_level: str = "light",
    machine_id: str = "",
) -> dict:
    """lfo setup: Bootstrap environment.

    Args:
        smoke_level: One of 'none', 'static', 'runtime', 'light', 'full'
        machine_id: Machine identifier (default: auto-detect)

    Returns:
        dict with setup results
    """
    if smoke_level not in SMOKE_LEVELS:
        return {
            "success": False,
            "error": f"Invalid smoke level: {smoke_level}. Must be one of: {SMOKE_LEVELS}",
        }

    if not machine_id:
        import platform
        machine_id = f"{platform.node()}-default"

    from lfo.services.environment_service import EnvironmentService

    service = EnvironmentService()
    try:
        discovery, profile = service.discover_and_create_profile(
            machine_id, save=True
        )

        # Also create an initial environment snapshot so downstream
        # pipelines (task readiness, doctor, preflight) have a reference
        # point. Without this, the first pipeline run fails with
        # "No environment snapshot found for machine '<id>'".
        snapshot_id = ""
        try:
            from lfo.core.database import Database
            from lfo.services.environment_snapshot_service import (
                EnvironmentSnapshotService,
            )
            db = Database(_workspace_db_path())
            db.init_schema()
            snap_svc = EnvironmentSnapshotService(db)
            record = snap_svc.capture_and_save(profile)
            snapshot_id = record.snapshot_id
        except Exception as snap_exc:  # noqa: BLE001 — best-effort
            # Snapshot creation is best-effort; setup itself succeeded.
            snapshot_id = f"failed: {snap_exc}"

        return {
            "success": True,
            "machine_id": machine_id,
            "smoke_level": smoke_level,
            "comfyui_running": discovery.comfyui_running,
            "comfyui_pid": discovery.comfyui_pid,
            "gpu_name": discovery.gpu_name,
            "vram_mib": discovery.vram_mib,
            "snapshot_id": snapshot_id,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


def _workspace_db_path() -> str:
    """Resolve the workspace SQLite path for the snapshot."""
    import os
    from pathlib import Path
    from lfo.services.workspace import db_path
    p = db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    return str(p)


@CommandRegistry.register
class SetupCommand:
    """CLI adapter for cmd_setup."""

    name = "setup"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument(
            "--smoke-level",
            default="light",
            choices=list(SMOKE_LEVELS),
            help="Smoke test level for the generated machine profile",
        )
        parser.add_argument(
            "--machine-id",
            default="",
            help="Machine identifier (default: auto-detect from hostname)",
        )

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_setup(
            smoke_level=args.smoke_level,
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
