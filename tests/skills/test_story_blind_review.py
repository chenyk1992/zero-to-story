from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
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
    (tmp_path / "ad_plan.md").write_text("SECRET_BRAND_CLAIM_AND_CTA", encoding="utf-8")
    (tmp_path / "mv_plan.md").write_text("SECRET_LYRICS_AND_SINGER_MAP", encoding="utf-8")
    (tmp_path / "timeline.json").write_text("SECRET_BEAT_WINDOWS", encoding="utf-8")
    (tmp_path / "old-review.json").write_text("SECRET_PRIOR_OBSERVATION", encoding="utf-8")
    return path


@pytest.mark.parametrize("profile", ["story", "ad", "promo", "song", "instrumental", "mv"])
def test_prepare_is_offline_bound_and_preserves_existing_report(
    observer, media, tmp_path, monkeypatch, profile
):
    helper = observer.load_helper()
    monkeypatch.setattr(helper, "analyze_video", lambda *a, **k: pytest.fail("Network in prepare"))
    monkeypatch.setattr(helper, "analyze_audio", lambda *a, **k: pytest.fail("Network in prepare"))
    monkeypatch.setattr(observer, "load_helper", lambda: helper)
    if profile in {"song", "instrumental"}:
        media = media.rename(media.with_suffix(".flac"))
    output = tmp_path / "prepared.json"
    report = observer.observe(media, output, prepare_only=True, profile=profile)
    assert report["status"] == "prepared"
    assert report["profile"] == profile
    assert report["source_sha256"] == observer.digest(media)
    assert "observation" not in report
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        observer.observe(media, output, profile=profile)
    assert output.read_bytes() == before


@pytest.mark.parametrize(("profile", "medium", "prompt_asset"), [
    (None, "video", "zero-to-story/assets/blind_review_prompt.txt"),
    ("ad", "video", "advertising-creator/assets/ad_blind_review_prompt.txt"),
    ("promo", "video", "advertising-creator/assets/promo_blind_review_prompt.txt"),
    ("song", "audio", "music-video-creator/assets/song_blind_review_prompt.txt"),
    ("instrumental", "audio", "music-video-creator/assets/instrumental_blind_review_prompt.txt"),
    ("mv", "video", "music-video-creator/assets/mv_blind_review_prompt.txt"),
])
def test_remote_payload_has_only_snapshot_and_neutral_prompt(
    observer, media, tmp_path, monkeypatch, profile, medium, prompt_asset
):
    helper = observer.load_helper()
    monkeypatch.setattr(observer, "load_helper", lambda: helper)
    monkeypatch.setenv("MIMO_API_KEY", "test-only-key")
    monkeypatch.setenv(f"MIMO_{medium.upper()}_BASE_URL", "https://unrelated.example")
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
    output = tmp_path / "observation.json"
    if medium == "audio":
        media = media.rename(media.with_suffix(".flac"))
    argv = ["blind_review.py", f"--{medium}", str(media), "--output", str(output)]
    if profile is not None:
        argv.extend(["--profile", profile])
    monkeypatch.setattr(sys, "argv", argv)
    assert observer.main() == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(captured) == 1
    request = captured[0]
    assert request.full_url == observer.ENDPOINT
    expected_prompt = (observer.SKILL_ROOT.parent / prompt_asset).read_text(encoding="utf-8").strip()
    encoded_media = base64.b64encode(media.read_bytes()).decode("ascii")
    if medium == "audio":
        expected_media = {
            "type": "input_audio", "input_audio": {"data": f"data:audio/flac;base64,{encoded_media}"},
        }
        assert "fps" not in report
        assert "media_resolution" not in report
    else:
        expected_media = {
            "type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{encoded_media}"},
            "fps": 2.0, "media_resolution": "default",
        }
    assert json.loads(request.data) == {
        "model": "mimo-v2.6-pro",
        "messages": [{
            "role": "user",
            "content": [
                expected_media,
                {"type": "text", "text": expected_prompt},
            ],
        }],
        "max_completion_tokens": 2000,
        "thinking": {"type": "disabled"},
    }
    for secret in (
        "SECRET_CREATIVE_INTENT", "SECRET_BRAND_CLAIM_AND_CTA", "SECRET_PRIOR_OBSERVATION",
        "SECRET_LYRICS_AND_SINGER_MAP", "SECRET_BEAT_WINDOWS",
        "secret-plot-answer", "test-only-key", str(tmp_path),
    ):
        assert secret not in request.data.decode()
    assert report["profile"] == (profile or "story")
    assert report["media_type"] == medium
    assert report["source_sha256"] == observer.digest(media)
    assert report["prompt"] == expected_prompt
    assert report["status"] == "observed"
    assert report["source_still_matches"] is True
    assert "decision" not in report
    assert "test-only-key" not in json.dumps(report)


