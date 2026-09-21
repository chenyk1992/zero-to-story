"""Read-only Canvas adapter tests for the H3 prompt linter."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
LINT_PATH = ROOT / ".agents" / "skills" / "h3-prompt-writing" / "scripts" / "h3_prompt_lint.py"
CLI_PATH = ROOT / ".agents" / "skills" / "h3-prompt-writing" / "scripts" / "validate_prompt.py"

LINT_SPEC = importlib.util.spec_from_file_location("h3_prompt_lint", LINT_PATH)
assert LINT_SPEC is not None and LINT_SPEC.loader is not None
LINT = importlib.util.module_from_spec(LINT_SPEC)
sys.modules[LINT_SPEC.name] = LINT
LINT_SPEC.loader.exec_module(LINT)

SPEC = importlib.util.spec_from_file_location("h3_prompt_validate_cli", CLI_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BASE = (
    "integrated_multimodal_description: [Shot 1] A woman waits by a door. "
    "[Shot 2] At 00:03.000, the camera cuts to her hand.\n\n"
    "overall_soundscape: Footsteps fade.\n\n"
    "non_diegetic_music: N/A"
)
SINGLE_SHOT = BASE.replace("[Shot 2] At 00:03.000, the camera cuts to her hand.", "")
PLAN = {
    "schema": "zero-to-story.creative-blueprint.v2",
    "panels": [{"id": "P001", "duration_s": 8, "shot_ids": ["C001"]}],
    "dialogue": [],
    "generation": {
        "panel_plans": [{"panel_id": "P001", "operation": "video.text_to_video"}],
        "shots": [{"id": "C001", "order": 1, "panel_id": "P001", "dialogue_ids": []}],
    },
}


class FakeClient:
    def __init__(self, responses: dict[str, list[Any]]) -> None:
        self.responses = {path: list(items) for path, items in responses.items()}
        self.calls: list[tuple[str, str, Any]] = []

    def request(self, method: str, path: str, body: Any = None) -> Any:
        assert method == "GET"
        assert body is None
        self.calls.append((method, path, body))
        result = self.responses[path].pop(0)
        if isinstance(result, Exception):
            raise result
        return copy.deepcopy(result)


def canvas(prompt: str = SINGLE_SHOT, *, version: int = 1) -> dict[str, Any]:
    return {
        "id": "canvas-1",
        "name": "test",
        "version": version,
        "graph": {
            "nodes": [
                {
                    "id": "video-1",
                    "type": "video",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "prompt": prompt,
                        "provider": "comfy",
                        "model": "h3",
                        "mode": "t2v",
                        "duration": 8,
                        "aspect_ratio": "16:9",
                    },
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": [],
        },
    }


def responses(
    first_canvas: dict[str, Any],
    second_canvas: dict[str, Any] | None = None,
    *,
    first_runs: list[dict[str, Any]] | None = None,
    second_runs: list[dict[str, Any]] | None = None,
    readiness: dict[str, Any] | None = None,
) -> dict[str, list[Any]]:
    return {
        "/api/canvases/canvas-1": [first_canvas, second_canvas or first_canvas],
        "/api/canvases/canvas-1/runs": [
            {"runs": first_runs or []},
            {"runs": second_runs if second_runs is not None else first_runs or []},
        ],
        "/api/readiness?canvas_id=canvas-1&node_id=video-1": [
            readiness or {"ready": True, "version": first_canvas["version"]}
        ],
    }


def test_inspect_canvas_is_get_only_and_returns_a_versioned_pass() -> None:
    client = FakeClient(responses(canvas()))
    result = MODULE.inspect_canvas(client, "canvas-1", "video-1", 1, blueprint=PLAN, panel_id="P001")

    assert result["status"] == "passed"
    assert result["canvas_version"] == 1
    assert result["input_digest"]
    assert all(method == "GET" and body is None for method, _, body in client.calls)


def test_valid_local_prompt_without_blueprint_needs_review() -> None:
    result = MODULE.inspect_canvas(FakeClient(responses(canvas())), "canvas-1", "video-1", 1)
    assert result["status"] == "needs_review"
    assert result["unverified"]


def test_structural_error_returns_failed_status() -> None:
    broken = canvas(BASE.replace("00:03.000", "00:10.000"))
    result = MODULE.inspect_canvas(FakeClient(responses(broken)), "canvas-1", "video-1", 1)
    assert result["status"] == "failed"
    assert any(finding["code"] == "H3-SHOTS" for finding in result["findings"])


@pytest.mark.parametrize(
    "client",
    [
        FakeClient(responses(canvas(), readiness={"ready": False, "version": 1, "reason": "missing input"})),
        FakeClient(responses(canvas(), canvas(version=2))),
    ],
)
def test_readiness_or_version_change_returns_unavailable(client: FakeClient) -> None:
    result = MODULE.inspect_canvas(client, "canvas-1", "video-1", 1)
    assert result["status"] == "unavailable"


def test_changed_effective_input_from_runs_returns_unavailable() -> None:
    prompt = (
        "For the target video, at 0.00 seconds into the target video, "
        "<Picture 1> (from [Shot 1]) is fully referenced.\n\n"
        f"{SINGLE_SHOT}"
    )
    current = canvas(prompt)
    current["graph"]["nodes"].insert(
        0,
        {
            "id": "image-1",
            "type": "image",
            "position": {"x": 0, "y": 0},
            "data": {"prompt": "frame", "provider": "codex-imagegen", "mode": "create"},
        },
    )
    current["graph"]["nodes"][1]["data"]["mode"] = "i2v"
    current["graph"]["edges"] = [
        {
            "id": "edge-1",
            "source": "image-1",
            "target": "video-1",
            "sourceHandle": "output",
            "targetHandle": "first_frame",
        }
    ]
    first_runs = [
        {
            "id": "image-run",
            "canvas_id": "canvas-1",
            "node_id": "image-1",
            "status": "succeeded",
            "outputs": [{"path": "old.png", "kind": "image"}],
            "updated_at": "2026-09-20T01:00:00Z",
        }
    ]
    second_runs = [{**first_runs[0], "outputs": [{"path": "new.png", "kind": "image"}]}]

    result = MODULE.inspect_canvas(
        FakeClient(responses(current, first_runs=first_runs, second_runs=second_runs)),
        "canvas-1",
        "video-1",
        1,
    )

    assert result["status"] == "unavailable"


def test_unrelated_run_change_does_not_invalidate_the_same_effective_input() -> None:
    first_runs = [{"id": "other", "canvas_id": "canvas-1", "node_id": "other", "status": "succeeded"}]
    second_runs = [{"id": "other-new", "canvas_id": "canvas-1", "node_id": "other", "status": "failed"}]
    result = MODULE.inspect_canvas(
        FakeClient(responses(canvas(), first_runs=first_runs, second_runs=second_runs)),
        "canvas-1",
        "video-1",
        1,
        blueprint=PLAN,
        panel_id="P001",
    )
    assert result["status"] == "passed"


def test_main_rejects_unpaired_blueprint_arguments_without_creating_a_client(capsys: Any) -> None:
    assert MODULE.main(["--canvas-id", "canvas-1", "--node-id", "video-1", "--expected-version", "1", "--blueprint", "x.json", "--json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "unavailable"


def test_main_reads_blueprint_without_modifying_it(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    blueprint = tmp_path / "creative_blueprint.json"
    original = json.dumps(PLAN, ensure_ascii=False, indent=2)
    blueprint.write_text(original, encoding="utf-8")
    client = FakeClient(
        {
            "/api/health": [{"status": "ok", "project_root": str(ROOT)}],
            **responses(canvas()),
        }
    )
    monkeypatch.setattr(MODULE.CanvasSettings, "resolve", lambda project_root: object())
    monkeypatch.setattr(MODULE, "CanvasClient", lambda settings, url=None: client)

    assert (
        MODULE.main(
            [
                "--canvas-id",
                "canvas-1",
                "--node-id",
                "video-1",
                "--expected-version",
                "1",
                "--project",
                str(ROOT),
                "--blueprint",
                str(blueprint),
                "--panel-id",
                "P001",
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert result["blueprint_digest"]
    assert blueprint.read_text(encoding="utf-8") == original


def test_main_stops_after_project_mismatch(monkeypatch: Any, capsys: Any) -> None:
    client = FakeClient({"/api/health": [{"status": "ok", "project_root": "C:/other-project"}]})
    monkeypatch.setattr(MODULE.CanvasSettings, "resolve", lambda project_root: object())
    monkeypatch.setattr(MODULE, "CanvasClient", lambda settings, url=None: client)

    assert MODULE.main(["--canvas-id", "canvas-1", "--node-id", "video-1", "--expected-version", "1", "--project", str(ROOT), "--json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "unavailable"
    assert [path for _, path, _ in client.calls] == ["/api/health"]
