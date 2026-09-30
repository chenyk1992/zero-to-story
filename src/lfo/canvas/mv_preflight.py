"""Opt-in, provider-neutral preflight for Music Video panels.

The metadata lives at ``graph.workspace.mv_production``.  It deliberately
describes only selected MV video nodes, so ordinary video and older canvases
remain unchanged.  The service calls :func:`inspect_mv_panel` after resolving
the regular generation snapshot and before confirmation; the returned context
can be frozen beside (never merged into) the provider prompt or inputs.

Schema, version 1::

    {
      "schema_version": 1,
      "script": {"node_id": "script-doc", "version": "draft-4"},
      "song": {"node_id": "music", "run_id": "music-run",
               "sha256": "<accepted file sha256>", "duration_ms": 178352},
      "panels": {
        "mv-p01": {
          "shot_id": "S01",
          "script_excerpt": "The exact, short script passage for this shot.",
          "song_window_ms": {"start": 0, "end": 4200},
          "mode": "i2v",
          "input_bindings": [{
            "id": "opening-card", "slot": "first_frame",
            "source_node_id": "lyrics-image", "source_run_id": "image-run",
            "sha256": "<image sha256>", "role": "typography"
          }],
          "text_events": [{
            "id": "hook-1", "text": "刚刚好", "renderer": "h3",
            "binding_id": "opening-card",
            "visual_check": {"decision": "ACCEPT",
              "asset_sha256": "<same image sha256>",
              "text_sha256": "<sha256 of the exact declared text>",
              "evidence": "人工核对了原文与版式"}
          }],
          "continuity": {"source_run_id": "previous-run",
            "source_node_id": "previous-shot", "binding_id": "carry-tail",
            "tail_sha256": "<accepted derived tail sha256>"},
          "requires_representative": true,
          "representative_evidence": {
            "run_id": "sample-run", "output_sha256": "<accepted video sha256>",
            "song_sha256": "<accepted song sha256>",
            "script_excerpt_sha256": "<sha256 of this panel excerpt>",
            "mode": "i2v",
            "scope": {"shot_ids": ["S01", "S02"],
              "mode": "i2v",
              "roles": ["typography"],
              "sample_window_ms": {"start": 0, "end": 4200}},
            "input_sha256s": ["<only the scoped typography inputs>"],
            "evidence": "试听及画面检查记录"
          }
        }
      }
    }

An imported track replaces the generated ``song`` example above with an
``asset`` node binding and an explicit user adoption record::

    "song": {
      "node_id": "existing-song",
      "sha256": "<imported file sha256>",
      "duration_ms": 178352,
      "imported_selection": {
        "decision": "ACCEPT",
        "asset_sha256": "<same imported file sha256>",
        "source": "user-selected local track",
        "evidence": "User chose this file as the master track for the MV"
      }
    }

``input_bindings`` enumerate this panel's actual first-frame and image-reference
inputs.  They do not prescribe a three-card or three-view set; a panel with no
picture inputs uses an empty array.  Only explicitly selected ``h3`` text
events need an image binding and a version-bound human observation.  This
module verifies the claimed binding and stored evidence fields, not pixels,
OCR, typography quality, lyric accuracy, or timing.  A ``post`` event is
outside the H3 image requirement.  Regular ``related`` edges never satisfy a
slot.

This preflight only checks files and existing Canvas ACCEPT reviews.  It does
not create a second review state, submit work, or add provider parameters.
The first sample Panel uses ``"representative": true`` and may proceed before
it has an output to review. After that run is accepted, expansion Panels use
``"requires_representative": true`` and bind the accepted sample plus an
explicit scope. Scope roles and hashes are local to the expansion Panel; an
unrelated script paragraph or another Panel's asset does not stale them.

An existing user-selected song is represented by an ``asset`` node instead
of inventing a run. Its asset must include the imported file's SHA-256 and
``metadata.duration_ms``; ``song.imported_selection`` records the selected
source, decision, evidence, and matching asset digest. Confirmation checks
the actual digest and probes the actual audio duration. A generated song uses
the existing audio run's Canvas ``ACCEPT`` review.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from lfo.canvas.graph import resolve_input_bindings, validate_graph
from lfo.media._ffmpeg import probe

_HEX = frozenset("0123456789abcdef")
_IMAGE_SLOTS = frozenset({"first_frame", "reference_images"})


def mv_metadata_fingerprint(
    canvas: Mapping[str, Any], node_id: str, runs: Sequence[Mapping[str, Any]] | None = None
) -> str | None:
    """Return a cheap declaration fingerprint for one opted-in MV panel.

    It hashes only the selected shot's script excerpt and declared production
    bindings plus the selected song run's database status/review.  It performs
    no media I/O.  Callers can compare this with the fingerprint frozen at
    confirmation; media byte changes are separately checked by
    ``CanvasMedia.inputs_unchanged`` using the preflight context's
    ``media_versions``.
    """

    try:
        graph = validate_graph(canvas["graph"])
        workspace = graph.get("workspace", {})
        production = workspace.get("mv_production")
        if not isinstance(production, Mapping):
            return None
        panels = production.get("panels")
        panel = panels.get(node_id) if isinstance(panels, Mapping) else None
        if not isinstance(panel, Mapping):
            return None
        song = production.get("song", {})
        run_list = list(runs or ())
        song_run_id = song.get("run_id") if isinstance(song, Mapping) else None
        song_run = _find_run(run_list, song_run_id)
        script = production.get("script")
        excerpt = panel.get("script_excerpt")
        script_node_id = script.get("node_id") if isinstance(script, Mapping) else None
        script_node = next(
            (item for item in graph["nodes"] if item.get("id") == script_node_id), None
        )
        script_data = script_node.get("data", {}) if script_node else {}
        script_content = script_data.get("content") if isinstance(script_data, Mapping) else None
        payload = {
            "schema_version": production.get("schema_version"),
            # A source-wide script revision is not a panel dependency. Bind
            # this shot to its exact excerpt and whether it is still present.
            "script_panel_binding": {
                "node_id": script_node_id,
                "excerpt_sha256": _sha_text(excerpt) if isinstance(excerpt, str) else None,
                "excerpt_present": isinstance(excerpt, str)
                and isinstance(script_content, str)
                and excerpt in script_content,
            },
            "song": {
                **(dict(song) if isinstance(song, Mapping) else {}),
                "asset_binding": _song_asset_fingerprint(graph, song),
                "run_status": song_run.get("status") if song_run else None,
                "run_review": {
                    key: (_review(song_run) or {}).get(key)
                    for key in ("decision", "output_path", "output_sha256")
                },
            },
            "panel": dict(panel),
        }
        return _json_sha(payload)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def inspect_mv_panel(
    canvas: Mapping[str, Any],
    node_id: str,
    snapshot: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    media: Any,
    *,
    verify_files: bool = True,
) -> dict[str, Any]:
    """Check one MV panel and return actionable issues plus a frozen context.

    ``snapshot`` must be the already-resolved provider-neutral snapshot from
    ``resolve_snapshot``. ``media`` is the service's ``CanvasMedia`` instance;
    Confirmation uses the default full byte checks. A readiness poll may pass
    ``verify_files=False`` to check bindings and paths without rereading the
    full song; the frozen run's ``media_versions`` can then use CanvasMedia's
    stat-cached ``inputs_unchanged`` check.
    """

    panel_id: str | None = None
    issues: list[dict[str, str]] = []

    def add(code: str, message: str, *, shot_id: str | None = None) -> None:
        issue = {"code": code, "severity": "error", "node_id": node_id, "message": message}
        if shot_id:
            issue["shot_id"] = shot_id
        issues.append(issue)

    try:
        graph = validate_graph(canvas["graph"])
    except (KeyError, TypeError, ValueError) as exc:
        return _result(False, [
            {"code": "mv_graph_invalid", "severity": "error", "node_id": node_id,
             "message": str(exc)}
        ])

    workspace = graph.get("workspace", {})
    production = workspace.get("mv_production") if isinstance(workspace, Mapping) else None
    if not isinstance(production, Mapping):
        return _result(False, [])
    panels = production.get("panels")
    raw_panel = panels.get(node_id) if isinstance(panels, Mapping) else None
    if not isinstance(raw_panel, Mapping):
        # The workspace opts individual video nodes into MV-specific checks.
        return _result(False, [])
    panel = dict(raw_panel)
    panel_id = _nonempty(panel.get("shot_id"))
    if not panel_id:
        add("mv_shot_id_required", "MV Panel需要明确的shot_id")

    if production.get("schema_version") != 1:
        add("mv_schema_unsupported", "MV生产元数据schema_version必须为1", shot_id=panel_id)

    script_context, script_content = _script_source(graph, production.get("script"), add, panel_id)
    excerpt = _nonempty(panel.get("script_excerpt"))
    excerpt_sha: str | None = None
    if not excerpt:
        add("mv_script_excerpt_required", "当前Panel需要绑定对应的简短脚本片段", shot_id=panel_id)
    elif script_content is not None:
        if excerpt not in script_content:
            add("mv_script_excerpt_stale", "脚本来源中已找不到当前Panel绑定的片段；请只更新受影响Panel", shot_id=panel_id)
        excerpt_sha = _sha_text(excerpt)

    song_context, song_path = _song_source(
        graph, production.get("song"), runs, media, add, panel_id, verify_files
    )
    window = _valid_window(panel.get("song_window_ms"), add, panel_id)
    if window and song_context and window[1] > song_context["duration_ms"]:
        add("mv_song_window_out_of_range", "Panel歌曲时间窗超出当前采用歌曲时长", shot_id=panel_id)

    if snapshot.get("node_type") != "video":
        add("mv_panel_not_video", "MV Panel必须对应视频节点", shot_id=panel_id)
    mode = _nonempty(panel.get("mode"))
    if not mode:
        add("mv_mode_required", "MV Panel需要记录实际视频模式", shot_id=panel_id)
    elif mode != snapshot.get("mode"):
        add("mv_mode_stale", "Panel记录的视频模式与当前实际快照不一致", shot_id=panel_id)

    bindings_by_id, bound_context, _image_hashes = _image_input_bindings(
        canvas, node_id, snapshot, runs, panel.get("input_bindings"), media, add, panel_id,
        verify_files,
    )
    _check_text_events(panel.get("text_events", []), bindings_by_id, mode, add, panel_id)

    continuity_context = _check_continuity(
        canvas,
        node_id,
        panel.get("continuity"),
        bindings_by_id,
        snapshot,
        runs,
        media,
        add,
        panel_id,
        verify_files,
    )

    representative_context = _check_representative(
        panel, panel_id, panel.get("representative_evidence"),
        excerpt_sha, song_context, bindings_by_id, mode, runs, media, add, verify_files
    )

    declaration_fingerprint = mv_metadata_fingerprint(canvas, node_id, runs)
    context: dict[str, Any] = {
        "schema_version": 1,
        "declaration_fingerprint": declaration_fingerprint,
        "panel": {
            "node_id": node_id,
            "shot_id": panel_id,
            "mode": mode,
            "script_excerpt_sha256": excerpt_sha,
            "song_window_ms": {"start": window[0], "end": window[1]} if window else None,
            "input_bindings": bound_context,
            "text_events": _context_text_events(panel.get("text_events", [])),
            "continuity": continuity_context,
            "representative_evidence": representative_context,
        },
        "script": script_context,
        "song": song_context,
        "media_versions": [],
    }
    if song_path and song_context:
        context["media_versions"].append(
            {"path": str(song_path), "sha256": song_context["sha256"], "scope_role": "song"}
        )
    context["media_versions"].extend(
        {"path": item["path"], "sha256": item["sha256"], "scope_role": item["id"]}
        for item in bound_context
    )
    # The full document hash is trace information. The scoped fingerprint uses
    # this Panel's exact excerpt and inputs only, so unrelated script edits do
    # not invalidate its earlier representative evidence.
    context["context_fingerprint"] = _json_sha({
        "declaration_fingerprint": declaration_fingerprint,
        "panel": context["panel"],
        "song": context["song"],
        "media_versions": context["media_versions"],
    })
    return _result(True, issues, context)


def _result(applicable: bool, issues: list[dict[str, str]], context: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "applicable": applicable,
        "ready": not any(item["severity"] == "error" for item in issues),
        "issues": issues,
    }
    if context is not None:
        result["context"] = context
    return result


def _script_source(
    graph: Mapping[str, Any], value: Any, add: Any, shot_id: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, Mapping):
        add("mv_script_source_required", "MV项目需要绑定画布中的脚本文档", shot_id=shot_id)
        return None, None
    node_id, version = _nonempty(value.get("node_id")), _nonempty(value.get("version"))
    if not node_id or not version:
        add("mv_script_source_invalid", "脚本来源需要node_id和version", shot_id=shot_id)
        return None, None
    node = next((item for item in graph["nodes"] if item["id"] == node_id), None)
    content = node.get("data", {}).get("content") if node else None
    if not node or node["type"] != "document" or not isinstance(content, str) or not content.strip():
        add("mv_script_source_missing", "脚本来源必须是有正文的document节点", shot_id=shot_id)
        return None, None
    return {"node_id": node_id, "sha256": _sha_text(content)}, content


def _song_source(
    graph: Mapping[str, Any], value: Any, runs: Sequence[Mapping[str, Any]], media: Any,
    add: Any, shot_id: str | None, verify_files: bool,
) -> tuple[dict[str, Any] | None, Path | None]:
    if not isinstance(value, Mapping):
        add("mv_song_source_required", "MV项目需要绑定一首已采用的歌曲版本", shot_id=shot_id)
        return None, None
    node_id = _nonempty(value.get("node_id"))
    run_id = _nonempty(value.get("run_id"))
    expected_sha = _valid_sha(value.get("sha256"))
    duration = _positive_int(value.get("duration_ms"))
    node = next((item for item in graph["nodes"] if item["id"] == node_id), None)
    run = _find_run(runs, run_id)
    if not node_id or not expected_sha or not duration:
        add("mv_song_binding_invalid", "歌曲绑定需要node_id、sha256和实际duration_ms", shot_id=shot_id)
        return None, None
    if not node:
        add("mv_song_binding_missing", "歌曲绑定的音频节点或素材不存在", shot_id=shot_id)
        return None, None
    if node["type"] == "asset":
        asset = node.get("data", {}).get("asset")
        asset_metadata = asset.get("metadata") if isinstance(asset, Mapping) else None
        asset_duration = _positive_int(asset_metadata.get("duration_ms")) if isinstance(asset_metadata, Mapping) else None
        if not isinstance(asset, Mapping) or asset.get("kind") != "audio" or asset_duration != duration:
            add("mv_song_asset_duration_missing", "已有歌曲Asset需带实际metadata.duration_ms并与时间轴一致", shot_id=shot_id)
            return None, None
        if asset.get("sha256") != expected_sha:
            add("mv_song_version_stale", "已有歌曲绑定摘要与Asset记录版本不一致", shot_id=shot_id)
        selection = value.get("imported_selection")
        if not isinstance(selection, Mapping):
            add("mv_song_selection_evidence_required", "导入歌曲需要记录采用来源、ACCEPT决定、证据和素材SHA", shot_id=shot_id)
        elif (
            selection.get("decision") != "ACCEPT"
            or selection.get("asset_sha256") != expected_sha
            or not _nonempty(selection.get("source"))
            or not _nonempty(selection.get("evidence"))
        ):
            add("mv_song_selection_evidence_stale", "导入歌曲采用记录必须以ACCEPT绑定当前素材SHA，并说明来源和选择依据", shot_id=shot_id)
        path = _verified_media_path(
            media, asset, expected_sha, add, "mv_song_file_invalid",
            "当前选择的歌曲文件不存在、类型不符或摘要已变化", shot_id, verify_files,
        )
        if verify_files and path:
            try:
                info = probe(path)
                if (
                    info.get("has_audio") is not True
                    or info.get("width") is not None
                    or info.get("duration_ms") != duration
                ):
                    add(
                        "mv_song_duration_stale",
                        "已有歌曲文件的FFprobe时长或音轨与Asset声明不一致",
                        shot_id=shot_id,
                    )
            except (OSError, ValueError, RuntimeError) as exc:
                add("mv_song_probe_failed", f"无法核实已有歌曲实际时长：{exc}", shot_id=shot_id)
        return {
            "node_id": node_id,
            "source_type": "asset",
            "sha256": expected_sha,
            "duration_ms": duration,
            "imported_selection": {
                key: selection.get(key)
                for key in ("decision", "asset_sha256", "source", "evidence")
            } if isinstance(selection, Mapping) else None,
        }, path
    if node["type"] != "audio" or not run or run.get("node_id") != node_id:
        add("mv_song_binding_missing", "生成歌曲绑定的音频节点或运行不存在", shot_id=shot_id)
        return None, None
    review = _review(run)
    if run.get("status") != "succeeded" or not review or review.get("decision") != "ACCEPT":
        add("mv_song_not_accepted", "MV歌曲必须引用Canvas中已ACCEPT的真实音频运行", shot_id=shot_id)
        return None, None
    if review.get("output_sha256") != expected_sha:
        add("mv_song_version_stale", "歌曲绑定摘要与Canvas采用版本不一致", shot_id=shot_id)
        return None, None
    path = _verified_media_path(
        media,
        {"path": review.get("output_path"), "kind": "audio"},
        expected_sha,
        add,
        "mv_song_file_invalid",
        "当前采用歌曲文件不存在、类型不符或摘要已变化",
        shot_id,
        verify_files,
    )
    actual_duration = _output_duration(run, review.get("output_path"))
    if actual_duration is None or actual_duration != duration:
        add("mv_song_duration_stale", "歌曲时长必须绑定当前采用运行的实际duration_ms", shot_id=shot_id)
    return {
        "node_id": node_id,
        "source_type": "accepted_run",
        "run_id": run_id,
        "sha256": expected_sha,
        "duration_ms": duration,
    }, path


def _song_asset_fingerprint(graph: Mapping[str, Any], song: Any) -> dict[str, Any] | None:
    """Include a selected local asset's declared identity in the cheap fingerprint."""

    if not isinstance(song, Mapping):
        return None
    node_id = _nonempty(song.get("node_id"))
    node = next((item for item in graph["nodes"] if item.get("id") == node_id), None)
    if not node or node.get("type") != "asset":
        return None
    asset = node.get("data", {}).get("asset")
    if not isinstance(asset, Mapping):
        return {"node_id": node_id, "asset": None}
    metadata = asset.get("metadata")
    return {
        "node_id": node_id,
        "path": asset.get("path"),
        "sha256": asset.get("sha256"),
        "duration_ms": metadata.get("duration_ms") if isinstance(metadata, Mapping) else None,
    }


