#!/usr/bin/env python3
"""Build a deterministic perspective environment pack from a 2:1 panorama.

The script uses only ffprobe, ffmpeg's v360 filter, and the Python standard
library. It writes to a staging directory and commits the final directory only
after all views, the contact sheet, and the manifest succeed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

EXPECTED_RATIO = 2.0
RATIO_TOLERANCE = 0.05
VIEW_SIZE = 1024
FOV_DEGREES = 90
VIEWS: tuple[tuple[str, int], ...] = (
    ("yaw_0", 0),
    ("yaw_90", 90),
    ("yaw_180", 180),
    ("yaw_m90", -90),
)


class PackError(RuntimeError):
    """A user-correctable environment-pack failure."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a roughly 2:1 equirectangular panorama into four "
            "1024x1024 v360 perspective views, a contact sheet, and manifest.json."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input equirectangular panorama file.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="New directory that will receive the completed environment pack.",
    )
    parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="ffmpeg executable name or absolute path.",
    )
    parser.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="ffprobe executable name or absolute path.",
    )
    return parser


def _resolve_executable(value: str, label: str) -> str:
    candidate = Path(value).expanduser()
    has_path_part = candidate.is_absolute() or len(candidate.parts) > 1
    if has_path_part:
        if candidate.is_symlink() or not candidate.is_file():
            raise PackError(f"{label} is not a regular executable file: {value}")
        resolved = candidate.resolve()
        if not shutil.which(str(resolved)):
            raise PackError(f"{label} is not executable: {value}")
        return str(resolved)

    resolved = shutil.which(value)
    if resolved is None:
        raise PackError(f"{label} was not found on PATH: {value}")
    return resolved


def _safe_input(raw_path: str) -> Path:
    input_path = Path(raw_path).expanduser()
    if input_path.is_symlink():
        raise PackError("Input must not be a symbolic link.")
    if not input_path.exists() or not input_path.is_file():
        raise PackError(f"Input is not a regular file: {raw_path}")
    return input_path.resolve()


def _safe_output(raw_path: str, input_path: Path) -> Path:
    output_dir = Path(raw_path).expanduser()
    if output_dir.exists():
        if output_dir.is_symlink():
            raise PackError("Output directory must not be a symbolic link.")
        raise PackError(
            f"Output directory already exists; choose a new empty path: {raw_path}"
        )

    parent = output_dir.parent
    if not parent.exists() or not parent.is_dir():
        raise PackError(f"Output parent directory does not exist: {parent}")
    if parent.is_symlink():
        raise PackError("Output parent directory must not be a symbolic link.")

    resolved_output = output_dir.resolve()
    if resolved_output == input_path:
        raise PackError("Output directory cannot be the input file.")
    return output_dir


