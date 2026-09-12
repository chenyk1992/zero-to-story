# -*- coding: utf-8 -*-
"""P007 验收审计：首帧 diff / 时序链 / 黑板无字 / 色彩 / 末态冻结 / 音频结构 / 目视图。"""
import os, wave, struct, math
from PIL import Image, ImageStat

RUN = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P007_run_46a069c8"
FRAMES = os.path.join(RUN, "frames")
FIRST = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\assets\first_frames\P007_first_frame_from_P006_tail.png"
FPS = 24
W, H = 480, 864

def fpath(n):  # 1-indexed
    return os.path.join(FRAMES, f"f_{n:04d}.png")

def load(n):
    return Image.open(fpath(n)).convert("RGB")

def diff(a, b):
    pa, pb = list(a.getdata()), list(b.getdata())
    s = 0
    for (r1, g1, b1), (r2, g2, b2) in zip(pa, pb):
        s += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
    return s / (len(pa) * 3)

def region_diff(a, b, box):
    ca, cb = a.crop(box), b.crop(box)
    return diff(ca, cb)

def sat(im):
    hsv = im.convert("HSV")
    h = hsv.histogram()[256:512]
    tot = sum(h)
    mean = sum(i * v for i, v in enumerate(h)) / tot / 255
    acc, p90 = 0, 0
    for i, v in enumerate(h):
        acc += v
        if acc >= tot * 0.9:
            p90 = i / 255
            break
    return mean, p90

def region_stats(im, box):
    c = im.crop(box).convert("L")
    st = ImageStat.Stat(c)
    px = list(c.getdata())
    light = sum(1 for v in px if v > 140) / len(px)
    return st.stddev[0], light

N = 345
print("=== 1. 首帧承接 ===")
first_ref = Image.open(FIRST).convert("RGB")
f1 = load(1)
print(f"f_0001 vs 首帧资产 diff = {diff(f1, first_ref):.2f}")

print()
print("=== 2. 时序链（whole 0.5s bins 帧差 + 关键区） ===")
SHEN16 = (40, 430, 230, 830)     # 沈默（前景左下/拉开后中景偏左）
LINRAN = (250, 180, 470, 640)    # 林燃大脸（7.5s 后右侧入画）
WINDOW = (0, 100, 180, 480)      # 窗外区（左侧）
BOARD_UR = (290, 120, 478, 330)  # 黑板右上角（首帧上部）
prev = load(1)
whole_rows = []
for n in range(2, N + 1):
    cur = load(n)
    whole_rows.append((n, diff(prev, cur)))
    prev = cur
# 0.5s bins 聚合
bins = {}
for n, d in whole_rows:
    b = int((n - 1) / FPS / 0.5)
    bins.setdefault(b, []).append(d)
for b in sorted(bins):
    v = bins[b]
    print(f"t={b*0.5:4.1f}-{(b+1)*0.5:4.1f}s whole diff mean={sum(v)/len(v):6.2f} max={max(v):6.2f}")

print()
print("=== 3. 关键区运动曲线（1s 步长区域帧差） ===")
for t in [1.0, 2.5, 4.0, 5.5, 7.0, 8.5, 10.0, 11.5, 13.0, 14.0]:
    n = min(int(t * FPS) + 1, N)
    a, b = load(max(n - 12, 1)), load(n)
    print(f"t={t:4.1f}s SHEN16={region_diff(a,b,SHEN16):6.2f} LINRAN={region_diff(a,b,LINRAN):6.2f} WINDOW={region_diff(a,b,WINDOW):6.2f} BOARD_UR={region_diff(a,b,BOARD_UR):6.2f}")

print()
print("=== 4. 黑板无字核验（0–3s 黑板在画内段） ===")
for t in [0.2, 1.0, 2.0, 3.0]:
    n = min(int(t * FPS) + 1, N)
    sd, lr = region_stats(load(n), BOARD_UR)
    print(f"t={t:4.1f}s BOARD_UR stddev={sd:5.2f} light_ratio={lr:.4f}")

print()
print("=== 5. 色彩（每 5s 段） ===")
for start in range(0, 14, 5):
    n0 = min(int(start * FPS) + 1, N)
    n1 = min(int((start + 5) * FPS) + 1, N)
    sm, p90, cnt = 0, 0, 0
    for n in range(n0, n1 + 1):
        m, p = sat(load(n))
        sm += m; p90 += p; cnt += 1
    print(f"t={start}-{start+5}s S_mean={sm/cnt:.3f} S_p90={p90/cnt:.3f}")

print()
print("=== 6. 末态冻结（13–14.3s） ===")
seg = [(n, d) for n, d in whole_rows if n >= int(13 * FPS)]
print(f"13s 后 whole diff max = {max(d for _, d in seg):.2f}")

print()
print("=== 7. 音频结构（0.5s RMS bins） ===")
wav = wave.open(os.path.join(RUN, "audio.wav"), "rb")
nf, sr = wav.getnframes(), wav.getframerate()
raw = wav.readframes(nf)
wav.close()
samples = struct.unpack(f"<{nf}h", raw)
half = sr // 2
rows = []
for i in range(0, nf - half, half):
    seg_s = samples[i:i + half]
    rms = math.sqrt(sum(v * v for v in seg_s) / len(seg_s))
    rows.append((i / sr, rms))
for t, r in rows:
    bar = "#" * int(r / 120)
    print(f"t={t:5.1f}s RMS={r:7.1f} {bar}")
loud = [t for t, r in rows if r > 2500]
print("响段（RMS>2500）:", loud if loud else "无")
