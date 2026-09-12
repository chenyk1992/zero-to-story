# -*- coding: utf-8 -*-
"""P007 目视图：时序链 sheet + 手部/黑板/林燃脸/末态放大。"""
from PIL import Image, ImageDraw
import os

RUN = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P007_run_46a069c8"
FRAMES = os.path.join(RUN, "frames")

def load(n):
    return Image.open(os.path.join(FRAMES, f"f_{n:04d}.png")).convert("RGB")

# 1) 时序链 sheet（11 帧）
times = [0.3, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.5, 10.0, 12.0, 13.9]
thumbs = [load(min(int(t * 24) + 1, 345)) for t in times]
tw = 200
th = int(tw * 864 / 480)
sheet = Image.new("RGB", (tw * len(thumbs) + (len(thumbs) - 1) * 4, th), (15, 15, 15))
d = ImageDraw.Draw(sheet)
for i, (im, t) in enumerate(zip(thumbs, times)):
    x = i * (tw + 4)
    sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, 0))
    d.text((x + 6, th - 22), f"{t:.1f}s", fill=(255, 255, 80))
sheet.save(os.path.join(RUN, "sheet_chain.png"))
print("sheet_chain.png", sheet.size)

# 2) 手部放大（4.0s 下半区）
for fno, box, scale, name in [
    (min(int(4.0 * 24) + 1, 345), (0, 400, 480, 864), 2, "zoom_hands_4s.png"),
    (min(int(1.0 * 24) + 1, 345), (200, 60, 480, 400), 2, "zoom_board_1s.png"),
    (min(int(10.0 * 24) + 1, 345), (150, 100, 480, 600), 2, "zoom_linran_10s.png"),
    (345, None, 1, "zoom_end_full.png"),
]:
    im = load(fno)
    if box:
        c = im.crop(box)
        c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
        im = c
    im.save(os.path.join(RUN, name))
    print(name, im.size)