def _find_run(runs: Sequence[Mapping[str, Any]], run_id: Any) -> Mapping[str, Any] | None:
    if not isinstance(run_id, str) or not run_id:
        return None
    return next(
        (run for run in runs if isinstance(run, Mapping) and run.get("id") == run_id),
        None,
    )


def _review(run: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(run, Mapping):
        return None
    review = run.get("review")
    return review if isinstance(review, Mapping) else None


def _output_duration(run: Mapping[str, Any], path: Any) -> int | None:
    outputs = run.get("outputs") or []
    if isinstance(outputs, Mapping):
        outputs = [outputs]
    if not isinstance(outputs, Sequence):
        return None
    for output in outputs:
        if not isinstance(output, Mapping) or output.get("path") != path:
            continue
        metadata = output.get("metadata")
        if isinstance(metadata, Mapping):
            return _positive_int(metadata.get("duration_ms"))
    return None


def _valid_window(value: Any, add: Any, shot_id: str | None) -> tuple[int, int] | None:
    if not isinstance(value, Mapping):
        add("mv_song_window_required", "Panel需要明确song_window_ms起止时间", shot_id=shot_id)
        return None
    start, end = value.get("start"), value.get("end")
    if (
        not isinstance(start, int) or isinstance(start, bool) or start < 0
        or not isinstance(end, int) or isinstance(end, bool) or end <= start
    ):
        add("mv_song_window_invalid", "song_window_ms必须是有效的毫秒起止区间", shot_id=shot_id)
        return None
    return start, end


def _image_input_bindings(
    canvas: Mapping[str, Any], node_id: str, snapshot: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]], value: Any, media: Any, add: Any,
    shot_id: str | None, verify_files: bool,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        add("mv_input_bindings_invalid", "input_bindings必须是数组；无图片输入时使用空数组", shot_id=shot_id)
        return {}, [], []
    declared_ids: set[str] = set()
    declared: dict[tuple[str, str, str | None, str | None], dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, Mapping):
            add("mv_input_binding_invalid", "每个input_binding必须是对象", shot_id=shot_id)
            continue
        item_id = _nonempty(item.get("id"))
        slot = item.get("slot")
        source_node_id = _nonempty(item.get("source_node_id"))
        source_run_id = _nonempty(item.get("source_run_id"))
        digest = _valid_sha(item.get("sha256"))
        role = _nonempty(item.get("role"))
        if not item_id or item_id in declared_ids:
            add("mv_input_binding_id_invalid", "input_binding id必须唯一且非空", shot_id=shot_id)
            continue
        declared_ids.add(item_id)
        if slot not in _IMAGE_SLOTS or not source_node_id or not digest or not role:
            add("mv_input_binding_invalid", "input_binding需要有效slot、source_node_id、sha256和role", shot_id=shot_id)
            continue
        key = (slot, source_node_id, source_run_id, digest)
        if key in declared:
            add("mv_input_binding_duplicate", "同一实际图片输入不能重复登记", shot_id=shot_id)
            continue
        declared[key] = dict(item)

    try:
        resolved = resolve_input_bindings(canvas, node_id, runs)
    except (ValueError, KeyError) as exc:
        add("mv_input_resolution_failed", f"无法解析Panel图片输入：{exc}", shot_id=shot_id)
        return {}, [], []

    snapshot_inputs = snapshot.get("inputs", {})
    snapshot_assets: dict[str, list[Mapping[str, Any]]] = {}
    if isinstance(snapshot_inputs, Mapping):
        frame = snapshot_inputs.get("first_frame")
        if isinstance(frame, Mapping):
            snapshot_assets["first_frame"] = [frame]
        refs = snapshot_inputs.get("reference_images", [])
        snapshot_assets["reference_images"] = [item for item in refs if isinstance(item, Mapping)] if isinstance(refs, Sequence) and not isinstance(refs, (str, bytes, bytearray)) else []
    actual_entries: list[dict[str, Any]] = []
    consumed_snapshot: Counter[tuple[str, str]] = Counter()
    actual_counts: Counter[tuple[str, str, str | None, str | None]] = Counter()
    for item in resolved:
        slot = item["slot"]
        asset = item["asset"]
        if slot not in _IMAGE_SLOTS or asset.get("kind") != "image":
            continue
        try:
            path = _validate_media_path(media, asset, verify_files)
            digest = _file_sha(path) if verify_files else _asset_sha(asset)
            if digest is None:
                raise ValueError("图片输入缺少可追溯的sha256")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            add("mv_input_file_invalid", f"MV图片输入不可用：{exc}", shot_id=shot_id)
            continue
        source_node_id = item["source_node_id"]
        source_run_id = _nonempty(item.get("source_run_id"))
        key = (slot, source_node_id, source_run_id, digest)
        actual_counts[key] += 1
        normalized = str(Path(str(asset.get("path"))).resolve())
        candidates = snapshot_assets.get(slot, [])
        found = False
        for candidate in candidates:
            try:
                candidate_path = _validate_media_path(media, candidate, verify_files)
                candidate_key = (slot, str(candidate_path.resolve()))
                if candidate_key == (slot, normalized) and consumed_snapshot[candidate_key] < sum(
                    1 for entry in resolved if entry["slot"] == slot and str(Path(str(entry["asset"].get("path"))).resolve()) == normalized
                ):
                    consumed_snapshot[candidate_key] += 1
                    found = True
                    break
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if not found:
            add("mv_input_not_in_snapshot", "声明的MV参考图未进入本次实际生成快照", shot_id=shot_id)
        actual_entries.append({
            "slot": slot,
            "source_node_id": source_node_id,
            "source_run_id": source_run_id,
            "sha256": digest,
            "path": str(path.resolve()),
            "source_handle": item["source_handle"],
            "require_accept": item["require_accept"],
        })

    actual_snapshot_count = sum(len(items) for items in snapshot_assets.values())
    if actual_snapshot_count != len(actual_entries):
        add("mv_input_set_mismatch", "Panel图片连线与本次实际快照中的图片集合不一致", shot_id=shot_id)

    declared_counts = Counter(declared.keys())
    for key, count in actual_counts.items():
        if declared_counts[key] < count:
            add("mv_input_untracked", "Panel的实际图片输入尚未绑定版本与用途", shot_id=shot_id)
    for key in declared:
        if actual_counts[key] == 0:
            add("mv_input_binding_stale", "已绑定参考图不再是当前Panel的实际输入", shot_id=shot_id)

    bindings_by_id: dict[str, dict[str, Any]] = {}
    bound_context: list[dict[str, Any]] = []
    image_hashes: list[str] = []
    actual_lookup: dict[tuple[str, str, str | None, str | None], list[dict[str, Any]]] = {}
    for item in actual_entries:
        key = (item["slot"], item["source_node_id"], item["source_run_id"], item["sha256"])
        actual_lookup.setdefault(key, []).append(item)
    for key, metadata in declared.items():
        available = actual_lookup.get(key, [])
        if not available:
            continue
        actual = available.pop(0)
        binding_id = str(metadata["id"])
        binding = {
            **actual,
            "id": binding_id,
            "role": str(metadata["role"]),
        }
        bindings_by_id[binding_id] = binding
        bound_context.append({key: binding[key] for key in (
            "id", "slot", "source_node_id", "source_run_id", "sha256", "role",
            "source_handle", "require_accept", "path",
        )})
        image_hashes.append(binding["sha256"])
    return bindings_by_id, bound_context, sorted(image_hashes)


