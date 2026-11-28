from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import transport
from lfo.comfy.face_refine import (
    CAPABILITY,
    collect_outputs,
    execute,
    prepare_workflow,
    resolve_refine_window,
)
from lfo.comfy.transport import OutputRef
from lfo.comfy.upscale import probe_video
from lfo.media._ffmpeg import run_command

ANCHOR = {"anchor_frame": 8, "left_x": 299, "right_x": 480, "anchor_y": 560}
SOLO_ANCHOR = {"anchor_frame": 8, "face_x": 320, "face_y": 420}


def test_duet_tracks_original_with_independent_references_and_stitches_both():
    graph = prepare_workflow("source.mp4", ["black.png", "white.png"], "Preserve motion.", "test", ANCHOR)

    def nodes(kind):
        return [(node_id, node["inputs"]) for node_id, node in graph.items() if node["class_type"] == kind]

    [(source_id, _)] = nodes("GetVideoComponents")
    tracks = nodes("H3FaceTrackCrop")
    assert [(node["select"], node["frame_index"], node["X"]) for _, node in tracks] == [
        ("closest_to_xy", 8, 299), ("closest_to_xy", 8, 480),
    ]
    assert all(node["images"] == [source_id, 0] for _, node in tracks)
    refs = nodes("LoadImage")
    assert [node["image"] for _, node in refs] == ["black.png", "white.png"]
    for (_, inputs), (ref, _), (track, _) in zip(nodes("MiniMaxH3ReferenceToVideo"), refs, tracks, strict=True):
        assert inputs["ref_images.ref_image_0"] == [ref, 0]
        assert inputs["length"] == [track, 6]
    (left_id, left), (_, right) = nodes("H3FaceStitch")
    assert left["base_images"] == [source_id, 0]
    assert right["base_images"] == [left_id, 0]
    assert [node["filename_prefix"] for _, node in nodes("SaveVideo")] == [
        "test/track-left", "test/track-right", "test/refined",
    ]


def test_solo_tracks_single_subject_and_stitches_once():
    graph = prepare_workflow("source.mp4", ["char.png"], "Preserve expression.", "test", SOLO_ANCHOR, mode="solo")

    def nodes(kind):
        return [(node_id, node["inputs"]) for node_id, node in graph.items() if node["class_type"] == kind]

    [(source_id, _)] = nodes("GetVideoComponents")
    tracks = nodes("H3FaceTrackCrop")
    assert len(tracks) == 1
    assert (tracks[0][1]["X"], tracks[0][1]["Y"], tracks[0][1]["frame_index"]) == (320, 420, 8)
    assert len(nodes("H3FaceStitch")) == 1
    assert nodes("H3FaceStitch")[0][1]["base_images"] == [source_id, 0]
    assert [node["filename_prefix"] for _, node in nodes("SaveVideo")] == [
        "test/track-solo", "test/refined",
    ]


def test_duet_and_solo_input_contracts():
    cap = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    duet_snapshot = {"mode": "duet", "parameters": ANCHOR, "inputs": {
        "reference_videos": [{"path": "source.mp4"}],
        "reference_images": [{"path": "left.png"}, {"path": "right.png"}],
    }}
    validate_input_contract(duet_snapshot, cap)
    duet_snapshot["inputs"]["reference_images"].pop()
    with pytest.raises(ValueError, match="至少需要 2"):
        validate_input_contract(duet_snapshot, cap)

    solo_snapshot = {"mode": "solo", "parameters": SOLO_ANCHOR, "inputs": {
        "reference_videos": [{"path": "source.mp4"}],
        "reference_images": [{"path": "solo.png"}],
    }}
    validate_input_contract(solo_snapshot, cap)
    solo_snapshot["inputs"]["reference_images"].append({"path": "extra.png"})
    with pytest.raises(ValueError, match="最多支持 1"):
        validate_input_contract(solo_snapshot, cap)


