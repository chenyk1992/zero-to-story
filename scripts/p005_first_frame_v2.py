# -*- coding: utf-8 -*-
"""P005 首帧 v2 合成：母亲反光从开场隐约在场（视线揭示版前置条件）。

底图 = P004 末帧（现首帧资产），素材 = P005 run 末帧的母亲反光 patch。
处理：patch 高斯模糊 2px + alpha 0.35 + 边缘 14px 线性羽化 → 贴入底图同位置。
"""
from PIL import Image, ImageFilter, ImageStat

REV = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review'
ASSET_DIR = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\assets\first_frames'

base = Image.open(ASSET_DIR + r'\P005_first_frame_from_P004_tail.png').convert('RGB')
tail = Image.open(REV + r'\P005_run_d9d786c5\frames\f_0345.png').convert('RGB')

# 1) 对齐度验证：patch 区域两帧像素差
BOX = (278, 356, 372, 592)  # x0,y0,x1,y1 — 母亲 + 周围玻璃环境
b_px = list(base.crop(BOX).getdata())
t_px = list(tail.crop(BOX).getdata())
diffs = [abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2]) for p, q in zip(b_px, t_px)]
mean_d = sum(diffs) / len(diffs) / 3.0
print('patch base-vs-tail mean abs diff: %.2f (0-255/通道)' % mean_d)

# 2) 素材 patch：模糊 2px（隐约感）
patch = tail.crop(BOX).filter(ImageFilter.GaussianBlur(2.0))

# 3) 羽化 alpha mask：中心 0.35，向边缘 14px 线性衰减到 0
W, H = patch.size
FEATHER = 14
ALPHA = 0.35
mask = Image.new('L', (W, H), 0)
mpx = mask.load()
for y in range(H):
    for x in range(W):
        d = min(x, y, W - 1 - x, H - 1 - y)
        a = ALPHA if d >= FEATHER else ALPHA * (d / FEATHER)
        mpx[x, y] = int(a * 255)

# 4) 合成
canvas = base.copy()
canvas.paste(patch, (BOX[0], BOX[1]), mask)
out = ASSET_DIR + r'\P005_first_frame_v2_mother_ambient.png'
canvas.save(out)
print('saved:', out)

# 5) 对比图：底图 | v2 首帧（全幅） + patch 区放大
zoom = canvas.crop(BOX).resize((W * 3, H * 3), Image.LANCZOS)
base_crop = base.crop(BOX).resize((W * 3, H * 3), Image.LANCZOS)
comp = Image.new('RGB', (W * 3 * 2 + 8, H * 3), (30, 30, 30))
comp.paste(base_crop, (0, 0))
comp.paste(zoom, (W * 3 + 8, 0))
comp.save(REV + r'\P005_run_d9d786c5\first_frame_v2_compare.png')
print('saved compare')