@pytest.mark.parametrize("extra_args", [
    ["--profile", "custom"],
    ["--brief", "ad_plan.md"],
    ["--prompt", "SECRET_CUSTOM_QUESTION"],
])
def test_cli_rejects_custom_review_context(observer, media, tmp_path, monkeypatch, extra_args):
    output = tmp_path / "observation.json"
    argv = ["blind_review.py", "--video", str(media), "--output", str(output), *extra_args]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(observer, "observe", lambda *a, **k: pytest.fail("Unexpected request"))
    with pytest.raises(SystemExit) as exc:
        observer.main()
    assert exc.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("media_args", [
    ["--audio", "song.flac", "--video", "mv.mp4", "--profile", "song"],
    ["--video", "mv.mp4", "--profile", "song"],
    ["--audio", "song.flac", "--profile", "mv"],
    ["--audio", "song.flac"],
    ["--audio", "song.flac", "--profile", "instrumental", "--fps", "2"],
])
def test_cli_rejects_incompatible_media_options(observer, tmp_path, monkeypatch, media_args):
    output = tmp_path / "observation.json"
    argv = ["blind_review.py", *media_args, "--output", str(output)]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(observer, "observe", lambda *a, **k: pytest.fail("Unexpected request"))
    with pytest.raises(SystemExit) as exc:
        observer.main()
    assert exc.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize(("finish_reason", "category"), [
    ("length", "truncated_response"),
    ("content_filter", "nonterminal_response"),
    ("stop", "empty_answer"),
])
def test_incomplete_response_is_not_an_observation(
    observer, media, tmp_path, monkeypatch, finish_reason, category
):
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
                                           "message": {"content": "" if finish_reason == "stop" else "partial"}}]}).encode()

    def send(*args, **kwargs):
        calls.append(True)
        return Response()

    monkeypatch.setattr(helper.urllib.request, "urlopen", send)
    output = tmp_path / "failure.json"
    with pytest.raises(RuntimeError):
        observer.observe(media, output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["error_category"] == category
    assert "observation" not in report
    assert len(calls) == 1


def test_http_failure_records_only_safe_diagnostics(observer, media, tmp_path, monkeypatch):
    helper = observer.load_helper()
    monkeypatch.setattr(observer, "load_helper", lambda: helper)
    monkeypatch.setenv("MIMO_API_KEY", "test-key")

    def fail(request, **kwargs):
        raise helper.urllib.error.HTTPError(
            request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"RAW_PROVIDER_BODY")
        )

    monkeypatch.setattr(helper.urllib.request, "urlopen", fail)
    output = tmp_path / "failed.json"
    with pytest.raises(RuntimeError, match="Observation failed") as exc:
        observer.observe(media, output, profile="mv")
    contents = output.read_text(encoding="utf-8")
    report = json.loads(contents)
    assert report["status"] == "failed"
    assert report["error_category"] == "http_error"
    assert report["http_status"] == 429
    assert "observation" not in report
    assert "RAW_PROVIDER_BODY" not in contents
    assert "RAW_PROVIDER_BODY" not in str(exc.value)


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
