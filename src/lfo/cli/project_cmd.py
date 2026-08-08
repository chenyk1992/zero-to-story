"""lfo project init command — initialize a project with default profile."""
from __future__ import annotations

import argparse

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.core.database import Database


def cmd_project_init(
    db_path: str,
    project_id: str,
    *,
    visual_input_policy: str = "allow_t2va_fallback",
    created_by: str = "system",
) -> dict:
    """Initialize a project with a default visual generation profile.

    Creates the project if it doesn't exist, then creates and activates
    a default profile revision.

    Args:
        db_path: Database path.
        project_id: The project ID.
        visual_input_policy: The visual input policy.
        created_by: User/system identifier.

    Returns:
        Dict with project_id and revision_id.
    """
    from lfo.application.visual_profile_service import VisualProfileService
    db = Database(db_path or ":memory:")
    db.init_schema()

    # Create project if not exists
    existing = db.fetchone(
        "SELECT project_id FROM projects WHERE project_id = ?", (project_id,)
    )
    if existing is None:
        db.execute(
            "INSERT INTO projects (project_id, name) VALUES (?, ?)",
            (project_id, project_id),
        )

    # Create and activate default profile
    profile_svc = VisualProfileService(db)
    content = {
        "visual_input_policy": visual_input_policy,
        "technical_checks": ["decodable", "hash", "dimensions", "mime_type"],
        "review_checklist": ["identity", "costume", "composition"],
    }
    revision_id = profile_svc.create_draft(project_id, content, created_by=created_by)
    profile_svc.activate(revision_id)

    db.close()
    return {
        "project_id": project_id,
        "profile_revision_id": revision_id,
        "visual_input_policy": visual_input_policy,
    }


@CommandRegistry.register
class ProjectInitCommand:
    name = "project_init"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--visual-input-policy", default="allow_t2va_fallback")
        parser.add_argument("--created-by", default="system")
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_project_init(
            args.db,
            args.project_id,
            visual_input_policy=args.visual_input_policy,
            created_by=args.created_by,
        )
        return CommandResult(ok=True, command="project_init", data=result)
