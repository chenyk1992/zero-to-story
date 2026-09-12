# -*- coding: utf-8 -*-
"""P005 (run d9d786c5) acceptance audit.
I2V 单镜 fixed + 末段 rack focus，14.0s 规格（实际 14.375s）。预期（提示词）：
  0-3.5s    P004 尾帧构图锁定（教练左正对、沈默右前景背对、全静止）
  ~4.3s     教练叹气（直起身、肩胸下沉、头低）
  ~5.4s     右手小摆手
  ~5.9s     D008 (S1)「算了。你父母在外面等你。」（~2.5s 语音）
  ~9.0s     rack focus：焦点教练→背景玻璃门（机位不动）
  ~10.5s    玻璃反光浮现母亲侧影（深色外套、不露正脸、抬手擦眼）+ 钢琴单音+雨声渐入
  12.0-14.0s 末态冻结
检查：首帧一致性 / fixed 无运镜 / 动作窗口 / rack focus 锐度交换 / 末态冻结 /
     母亲反光放大 / 无字 / 音频包络（含额外响段排查——P004 教训）。
"""
import os, math, wave
from PIL import Image, ImageChops, ImageStat

REV = "E:/ideaProjects/zero-to-story/workspace/projects/开不了口的事/ep001/review/P005_run_d9d786c5"
FR  = REV + "/frames"
REF = "E:/ideaProjects/zero-to-story/workspace/projects/开不了口的事/assets/first_frames/P005_first_frame_from_P004_tail.png"
FPS = 24.0

frames = sorted(f for f in os.listdir(FR) if f.endswith(".png"))
n = len(frames)
print(f"frames={n} duration={n/FPS:.3f}s")
imgs = [Image.open(os.path.join(FR, f)).convert("RGB") for f in frames]
W, H = imgs[0].size
print(f"size={W}x{H}")

# 1. 首帧一致性
ref = Image.open(REF).convert("RGB")
if ref.size != (W, H): ref = ref.resize((W, H))
st = ImageStat.Stat(ImageChops.difference(ref, imgs[0]))
print("first_frame vs P004 tail: mean abs diff RGB =", [round(x, 2) for x in st.mean])

COACH = (140, 300, 290, 520)   # 教练脸+上身
SHEN  = (300, 100, 480, 700)   # 沈默右前景
DOOR  = (20, 120, 280, 360)    # 背景玻璃门带

gs = [im.convert("L") for im in imgs]
def wdiff(i):
    return ImageStat.Stat(ImageChops.difference(gs[i], gs[i-1])).mean[0]
def bdiff(i, box):
    return ImageStat.Stat(ImageChops.difference(gs[i].crop(box), gs[i-1].crop(box))).mean[0]

# 2. 全程 0.25s 帧差（四区域）
print("\n== diff per 0.25s: whole / coach / shen / door ==")
for i in range(1, n):
    if (i - 1) % 6 == 0:
        seg = range(i, min(i + 6, n))
        wv = sum(wdiff(k) for k in seg) / len(seg)
        cv = sum(bdiff(k, COACH) for k in seg) / len(seg)
        sv = sum(bdiff(k, SHEN) for k in seg) / len(seg)
        dv = sum(bdiff(k, DOOR) for k in seg) / len(seg)
        print(f"{(i-1)/FPS:6.2f}s  whole={wv:6.2f}  coach={cv:6.2f}  shen={sv:6.2f}  door={dv:6.2f}")

# 3. 运镜排除（静止时刻 ±3px 位移残差，无方向性 = 无运镜）
print("\n== lateral residual at still moments (no camera move expected) ==")
for t in (1.5, 2.5, 3.0, 12.5, 13.5):
    i = min(int(t * FPS), n - 1)
    rR = ImageStat.Stat(ImageChops.difference(gs[i], ImageChops.offset(gs[i-1], 3, 0))).mean[0]
    rL = ImageStat.Stat(ImageChops.difference(gs[i], ImageChops.offset(gs[i-1], -3, 0))).mean[0]
    rU = ImageStat.Stat(ImageChops.difference(gs[i], ImageChops.offset(gs[i-1], 0, 3))).mean[0]
    print(f"t={t:5.2f}s  resid(x+3)={rR:6.2f}  resid(x-3)={rL:6.2f}  resid(y+3)={rU:6.2f}")

# 4. rack focus 锐度交换：教练区 vs 门区局部 stddev（0.5s 粒度，8-13s）
print("\n== sharpness swap (stddev per 0.5s): coach / door ==")
for b in range(int(7.5 * 2), int(13.5 * 2)):
    seg = imgs[b*12:(b+1)*12]
    if not seg: break
    cs = sum(ImageStat.Stat(im.convert("L").crop(COACH)).stddev[0] for im in seg) / len(seg)
    ds = sum(ImageStat.Stat(im.convert("L").crop(DOOR)).stddev[0] for im in seg) / len(seg)
    print(f"{b*0.5:5.1f}-{(b+1)*0.5:5.1f}s  coach_std={cs:6.1f}  door_std={ds:6.1f}")

# 5. 末态冻结（12.0-14.0s）
fz = [wdiff(i) for i in range(int(12.0 * FPS), n)]
print(f"\n== end freeze: frames={len(fz)}  max={max(fz):.2f}  mean={sum(fz)/len(fz):.2f}")

# 6. 放大目视
def save(idx, box, name, scale):
    im = imgs[idx].crop(box)
    im = im.resize((im.width*scale, im.height*scale), Image.LANCZOS)
    im.save(f"{REV}/{name}.png")
    print(f"saved {name}.png  t={idx/FPS:.2f}s")

save(0,   (0, 0, W, H), "zoom_first_full", 2)
save(n-1, (0, 0, W, H), "zoom_end_full", 2)
save(int(13.0*FPS), (0, 60, 300, 420), "zoom_reflection_13s", 3)   # 反光区放大
save(int(11.0*FPS), (0, 60, 300, 420), "zoom_reflection_11s", 3)
# 教练动作序列（叹气→摆手→说话起始）
sheet = Image.new("RGB", (6*200+50, 460), (20, 20, 20))
for k, t in enumerate((3.0, 4.3, 4.8, 5.4, 6.0, 7.0)):
    i = min(int(t*FPS), n-1)
    c = imgs[i].crop((60, 220, 320, 620)).resize((200, 308))
    sheet.paste(c, (k*210+10, 4))
sheet.save(f"{REV}/sheet_coach_actions.png")
print("saved sheet_coach_actions.png")
# 无字：屏幕区
save(int(6.0*FPS), (0, 100, 200, 300), "zoom_screen_6s", 3)

# 7. 音频
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
print("-- full timeline @0.5s (extra-segment scan) --")
vals = []
t = 0.0
while t < nfr/sr:
    vals.append((t, rms_db(t, t+0.5)))
    t += 0.5
for k in range(0, len(vals), 4):
    print("   " + "  ".join(f"{tt:5.2f}s:{db:6.1f}" for tt, db in vals[k:k+4]))
print("-- key windows @0.1s --")
for t0, t1, tag in ((3.8, 5.2, "sigh ~4.3s"), (5.4, 9.0, "D008 speech ~5.9-8.4s"),
                    (9.5, 12.0, "piano+rain fade-in ~10.5s"), (12.0, 14.35, "tail hold")):
    print(f"[{tag}]")
    t = t0
    while t < t1:
        print(f"   {t:5.2f}s:{rms_db(t,t+0.1):6.1f}", end="")
        t += 0.1
    print()
