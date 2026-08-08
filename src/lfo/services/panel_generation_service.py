"""PanelGenerationService — generate Hub-style video plans from storyboard panels."""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.planning.hub_style_prompt import compile_hub_style_panel_prompt
from lfo.planning.panel_pack import PanelPack, build_panel_pack
from lfo.planning.workflow_selector import select_workflow_for_panel
from lfo.storyboard.storyboard import Beat, Panel, Storyboard


@dataclass
class PanelGenerationPlan:
    """Generation plan for a single panel."""

    panel_id: str
    workflow_mode: str
    workflow_id: str
    selection_status: str
    prompt_text: str
    pack: PanelPack
    task_type: str = "video.h3"
    missing_requirements: list[str] = field(default_factory=list)


@dataclass
class GenerationPlan:
    """Complete generation plan for a storyboard."""

    project_id: str
    panel_plans: list[PanelGenerationPlan] = field(default_factory=list)


class PanelGenerationService:
    """Generate Hub-style prompts and workflow plans from storyboard panels."""

    def generate_plan(
        self,
        storyboard: Storyboard,
        project_id: str,
        *,
        max_ref_images: int = 3,
        available_assets: dict | None = None,
    ) -> GenerationPlan:
        """Build a generation plan for every panel in the storyboard."""
        plan = GenerationPlan(project_id=project_id)
        assets = available_assets or {}

        for index, panel in enumerate(storyboard.panels):
            panel_plan = self._plan_panel(
                panel,
                storyboard,
                panel_index=index,
                max_ref_images=max_ref_images,
                available_assets=assets,
            )
            plan.panel_plans.append(panel_plan)

        return plan

    def _plan_panel(
        self,
        panel: Panel,
        storyboard: Storyboard,
        *,
        panel_index: int,
        max_ref_images: int,
        available_assets: dict,
    ) -> PanelGenerationPlan:
        pack = self._resolve_pack(
            panel,
            storyboard,
            max_ref_images=max_ref_images,
            available_assets=available_assets,
        )
        selection = select_workflow_for_panel(
            pack,
            max_ref_images=max_ref_images,
            available_assets=available_assets or None,
        )
        beats = _beats_for_panel(storyboard, panel)
        prompt_text = compile_hub_style_panel_prompt(
            pack=pack,
            opening=_opening_for_panel(panel_index, beats),
            action_chain=_action_chain_from_beats(beats),
            sound_design=_sound_design_from_beats(beats),
            medium_lock=storyboard.style.medium_lock,
        )
        return PanelGenerationPlan(
            panel_id=panel.panel_id,
            workflow_mode=selection.workflow_mode,
            workflow_id=selection.workflow_id,
            selection_status=selection.selection_status,
            prompt_text=prompt_text,
            pack=pack,
            missing_requirements=list(selection.missing_requirements),
        )

    def _resolve_pack(
        self,
        panel: Panel,
        storyboard: Storyboard,
        *,
        max_ref_images: int,
        available_assets: dict,
    ) -> PanelPack:
        if panel.pack is not None:
            return panel.pack

        character_assets = _character_assets_for_panel(
            panel,
            storyboard,
            available_assets,
        )
        return build_panel_pack(
            panel_id=panel.panel_id,
            beat_range=panel.beat_range,
            bw_asset_id=panel.bw_asset_id,
            character_assets=character_assets,
            max_ref_images=max_ref_images,
        )


def _beats_for_panel(storyboard: Storyboard, panel: Panel) -> list[Beat]:
    beats: list[Beat] = []
    for beat_id in panel.beat_ids:
        beat = storyboard.beat_by_id(beat_id)
        if beat is not None:
            beats.append(beat)
    if beats:
        return beats

    start, end = panel.beat_range
    return [b for b in storyboard.beats if start <= b.sequence <= end]


def _character_ids_for_panel(panel: Panel, storyboard: Storyboard) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for beat in _beats_for_panel(storyboard, panel):
        for appearance in beat.characters:
            if appearance.character_id and appearance.character_id not in seen:
                seen.add(appearance.character_id)
                ordered.append(appearance.character_id)
    return ordered


def _character_assets_for_panel(
    panel: Panel,
    storyboard: Storyboard,
    available_assets: dict,
) -> list[tuple[str, str]]:
    assets: list[tuple[str, str]] = []
    for character_id in _character_ids_for_panel(panel, storyboard):
        entity_assets = available_assets.get(character_id, {})
        ref = entity_assets.get("character_ref", {})
        if ref.get("status") == "approved" and ref.get("asset_id"):
            assets.append((character_id, str(ref["asset_id"])))
    return assets


def _opening_for_panel(panel_index: int, beats: list[Beat]) -> str:
    if panel_index == 0:
        return ""
    if beats and beats[0].description.strip():
        return f"承接：{beats[0].description.strip()}"
    return "承接上一段动作末态。"


def _action_chain_from_beats(beats: list[Beat]) -> str:
    descriptions = [beat.description.strip() for beat in beats if beat.description.strip()]
    return " ".join(descriptions)


def _sound_design_from_beats(beats: list[Beat]) -> str:
    sounds = [beat.sound.strip() for beat in beats if beat.sound.strip()]
    return "；".join(sounds)
