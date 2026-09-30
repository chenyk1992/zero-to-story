from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def cli():
    path = Path(__file__).resolve().parents[2] / ".agents/skills/music-video-creator/scripts/music_tools.py"
    spec = importlib.util.spec_from_file_location("mv_tools_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_dispatch_cache_and_exclusive_receipt(cli, monkeypatch, tmp_path):
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"song")
    timeline = tmp_path / "timeline.json"
    timeline.write_text(json.dumps({"source": {"path": str(audio)}}))
    edit = tmp_path / "edit.json"
    edit.write_text(json.dumps({"music_timeline": str(timeline), "segments": []}))
    output, receipt, cache = tmp_path / "movie.mp4", tmp_path / "receipt.json", tmp_path / "cache"
    calls = []
    def render(value, path, *, cache_dir):
        calls.append((path, cache_dir))
        return {"path": str(path), "render_status": "technical"}
    monkeypatch.setattr(cli, "render_edit", render)
    assert cli.main(["render", "--edit", str(edit), "--output", str(output), "--cache-dir", str(cache),
                     "--receipt", str(receipt)]) == 0
    assert calls == [(output, cache)]
    assert json.loads(receipt.read_text())["render_status"] == "technical"
    assert cli.main(["render", "--edit", str(edit), "--output", str(output), "--receipt", str(audio)]) == 1
    assert len(calls) == 1 and audio.read_bytes() == b"song"


def test_preview_dispatch_and_production_are_distinct(cli, monkeypatch, tmp_path):
    edit = tmp_path / "preview.json"
    edit.write_text(json.dumps({"schema": "lfo.mv.preview.v1"}))
    monkeypatch.setattr(cli, "render_preview", lambda *args, **kwargs: {"render_status": "preview"})
    output = tmp_path / "preview.mp4"
    assert cli.main(["preview", "--edit", str(edit), "--output", str(output)]) == 0
    reads = []
    def read(canvas_id, suffix):
        reads.append((canvas_id, suffix))
        return {"canvas_id": canvas_id, "run_counts": {}}
    monkeypatch.setattr(cli, "_canvas_read", read)
    saved = tmp_path / "stats.json"
    assert cli.main(["production", "--canvas-id", "mv", "--output", str(saved)]) == 0
    assert reads == [("mv", "/production")]


def test_adoption_requires_current_accepted_version(cli, monkeypatch, tmp_path):
    source = tmp_path / "video.mp4"
    edit = {"segments": [{"run_id": "run", "path": str(source), "sha256": "good"}]}
    run = {"id": "run", "status": "succeeded", "review": {
        "decision": "ACCEPT", "output_path": str(source), "output_sha256": "good"}}
    monkeypatch.setattr(cli, "_canvas_read", lambda *args: {"runs": [run]})
    cli._check_adopted_segments(edit, "mv")
    run["review"]["output_sha256"] = "old"
    with pytest.raises(ValueError, match="正式采用"):
        cli._check_adopted_segments(edit, "mv")
    run["review"]["output_sha256"] = "good"
    run["status"] = "unknown"
    with pytest.raises(ValueError, match="正式采用"):
        cli._check_adopted_segments(edit, "mv")
