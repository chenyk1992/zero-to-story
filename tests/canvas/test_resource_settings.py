from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from lfo.canvas.capabilities import CapabilityCatalog
from lfo.canvas.graph import CanvasError
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings


def test_runtime_image_limit_can_reduce_concurrency_without_changing_provider(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LFO_IMAGE_CONCURRENCY", "1")
    root = Path(__file__).resolve().parents[2]
    settings = CanvasSettings.resolve(root, tmp_path / "state", tmp_path / "media")
    service = CanvasService(settings, start_worker=False)
    try:
        graph = {
            "nodes": [
                {
                    "id": str(i),
                    "type": "image",
                    "position": {"x": i, "y": 0},
                    "data": {
                        "provider": "codex-imagegen",
                        "model": "image_gen",
                        "mode": "create",
                        "prompt": "independent image",
                    },
                }
                for i in range(2)
            ],
            "edges": [],
        }
        canvas = service.store.create_canvas("independent", graph)
        runs = [
            service.confirm(canvas["id"], str(i), canvas["version"], f"request-{i}")
            for i in range(2)
        ]
        service.claim_agent(runs[0]["id"], ["image_gen"])
        with pytest.raises(CanvasError, match="busy"):
            service.claim_agent(runs[1]["id"], ["image_gen"])
        assert all(
            run["snapshot"]["provider"] == "codex-imagegen" for run in service.store.list_runs()
        )
    finally:
        service.close()


@pytest.mark.parametrize("value", ["0", "3", "invalid"])
def test_invalid_image_limit_is_reported(tmp_path, monkeypatch, value):
    monkeypatch.setenv("LFO_IMAGE_CONCURRENCY", value)
    with pytest.raises(ValueError):
        CanvasSettings.resolve(tmp_path, tmp_path / "state", tmp_path / "media")


def test_project_comfy_mcp_config_satisfies_capability_check(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    skill = project / ".agents" / "skills" / "comfy-video"
    skill.mkdir(parents=True)
    (skill / "execute.py").write_text("", encoding="utf-8")
    (skill / "capability.json").write_text(
        json.dumps(
            {
                "id": "comfy",
                "execution": "script",
                "entrypoint": "execute.py",
                "node_types": ["video"],
                "requires_executables": ["comfy-mcp"],
            }
        ),
        encoding="utf-8",
    )
    from lfo.comfy import transport

    monkeypatch.setattr(transport, "load_runtime_config", lambda: transport.RuntimeConfig())

    capability = CapabilityCatalog(project).get("comfy")

    assert capability["available"] is True


def test_explicit_ffprobe_path_satisfies_capability_check(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    skill = project / ".agents" / "skills" / "media-probe"
    skill.mkdir(parents=True)
    (skill / "execute.py").write_text("", encoding="utf-8")
    (skill / "capability.json").write_text(
        json.dumps(
            {
                "id": "media-probe",
                "execution": "script",
                "entrypoint": "execute.py",
                "node_types": ["video"],
                "requires_executables": ["ffprobe"],
            }
        ),
        encoding="utf-8",
    )
    executable = tmp_path / "custom-ffprobe.exe"
    executable.write_bytes(b"test executable")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("LFO_FFPROBE", str(executable))

    capability = CapabilityCatalog(project).get("media-probe")

    assert capability["available"] is True


def test_aistudio_video_uses_independent_serial_resource_without_blocking_comfy_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("LFO_AISTUDIO_BASE_URL", "http://127.0.0.1:2048")
    from lfo.comfy import transport

    monkeypatch.setattr(transport, "load_runtime_config", lambda: transport.RuntimeConfig())
    settings = CanvasSettings.resolve(root, tmp_path / "state", tmp_path / "media")
    service = CanvasService(settings, start_worker=False)
    try:
        graph = {
            "nodes": [
                {
                    "id": "v_comfy",
                    "type": "video",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "provider": "comfy",
                        "model": "h3",
                        "mode": "t2v",
                        "prompt": "local comfy",
                        "duration": 5,
                        "aspect_ratio": "16:9",
                        "megapixels": 0.6,
                        "options": {"comfy": {"sampler_profile": "native", "steps": 12}},
                    },
                },
                {
                    "id": "v_aistudio_1",
                    "type": "video",
                    "position": {"x": 100, "y": 0},
                    "data": {
                        "provider": "aistudio-video",
                        "model": "gemini-omni-1.2-flash",
                        "mode": "t2v",
                        "prompt": "omni 1",
                        "duration": 5,
                        "aspect_ratio": "16:9",
                    },
                },
                {
                    "id": "v_aistudio_2",
                    "type": "video",
                    "position": {"x": 200, "y": 0},
                    "data": {
                        "provider": "aistudio-video",
                        "model": "gemini-omni-1.2-flash",
                        "mode": "t2v",
                        "prompt": "omni 2",
                        "duration": 5,
                        "aspect_ratio": "16:9",
                    },
                },
            ],
            "edges": [],
        }
        canvas = service.store.create_canvas("resources", graph)
        r_comfy = service.confirm(canvas["id"], "v_comfy", canvas["version"], "req-c1")
        r_ai1 = service.confirm(canvas["id"], "v_aistudio_1", canvas["version"], "req-a1")
        r_ai2 = service.confirm(canvas["id"], "v_aistudio_2", canvas["version"], "req-a2")

        assert r_comfy["resource_key"] == "video"
        assert r_ai1["resource_key"] == "aistudio-video"
        assert r_ai1["resource_capacity"] == 1

        # Claim Comfy local video -> AIStudio video can still run concurrently, while 2nd AIStudio waits
        service.store.claim_run(r_comfy["id"], owner_token="tok-c1")
        service.store.claim_run(r_ai1["id"], owner_token="tok-a1")
        with pytest.raises(CanvasError, match="busy"):
            service.store.claim_run(r_ai2["id"], owner_token="tok-a2")
    finally:
        service.close()


def test_video_model_affinity_reorders_without_starvation(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    settings = CanvasSettings.resolve(root, tmp_path / "state", tmp_path / "media")
    service = CanvasService(settings, start_worker=False)
    try:
        graph = {
            "nodes": [
                {"id": "v1", "type": "video", "position": {"x": 0, "y": 0}, "data": {"prompt": "p", "provider": "comfy", "mode": "t2v"}},
                {"id": "v2", "type": "video", "position": {"x": 100, "y": 0}, "data": {"prompt": "p", "provider": "comfy", "mode": "t2v"}},
                {"id": "v3", "type": "video", "position": {"x": 200, "y": 0}, "data": {"prompt": "p", "provider": "comfy", "mode": "t2v"}},
            ],
            "edges": [],
        }
        canvas = service.store.create_canvas("affinity", graph)
        prev = service.store.create_run(
            canvas["id"], "v1", canvas["version"], "prev-b",
            {"node_id": "v1", "node_type": "video", "provider": "comfy", "model": "model-B"},
            status="succeeded", resource_key="video",
        )
        assert service.store.latest_succeeded_signature("video") == ("comfy", "model-B")
        assert prev["status"] == "succeeded"

        q_a = service.store.create_run(
            canvas["id"], "v2", canvas["version"], "q-a",
            {"node_id": "v2", "node_type": "video", "provider": "comfy", "model": "model-A"},
            status="queued", resource_key="video",
        )
        q_b = service.store.create_run(
            canvas["id"], "v3", canvas["version"], "q-b",
            {"node_id": "v3", "node_type": "video", "provider": "comfy", "model": "model-B"},
            status="queued", resource_key="video",
        )

        # Matching model-B jumps ahead of queued model-A to avoid reloading
        reordered = service._prioritize_queued_runs(service.store.list_queued_runs())
        assert [r["id"] for r in reordered] == [q_b["id"], q_a["id"]]

        # Anti-starvation cap restores FIFO once streak reaches limit
        service._video_affinity_streak = service._MAX_AFFINITY_STREAK
        unreordered = service._prioritize_queued_runs(service.store.list_queued_runs())
        assert [r["id"] for r in unreordered] == [q_a["id"], q_b["id"]]
    finally:
        service.close()
