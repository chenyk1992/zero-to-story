"""Verification of an exported film (not just file presence).
python3 tools/verify.py out/film.mp4 --track music/approved-track.m4a [--start 0 --end 130]
Checks: data reproducibility from seed, caption facts, container/stream specs, audible audio,
audio = designated track (cross-correlation), black frames, frozen spans, file decodes end-to-end."""
import argparse, json, math, os, re, subprocess, sys, hashlib
from check_dependencies import require_dependencies, require_track
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float, default=130)
ap.add_argument('--track', required=True, help='Same project-approved audio used for encoding')
ap.add_argument('--audio-start', type=float, default=0)
a = ap.parse_args(); V = os.path.join(ROOT, a.video); res = []
require_track(ap, a.track)
require_dependencies(ap, 'verify')
import numpy as np, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
def check(name, ok, detail=''): res.append({'check': name, 'pass': bool(ok), 'detail': detail}); print(('PASS ' if ok else 'FAIL ') + name + (' — ' + str(detail) if detail else ''))
# 1 data reproducibility
h1 = hashlib.md5(open(os.path.join(ROOT, 'data/data.json'), 'rb').read()).hexdigest()
subprocess.run([sys.executable, os.path.join(ROOT, 'data/gen_data.py')], capture_output=True, check=True, cwd=ROOT)
h2 = hashlib.md5(open(os.path.join(ROOT, 'data/data.json'), 'rb').read()).hexdigest()
check('data.json reproducible from fixed seed', h1 == h2, h2)
D = json.load(open(os.path.join(ROOT, 'data/data.json'))); SB = json.load(open(os.path.join(ROOT, 'src/storyboard.json')))
# 2 independent recomputation of on-screen facts
rng = np.random.Generator(np.random.PCG64(D['seed'])); fl = rng.integers(0, 2, size=(D['people'], D['tosses']), dtype=np.int8)
cum = fl.cumsum(1); n = np.arange(1, D['tosses'] + 1); pr = cum / n; hl = D['highlight']
ok = sum(fl[hl, :10]) == D['facts']['heads10'] and abs(min(pr[hl, :10]) - float(D['facts']['min10'].rstrip('%')) / 100) < .005
for k in (10, 100, 1000, 10000):
    lo, hi = pr[:, k - 1].min(), pr[:, k - 1].max(); ok &= abs(lo - D['ranges'][str(k)][0]) < 1e-12 and abs(hi - D['ranges'][str(k)][1]) < 1e-12
