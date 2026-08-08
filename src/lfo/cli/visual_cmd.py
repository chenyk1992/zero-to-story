"""lfo visual commands — profile, provider, task, result, route."""
from __future__ import annotations

import argparse
import json
from typing import Any

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.core.database import Database

# ---------------------------------------------------------------------------
# Profile commands
# ---------------------------------------------------------------------------

def _ensure_project(db: Database, project_id: str) -> None:
    """Create project if it doesn't exist."""
    existing = db.fetchone(
        "SELECT project_id FROM projects WHERE project_id = ?", (project_id,)
    )
    if existing is None:
        db.execute(
            "INSERT INTO projects (project_id, name) VALUES (?, ?)",
            (project_id, project_id),
        )


def cmd_visual_profile_show(db_path: str, project_id: str) -> dict:
    """Show active profile for a project."""
    from lfo.application.visual_profile_service import VisualProfileService
    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = VisualProfileService(db)
    active = svc.get_active(project_id)
    db.close()
    if active is None:
        return {"found": False, "project_id": project_id}
    return {"found": True, **active}


def cmd_visual_profile_create(
    db_path: str,
    project_id: str,
    content: dict[str, Any],
    *,
    create_project: bool = True,
) -> dict:
    """Create a profile draft for a project."""
    from lfo.application.visual_profile_service import VisualProfileService
    db = Database(db_path or ":memory:")
    try:
        db.init_schema()
        if create_project:
            _ensure_project(db, project_id)
        svc = VisualProfileService(db)
        revision_id = svc.create_draft(project_id, content)
        return {"revision_id": revision_id}
    finally:
        db.close()


def cmd_visual_profile_activate(db_path: str, revision_id: str) -> dict:
    """Activate a profile revision."""
    from lfo.application.visual_profile_service import VisualProfileService
    db = Database(db_path or ":memory:")
    try:
        db.init_schema()
        svc = VisualProfileService(db)
        svc.activate(revision_id)
        return {"activated": revision_id}
    finally:
        db.close()


def cmd_visual_profile_clone(db_path: str, revision_id: str) -> dict:
    """Clone a profile revision as a new draft."""
    from lfo.application.visual_profile_service import VisualProfileService
    db = Database(db_path or ":memory:")
    try:
        db.init_schema()
        svc = VisualProfileService(db)
        new_id = svc.clone(revision_id)
        return {"clone_revision_id": new_id, "parent_revision_id": revision_id}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Provider commands
# ---------------------------------------------------------------------------

def cmd_visual_provider_list(db_path: str) -> dict:
    """List all provider revisions."""
    db = Database(db_path or ":memory:")
    db.init_schema()
    rows = db.fetchall(
        "SELECT revision_id, provider_id, scope_type, scope_id, "
        "provider_type, status FROM visual_provider_revisions"
    )
    db.close()
    return {
        "providers": [
            {
                "revision_id": r["revision_id"],
                "provider_id": r["provider_id"],
                "scope_type": r["scope_type"],
                "scope_id": r["scope_id"],
                "provider_type": r["provider_type"],
                "status": r["status"],
            }
            for r in rows
        ]
    }


def cmd_visual_provider_create(
    db_path: str,
    provider_id: str,
    scope_type: str,
    scope_id: str,
    provider_type: str,
    config: dict[str, Any],
    capabilities: dict[str, Any],
) -> dict:
    """Create a provider revision draft."""
    from lfo.application.visual_provider_service import VisualProviderService
    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = VisualProviderService(db)
    revision_id = svc.create_draft(
        provider_id=provider_id,
        scope_type=scope_type,
        scope_id=scope_id,
        provider_type=provider_type,
        adapter_name="cli",
        config=config,
        capabilities=capabilities,
    )
    db.close()
    return {"revision_id": revision_id}


def cmd_visual_provider_disable(db_path: str, revision_id: str) -> dict:
    """Disable a provider revision."""
    from lfo.application.visual_provider_service import VisualProviderService
    db = Database(db_path or ":memory:")
    db.init_schema()
    svc = VisualProviderService(db)
    svc.disable(revision_id)
    db.close()
    return {"disabled": revision_id}


# ---------------------------------------------------------------------------
# Task commands
# ---------------------------------------------------------------------------

def cmd_visual_task_list(db_path: str, status: str | None = None) -> dict:
    """List visual tasks, optionally filtered by status."""
    db = Database(db_path or ":memory:")
    db.init_schema()
    if status:
        rows = db.fetchall(
            """SELECT t.task_id, t.task_type, t.status, vc.visual_stage
               FROM tasks t
               JOIN visual_task_contracts vc ON t.task_id = vc.task_id
               WHERE t.task_type LIKE 'visual.%' AND t.status = ?
               ORDER BY t.created_at""",
            (status,),
        )
    else:
        rows = db.fetchall(
            """SELECT t.task_id, t.task_type, t.status, vc.visual_stage
               FROM tasks t
               JOIN visual_task_contracts vc ON t.task_id = vc.task_id
               WHERE t.task_type LIKE 'visual.%'
               ORDER BY t.created_at"""
        )
    db.close()
    return {
        "tasks": [
            {
                "task_id": r["task_id"],
                "task_type": r["task_type"],
                "status": r["status"],
                "visual_stage": r["visual_stage"],
            }
            for r in rows
        ]
    }


