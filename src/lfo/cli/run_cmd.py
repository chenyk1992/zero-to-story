"""lfo run command — execute pipeline for a storyboard."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.core.database import Database
from lfo.core.recovery import recover_project
from lfo.services.pipeline_service import PipelineService
from lfo.storyboard.storyboard import Storyboard

logger = logging.getLogger(__name__)


def _run_recovery(db: Database, project_id: str) -> None:
    """Run crash recovery for ``project_id`` and log a one-line summary.

    Never raises — recovery failures are logged at WARNING and the run
    continues. A user who just lost a process should still be able to
    start a new run; recovery is best-effort insurance, not a gate.
    """
    try:
        summary = recover_project(db, project_id)
    except Exception as e:
        logger.warning("Crash recovery failed: %s", e)
        return

    logger.info(
        "Recovery for %s: %d task(s) reset, %d journal(s) marked uncertain, "
        "%d lease(s) released",
        project_id,
        summary.get("tasks_reset", 0),
        summary.get("journals_marked_uncertain", 0),
        summary.get("leases_released", 0),
    )


def cmd_run(
    storyboard_path: str = "",
    db_path: str = "",
    comfy_url: str = "http://127.0.0.1:8188",
    output_dir: str = "",
    skip_images: bool = False,
    auto_approve: bool = True,
) -> dict:
    """lfo run: Execute the full pipeline for a storyboard.

    Args:
        storyboard_path: Path to storyboard JSON file
        db_path: Database path (default: in-memory)
        comfy_url: ComfyUI server URL
        output_dir: Output directory for generated assets
        skip_images: Skip character sheet image generation phase

    Returns:
        dict with pipeline results
    """
    if not storyboard_path:
        return {"success": False, "error": "storyboard_path is required"}

    sb_path = Path(storyboard_path)
    if not sb_path.exists():
        return {"success": False, "error": f"Storyboard file not found: {storyboard_path}"}

    # Load storyboard
    try:
        data = json.loads(sb_path.read_text(encoding="utf-8"))
        storyboard = Storyboard.from_dict(data)
    except Exception as e:
        return {"success": False, "error": f"Failed to load storyboard: {e}"}

    # Create DB
    db = Database(db_path or ":memory:")
    db.init_schema()

    # Crash recovery: best-effort, never blocks the run.
    # Only meaningful for persistent (on-disk) databases — an in-memory
    # DB has nothing to recover from.
    if db_path:
        _run_recovery(db, storyboard.project.project_id)

    # Run pipeline
    service = PipelineService(
        db,
        comfy_url=comfy_url,
        output_dir=output_dir,
        project_id=storyboard.project.project_id,
        # Pass explicit novel/chapter if the storyboard supplies them — this
        # avoids the dash-splitting ambiguity for non-ASCII or dash-containing
        # novel names. If the storyboard is older and only sets project_id,
        # we fall back to the legacy split-on-first-dash logic inside
        # PipelineService.
        novel_id=storyboard.project.novel_id,
        chapter_id=storyboard.project.chapter_id,
        skip_images=skip_images,
        auto_approve=auto_approve,
    )
    result = service.execute(storyboard)

    return {
        "success": result.success,
        "project_id": result.project_id,
        "total_tasks": result.total_tasks,
        "completed_tasks": result.completed_tasks,
        "failed_tasks": result.failed_tasks,
        "errors": result.errors,
        "paused": result.paused,
        "image_phase": result.image_phase,
        "task_results": [
            {
                "task_id": tr.task_id,
                "shot_id": tr.shot_id,
                "success": tr.success,
                "status": tr.status,
                "asset_id": tr.asset_id,
                "qc_passed": tr.qc_passed,
                "normalized": tr.normalized,
                "end_frame_extracted": tr.end_frame_extracted,
                "error": tr.error,
            }
            for tr in result.task_results
        ],
    }


@CommandRegistry.register
class RunCommand:
    """CLI adapter for cmd_run — registers with CommandRegistry."""

    name = "run"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("storyboard_path", help="Path to storyboard JSON file")
        parser.add_argument("--db", default="", help="Database path")
        parser.add_argument("--comfy-url", default="http://127.0.0.1:8188", help="ComfyUI URL")
        parser.add_argument("--output-dir", default="", help="Output directory")
        parser.add_argument("--skip-images", action="store_true", help="Skip character sheet image generation")
        parser.add_argument("--no-auto-approve", action="store_true", help="Don't auto-approve selections (default: auto-approve)")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_run(
            storyboard_path=args.storyboard_path,
            db_path=args.db,
            comfy_url=args.comfy_url,
            output_dir=args.output_dir,
            skip_images=args.skip_images,
            auto_approve=not args.no_auto_approve,
        )
        ok = result.get("success", False)
        if ok:
            return CommandResult(ok=True, command="run", data=result)
        else:
            return CommandResult(
                ok=False,
                command="run",
                error={"code": "E_RUN", "message": result.get("error", "unknown")},
            )