d = 2 * cum[hl] - n; ok &= d[99] == D['facts']['hl_diff100'] and d[-1] == D['facts']['hl_diff']
check('simulation facts recomputed independently', ok, f"heads10={D['facts']['heads10']} ranges={D['facts']['range10']},{D['facts']['range1000']},{D['facts']['range10000']} gap {d[99]}→{d[-1]}")
ex = {4: (6, 16), 10: (672, 1024)}; ok = all(sum(math.comb(k, i) for i in range(math.ceil(.4 * k), math.floor(.6 * k) + 1)) == ex[k][0] and 2 ** k == ex[k][1] for k in ex)
p100 = sum(math.comb(100, i) for i in range(40, 61)) / 2 ** 100; p1000 = sum(math.comb(1000, i) for i in range(400, 601)) / 2 ** 1000
ok &= f'{p100*100:.1f}%' == D['facts']['share100'] and p1000 > .99999999
check('exact binomial shares', ok, f'4:6/16 10:672/1024 100:{p100:.6f} 1000:{p1000:.12f}')
check('Kerrich 5067/10000 = 50.67% inside simulated n=10,000 range', D['ranges']['10000'][0] < .5067 < D['ranges']['10000'][1])
check('dice mean & Cauchy series present', abs(D['dice_final'] - 3.5) < .1 and max(map(abs, D['cauchy_mean'])) > 1, f"dice {D['dice_final']:.3f}")
unres = [c['text'] for c in SB['captions'] if re.search(r'\{(\w+)\}', c['text']) and any(k not in D['facts'] for k in re.findall(r'\{(\w+)\}', c['text']))]
check('all caption placeholders resolve to computed facts', not unres, unres)
caps = SB['captions']; gaps = [round(caps[i+1]['t0'] - caps[i]['t1'], 2) for i in range(len(caps) - 1)]
short = [c['text'][:12] for c in caps if (c['t1'] - c['t0']) < max(2.6, len(re.sub(r'[\[\]\{\}\w ]', 'x', c['text'])) / 9.0)]
check('caption reading time (>= ~9 chars/s, >= 2.6 s)', not short, short)
check('captions do not overlap', min(gaps) >= 0, f'min gap {min(gaps)} s')
# 3 container
pr_ = subprocess.run([FF, '-hide_banner', '-i', V], capture_output=True, text=True).stderr
dur = re.search(r'Duration: (\d+):(\d+):([\d.]+)', pr_); dur = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])
check('duration', abs(dur - (a.end - a.start)) < .1, f'{dur:.2f}s')
check('1920x1080 @30fps h264', re.search(r'h264.*1920x1080.*30 fps', pr_) is not None, re.search(r'Video:.*', pr_)[0][:90])
check('has AAC audio stream', 'Audio: aac' in pr_)
# 4 full decode
dec = subprocess.run([FF, '-v', 'error', '-i', V, '-f', 'null', '-'], capture_output=True, text=True)
check('decodes end-to-end without errors', dec.returncode == 0 and not dec.stderr.strip(), dec.stderr.strip()[:200])
# 5 audio audible + matches designated track
def pcm(src, ss=0, t=None):
    c = [FF, '-v', 'error', '-ss', str(ss), '-i', src] + (['-t', str(t)] if t else []) + ['-ac', '1', '-ar', '8000', '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(c, capture_output=True, check=True).stdout, np.float32)
out = pcm(V); ref = pcm(os.path.join(ROOT, a.track), a.audio_start, a.end - a.start)
rms = 20 * np.log10(np.sqrt(np.mean(out ** 2)) + 1e-12)
check('exported audio is audible', rms > -40, f'RMS {rms:.1f} dBFS')
m = min(len(out), len(ref)) - 8000 * 4; o, r = out[:m], ref[:m]
cc = np.dot(o, r) / (np.linalg.norm(o) * np.linalg.norm(r) + 1e-12)
lags = [];
for st in range(0, m - 8000 * 6, 8000 * 20):
    seg = o[st:st + 8000 * 4]; win = r[max(0, st - 800):st + 8000 * 4 + 800]
    c = np.correlate(win, seg, 'valid'); lags.append((np.argmax(c) - min(st, 800)) / 8)
check('audio is the designated track (corr, drift)', cc > .97 and max(map(abs, lags)) <= 5, f'corr {cc:.4f}, offsets ms {lags}')
# 6 black / frozen frames
bd = subprocess.run([FF, '-hide_banner', '-i', V, '-vf', 'blackdetect=d=0.5:pic_th=0.985:pix_th=0.06', '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
blacks = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', bd); unexpected = [b for b in blacks if float(b[0]) < (a.end - a.start) - 1.5]
check('no unexpected black spans (end fade allowed)', not unexpected, blacks)
fz = subprocess.run([FF, '-hide_banner', '-i', V, '-vf', 'freezedetect=n=0.0008:d=2.5', '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
fr = re.findall(r'freeze_start: ([\d.]+)', fz)
check('no frozen spans > 2.5 s', not fr, fr)
json.dump(res, open(os.path.join(ROOT, 'out', os.path.basename(V) + '.verify.json'), 'w'), ensure_ascii=False, indent=1)
print(f"{sum(r['pass'] for r in res)}/{len(res)} checks passed")
