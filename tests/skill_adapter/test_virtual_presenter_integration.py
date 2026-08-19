from __future__ import annotations

import pathlib

from lfo.backends.passthrough import PASSTHROUGH_BACKEND_ID
from lfo.backends.video_router import H3_PRESENTER_BACKEND_ID, build_video_backend_registry
from lfo.contracts.package import VideoExecutionPackage, validate_package
from lfo.execution.dag import build_dag
from lfo.execution.materializer import materialize
from lfo.services.artifact_layout import RunArtifactLayout
from lfo.skill_adapter.virtual_presenter import build_assembly_package, build_shot_package


def _plan() -> dict:
    return {
        "project": {
            "project_id": "presenter-integration",
            "title": "Presenter integration",
            "locale": "zh-CN",
        },
        "inputs": {
            "character_uri": "inputs/character.png",
            "panorama_uri": "inputs/panorama.png",
            "voice_uri": "inputs/voice.wav",
        },
        "output": {"width": 1080, "height": 1920, "fps": 24},
        "shots": [
            {
                "shot_id": "shot-001",
                "sequence": 1,
                "duration_ms": 5_000,
                "prompt": "<Picture 1> speaks with the voice of <Audio 1>.",
                "environment_view_uri": "environment-pack/yaw_0.png",
                "subtitles": {
                    "cues": [{"start_ms": 0, "end_ms": 1_000, "text": "你好"}]
                },
            },
            {
                "shot_id": "shot-002",
                "sequence": 2,
                "duration_ms": 5_000,
                "prompt": "<Picture 1> continues from <Video 1>.",
                "environment_view_uri": "environment-pack/yaw_0.png",
            },
        ],
        "approval": {"status": "approved", "reviewer": "user"},
    }


def _layout(
    tmp_path: pathlib.Path,
    run_id: str,
    package: VideoExecutionPackage,
) -> dict:
    return RunArtifactLayout.from_package(
        workspace_root=tmp_path / "workspace",
        run_id=run_id,
        package=package,
    ).to_dict()


def _resolutions(
    package: VideoExecutionPackage,
    tmp_path: pathlib.Path,
) -> dict[str, dict[str, str]]:
    return {
        asset.asset_key: {
            "asset_revision_id": f"revision-{index}",
            "file_path": str(tmp_path / asset.source.uri),
        }
        for index, asset in enumerate(package.assets)
    }


def test_presenter_and_assembly_packages_cross_the_public_runtime_boundary(
    tmp_path: pathlib.Path,
) -> None:
    registry = build_video_backend_registry()
    shot_package = build_shot_package(_plan(), "shot-001")
    assert validate_package(shot_package.to_dict()).ok

    shot_run = materialize(
        "shot-run",
        shot_package,
        "shot-package-hash",
        registry,
        asset_resolutions=_resolutions(shot_package, tmp_path),
        artifact_layout=_layout(tmp_path, "shot-run", shot_package),
    )
    shot_graph = build_dag(shot_run)
    shot_task = shot_graph.tasks_by_type("video.generate")[0]
    assert shot_task.metadata["backend_id"] == H3_PRESENTER_BACKEND_ID
    assert shot_task.metadata["operation"] == "video.virtual_presenter"
    assert [ref["slot"] for ref in shot_task.metadata["resolved_references"]] == [
        "ref_image_0",
        "ref_image_1",
        "ref_image_2",
        "ref_audio_0",
    ]

    assembly_package = build_assembly_package(
        _plan(),
        [
            {
                "shot_id": "shot-002",
                "sequence": 2,
                "duration_ms": 5_000,
                "uri": "accepted/shot-002.mp4",
            },
            {
                "shot_id": "shot-001",
                "sequence": 1,
                "duration_ms": 5_000,
                "uri": "accepted/shot-001.mp4",
            },
        ],
    )
    assert validate_package(assembly_package.to_dict()).ok
    assembly_run = materialize(
        "assembly-run",
        assembly_package,
        "assembly-package-hash",
        registry,
        asset_resolutions=_resolutions(assembly_package, tmp_path),
        artifact_layout=_layout(tmp_path, "assembly-run", assembly_package),
    )
    assembly_graph = build_dag(assembly_run)
    assembly_tasks = assembly_graph.tasks_by_type("video.generate")
    assert [task.clip_id for task in assembly_tasks] == ["shot-001", "shot-002"]
    assert all(task.metadata["backend_id"] == PASSTHROUGH_BACKEND_ID for task in assembly_tasks)
    assert all(task.metadata["operation"] == "video.passthrough" for task in assembly_tasks)
