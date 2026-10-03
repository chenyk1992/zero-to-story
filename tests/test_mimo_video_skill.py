"""Regression tests for the shared MiMo audio/video-understanding helper."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "mimo-video-understanding"
    / "scripts"
    / "mimo_video.py"
)


class FakeHTTPResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = json.dumps(body, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> FakeHTTPResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


@pytest.fixture
def mimo_video() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mimo_video_skill_under_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_fake_response(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    body: dict[str, Any],
    captured: dict[str, Any],
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> FakeHTTPResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeHTTPResponse(body)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)


def request_payload(captured: dict[str, Any]) -> dict[str, Any]:
    request = captured["request"]
    return json.loads(request.data.decode("utf-8"))


def make_video(tmp_path: Path) -> str:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"test video bytes")
    return str(video)


def test_analyze_video_defaults_to_disabled_thinking_and_saves_final_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mimo_video: ModuleType
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    captured: dict[str, Any] = {}
    install_fake_response(
        monkeypatch,
        mimo_video,
        {"choices": [{"finish_reason": "stop", "message": {"content": "清晰的正文"}}]},
        captured,
    )
    output = tmp_path / "result.txt"

    result = mimo_video.analyze_video(make_video(tmp_path), "分析视频", output=str(output))

    assert result == "清晰的正文"
    assert output.read_text(encoding="utf-8") == "清晰的正文"
    assert request_payload(captured)["thinking"] == {"type": "disabled"}


def test_analyze_video_allows_explicit_enabled_thinking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mimo_video: ModuleType
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    captured: dict[str, Any] = {}
    install_fake_response(
        monkeypatch,
        mimo_video,
        {"choices": [{"finish_reason": "stop", "message": {"content": "正文"}}]},
        captured,
    )

    assert mimo_video.analyze_video(make_video(tmp_path), "分析", thinking="enabled") == "正文"
    assert request_payload(captured)["thinking"] == {"type": "enabled"}


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": "被截断的正文"},
                    }
                ]
            },
            "finish_reason=length",
        ),
        (
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "reasoning_content": "只有思考过程，没有最终答案",
                            "content": "",
                        },
                    }
                ]
            },
            "no final answer",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": "   \n\t"}}]},
            "no final answer",
        ),
    ],
)
def test_failed_responses_raise_and_preserve_existing_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mimo_video: ModuleType,
    response: dict[str, Any],
    message: str,
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    captured: dict[str, Any] = {}
    install_fake_response(monkeypatch, mimo_video, response, captured)
    output = tmp_path / "result.txt"
    output.write_text("previous answer", encoding="utf-8")

    with pytest.raises(RuntimeError, match=message):
        mimo_video.analyze_video(make_video(tmp_path), "分析", output=str(output))

    assert output.read_text(encoding="utf-8") == "previous answer"


def test_extract_message_text_never_uses_reasoning_as_final_answer(mimo_video: ModuleType) -> None:
    response = {
        "choices": [
            {
                "message": {
                    "reasoning_content": "内部推理，不应写入结果",
                    "content": None,
                }
            }
        ]
    }

    assert mimo_video.extract_message_text(response) == ""


def test_legacy_omni_model_keeps_payload_compatible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mimo_video: ModuleType
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    captured: dict[str, Any] = {}
    install_fake_response(
        monkeypatch,
        mimo_video,
        {"choices": [{"finish_reason": "stop", "message": {"content": "旧模型正文"}}]},
        captured,
    )

    result = mimo_video.analyze_video(
        make_video(tmp_path), "分析", model="mimo-v2-omni", thinking="disabled"
    )

    assert result == "旧模型正文"
    assert "thinking" not in request_payload(captured)

    with pytest.raises(ValueError, match="only for mimo-v2.6-pro"):
        mimo_video.analyze_video(
            make_video(tmp_path), "分析", model="mimo-v2-omni", thinking="enabled"
        )


def test_cli_passes_explicit_thinking_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mimo_video: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    captured: dict[str, Any] = {}
    install_fake_response(
        monkeypatch,
        mimo_video,
        {"choices": [{"finish_reason": "stop", "message": {"content": "CLI正文"}}]},
        captured,
    )
    video = make_video(tmp_path)
    output = tmp_path / "cli-result.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mimo_video.py",
            "--video",
            video,
            "--prompt",
            "分析",
            "--thinking",
            "enabled",
            "--output",
            str(output),
        ],
    )

    mimo_video.main()

    assert capsys.readouterr().out.strip() == "CLI正文"
    assert output.read_text(encoding="utf-8") == "CLI正文"
    assert request_payload(captured)["thinking"] == {"type": "enabled"}


@pytest.mark.parametrize("model", ["mimo-v2.6-pro", "mimo-v2.6-flash"])
@pytest.mark.parametrize("kind", ["audio", "video"])
def test_both_models_send_the_correct_media_part(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mimo_video: ModuleType,
    model: str,
    kind: str,
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    source = tmp_path / ("sample.mp3" if kind == "audio" else "sample.mp4")
    source.write_bytes(b"source media bytes")
    output = tmp_path / "observation.txt"
    captured: dict[str, Any] = {}
    install_fake_response(
        monkeypatch,
        mimo_video,
        {"choices": [{"finish_reason": "stop", "message": {"content": "实际媒体观察"}}]},
        captured,
    )

    result = getattr(mimo_video, f"analyze_{kind}")(
        str(source), "描述", model=model, thinking="enabled", output=str(output)
    )

    payload = request_payload(captured)
    part = payload["messages"][0]["content"][0]
    assert result == output.read_text(encoding="utf-8") == "实际媒体观察"
    assert payload["model"] == model
    assert payload["thinking"] == {"type": "enabled"}
    if kind == "audio":
        assert set(part) == {"type", "input_audio"}
        assert part["type"] == "input_audio"
        uri = part["input_audio"]["data"]
        assert uri.startswith("data:audio/mpeg;base64,")
    else:
        assert part["type"] == "video_url"
        assert part["fps"] == 2.0
        assert part["media_resolution"] == "default"
        uri = part["video_url"]["url"]
        assert uri.startswith("data:video/mp4;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == source.read_bytes()
    assert captured["request"].full_url == "https://api.xiaomimimo.com/v1/chat/completions"


@pytest.mark.parametrize(
    "suffix,mime",
    [
        (".MP3", "audio/mpeg"),
        (".wav", "audio/wav"),
        (".flac", "audio/flac"),
        (".m4a", "audio/mp4"),
        (".ogg", "audio/ogg"),
    ],
)
def test_audio_formats_use_canonical_mime(
    tmp_path: Path,
    mimo_video: ModuleType,
    suffix: str,
    mime: str,
) -> None:
    source = tmp_path / f"sample{suffix}"
    source.write_bytes(b"audio bytes")
    uri, actual_mime, count = mimo_video.encode_media_base64(str(source), "audio")
    assert actual_mime == mime
    assert uri.startswith(f"data:{mime};base64,")
    assert count == len(uri.split(",", 1)[1])


def test_audio_url_uses_its_endpoint_override_without_local_read(
    monkeypatch: pytest.MonkeyPatch,
    mimo_video: ModuleType,
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    monkeypatch.setenv("MIMO_AUDIO_BASE_URL", "https://audio.example/v1")
    monkeypatch.setenv("MIMO_VIDEO_BASE_URL", "https://video.example/v1")
    captured: dict[str, Any] = {}
    install_fake_response(
        monkeypatch,
        mimo_video,
        {"choices": [{"finish_reason": "stop", "message": {"content": "观察"}}]},
        captured,
    )
    url = "https://media.example/song?version=1"
    mimo_video.analyze_audio(url, "描述")
    assert captured["request"].full_url == "https://audio.example/v1/chat/completions"
    assert request_payload(captured)["messages"][0]["content"][0] == {
        "type": "input_audio",
        "input_audio": {"data": url},
    }
    assert request_payload(captured)["thinking"] == {"type": "disabled"}
    mimo_video.analyze_audio(url, "描述", base_url="https://explicit.example/v1/chat/completions")
    assert captured["request"].full_url == "https://explicit.example/v1/chat/completions"


@pytest.mark.parametrize("problem", ["format", "empty", "oversize", "model", "overwrite"])
def test_invalid_audio_stops_before_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mimo_video: ModuleType,
    problem: str,
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    source = tmp_path / ("sample.mp4" if problem == "format" else "sample.mp3")
    source.write_bytes(b"" if problem == "empty" else b"original bytes")
    original = source.read_bytes()
    if problem == "oversize":
        monkeypatch.setattr(mimo_video, "BASE64_LIMIT_CHARS", 4)
    captured: dict[str, Any] = {}
    install_fake_response(monkeypatch, mimo_video, {}, captured)
    with pytest.raises(ValueError):
        mimo_video.analyze_audio(
            str(source),
            "描述",
            model="mimo-v2-omni" if problem == "model" else "mimo-v2.6-flash",
            output=str(source) if problem == "overwrite" else None,
        )
    assert not captured
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "response",
    [
        {"choices": [{"finish_reason": "length", "message": {"content": "截断"}}]},
        {"choices": [{"finish_reason": "content_filter", "message": {"content": "部分"}}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": "<think>仅推理"}}]},
        {
            "choices": [
                {"finish_reason": "stop", "message": {"content": "", "reasoning_content": "推理"}}
            ]
        },
    ],
)
def test_audio_failure_preserves_output_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mimo_video: ModuleType,
    response: dict[str, Any],
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    calls = []

    def fake_urlopen(request: Any, timeout: int) -> FakeHTTPResponse:
        calls.append(request)
        return FakeHTTPResponse(response)

    monkeypatch.setattr(mimo_video.urllib.request, "urlopen", fake_urlopen)
    output = tmp_path / "result.txt"
    output.write_text("previous observation", encoding="utf-8")
    with pytest.raises(RuntimeError):
        mimo_video.analyze_audio("https://example.com/audio.mp3", "分析", output=str(output))
    assert len(calls) == 1
    assert output.read_text(encoding="utf-8") == "previous observation"


@pytest.mark.parametrize(
    "content",
    [
        "<think>hidden reasoning</think>final observation",
        "hidden reasoning</think>final observation",
        [
            {"type": "reasoning", "text": "hidden reasoning"},
            {"type": "text", "text": "final observation"},
        ],
    ],
)
def test_response_extraction_excludes_tagged_reasoning(
    mimo_video: ModuleType, content: Any
) -> None:
    response = {"choices": [{"message": {"content": content}}]}
    assert mimo_video.extract_message_text(response) == "final observation"


def test_audio_cli_selects_flash_without_video_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mimo_video: ModuleType,
) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    captured: dict[str, Any] = {}
    install_fake_response(
        monkeypatch,
        mimo_video,
        {"choices": [{"finish_reason": "stop", "message": {"content": "音频正文"}}]},
        captured,
    )
    output = tmp_path / "audio.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mimo_video.py",
            "--audio",
            "https://example.com/song.mp3",
            "--model",
            "mimo-v2.6-flash",
            "--prompt",
            "听结尾",
            "--output",
            str(output),
        ],
    )
    mimo_video.main()
    assert output.read_text(encoding="utf-8") == "音频正文"
    assert request_payload(captured)["model"] == "mimo-v2.6-flash"
    assert request_payload(captured)["messages"][0]["content"][0]["type"] == "input_audio"


@pytest.mark.parametrize(
    "extra", [["--video", "clip.mp4"], ["--fps", "2"], ["--media-resolution", "max"]]
)
def test_audio_cli_rejects_mixed_inputs_and_video_options(
    monkeypatch: pytest.MonkeyPatch,
    mimo_video: ModuleType,
    extra: list[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mimo_video.py",
            "--audio",
            "song.mp3",
            "--prompt",
            "分析",
            *extra,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        mimo_video.main()
    assert exc.value.code == 2


def test_audio_cli_rejects_video_only_model_before_analysis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mimo_video: ModuleType,
) -> None:
    def unexpected_analysis(*args: Any, **kwargs: Any) -> str:
        pytest.fail("Invalid audio model must stop before media analysis")

    monkeypatch.setattr(mimo_video, "analyze_audio", unexpected_analysis)
    output = tmp_path / "observation.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mimo_video.py",
            "--audio",
            "missing-song.mp3",
            "--model",
            "mimo-v2-omni",
            "--prompt",
            "分析",
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        mimo_video.main()
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "--audio requires one of" in error
    assert "mimo-v2.6-pro" in error and "mimo-v2.6-flash" in error
    assert "Traceback" not in error
    assert not output.exists()
