from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.comfy import qwen_image as qwen


def snapshot(tmp_path, mode="create", count=0):
    refs = []
    for index in range(count):
        path = tmp_path / f"ref-{index + 1}.png"
        path.write_bytes(b"image fixture")
        refs.append({"path": str(path), "kind": "image"})
    return {
        "node_id": "picture",
        "node_type": "image",
        "provider": "comfy-qwen-image",
        "model": "qwen-image-2.1",
        "mode": mode,
        "prompt": "A cinematic portrait",
        "request_id": "request-one",
        "parameters": {"aspect_ratio": "3:2", "megapixels": 1, "seed": 42},
        "inputs": {"reference_images": refs},
    }


def inspect(_path):
    return {"width": 1000, "height": 701, "codec": "png", "has_alpha": False, "has_transparency": False}


@pytest.mark.parametrize(
    "mode,count",
    [
        ("create", 0),
        ("reference", 1),
        ("reference", 3),
        ("reference", 10),
        ("edit", 1),
        ("edit", 10),
    ],
)
def test_workflow_preserves_prompt_and_numeric_reference_order(tmp_path, mode, count):
    value = snapshot(tmp_path, mode, count)
    if mode == "edit":
        value["parameters"] = {"seed": 42}
    uploads = []
    workflow, normalized = qwen.prepare_workflow(
        value,
        uploader=lambda path: uploads.append(path.name) or path.name,
        inspect_fn=inspect,
    )
    encoder = workflow["4"]["inputs"]
    assert encoder["prompt"] == value["prompt"]
    if count == 0:
        assert encoder["images"] == {}
    assert uploads == [f"ref-{i}.png" for i in range(1, count + 1)]
    for i in range(1, count + 1):
        link = encoder[f"images.image_{i}"]
        assert workflow[link[0]]["inputs"]["image"] == f"ref-{i}.png"
    assert workflow["6"]["inputs"]["seed"] == 42
    assert normalized["width"] % 32 == normalized["height"] % 32 == 0
    if mode == "edit":
        assert workflow["6"]["inputs"]["latent_image"] == ["4", 2]
        assert (normalized["width"], normalized["height"]) == (992, 704)
    else:
        assert workflow["6"]["inputs"]["latent_image"] == ["5", 0]


@pytest.mark.parametrize(
    "mode,count", [("create", 1), ("reference", 0), ("edit", 0), ("reference", 11), ("edit", 11)]
)
def test_invalid_counts_fail_before_upload(tmp_path, mode, count):
    calls = []
    with pytest.raises(ValueError):
        qwen.prepare_workflow(
            snapshot(tmp_path, mode, count), uploader=lambda p: calls.append(p), inspect_fn=inspect
        )
    assert not calls


def test_invalid_image_marker_is_rejected(tmp_path):
    value = snapshot(tmp_path, "reference", 2)
    value["prompt"] = "Use <image3> as the person"
    with pytest.raises(ValueError, match="image3"):
        qwen.normalize_snapshot(value, inspect_fn=inspect)


def test_edit_rejects_new_canvas_parameters_instead_of_ignoring_them(tmp_path):
    with pytest.raises(ValueError):
        qwen.normalize_snapshot(snapshot(tmp_path, "edit", 1), inspect_fn=inspect)


def test_reference_pixel_budget_preserves_aspect(tmp_path):
    value = snapshot(tmp_path, "edit", 1)
    value["parameters"] = {"reference_resolution": 1024}
    result = qwen.normalize_snapshot(value, inspect_fn=inspect)
    assert (result["width"], result["height"]) == (1216, 864)


def test_defaults_and_seed_are_recorded(tmp_path):
    value = snapshot(tmp_path)
    del value["parameters"]["seed"]
    workflow, normalized = qwen.prepare_workflow(
        value, uploader=lambda p: p.name, inspect_fn=inspect
    )
    assert normalized["steps"] == 25
    assert workflow["6"]["inputs"]["cfg"] == 1
    assert 0 <= normalized["seed"] <= 2**53 - 1
    assert workflow["6"]["inputs"]["seed"] == normalized["seed"]


@pytest.mark.parametrize("empty", [None, ""])
def test_optional_empty_values_use_defaults(tmp_path, empty):
    value = snapshot(tmp_path, "reference", 1)
    value["parameters"].update(seed=empty, steps=empty, reference_resolution=empty, transparent=empty)
    result = qwen.normalize_snapshot(value, inspect_fn=inspect)
    assert result["steps"] == 25 and result["reference_resolution"] == 0
    assert isinstance(result["seed"], int) and result["transparent"] is False


