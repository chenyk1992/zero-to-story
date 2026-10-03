from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.input_contract import validate_input_contract
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings

PROJECT = Path(__file__).resolve().parents[2]
CAPABILITY_PATH = PROJECT / ".agents" / "skills" / "comfy-upscale-executor" / "capability.json"


def capability() -> dict:
    return json.loads(CAPABILITY_PATH.read_text(encoding="utf-8"))


def test_capability_catalog_sees_descriptor_created_after_catalog_construction(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    assert catalog.public() == []

    skill = tmp_path / ".agents" / "skills" / "comfy-upscale-executor"
    skill.mkdir(parents=True)
    (skill / "capability.json").write_text(
        json.dumps(
            {
                "id": "comfy-upscale",
                "label": "视频超分",
                "node_types": ["video"],
                "execution": "script",
                "entrypoint": "scripts/execute.py",
                "models": [{"id": "seedvr2-3b-int8", "label": "SeedVR2"}],
                "modes": [{"id": "upscale", "label": "视频超分"}],
                "fields": [],
            }
        ),
        encoding="utf-8",
    )

    discovered = catalog.public()
    assert [item["id"] for item in discovered] == ["comfy-upscale"]


def snapshot(source: Path, *, references: list[dict] | None = None) -> dict:
    return {
        "node_type": "video",
        "provider": "comfy-upscale",
        "model": "seedvr2-3b-int8",
        "mode": "upscale",
        "prompt": "按所选工作流超分参考底片，保持人物和构图。",
        "parameters": {
            "start_frame": 0,
            "frame_count": 120,
            "target_width": 1920,
            "target_height": 1066,
            "chunk_mode": "auto",
        },
        "inputs": {
            "reference_videos": references
            if references is not None
            else [{"path": str(source), "kind": "video"}]
        },
    }


def test_upscale_capability_is_discovered_and_accepts_one_five_second_video(tmp_path):
    catalog = CapabilityCatalog(PROJECT)
    entry = catalog.get("comfy-upscale")
    assert entry["execution"] == "script"
    assert entry["node_types"] == ["video"]
    assert entry["resource"] == {"key": "video", "capacity": 1}
    assert any(item["id"] == "seedvr2-3b-int8" for item in entry["models"])
    assert any(item["id"] == "upscale" for item in entry["modes"])

    reference = tmp_path / "h3-raw.mp4"
    reference.write_bytes(b"test fixture")
    validate_input_contract(snapshot(reference), entry)


def test_upscale_contract_requires_exactly_one_video_reference(tmp_path):
    cap = capability()
    reference = tmp_path / "h3-raw.mp4"
    reference.write_bytes(b"test fixture")
    base = snapshot(reference)

    for references in ([], [base["inputs"]["reference_videos"][0]] * 2):
        invalid = copy.deepcopy(base)
        invalid["inputs"]["reference_videos"] = references
        with pytest.raises(ValueError):
            validate_input_contract(invalid, cap)

    invalid = copy.deepcopy(base)
    invalid["inputs"]["reference_videos"] = [{
        "path": str(tmp_path / "not-a-video.png"),
        "kind": "video",
    }]
    with pytest.raises(ValueError):
        validate_input_contract(invalid, cap)


def test_confirm_freezes_upscale_source_and_queues_on_shared_video_resource(tmp_path, monkeypatch):
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media")
    service = CanvasService(settings, start_worker=False)
    source = settings.media_root / "assets" / "uploads" / "h3-raw.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"test fixture")
    asset = service.media.asset(source)
    entry = copy.deepcopy(service.catalog.get("comfy-upscale"))
    entry.update(installed=True, available=True)
    monkeypatch.setattr(service.catalog, "get", lambda *_args, **_kwargs: entry)

    graph = {
        "nodes": [
            {
                "id": "h3-source",
                "type": "asset",
                "position": {"x": 0, "y": 0},
                "data": {"asset": asset},
            },
            {
                "id": "upscale",
                "type": "video",
                "position": {"x": 300, "y": 0},
                "data": {
                    "prompt": "按所选工作流超分参考底片，保持人物和构图。",
                    "provider": "comfy-upscale",
                    "model": "seedvr2-3b-int8",
                    "mode": "upscale",
                    "options": {
                        "comfy-upscale": {
                            "start_frame": 0,
                            "frame_count": 120,
                            "target_width": 1920,
                            "target_height": 1066,
                            "chunk_mode": "auto",
                        }
                    },
                },
            },
        ],
        "edges": [
            {
                "id": "raw-to-upscale",
                "source": "h3-source",
                "target": "upscale",
                "sourceHandle": "output",
                "targetHandle": "reference_video",
            }
        ],
    }
    canvas = service.store.create_canvas("超分接入测试", graph)
    try:
        run = service.confirm(canvas["id"], "upscale", canvas["version"], "upscale-confirm")
        frozen = run["snapshot"]["inputs"]["reference_videos"][0]
        assert run["status"] == "queued"
        assert run["resource_key"] == "video"
        assert frozen["sha256"]
        assert Path(frozen["frozen_path"]).read_bytes() == b"test fixture"
    finally:
        service.close()
