"""Apply a confirmed cut plan using the same media API from any agent host."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from lfo.media._ffmpeg import MediaCommandError
from lfo.media.speech_edit import (
    ConfirmedSilentInterval,
    ProtectedSpeechInterval,
    SpeechProtectedEditor,
    SpeechProtectedEditSpec,
)
from lfo.media.subtitles import SubtitleCue, cues_to_srt


def _error_code(message: str, *, fallback: str = "E_MEDIA_EDIT") -> str:
    """Classify a deterministic CLI failure without hiding its message."""
    normalized = message.lower()
    if normalized.startswith("media ") or "ffmpeg" in normalized or "ffprobe" in normalized:
        return "E_MEDIA_COMMAND"
    return fallback


def _print_error(code: str, message: str) -> int:
    print(
        json.dumps(
            {"ok": False, "command": "media-edit", "error": {"code": code, "message": message}},
            ensure_ascii=False,
        )
    )
    return 1


def _load_spec(spec_file: Path) -> SpeechProtectedEditSpec:
    values = json.loads(spec_file.read_text(encoding="utf-8-sig"))
    if not isinstance(values, dict):
        raise ValueError("edit spec must be a JSON object")
    for key in ("source_path", "output_path"):
        value = values.get(key)
        if value and not Path(value).is_absolute():
            values[key] = str((spec_file.resolve().parent / value).resolve())
    for key, cls in (
        ("confirmed_silent_intervals", ConfirmedSilentInterval),
        ("protected_speech_intervals", ProtectedSpeechInterval),
        ("subtitle_cues", SubtitleCue),
    ):
        raw_items = values.get(key, [])
        if not isinstance(raw_items, list):
            raise TypeError(f"{key} must be a JSON array")
        values[key] = [cls(**item) for item in raw_items]
    return SpeechProtectedEditSpec(**values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查或执行已确定的语音保护剪辑。不调用生成模型")
    parser.add_argument("spec_file", type=Path)
    parser.add_argument(
        "--apply", action="store_true", help="写出剪辑视频与对应字幕。省略时只返回时间映射"
    )
    args = parser.parse_args(argv)
    try:
        spec = _load_spec(args.spec_file)
        editor = SpeechProtectedEditor()
        if args.apply:
            result = editor.apply(spec)
            if not result.success:
                message = result.error or "Speech-protected edit failed"
                return _print_error(_error_code(message), message)
            if result.plan is None or result.output_path is None:
                return _print_error("E_MEDIA_EDIT", "Speech-protected edit returned no output plan")
            plan = result.plan
            if plan.mapped_subtitle_cues:
                subtitle_path = Path(result.output_path).with_suffix(".srt")
                subtitle_path.write_text(
                    cues_to_srt(list(plan.mapped_subtitle_cues)), encoding="utf-8"
                )
        else:
            plan = editor.plan(spec)
        print(
            json.dumps(
                {"ok": True, "command": "media-edit", "applied": args.apply, "plan": asdict(plan)},
                ensure_ascii=False,
            )
        )
        return 0
    except MediaCommandError as exc:
        return _print_error("E_MEDIA_COMMAND", str(exc))
    except (OSError, TypeError, ValueError, KeyError) as exc:
        return _print_error("E_INVALID_INPUT", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