def _check_text_events(
    value: Any, bindings: Mapping[str, Mapping[str, Any]], mode: str | None,
    add: Any, shot_id: str | None,
) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        add("mv_text_events_invalid", "text_events必须是数组", shot_id=shot_id)
        return
    event_ids: set[str] = set()
    for event in value:
        if not isinstance(event, Mapping):
            add("mv_text_event_invalid", "每个text_event必须是对象", shot_id=shot_id)
            continue
        event_id, text, renderer = (
            _nonempty(event.get("id")), _nonempty(event.get("text")), event.get("renderer")
        )
        if not event_id or event_id in event_ids or not text or renderer not in {"h3", "post"}:
            add("mv_text_event_invalid", "文字事件需要唯一id、准确原文和h3/post责任", shot_id=shot_id)
            continue
        event_ids.add(event_id)
        if renderer == "post":
            continue
        binding_id = _nonempty(event.get("binding_id"))
        binding = bindings.get(binding_id or "")
        if binding is None:
            add("mv_text_image_required", f"文字事件{event_id}由H3生成，但没有绑定本次真实图片输入", shot_id=shot_id)
            continue
        expected_slots = {
            "i2v": {"first_frame"},
            "r2v": {"first_frame", "reference_images"},
            "fl2v": {"first_frame", "reference_images"},
        }.get(mode or "", set())
        if binding.get("slot") not in expected_slots:
            add("mv_text_image_wrong_slot", f"文字事件{event_id}的图片槽位与{mode or '当前'}模式不匹配", shot_id=shot_id)
        observation = event.get("visual_check")
        if not isinstance(observation, Mapping):
            add("mv_text_visual_check_required", f"文字事件{event_id}缺少绑定图片版本的人工核对记录", shot_id=shot_id)
            continue
        if (
            observation.get("decision") != "ACCEPT"
            or observation.get("asset_sha256") != binding.get("sha256")
            or observation.get("text_sha256") != _sha_text(text)
            or not _nonempty(observation.get("evidence"))
        ):
            add("mv_text_visual_check_stale", f"文字事件{event_id}的观察记录未绑定当前文字与图片版本", shot_id=shot_id)


