"""Regression tests for the local MiMo video-understanding helper."""

from __future__ import annotations

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
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "   \n\t"}}
                ]
            },
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

    with pytest.raises(ValueError, match="only for mimo-v2.5"):
        mimo_video.analyze_video(
            make_video(tmp_path), "分析", model="mimo-v2-omni", thinking="enabled"
        )


def test_cli_passes_explicit_thinking_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mimo_video: ModuleType, capsys: pytest.CaptureFixture[str]
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
