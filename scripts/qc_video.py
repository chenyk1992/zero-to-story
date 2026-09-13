"""视频审片辅助：抽样帧和一次整体响度检查；不替代听审或真实尾帧。

用法:
    python scripts/qc_video.py <video_path> <outdir> [frame_count]
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> str:
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Media command timed out: {cmd[0]}") from exc
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout or "Media command failed")[-1200:])
    return (p.stdout or "") + (p.stderr or "")


def main() -> None:
    if len(sys.argv) < 3:
        raise ValueError("usage: qc_video.py <video_path> <outdir> [frame_count]")
    video = Path(sys.argv[1])
    outdir = Path(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    if n < 2 or n > 120:
        raise ValueError("frame_count must be between 2 and 120")
    if not video.is_file():
        raise FileNotFoundError(video)

    info = json.loads(run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video),
    ]))
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if v is None:
        raise ValueError("Input has no video stream")
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration") or 0)
    if not math.isfinite(dur) or dur <= 0:
        raise ValueError("Input duration must be finite and positive")

    outdir.mkdir(parents=True, exist_ok=False)
    print(json.dumps({
        "duration": dur,
        "video": {"codec": v.get("codec_name"), "w": v.get("width"),
                   "h": v.get("height"), "fps": v.get("r_frame_rate")},
        "audio": ({"codec": a.get("codec_name"), "channels": a.get("channels"),
                   "sample_rate": a.get("sample_rate")} if a else None),
    }, ensure_ascii=False))

    for i in range(n):
        t = dur * (i + 0.5) / n
        frame = outdir / f"frame_{i:02d}_{t:04.1f}s.jpg"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
             "-frames:v", "1", "-q:v", "2", str(frame)])
        if not frame.is_file() or frame.stat().st_size == 0:
            raise RuntimeError(f"Frame extraction produced no file: {frame}")

    report = outdir / "audio_report.txt"
    if a is None:
        report.write_text("No audio stream; no listening evidence inferred.\n", encoding="utf-8")
        print("frames ->", outdir)
        return
    volume_output = run(["ffmpeg", "-i", str(video), "-af", "volumedetect", "-f", "null", "-"])
    volume_lines = [
        line for line in volume_output.splitlines() if "mean_volume" in line or "max_volume" in line
    ]
    if not volume_lines:
        raise RuntimeError("Audio analysis produced no volume statistics")
    report.write_text("== overall volumedetect ==\n" + "\n".join(volume_lines) + "\n", encoding="utf-8")
    print("frames+audio report ->", outdir)


if __name__ == "__main__":
    main()
