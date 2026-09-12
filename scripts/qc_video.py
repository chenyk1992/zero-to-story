"""EP01 视频验收辅助：抽帧 + 分段音频响度。

用法:
    python scripts/qc_video.py <video_path> <outdir> [frame_count]

产物:
    <outdir>/frame_XX.jpg      均匀时间点抽帧
    <outdir>/audio_report.txt  整体与逐秒响度（volumedetect / astats）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (p.stdout or "") + (p.stderr or "")


def main() -> None:
    video = Path(sys.argv[1])
    outdir = Path(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    outdir.mkdir(parents=True, exist_ok=True)

    probe = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video),
    ])
    info = json.loads(probe)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    print(json.dumps({
        "duration": dur,
        "video": {"codec": v["codec_name"], "w": v["width"], "h": v["height"],
                  "fps": v.get("r_frame_rate")},
        "audio": ({"codec": a["codec_name"], "channels": a["channels"],
                   "sample_rate": a["sample_rate"]} if a else None),
    }, ensure_ascii=False))

    for i in range(n):
        t = dur * (i + 0.5) / n
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
             "-frames:v", "1", "-q:v", "2", str(outdir / f"frame_{i:02d}_{t:04.1f}s.jpg")])

    rep = outdir / "audio_report.txt"
    with rep.open("w", encoding="utf-8") as f:
        f.write("== overall volumedetect ==\n")
        f.write(run(["ffmpeg", "-i", str(video), "-af", "volumedetect",
                     "-f", "null", "-"]) .split("Press [q]")[0])
        step = 1.0
        t0 = 0.0
        while t0 < dur:
            seg = run(["ffmpeg", "-ss", f"{t0:.2f}", "-t", f"{step:.2f}", "-i", str(video),
                       "-af", "volumedetect", "-f", "null", "-"])
            keep = [ln for ln in seg.splitlines()
                    if "mean_volume" in ln or "max_volume" in ln]
            f.write(f"\n-- {t0:.1f}s - {min(t0 + step, dur):.1f}s --\n")
            f.write("\n".join(keep) + "\n")
            t0 += step
    print("frames+audio report ->", outdir)


if __name__ == "__main__":
    main()
