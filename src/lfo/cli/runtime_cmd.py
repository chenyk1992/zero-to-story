"""CLI adapters for the public ``VideoRuntime`` facade.

Commands contain no execution policy.  They only parse arguments, construct a
runtime with the caller's persistent database/workspace configuration, and
render the facade result.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from lfo.application.video_runtime import VideoRuntime
from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry

RuntimeFactory = Callable[..., VideoRuntime]


def _make_runtime(
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    machine_id: str = "",
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> VideoRuntime:
    """Construct the public facade without choosing a backend or handler."""
    kwargs: dict[str, Any] = {}
    if db_path:
        kwargs["db_path"] = Path(db_path)
    if workspace_root:
        kwargs["workspace_root"] = Path(workspace_root)
    if machine_id:
        kwargs["machine_id"] = machine_id
    return runtime_factory(**kwargs)


def cmd_validate(
    package_path: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    machine_id: str = "",
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Validate a VideoExecutionPackage file."""
    if not package_path:
        return {"success": False, "valid": False, "error": "package_path is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        machine_id=machine_id,
        runtime_factory=runtime_factory,
    ).validate(package_path)
    return {
        "success": result.valid,
        "valid": result.valid,
        "package_sha256": result.package_sha256,
        "errors": result.errors,
        "warnings": result.warnings,
    }


def cmd_plan(
    package_path: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    machine_id: str = "",
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Generate a materialization plan without running."""
    if not package_path:
        return {"success": False, "error": "package_path is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        machine_id=machine_id,
        runtime_factory=runtime_factory,
    ).plan(package_path)
    return {
        "success": result.error is None,
        "plan_id": result.plan_id,
        "clips": result.clip_plans,
        "warnings": result.warnings,
        "backend_summary": result.backend_summary,
        "output_layout": result.output_layout,
        "error": result.error,
    }


def cmd_execute(
    package_path: str = "",
    approved_sha256: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    machine_id: str = "",
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Execute a package after exact file-hash approval."""
    if not package_path:
        return {"success": False, "error": "package_path is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        machine_id=machine_id,
        runtime_factory=runtime_factory,
    ).execute(package_path, approved_sha256=approved_sha256)
    return {
        "success": result.status == "COMPLETED",
        "run_id": result.run_id,
        "status": result.status,
        "clip_count": result.clip_count,
        "file_path": result.file_path,
        "output_layout": result.output_layout,
        "error": result.error,
    }


def cmd_runtime_status(
    run_id: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    machine_id: str = "",
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Read a persisted v1 runtime run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        machine_id=machine_id,
        runtime_factory=runtime_factory,
    ).status(run_id)
    return {
        "success": result.error is None,
        "run_id": result.run_id,
        "status": result.status,
        "tasks": result.tasks,
        "progress": result.progress,
        "output_layout": result.output_layout,
        "error": result.error,
    }


def cmd_cancel(
    run_id: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    machine_id: str = "",
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Cancel a persisted run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    runtime = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        machine_id=machine_id,
        runtime_factory=runtime_factory,
    )
    cancelled = runtime.cancel(run_id)
    if not cancelled:
        current = runtime.status(run_id)
        if current.error is not None:
            return {"success": False, "run_id": run_id, "error": current.error}
        return {
            "success": False,
            "run_id": run_id,
            "status": current.status,
            "error": f"Run is {current.status} and cannot be cancelled",
        }
    return {"success": True, "run_id": run_id, "status": "CANCELLED"}


def cmd_export(
    run_id: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    machine_id: str = "",
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Export a completed persisted run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        machine_id=machine_id,
        runtime_factory=runtime_factory,
    ).export(run_id)
    return {
        "success": result.status == "READY",
        "export_id": result.export_id,
        "status": result.status,
        "file_path": result.file_path,
        "error": result.error,
    }


def _configure_runtime_context(parser) -> None:
    parser.add_argument(
        "--workspace-root",
        default=None,
        help="LFO workspace root (defaults to the runtime configuration)",
    )
    parser.add_argument(
        "--machine-id",
        default="",
        help="Saved machine profile used for ComfyUI/comfy-cli execution",
    )


def _command_result(command: str, data: dict[str, Any]) -> CommandResult:
    if data.get("success"):
        return CommandResult(ok=True, command=command, data=data)
    return CommandResult(
        ok=False,
        command=command,
        data=data,
        error={"code": f"E_{command.upper()}", "message": data.get("error", "operation failed")},
    )


@CommandRegistry.register
class ValidateCommand:
    name = "validate"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("package_path", help="Path to execution-package.json")
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("validate", cmd_validate(
            args.package_path, db_path=args.db, workspace_root=args.workspace_root,
            machine_id=args.machine_id,
        ))


@CommandRegistry.register
class PlanCommand:
    name = "plan"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("package_path", help="Path to execution-package.json")
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("plan", cmd_plan(
            args.package_path, db_path=args.db, workspace_root=args.workspace_root,
            machine_id=args.machine_id,
        ))


@CommandRegistry.register
class ExecuteCommand:
    name = "execute"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("package_path", help="Path to execution-package.json")
        parser.add_argument(
            "--approved-sha256",
            required=True,
            help="Exact SHA-256 of the approved execution-package.json bytes",
        )
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("execute", cmd_execute(
            args.package_path, approved_sha256=args.approved_sha256, db_path=args.db,
            workspace_root=args.workspace_root, machine_id=args.machine_id,
        ))


@CommandRegistry.register
class RuntimeStatusCommand:
    name = "status"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("run_id", help="Persisted Runtime v1 run ID")
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("status", cmd_runtime_status(
            args.run_id, db_path=args.db, workspace_root=args.workspace_root,
            machine_id=args.machine_id,
        ))


@CommandRegistry.register
class CancelCommand:
    name = "cancel"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("run_id", help="Persisted Runtime v1 run ID")
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("cancel", cmd_cancel(
            args.run_id, db_path=args.db, workspace_root=args.workspace_root,
            machine_id=args.machine_id,
        ))


@CommandRegistry.register
class ExportCommand:
    name = "export"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("run_id", help="Persisted Runtime v1 run ID")
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("export", cmd_export(
            args.run_id, db_path=args.db, workspace_root=args.workspace_root,
            machine_id=args.machine_id,
        ))