def test_capability_uses_shared_gpu_resource_and_ten_inputs():
    cap = json.loads((qwen.SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    assert cap["execution"] == "script"
    assert cap["resource"] == {"key": "video", "capacity": 1}
    assert cap["input_rules"]["edit"]["max_counts"]["reference_images"] == 10
    assert cap["input_rules"]["reference"]["max_counts"]["reference_images"] == 10


def test_transparent_output_requires_real_transparency(tmp_path, monkeypatch):
    from lfo.comfy.transport import ComfyResult, OutputRef, RuntimeConfig

    image = tmp_path / "remote.png"
    image.write_bytes(b"image")
    result = ComfyResult("prompt-one", (OutputRef(str(image), file_type="absolute"),))
    monkeypatch.setattr(qwen, "inspect_image", lambda p: {**inspect(p), "has_alpha": True})
    with pytest.raises(ValueError, match="透明"):
        qwen.materialize_image(
            result,
            tmp_path / "outputs",
            RuntimeConfig(),
            {"width": 1000, "height": 701, "transparent": True},
        )


def test_output_dimensions_must_match_frozen_request(tmp_path, monkeypatch):
    from lfo.comfy.transport import ComfyResult, OutputRef, RuntimeConfig

    image = tmp_path / "remote.png"
    image.write_bytes(b"image")
    result = ComfyResult("prompt-one", (OutputRef(str(image), file_type="absolute"),))
    monkeypatch.setattr(qwen, "inspect_image", inspect)
    with pytest.raises(ValueError, match="尺寸"):
        qwen.materialize_image(
            result,
            tmp_path / "outputs",
            RuntimeConfig(),
            {"width": 1024, "height": 1024, "transparent": False},
        )
    assert not list((tmp_path / "outputs").glob("*.png"))
    assert image.is_file()


def test_capability_rejects_gif_before_worker_runs(tmp_path):
    from lfo.canvas.input_contract import validate_input_contract
    cap = json.loads((qwen.SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    value = snapshot(tmp_path, "reference", 1)
    value["inputs"]["reference_images"][0]["path"] = "animation.gif"
    with pytest.raises(ValueError, match="格式"):
        validate_input_contract(value, cap)


def test_execute_uses_one_shared_submission_and_keeps_conditions(tmp_path, monkeypatch):
    from lfo.comfy import transport

    value = snapshot(tmp_path, "reference", 3)
    events, calls = [], []
    monkeypatch.setattr(qwen, "inspect_image", inspect)
    monkeypatch.setattr(transport, "preflight_workflow", lambda *a: calls.append("preflight"))
    from contextlib import nullcontext

    monkeypatch.setattr(transport, "ready_session", lambda *a: nullcontext(object()))
    monkeypatch.setattr(transport, "upload_input", lambda p, _s: calls.append(p.name) or p.name)

    def submit(path, _output_dir, _config, _session, *, guard, emit):
        calls.append("submit")
        graph = json.loads(path.read_text(encoding="utf-8"))
        assert graph["4"]["inputs"]["prompt"] == value["prompt"]
        assert guard.request_id == value["request_id"]
        return transport.ComfyResult("pid", ())

    monkeypatch.setattr(transport, "run_workflow", submit)
    monkeypatch.setattr(
        qwen, "materialize_image", lambda *a: {"path": "image.png", "kind": "image"}
    )
    result = qwen.execute_snapshot(
        value, tmp_path / "run", transport.RuntimeConfig(), emit=events.append
    )
    assert calls == ["ref-1.png", "ref-2.png", "ref-3.png", "preflight", "submit"]
    assert result["status"] == "succeeded"
    conditions = json.loads((tmp_path / "run/conditions.json").read_text(encoding="utf-8"))
    assert [r["index"] for r in conditions["references"]] == [1, 2, 3]
    assert conditions["seed"] == 42
    assert events[-1]["remote_finished"] is True


def test_unknown_submission_is_not_retried(tmp_path, monkeypatch):
    from lfo.comfy import transport

    calls = []
    monkeypatch.setattr(transport, "preflight_workflow", lambda *a: None)

    def submit(*a, **kw):
        calls.append(1)
        raise transport.ExecutorError(
            "lost connection", provider_task_id="original", status="unknown"
        )

    from contextlib import nullcontext

    monkeypatch.setattr(transport, "ready_session", lambda *a: nullcontext(object()))
    monkeypatch.setattr(transport, "run_workflow", submit)
    with pytest.raises(transport.ExecutorError) as err:
        qwen.execute_snapshot(
            snapshot(tmp_path), tmp_path / "run", transport.RuntimeConfig(), emit=lambda e: None
        )
    assert len(calls) == 1
    assert err.value.status == "unknown"
    assert err.value.provider_task_id == "original"


def test_missing_models_stop_before_upload_or_submission(tmp_path, monkeypatch):
    from lfo.comfy import transport

    monkeypatch.setattr(qwen, "inspect_image", inspect)

    def missing(*a):
        raise transport.ExecutorError("missing model")

    monkeypatch.setattr(transport, "preflight_workflow", missing)
    from contextlib import nullcontext

    monkeypatch.setattr(transport, "ready_session", lambda *a: nullcontext(object()))
    monkeypatch.setattr(transport, "upload_input", lambda p, _s: p.name)
    monkeypatch.setattr(transport, "run_workflow", lambda *a, **k: pytest.fail("must not submit"))
    with pytest.raises(transport.ExecutorError, match="missing model"):
        qwen.execute_snapshot(
            snapshot(tmp_path, "reference", 1),
            tmp_path / "run",
            transport.RuntimeConfig(),
            emit=lambda e: None,
        )


def test_corrupt_image_fails_full_decode(tmp_path, monkeypatch):
    import subprocess

    outputs = iter(
        [
            subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    {"streams": [{"codec_name": "png", "width": 2, "height": 2, "pix_fmt": "rgba"}]}
                ).encode(),
            ),
            subprocess.CompletedProcess([], 1, b"", b"corrupt PNG data"),
        ]
    )
    monkeypatch.setattr(qwen.subprocess, "run", lambda *a, **k: next(outputs))
    with pytest.raises(ValueError, match="解码失败"):
        qwen.inspect_image(tmp_path / "bad.png")


def test_image_inspection_reports_actual_alpha(tmp_path, monkeypatch):
    import subprocess

    outputs = iter(
        [
            subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    {"streams": [{"codec_name": "png", "width": 2, "height": 1, "pix_fmt": "rgba"}]}
                ).encode(),
            ),
            subprocess.CompletedProcess([], 0, bytes([255, 0, 0, 0, 0, 255, 0, 255])),
        ]
    )
    monkeypatch.setattr(qwen.subprocess, "run", lambda *a, **k: next(outputs))
    result = qwen.inspect_image(tmp_path / "cutout.png")
    assert result["has_alpha"] and result["has_transparency"] and result["has_visible_pixels"]