def _check_continuity(
    canvas: Mapping[str, Any], node_id: str, value: Any,
    bindings: Mapping[str, Mapping[str, Any]], snapshot: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]], media: Any, add: Any, shot_id: str | None,
    verify_files: bool,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        add("mv_continuity_invalid", "continuity必须是一个对象", shot_id=shot_id)
        return None
    run_id = _nonempty(value.get("source_run_id"))
    source_node_id = _nonempty(value.get("source_node_id"))
    binding_id = _nonempty(value.get("binding_id"))
    tail_sha = _valid_sha(value.get("tail_sha256"))
    source_run = _find_run(runs, run_id)
    binding = bindings.get(binding_id or "")
    if not run_id or not source_node_id or not binding or not tail_sha:
        add("mv_continuity_invalid", "连续动作需要来源run、来源Panel、首帧binding和真实尾帧SHA", shot_id=shot_id)
        return None
    if binding.get("slot") != "first_frame" or binding.get("source_run_id") != run_id or binding.get("source_node_id") != source_node_id or binding.get("sha256") != tail_sha:
        add("mv_continuity_binding_stale", "连续动作的真实尾帧必须作为当前Panel first_frame并绑定同一来源run", shot_id=shot_id)
        return None
    source_review = _review(source_run)
    if not source_run or source_run.get("node_id") != source_node_id or source_run.get("status") != "succeeded" or not source_review or source_review.get("decision") != "ACCEPT":
        add("mv_continuity_source_not_accepted", "连续动作来源run必须是Canvas已ACCEPT的视频", shot_id=shot_id)
        return None
    if not binding.get("require_accept") or not str(binding.get("source_handle", "")).startswith("output:"):
        add("mv_continuity_not_derived_tail", "连续动作必须连接来源Panel的已接受衍生尾帧", shot_id=shot_id)
        return None
    accepted_input = (snapshot.get("inputs") or {}).get("first_frame")
    if not isinstance(accepted_input, Mapping) or accepted_input.get("accepted_sha256") != tail_sha:
        add("mv_continuity_acceptance_missing", "first_frame没有来源review接受的尾帧摘要", shot_id=shot_id)
        return None
    source_node = next((item for item in canvas["graph"]["nodes"] if item["id"] == source_node_id), None)
    derived_id = str(binding["source_handle"])[len("output:"):]
    derived = None
    if source_node:
        derived = next((item for item in source_node.get("data", {}).get("derived_outputs", []) if item.get("id") == derived_id), None)
    if not isinstance(derived, Mapping) or derived.get("source_run_id") != run_id or (derived.get("asset") or {}).get("sha256") != tail_sha:
        add("mv_continuity_derived_asset_stale", "来源尾帧记录与当前绑定的派生图片版本不一致", shot_id=shot_id)
        return None
    # The existing Canvas review remains the authority. Check its actual file
    # identity here; do not create a parallel acceptance field.
    review_path = source_review.get("output_path")
    review_sha = source_review.get("output_sha256")
    _verified_media_path(
        media, {"path": review_path, "kind": "video"}, review_sha,
        add, "mv_continuity_source_file_stale", "连续动作来源的采用视频文件已变化", shot_id,
        verify_files,
    )
    return {"source_run_id": run_id, "source_node_id": source_node_id, "tail_sha256": tail_sha}


