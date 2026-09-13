from __future__ import annotations

import copy
import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from lfo.canvas.accepted_tail import extract_accepted_tail
from lfo.canvas.settings import CanvasSettings
from lfo.media._ffmpeg import run_command


def client_for(tmp_path, decision="ACCEPT"):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"original video")
    run = {"id": "run", "canvas_id": "canvas", "status": "succeeded", "snapshot": {"node_type": "video"},
           "review": {"decision": decision, "output_path": str(source), "output_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}
    return SimpleNamespace(settings=CanvasSettings(tmp_path, tmp_path / "state", tmp_path / "media"), request=lambda *args: copy.deepcopy(run)), run


@pytest.mark.parametrize("decision", ["REJECT", "INCONCLUSIVE", None])
def test_unaccepted_run_cannot_extract(tmp_path, monkeypatch, decision):
    client, _ = client_for(tmp_path, decision)
    monkeypatch.setattr("lfo.canvas.accepted_tail.run_command", lambda *args: pytest.fail("must not decode"))
    with pytest.raises(ValueError, match="ACCEPT"):
        extract_accepted_tail(client, "run")


def test_changed_source_cannot_extract(tmp_path):
    client, run = client_for(tmp_path)
    Path(run["review"]["output_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="摘要"):
        extract_accepted_tail(client, "run")


def test_tail_uses_all_frames_and_preserves_source(tmp_path, monkeypatch):
    client, run = client_for(tmp_path)
    def decode(command):
        assert "-frames:v" not in command and "-ss" not in command
        assert command[command.index("-update") + 1] == "1"
        Path(command[-1]).write_bytes(b"final decoded frame")
    monkeypatch.setattr("lfo.canvas.accepted_tail.run_command", decode)
    first = extract_accepted_tail(client, "run")
    second = extract_accepted_tail(client, "run")
    assert first["asset"]["path"] != second["asset"]["path"]
    assert Path(first["asset"]["path"]).read_bytes() == b"final decoded frame"
    assert Path(run["review"]["output_path"]).read_bytes() == b"original video"


def test_review_changed_during_decode_is_rejected(tmp_path, monkeypatch):
    client, run = client_for(tmp_path)
    def decode(command):
        Path(command[-1]).write_bytes(b"frame")
        run["review"]["decision"] = "REJECT"
    monkeypatch.setattr("lfo.canvas.accepted_tail.run_command", decode)
    with pytest.raises(ValueError, match="提取期间"):
        extract_accepted_tail(client, "run")
    assert not list(client.settings.media_root.rglob("*.png"))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required for actual final-frame verification")
def test_real_tail_includes_action_after_last_sample(tmp_path):
    client, run = client_for(tmp_path)
    source = Path(run["review"]["output_path"])
    # 26 frames: the frame at index 25 differs from sampled indices 0, 12, 24.
    run_command(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24",
                 "-frames:v", "26", "-c:v", "ffv1", "-f", "matroska", "-y", str(source)])
    run["review"]["output_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    expected = tmp_path / "expected.png"
    sampled = tmp_path / "sampled.png"
    for index, output in ((25, expected), (24, sampled)):
        run_command(["ffmpeg", "-v", "error", "-i", str(source), "-vf", f"select=eq(n\\,{index})", "-frames:v", "1", str(output)])
    result = extract_accepted_tail(client, "run")
    actual = Path(result["asset"]["path"]).read_bytes()
    assert actual == expected.read_bytes()
    assert actual != sampled.read_bytes()
