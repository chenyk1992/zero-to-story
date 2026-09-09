"""Focused tests for the provider-neutral canvas graph contract."""

from __future__ import annotations

import pytest

from lfo.canvas.graph import (
    GraphValidationError,
    MissingInputError,
    SnapshotResolutionError,
    resolve_snapshot,
    validate_graph,
)


def _node(node_id: str, node_type: str, data: dict | None = None) -> dict:
    values = dict(data or {})
    if node_type in {"image", "video"}:
        values.setdefault("provider", "codex-imagegen" if node_type == "image" else "comfy")
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": 0, "y": 0},
        "data": values,
    }


def _canvas(nodes: list[dict], edges: list[dict] | None = None) -> dict:
    return {
        "id": "canvas-1",
        "name": "test",
        "version": 1,
        "graph": {
            "nodes": nodes,
            "edges": edges or [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": [],
        },
    }


def _edge(
    edge_id: str,
    source: str,
    target: str,
    target_handle: str,
    source_handle: str = "output",
) -> dict:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "sourceHandle": source_handle,
        "targetHandle": target_handle,
    }


def test_prompt_and_result_nodes_are_removed_from_the_graph_contract() -> None:
    for node_type in ("prompt", "result"):
        with pytest.raises(GraphValidationError) as error:
            validate_graph({"nodes": [_node(node_type, node_type)]})
        assert error.value.code == "unknown_node_type"

    image = _node("image", "image", {"prompt": "直接写在图片节点", "mode": "create"})
    snapshot = resolve_snapshot(_canvas([image]), "image")
    assert snapshot["prompt"] == "直接写在图片节点"


def test_execution_edges_reject_removed_prompt_and_media_ports() -> None:
    nodes = [
        _node("image", "image", {"prompt": "a moon", "mode": "create"}),
        _node("video", "video", {"prompt": "animate", "mode": "t2v"}),
    ]
    for target_handle in ("prompt", "media"):
        with pytest.raises(GraphValidationError) as error:
            validate_graph({"nodes": nodes, "edges": [_edge("e", "image", "video", target_handle)]})
        assert error.value.code == "target_handle"


def test_validate_graph_rejects_unknown_type_and_execution_cycles() -> None:
    with pytest.raises(GraphValidationError) as type_error:
        validate_graph({"nodes": [_node("n", "unknown")]})
    assert type_error.value.code == "unknown_node_type"

    nodes = [_node("a", "image"), _node("b", "video")]
    edges = [_edge("e1", "a", "b", "reference_image"), _edge("e2", "b", "a", "reference_video")]
    with pytest.raises(GraphValidationError) as cycle_error:
        validate_graph({"nodes": nodes, "edges": edges})
    assert cycle_error.value.code == "graph_cycle"


def test_local_prompt_and_provider_options_are_resolved() -> None:
    nodes = [
        _node(
            "video-1",
            "video",
            {
                "prompt": "a red paper boat",
                "duration": 6,
                "aspect_ratio": "9:16",
                "megapixels": 0.4,
                "provider": "comfy",
                "model": "demo-model",
                "mode": "text_to_video",
                "options": {"comfy": {"steps": 8}},
            },
        )
    ]
    snapshot = resolve_snapshot(_canvas(nodes), "video-1")
    assert snapshot["prompt"] == "a red paper boat"
    assert snapshot["provider"] == "comfy"
    assert snapshot["parameters"] == {
        "duration": 6,
        "aspect_ratio": "9:16",
        "megapixels": 0.4,
        "steps": 8,
    }
    assert snapshot["inputs"] == {
        "reference_images": [],
        "reference_videos": [],
        "reference_audios": [],
    }