def _check_representative(
    panel: Mapping[str, Any], shot_id: str | None, value: Any,
    excerpt_sha: str | None, song: Mapping[str, Any] | None,
    bindings: Mapping[str, Mapping[str, Any]], mode: str | None,
    runs: Sequence[Mapping[str, Any]], media: Any, add: Any, verify_files: bool,
) -> dict[str, Any] | None:
    if panel.get("representative") and value is None:
        # The first representative clip must be allowed to run before it can
        # have a Canvas ACCEPT review. Its downstream evidence is registered
        # only after the actual result is reviewed.
        return {"role": "sample", "pending_review": True}
    if not panel.get("requires_representative") and value is None:
        return None
    if not isinstance(value, Mapping):
        add("mv_representative_evidence_required", "扩展Panel需要绑定已接受的代表片证据", shot_id=shot_id)
        return None
    run_id = _nonempty(value.get("run_id"))
    output_sha = _valid_sha(value.get("output_sha256"))
    sample_run = _find_run(runs, run_id)
    sample_review = _review(sample_run)
    if not run_id or not output_sha or not sample_run or sample_run.get("status") != "succeeded" or not sample_review or sample_review.get("decision") != "ACCEPT":
        add("mv_representative_not_accepted", "代表片必须引用Canvas已ACCEPT的真实视频run", shot_id=shot_id)
        return None
    review = sample_review
    if review.get("output_sha256") != output_sha:
        add("mv_representative_output_stale", "代表片SHA与Canvas采用的视频版本不一致", shot_id=shot_id)
    _verified_media_path(
        media, {"path": review.get("output_path"), "kind": "video"}, output_sha,
        add, "mv_representative_file_invalid", "代表片采用文件不存在或摘要已变化", shot_id,
        verify_files,
    )
    if not isinstance(song, Mapping) or value.get("song_sha256") != song.get("sha256"):
        add("mv_representative_song_stale", "代表片证据未绑定当前采用歌曲版本", shot_id=shot_id)
    if not excerpt_sha or value.get("script_excerpt_sha256") != excerpt_sha:
        add("mv_representative_script_stale", "代表片证据必须绑定当前Panel的脚本片段", shot_id=shot_id)
    if value.get("mode") != mode:
        add("mv_representative_mode_stale", "代表片证据的视频模式与当前Panel不一致", shot_id=shot_id)
    scope = value.get("scope")
    if not isinstance(scope, Mapping):
        add("mv_representative_scope_required", "代表片证据需要明确适用镜头、输入用途和测试时间窗", shot_id=shot_id)
        scope = {}
    if scope.get("mode") != mode:
        add("mv_representative_scope_mode_stale", "代表片适用范围需要声明与当前Panel一致的视频模式", shot_id=shot_id)
    scope_shots = scope.get("shot_ids")
    if (
        not isinstance(scope_shots, Sequence)
        or isinstance(scope_shots, (str, bytes, bytearray))
        or shot_id not in scope_shots
    ):
        add("mv_representative_shot_out_of_scope", "当前Panel不在代表片声明覆盖的镜头范围内", shot_id=shot_id)
    roles = scope.get("roles")
    no_image_t2v = mode == "t2v" and not bindings
    if not isinstance(roles, Sequence) or isinstance(roles, (str, bytes, bytearray)):
        add("mv_representative_roles_required", "代表片证据需要列出实际覆盖的人物、环境或文字输入用途", shot_id=shot_id)
        roles = []
    elif not roles and not no_image_t2v:
        add("mv_representative_roles_required", "代表片证据需要列出实际覆盖的人物、环境或文字输入用途", shot_id=shot_id)
    elif roles:
        available_roles = {
            binding["role"] for binding in bindings.values()
            if isinstance(binding.get("role"), str)
        }
        if any(not isinstance(role, str) or role not in available_roles for role in roles):
            add("mv_representative_roles_stale", "代表片声明的输入用途必须实际存在于当前Panel绑定素材中", shot_id=shot_id)
    sample_window = _valid_window(scope.get("sample_window_ms"), add, shot_id)
    if song and sample_window and sample_window[1] > song["duration_ms"]:
        add("mv_representative_window_out_of_range", "代表片测试时间窗超出当前歌曲", shot_id=shot_id)
    expected_hashes = value.get("input_sha256s")
    scoped_hashes = sorted(
        str(binding["sha256"])
        for binding in bindings.values()
        if binding.get("role") in roles
    )
    normalized_expected_hashes = (
        [_valid_sha(item) for item in expected_hashes]
        if isinstance(expected_hashes, Sequence)
        and not isinstance(expected_hashes, (str, bytes, bytearray))
        else None
    )
    if (
        normalized_expected_hashes is None
        or any(item is None for item in normalized_expected_hashes)
        or sorted(item for item in normalized_expected_hashes if item is not None) != scoped_hashes
    ):
        add("mv_representative_inputs_stale", "代表片覆盖用途对应的参考图版本与当前Panel不一致", shot_id=shot_id)
    sample_snapshot = sample_run.get("snapshot")
    sample_inputs = sample_snapshot.get("inputs", {}) if isinstance(sample_snapshot, Mapping) else {}
    if not isinstance(sample_snapshot, Mapping) or sample_snapshot.get("mode") != mode:
        add("mv_representative_mode_stale", "代表片运行快照模式与当前Panel不一致", shot_id=shot_id)
    sample_hashes = _snapshot_image_hashes(sample_inputs)
    if verify_files and not media.inputs_unchanged(sample_snapshot or {}):
        add("mv_representative_source_changed", "代表片的输入素材已变化，原采样证据不再适用", shot_id=shot_id)
    if not Counter(
        item for item in (normalized_expected_hashes or []) if isinstance(item, str)
    ) <= Counter(sample_hashes):
        add("mv_representative_not_in_sample_inputs", "代表片运行快照没有使用证据所绑定的参考图版本", shot_id=shot_id)
    if not _nonempty(value.get("evidence")):
        add("mv_representative_evidence_text_required", "代表片记录需要说明实际核对的声音或画面范围", shot_id=shot_id)
    return {
        "run_id": run_id,
        "output_sha256": output_sha,
        "sample_window_ms": {"start": sample_window[0], "end": sample_window[1]} if sample_window else None,
        "song_sha256": value.get("song_sha256"),
        "script_excerpt_sha256": excerpt_sha,
        "mode": mode,
        "scope": {
            "shot_ids": [item for item in scope_shots if isinstance(item, str)]
            if isinstance(scope_shots, Sequence) and not isinstance(scope_shots, (str, bytes, bytearray))
            else [],
            "mode": scope.get("mode"),
            "roles": list(roles),
            "sample_window_ms": {"start": sample_window[0], "end": sample_window[1]} if sample_window else None,
        },
        "input_sha256s": scoped_hashes,
        "evidence": _nonempty(value.get("evidence")),
    }


