"""lfo edit commands — select and approve selected clips."""
from __future__ import annotations

import argparse

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.core.database import Database
from lfo.services.editorial_service import EditorialService
from lfo.services.media_service import MediaService


def cmd_edit_select(
    project_id: str,
    shot_id: str,
    normalized_asset_id: str,
    in_frame: int = 0,
    out_frame: int = 0,
    db_path: str = "",
) -> dict:
    """Create a draft selection for a shot."""
    if not all([project_id, shot_id, normalized_asset_id]):
        return {"success": False, "error": "project_id, shot_id, normalized_asset_id required"}

    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = EditorialService(db, media_service=MediaService(db))

    try:
        clip = svc.create_selection(
            project_id=project_id,
            shot_id=shot_id,
            normalized_asset_id=normalized_asset_id,
            in_frame=in_frame,
            out_frame_exclusive=out_frame if out_frame > 0 else None,
        )
        return {
            "success": True,
            "selected_clip_id": clip.selected_clip_id,
            "shot_id": clip.shot_id,
            "revision": clip.revision,
            "status": clip.status,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def cmd_edit_approve(
    selected_clip_id: str,
    db_path: str = "",
) -> dict:
    """Approve a selected clip."""
    if not selected_clip_id:
        return {"success": False, "error": "selected_clip_id required"}

    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = EditorialService(db, media_service=MediaService(db))

    try:
        approved = svc.approve_selected_clip(selected_clip_id)
        return {
            "success": True,
            "selected_clip_id": approved.selected_clip_id,
            "status": approved.status,
            "approved_at": approved.approved_at,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@CommandRegistry.register
class EditSelectCommand:
    name = "edit_select"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--shot-id", required=True)
        parser.add_argument("--normalized-asset-id", required=True)
        parser.add_argument("--in-frame", type=int, default=0)
        parser.add_argument("--out-frame", type=int, default=0)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_edit_select(
            project_id=args.project_id,
            shot_id=args.shot_id,
            normalized_asset_id=args.normalized_asset_id,
            in_frame=args.in_frame,
            out_frame=args.out_frame,
            db_path=args.db,
        )
        if result.get("success"):
            return CommandResult(ok=True, command="edit_select", data=result)
        return CommandResult(ok=False, command="edit_select",
                            error={"code": "E_EDIT_SELECT", "message": result.get("error", "")})


@CommandRegistry.register
class EditApproveCommand:
    name = "edit_approve"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--selected-clip-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_edit_approve(
            selected_clip_id=args.selected_clip_id,
            db_path=args.db,
        )
        if result.get("success"):
            return CommandResult(ok=True, command="edit_approve", data=result)
        return CommandResult(ok=False, command="edit_approve",
                            error={"code": "E_EDIT_APPROVE", "message": result.get("error", "")})
