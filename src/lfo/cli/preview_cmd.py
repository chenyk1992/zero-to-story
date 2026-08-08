"""lfo preview command — build storyboard preview image requests and collect results.

Two modes:
  lfo preview build <storyboard.json>   — build preview sheet requests
  lfo preview collect <storyboard.json> — collect agent generation results
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.core.database import Database
from lfo.services.storyboard_preview_service import StoryboardPreviewService
from lfo.storyboard.storyboard import Storyboard
from lfo.visual.image_request import read_batch


def cmd_preview_build(
    storyboard_path: str = "",
    db_path: str = "",
    output_dir: str = "",
) -> dict:
    """Build storyboard preview image requests.

    Args:
        storyboard_path: Path to storyboard JSON file
        db_path: Database path (unused, for API consistency)
        output_dir: Output directory for generated assets

    Returns:
        dict with build results
    """
    if not storyboard_path:
        return {"success": False, "error": "storyboard_path is required"}

    sb_path = Path(storyboard_path)
    if not sb_path.exists():
        return {"success": False, "error": f"Storyboard file not found: {storyboard_path}"}

    try:
        data = json.loads(sb_path.read_text(encoding="utf-8"))
        storyboard = Storyboard.from_dict(data)
    except Exception as e:
        return {"success": False, "error": f"Failed to load storyboard: {e}"}

    if not storyboard.panels:
        return {"success": False, "error": "No panels in storyboard"}

    db = Database(db_path or ":memory:")
    db.init_schema()

    service = StoryboardPreviewService(db, output_root=output_dir)
    batch = service.build_requests(storyboard, storyboard.project.project_id)

    if not batch.requests:
        return {
            "success": True,
            "status": "skipped",
            "message": "No panels to preview",
            "requests_count": 0,
        }

    batch_path = service.write_requests(batch, storyboard.project.novel_id, storyboard.project.chapter_id)
    results_path = batch_path.with_name(f"{batch.batch_id}_results.json")

    return {
        "success": True,
        "status": "waiting",
        "requests_count": len(batch.requests),
        "total_panels": len(storyboard.panels),
        "batch_id": batch.batch_id,
        "batch_path": str(batch_path),
        "results_path": str(results_path),
        "message": (
            f"{len(batch.requests)} preview sheet request(s) written to {batch_path} "
            f"({len(storyboard.panels)} panels across {len(batch.requests)} sheets). "
            f"Use your agent to generate images, then run "
            f"'lfo preview collect {storyboard_path}' to collect results."
        ),
    }


def cmd_preview_collect(
    storyboard_path: str = "",
    db_path: str = "",
    output_dir: str = "",
) -> dict:
    """Collect agent preview sheet generation results.

    Args:
        storyboard_path: Path to storyboard JSON file
        db_path: Database path (unused, for API consistency)
        output_dir: Output directory for generated assets

    Returns:
        dict with collection results
    """
    if not storyboard_path:
        return {"success": False, "error": "storyboard_path is required"}

    sb_path = Path(storyboard_path)
    if not sb_path.exists():
        return {"success": False, "error": f"Storyboard file not found: {storyboard_path}"}

    try:
        data = json.loads(sb_path.read_text(encoding="utf-8"))
        storyboard = Storyboard.from_dict(data)
    except Exception as e:
        return {"success": False, "error": f"Failed to load storyboard: {e}"}

    db = Database(db_path or ":memory:")
    db.init_schema()

    # Find the most recent preview batch file with results
    service = StoryboardPreviewService(db, output_root=output_dir)
    batch_dir = service.output_root / storyboard.project.novel_id / storyboard.project.chapter_id / "image_requests"
    if not batch_dir.exists():
        return {
            "success": False,
            "error": f"No image_requests directory found at {batch_dir}. "
                     f"Run 'lfo preview build {storyboard_path}' first.",
        }

    # Find preview batch files (not results) that have corresponding results
    batch_files = sorted(
        [
            f for f in batch_dir.glob("batch_preview_*.json")
            if not f.name.endswith("_results.json")
            and f.with_name(f"{f.stem}_results.json").exists()
        ],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not batch_files:
        pending = [
            f for f in batch_dir.glob("batch_preview_*.json")
            if not f.name.endswith("_results.json")
        ]
        if pending:
            return {
                "success": False,
                "error": "Results file not found. Generate images with your agent first.",
            }
        return {
            "success": False,
            "error": f"No preview batch files found in {batch_dir}. "
                     f"Run 'lfo preview build {storyboard_path}' first.",
        }

    # Use the most recent batch file with results
    batch_path = batch_files[0]
    results_path = batch_path.with_name(f"{batch_path.stem}_results.json")

    # Load batch and collect results
    batch = read_batch(str(batch_path))
    collected = service.collect_results(batch, str(results_path), storyboard)

    success_count = sum(1 for c in collected if c.success)
    fail_count = sum(1 for c in collected if not c.success)

    return {
        "success": True,
        "status": "collected",
        "batch_id": batch.batch_id,
        "total": len(collected),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": [
            {
                "sheet_id": c.sheet_id,
                "success": c.success,
                "asset_id": c.asset_id,
                "file_path": c.file_path,
                "error": c.error,
            }
            for c in collected
        ],
    }


@CommandRegistry.register
class PreviewCommand:
    """CLI adapter for lfo preview — build and collect preview sheet requests."""

    name = "preview"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="action", help="Action to perform")
        build_parser = subparsers.add_parser("build", help="Build preview sheet image requests")
        build_parser.add_argument("storyboard_path", help="Path to storyboard JSON file")
        build_parser.add_argument("--db", default="", help="Database path")
        build_parser.add_argument("--output-dir", default="", help="Output directory")

        collect_parser = subparsers.add_parser("collect", help="Collect agent preview generation results")
        collect_parser.add_argument("storyboard_path", help="Path to storyboard JSON file")
        collect_parser.add_argument("--db", default="", help="Database path")
        collect_parser.add_argument("--output-dir", default="", help="Output directory")

    @staticmethod
    def execute(context, args) -> CommandResult:
        action = getattr(args, "action", None)
        if action == "build":
            result = cmd_preview_build(
                storyboard_path=args.storyboard_path,
                db_path=args.db,
                output_dir=args.output_dir,
            )
        elif action == "collect":
            result = cmd_preview_collect(
                storyboard_path=args.storyboard_path,
                db_path=args.db,
                output_dir=args.output_dir,
            )
        else:
            return CommandResult(
                ok=False,
                command="preview",
                error={"code": "E_ACTION", "message": "Specify 'build' or 'collect'"},
            )

        ok = result.get("success", False)
        if ok:
            return CommandResult(ok=True, command="preview", data=result)
        else:
            return CommandResult(
                ok=False,
                command="preview",
                error={"code": "E_PREVIEW", "message": result.get("error", "unknown")},
            )
