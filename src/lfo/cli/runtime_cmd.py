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
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> VideoRuntime:
    """Construct the public facade without choosing a backend or handler.

    ``VideoRuntime`` gained persistence arguments in Runtime v1.  The narrow
    compatibility fallback keeps the CLI importable while an older facade is
    present during a staged source update; it is not a fake runtime.
    """
    kwargs: dict[str, Any] = {}
    if db_path:
        kwargs["db_path"] = Path(db_path)
    if workspace_root:
        kwargs["workspace_root"] = Path(workspace_root)
    if not kwargs:
        return runtime_factory()
    try:
        return runtime_factory(**kwargs)
    except TypeError as exc:
        if runtime_factory is VideoRuntime and "unexpected keyword argument" in str(exc):
            return runtime_factory()
        raise


def cmd_validate(
    package_path: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Validate a VideoExecutionPackage file."""
    if not package_path:
        return {"success": False, "valid": False, "error": "package_path is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        runtime_factory=runtime_factory,
    ).validate(package_path)
    return {"success": result.valid, "valid": result.valid, "errors": result.errors}


def cmd_plan(
    package_path: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Generate a materialization plan without running."""
    if not package_path:
        return {"success": False, "error": "package_path is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        runtime_factory=runtime_factory,
    ).plan(package_path)
    return {
        "success": result.error is None,
        "plan_id": result.plan_id,
        "clips": result.clip_plans,
        "warnings": result.warnings,
        "backend_summary": result.backend_summary,
        "error": result.error,
    }


def cmd_execute(
    package_path: str = "",
    approve: bool = False,
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Execute a previously reviewed VideoExecutionPackage."""
    if not package_path:
        return {"success": False, "error": "package_path is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        runtime_factory=runtime_factory,
    ).execute(package_path, approval=approve)
    return {
        "success": result.status == "COMPLETED",
        "run_id": result.run_id,
        "status": result.status,
        "clip_count": result.clip_count,
        "error": result.error,
    }


def cmd_runtime_status(
    run_id: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Read a persisted v1 runtime run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        runtime_factory=runtime_factory,
    ).status(run_id)
    return {
        "success": result.error is None,
        "run_id": result.run_id,
        "status": result.status,
        "tasks": result.tasks,
        "error": result.error,
    }


def cmd_retry(
    run_id: str = "",
    clip_id: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Retry a failed run or one clip using the stored run snapshot."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        runtime_factory=runtime_factory,
    ).retry(run_id, scope=clip_id or None)
    return {
        "success": result.status == "COMPLETED",
        "run_id": result.run_id,
        "status": result.status,
        "error": result.error,
    }


def cmd_cancel(
    run_id: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Cancel a persisted run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        runtime_factory=runtime_factory,
    ).cancel(run_id)
    return {"success": True, "run_id": run_id, "status": "CANCELLED"}


def cmd_review(
    run_id: str = "",
    target: str = "",
    decision: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Record an approval or rejection against a runtime review target."""
    if not run_id or not target:
        return {"success": False, "error": "run_id and target are required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
        runtime_factory=runtime_factory,
    ).review(run_id, target, decision)
    return {
        "success": result.error is None,
        "review_id": result.review_id,
        "decision": result.decision,
        "error": result.error,
    }


def cmd_export(
    run_id: str = "",
    *,
    db_path: str | None = None,
    workspace_root: str | None = None,
    runtime_factory: RuntimeFactory = VideoRuntime,
) -> dict[str, Any]:
    """Export a completed persisted run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    result = _make_runtime(
        db_path=db_path,
        workspace_root=workspace_root,
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
        ))


@CommandRegistry.register
class ExecuteCommand:
    name = "execute"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("package_path", help="Path to reviewed execution-package.json")
        parser.add_argument("--approve", action="store_true", help="Confirm execution approval")
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("execute", cmd_execute(
            args.package_path, approve=args.approve, db_path=args.db,
            workspace_root=args.workspace_root,
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
        ))


@CommandRegistry.register
class RetryCommand:
    name = "retry"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("run_id", help="Persisted Runtime v1 run ID")
        parser.add_argument("--clip-id", default="", help="Retry only this clip")
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("retry", cmd_retry(
            args.run_id, args.clip_id, db_path=args.db, workspace_root=args.workspace_root,
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
        ))


@CommandRegistry.register
class ReviewCommand:
    name = "review"

    @staticmethod
    def configure_parser(parser) -> None:
        parser.add_argument("run_id", help="Persisted Runtime v1 run ID")
        parser.add_argument("target", help="Review target, usually a clip ID")
        parser.add_argument("decision", choices=("approved", "rejected"))
        _configure_runtime_context(parser)

    @staticmethod
    def execute(context, args) -> CommandResult:
        return _command_result("review", cmd_review(
            args.run_id, args.target, args.decision, db_path=args.db,
            workspace_root=args.workspace_root,
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
        ))
