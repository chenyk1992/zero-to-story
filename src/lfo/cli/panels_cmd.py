"""lfo panels command — plan, pack, and prompt for panel-level video production.

Commands:
  lfo panels plan --storyboard <path>     # print beat/panel counts + ranges
  lfo panels pack --storyboard <path> [--max-ref-images 3]
      # write workspace/.../panels/panel_XX_pack.json for each panel
  lfo panels prompt --storyboard <path>   # write/update video_prompt_list.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry
from lfo.planning.panel_pack import panel_pack_from_dict, panel_pack_to_dict
from lfo.services.panel_generation_service import PanelGenerationService
from lfo.services.workspace import project_dir, project_panels_dir
from lfo.storyboard.storyboard import Panel, ProjectInfo, Storyboard


def _load_storyboard(storyboard_path: str) -> tuple[Storyboard | None, str | None]:
    if not storyboard_path:
        return None, "storyboard_path is required"

    sb_path = Path(storyboard_path)
    if not sb_path.exists():
        return None, f"Storyboard file not found: {storyboard_path}"

    try:
        data = json.loads(sb_path.read_text(encoding="utf-8"))
        return Storyboard.from_dict(data), None
    except Exception as exc:
        return None, f"Failed to load storyboard: {exc}"


def _resolve_novel_chapter(project: ProjectInfo) -> tuple[str, str]:
    if project.novel_id and project.chapter_id:
        return project.novel_id, project.chapter_id
    project_id = project.project_id
    if "-" in project_id:
        novel_id, chapter_id = project_id.split("-", 1)
        return novel_id, chapter_id
    return project_id, project_id


def _available_assets_from_storyboard(storyboard: Storyboard) -> dict:
    assets: dict = {}
    for character in storyboard.characters:
        if character.ref_asset_id:
            assets[character.character_id] = {
                "character_ref": {
                    "status": "approved",
                    "asset_id": character.ref_asset_id,
                },
            }
    return assets


def _panel_pack_path(panels_dir: Path, panel: Panel) -> Path:
    return panels_dir / f"panel_{panel.sequence:02d}_pack.json"


def _load_panel_pack_from_disk(panels_dir: Path, panel: Panel) -> bool:
    pack_path = _panel_pack_path(panels_dir, panel)
    if not pack_path.exists():
        return False
    data = json.loads(pack_path.read_text(encoding="utf-8"))
    panel.pack = panel_pack_from_dict(data)
    return True


def cmd_panels_plan(storyboard_path: str = "") -> dict:
    """Print beat/panel counts and beat ranges per panel."""
    storyboard, error = _load_storyboard(storyboard_path)
    if storyboard is None:
        return {"success": False, "error": error}

    if not storyboard.panels:
        return {"success": False, "error": "No panels in storyboard"}

    panels_summary = [
        {
            "panel_id": panel.panel_id,
            "sequence": panel.sequence,
            "beat_range": list(panel.beat_range),
            "desired_duration_ms": panel.desired_duration_ms,
            "bw_asset_id": panel.bw_asset_id,
        }
        for panel in storyboard.panels
    ]

    return {
        "success": True,
        "beat_count": len(storyboard.beats),
        "panel_count": len(storyboard.panels),
        "panels": panels_summary,
    }


def cmd_panels_pack(
    storyboard_path: str = "",
    *,
    max_ref_images: int = 3,
) -> dict:
    """Write panel_XX_pack.json for each panel under workspace panels dir."""
    storyboard, error = _load_storyboard(storyboard_path)
    if storyboard is None:
        return {"success": False, "error": error}

    if not storyboard.panels:
        return {"success": False, "error": "No panels in storyboard"}

    novel_id, chapter_id = _resolve_novel_chapter(storyboard.project)
    panels_dir = project_panels_dir(novel_id, chapter_id)
    panels_dir.mkdir(parents=True, exist_ok=True)

    service = PanelGenerationService()
    available_assets = _available_assets_from_storyboard(storyboard)
    plan = service.generate_plan(
        storyboard,
        storyboard.project.project_id,
        max_ref_images=max_ref_images,
        available_assets=available_assets,
    )

    written: list[str] = []
    for panel_plan in plan.panel_plans:
        panel = next(
            (p for p in storyboard.panels if p.panel_id == panel_plan.panel_id),
            None,
        )
        if panel is None:
            continue
        pack_path = _panel_pack_path(panels_dir, panel)
        pack_path.write_text(
            json.dumps(panel_pack_to_dict(panel_plan.pack), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append(str(pack_path))

    return {
        "success": True,
        "written_count": len(written),
        "max_ref_images": max_ref_images,
        "panels_dir": str(panels_dir),
        "pack_paths": written,
    }


def _render_video_prompt_list(storyboard: Storyboard, panel_plans: list) -> str:
    title = storyboard.project.title or storyboard.project.project_id
    lines = [
        f"# {title} — Video Generation Prompts",
        "",
        "## 项目信息",
        f"- **项目**: {storyboard.project.project_id}",
        f"- **Panel 数**: {len(storyboard.panels)}",
        f"- **Beat 数**: {len(storyboard.beats)}",
        "",
        "## Medium Lock",
        storyboard.style.medium_lock or "",
        "",
        "---",
        "",
    ]

    for panel_plan in panel_plans:
        panel = next(
            (p for p in storyboard.panels if p.panel_id == panel_plan.panel_id),
            None,
        )
        sequence = panel.sequence if panel is not None else 0
        lines.extend([
            f"## Panel {sequence} ({panel_plan.panel_id})",
            "",
            f"- **workflow**: {panel_plan.workflow_mode} / {panel_plan.workflow_id}",
            f"- **beat_range**: {list(panel.beat_range) if panel else []}",
            "",
            panel_plan.prompt_text,
            "",
            "---",
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"


def cmd_panels_prompt(storyboard_path: str = "", *, max_ref_images: int = 3) -> dict:
    """Write or update video_prompt_list.md with Hub-style panel sections."""
    storyboard, error = _load_storyboard(storyboard_path)
    if storyboard is None:
        return {"success": False, "error": error}

    if not storyboard.panels:
        return {"success": False, "error": "No panels in storyboard"}

    novel_id, chapter_id = _resolve_novel_chapter(storyboard.project)
    panels_dir = project_panels_dir(novel_id, chapter_id)

    for panel in storyboard.panels:
        _load_panel_pack_from_disk(panels_dir, panel)

    service = PanelGenerationService()
    available_assets = _available_assets_from_storyboard(storyboard)
    plan = service.generate_plan(
        storyboard,
        storyboard.project.project_id,
        max_ref_images=max_ref_images,
        available_assets=available_assets,
    )

    project_path = project_dir(novel_id, chapter_id)
    project_path.mkdir(parents=True, exist_ok=True)
    prompt_path = project_path / "video_prompt_list.md"
    prompt_path.write_text(
        _render_video_prompt_list(storyboard, plan.panel_plans),
        encoding="utf-8",
    )

    return {
        "success": True,
        "panel_count": len(plan.panel_plans),
        "prompt_path": str(prompt_path),
    }


@CommandRegistry.register
class PanelsCommand:
    """CLI adapter for lfo panels — plan, pack, and prompt."""

    name = "panels"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="action", help="Action to perform")

        plan_parser = subparsers.add_parser("plan", help="Show beat/panel counts and ranges")
        plan_parser.add_argument("--storyboard", required=True, help="Path to storyboard JSON")

        pack_parser = subparsers.add_parser("pack", help="Write panel pack JSON files")
        pack_parser.add_argument("--storyboard", required=True, help="Path to storyboard JSON")
        pack_parser.add_argument(
            "--max-ref-images",
            type=int,
            default=3,
            help="Maximum reference images per panel (default: 3)",
        )

        prompt_parser = subparsers.add_parser(
            "prompt",
            help="Write video_prompt_list.md Hub-style sections",
        )
        prompt_parser.add_argument("--storyboard", required=True, help="Path to storyboard JSON")
        prompt_parser.add_argument(
            "--max-ref-images",
            type=int,
            default=3,
            help="Maximum reference images per panel (default: 3)",
        )

    @staticmethod
    def execute(context, args) -> CommandResult:
        action = getattr(args, "action", None)
        if action == "plan":
            result = cmd_panels_plan(storyboard_path=args.storyboard)
        elif action == "pack":
            result = cmd_panels_pack(
                storyboard_path=args.storyboard,
                max_ref_images=args.max_ref_images,
            )
        elif action == "prompt":
            result = cmd_panels_prompt(
                storyboard_path=args.storyboard,
                max_ref_images=args.max_ref_images,
            )
        else:
            return CommandResult(
                ok=False,
                command="panels",
                error={"code": "E_ACTION", "message": "Specify 'plan', 'pack', or 'prompt'"},
            )

        if result.get("success", False):
            return CommandResult(ok=True, command="panels", data=result)
        return CommandResult(
            ok=False,
            command="panels",
            error={"code": "E_PANELS", "message": result.get("error", "unknown")},
        )
