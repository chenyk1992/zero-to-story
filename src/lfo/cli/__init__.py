"""LFO CLI package — command entry points.

Commands register via @CommandRegistry.register at import time.
"""
from __future__ import annotations

from .config_cmd import cmd_config_resolve
from .doctor_cmd import cmd_doctor
from .machine_cmd import (
    cmd_machine_add,
    cmd_machine_inspect,
    cmd_machine_list,
    cmd_machine_migrate_project,
    cmd_machine_validate,
)
from .preflight_cmd import cmd_preflight
from .runtime_cmd import (
    cmd_cancel,
    cmd_export,
    cmd_execute,
    cmd_plan,
    cmd_retry,
    cmd_runtime_status,
    cmd_validate,
)
from .setup import cmd_setup
from .workflow_cmd import cmd_workflow_fork

__all__ = [
    "cmd_cancel",
    "cmd_config_resolve",
    "cmd_doctor",
    "cmd_export",
    "cmd_execute",
    "cmd_machine_add",
    "cmd_machine_inspect",
    "cmd_machine_list",
    "cmd_machine_migrate_project",
    "cmd_machine_validate",
    "cmd_plan",
    "cmd_preflight",
    "cmd_retry",
    "cmd_runtime_status",
    "cmd_setup",
    "cmd_validate",
    "cmd_workflow_fork",
]
