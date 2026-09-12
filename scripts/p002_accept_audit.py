# -*- coding: utf-8 -*-
"""P002 (run e95dd7ce) acceptance audit: audio envelope + cut-point numerics + wide-shot motion."""
import sys, wave, array, math
from PIL import Image, ImageChops, ImageStat

sys.stdout.reconfigure(encoding='utf-8')
D = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\review\P002_run_e95dd7ce"

# ---------- 1. audio RMS envelope (50ms windows) ----------
w = wave.open(D + r"\audio.wav", 'rb')
sr, n = w.getframerate(), w.getnframes()
samples = array.array('h', w.readframes(n)); w.close()
win = int(sr * 0.05)
env = [math.sqrt(sum(x * x for x in samples[i:i + win]) / win)
       for i in range(0, len(samples) - win, win)]
print("== audio RMS/50ms (val//100), 20 per second ==")
for s in range(0, (len(env) + 19) // 20):
    row = env[s * 20:(s + 1) * 20]
    print(f"{s:>2}s: " + " ".join(f"{v // 100:>3}" for v in row))
pk = max(env)
sil = max(env[int(5.1 / 0.05):int(6.1 / 0.05)])
print(f"peak={pk:.0f}  silence(5.1-6.1s)max={sil:.0f}  ratio={pk / max(sil, 1):.1f}")

def L(img):
    return img.convert('L')

def stat_pair(fa, fb, box):
    d = ImageChops.difference(L(Image.open(fa)).crop(box), L(Image.open(fb)).crop(box))
    return round(ImageStat.Stat(d).mean[0], 2)

# ---------- 2. cut1 boundary numerics: center-region brightness ----------
print("\n== cut1 center-region (120,216,360,648) mean/std timeline ==")
seq = [("d1_013", 4.792), ("d1_014", 4.833), ("d1_015", 4.875),
       ("d3_002", 4.958), ("d3_003", 5.000), ("d3_004", 5.042), ("d3_005", 5.083),
       ("d3_006", 5.125), ("d3_007", 5.167), ("d3_008", 5.208), ("d3_009", 5.250)]
box = (120, 216, 360, 648)
for name, t in seq:
    im = L(Image.open(D + r"\frames\\" + name + ".png")).crop(box)
    st = ImageStat.Stat(im)
    print(f"{name} {t:6.3f}s  mean={st.mean[0]:6.1f}  std={st.stddev[0]:6.1f}")

# ---------- 3. cut2 boundary numerics ----------
print("\n== cut2 center-region mean timeline ==")
for name, t in [("d2_007", 8.792), ("d2_008", 8.833), ("d2_009", 8.875), ("d2_010", 8.917)]:
    im = L(Image.open(D + r"\frames\\" + name + ".png")).crop(box)
    print(f"{name} {t:6.3f}s  mean={ImageStat.Stat(im).mean[0]:6.1f}")

# ---------- 4. wide shot: screens band column motion (9.5->10.5->11.5) ----------
def col_diff(fa, fb, ybox, ncol=10):
    a = L(Image.open(fa)).crop((0, ybox[0], 480, ybox[1]))
    b = L(Image.open(fb)).crop((0, ybox[0], 480, ybox[1]))
    d = ImageChops.difference(a, b); px = d.load()
    ww, hh = d.size; out = []
    for c in range(ncol):
        x0, x1 = int(c * ww / ncol), int((c + 1) * ww / ncol)
        s = cnt = 0
        for x in range(x0, x1):
            for y in range(0, hh, 2):
                s += px[x, y]; cnt += 1
        out.append(round(s / cnt, 1))
    return out

fr = D + r"\frames\\"
r95, r105, r115 = fr + "r_13_9.5s.png", fr + "r_14_10.5s.png", fr + "r_15_11.5s.png"
print("\n== screens band(360-540) col mean-diff 9.5->10.5 ==")
print(col_diff(r95, r105, (360, 540)))
print("== screens band col mean-diff 10.5->11.5 ==")
print(col_diff(r105, r115, (360, 540)))
print("== stations band(520-700) col mean-diff 9.5->11.5 (all ~0 = nobody moves) ==")
print(col_diff(r95, r115, (520, 700)))
print("== his-back box(185,540,295,690) diff 9.5->10.5 / 10.5->11.5 ==")
print(stat_pair(r95, r105, (185, 540, 295, 690)), stat_pair(r105, r115, (185, 540, 295, 690)))

# ---------- 5. shot2 static check: reflection CU 5.2 vs 6.8 vs 8.4 ----------
rcu = (0, 150, 480, 560)
print("\n== shot2 CU region diff 5.2->6.8 / 6.8->8.4 (expect ~0) ==")
print(stat_pair(fr + "r_08_5.2s.png", fr + "r_10_6.8s.png", rcu),
      stat_pair(fr + "r_10_6.8s.png", fr + "r_12_8.4s.png", rcu))
