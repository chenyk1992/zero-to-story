"""Regression tests for tracked user-facing templates."""
from __future__ import annotations

import json
from pathlib import Path

from lfo.planning.panel_pack import validate_panel_pack
from lfo.services.panel_generation_service import PanelGenerationService
from lfo.storyboard.storyboard import Storyboard
from lfo.storyboard.validate import validate_storyboard

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def test_minimal_storyboard_is_current_panel_first_example() -> None:
    data = json.loads(
        (TEMPLATES_DIR / "storyboard.minimal.json").read_text(encoding="utf-8")
    )

    validation = validate_storyboard(data)
    assert validation.valid, [error.to_dict() for error in validation.errors]
    assert "shots" not in data

    storyboard = Storyboard.from_dict(data)
    assert len(storyboard.beats) == 8
    assert len(storyboard.panels) == 1

    panel = storyboard.panels[0]
    assert panel.beat_range == (1, 8)
    assert panel.beat_ids == [beat.beat_id for beat in storyboard.beats]
    assert panel.desired_duration_ms == 15_000
    assert panel.pack is not None
    assert validate_panel_pack(panel.pack, max_ref_images=3) == []
    assert panel.pack.refs[-1].role == "composition"


def test_minimal_storyboard_compiles_confirmed_r2v_prompt() -> None:
    data = json.loads(
        (TEMPLATES_DIR / "storyboard.minimal.json").read_text(encoding="utf-8")
    )
    storyboard = Storyboard.from_dict(data)

    plan = PanelGenerationService().generate_plan(
        storyboard,
        storyboard.project.project_id,
    )

    assert len(plan.panel_plans) == 1
    panel_plan = plan.panel_plans[0]
    assert panel_plan.workflow_mode == "r2v"
    assert panel_plan.selection_status == "confirmed"
    assert "不要背景音乐" in panel_plan.prompt_text
    assert storyboard.style.medium_lock in panel_plan.prompt_text
