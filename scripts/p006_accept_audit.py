# -*- coding: utf-8 -*-
"""P006 (run 8d7eb676) 验收审计：教室醒来 · 黑板无字核验 · push-in 时序 · 唯一语音窗。

分区：SHEN16(沈默16岁) / TEACHER(老师) / BOARD_UR(黑板右上叠字区——无字核验) / LINRAN(前景林燃)。
"""
import os, wave, struct, math
from PIL import Image

REV = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P006_run_8d7eb676'
KF = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\assets\scene_keyframes\scene_keyframe_P006_classroom_day.jpg'
FR = os.path.join(REV, 'frames')

BOXES = {
    'SHEN16':  (100, 260, 260, 450),
    'TEACHER': (210, 180, 310, 340),
    'BOARD_UR':(330, 80, 460, 165),
    'LINRAN':  (5, 270, 105, 470),
}

def framediff(a, b, box):
    pa = list(a.crop(box).convert('L').getdata())
    pb = list(b.crop(box).convert('L').getdata())
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)

def stddev(img):
    px = list(img.getdata())
    n = len(px)
    m = sum(px) / n
    return math.sqrt(sum((p - m) ** 2 for p in px) / n)

def saturation(path):
    im = Image.open(path).convert('RGB').resize((120, 216))
    s = sorted(0.0 if max(r, g, b) == 0 else (max(r, g, b) - min(r, g, b)) / max(r, g, b) for r, g, b in im.getdata())
    n = len(s)
    return sum(s) / n, s[int(n * 0.9)]

frames = sorted(os.listdir(FR))
print('frames:', len(frames))

# 1) 首帧一致性 vs 关键帧
f0 = Image.open(os.path.join(FR, frames[0])).convert('RGB')
kf = Image.open(KF).convert('RGB').resize(f0.size)
pa, pb = list(f0.getdata()), list(kf.getdata())
d = sum(abs(p[0]-q[0]) + abs(p[1]-q[1]) + abs(p[2]-q[2]) for p, q in zip(pa, pb)) / (len(pa) * 3)
print('first-frame diff vs scene keyframe: %.2f' % d)

# 2) 全幅+分区帧差时间线（0.5s bins，覆盖运镜三段）
print('\n[whole+region diff, 0.5s bins]')
for half in range(0, 28):
    i, j = half * 12, half * 12 + 12
    if j > len(frames) - 1: break
    a = Image.open(os.path.join(FR, frames[i])).convert('RGB')
    b = Image.open(os.path.join(FR, frames[j])).convert('RGB')
    pa, pb = list(a.convert('L').getdata()), list(b.convert('L').getdata())
    whole = sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)
    vals = {k: framediff(a, b, box) for k, box in BOXES.items()}
    print('t=%4.1f-%4.1fs whole=%.2f  ' % (half * 0.5, half * 0.5 + 0.5, whole) +
          '  '.join('%s=%.2f' % (k, v) for k, v in vals.items()))

# 3) 黑板无字核验：BOARD_UR 每 2s stddev（<3 = 纯色区）+ 浅色像素占比
print('\n[blackboard upper-right: stddev / light-pixel ratio per 2s]')
for sec in range(0, 14, 2):
    i = min(sec * 24, len(frames) - 1)
    im = Image.open(os.path.join(FR, frames[i])).convert('RGB')
    crop = im.crop(BOXES['BOARD_UR'])
    sd = stddev(crop.convert('L'))
    px = list(crop.getdata())
    light = sum(1 for r, g, b in px if r > 140 and g > 140 and b > 140) / len(px)
    print('t=%2ds  stddev=%.2f  light_ratio=%.4f' % (sec, sd, light))

# 4) 饱和度（关键帧基线对比）
m, p90 = saturation(os.path.join(FR, frames[0]))
mk, p90k = saturation(KF)
print('\n[saturation] frame0 S_mean=%.3f S_p90=%.3f | keyframe S_mean=%.3f S_p90=%.3f' % (m, p90, mk, p90k))

# 5) 末态冻结 12-14s
mx = 0.0
for i in range(12 * 24, min(14 * 24, len(frames) - 1)):
    a = Image.open(os.path.join(FR, frames[i])).convert('L')
    b = Image.open(os.path.join(FR, frames[i + 1])).convert('L')
    pa, pb = list(a.getdata()), list(b.getdata())
    mx = max(mx, sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa))
print('[end-state freeze 12-14s] whole max diff: %.2f' % mx)

# 6) 音频 0.5s RMS + 响段
print('\n[audio 0.5s RMS dBFS]')
wf = wave.open(os.path.join(REV, 'audio.wav'), 'rb')
n, sr = wf.getnframes(), wf.getframerate()
samples = struct.unpack('<%dh' % n, wf.readframes(n)); wf.close()
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
    if db > -30 and not in_seg: in_seg, st = True, t
    elif db <= -30 and in_seg:
        in_seg = False
        print('  %.1f - %.1fs' % (st, t))
if in_seg: print('  %.1f - end' % st)

# 7) 粉笔敲击脉冲：4-7.5s 内 0.05s 窗找峰
print('\n[chalk taps 4.0-7.5s, 0.05s windows > -28dB]')
w = int(sr * 0.05)
for s in range(int(4.0 * sr), int(7.5 * sr) - w, w):
    seg = samples[s:s + w]
    rms = math.sqrt(sum(x * x for x in seg) / len(seg))
    db = 20 * math.log10(max(rms, 1) / 32768.0)
    if db > -28:
        print('  %.2fs  %.1f' % (s / sr, db))
