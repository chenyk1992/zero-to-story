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


def test_generated_images_and_logos_use_current_review_imported_images_do_not_fake_run(cli, monkeypatch, tmp_path):
    image = tmp_path / "logo.png"
    run = {"id": "image-run", "status": "succeeded", "review": {
        "decision": "ACCEPT", "output_path": str(image), "output_sha256": "current"}}
    monkeypatch.setattr(cli, "_canvas_read", lambda *args: {"runs": [run]})
    generated = {"kind": "image", "path": str(image), "sha256": "current", "run_id": "image-run"}
    imported = {"kind": "image", "path": str(image), "sha256": "current", "source_note": "user selected image"}
    cli._check_adopted_segments({"segments": [generated, imported]}, "mv")
    cli._check_adopted_segments({"segments": [{**imported, "kind": "video"}]}, "mv")
    cli._check_adopted_segments({"segments": [], "image_overlays": [generated]}, "mv")
    run["review"]["decision"] = "REJECT"
    with pytest.raises(ValueError, match="正式采用"):
        cli._check_adopted_segments({"segments": [], "image_overlays": [generated]}, "mv")


@pytest.mark.parametrize("protected", ["edit", "receipt"])
def test_cli_cache_cannot_contain_manifest_or_receipt(cli, monkeypatch, tmp_path, protected):
    cache = tmp_path / "cache"
    cache.mkdir()
    edit = (cache if protected == "edit" else tmp_path) / "manifest.json"
    edit.write_text("{}", encoding="utf-8")
    calls = []
    monkeypatch.setattr(cli, "render_edit", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(cli, "_receipt_target", lambda *args: None)
    command = ["render", "--edit", str(edit), "--output", str(tmp_path / "out.mp4"),
               "--cache-dir", str(cache)]
    if protected == "receipt":
        command += ["--receipt", str(cache / "receipt.json")]
    assert cli.main(command) == 1
    assert not calls
    assert edit.read_text(encoding="utf-8") == "{}"


def test_receipt_cannot_use_overlay_input_path(cli, tmp_path):
    audio, image = tmp_path / "song.flac", tmp_path / "logo.png"
    audio.write_bytes(b"song")
    image.write_bytes(b"logo")
    timeline = tmp_path / "timeline.json"
    timeline.write_text(json.dumps({"source": {"path": str(audio)}}))
    with pytest.raises(ValueError, match="覆盖"):
        cli._receipt_target(image, {"music_timeline": str(timeline), "image_overlays": [{"path": str(image)}]},
                            tmp_path / "edit.json", tmp_path / "new.mp4")


@pytest.mark.parametrize("overlay", [{}, None, {"path": 123}])
def test_malformed_overlay_with_receipt_returns_error_without_render(cli, monkeypatch, tmp_path, capsys, overlay):
    timeline = tmp_path / "timeline.json"
    timeline.write_text(json.dumps({"source": {"path": str(tmp_path / "song.flac")}}))
    edit = tmp_path / "edit.json"
    edit.write_text(json.dumps({"music_timeline": str(timeline), "image_overlays": [overlay]}))
    calls = []
    monkeypatch.setattr(cli, "render_edit", lambda *args, **kwargs: calls.append(args))
    result = cli.main(["render", "--edit", str(edit), "--output", str(tmp_path / "out.mp4"),
                       "--receipt", str(tmp_path / "receipt.json")])
    assert result == 1
    assert "image_overlays" in capsys.readouterr().err
    assert not calls and not (tmp_path / "receipt.json").exists()


@pytest.mark.parametrize("records", [None, [{}], [None], [{"path": 123}],
                                     [{"path": "logo.png", "sha256": []}],
                                     [{"path": "logo.png", "sha256": "hash", "run_id": []}]])
@pytest.mark.parametrize("key", ["segments", "image_overlays"])
def test_malformed_adoption_without_receipt_returns_error(cli, monkeypatch, tmp_path, capsys, key, records):
    edit = tmp_path / "edit.json"
    edit.write_text(json.dumps({key: records}))
    calls = []
    monkeypatch.setattr(cli, "_canvas_read", lambda *args: calls.append(args))
    monkeypatch.setattr(cli, "render_edit", lambda *args, **kwargs: calls.append(args))
    output = tmp_path / "out.mp4"
    assert cli.main(["render", "--edit", str(edit), "--output", str(output), "--canvas-id", "mv"]) == 1
    assert key in capsys.readouterr().err
    assert not calls and not output.exists()
