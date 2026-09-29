"""Local, deterministic MV timing and finishing tools; no provider submissions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lfo.media.music_timeline import inspect_music, validate_music_timeline  # noqa: E402
from lfo.media.mv_edit import render_edit  # noqa: E402


def _save_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MV music timeline and deterministic finishing")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "analyze"):
        command = commands.add_parser(name)
        command.add_argument("--audio", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--start-ms", type=int, default=0)
        command.add_argument("--end-ms", type=int)
    check = commands.add_parser("validate")
    check.add_argument("--timeline", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    render = commands.add_parser("render")
    render.add_argument("--edit", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in {"inspect", "analyze"}:
            if args.command == "inspect":
                value = inspect_music(args.audio, start_ms=args.start_ms, end_ms=args.end_ms)
            else:
                from lfo.media.music_analysis import analyze_music

                value = analyze_music(args.audio, start_ms=args.start_ms, end_ms=args.end_ms)
            if args.output.resolve() == args.audio.resolve():
                raise ValueError("输出不得覆盖源音频")
            _save_new(args.output, value)
        elif args.command == "validate":
            value = validate_music_timeline(json.loads(args.timeline.read_text(encoding="utf-8")))
            if args.output.resolve() == args.timeline.resolve():
                raise ValueError("输出不得覆盖原时间轴")
            _save_new(args.output, value)
        else:
            value = render_edit(json.loads(args.edit.read_text(encoding="utf-8")), args.output)
        print(json.dumps(value, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
