#!/usr/bin/env python3
"""Validate the low-cost creative contract used before media generation.

The creative blueprint is a machine-readable index compiled from the human
readable ``storyboard_brief.md``.  It catches omissions and continuity breaks
before character images, storyboard boards, or videos are generated.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

SCHEMA = "zero-to-story.creative-blueprint.v1"
MANDATORY_PRIORITIES = {"must_show", "must_explain"}
VALID_PRIORITIES = MANDATORY_PRIORITIES | {"optional"}
VALID_TEXT_STRATEGIES = {"none", "post"}
VALID_TRANSITION_OWNERS = {"previous", "next"}
PLACEHOLDER_MARKERS = ("[填写", "[项目", "[原文", "TODO", "TBD", "待填写")

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Issue:
    """One actionable creative preflight issue."""

    path: str
    message: str

    def as_dict(self) -> JsonObject:
        return {"path": self.path, "message": self.message}

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def _is_mapping(value: object) -> bool:
    return isinstance(value, Mapping)


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_placeholder(value: str) -> bool:
    text = value.strip()
    return (text.startswith("[") and text.endswith("]")) or any(
        marker in text for marker in PLACEHOLDER_MARKERS
    )


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _state(value: object) -> bool:
    return _is_mapping(value) and bool(value)


def _list_of_text(value: object, *, allow_empty: bool = False) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(
        _is_nonempty_text(item) for item in value
    )


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if _is_mapping(value) else None


def _record_list(
    root: Mapping[str, Any],
    key: str,
    issues: list[Issue],
) -> list[Mapping[str, Any]]:
    value = root.get(key)
    if not isinstance(value, list) or not value:
        issues.append(Issue(key, "must be a non-empty array"))
        return []
    records: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not _is_mapping(item):
            issues.append(Issue(f"{key}[{index}]", "must be an object"))
            continue
        records.append(item)
    return records


def _ordered_records(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    issues: list[Issue],
) -> tuple[dict[str, Mapping[str, Any]], list[Mapping[str, Any]]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    order_values: list[int] = []
    for index, record in enumerate(records):
        path = f"{label}[{index}]"
        record_id = record.get("id")
        if not _is_nonempty_text(record_id):
            issues.append(Issue(f"{path}.id", "must be non-empty text"))
        elif record_id in by_id:
            issues.append(Issue(f"{path}.id", f"duplicates {record_id!r}"))
        else:
            by_id[record_id] = record

        order = record.get("order")
        if not _is_positive_int(order):
            issues.append(Issue(f"{path}.order", "must be a positive integer"))
        else:
            order_values.append(order)

    if order_values and sorted(order_values) != list(range(1, len(order_values) + 1)):
        issues.append(Issue(label, "order must be a contiguous sequence starting at 1"))

    ordered = sorted(
        (record for record in records if _is_positive_int(record.get("order"))),
        key=lambda record: record["order"],
    )
    return by_id, ordered


def _require_text(
    record: Mapping[str, Any],
    field: str,
    path: str,
    issues: list[Issue],
    *,
    reject_placeholder: bool = True,
) -> str | None:
    value = record.get(field)
    if not _is_nonempty_text(value):
        issues.append(Issue(f"{path}.{field}", "must be non-empty text"))
        return None
    if reject_placeholder and _is_placeholder(value):
        issues.append(Issue(f"{path}.{field}", "must be filled before preflight"))
    return value.strip()


def _require_list(
    record: Mapping[str, Any],
    field: str,
    path: str,
    issues: list[Issue],
    *,
    allow_empty: bool = False,
) -> list[Any]:
    value = record.get(field)
    if not isinstance(value, list) or (not allow_empty and not value):
        expectation = "array" if allow_empty else "non-empty array"
        issues.append(Issue(f"{path}.{field}", f"must be a {expectation}"))
        return []
    return value


def _require_state(
    record: Mapping[str, Any],
    field: str,
    path: str,
    issues: list[Issue],
) -> Mapping[str, Any] | None:
    value = record.get(field)
    if not _state(value):
        issues.append(Issue(f"{path}.{field}", "must be a non-empty state object"))
        return None
    return value


def _unique_texts(
    values: Sequence[Any],
    *,
    path: str,
    issues: list[Issue],
) -> list[str]:
    result: list[str] = []
    for index, value in enumerate(values):
        if not _is_nonempty_text(value):
            issues.append(Issue(f"{path}[{index}]", "must be non-empty text"))
            continue
        result.append(value)
    duplicates = sorted(item for item, count in Counter(result).items() if count > 1)
    if duplicates:
        issues.append(Issue(path, f"contains duplicate ids: {', '.join(duplicates)}"))
    return result


def _compare_ids(
    actual: Sequence[Any],
    expected: Sequence[str],
    *,
    path: str,
    issues: list[Issue],
) -> None:
    actual_ids = _unique_texts(actual, path=path, issues=issues)
    if actual_ids != list(expected):
        issues.append(
            Issue(
                path,
                f"must exactly follow the compiled order: {', '.join(expected) or '(none)'}",
            )
        )


def _validate_source(root: Mapping[str, Any], issues: list[Issue]) -> None:
    source = _mapping(root.get("source"))
    if source is None:
        issues.append(Issue("source", "must be an object"))
        return
    _require_text(source, "canonical", "source", issues)
    conflicts = source.get("conflicts")
    if not isinstance(conflicts, list):
        issues.append(Issue("source.conflicts", "must be an array"))
        return
    for index, conflict_value in enumerate(conflicts):
        path = f"source.conflicts[{index}]"
        conflict = _mapping(conflict_value)
        if conflict is None:
            issues.append(Issue(path, "must be an object"))
            continue
        _require_text(conflict, "id", path, issues)
        _require_text(conflict, "question", path, issues)
        _require_text(conflict, "resolution", path, issues)
        status = _require_text(conflict, "status", path, issues)
        if status is not None and status != "resolved":
            issues.append(Issue(f"{path}.status", "must be 'resolved' before generation"))


def _validate_scenes(
    scenes: Sequence[Mapping[str, Any]],
    *,
    issues: list[Issue],
) -> tuple[dict[str, Mapping[str, Any]], list[Mapping[str, Any]]]:
    by_id, ordered = _ordered_records(scenes, label="scenes", issues=issues)
    for index, scene in enumerate(scenes):
        path = f"scenes[{index}]"
        _require_text(scene, "purpose", path, issues)
        _require_text(scene, "turn", path, issues)
        _require_text(scene, "next_obligation", path, issues)
        _require_text(scene, "location", path, issues)
        _require_state(scene, "entry_state", path, issues)
        _require_state(scene, "exit_state", path, issues)
        cast = _require_list(scene, "cast", path, issues, allow_empty=True)
        _unique_texts(cast, path=f"{path}.cast", issues=issues)
        bridge = scene.get("bridge_from_previous")
        order = scene.get("order")
        if isinstance(order, int) and order > 1:
            bridge_object = _mapping(bridge)
            if bridge_object is None:
                issues.append(Issue(f"{path}.bridge_from_previous", "required after the first scene"))
            else:
                _require_text(bridge_object, "type", f"{path}.bridge_from_previous", issues)
                _require_text(bridge_object, "description", f"{path}.bridge_from_previous", issues)
        elif bridge is not None and not _is_mapping(bridge):
            issues.append(Issue(f"{path}.bridge_from_previous", "must be an object or null"))
    return by_id, ordered


def _validate_panels(
    panels: Sequence[Mapping[str, Any]],
    *,
    scene_ids: set[str],
    issues: list[Issue],
) -> tuple[dict[str, Mapping[str, Any]], list[Mapping[str, Any]]]:
    by_id, ordered = _ordered_records(panels, label="panels", issues=issues)
    for index, panel in enumerate(panels):
        path = f"panels[{index}]"
        duration = panel.get("duration_s")
        if not _is_number(duration) or not 4 <= duration <= 15:
            issues.append(Issue(f"{path}.duration_s", "must be between 4 and 15 seconds"))
        scene_id = _require_text(panel, "scene_id", path, issues)
        if scene_id is not None and scene_id not in scene_ids:
            issues.append(Issue(f"{path}.scene_id", f"unknown scene {scene_id!r}"))
        _require_state(panel, "entry_state", path, issues)
        _require_state(panel, "exit_state", path, issues)
        _require_list(panel, "shot_ids", path, issues)
        _require_list(panel, "coverage_ids", path, issues)
        transition = panel.get("transition_to_next")
        order = panel.get("order")
        if isinstance(order, int) and order < len(panels):
            transition_object = _mapping(transition)
            if transition_object is None:
                issues.append(Issue(f"{path}.transition_to_next", "required before the next panel"))
            else:
                owner = _require_text(transition_object, "ownership", f"{path}.transition_to_next", issues)
                if owner is not None and owner not in VALID_TRANSITION_OWNERS:
                    issues.append(
                        Issue(
                            f"{path}.transition_to_next.ownership",
                            "must be 'previous' or 'next'",
                        )
                    )
                _require_text(transition_object, "bridge", f"{path}.transition_to_next", issues)
        elif transition is not None and not _is_mapping(transition):
            issues.append(Issue(f"{path}.transition_to_next", "must be an object or null"))
    return by_id, ordered


def _validate_coverage(
    coverage: Sequence[Mapping[str, Any]],
    *,
    scene_ids: set[str],
    panel_ids: set[str],
    issues: list[Issue],
) -> tuple[dict[str, Mapping[str, Any]], list[Mapping[str, Any]]]:
    by_id, ordered = _ordered_records(coverage, label="coverage", issues=issues)
    for index, item in enumerate(coverage):
        path = f"coverage[{index}]"
        priority = _require_text(item, "priority", path, issues)
        if priority is not None and priority not in VALID_PRIORITIES:
            issues.append(Issue(f"{path}.priority", "must be must_show, must_explain, or optional"))
        source_refs = _require_list(item, "source_refs", path, issues)
        _unique_texts(source_refs, path=f"{path}.source_refs", issues=issues)
        _require_text(item, "event", path, issues)
        _require_text(item, "visible_proof", path, issues)

        scene_id = item.get("scene_id")
        panel_id = item.get("panel_id")
        shot_id = item.get("shot_id")
        mandatory = priority in MANDATORY_PRIORITIES
        for field, value, known_ids in (
            ("scene_id", scene_id, scene_ids),
            ("panel_id", panel_id, panel_ids),
        ):
            if mandatory and not _is_nonempty_text(value):
                issues.append(Issue(f"{path}.{field}", "required for mandatory coverage"))
            if value is not None and value != "" and value not in known_ids:
                issues.append(Issue(f"{path}.{field}", f"unknown id {value!r}"))
        if mandatory and not _is_nonempty_text(shot_id):
            issues.append(Issue(f"{path}.shot_id", "required for mandatory coverage"))
        if shot_id is not None and shot_id != "" and not _is_nonempty_text(shot_id):
            issues.append(Issue(f"{path}.shot_id", "must be non-empty text or null"))

        if mandatory or (scene_id is not None and scene_id != ""):
            _require_state(item, "before_state", path, issues)
            _require_state(item, "after_state", path, issues)
    return by_id, ordered


def _validate_generation(
    generation: Mapping[str, Any] | None,
    *,
    scene_ids: set[str],
    panel_ids: set[str],
    coverage_by_id: Mapping[str, Mapping[str, Any]],
    issues: list[Issue],
) -> tuple[dict[str, Mapping[str, Any]], list[Mapping[str, Any]], Mapping[str, Any]]:
    if generation is None:
        issues.append(Issue("generation", "must be an object"))
        return {}, [], {}
    limits = _mapping(generation.get("limits"))
    if limits is None:
        issues.append(Issue("generation.limits", "must be an object"))
        limits = {}
    limit_specs = {
        "reference_slots": 0,
        "max_critical_characters": 1,
        "max_actions": 1,
        "max_camera_moves": 0,
        "max_dialogue_lines": 0,
    }
    for field, minimum in limit_specs.items():
        value = limits.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            issues.append(Issue(f"generation.limits.{field}", f"must be an integer >= {minimum}"))

    shots = _record_list(generation, "shots", issues)
    by_id, ordered = _ordered_records(shots, label="generation.shots", issues=issues)
    coverage_ids = set(coverage_by_id)
    for index, shot in enumerate(shots):
        path = f"generation.shots[{index}]"
        scene_id = _require_text(shot, "scene_id", path, issues)
        panel_id = _require_text(shot, "panel_id", path, issues)
        if scene_id is not None and scene_id not in scene_ids:
            issues.append(Issue(f"{path}.scene_id", f"unknown scene {scene_id!r}"))
        if panel_id is not None and panel_id not in panel_ids:
            issues.append(Issue(f"{path}.panel_id", f"unknown panel {panel_id!r}"))
        coverage = _require_list(shot, "coverage_ids", path, issues)
        shot_coverage = _unique_texts(coverage, path=f"{path}.coverage_ids", issues=issues)
        unknown_coverage = sorted(set(shot_coverage) - coverage_ids)
        if unknown_coverage:
            issues.append(Issue(f"{path}.coverage_ids", f"unknown coverage: {', '.join(unknown_coverage)}"))
        dialogue = _require_list(shot, "dialogue_ids", path, issues, allow_empty=True)
        _unique_texts(dialogue, path=f"{path}.dialogue_ids", issues=issues)
        critical_characters = _require_list(shot, "critical_characters", path, issues, allow_empty=True)
        character_ids = _unique_texts(
            critical_characters,
            path=f"{path}.critical_characters",
            issues=issues,
        )
        references = _require_list(shot, "reference_keys", path, issues, allow_empty=True)
        reference_keys = _unique_texts(references, path=f"{path}.reference_keys", issues=issues)
        actions = _require_list(shot, "actions", path, issues)
        camera_moves = _require_list(shot, "camera_moves", path, issues, allow_empty=True)
        _unique_texts(actions, path=f"{path}.actions", issues=issues)
        _unique_texts(camera_moves, path=f"{path}.camera_moves", issues=issues)
        _require_text(shot, "purpose", path, issues)
        _require_state(shot, "state_before", path, issues)
        _require_state(shot, "state_after", path, issues)

        text_strategy = _require_text(shot, "text_strategy", path, issues)
        if text_strategy is not None and text_strategy not in VALID_TEXT_STRATEGIES:
            issues.append(Issue(f"{path}.text_strategy", "must be 'none' or 'post'"))
        if text_strategy == "post":
            _require_text(shot, "post_asset", path, issues)
        elif text_strategy == "none" and shot.get("post_asset") not in (None, ""):
            issues.append(Issue(f"{path}.post_asset", "must be null when text_strategy is 'none'"))

        reference_limit = limits.get("reference_slots")
        if isinstance(reference_limit, int) and len(reference_keys) > reference_limit:
            issues.append(
                Issue(
                    f"{path}.reference_keys",
                    f"has {len(reference_keys)} references but the budget is {reference_limit}",
                )
            )
        character_limit = limits.get("max_critical_characters")
        if isinstance(character_limit, int) and len(character_ids) > character_limit:
            issues.append(
                Issue(
                    f"{path}.critical_characters",
                    f"has {len(character_ids)} critical characters but the budget is {character_limit}",
                )
            )
        action_limit = limits.get("max_actions")
        if isinstance(action_limit, int) and len(actions) > action_limit:
            issues.append(
                Issue(
                    f"{path}.actions",
                    f"has {len(actions)} actions but the budget is {action_limit}",
                )
            )
        camera_limit = limits.get("max_camera_moves")
        if isinstance(camera_limit, int) and len(camera_moves) > camera_limit:
            issues.append(
                Issue(
                    f"{path}.camera_moves",
                    f"has {len(camera_moves)} camera moves but the budget is {camera_limit}",
                )
            )
        dialogue_limit = limits.get("max_dialogue_lines")
        if isinstance(dialogue_limit, int) and len(dialogue) > dialogue_limit:
            issues.append(
                Issue(
                    f"{path}.dialogue_ids",
                    f"has {len(dialogue)} dialogue lines but the budget is {dialogue_limit}",
                )
            )
    return by_id, ordered, limits


def _validate_dialogue(
    dialogue: Sequence[Mapping[str, Any]],
    *,
    coverage_by_id: Mapping[str, Mapping[str, Any]],
    shot_by_id: Mapping[str, Mapping[str, Any]],
    issues: list[Issue],
) -> None:
    by_id, ordered = _ordered_records(dialogue, label="dialogue", issues=issues)
    del by_id
    previous_shot_order: int | None = None
    for index, line in enumerate(dialogue):
        path = f"dialogue[{index}]"
        _require_text(line, "speaker", path, issues)
        _require_text(line, "text", path, issues)
        coverage_id = _require_text(line, "coverage_id", path, issues)
        shot_id = _require_text(line, "shot_id", path, issues)
        if coverage_id is not None and coverage_id not in coverage_by_id:
            issues.append(Issue(f"{path}.coverage_id", f"unknown coverage {coverage_id!r}"))
        if shot_id is not None and shot_id not in shot_by_id:
            issues.append(Issue(f"{path}.shot_id", f"unknown shot {shot_id!r}"))
        if coverage_id in coverage_by_id and shot_id in shot_by_id:
            expected_shot = coverage_by_id[coverage_id].get("shot_id")
            if expected_shot not in (None, "", shot_id):
                issues.append(
                    Issue(
                        f"{path}.shot_id",
                        f"must match coverage {coverage_id}'s shot_id {expected_shot!r}",
                    )
                )
            shot_order = shot_by_id[shot_id].get("order")
            if isinstance(shot_order, int):
                if previous_shot_order is not None and shot_order < previous_shot_order:
                    issues.append(
                        Issue(
                            "dialogue",
                            "dialogue order crosses back to an earlier shot; preserve story order",
                        )
                    )
                previous_shot_order = shot_order

    dialogue_by_shot: defaultdict[str, list[int]] = defaultdict(list)
    for line in ordered:
        shot_id = line.get("shot_id")
        order = line.get("order")
        if isinstance(shot_id, str) and isinstance(order, int):
            dialogue_by_shot[shot_id].append(order)
    for shot_id, orders in dialogue_by_shot.items():
        if orders != sorted(orders):
            issues.append(Issue(f"dialogue[{shot_id}]", "dialogue order regresses inside a shot"))


def _validate_links_and_continuity(
    *,
    scenes: Sequence[Mapping[str, Any]],
    scene_by_id: Mapping[str, Mapping[str, Any]],
    panels: Sequence[Mapping[str, Any]],
    panel_by_id: Mapping[str, Mapping[str, Any]],
    coverage: Sequence[Mapping[str, Any]],
    coverage_by_id: Mapping[str, Mapping[str, Any]],
    shots: Sequence[Mapping[str, Any]],
    shot_by_id: Mapping[str, Mapping[str, Any]],
    issues: list[Issue],
) -> None:
    scene_ids = {record_id for record_id in scene_by_id}
    panel_ids = {record_id for record_id in panel_by_id}

    shots_by_panel: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    shots_by_scene: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for shot in shots:
        panel_id = shot.get("panel_id")
        scene_id = shot.get("scene_id")
        if panel_id in panel_ids:
            shots_by_panel[panel_id].append(shot)
        if scene_id in scene_ids:
            shots_by_scene[scene_id].append(shot)

    coverage_by_panel: defaultdict[str, list[str]] = defaultdict(list)
    for item in coverage:
        coverage_id = item.get("id")
        panel_id = item.get("panel_id")
        if isinstance(coverage_id, str):
            if isinstance(panel_id, str) and panel_id:
                coverage_by_panel[panel_id].append(coverage_id)
    for panel in panels:
        panel_id = panel.get("id")
        if not isinstance(panel_id, str):
            continue
        panel_path = f"panels[{panel_id}]"
        panel_shots = sorted(shots_by_panel[panel_id], key=lambda item: item.get("order", 0))
        expected_shots = [shot["id"] for shot in panel_shots]
        _compare_ids(panel.get("shot_ids", []), expected_shots, path=f"{panel_path}.shot_ids", issues=issues)
        expected_coverage = coverage_by_panel[panel_id]
        _compare_ids(
            panel.get("coverage_ids", []),
            expected_coverage,
            path=f"{panel_path}.coverage_ids",
            issues=issues,
        )
        if panel_shots:
            first_shot = panel_shots[0]
            last_shot = panel_shots[-1]
            if first_shot.get("state_before") != panel.get("entry_state"):
                issues.append(
                    Issue(
                        f"generation.shots[{first_shot.get('id')}].state_before",
                        f"must match panel {panel_id!r} entry_state",
                    )
                )
            if last_shot.get("state_after") != panel.get("exit_state"):
                issues.append(
                    Issue(
                        f"generation.shots[{last_shot.get('id')}].state_after",
                        f"must match panel {panel_id!r} exit_state",
                    )
                )

    for shot in shots:
        shot_id = shot.get("id")
        if not isinstance(shot_id, str):
            continue
        path = f"generation.shots[{shot_id}]"
        shot_coverage = shot.get("coverage_ids", [])
        for coverage_id in shot_coverage if isinstance(shot_coverage, list) else []:
            if coverage_id not in coverage_by_id:
                continue
            item = coverage_by_id[coverage_id]
            if item.get("shot_id") != shot_id:
                issues.append(
                    Issue(
                        f"{path}.coverage_ids",
                        f"coverage {coverage_id!r} must point back to shot {shot_id!r}",
                    )
                )
        valid_coverage = [
            coverage_by_id[coverage_id]
            for coverage_id in shot_coverage
            if coverage_id in coverage_by_id
        ]
        valid_coverage.sort(key=lambda item: item.get("order", 0))
        listed_orders = [coverage_by_id[item].get("order") for item in shot_coverage if item in coverage_by_id]
        sorted_orders = [item.get("order") for item in valid_coverage]
        if listed_orders != sorted_orders:
            issues.append(Issue(f"{path}.coverage_ids", "must follow story coverage order"))
        for previous, current in pairwise(valid_coverage):
            previous_state = previous.get("after_state")
            current_state = current.get("before_state")
            if _state(previous_state) and _state(current_state) and previous_state != current_state:
                issues.append(
                    Issue(
                        f"{path}.coverage_ids",
                        f"coverage {previous.get('id')!r} does not hand its state to {current.get('id')!r}",
                    )
                )

    for item in coverage:
        coverage_id = item.get("id")
        shot_id = item.get("shot_id")
        if not isinstance(coverage_id, str) or shot_id in (None, ""):
            continue
        if shot_id not in shot_by_id:
            issues.append(Issue(f"coverage[{coverage_id}].shot_id", f"unknown shot {shot_id!r}"))
            continue
        shot = shot_by_id[shot_id]
        if item.get("panel_id") != shot.get("panel_id"):
            issues.append(
                Issue(
                    f"coverage[{coverage_id}].panel_id",
                    f"must match shot {shot_id!r} panel_id {shot.get('panel_id')!r}",
                )
            )
        if item.get("scene_id") != shot.get("scene_id"):
            issues.append(
                Issue(
                    f"coverage[{coverage_id}].scene_id",
                    f"must match shot {shot_id!r} scene_id {shot.get('scene_id')!r}",
                )
            )

    mandatory_ids = {
        item.get("id")
        for item in coverage
        if item.get("priority") in MANDATORY_PRIORITIES and isinstance(item.get("id"), str)
    }
    listed_coverage: Counter[str] = Counter()
    for shot in shots:
        values = shot.get("coverage_ids", [])
        if isinstance(values, list):
            listed_coverage.update(value for value in values if isinstance(value, str))
    for coverage_id in sorted(mandatory_ids):
        if listed_coverage[coverage_id] != 1:
            issues.append(
                Issue(
                    f"coverage[{coverage_id}]",
                    f"mandatory coverage must map to exactly one shot, found {listed_coverage[coverage_id]}",
                )
            )

    # Each scene must have a visible beginning and ending state carried by its panels.
    panels_by_scene: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for panel in panels:
        scene_id = panel.get("scene_id")
        if scene_id in scene_ids:
            panels_by_scene[scene_id].append(panel)
    for scene in scenes:
        scene_id = scene.get("id")
        if not isinstance(scene_id, str):
            continue
        scene_panels = sorted(panels_by_scene[scene_id], key=lambda item: item.get("order", 0))
        if not scene_panels:
            issues.append(Issue(f"scenes[{scene_id}]", "must contain at least one panel"))
            continue
        if scene_panels[0].get("entry_state") != scene.get("entry_state"):
            issues.append(Issue(f"scenes[{scene_id}].entry_state", "must match the first panel entry_state"))
        if scene_panels[-1].get("exit_state") != scene.get("exit_state"):
            issues.append(Issue(f"scenes[{scene_id}].exit_state", "must match the last panel exit_state"))

    ordered_panels = sorted(panels, key=lambda item: item.get("order", 0))
    for previous_panel, next_panel in pairwise(ordered_panels):
        if previous_panel.get("scene_id") == next_panel.get("scene_id"):
            if previous_panel.get("exit_state") != next_panel.get("entry_state"):
                issues.append(
                    Issue(
                        f"panels[{next_panel.get('id')}].entry_state",
                        f"must match previous panel {previous_panel.get('id')!r} exit_state in the same scene",
                    )
                )

    ordered_shots = sorted(shots, key=lambda item: item.get("order", 0))
    for previous_shot, next_shot in pairwise(ordered_shots):
        if previous_shot.get("scene_id") == next_shot.get("scene_id"):
            if previous_shot.get("state_after") != next_shot.get("state_before"):
                issues.append(
                    Issue(
                        f"generation.shots[{next_shot.get('id')}].state_before",
                        f"must match previous shot {previous_shot.get('id')!r} state_after in the same scene",
                    )
                )

    del shots_by_scene, shot_by_id


def validate_blueprint(document: object) -> list[Issue]:
    """Return all creative preflight issues in ``document``.

    The function intentionally returns every issue in one pass so a writer can
    repair the design in one edit cycle instead of paying for repeated media
    generations.
    """

    issues: list[Issue] = []
    root = _mapping(document)
    if root is None:
        return [Issue("$", "blueprint root must be an object")]

    schema = _require_text(root, "schema", "$", issues)
    if schema is not None and schema != SCHEMA:
        issues.append(Issue("$.schema", f"must be {SCHEMA!r}"))

    project = _mapping(root.get("project"))
    if project is None:
        issues.append(Issue("project", "must be an object"))
        project = {}
    _require_text(project, "title", "project", issues)
    _require_text(project, "scope", "project", issues)
    target_duration = project.get("target_duration_s")
    if not _is_number(target_duration) or target_duration <= 0:
        issues.append(Issue("project.target_duration_s", "must be a positive number"))

    _validate_source(root, issues)
    scene_records = _record_list(root, "scenes", issues)
    scene_by_id, ordered_scenes = _validate_scenes(scene_records, issues=issues)
    panel_records = _record_list(root, "panels", issues)
    panel_by_id, ordered_panels = _validate_panels(
        panel_records,
        scene_ids=set(scene_by_id),
        issues=issues,
    )
    coverage_records = _record_list(root, "coverage", issues)
    coverage_by_id, ordered_coverage = _validate_coverage(
        coverage_records,
        scene_ids=set(scene_by_id),
        panel_ids=set(panel_by_id),
        issues=issues,
    )
    generation = _mapping(root.get("generation"))
    shot_by_id, ordered_shots, limits = _validate_generation(
        generation,
        scene_ids=set(scene_by_id),
        panel_ids=set(panel_by_id),
        coverage_by_id=coverage_by_id,
        issues=issues,
    )
    dialogue_values = root.get("dialogue")
    if not isinstance(dialogue_values, list):
        issues.append(Issue("dialogue", "must be an array"))
        dialogue_records = []
    else:
        dialogue_records = []
        for index, item in enumerate(dialogue_values):
            if not _is_mapping(item):
                issues.append(Issue(f"dialogue[{index}]", "must be an object"))
                continue
            dialogue_records.append(item)
    _validate_dialogue(
        [item for item in dialogue_records if _is_mapping(item)],
        coverage_by_id=coverage_by_id,
        shot_by_id=shot_by_id,
        issues=issues,
    )

    _validate_links_and_continuity(
        scenes=ordered_scenes,
        scene_by_id=scene_by_id,
        panels=ordered_panels,
        panel_by_id=panel_by_id,
        coverage=ordered_coverage,
        coverage_by_id=coverage_by_id,
        shots=ordered_shots,
        shot_by_id=shot_by_id,
        issues=issues,
    )

    durations = [panel.get("duration_s") for panel in ordered_panels if _is_number(panel.get("duration_s"))]
    if _is_number(target_duration) and durations and not math.isclose(
        sum(durations), target_duration, rel_tol=0, abs_tol=0.01
    ):
        issues.append(
            Issue(
                "project.target_duration_s",
                f"must equal the panel duration sum ({sum(durations):g}s)",
            )
        )

    # Limits are validated in _validate_generation; retaining the local name makes
    # the contract explicit for callers inspecting the function during debugging.
    del limits
    return issues


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a zero-to-story creative blueprint before media generation."
    )
    parser.add_argument("blueprint", type=Path, help="path to creative_blueprint.json")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit a machine-readable result",
    )
    args = parser.parse_args(argv)

    try:
        document = _load_json(args.blueprint)
    except ValueError as exc:
        issues = [Issue(str(args.blueprint), str(exc))]
    else:
        issues = validate_blueprint(document)

    if args.json_output:
        print(json.dumps({"ok": not issues, "issues": [issue.as_dict() for issue in issues]}, ensure_ascii=False))
    elif issues:
        print(f"CREATIVE PREFLIGHT: FAIL ({len(issues)} issue(s))")
        for issue in issues:
            print(f"- {issue.format()}")
    else:
        print("CREATIVE PREFLIGHT: PASS")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