def test_generation_input_uses_embedded_asset_without_a_fake_run() -> None:
    nodes = [
        _node(
            "image-1",
            "image",
            {
                "prompt": "a moon",
                "mode": "create",
                "asset": {"path": "anchor.png", "kind": "image", "name": "anchor"},
            },
        ),
        _node("video-1", "video", {"prompt": "animate it", "mode": "image_to_video"}),
    ]
    canvas = _canvas(nodes, [_edge("image-edge", "image-1", "video-1", "first_frame")])
    snapshot = resolve_snapshot(canvas, "video-1", runs=[])
    assert snapshot["inputs"]["first_frame"] == {
        "path": "anchor.png",
        "kind": "image",
        "name": "anchor",
    }


def test_successful_run_is_newer_than_embedded_asset() -> None:
    nodes = [
        _node(
            "image-1",
            "image",
            {
                "prompt": "a moon",
                "mode": "create",
                "asset": {"path": "old.png", "kind": "image"},
            },
        ),
        _node("video-1", "video", {"prompt": "animate it", "mode": "image_to_video"}),
    ]
    canvas = _canvas(nodes, [_edge("image-edge", "image-1", "video-1", "first_frame")])
    runs = [
        {
            "id": "run-old",
            "canvas_id": "canvas-1",
            "node_id": "image-1",
            "status": "succeeded",
            "outputs": [{"path": "old-run.png", "kind": "image"}],
            "updated_at": "2026-09-08T01:00:00Z",
        },
        {
            "id": "run-new",
            "canvas_id": "canvas-1",
            "node_id": "image-1",
            "status": "succeeded",
            "outputs": [{"path": "new-run.png", "kind": "image"}],
            "updated_at": "2026-09-08T02:00:00Z",
        },
    ]
    snapshot = resolve_snapshot(canvas, "video-1", runs)
    assert snapshot["inputs"]["first_frame"]["path"] == "new-run.png"


def test_generated_input_requires_successful_run_or_embedded_asset() -> None:
    nodes = [
        _node("image-1", "image", {"prompt": "a moon", "mode": "create"}),
        _node("video-1", "video", {"prompt": "animate it", "mode": "image_to_video"}),
    ]
    canvas = _canvas(nodes, [_edge("image-edge", "image-1", "video-1", "first_frame")])
    with pytest.raises(MissingInputError) as missing_error:
        resolve_snapshot(canvas, "video-1", runs=[])
    assert missing_error.value.code == "missing_upstream_result"

    snapshot = resolve_snapshot(
        canvas,
        "video-1",
        runs=[
            {
                "node_id": "image-1",
                "canvas_id": "canvas-1",
                "status": "succeeded",
                "outputs": [{"path": "frame.png", "kind": "image", "name": "frame"}],
                "updated_at": "2026-09-08T01:00:00Z",
            }
        ],
    )
    assert snapshot["inputs"]["first_frame"]["path"] == "frame.png"


def test_derived_output_handle_resolves_fixed_asset_and_missing_is_explicit() -> None:
    nodes = [
        _node(
            "image-1",
            "image",
            {
                "prompt": "a moon",
                "mode": "create",
                "derived_outputs": [
                    {
                        "id": "first-frame",
                        "label": "首帧",
                        "asset": {"path": "fixed.png", "kind": "image"},
                        "source_version": "v1",
                    }
                ],
            },
        ),
        _node("video-1", "video", {"prompt": "animate it", "mode": "image_to_video"}),
    ]
    edge = _edge(
        "derived-edge", "image-1", "video-1", "first_frame", source_handle="output:first-frame"
    )
    canvas = _canvas(nodes, [edge])
    snapshot = resolve_snapshot(canvas, "video-1")
    assert snapshot["inputs"]["first_frame"]["path"] == "fixed.png"

    missing = _canvas(nodes, [_edge("missing", "image-1", "video-1", "first_frame", "output:nope")])
    with pytest.raises(MissingInputError) as error:
        resolve_snapshot(missing, "video-1")
    assert error.value.code == "missing_derived_output"


