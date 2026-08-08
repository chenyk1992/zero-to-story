"""Shared beats/panels storyboard fixtures for tests."""
from __future__ import annotations

import json
from pathlib import Path

from lfo.storyboard.storyboard import (
    Beat,
    CharacterAppearance,
    Panel,
    ProjectInfo,
    Storyboard,
    StyleGuide,
)


def make_panel_storyboard(
    num_panels: int = 1,
    *,
    project_id: str = "proj-test",
    title: str = "Test",
    beat_description_fn=None,
    with_characters: list[CharacterAppearance] | None = None,
    style: StyleGuide | None = None,
    dialogue_fn=None,
) -> Storyboard:
    """Create a storyboard with one beat per panel."""
    beats: list[Beat] = []
    panels: list[Panel] = []
    for i in range(num_panels):
        n = i + 1
        beat_id = f"beat_{n:03d}"
        description = (
            beat_description_fn(n)
            if beat_description_fn
            else f"Shot {n} description"
        )
        dialogue = dialogue_fn(n) if dialogue_fn else ""
        beats.append(
            Beat(
                beat_id=beat_id,
                sequence=n,
                scene_id="scene_001",
                description=description,
                dialogue=dialogue,
                framing="medium",
                characters=list(with_characters or []),
            )
        )
        panels.append(
            Panel(
                panel_id=f"panel_{n:03d}",
                sequence=n,
                beat_range=(n, n),
                beat_ids=[beat_id],
                desired_duration_ms=15_000,
            )
        )
    return Storyboard(
        project=ProjectInfo(project_id=project_id, title=title),
        style=style or StyleGuide(),
        beats=beats,
        panels=panels,
    )


def minimal_storyboard_dict(
    *,
    project_id: str = "proj-test",
    title: str = "Test",
    beats: list | None = None,
    panels: list | None = None,
    characters: list | None = None,
    **extra: object,
) -> dict:
    """Minimal valid storyboard JSON dict (beats + panels schema)."""
    data: dict = {
        "project": {"project_id": project_id, "title": title},
        "beats": beats if beats is not None else [],
        "panels": panels if panels is not None else [],
    }
    if characters is not None:
        data["characters"] = characters
    data.update(extra)
    return data


def write_storyboard_json(
    tmp_path: Path,
    data: dict,
    filename: str = "test_storyboard.json",
) -> Path:
    sb_path = tmp_path / filename
    sb_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return sb_path


def make_panel_storyboard_json(
    tmp_path: Path,
    num_panels: int = 1,
    *,
    project_id: str = "proj-test",
    characters: list | None = None,
) -> Path:
    """Write a beats/panels storyboard JSON file to tmp_path."""
    beats = []
    panels = []
    for i in range(num_panels):
        n = i + 1
        beat_id = f"beat_{n:03d}"
        beats.append(
            {
                "beat_id": beat_id,
                "sequence": n,
                "scene_id": "scene_001",
                "description": f"Shot {n} description",
                "dialogue": "",
                "sound": "",
                "characters": [],
                "framing": "medium",
            }
        )
        panels.append(
            {
                "panel_id": f"panel_{n:03d}",
                "sequence": n,
                "beat_range": [n, n],
                "beat_ids": [beat_id],
                "desired_duration_ms": 15_000,
                "prompt_text": "",
            }
        )
    data = minimal_storyboard_dict(
        project_id=project_id,
        title="Test",
        beats=beats,
        panels=panels,
        characters=characters,
    )
    return write_storyboard_json(tmp_path, data)