def test_collect_outputs_keeps_remote_name_for_duet_and_solo(tmp_path):
    labels = ("refined", "track-left", "track-right")
    files = tuple(
        OutputRef(
            str(tmp_path / f"prompt_{index:03}.mp4"),
            file_type="output",
            source_url=f"http://127.0.0.1:8188/view?filename={label}_00001_.mp4"
                       "&subfolder=canvas%5Cface-refine%5Ctest&type=output",
        )
        for index, label in enumerate(labels)
    )
    assert collect_outputs(files, "canvas/face-refine/test") == {
        label: tmp_path / f"prompt_{index:03}.mp4" for index, label in enumerate(labels)
    }
    with pytest.raises(ValueError, match="refined"):
        collect_outputs(files, "canvas/face-refine/other")

    solo_files = (files[0], OutputRef(
        str(tmp_path / "solo_track.mp4"),
        file_type="output",
        source_url="http://127.0.0.1:8188/view?filename=track-solo_00001_.mp4"
                   "&subfolder=canvas%5Cface-refine%5Ctest&type=output",
    ))
    assert collect_outputs(solo_files, "canvas/face-refine/test", mode="solo") == {
        "refined": tmp_path / "prompt_000.mp4",
        "track-solo": tmp_path / "solo_track.mp4",
    }


def test_resolve_refine_window_alignment_and_guards():
    details = {"fps": 24.0, "frame_count": 144}
    # Forward extension: 48 frames aligns to 56 (17*3+5) starting at 40.
    win = resolve_refine_window(details, {
        "anchor_frame": 50, "start_frame": 40, "frame_count": 48, "shot_start_frame": 0, "shot_end_frame": 120,
    })
    assert (win["work_start"], win["work_end"], win["work_frames"], win["trim_offset"], win["local_anchor_frame"]) == (
        40, 96, 56, 0, 10
    )

    # Near shot_end: shifts work_start backward within the same shot.
    back = resolve_refine_window(details, {
        "anchor_frame": 90, "start_frame": 72, "frame_count": 48, "shot_start_frame": 0, "shot_end_frame": 120,
    })
    assert (back["work_start"], back["work_end"], back["work_frames"], back["trim_offset"], back["local_anchor_frame"]) == (
        64, 120, 56, 8, 26
    )

    # Long shot without window params fails clearly.
    with pytest.raises(ValueError, match="超过 96 帧"):
        resolve_refine_window(details, {"anchor_frame": 10})

    # Shot shorter than aligned 17k+5 fails rather than crossing cut.
    with pytest.raises(ValueError, match="17k\\+5"):
        resolve_refine_window(details, {
            "anchor_frame": 30, "start_frame": 20, "frame_count": 30, "shot_start_frame": 15, "shot_end_frame": 50,
        })

    # Anchor outside working window fails.
    with pytest.raises(ValueError, match="anchor_frame"):
        resolve_refine_window(details, {
            "anchor_frame": 5, "start_frame": 40, "frame_count": 48, "shot_start_frame": 0, "shot_end_frame": 120,
        })


