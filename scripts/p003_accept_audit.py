# -*- coding: utf-8 -*-
"""P003 (run 972c26c7) acceptance audit.

单镜连续 I2V，11.0s 规格（实际 11.542s）。预期结构（提示词）：
  0-2.0s   静止（P002 尾帧全景，四动一静）
  ~2.5s    微动（肩/手）
  ~4.5s    起身（silence 可读）
  ~6.3s    起步 + 摄影机 track left（画面内容整体右移）
  ~8.8s    人群剪影随横移从左侧入画
  ~10.2s   运动停止，末态锁定（背影被人群剪影吞没）
检查：首帧一致性 / 运动时间线 / 横移方向 / 中心站位区 / 左缘人群带 /
     屏幕与队服文字放大 / 音频 RMS 包络。
"""
import os, math, wave
from PIL import Image, ImageChops, ImageStat

VID = "E:/ideaProjects/zero-to-story/workspace/projects/861ebeb3-0381-42fb-819a-c7b6ad8fecf0/outputs/972c26c7-e007-406c-81af-e470174160d9/video_00001_.mp4"
REV = "E:/ideaProjects/zero-to-story/workspace/projects/开不了口的事/ep001/review/P003_run_972c26c7"
FR  = REV + "/frames"
REF = "E:/ideaProjects/zero-to-story/workspace/projects/开不了口的事/assets/first_frames/P003_first_frame_from_P002_tail.png"

FPS = 24.0
frames = sorted(f for f in os.listdir(FR) if f.endswith(".png"))
n = len(frames)
print(f"frames={n} duration={n/FPS:.3f}s")

imgs = [Image.open(os.path.join(FR, f)).convert("RGB") for f in frames]
W, H = imgs[0].size
print(f"size={W}x{H}")

# ---------- 1. 首帧一致性 ----------
ref = Image.open(REF).convert("RGB")
if ref.size != (W, H):
    ref = ref.resize((W, H))
st = ImageStat.Stat(ImageChops.difference(ref, imgs[0]))
print("first_frame vs P002 tail: mean abs diff RGB =", [round(x, 2) for x in st.mean])

# ---------- 工具 ----------
def small(im):  # 120x216 灰度
    return im.convert("L").resize((120, 216))

gs = [small(im) for im in imgs]

def box_diff(a, b, box):
    return ImageStat.Stat(ImageChops.difference(a.crop(box), b.crop(box))).mean[0]

# ---------- 2. 运动时间线（每 0.25s，三个区域） ----------
WHOLE = (0, 0, 120, 216)
CENTER_STA = (40, 80, 85, 190)   # 中心站位区（沈默）
LEFT_BAND  = (0, 0, 28, 216)     # 左缘人群带
print("\n== motion per 0.25s: whole / center_sta / left_band (mean abs diff) ==")
for i in range(1, n):
    if (i - 1) % 6 == 0:  # 每 6 帧 ≈ 0.25s 打一行
        seg = range(i, min(i + 6, n))
        wv = sum(ImageStat.Stat(ImageChops.difference(gs[k], gs[k-1])).mean[0] for k in seg) / len(seg)
        cv = sum(box_diff(gs[k], gs[k-1], CENTER_STA) for k in seg) / len(seg)
        lv = sum(box_diff(gs[k], gs[k-1], LEFT_BAND) for k in seg) / len(seg)
        print(f"{(i-1)/FPS:6.2f}s  whole={wv:6.2f}  center={cv:6.2f}  left={lv:6.2f}")

# ---------- 3. 横移方向（truck 窗口内，±3px 位移残差对比） ----------
def lateral_dir(i):
    a, b = gs[i], gs[i-1]
    rR = ImageStat.Stat(ImageChops.difference(a, ImageChops.offset(b, 3, 0))).mean[0]  # b 右移对齐 a
    rL = ImageStat.Stat(ImageChops.difference(a, ImageChops.offset(b, -3, 0))).mean[0] # b 左移对齐 a
    return rR, rL

print("\n== lateral direction (content moves RIGHT => camera trucks LEFT) ==")
for t in (6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0):
    i = int(t * FPS)
    if i < n:
        rR, rL = lateral_dir(i)
        verdict = "RIGHT" if rR < rL else "LEFT"
        print(f"t={t:5.2f}s  resid(shift+3)={rR:6.2f}  resid(shift-3)={rL:6.2f}  -> content {verdict}")

# ---------- 4. 左缘人群带亮度演化（人群入场证据） ----------
print("\n== left band mean brightness per 0.5s ==")
for b in range(int(n / 12)):
    seg = imgs[b*12:(b+1)*12]
    if not seg: break
    vals = [ImageStat.Stat(im.convert("L").crop((0, 0, 112, 864))).mean[0] for im in seg]
    print(f"{b*0.5:5.1f}-{(b+1)*0.5:5.1f}s  left_mean={sum(vals)/len(vals):6.1f}")

# ---------- 5. 文字核验放大图 ----------
def zoom_save(idx, box, name, scale):
    im = imgs[idx].crop(box)
    im = im.resize((im.width*scale, im.height*scale), Image.LANCZOS)
    p = f"{REV}/{name}.png"
    im.save(p)
    st = ImageStat.Stat(im.convert("L"))
    print(f"saved {name}: box={box} frame_t={idx/FPS:.2f}s stddev={st.stddev[0]:.1f} mean={st.mean[0]:.1f}")

# 静止阶段屏幕带（战斗画面应为抽象光影，无可读字）
zoom_save(int(1.0*FPS), (0, 300, 480, 560), "zoom_screens_static", 2)
# 起身阶段队服背面（silence 可读性）
zoom_save(int(5.5*FPS), (150, 380, 330, 640), "zoom_jersey_stand", 3)
# 末态整帧（人群吞没背影）
zoom_save(n-1, (0, 0, 480, 864), "zoom_end_state", 1)
# 人群入场序列（左半带，8.5s / 9.5s / 10.5s / 末帧）
sheet = Image.new("RGB", (4*240+30, 440), (20, 20, 20))
for k, t in enumerate((8.5, 9.5, 10.5, (n-1)/FPS)):
    i = min(int(t*FPS), n-1)
    c = imgs[i].crop((0, 0, 240, 864)).resize((240, 432))
    sheet.paste(c, (k*250+10, 4))
sheet.save(f"{REV}/sheet_crowd_left.png")
print("saved sheet_crowd_left.png")

# ---------- 6. 音频 RMS 包络 ----------
wav = wave.open(REV + "/audio.wav", "rb")
nfr, sr = wav.getnframes(), wav.getframerate()
raw = wav.readframes(nfr)
wav.close()
print(f"\n== audio: sr={sr} dur={nfr/sr:.2f}s ==")
print("== RMS dBFS per 0.5s ==")
samples = [int.from_bytes(raw[i:i+2], "little", signed=True) for i in range(0, len(raw), 2)]
for b in range(0, len(samples), int(0.5*sr)):
    seg = samples[b:b+int(0.5*sr)]
    if not seg: break
    rms = math.sqrt(sum(s*s for s in seg) / len(seg))
    db = 20 * math.log10(rms / 32768.0) if rms > 0 else -120
    print(f"{b/sr:5.2f}-{min((b+len(seg))/sr, nfr/sr):5.2f}s  rms={db:7.1f} dBFS")
