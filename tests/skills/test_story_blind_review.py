from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def observer():
    path = Path(__file__).resolve().parents[2] / ".agents/skills/zero-to-story/scripts/blind_review.py"
    spec = importlib.util.spec_from_file_location("story_blind_review", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def media(tmp_path):
    # Transport fixture only; no claim of decoding or audiovisual validity.
    path = tmp_path / "secret-plot-answer.mp4"
    path.write_bytes(b"synthetic-video-payload")
    (tmp_path / "handoff.md").write_text("SECRET_CREATIVE_INTENT", encoding="utf-8")
    return path


def test_prepare_is_offline_bound_and_preserves_existing_report(observer, media, tmp_path, monkeypatch):
    helper = observer.load_helper()
    monkeypatch.setattr(helper, "analyze_video", lambda *a, **k: pytest.fail("Network in prepare"))
    monkeypatch.setattr(observer, "load_helper", lambda: helper)
    output = tmp_path / "prepared.json"
    report = observer.observe(media, output, prepare_only=True)
    assert report["status"] == "prepared"
    assert report["source_sha256"] == observer.digest(media)
    assert "observation" not in report
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        observer.observe(media, output)
    assert output.read_bytes() == before


def test_remote_payload_has_only_snapshot_and_neutral_prompt(observer, media, tmp_path, monkeypatch):
    helper = observer.load_helper()
    monkeypatch.setattr(observer, "load_helper", lambda: helper)
    monkeypatch.setenv("MIMO_API_KEY", "test-only-key")
    monkeypatch.setenv("MIMO_VIDEO_BASE_URL", "https://unrelated.example")
    captured = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps({"choices": [{"finish_reason": "stop", "message": {
                "content": "Observed uncertainty at the ending; audio not verified."
            }}]}).encode()

    def send(request, **kwargs):
        captured.append(request)
        return Response()

    monkeypatch.setattr(helper.urllib.request, "urlopen", send)
    report = observer.observe(media, tmp_path / "observation.json")
    assert len(captured) == 1
    request = captured[0]
    assert request.full_url == observer.ENDPOINT
    payload = json.loads(request.data)
    assert len(payload["messages"]) == 1
    content = payload["messages"][0]["content"]
    assert [part["type"] for part in content] == ["video_url", "text"]
    assert content[1]["text"] == report["prompt"]
    assert "tools" not in payload
    for secret in ("SECRET_CREATIVE_INTENT", "secret-plot-answer", "test-only-key", str(tmp_path)):
        assert secret not in request.data.decode()
    assert report["status"] == "observed"
    assert report["source_still_matches"] is True
    assert "decision" not in report
    assert "test-only-key" not in json.dumps(report)


@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
def test_incomplete_response_is_not_an_observation(observer, media, tmp_path, monkeypatch, finish_reason):
    helper = observer.load_helper()
    monkeypatch.setattr(observer, "load_helper", lambda: helper)
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps({"choices": [{"finish_reason": finish_reason,
                                           "message": {"content": "partial"}}]}).encode()

    def send(*args, **kwargs):
        calls.append(True)
        return Response()

    monkeypatch.setattr(helper.urllib.request, "urlopen", send)
    output = tmp_path / "failure.json"
    with pytest.raises(RuntimeError):
        observer.observe(media, output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert "observation" not in report
    assert len(calls) == 1


def test_input_change_is_detected_before_request(observer, media, tmp_path, monkeypatch):
    original = observer.shutil.copyfile

    def copy_and_change(source, destination):
        original(source, destination)
        source.write_bytes(b"changed-version")

    monkeypatch.setattr(observer.shutil, "copyfile", copy_and_change)
    with pytest.raises(RuntimeError):
        observer.observe(media, tmp_path / "changed.json", prepare_only=True)
    assert json.loads((tmp_path / "changed.json").read_text())["status"] == "failed"


def test_cannot_replace_source_media(observer, media):
    before = media.read_bytes()
    with pytest.raises(ValueError):
        observer.observe(media, media, prepare_only=True)
    assert media.read_bytes() == before
