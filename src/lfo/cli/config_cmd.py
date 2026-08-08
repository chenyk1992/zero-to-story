"""lfo config command — resolve configuration."""
from __future__ import annotations

from lfo.config.config_resolver import resolve_config


def cmd_config_resolve(
    project_path: str = "",
    machine_id: str = "",
) -> dict:
    """lfo config resolve: Show resolved configuration.

    Args:
        project_path: Path to project directory
        machine_id: Machine identifier

    Returns:
        dict with resolved config
    """
    import pathlib

    proj_path = pathlib.Path(project_path) if project_path else None

    resolved = resolve_config(
        project_path=proj_path,
        machine_id=machine_id,
    )

    return {
        "success": True,
        "machine_id": resolved.machine_id,
        "config": resolved.raw,
    }
