from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.input_contract import validate_input_contract
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings

ROOT = Path(__file__).resolve().parents[2]
CAPABILITY = json.loads((ROOT / ".agents/skills/comfy-video-executor/capability.json").read_text(encoding="utf-8"))


def snapshot():
    return {"mode": "t2v", "parameters": {"duration": 5, "aspect_ratio": "16:9", "megapixels": 0.6, "sampler_profile": "native", "steps": 12}, "inputs": {}}


@pytest.mark.parametrize("mode,inputs", [
    ("t2v", {}), ("i2v", {"first_frame": {"path": "first.png"}}),
    ("fl2v", {"first_frame": {}, "last_frame": {}}),
    ("r2v", {"reference_images": [{"path": "identity.png"}]}),
])
def test_four_supported_modes(mode, inputs):
    validate_input_contract({**snapshot(), "mode": mode, "inputs": inputs}, CAPABILITY)


@pytest.mark.parametrize("mode,patch", [
    ("i2v", {}), ("t2v", {"sampler_profile": "vdn_turbo", "steps": 9}),
    ("t2v", {"fps": 30}), ("t2v", {"megapixels": -0.4}),
    ("t2v", {"steps": 8.5}), ("t2v", {"reference_image_size": "max"}),
])
def test_invalid_inputs_never_create_run(tmp_path, monkeypatch, mode, patch):
    capability = {**copy.deepcopy(CAPABILITY), "available": True, "installed": True}
    monkeypatch.setattr(CapabilityCatalog, "get", lambda *args, **kwargs: capability)
    service = CanvasService(CanvasSettings(ROOT, tmp_path / "state", tmp_path / "media"), start_worker=False)
    try:
        parameters = {**snapshot()["parameters"], **patch}
        data = {"prompt": "Test", "provider": "comfy", "model": "h3", "mode": mode,
                "duration": parameters.pop("duration"), "aspect_ratio": parameters.pop("aspect_ratio"),
                "megapixels": parameters.pop("megapixels"), "options": {"comfy": parameters}}
        canvas = service.store.create_canvas("test", {"nodes": [{"id": "clip", "type": "video", "position": {"x": 0, "y": 0}, "data": data}], "edges": []})
        with pytest.raises(ValueError):
            service.confirm(canvas["id"], "clip", canvas["version"], "request")
        assert service.store.list_runs() == []
    finally:
        service.close()
