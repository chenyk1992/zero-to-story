"""lfo machine command — list/inspect/validate/add/migrate-project."""
from __future__ import annotations

from lfo.config.machine_profile import (
    list_machine_ids,
    load_machine_profile,
    validate_machine_profile,
)
from lfo.services.migration_service import MigrationService


def cmd_machine_list() -> dict:
    """List all registered machines."""
    ids = list_machine_ids()
    return {
        "success": True,
        "machines": [
            {"machine_id": mid, "configured": load_machine_profile(mid) is not None}
            for mid in ids
        ],
    }


def cmd_machine_inspect(machine_id: str = "") -> dict:
    """Inspect a machine profile."""
    if not machine_id:
        return {"success": False, "error": "machine_id is required"}

    profile = load_machine_profile(machine_id)
    if profile is None:
        return {
            "success": False,
            "error": f"Machine profile not found: {machine_id}",
        }

    return {
        "success": True,
        "profile": profile.to_dict(),
    }


def cmd_machine_validate(machine_id: str = "") -> dict:
    """Validate a machine profile."""
    if not machine_id:
        return {"success": False, "error": "machine_id is required"}

    profile = load_machine_profile(machine_id)
    if profile is None:
        return {
            "success": False,
            "error": f"Machine profile not found: {machine_id}",
        }

    errors = validate_machine_profile(profile)
    return {
        "success": len(errors) == 0,
        "machine_id": machine_id,
        "errors": errors,
    }


def cmd_machine_add(machine_id: str = "") -> dict:
    """Add a new machine by auto-discovery."""
    if not machine_id:
        return {"success": False, "error": "machine_id is required"}

    from lfo.services.environment_service import EnvironmentService

    service = EnvironmentService()
    try:
        _, profile = service.discover_and_create_profile(machine_id, save=True)
        return {
            "success": True,
            "machine_id": machine_id,
            "profile": profile.to_dict(),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


def cmd_machine_migrate_project(
    project_id: str = "",
    target_machine: str = "",
) -> dict:
    """Migrate a project to a different machine."""
    if not project_id:
        return {"success": False, "error": "project_id is required"}
    if not target_machine:
        return {"success": False, "error": "target_machine is required"}

    import platform
    source_id = f"{platform.node()}-default"

    source_profile = load_machine_profile(source_id)
    if source_profile is None:
        return {
            "success": False,
            "error": f"Source machine profile not found: {source_id}",
        }

    service = MigrationService(source_profile)
    return service.migrate_project(project_id, target_machine)
