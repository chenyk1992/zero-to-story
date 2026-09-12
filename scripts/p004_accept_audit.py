# -*- coding: utf-8 -*-
"""P004 (run 91636a6f) acceptance audit.
R2V 切镜两镜版，14.0s 规格（实际 14.375s）。预期结构（提示词）：
  [Shot 1] 0-5.0s   隔玻璃构图锁定（0.3s 门合闷响；烟线微动）
  硬切     5.0s     切点帧差尖峰，切后立即回落（无 morph）
  [Shot 2] 5.0-6.2s 教练按烟（画面左侧）
           ~6.8s    D005 教练 (S1) 说话（音频峰 + 左区帧差）
           ~8.8s    D006 教练 (S1) 说话
           11.3-11.9s 沈默唇动无声（右前景小幅）
           11.9-14.0s fixed 留白冻结
检查：切点定位 / 无 morph / Shot1 静止 / Shot2 左右分区 / 末态冻结 /
     门框·屏幕文字放大 / 音频 0.1s RMS 包络。
"""
import os, math, wave
from PIL import Image, ImageChops, ImageStat

REV = "E:/ideaProjects/zero-to-story/workspace/projects/开不了口的事/ep001/review/P004_run_91636a6f"
FR  = REV + "/frames"
FPS = 24.0

frames = sorted(f for f in os.listdir(FR) if f.endswith(".png"))
n = len(frames)
print(f"frames={n} duration={n/FPS:.3f}s")
imgs = [Image.open(os.path.join(FR, f)).convert("RGB") for f in frames]
W, H = imgs[0].size
print(f"size={W}x{H}")

def small(im):
    return im.convert("L").resize((120, 216))
gs = [small(im) for im in imgs]

def wdiff(i):  # whole-frame diff between i and i-1 (small)
    return ImageStat.Stat(ImageChops.difference(gs[i], gs[i-1])).mean[0]

def box_diff(a, b, box):
    return ImageStat.Stat(ImageChops.difference(a.crop(box), b.crop(box))).mean[0]

LBOX = (0, 0, 60, 216)    # 教练区（画面左侧）
RBOX = (60, 0, 120, 216)  # 沈默右前景区

# ---------- 1. 全程 0.25s 粒度帧差 ----------
print("\n== whole-frame diff per 0.25s ==")
for i in range(1, n):
    if (i - 1) % 6 == 0:
        seg = range(i, min(i + 6, n))
        wv = sum(wdiff(k) for k in seg) / len(seg)
        print(f"{(i-1)/FPS:6.2f}s  whole={wv:6.2f}")

# ---------- 2. 切点细查（4.5-5.5s 逐帧） ----------
print("\n== cut-point per-frame diff (4.5-5.5s) ==")
for i in range(108, 133):
    if i < n:
        print(f"frame#{i+1} t={i/FPS:6.3f}s  diff={wdiff(i):7.2f}")

# ---------- 3. Shot1 静止核验（0.5-4.75s，排除门动窗口） ----------
print("\n== shot1 stillness: per 0.25s whole diff (0.0-5.0s) ==")
mx, mt = 0.0, -1
for i in range(1, 120):
    seg = range(i, min(i + 6, 120))
    wv = sum(wdiff(k) for k in seg) / len(seg)
    if 0.25 <= (i-1)/FPS and wv > mx:
        mx, mt = wv, (i-1)/FPS
print(f"max whole diff in 0.25-4.96s: {mx:.2f} @ {mt:.2f}s")

# ---------- 4. Shot2 左右分区运动（5-14s 每 0.5s） ----------
print("\n== shot2 zone diff per 0.5s: L(coach) / R(shenmo fg) ==")
for i in range(120, n):
    if (i - 120) % 12 == 0:
        seg = range(i, min(i + 12, n))
        lv = sum(box_diff(gs[k], gs[k-1], LBOX) for k in seg) / len(seg)
        rv = sum(box_diff(gs[k], gs[k-1], RBOX) for k in seg) / len(seg)
        print(f"{(i-1)/FPS:6.2f}s  L={lv:6.2f}  R={rv:6.2f}")

