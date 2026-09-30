from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lfo.canvas.graph import resolve_snapshot
from lfo.canvas.media import CanvasMedia
from lfo.canvas.mv_preflight import inspect_mv_panel, mv_metadata_fingerprint
from lfo.canvas.settings import CanvasSettings


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _node(node_id: str, node_type: str, data: dict | None = None) -> dict:
    return {"id": node_id, "type": node_type, "position": {"x": 0, "y": 0}, "data": data or {}}


def _media(tmp_path: Path) -> CanvasMedia:
    project = tmp_path / "project"
    root = tmp_path / "media"
    project.mkdir(parents=True)
    root.mkdir(parents=True)
    return CanvasMedia(CanvasSettings(project, tmp_path / "state", root))


def _fixture(tmp_path: Path, *, mode: str = "r2v", target_handle: str = "reference_image"):
    media = _media(tmp_path)
    song_path = media.settings.media_root / "song.flac"
    song_path.write_bytes(b"accepted song bytes")
    image_path = media.settings.media_root / "lyrics.png"
    image_path.write_bytes(b"lyrics image bytes")
    sample_path = media.settings.media_root / "sample.mp4"
    sample_path.write_bytes(b"accepted sample bytes")
    song_sha, image_sha, sample_sha = _sha(song_path), _sha(image_path), _sha(sample_path)
    excerpt = "S01: the character turns into the warm light."
    graph = {
        "nodes": [
            _node("script", "document", {"content": f"# MV\n{excerpt}\nS02: another shot."}),
            _node("music", "audio"),
            _node("lyrics", "asset", {"asset": {"path": str(image_path), "kind": "image", "sha256": image_sha}}),
            _node("video", "video", {"prompt": "Animate the shot.", "provider": "comfy", "mode": mode}),
        ],
        "edges": [
            {
                "id": "lyrics-to-video",
                "source": "lyrics",
                "target": "video",
                "sourceHandle": "output",
                "targetHandle": target_handle,
            }
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": [],
        "workspace": {
            "mv_production": {
                "schema_version": 1,
                "script": {"node_id": "script", "version": "script-v2"},
                "song": {
                    "node_id": "music",
                    "run_id": "song-run",
                    "sha256": song_sha,
                    "duration_ms": 3000,
                },
                "panels": {
                    "video": {
                        "shot_id": "S01",
                        "script_excerpt": excerpt,
                        "song_window_ms": {"start": 200, "end": 2400},
                        "mode": mode,
                        "input_bindings": [
                            {
                                "id": "lyric-card",
                                "slot": "reference_images" if target_handle == "reference_image" else target_handle,
                                "source_node_id": "lyrics",
                                "sha256": image_sha,
                                "role": "typography",
                            }
                        ],
                        "text_events": [
                            {
                                "id": "main-phrase",
                                "text": "刚刚好",
                                "renderer": "h3",
                                "binding_id": "lyric-card",
                                "visual_check": {
                                    "decision": "ACCEPT",
                                    "asset_sha256": image_sha,
                                    "text_sha256": hashlib.sha256("刚刚好".encode()).hexdigest(),
                                    "evidence": "人工核对原文与版式；此字段不代表OCR结果",
                                },
                            }
                        ],
                    }
                },
            }
        },
    }
    runs = [
        {
            "id": "song-run",
            "canvas_id": "mv-canvas",
            "node_id": "music",
            "status": "succeeded",
            "outputs": [{"path": str(song_path), "kind": "audio", "metadata": {"duration_ms": 3000}}],
            "review": {"decision": "ACCEPT", "output_path": str(song_path), "output_sha256": song_sha},
        }
    ]
    canvas = {"id": "mv-canvas", "version": 7, "graph": graph}
    return canvas, runs, media, {"song": song_sha, "image": image_sha, "sample": sample_sha, "sample_path": sample_path}


def _inspect(canvas, runs, media, node_id="video", **kwargs):
    snapshot = resolve_snapshot(canvas, node_id, runs)
    return inspect_mv_panel(canvas, node_id, snapshot, runs, media, **kwargs)


def _codes(result: dict) -> set[str]:
    return {issue["code"] for issue in result["issues"]}


def test_valid_opted_in_mv_panel_freezes_scoped_context(tmp_path: Path) -> None:
    canvas, runs, media, hashes = _fixture(tmp_path)

    result = _inspect(canvas, runs, media)

    assert result["applicable"] is True
    assert result["ready"] is True
    assert result["issues"] == []
    context = result["context"]
    assert context["song"]["run_id"] == "song-run"
    assert context["panel"]["song_window_ms"] == {"start": 200, "end": 2400}
    assert context["panel"]["input_bindings"][0]["sha256"] == hashes["image"]
    assert context["panel"]["text_events"][0]["text"] == "刚刚好"
    assert {item["scope_role"] for item in context["media_versions"]} == {"song", "lyric-card"}
    assert "path" not in context["song"]


def test_old_non_mv_video_and_unlisted_panel_remain_compatible(tmp_path: Path) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    canvas["graph"]["workspace"].pop("mv_production")
    assert _inspect(canvas, runs, media) == {"applicable": False, "ready": True, "issues": []}

    canvas, runs, media, _ = _fixture(tmp_path / "second")
    canvas["graph"]["workspace"]["mv_production"]["panels"].pop("video")
    result = _inspect(canvas, runs, media)
    assert result["applicable"] is False and result["ready"] is True


def test_related_edge_does_not_supply_an_actual_text_image_input(tmp_path: Path) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    canvas["graph"]["edges"][0]["targetHandle"] = "related"

    result = _inspect(canvas, runs, media)

    assert result["ready"] is False
    assert {"mv_input_binding_stale", "mv_text_image_required"} <= _codes(result)


def test_i2v_text_image_must_be_the_actual_first_frame_and_match_file_bytes(tmp_path: Path) -> None:
    canvas, runs, media, _ = _fixture(tmp_path, mode="i2v", target_handle="reference_image")

    wrong_slot = _inspect(canvas, runs, media)
    assert "mv_text_image_wrong_slot" in _codes(wrong_slot)

    image_path = Path(canvas["graph"]["nodes"][2]["data"]["asset"]["path"])
    image_path.write_bytes(b"new image version")
    stale_image = _inspect(canvas, runs, media)
    assert "mv_input_untracked" in _codes(stale_image)
    assert "mv_input_binding_stale" in _codes(stale_image)


def test_generated_reference_image_binds_the_exact_successful_source_run(tmp_path: Path) -> None:
    canvas, runs, media, hashes = _fixture(tmp_path)
    image_path = Path(canvas["graph"]["nodes"][2]["data"]["asset"]["path"])
    canvas["graph"]["nodes"][2] = _node(
        "lyrics", "image", {"prompt": "exact lyric card", "provider": "codex-imagegen", "mode": "create"}
    )
    canvas["graph"]["edges"][0]["source_run_id"] = "image-run"
    image_run = {
        "id": "image-run",
        "canvas_id": "mv-canvas",
        "node_id": "lyrics",
        "status": "succeeded",
        "outputs": [{"path": str(image_path), "kind": "image", "sha256": hashes["image"]}],
    }
    runs.append(image_run)
    panel = canvas["graph"]["workspace"]["mv_production"]["panels"]["video"]
    panel["input_bindings"][0]["source_run_id"] = "image-run"

    result = _inspect(canvas, runs, media)

    assert result["ready"] is True
    binding = result["context"]["panel"]["input_bindings"][0]
    assert binding["source_node_id"] == "lyrics"
    assert binding["source_run_id"] == "image-run"
    assert binding["sha256"] == hashes["image"]


def test_changed_song_review_or_duration_blocks_only_the_current_panel(tmp_path: Path) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    runs[0]["review"]["decision"] = "REJECT"

    result = _inspect(canvas, runs, media)
    assert "mv_song_not_accepted" in _codes(result)

    # An unrelated video remains outside the declared MV scope.
    assert inspect_mv_panel(
        canvas, "other-video", {}, runs, media
    ) == {"applicable": False, "ready": True, "issues": []}


def test_song_window_uses_selected_song_duration_and_context_is_panel_scoped(tmp_path: Path) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    result = _inspect(canvas, runs, media)
    before = mv_metadata_fingerprint(canvas, "video", runs)
    assert result["ready"]

    # Unrelated script text/version changes do not stale this shot excerpt.
    canvas["graph"]["nodes"][0]["data"]["content"] += "\nS99: a separate unrelated shot."
    canvas["graph"]["workspace"]["mv_production"]["script"]["version"] = "draft-5"
    assert mv_metadata_fingerprint(canvas, "video", runs) == before

    canvas["graph"]["workspace"]["mv_production"]["panels"]["video"]["song_window_ms"]["end"] = 4000
    stale = _inspect(canvas, runs, media)
    assert "mv_song_window_out_of_range" in _codes(stale)
    assert mv_metadata_fingerprint(canvas, "video", runs) != before


def test_existing_selected_song_asset_is_supported_when_version_and_duration_are_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    song_path = media.settings.media_root / "existing-song.flac"
    song_path.write_bytes(b"existing track")
    song_sha = _sha(song_path)
    canvas["graph"]["nodes"][1] = _node(
        "existing-song",
        "asset",
        {
            "asset": {
                "path": str(song_path),
                "kind": "audio",
                "sha256": song_sha,
                "metadata": {"duration_ms": 3000},
            }
        },
    )
    production = canvas["graph"]["workspace"]["mv_production"]
    production["song"] = {
        "node_id": "existing-song",
        "sha256": song_sha,
        "duration_ms": 3000,
        "imported_selection": {
            "decision": "ACCEPT",
            "asset_sha256": song_sha,
            "source": "user-selected local track",
            "evidence": "用户选择此文件作为MV主音轨",
        },
    }
    monkeypatch.setattr(
        "lfo.canvas.mv_preflight.probe",
        lambda _path: {"has_audio": True, "width": None, "duration_ms": 3000},
    )

    result = _inspect(canvas, runs, media)

    assert result["ready"] is True
    assert result["context"]["song"]["source_type"] == "asset"
    assert result["context"]["song"]["imported_selection"]["decision"] == "ACCEPT"

    before = mv_metadata_fingerprint(canvas, "video", runs)
    asset = canvas["graph"]["nodes"][1]["data"]["asset"]
    asset["path"] = str(song_path) + ".renamed"
    assert mv_metadata_fingerprint(canvas, "video", runs) != before


def test_existing_song_requires_selection_evidence_bound_to_asset_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    song_path = media.settings.media_root / "existing-song.flac"
    song_path.write_bytes(b"existing track")
    song_sha = _sha(song_path)
    canvas["graph"]["nodes"][1] = _node(
        "existing-song", "asset", {"asset": {
            "path": str(song_path), "kind": "audio", "sha256": song_sha,
            "metadata": {"duration_ms": 3000},
        }}
    )
    production = canvas["graph"]["workspace"]["mv_production"]
    production["song"] = {
        "node_id": "existing-song", "sha256": song_sha, "duration_ms": 3000,
        "imported_selection": {
            "decision": "ACCEPT", "asset_sha256": "0" * 64,
            "source": "user-selected local track", "evidence": "User chose the track",
        },
    }
    monkeypatch.setattr(
        "lfo.canvas.mv_preflight.probe",
        lambda _path: {"has_audio": True, "width": None, "duration_ms": 3000},
    )
    result = _inspect(canvas, runs, media)
    assert "mv_song_selection_evidence_stale" in _codes(result)


def test_first_representative_clip_can_run_before_it_has_an_accepted_result(tmp_path: Path) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    canvas["graph"]["workspace"]["mv_production"]["panels"]["video"]["representative"] = True

    result = _inspect(canvas, runs, media)

    assert result["ready"] is True
    assert result["context"]["panel"]["representative_evidence"] == {
        "role": "sample",
        "pending_review": True,
    }


def test_continuity_requires_accepted_real_tail_derived_from_the_named_run(tmp_path: Path) -> None:
    canvas, runs, media, hashes = _fixture(tmp_path, mode="i2v", target_handle="first_frame")
    tail_path = media.settings.media_root / "accepted-tail.png"
    tail_path.write_bytes(b"real derived tail")
    tail_sha = _sha(tail_path)
    previous_path = media.settings.media_root / "previous.mp4"
    previous_path.write_bytes(b"accepted previous video")
    previous_sha = _sha(previous_path)
    previous_run = {
        "id": "previous-run",
        "canvas_id": "mv-canvas",
        "node_id": "previous",
        "status": "succeeded",
        "outputs": [{"path": str(previous_path), "kind": "video"}],
        "review": {"decision": "ACCEPT", "output_path": str(previous_path), "output_sha256": previous_sha},
    }
    runs.append(previous_run)
    graph = canvas["graph"]
    graph["nodes"].insert(2, _node("previous", "video", {
        "prompt": "previous accepted shot", "mode": "i2v",
        "derived_outputs": [{
            "id": "tail", "label": "accepted tail", "source_run_id": "previous-run",
            "asset": {"path": str(tail_path), "kind": "image", "sha256": tail_sha},
        }],
    }))
    graph["nodes"][3] = _node("lyrics", "asset", {"asset": {"path": str(tail_path), "kind": "image", "sha256": tail_sha}})
    # The same tail is also the selected lyric/text image in this test panel.
    panel = graph["workspace"]["mv_production"]["panels"]["video"]
    panel["input_bindings"] = [{
        "id": "carry-tail", "slot": "first_frame", "source_node_id": "previous",
        "source_run_id": "previous-run", "sha256": tail_sha, "role": "opening-state",
    }]
    panel["text_events"] = []
    panel["continuity"] = {
        "source_run_id": "previous-run", "source_node_id": "previous",
        "binding_id": "carry-tail", "tail_sha256": tail_sha,
    }
    graph["edges"] = [{
        "id": "carry", "source": "previous", "target": "video",
        "sourceHandle": "output:tail", "targetHandle": "first_frame",
        "source_run_id": "previous-run", "require_accept": True,
    }]

    result = _inspect(canvas, runs, media)

    assert result["ready"] is True
    assert result["context"]["panel"]["continuity"]["tail_sha256"] == tail_sha

    graph["edges"][0]["require_accept"] = False
    invalid = _inspect(canvas, runs, media)
    assert "mv_continuity_not_derived_tail" in _codes(invalid)


def test_representative_evidence_is_bound_to_local_song_script_and_inputs(tmp_path: Path) -> None:
    canvas, runs, media, hashes = _fixture(tmp_path)
    sample_path = hashes["sample_path"]
    sample_run = {
        "id": "sample-run",
        "canvas_id": "mv-canvas",
        "node_id": "video",
        "status": "succeeded",
        "outputs": [{"path": str(sample_path), "kind": "video"}],
        "review": {"decision": "ACCEPT", "output_path": str(sample_path), "output_sha256": hashes["sample"]},
        "snapshot": {
            "mode": "r2v",
            "inputs": {
                "first_frame": None,
                "reference_images": [{
                    "path": str(media.settings.media_root / "lyrics.png"),
                    "kind": "image",
                    "sha256": hashes["image"],
                }],
            },
        },
    }
    runs.append(sample_run)
    panel = canvas["graph"]["workspace"]["mv_production"]["panels"]["video"]
    excerpt_sha = hashlib.sha256(panel["script_excerpt"].encode()).hexdigest()
    panel["requires_representative"] = True
    panel["representative_evidence"] = {
        "run_id": "sample-run",
        "output_sha256": hashes["sample"],
        "song_sha256": hashes["song"],
        "script_excerpt_sha256": excerpt_sha,
        "input_sha256s": [hashes["image"]],
        "mode": "r2v",
        "scope": {
            "shot_ids": ["S01", "S02"],
            "mode": "r2v",
            "roles": ["typography"],
            "sample_window_ms": {"start": 0, "end": 2500},
        },
        "evidence": "sample reviewed for lyric legibility and phrase alignment",
    }

    result = _inspect(canvas, runs, media)
    assert result["ready"] is True

    panel["representative_evidence"]["script_excerpt_sha256"] = None
    missing_script = _inspect(canvas, runs, media)
    assert "mv_representative_script_stale" in _codes(missing_script)
    panel["representative_evidence"]["script_excerpt_sha256"] = excerpt_sha

    panel["representative_evidence"]["scope"]["roles"] = ["unused-role"]
    panel["representative_evidence"]["input_sha256s"] = []
    unknown_role = _inspect(canvas, runs, media)
    assert "mv_representative_roles_stale" in _codes(unknown_role)
    panel["representative_evidence"]["scope"]["roles"] = ["typography"]
    panel["representative_evidence"]["input_sha256s"] = [hashes["image"]]

    panel["representative_evidence"]["input_sha256s"] = []
    stale = _inspect(canvas, runs, media)
    assert "mv_representative_inputs_stale" in _codes(stale)


def test_image_free_t2v_representative_can_use_empty_roles_and_hashes(tmp_path: Path) -> None:
    canvas, runs, media, hashes = _fixture(tmp_path)
    graph = canvas["graph"]
    graph["edges"] = []
    video = next(node for node in graph["nodes"] if node["id"] == "video")
    video["data"]["mode"] = "t2v"
    panel = graph["workspace"]["mv_production"]["panels"]["video"]
    panel["mode"] = "t2v"
    panel["input_bindings"] = []
    panel["text_events"] = []
    panel["requires_representative"] = True
    excerpt_sha = hashlib.sha256(panel["script_excerpt"].encode()).hexdigest()
    sample_path = hashes["sample_path"]
    runs.append({
        "id": "sample-run", "canvas_id": "mv-canvas", "node_id": "video",
        "status": "succeeded", "outputs": [], "review": {
            "decision": "ACCEPT", "output_path": str(sample_path), "output_sha256": hashes["sample"],
        },
        "snapshot": {"mode": "t2v", "inputs": {"first_frame": None, "reference_images": []}},
    })
    panel["representative_evidence"] = {
        "run_id": "sample-run", "output_sha256": hashes["sample"],
        "song_sha256": hashes["song"], "script_excerpt_sha256": excerpt_sha,
        "input_sha256s": [], "mode": "t2v",
        "scope": {"shot_ids": ["S01"], "mode": "t2v", "roles": [],
                  "sample_window_ms": {"start": 0, "end": 2000}},
        "evidence": "Image-free T2V representative sample reviewed",
    }

    result = _inspect(canvas, runs, media)

    assert result["ready"] is True


def test_malformed_review_and_representative_hash_metadata_returns_issues(tmp_path: Path) -> None:
    canvas, runs, media, _ = _fixture(tmp_path)
    runs[0]["review"] = "not-an-object"
    result = _inspect(canvas, runs, media)
    assert "mv_song_not_accepted" in _codes(result)

    canvas, runs, media, hashes = _fixture(tmp_path / "rep")
    sample_path = hashes["sample_path"]
    runs.append({
        "id": "sample-run", "canvas_id": "mv-canvas", "node_id": "video",
        "status": "succeeded", "outputs": [], "review": {
            "decision": "ACCEPT", "output_path": str(sample_path), "output_sha256": hashes["sample"],
        },
        "snapshot": {"mode": "r2v", "inputs": {"reference_images": []}},
    })
    panel = canvas["graph"]["workspace"]["mv_production"]["panels"]["video"]
    panel["requires_representative"] = True
    panel["representative_evidence"] = {
        "run_id": "sample-run", "output_sha256": hashes["sample"],
        "song_sha256": hashes["song"], "script_excerpt_sha256": hashlib.sha256(panel["script_excerpt"].encode()).hexdigest(),
        "input_sha256s": [None, {}], "mode": "r2v",
        "scope": {"shot_ids": ["S01"], "mode": "r2v", "roles": ["typography"],
                  "sample_window_ms": {"start": 0, "end": 2000}},
        "evidence": "sample reviewed",
    }
    malformed = _inspect(canvas, runs, media)
    assert "mv_representative_inputs_stale" in _codes(malformed)
