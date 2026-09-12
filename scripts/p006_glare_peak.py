# -*- coding: utf-8 -*-
"""P006 白闪峰值逐帧核验：0.2–2.0s 窗每帧平均亮度，定位眩光脉冲形态与持续帧数。"""
import os
from PIL import Image, ImageStat

FRAMES = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P006_run_8d7eb676\frames"
FPS = 24

# 0.2s–2.0s => frame 4.8–48
start, end = 4, 50
rows = []
for i in range(start, min(end, 345) + 1):
    p = os.path.join(FRAMES, f"f_{i:04d}.png")
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert("L")
    lum = ImageStat.Stat(im).mean[0]
    t = i / FPS
    rows.append((i, t, lum))

base = [r[2] for r in rows if r[0] < 10]
base_mean = sum(base) / len(base) if base else 0
peak = max(rows, key=lambda r: r[2])

print(f"baseline(0.2-0.4s) mean luminance = {base_mean:.1f}")
print(f"peak: frame {peak[0]} t={peak[1]:.2f}s lum={peak[2]:.1f} ({peak[2]/base_mean:.2f}x baseline)")
print()
for i, t, lum in rows:
    bar = "#" * int(lum / 2)
    flag = "  <-- overexposed" if lum > 200 else ""
    print(f"f_{i:04d} t={t:5.2f}s lum={lum:6.1f} {bar}{flag}")
