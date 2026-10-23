"""Prepare bounded local media evidence; never install, download models or call cloud APIs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def prepare(input_path: Path, output: Path, *, frame_count: int = 8) -> dict:
    input_path = input_path.resolve(strict=True)
    if not input_path.is_file():
        raise ValueError("input must be an existing local file")
    if not 1 <= frame_count <= 24:
        raise ValueError("frame count must be between 1 and 24")
    probe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not probe or not ffmpeg:
        raise ValueError("existing ffprobe and ffmpeg are required; nothing installed automatically")
    result = subprocess.run([probe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(input_path)],
                            check=True, capture_output=True, text=True, encoding="utf-8", timeout=60)
    media = json.loads(result.stdout)
    duration = float(media.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("media duration is unknown or invalid")
    output.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256()
    with input_path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    manifest = {"source": str(input_path), "sha256": digest.hexdigest(),
                "prepared_at": datetime.now(timezone.utc).isoformat(), "duration_seconds": duration,
                "frames": [],
                "limitations": "sampled frames are not continuous audiovisual review; use existing captions for text"}
    (output / "probe.json").write_text(json.dumps(media, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        if any(stream.get("codec_type") == "video" for stream in media.get("streams", [])):
            for index in range(frame_count):
                seconds = duration * (index + 0.5) / frame_count
                filename = f"frame-{index + 1:02d}.jpg"
                subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-ss", str(seconds), "-i", str(input_path),
                                "-frames:v", "1", "-vf", "scale=960:-2", "-n", str(output / filename)],
                               check=True, capture_output=True, timeout=60)
                if not (output / filename).is_file():
                    raise ValueError("frame extraction returned no file")
                manifest["frames"].append({"seconds": round(seconds, 3), "path": filename})
    except Exception as error:
        manifest["error"] = f"{type(error).__name__}: {str(error)[:300]}"
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        manifest = prepare(args.input, args.output_dir, frame_count=args.frames)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 2 if manifest.get("error") else 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
