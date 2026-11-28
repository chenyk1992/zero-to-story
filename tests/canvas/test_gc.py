"""Tests for read-only workspace GC diagnostics and opt-in orphan cleanup."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from lfo.canvas.__main__ import main as canvas_cli_main
from lfo.canvas.gc import inspect_and_clean_workspace
from lfo.canvas.settings import CanvasSettings
from lfo.canvas.store import CanvasStore

PROJECT = Path(__file__).resolve().parents[2]


def _age_dir(path: Path, seconds_ago: float) -> None:
    past = time.time() - seconds_ago
    for root, dirs, files in os.walk(path):
        for name in files:
            os.utime(Path(root) / name, (past, past))
        for name in dirs:
            os.utime(Path(root) / name, (past, past))
    os.utime(path, (past, past))


def test_gc_dry_run_and_apply_protects_live_rejected_final_custom_and_uploads(tmp_path: Path) -> None:
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    store = CanvasStore(settings.database)

    used_upload = settings.media_root / "assets" / "uploads" / "used.png"
    used_upload.parent.mkdir(parents=True, exist_ok=True)
    used_upload.write_bytes(b"used")
    unused_upload = settings.media_root / "assets" / "uploads" / "unused.png"
    unused_upload.write_bytes(b"unused")

    canvas = store.create_canvas(
        "gc-test",
        {
            "nodes": [
                {"id": "a1", "type": "asset", "position": {"x": 0, "y": 0}, "data": {"asset": {"path": str(used_upload), "kind": "image"}}},
                {"id": "v1", "type": "video", "position": {"x": 100, "y": 0}, "data": {"prompt": "p", "provider": "comfy", "mode": "t2v"}},
                {"id": "v2", "type": "video", "position": {"x": 200, "y": 0}, "data": {"prompt": "p2", "provider": "comfy", "mode": "t2v"}},
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selection": [],
        },
    )

    accepted_run = store.create_run(
        canvas["id"], "v1", canvas["version"], "req-accept",
        {"node_id": "v1", "node_type": "video"}, status="succeeded", resource_key="video",
    )
    accepted_dir = settings.output_dir(canvas["id"], accepted_run["id"])
    accepted_dir.mkdir(parents=True, exist_ok=True)
    (accepted_dir / "accept.mp4").write_bytes(b"accept-video")
    ready_dir = accepted_dir / "review-abc-ready"
    ready_dir.mkdir(parents=True, exist_ok=True)
    (ready_dir / "silent.mp4").write_bytes(b"silent-copy")
    _age_dir(accepted_dir, 7200)

    rejected_run = store.create_run(
        canvas["id"], "v2", canvas["version"], "req-reject",
        {"node_id": "v2", "node_type": "video"}, status="succeeded", resource_key="video",
    )
    rejected_dir = settings.output_dir(canvas["id"], rejected_run["id"])
    rejected_dir.mkdir(parents=True, exist_ok=True)
    (rejected_dir / "reject.mp4").write_bytes(b"reject-video")
    _age_dir(rejected_dir, 7200)

    # Terminal vs non-terminal frozen inputs in AppData/inputs
    terminal_input = settings.data_dir / "inputs" / uuid.uuid5(uuid.NAMESPACE_URL, "req-accept").hex
    terminal_input.mkdir(parents=True, exist_ok=True)
    (terminal_input / "input-1.png").write_bytes(b"terminal-frozen")
    _age_dir(terminal_input, 7200)

    running_run = store.create_run(
        canvas["id"], "v2", canvas["version"], "req-running",
        {"node_id": "v2", "node_type": "video"}, status="running", resource_key="video",
    )
    running_input = settings.data_dir / "inputs" / uuid.uuid5(uuid.NAMESPACE_URL, "req-running").hex
    running_input.mkdir(parents=True, exist_ok=True)
    (running_input / "input-1.png").write_bytes(b"running-frozen")
    _age_dir(running_input, 7200)

    store.create_run(
        canvas["id"], "v2", canvas["version"], "req-unknown",
        {"node_id": "v2", "node_type": "video"}, status="unknown", resource_key="video",
    )
    unknown_input = settings.data_dir / "inputs" / uuid.uuid5(uuid.NAMESPACE_URL, "req-unknown").hex
    unknown_input.mkdir(parents=True, exist_ok=True)
    (unknown_input / "input-1.png").write_bytes(b"unknown-frozen")
    _age_dir(unknown_input, 7200)

    # Final delivery directory is always protected
    final_file = settings.media_root / "projects" / canvas["id"] / "final" / "episode.mp4"
    final_file.parent.mkdir(parents=True, exist_ok=True)
    final_file.write_bytes(b"final-episode")

    # Deleted canvas UUID directory is counted in diagnostics and preserved
    deleted_proj = settings.media_root / "projects" / "33333333-3333-3333-3333-333333333333"
    (deleted_proj / "final").mkdir(parents=True, exist_ok=True)
    (deleted_proj / "final" / "old-final.mp4").write_bytes(b"123456")

    # Custom non-UUID dir under outputs/ must NEVER be deleted
    custom_post = settings.output_dir(canvas["id"], "post_work")
    custom_post.mkdir(parents=True, exist_ok=True)
    (custom_post / "rough.mp4").write_bytes(b"manual-edit")
    _age_dir(custom_post, 7200)

    # Orphans: old unreferenced UUID run dir, too-new UUID run dir, old orphan input dir, stale execute-* temp dir
    old_orphan_run = settings.output_dir(canvas["id"], "11111111-1111-1111-1111-111111111111")
    old_orphan_run.mkdir(parents=True, exist_ok=True)
    (old_orphan_run / "junk.mp4").write_bytes(b"12345")
    _age_dir(old_orphan_run, 7200)

    fresh_orphan_run = settings.output_dir(canvas["id"], "22222222-2222-2222-2222-222222222222")
    fresh_orphan_run.mkdir(parents=True, exist_ok=True)
    (fresh_orphan_run / "new.mp4").write_bytes(b"999")

    old_orphan_input = settings.data_dir / "inputs" / "deadbeef"
    old_orphan_input.mkdir(parents=True, exist_ok=True)
    (old_orphan_input / "input-1.png").write_bytes(b"frozen-orphan")
    _age_dir(old_orphan_input, 7200)

    stale_temp = settings.data_dir / "temporary" / "execute-stale123"
    stale_temp.mkdir(parents=True, exist_ok=True)
    (stale_temp / "input.json").write_bytes(b"{}")
    _age_dir(stale_temp, 7200)

    store.close()

    # Dry-run while a run is active skips stale_temp and deletes nothing
    dry = inspect_and_clean_workspace(settings, apply=False, min_age_seconds=3600)
    assert dry["mode"] == "dry_run"
    assert dry["has_running_runs"] is True
    by_path = {Path(c["path"]).resolve(): c["kind"] for c in dry["candidates"]}
    assert by_path[old_orphan_run.resolve()] == "orphan_run_output_dir"
    assert by_path[old_orphan_input.resolve()] == "orphan_frozen_input_dir"
    assert by_path[terminal_input.resolve()] == "terminal_frozen_input_dir"
    assert running_input.resolve() not in by_path
    assert unknown_input.resolve() not in by_path
    assert custom_post.resolve() not in by_path
    assert fresh_orphan_run.resolve() not in by_path
    assert stale_temp.resolve() not in by_path
    assert dry["diagnostics"]["custom_output_subdirs"]["count"] == 1
    assert dry["diagnostics"]["deleted_canvas_projects"]["count"] == 1
    assert dry["diagnostics"]["deleted_canvas_projects"]["final_bytes"] == 6
    assert dry["diagnostics"]["review_silent_videos"]["count"] == 1
    assert dry["diagnostics"]["unreferenced_uploads"]["count"] == 1

    # Finish the running run so stale_temp becomes eligible
    store = CanvasStore(settings.database)
    store.update_run(running_run["id"], status="failed", error="ended")
    store.close()

    applied = inspect_and_clean_workspace(settings, apply=True, min_age_seconds=3600)
    assert applied["mode"] == "apply"
    # Deletes old_orphan_run, old_orphan_input, terminal_input (accept), running_input (now failed), stale_temp
    assert applied["deleted_count"] == 5
    assert not old_orphan_run.exists()
    assert not old_orphan_input.exists()
    assert not terminal_input.exists()
    assert not stale_temp.exists()

    # Unknown run frozen input and custom outputs subdirs remain untouched
    assert (unknown_input / "input-1.png").is_file()
    assert (custom_post / "rough.mp4").is_file()
    assert (accepted_dir / "accept.mp4").is_file()
    assert (rejected_dir / "reject.mp4").is_file()
    assert final_file.is_file()
    assert unused_upload.is_file()
    assert (fresh_orphan_run / "new.mp4").is_file()


def test_gc_cli_defaults_to_dry_run(tmp_path: Path, capsys) -> None:
    rc = canvas_cli_main(
        ["--project", str(PROJECT), "--data-dir", str(tmp_path / "state"), "--media-root", str(tmp_path / "media"), "gc"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry_run"
    assert payload["deleted_count"] == 0
