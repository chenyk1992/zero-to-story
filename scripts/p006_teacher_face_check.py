# -*- coding: utf-8 -*-
"""P006 D009 窗内老师面部核验：6.0s / 7.5s / 8.0s 三帧裁上部区域 3x 放大。"""
from PIL import Image
import os

FRAMES = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P006_run_8d7eb676\frames"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P006_run_8d7eb676"

targets = [(144, 6.0), (180, 7.5), (192, 8.0)]
crops = []
for idx, t in targets:
    p = os.path.join(FRAMES, f"f_{idx:04d}.png")
    im = Image.open(p)
    w, h = im.size
    # 裁上部 45% 宽带（老师活动区），x 全宽收中带
    box = (int(w * 0.20), int(h * 0.08), int(w * 0.72), int(h * 0.42))
    c = im.crop(box)
    c = c.resize((c.width * 3, c.height * 3), Image.LANCZOS)
    crops.append((c, t))

total_w = sum(c.width for c, _ in crops)
total_h = max(c.height for c, _ in crops)
sheet = Image.new("RGB", (total_w, total_h), (20, 20, 20))
x = 0
for c, _ in crops:
    sheet.paste(c, (x, 0))
    x += c.width
out_path = os.path.join(OUT, "zoom_teacher_face_d009.png")
sheet.save(out_path)
print(f"saved: {out_path}")
print(f"sheet size: {sheet.size}, source frames: f_0144(6.0s) f_0180(7.5s) f_0192(8.0s)")