def _context_text_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        {
            key: event[key]
            for key in ("id", "text", "renderer", "binding_id", "visual_check")
            if key in event
        }
        for event in value
        if isinstance(event, Mapping)
    ]


def _snapshot_image_hashes(inputs: Any) -> list[str]:
    if not isinstance(inputs, Mapping):
        return []
    assets: list[Mapping[str, Any]] = []
    frame = inputs.get("first_frame")
    if isinstance(frame, Mapping):
        assets.append(frame)
    references = inputs.get("reference_images", [])
    if isinstance(references, Sequence) and not isinstance(references, (str, bytes, bytearray)):
        assets.extend(item for item in references if isinstance(item, Mapping))
    return [digest for item in assets if (digest := _asset_sha(item)) is not None]


def _verified_media_path(
    media: Any, asset: Mapping[str, Any], expected_sha: str | None, add: Any,
    code: str, message: str, shot_id: str | None, verify_files: bool = True,
) -> Path | None:
    try:
        path = _validate_media_path(media, asset, verify_files)
        digest = _file_sha(path) if verify_files else expected_sha
    except (OSError, ValueError, KeyError, TypeError):
        add(code, message, shot_id=shot_id)
        return None
    if not expected_sha or digest != expected_sha:
        add(code, message, shot_id=shot_id)
        return None
    return Path(path).resolve()


def _validate_media_path(media: Any, asset: Mapping[str, Any], verify_files: bool) -> Path:
    if verify_files:
        return media.validate_input(dict(asset))
    path = media.resolve(str(asset.get("path", "")))
    if media.asset(path)["kind"] != asset.get("kind"):
        raise ValueError("素材类型与输入端口不匹配")
    return path


def _asset_sha(asset: Mapping[str, Any]) -> str | None:
    return _valid_sha(asset.get("accepted_sha256")) or _valid_sha(asset.get("sha256"))


def _file_sha(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha_text(raw)


def _valid_sha(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) != 64 or not set(value.lower()) <= _HEX:
        return None
    return value.lower()


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _nonempty(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