# ---------- 5. 末态冻结（11.95-14.0s） ----------
print("\n== end freeze: per-frame whole diff from 11.95s ==")
fz = [wdiff(i) for i in range(int(11.95*FPS), n)]
print(f"frames={len(fz)}  max={max(fz):.2f}  mean={sum(fz)/len(fz):.2f}")

# ---------- 6. 两镜亮度剖面 ----------
def zone_bright(i, box):
    return ImageStat.Stat(imgs[i].convert("L").crop(box)).mean[0]
print("\n== brightness: whole / left-edge(0-100px) shot1 vs shot2 ==")
for label, i in (("shot1@2.5s", 60), ("shot1@4.5s", 108), ("shot2@6.0s", 144), ("shot2@7.5s", 180), ("shot2@12.5s", 300)):
    if i < n:
        print(f"{label:12s} whole={zone_bright(i,(0,0,W,H)):6.1f}  left_edge={zone_bright(i,(0,0,100,H)):6.1f}")

# ---------- 7. 放大目视图 ----------
def save(idx, box, name, scale):
    im = imgs[idx].crop(box)
    im = im.resize((im.width*scale, im.height*scale), Image.LANCZOS)
    im.save(f"{REV}/{name}.png")
    print(f"saved {name}.png  frame#{idx+1} t={idx/FPS:.2f}s")

save(60,  (0, 0, W, H), "zoom_shot1_full", 2)          # Shot1 整帧：门框前景核验
save(180, (0, 0, W, H), "zoom_shot2_full", 2)          # Shot2 整帧：无门框 + 教练左/沈默右核验
save(60,  (60, 80, 420, 400), "zoom_shot1_screen", 3)  # 回放屏文字核验
save(180, (0, 60, 360, 420), "zoom_shot2_screen", 3)   # Shot2 屏幕文字核验
# 切点并排：f_0120 / f_0121
pair = Image.new("RGB", (2*240+30, 440), (20, 20, 20))
for k, i in enumerate((119, 120)):
    pair.paste(imgs[i].resize((240, 432)), (k*250+10, 4))
pair.save(f"{REV}/sheet_cut_pair.png")
print("saved sheet_cut_pair.png")
# 唇动窗口（11.1-12.1s 右前景区连续帧）
lip = Image.new("RGB", (8*200+70, 460), (20, 20, 20))
for k, t in enumerate((11.1, 11.3, 11.5, 11.65, 11.8, 11.95, 12.2, 12.6)):
    i = min(int(t*FPS), n-1)
    c = imgs[i].crop((240, 60, 480, 540)).resize((200, 400))
    lip.paste(c, (k*210+10, 4))
lip.save(f"{REV}/sheet_lip_window.png")
print("saved sheet_lip_window.png")

# ---------- 8. 音频 RMS 包络 ----------
wav = wave.open(REV + "/audio.wav", "rb")
nfr, sr = wav.getnframes(), wav.getframerate()
raw = wav.readframes(nfr)
wav.close()
samples = [int.from_bytes(raw[i:i+2], "little", signed=True) for i in range(0, len(raw), 2)]
def rms_db(t0, t1):
    seg = samples[int(t0*sr):int(t1*sr)]
    if not seg: return -120.0
    r = math.sqrt(sum(s*s for s in seg)/len(seg))
    return 20*math.log10(r/32768.0) if r > 0 else -120.0
print(f"\n== audio sr={sr} dur={nfr/sr:.2f}s ==")
print("-- key windows @0.1s --")
for t0, t1, tag in ((0.0,1.2,"door thud ~0.3s"), (5.0,6.6,"ceramic clink ~5.6s"),
                    (6.4,8.6,"D005 speech ~6.8s"), (8.4,11.4,"D006 speech ~8.8s"),
                    (11.2,12.4,"lip window (silent)"), (12.4,14.3,"tail hold")):
    step = 0.1
    t = t0
    line = []
    while t < t1:
        line.append(f"{t:5.2f}s:{rms_db(t,t+step):6.1f}")
        t += step
    print(f"[{tag}]")
    for k in range(0, len(line), 6):
        print("   " + "  ".join(line[k:k+6]))