def test_nearly_opaque_alpha_is_not_a_removed_background(tmp_path, monkeypatch):
    from lfo.comfy.transport import ComfyResult, OutputRef, RuntimeConfig
    image = tmp_path / "remote.png"
    image.write_bytes(b"image")
    result = ComfyResult("pid", (OutputRef(str(image), file_type="absolute"),))
    monkeypatch.setattr(qwen, "inspect_image", lambda p: {**inspect(p), "codec": "png", "has_alpha": True, "has_transparency": True, "has_visible_pixels": True, "alpha_min": 254, "alpha_max": 255})
    with pytest.raises(ValueError, match="透明"):
        qwen.materialize_image(result, tmp_path / "out", RuntimeConfig(), {"width": 1000, "height": 701, "transparent": True})


def test_browser_qwen_confirmation_needs_no_host_and_shares_video_slot(tmp_path, monkeypatch):
    from lfo.canvas.capabilities import CapabilityCatalog
    from lfo.canvas.service import CanvasService
    from lfo.canvas.settings import CanvasSettings

    cap = json.loads((qwen.SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    cap.update(installed=True, available=True)
    monkeypatch.setattr(CapabilityCatalog, "get", lambda *a, **k: cap)
    service = CanvasService(
        CanvasSettings(Path(__file__).resolve().parents[2], tmp_path / "state", tmp_path / "media"),
        start_worker=False,
    )
    try:
        graph = {
            "nodes": [
                {
                    "id": "image",
                    "type": "image",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "provider": "comfy-qwen-image",
                        "model": "qwen-image-2.1",
                        "mode": "create",
                        "prompt": "角色图",
                        "aspect_ratio": "1:1",
                        "megapixels": 1,
                    },
                }
            ],
            "edges": [],
        }
        canvas = service.store.create_canvas("Qwen", graph)
        run = service.confirm(canvas["id"], "image", canvas["version"], "unique-request")
        assert run["status"] == "queued"
        assert run["resource_key"] == "video" and run["resource_capacity"] == 1
        assert (
            service.confirm(canvas["id"], "image", canvas["version"], "unique-request")["id"]
            == run["id"]
        )
    finally:
        service.close()