def cmd_visual_task_show(db_path: str, task_id: str) -> dict:
    """Show details of a visual task."""
    db = Database(db_path or ":memory:")
    db.init_schema()
    task = db.fetchone(
        "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
    )
    contract = db.fetchone(
        "SELECT * FROM visual_task_contracts WHERE task_id = ?", (task_id,)
    )
    db.close()
    if task is None:
        return {"found": False}
    return {
        "found": True,
        "task": dict(task),
        "contract": dict(contract) if contract else None,
    }


# ---------------------------------------------------------------------------
# Route dry-run
# ---------------------------------------------------------------------------

def cmd_visual_route_dry_run(
    db_path: str,
    project_id: str,
    purpose: str,
    required_capabilities: list[str] | None = None,
) -> dict:
    """Simulate routing without modifying state."""
    from lfo.application.visual_routing_service import VisualRoutingService
    db = Database(db_path or ":memory:")
    db.init_schema()
    rs = VisualRoutingService(db)
    result = rs.dry_run(
        project_id=project_id,
        purpose=purpose,
        required_capabilities=required_capabilities or [],
    )
    db.close()
    return result


# ---------------------------------------------------------------------------
# CLI adapter classes
# ---------------------------------------------------------------------------

@CommandRegistry.register
class VisualProfileShowCommand:
    name = "visual_profile_show"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_visual_profile_show(args.db, args.project_id)
        return CommandResult(ok=result.get("found", True), command="visual_profile_show", data=result)


@CommandRegistry.register
class VisualProfileCreateCommand:
    name = "visual_profile_create"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--content", required=True, help="JSON string")
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        content = json.loads(args.content)
        result = cmd_visual_profile_create(args.db, args.project_id, content)
        return CommandResult(ok=True, command="visual_profile_create", data=result)


@CommandRegistry.register
class VisualProfileActivateCommand:
    name = "visual_profile_activate"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--revision-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_visual_profile_activate(args.db, args.revision_id)
        return CommandResult(ok=True, command="visual_profile_activate", data=result)


@CommandRegistry.register
class VisualProfileCloneCommand:
    name = "visual_profile_clone"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--revision-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_visual_profile_clone(args.db, args.revision_id)
        return CommandResult(ok=True, command="visual_profile_clone", data=result)


@CommandRegistry.register
class VisualProviderListCommand:
    name = "visual_provider_list"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_visual_provider_list(args.db)
        return CommandResult(ok=True, command="visual_provider_list", data=result)


@CommandRegistry.register
class VisualProviderCreateCommand:
    name = "visual_provider_create"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--provider-id", required=True)
        parser.add_argument("--scope-type", default="global")
        parser.add_argument("--scope-id", default="*")
        parser.add_argument("--provider-type", default="managed")
        parser.add_argument("--config", required=True, help="JSON string")
        parser.add_argument("--capabilities", required=True, help="JSON string")
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        config = json.loads(args.config)
        capabilities = json.loads(args.capabilities)
        result = cmd_visual_provider_create(
            args.db, args.provider_id, args.scope_type, args.scope_id,
            args.provider_type, config, capabilities,
        )
        return CommandResult(ok=True, command="visual_provider_create", data=result)


@CommandRegistry.register
class VisualProviderDisableCommand:
    name = "visual_provider_disable"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--revision-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_visual_provider_disable(args.db, args.revision_id)
        return CommandResult(ok=True, command="visual_provider_disable", data=result)


@CommandRegistry.register
class VisualTaskListCommand:
    name = "visual_task_list"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--status", default=None)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_visual_task_list(args.db, args.status)
        return CommandResult(ok=True, command="visual_task_list", data=result)


@CommandRegistry.register
class VisualTaskShowCommand:
    name = "visual_task_show"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--task-id", required=True)
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        result = cmd_visual_task_show(args.db, args.task_id)
        return CommandResult(ok=result.get("found", True), command="visual_task_show", data=result)


@CommandRegistry.register
class VisualRouteDryRunCommand:
    name = "visual_route_dry_run"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--purpose", required=True)
        parser.add_argument("--capabilities", default="")
        parser.add_argument("--db", default="")

    @staticmethod
    def execute(context, args) -> CommandResult:
        caps = [c.strip() for c in args.capabilities.split(",") if c.strip()] if args.capabilities else []
        result = cmd_visual_route_dry_run(args.db, args.project_id, args.purpose, caps)
        return CommandResult(ok=True, command="visual_route_dry_run", data=result)
