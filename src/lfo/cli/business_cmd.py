"""lfo business commands — assemble, export, retry, recover, continuity, attempts."""
from __future__ import annotations

import argparse

from lfo.assembly.compiler import AssemblyCompiler
from lfo.assembly.service import AssemblyService
from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.core.database import Database
from lfo.core.retry import RemediationPlanner, classify_failure
from lfo.services.continuity_service import ContinuityService
from lfo.services.edl_service import EDLService
from lfo.services.report_service import ReportService


def cmd_assemble(edl_id: str, db_path: str = "") -> dict:
    """Assemble a final MP4 from an approved EDL."""
    if not edl_id:
        return {"success": False, "error": "edl_id required"}

    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = AssemblyService(db, compiler=AssemblyCompiler(db), edl_service=EDLService(db))

    try:
        result = svc.build_from_edl(edl_id)
        return {
            "success": result.success,
            "output_asset_id": result.output_asset_id,
            "output_file_path": result.output_file_path,
            "duration_sec": result.duration_sec,
            "error": result.error,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def cmd_export(
    project_id: str,
    edl_id: str = "",
    db_path: str = "",
    output_dir: str = "",
    reports_only: bool = False,
) -> dict:
    """Export: assemble video OR generate report package to disk.

    Modes:
    - Default (with --edl-id): assemble video + SRT
    - With --reports-only: write JSON/MD reports to --output-dir
    """
    if reports_only:
        return cmd_export_reports(project_id, output_dir, db_path)

    if not all([project_id, edl_id]):
        return {"success": False, "error": "project_id and edl_id required (or use --reports-only)"}

    return cmd_assemble(edl_id, db_path)


def cmd_export_reports(project_id: str, output_dir: str, db_path: str = "") -> dict:
    """Write project reports to disk."""
    if not project_id:
        return {"success": False, "error": "project_id required"}
    if not output_dir:
        return {"success": False, "error": "output_dir required"}

    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = ReportService(db)

    try:
        return svc.export_to_disk(project_id, output_dir)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def cmd_retry(task_id: str, db_path: str = "") -> dict:
    """Retry a failed task using RemediationPlanner."""
    if not task_id:
        return {"success": False, "error": "task_id required"}

    db = Database(db_path or ":memory:")
    db.init_schema()

    task = db.fetchone(
        "SELECT task_id, project_id, status, error FROM tasks WHERE task_id = ?",
        (task_id,),
    )
    if task is None:
        return {"success": False, "error": f"Task {task_id} not found"}

    error_msg = task[3] or ""
    classification = classify_failure(error_msg)
    planner = RemediationPlanner()
    action = planner.plan(
        task_id=task[0],
        project_id=task[1],
        failure_classification=classification,
        attempt_count=0,
        error_message=error_msg,
    )

    return {
        "success": True,
        "task_id": task_id,
        "classification": classification.value,
        "action": action.action_type,
        "reason": action.reason,
        "delay_sec": action.delay_sec,
    }


def cmd_recover(project_id: str, db_path: str = "") -> dict:
    """Recover: find all failed tasks and plan remediation."""
    if not project_id:
        return {"success": False, "error": "project_id required"}

    db = Database(db_path or ":memory:")
    db.init_schema()

    failed = db.fetchall(
        """SELECT task_id, error FROM tasks
           WHERE project_id = ? AND status LIKE 'FAILED%'""",
        (project_id,),
    )

    planner = RemediationPlanner()
    plans = []
    for task_id, error_msg in failed:
        classification = classify_failure(error_msg or "")
        action = planner.plan(
            task_id=task_id,
            project_id=project_id,
            failure_classification=classification,
            attempt_count=0,
            error_message=error_msg or "",
        )
        plans.append({
            "task_id": task_id,
            "classification": classification.value,
            "action": action.action_type,
            "reason": action.reason,
        })

    return {
        "success": True,
        "project_id": project_id,
        "failed_count": len(failed),
        "plans": plans,
    }


def cmd_continuity_inspect(project_id: str, db_path: str = "") -> dict:
    """Inspect continuity states for a project."""
    if not project_id:
        return {"success": False, "error": "project_id required"}

    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = ContinuityService(db)

    pending = svc.get_pending_for_project(project_id)
    return {
        "success": True,
        "project_id": project_id,
        "pending_count": len(pending),
        "pending": [
            {
                "continuity_id": p.continuity_id,
                "shot_id": p.shot_id,
                "source_shot_id": p.source_shot_id,
                "status": p.status,
            }
            for p in pending
        ],
    }


def cmd_attempts_list(task_id: str, db_path: str = "") -> dict:
    """List all attempts for a task."""
    if not task_id:
        return {"success": False, "error": "task_id required"}

    db = Database(db_path or ":memory:")
    db.init_schema()

    attempts = db.fetchall(
        """SELECT attempt_id, status, created_at, updated_at FROM attempts
           WHERE task_id = ? ORDER BY created_at""",
        (task_id,),
    )

    return {
        "success": True,
        "task_id": task_id,
        "attempt_count": len(attempts),
        "attempts": [
            {"attempt_id": a[0], "status": a[1], "created_at": a[2], "updated_at": a[3]}
            for a in attempts
        ],
    }


# -- CLI adapters -- #


@CommandRegistry.register
class AssembleCommand:
    name = "assemble"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--edl-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_assemble(args.edl_id, args.db)
        if result.get("success"):
            return CommandResult(ok=True, command="assemble", data=result)
        return CommandResult(ok=False, command="assemble",
                            error={"code": "E_ASSEMBLE", "message": result.get("error", "")})


@CommandRegistry.register
class ExportCommand:
    name = "export"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--edl-id", default="")
        parser.add_argument("--output-dir", default="")
        parser.add_argument("--reports-only", action="store_true",
                            help="Export JSON/MD reports instead of video")
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_export(
            project_id=args.project_id,
            edl_id=args.edl_id,
            db_path=args.db,
            output_dir=args.output_dir,
            reports_only=args.reports_only,
        )
        if result.get("success"):
            return CommandResult(ok=True, command="export", data=result)
        return CommandResult(ok=False, command="export",
                            error={"code": "E_EXPORT", "message": result.get("error", "")})


@CommandRegistry.register
class RetryCommand:
    name = "retry"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--task-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_retry(args.task_id, args.db)
        if result.get("success"):
            return CommandResult(ok=True, command="retry", data=result)
        return CommandResult(ok=False, command="retry",
                            error={"code": "E_RETRY", "message": result.get("error", "")})


@CommandRegistry.register
class RecoverCommand:
    name = "recover"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_recover(args.project_id, args.db)
        if result.get("success"):
            return CommandResult(ok=True, command="recover", data=result)
        return CommandResult(ok=False, command="recover",
                            error={"code": "E_RECOVER", "message": result.get("error", "")})


@CommandRegistry.register
class ContinuityInspectCommand:
    name = "continuity_inspect"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_continuity_inspect(args.project_id, args.db)
        if result.get("success"):
            return CommandResult(ok=True, command="continuity_inspect", data=result)
        return CommandResult(ok=False, command="continuity_inspect",
                            error={"code": "E_CONTINUITY", "message": result.get("error", "")})


@CommandRegistry.register
class AttemptsListCommand:
    name = "attempts_list"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--task-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_attempts_list(args.task_id, args.db)
        if result.get("success"):
            return CommandResult(ok=True, command="attempts_list", data=result)
        return CommandResult(ok=False, command="attempts_list",
                            error={"code": "E_ATTEMPTS", "message": result.get("error", "")})