def test_derived_output_requires_a_real_asset() -> None:
    nodes = [
        _node(
            "image-1",
            "image",
            {
                "prompt": "a moon",
                "mode": "create",
                "derived_outputs": [
                    {"id": "broken", "label": "空结果", "asset": {"kind": "image"}}
                ],
            },
        ),
        _node("video-1", "video", {"prompt": "animate it", "mode": "image_to_video"}),
    ]
    with pytest.raises(GraphValidationError) as graph_error:
        validate_graph(
            {
                "nodes": nodes,
                "edges": [
                    _edge("broken-edge", "image-1", "video-1", "first_frame", "output:broken")
                ],
            }
        )
    assert graph_error.value.code == "asset_path"


def test_asset_edges_are_type_checked_and_draft_fields_can_be_empty() -> None:
    draft = {"nodes": [_node("video-1", "video")], "edges": []}
    normalized = validate_graph(draft)
    assert normalized["viewport"] == {"x": 0, "y": 0, "zoom": 1}
    assert normalized["selection"] == []

    bad_edge = [_edge("bad", "video-1", "document-1", "reference_image")]
    with pytest.raises(GraphValidationError) as edge_error:
        validate_graph(
            {
                "nodes": [_node("video-1", "video"), _node("document-1", "document")],
                "edges": bad_edge,
            }
        )
    assert edge_error.value.code == "incompatible_edge"


def test_document_section_and_workspace_metadata_are_preserved() -> None:
    graph = {
        "workspace": {
            "story": "一段故事",
            "chapter": "第一章",
            "summary": "冲突在雨夜发生",
            "source": "notes/story.md",
        },
        "nodes": [
            _node(
                "doc-1",
                "document",
                {
                    "category": "document",
                    "panel_id": "P001",
                    "description": "这一段的资料",
                    "content": "人物从门口走进来。",
                    "source_path": "notes/story.md",
                    "status": "draft",
                    "custom_field": {"keep": True},
                },
            ),
            _node(
                "section-1",
                "section",
                {"label": "第一幕背景", "width": 1200, "height": 800},
            ),
        ],
        "edges": [],
    }

    normalized = validate_graph(graph)

    assert normalized["workspace"] == graph["workspace"]
    assert normalized["nodes"][0]["type"] == "document"
    assert normalized["nodes"][0]["data"]["custom_field"] == {"keep": True}
    assert normalized["nodes"][1]["data"]["width"] == 1200


def test_history_and_derived_output_shape_is_preserved() -> None:
    node = _node(
        "image-1",
        "image",
        {
            "prompt": "当前画面",
            "mode": "create",
            "history": [
                {
                    "id": "v1",
                    "label": "第一版",
                    "asset": {"path": "v1.png", "kind": "image"},
                    "generation_snapshot": {"prompt": "第一版"},
                    "status": "accepted",
                    "source_path": "inputs/v1.png",
                }
            ],
            "derived_outputs": [
                {
                    "id": "frame",
                    "label": "固定首帧",
                    "asset": {"path": "frame.png", "kind": "image"},
                    "source_version": "v1",
                }
            ],
        },
    )
    normalized = validate_graph({"nodes": [node], "edges": []})
    assert normalized["nodes"][0]["data"]["history"][0]["generation_snapshot"] == {
        "prompt": "第一版"
    }
    assert normalized["nodes"][0]["data"]["derived_outputs"][0]["id"] == "frame"


def test_related_cycle_is_saveable_and_ignored_by_video_snapshot() -> None:
    nodes = [
        _node("document-1", "document", {"content": "资料不会成为视频输入"}),
        _node("video-1", "video", {"prompt": "雨夜里的门口", "provider": "comfy", "mode": "t2v"}),
    ]
    related_edges = [
        _edge("related-forward", "document-1", "video-1", "related"),
        _edge("related-back", "video-1", "document-1", "related"),
    ]

    graph = validate_graph({"nodes": nodes, "edges": related_edges})
    snapshot = resolve_snapshot(_canvas(graph["nodes"], graph["edges"]), "video-1")

    assert len(graph["edges"]) == 2
    assert snapshot["prompt"] == "雨夜里的门口"
    assert snapshot["inputs"] == {
        "reference_images": [],
        "reference_videos": [],
        "reference_audios": [],
    }


