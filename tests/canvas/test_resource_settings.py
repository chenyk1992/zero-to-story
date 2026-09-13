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


def test_explicit_comfy_cli_path_satisfies_capability_check(tmp_path, monkeypatch) -> None:
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
                "requires_executables": ["comfy"],
            }
        ),
        encoding="utf-8",
    )
    executable = tmp_path / "custom-comfy.exe"
    executable.write_bytes(b"test executable")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("LFO_COMFY_CLI", str(executable))

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
