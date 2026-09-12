# -*- coding: utf-8 -*-
"""P005 v2 (run 08de5aa0) 验收审计：视线揭示版 + 色彩指令效果。

新增 vs v1：饱和度全片统计（验收线 S_mean>=0.18 / S_p90>=0.30）、母亲反光区
(MOTHER) 锐度与可见性、教练瞥头时序、唯一语音窗 5.9-8.4 验证。
"""
import os, wave, struct, math
from PIL import Image

REV = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P005_v2_run_08de5aa0'
FIRST = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\assets\first_frames\P005_first_frame_v2_mother_ambient.png'
FR = os.path.join(REV, 'frames')

BOXES = {
    'COACH':  (140, 300, 290, 520),
    'SHEN':   (300, 100, 480, 700),
    'DOOR':   (20, 120, 280, 360),    # 左上玻璃门区（rack focus 应变清晰）
    'MOTHER': (288, 370, 348, 570),   # 母亲反光区
}

def gray(im, box):
    return im.crop(box).convert('L')

def stddev(img):
    px = list(img.get_flattened_data()) if hasattr(img, 'get_flattened_data') else list(img.getdata())
    n = len(px)
    m = sum(px) / n
    return math.sqrt(sum((p - m) ** 2 for p in px) / n)

def framediff(a, b, box):
    pa, pb = list(a.crop(box).convert('L').getdata()), list(b.crop(box).convert('L').getdata())
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)

def saturation(path):
    im = Image.open(path).convert('RGB').resize((120, 216))
    s_vals = []
    for r, g, b in im.getdata():
        mx, mn = max(r, g, b), min(r, g, b)
        s_vals.append(0.0 if mx == 0 else (mx - mn) / mx)
    s_vals.sort()
    n = len(s_vals)
    return sum(s_vals) / n, s_vals[n // 2], s_vals[int(n * 0.9)]

frames = sorted(os.listdir(FR))
print('frames:', len(frames))

# 1) 首帧一致性 vs 合成首帧
f0 = Image.open(os.path.join(FR, frames[0])).convert('RGB')
ref = Image.open(FIRST).convert('RGB')
pa, pb = list(f0.getdata()), list(ref.getdata())
d = sum(abs(p[0]-q[0]) + abs(p[1]-q[1]) + abs(p[2]-q[2]) for p, q in zip(pa, pb)) / (len(pa) * 3)
print('first-frame diff vs composite: %.2f' % d)

# 2) 区域帧差时间线（0.25s bin）+ 3) 教练区动作时序
print('\n[region diff timeline, 0.5s bins]')
for sec in range(0, 14, 1):
    i = sec * 24
    if i + 24 > len(frames): break
    a = Image.open(os.path.join(FR, frames[i])).convert('RGB')
    b = Image.open(os.path.join(FR, frames[i + 24])).convert('RGB')
    vals = {k: framediff(a, b, box) for k, box in BOXES.items()}
    print('t=%2d-%2ds  ' % (sec, sec + 1) + '  '.join('%s=%.2f' % (k, v) for k, v in vals.items()))

# 4) 锐度交换：coach vs door vs mother stddev（7.0-12.0s，0.5s 步）
print('\n[sharpness stddev 7.0-12.0s]')
for half in range(14, 24):
    i = half * 12
    if i >= len(frames): break
    im = Image.open(os.path.join(FR, frames[i])).convert('L')
    print('t=%.1fs  coach=%.1f  door=%.1f  mother=%.1f' % (
        half * 0.5, stddev(im.crop(BOXES['COACH'])), stddev(im.crop(BOXES['DOOR'])),
        stddev(im.crop(BOXES['MOTHER']))))

# 5) 饱和度：全片每 1s + 汇总
print('\n[saturation per 1s]')
sms, s90s = [], []
for sec in range(0, 14):
    i = min(sec * 24, len(frames) - 1)
    m, p50, p90 = saturation(os.path.join(FR, frames[i]))
    sms.append(m); s90s.append(p90)
    print('t=%2ds  S_mean=%.3f  S_p50=%.3f  S_p90=%.3f' % (sec, m, p50, p90))
print('FULL: S_mean=%.3f  S_p90=%.3f  (验收线 0.18 / 0.30)' % (sum(sms)/len(sms), sum(s90s)/len(s90s)))

# 6) 末态冻结 12.0-14.0s
print('\n[end-state freeze 12-14s]')
mx = 0.0
for i in range(12 * 24, min(14 * 24, len(frames) - 1)):
    a = Image.open(os.path.join(FR, frames[i])).convert('L')
    b = Image.open(os.path.join(FR, frames[i + 1])).convert('L')
    pa, pb = list(a.getdata()), list(b.getdata())
    fd = sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)
    mx = max(mx, fd)
print('whole-frame max diff: %.2f' % mx)

# 7) 音频：0.5s RMS 全片扫描 + 响段列表
print('\n[audio 0.5s RMS dBFS]')
wf = wave.open(os.path.join(REV, 'audio.wav'), 'rb')
n = wf.getnframes(); sr = wf.getframerate()
raw = wf.readframes(n); wf.close()
samples = struct.unpack('<%dh' % n, raw)
half = int(sr * 0.5)
rms_list = []
for s in range(0, n - half, half):
    seg = samples[s:s + half]
    rms = math.sqrt(sum(x * x for x in seg) / len(seg))
    db = 20 * math.log10(max(rms, 1) / 32768.0)
    rms_list.append((s / sr, db))
    print('%.1fs  %6.1f' % (s / sr, db))
print('\n[segments louder than -30dBFS]')
in_seg, st = False, 0
for t, db in rms_list:
    if db > -30 and not in_seg:
        in_seg, st = True, t
    elif db <= -30 and in_seg:
        in_seg = False
        print('  %.1f - %.1fs' % (st, t))
if in_seg:
    print('  %.1f - end' % st)
