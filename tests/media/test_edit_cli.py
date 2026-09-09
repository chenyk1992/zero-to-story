from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.media import edit_cli
from lfo.media._ffmpeg import MediaCommandError
from lfo.media.speech_edit import (
    EditSegment,
    SourceInterval,
    SpeechProtectedEditPlan,
    SpeechProtectedEditResult,
    SpeechProtectedEditSpec,
)
from lfo.media.subtitles import SubtitleCue


def _write_spec(path: Path, **overrides: object) -> Path:
    values: dict[str, object] = {
        "source_path": "../media/source.mp4",
        "output_path": "../outputs/edited.mp4",
        "confirmed_silent_intervals": [
            {"start_ms": 1000, "end_ms": 2000, "confirmation": "manual_review"},
        ],
        "protected_speech_intervals": [
            {"start_ms": 2400, "end_ms": 3200, "tail_margin_ms": 200},
        ],
        "subtitle_cues": [
            {"start_ms": 500, "end_ms": 1500, "text": "before pause"},
            {"start_ms": 2800, "end_ms": 3200, "text": "spoken line"},
        ],
        "source_duration_ms": 4000,
    }
    values.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_readonly_mapping_resolves_relative_paths_and_never_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec_path = _write_spec(tmp_path / "specs" / "edit.json")
    source = (spec_path.parent / "../media/source.mp4").resolve()
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source")
    seen: dict[str, Path] = {}

    def fake_probe(path: str | Path) -> dict[str, object]:
        seen["source"] = Path(path)
        return {"duration_ms": 4000, "fps": 25.0, "has_audio": True}

    monkeypatch.setattr("lfo.media.speech_edit.probe", fake_probe)

    def fail_apply(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("readonly mode must not apply an edit")

    monkeypatch.setattr(edit_cli.SpeechProtectedEditor, "apply", fail_apply)

    code = edit_cli.main([str(spec_path)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["applied"] is False
    assert Path(payload["plan"]["source_path"]) == source
    assert (
        Path(payload["plan"]["output_path"])
        == (spec_path.parent / "../outputs/edited.mp4").resolve()
    )
    assert seen["source"] == source
    assert payload["plan"]["output_duration_ms"] == 3000
    assert payload["plan"]["mapped_subtitle_cues"] == [
        {"start_ms": 500, "end_ms": 1000, "text": "before pause"},
        {"start_ms": 1800, "end_ms": 2200, "text": "spoken line"},
    ]


def test_apply_writes_mapped_srt_from_mocked_editor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    spec_path = _write_spec(tmp_path / "specs" / "edit.json", output_path="../outputs/edited.mp4")
    source = (spec_path.parent / "../media/source.mp4").resolve()
    output = (spec_path.parent / "../outputs/edited.mp4").resolve()
    mapped = (
        SubtitleCue(200, 600, "mapped line"),
        SubtitleCue(800, 1000, "second line"),
    )
    plan = SpeechProtectedEditPlan(
        source_path=str(source),
        output_path=str(output),
        source_duration_ms=4000,
        output_duration_ms=1000,
        removed_intervals=(SourceInterval(1000, 4000),),
        kept_intervals=(SourceInterval(0, 1000),),
        segments=(EditSegment(0, 1000, 0),),
        mapped_subtitle_cues=mapped,
    )
    result = SpeechProtectedEditResult(
        True, plan=plan, output_path=str(output), command=("ffmpeg",)
    )
    seen: dict[str, SpeechProtectedEditSpec] = {}

    class FakeEditor:
        def apply(self, spec: SpeechProtectedEditSpec) -> SpeechProtectedEditResult:
            seen["spec"] = spec
            return result

    monkeypatch.setattr(edit_cli, "SpeechProtectedEditor", FakeEditor)

    code = edit_cli.main([str(spec_path), "--apply"])
    payload = json.loads(capsys.readouterr().out)
    subtitle_path = output.with_suffix(".srt")

    assert code == 0
    assert payload["ok"] is True
    assert payload["applied"] is True
    assert subtitle_path.read_text(encoding="utf-8") == (
        "1\n00:00:00,200 --> 00:00:00,600\nmapped line\n\n"
        "2\n00:00:00,800 --> 00:00:01,000\nsecond line\n"
    )
    assert Path(seen["spec"].source_path) == source
    assert Path(seen["spec"].output_path or "") == output


def test_missing_probe_emits_structured_media_command_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec_path = _write_spec(tmp_path / "edit.json")

    def missing_probe(_path: str | Path) -> dict[str, object]:
        raise MediaCommandError("Media executable not found: ffprobe")

    monkeypatch.setattr("lfo.media.speech_edit.probe", missing_probe)

    code = edit_cli.main([str(spec_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 1
    assert payload == {
        "ok": False,
        "command": "media-edit",
        "error": {"code": "E_MEDIA_COMMAND", "message": "Media executable not found: ffprobe"},
    }
    assert captured.err == ""


def test_invalid_input_is_structured_and_does_not_construct_editor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec_path = _write_spec(
        tmp_path / "edit.json",
        confirmed_silent_intervals=[
            {"start_ms": 100, "end_ms": 200, "confirmation": "automatic_vad"}
        ],
    )

    def fail_constructor() -> None:
        raise AssertionError("invalid input must fail before an editor is constructed")

    monkeypatch.setattr(edit_cli, "SpeechProtectedEditor", fail_constructor)

    code = edit_cli.main([str(spec_path)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["ok"] is False
    assert payload["command"] == "media-edit"
    assert payload["error"]["code"] == "E_INVALID_INPUT"
    assert "automatic silence detection" in payload["error"]["message"]
