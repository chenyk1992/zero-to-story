"""Focused regression coverage for canvas review findings."""

from __future__ import annotations

import json
from pathlib import Path

from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings


def _image_graph(asset: Path | None = None) -> dict[str, object]:
    nodes: list[dict[str, object]] = [
        {
            "id": "image-one",
            "type": "image",
            "position": {"x": 0, "y": 0},
            "data": {
                "prompt": "测试画面",
                "provider": "codex-imagegen",
                "model": "image_gen",
                "mode": "create",
            },
        }
    ]
    edges: list[dict[str, str]] = []
    if asset is not None:
        nodes.append(
            {
                "id": "reference",
                "type": "asset",
                "position": {"x": 0, "y": 0},
                "data": {"asset": {"path": str(asset), "kind": "image", "name": asset.name}},
            }
        )
        edges.append(
            {
                "id": "reference-edge",
                "source": "reference",
                "target": "image-one",
                "sourceHandle": "output",
                "targetHandle": "reference_image",
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
    }


def _settings(root: Path, data_dir: Path, media_root: Path) -> CanvasSettings:
    return CanvasSettings.resolve(
        project_root=root, data_dir=data_dir, media_root=media_root, port=0
    )


def _write_image_capability(project: Path) -> None:
    skill = project / ".agents" / "skills" / "codex-imagegen"
    skill.mkdir(parents=True)
    (skill / "capability.json").write_text(
        json.dumps(
            {
                "id": "codex-imagegen",
                "label": "test image agent",
                "node_types": ["image"],
                "execution": "agent",
                "models": [],
                "modes": [],
                "fields": [],
            }
        ),
        encoding="utf-8",
    )


def test_replacing_asset_bytes_marks_existing_run_stale(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_image_capability(project)
    media_root = tmp_path / "media"
    media_root.mkdir()
    asset = media_root / "reference.png"
    asset.write_bytes(b"original")
    service = CanvasService(_settings(project, tmp_path / "state", media_root), start_worker=False)
    try:
        canvas = service.store.create_canvas("asset", _image_graph(asset))
        service.confirm(canvas["id"], "image-one", canvas["version"], "asset-review")
        asset.write_bytes(b"replacement-with-different-bytes")
        assert service.runs(canvas["id"])[0]["matches_current"] is False
    finally:
        service.close()
