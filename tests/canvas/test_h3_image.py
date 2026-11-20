from __future__ import annotations

from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.comfy import h3_image


def snapshot(tmp_path, mode, count):
    refs = []
    for i in range(count):
        path = tmp_path / f"{i}.png"
        path.write_bytes(b"fixture")
        refs.append({"path": str(path), "kind": "image"})
    return {
        "node_type": "image",
        "provider": "comfy-h3-image",
        "model": "minimax-h3-image",
        "mode": mode,
        "request_id": "h3-test",
        "prompt": "Preserve exact text",
        "parameters": {"megapixels": 4, **({} if mode == "edit" else {"aspect_ratio": "3:2"})},
        "inputs": {"reference_images": refs},
    }


@pytest.mark.parametrize(
    "mode,count", [("create", 0), ("reference", 1), ("reference", 16), ("edit", 16)]
)
def test_workflow(tmp_path, mode, count):
    value = snapshot(tmp_path, mode, count)
    workflow, n = h3_image.prepare_workflow(
        value, uploader=lambda p: p.name, inspect_fn=lambda p: {"width": 1200, "height": 800}
    )
    assert workflow["4"]["inputs"]["prompt"] == value["prompt"]
    assert workflow["6"]["inputs"]["latent_image"] == ["4", 1]
    assert workflow["6"]["inputs"]["steps"] == 6
    assert n["width"] % 32 == n["height"] % 32 == 0
    for i in range(1, count + 1):
        link = workflow["4"]["inputs"][f"images.image_{i}"]
        assert workflow[link[0]]["inputs"]["image"] == f"{i - 1}.png"


@pytest.mark.parametrize(
    "mode,count", [("create", 1), ("reference", 0), ("edit", 0), ("reference", 17), ("edit", 17)]
)
def test_invalid_counts_before_upload(tmp_path, mode, count):
    calls = []
    with pytest.raises(ValueError):
        h3_image.prepare_workflow(
            snapshot(tmp_path, mode, count), uploader=lambda p: calls.append(p)
        )
    assert calls == []


def test_marker_and_budget(tmp_path):
    value = snapshot(tmp_path, "reference", 1)
    value["prompt"] = "Use <Picture 2>"
    with pytest.raises(ValueError, match="Picture 2"):
        h3_image.normalize_snapshot(value)
    value["prompt"] = "valid"
    value["parameters"]["megapixels"] = 1
    with pytest.raises(ValueError):
        h3_image.normalize_snapshot(value)


def test_catalog():
    root = Path(__file__).resolve().parents[2]
    cap = CapabilityCatalog(root).get("comfy-h3-image")
    assert cap["execution"] == "script"
    assert cap["resource"]["key"] == "video"
    assert cap["input_rules"]["reference"]["max_counts"]["reference_images"] == 16