def test_execute_solo_windowed_long_shot_splices_back_with_audio(tmp_path: Path, monkeypatch):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("real FFmpeg is required for windowed FaceRefine test")
    ffmpeg = os.environ.get("LFO_FFMPEG") or "ffmpeg"
    source = tmp_path / "long_shot.mp4"
    run_command([
        ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-frames:v", "120", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ])
    ref = tmp_path / "char.png"
    run_command([
        ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=white:s=64x64:r=24:d=0.1",
        "-frames:v", "1", str(ref),
    ])

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    uploads: list[Path] = []

    def fake_upload(path: Path, _session):
        uploads.append(path)
        return path.name

    def fake_run(_wf, out_dir: Path, _cfg, _sess, *, guard, emit):
        prefix = "canvas/face-refine/" + ("3" * 20)
        # Produce a 56-frame silent Comfy output matching the sliced window.
        refined_clip = out_dir / "comfy_refined.mp4"
        track_clip = out_dir / "comfy_track.mp4"
        for target in (refined_clip, track_clip):
            run_command([
                ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=24",
                "-frames:v", "56", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target),
            ])
        guard.submitted("task-solo-1")
        guard.finished()
        return transport.ComfyResult(
            provider_task_id="task-solo-1",
            outputs=(
                OutputRef(str(refined_clip), file_type="output",
                          source_url=f"http://127.0.0.1:8188/view?filename=refined_00001_.mp4&subfolder={prefix}&type=output"),
                OutputRef(str(track_clip), file_type="output",
                          source_url=f"http://127.0.0.1:8188/view?filename=track-solo_00001_.mp4&subfolder={prefix}&type=output"),
            ),
        )

    monkeypatch.setenv("LFO_VIDEO_STATE", str(tmp_path / "video_state"))
    monkeypatch.setattr("lfo.comfy.face_refine.transport.ready_session", lambda _cfg: FakeSession())
    monkeypatch.setattr("lfo.comfy.face_refine.transport.upload_input", fake_upload)
    monkeypatch.setattr("lfo.comfy.face_refine.transport.preflight_workflow", lambda *_args: None)
    monkeypatch.setattr("lfo.comfy.face_refine.transport.run_workflow", fake_run)
    monkeypatch.setattr("lfo.comfy.face_refine.emit", lambda *_args: None)

    out_dir = tmp_path / "out"
    req_id = "req-solo-window"
    snapshot = {
        "request_id": req_id,
        "node_type": "video",
        "provider": "comfy-h3-face-refine",
        "model": "minimax-h3-fl2va",
        "mode": "solo",
        "prompt": "Refine single character face.",
        "parameters": {
            "anchor_frame": 60,
            "face_x": 80,
            "face_y": 60,
            "start_frame": 48,
            "frame_count": 48,
            "shot_start_frame": 0,
            "shot_end_frame": 120,
        },
        "inputs": {
            "reference_videos": [{"path": str(source)}],
            "reference_images": [{"path": str(ref)}],
        },
    }
    # Align expected subfolder prefix with execute()'s sha256(request_id)[:20].
    import hashlib
    expected_prefix = f"canvas/face-refine/{hashlib.sha256(req_id.encode()).hexdigest()[:20]}"

    def fake_run_exact(wf, od: Path, cfg, sess, *, guard, emit):
        refined_clip = od / "comfy_refined.mp4"
        track_clip = od / "comfy_track.mp4"
        for target in (refined_clip, track_clip):
            run_command([
                ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=24",
                "-frames:v", "56", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target),
            ])
        guard.submitted("task-solo-1")
        guard.finished()
        return transport.ComfyResult(
            provider_task_id="task-solo-1",
            outputs=(
                OutputRef(str(refined_clip), file_type="output",
                          source_url=f"http://127.0.0.1:8188/view?filename=refined_00001_.mp4&subfolder={expected_prefix}&type=output"),
                OutputRef(str(track_clip), file_type="output",
                          source_url=f"http://127.0.0.1:8188/view?filename=track-solo_00001_.mp4&subfolder={expected_prefix}&type=output"),
            ),
        )

    monkeypatch.setattr("lfo.comfy.face_refine.transport.run_workflow", fake_run_exact)
    result = execute(snapshot, out_dir, transport.RuntimeConfig(base_url="http://127.0.0.1:8188"))
    assert result["status"] == "succeeded"
    assert uploads[0].name == "window-input.mp4"
    assert probe_video(uploads[0])["frame_count"] == 56
    delivered = Path(result["outputs"][0]["path"])
    info = probe_video(delivered)
    assert info["frame_count"] == 120
    assert info["fps"] == 24.0
    assert info["has_audio"] is True
    assert result["outputs"][0]["metadata"]["mode"] == "solo"
    assert "solo" in result["outputs"][0]["metadata"]["face_track_previews"]
    assert (out_dir / "delivery.json").is_file()