def _run(command: Sequence[str], label: str) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(command),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise PackError(f"{label} executable was not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if len(detail) > 1200:
            detail = detail[-1200:]
        suffix = f": {detail}" if detail else ""
        raise PackError(f"{label} failed{suffix}") from exc
    return completed


def _probe_dimensions(ffprobe: str, media_path: Path) -> tuple[int, int]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(media_path),
    ]
    result = _run(command, "ffprobe")
    try:
        payload: dict[str, Any] = json.loads(result.stdout)
        stream = payload["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PackError(f"ffprobe returned no usable video dimensions: {media_path}") from exc
    if width <= 0 or height <= 0:
        raise PackError(f"ffprobe returned invalid video dimensions: {media_path}")
    return width, height


def _check_source_ratio(width: int, height: int) -> float:
    ratio = width / height
    relative_error = abs(ratio - EXPECTED_RATIO) / EXPECTED_RATIO
    if relative_error > RATIO_TOLERANCE + 1e-9:
        raise PackError(
            f"Input ratio {ratio:.5f} is outside 2:1 ±5% "
            f"(measured {width}x{height})."
        )
    return ratio


def _render_view(
    ffmpeg: str,
    source_path: Path,
    stage_dir: Path,
    label: str,
    yaw: int,
) -> Path:
    output_path = stage_dir / f"{label}.png"
    filter_spec = (
        "v360=input=equirect:output=rectilinear:"
        f"yaw={yaw}:pitch=0:h_fov={FOV_DEGREES}:v_fov={FOV_DEGREES}:"
        f"w={VIEW_SIZE}:h={VIEW_SIZE}"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(source_path),
        "-vf",
        filter_spec,
        "-frames:v",
        "1",
        "-an",
        str(output_path),
    ]
    _run(command, f"ffmpeg view {label}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise PackError(f"ffmpeg did not produce a non-empty view: {output_path.name}")
    return output_path


def _render_contact_sheet(
    ffmpeg: str,
    view_paths: Sequence[Path],
    stage_dir: Path,
) -> Path:
    contact_path = stage_dir / "contact_sheet.png"
    filter_spec = (
        "[0:v][1:v]hstack=inputs=2[top];"
        "[2:v][3:v]hstack=inputs=2[bottom];"
        "[top][bottom]vstack=inputs=2[sheet]"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
    ]
    for view_path in view_paths:
        command.extend(["-i", str(view_path)])
    command.extend(
        [
            "-filter_complex",
            filter_spec,
            "-map",
            "[sheet]",
            "-frames:v",
            "1",
            "-an",
            str(contact_path),
        ]
    )
    _run(command, "ffmpeg contact sheet")
    if not contact_path.is_file() or contact_path.stat().st_size == 0:
        raise PackError("ffmpeg did not produce a non-empty contact sheet.")
    return contact_path


def _write_manifest(
    stage_dir: Path,
    input_path: Path,
    source_dimensions: tuple[int, int],
    ratio: float,
    view_paths: Sequence[Path],
    contact_path: Path,
) -> Path:
    width, height = source_dimensions
    manifest = {
        "schema": "virtual-presenter.environment-pack.v1",
        "projection": "equirectangular",
        "source": {
            "path": str(input_path),
            "width": width,
            "height": height,
            "ratio": ratio,
            "ratio_tolerance": RATIO_TOLERANCE,
        },
        "view_spec": {
            "projection": "rectilinear",
            "pitch": 0,
            "horizontal_fov": FOV_DEGREES,
            "vertical_fov": FOV_DEGREES,
            "width": VIEW_SIZE,
            "height": VIEW_SIZE,
        },
        "views": [
            {
                "name": label,
                "file": view_path.name,
                "yaw": yaw,
                "pitch": 0,
                "horizontal_fov": FOV_DEGREES,
                "vertical_fov": FOV_DEGREES,
                "width": VIEW_SIZE,
                "height": VIEW_SIZE,
            }
            for (label, yaw), view_path in zip(VIEWS, view_paths, strict=True)
        ],
        "contact_sheet": {
            "file": contact_path.name,
            "layout": "yaw_0 | yaw_90 / yaw_180 | yaw_m90",
            "width": VIEW_SIZE * 2,
            "height": VIEW_SIZE * 2,
        },
    }
    temporary_manifest = stage_dir / "manifest.json.tmp"
    manifest_path = stage_dir / "manifest.json"
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_manifest.replace(manifest_path)
    return manifest_path


def build_environment_pack(
    input_path: Path,
    output_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> Path:
    source_dimensions = _probe_dimensions(ffprobe, input_path)
    ratio = _check_source_ratio(*source_dimensions)
    stage_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=str(output_dir.parent))
    )
    committed = False
    try:
        view_paths = [
            _render_view(ffmpeg, input_path, stage_dir, label, yaw)
            for label, yaw in VIEWS
        ]
        for view_path in view_paths:
            dimensions = _probe_dimensions(ffprobe, view_path)
            if dimensions != (VIEW_SIZE, VIEW_SIZE):
                raise PackError(
                    f"Rendered view has wrong dimensions {dimensions[0]}x{dimensions[1]}: "
                    f"{view_path.name}"
                )
        contact_path = _render_contact_sheet(ffmpeg, view_paths, stage_dir)
        contact_dimensions = _probe_dimensions(ffprobe, contact_path)
        expected_contact = (VIEW_SIZE * 2, VIEW_SIZE * 2)
        if contact_dimensions != expected_contact:
            raise PackError(
                f"Contact sheet has wrong dimensions "
                f"{contact_dimensions[0]}x{contact_dimensions[1]}."
            )
        manifest_path = _write_manifest(
            stage_dir,
            input_path,
            source_dimensions,
            ratio,
            view_paths,
            contact_path,
        )
        if not manifest_path.is_file():
            raise PackError("Manifest was not created.")
        if output_dir.exists():
            raise PackError(f"Output path appeared during rendering: {output_dir}")
        stage_dir.replace(output_dir)
        committed = True
        return output_dir
    finally:
        if not committed:
            shutil.rmtree(stage_dir, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        ffmpeg = _resolve_executable(args.ffmpeg, "ffmpeg")
        ffprobe = _resolve_executable(args.ffprobe, "ffprobe")
        input_path = _safe_input(args.input)
        output_dir = _safe_output(args.output_dir, input_path)
        result = build_environment_pack(input_path, output_dir, ffmpeg, ffprobe)
    except (OSError, PackError) as exc:
        print(f"environment-pack: error: {exc}", file=sys.stderr)
        return 2
    print(f"Environment pack written to {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