def test_related_edges_do_not_hide_an_execution_cycle() -> None:
    nodes = [
        _node("image-1", "image", {"prompt": "a moon", "mode": "create"}),
        _node("video-1", "video", {"prompt": "animate it", "mode": "image_to_video"}),
    ]
    edges = [
        _edge("related-forward", "image-1", "video-1", "related"),
        _edge("related-back", "video-1", "image-1", "related"),
        _edge("execution-forward", "image-1", "video-1", "first_frame"),
        _edge("execution-back", "video-1", "image-1", "reference_video"),
    ]

    with pytest.raises(GraphValidationError) as cycle_error:
        validate_graph({"nodes": nodes, "edges": edges})
    assert cycle_error.value.code == "graph_cycle"


def test_section_cannot_be_connected() -> None:
    edges = [_edge("section-edge", "section-1", "document-1", "related")]

    with pytest.raises(GraphValidationError) as edge_error:
        validate_graph(
            {
                "nodes": [_node("section-1", "section"), _node("document-1", "document")],
                "edges": edges,
            }
        )
    assert edge_error.value.code == "incompatible_edge"


def test_empty_prompt_and_mode_are_runtime_errors_but_draft_is_saveable() -> None:
    graph = {"nodes": [_node("video", "video", {"prompt": "", "mode": ""})], "edges": []}
    validate_graph(graph)
    with pytest.raises(MissingInputError) as prompt_error:
        resolve_snapshot(_canvas(graph["nodes"], graph["edges"]), "video")
    assert prompt_error.value.code == "missing_prompt"

    graph["nodes"][0]["data"]["prompt"] = "完成"
    with pytest.raises(MissingInputError) as mode_error:
        resolve_snapshot(_canvas(graph["nodes"], graph["edges"]), "video")
    assert mode_error.value.code == "missing_mode"


def test_provider_options_cannot_hide_common_parameters() -> None:
    node = _node(
        "image",
        "image",
        {
            "prompt": "画面",
            "mode": "create",
            "options": {"codex-imagegen": {"aspect_ratio": "1:1"}},
        },
    )
    with pytest.raises(SnapshotResolutionError, match="专属参数不能覆盖"):
        resolve_snapshot(_canvas([node]), "image")


@pytest.mark.parametrize("require_accept", [False, True])
def test_explicit_derived_run_cannot_select_another_runs_frame(require_accept):
    frame = {
        "id": "tail",
        "label": "实际末帧",
        "source_run_id": "other-run",
        "asset": {"path": "frame.png", "kind": "image", "sha256": "a" * 64},
    }
    nodes = [
        _node("previous", "video", {"derived_outputs": [frame]}),
        _node("next", "video", {"prompt": "接镜", "mode": "image_to_video"}),
    ]
    edge = {
        **_edge("continuity", "previous", "next", "first_frame", "output:tail"),
        "source_run_id": "adopted-run",
        "require_accept": require_accept,
    }
    run = {
        "id": "adopted-run",
        "canvas_id": "canvas-1",
        "node_id": "previous",
        "status": "succeeded",
        "review": {"decision": "ACCEPT", "output_path": "accepted.mp4", "output_sha256": "b" * 64},
    }
    with pytest.raises(MissingInputError) as raised:
        resolve_snapshot(_canvas(nodes, [edge]), "next", [run])
    assert raised.value.code == "derived_source_mismatch"
    frame["source_run_id"] = "adopted-run"
    result = resolve_snapshot(_canvas(nodes, [edge]), "next", [run])
    assert result["inputs"]["first_frame"]["source_run_id"] == "adopted-run"
    if require_accept:
        assert result["inputs"]["first_frame"]["accepted_sha256"] == "a" * 64
        frame["asset"].pop("sha256")
        with pytest.raises(MissingInputError) as missing_digest:
            resolve_snapshot(_canvas(nodes, [edge]), "next", [run])
        assert missing_digest.value.code == "derived_digest_missing"
