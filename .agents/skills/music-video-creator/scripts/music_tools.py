"""Local, deterministic MV timing and finishing tools; no provider submissions."""

# ruff: noqa: RUF001 -- Chinese user-facing messages.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lfo.media.music_timeline import inspect_music, validate_music_timeline  # noqa: E402
from lfo.media.mv_edit import render_edit, render_preview  # noqa: E402
from lfo.media.mv_render import validate_cache_directory  # noqa: E402


def _save_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _canvas_read(canvas_id: str, suffix: str) -> dict:
    from lfo.canvas.client import CanvasClient
    from lfo.canvas.settings import CanvasSettings

    return CanvasClient(CanvasSettings.resolve(PROJECT_ROOT)).request(
        "GET", f"/api/canvases/{canvas_id}{suffix}"
    )


def _check_adopted_segments(edit: dict, canvas_id: str) -> None:
    assets = []
    for key in ("segments", "image_overlays"):
        records = edit.get(key, [])
        if not isinstance(records, list):
            raise ValueError(f"{key} 必须是数组")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"{key} 条目必须是对象")
            for field in ("path", "sha256"):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    raise ValueError(f"{key} 条目缺少有效 {field}")
            if record.get("run_id") is not None and not isinstance(record["run_id"], str):
                raise ValueError(f"{key} run_id 必须是字符串")
            assets.append(record)
    runs = {run["id"]: run for run in _canvas_read(canvas_id, "/runs")["runs"]}
    for segment in assets:
        if not segment.get("run_id") and isinstance(segment.get("source_note"), str) and segment["source_note"].strip():
            # Imported media have no Canvas run. Their bytes/type/source are
            # checked by validate_edit; actual visual adoption stays with caller.
            continue
        run = runs.get(segment.get("run_id"), {})
        review = run.get("review") or {}
        if (run.get("status") != "succeeded" or review.get("decision") != "ACCEPT"
                or Path(review.get("output_path", "")).resolve() != Path(segment["path"]).resolve()
                or review.get("output_sha256") != segment["sha256"]):
            raise ValueError(f"正式采用不匹配：{segment.get('run_id', '缺少运行编号')}")


def _receipt_target(path: Path | None, edit: dict, edit_path: Path, output: Path) -> None:
    if path is None:
        return
    target = path.resolve()
    protected = {edit_path.resolve(), output.resolve()}
    timeline_value = edit.get("music_timeline")
    if not isinstance(timeline_value, str) or not timeline_value:
        raise ValueError("music_timeline 必须是实际时间轴路径")
    timeline_path = Path(timeline_value).resolve()
    protected.add(timeline_path)
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    source = timeline.get("source") if isinstance(timeline, dict) else None
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        raise ValueError("音乐时间轴缺少有效源音频路径")
    protected.add(Path(source["path"]).resolve())
    for key in ("segments", "sound_effects", "image_overlays"):
        records = edit.get(key, [])
        if not isinstance(records, list):
            raise ValueError(f"{key} 必须是数组")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"{key} 条目必须是对象")
            media = record.get("media", record) if key == "segments" else record
            if not isinstance(media, dict):
                raise ValueError(f"{key} 媒体必须是对象")
            if key == "segments" and media.get("type") == "placeholder":
                continue
            media_path = media.get("path")
            if not isinstance(media_path, str) or not media_path:
                raise ValueError(f"{key} 条目缺少有效媒体路径")
            protected.add(Path(media_path).resolve())
    if target in protected or target.exists() or target.is_symlink():
        raise ValueError("回执不得覆盖输入清单、媒体、输出或已有文件")


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
    render.add_argument("--cache-dir", type=Path)
    render.add_argument("--receipt", type=Path)
    render.add_argument("--canvas-id", help="正式交接时核对当前Canvas采用版本")
    preview = commands.add_parser("preview", help="渲染明确标记的结构预览，可含图片及占位")
    preview.add_argument("--edit", type=Path, required=True)
    preview.add_argument("--output", type=Path, required=True)
    preview.add_argument("--cache-dir", type=Path)
    preview.add_argument("--receipt", type=Path)
    preflight = commands.add_parser("preflight", help="只读检查当前Panel输入，不生成")
    preflight.add_argument("--canvas-id", required=True)
    preflight.add_argument("--node-id", required=True)
    preflight.add_argument("--output", type=Path, required=True)
    production = commands.add_parser("production", help="读取有证据的阶段耗时与数量")
    production.add_argument("--canvas-id", required=True)
    production.add_argument("--output", type=Path, required=True)
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
        elif args.command in {"preflight", "production"}:
            if args.command == "preflight":
                from urllib.parse import urlencode

                from lfo.canvas.client import CanvasClient
                from lfo.canvas.settings import CanvasSettings

                value = CanvasClient(CanvasSettings.resolve(PROJECT_ROOT)).request(
                    "GET", "/api/readiness?" + urlencode({"canvas_id": args.canvas_id, "node_id": args.node_id})
                )
            else:
                value = _canvas_read(args.canvas_id, "/production")
            _save_new(args.output, value)
        else:
            edit = json.loads(args.edit.read_text(encoding="utf-8"))
            _receipt_target(args.receipt, edit, args.edit, args.output)
            cache = args.cache_dir if args.cache_dir is not None else args.output.with_name(
                f".{args.output.stem}-segments"
            )
            validate_cache_directory(cache, [args.edit, *([args.receipt] if args.receipt else [])])
            if args.command == "render" and args.canvas_id:
                _check_adopted_segments(edit, args.canvas_id)
            renderer = render_preview if args.command == "preview" else render_edit
            value = renderer(edit, args.output, cache_dir=args.cache_dir)
            if args.receipt:
                _save_new(args.receipt, value)
        print(json.dumps(value, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
