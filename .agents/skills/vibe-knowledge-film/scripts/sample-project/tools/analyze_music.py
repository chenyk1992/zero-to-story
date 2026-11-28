"""Measure the designated track: loudness sections, beat grid, strong onsets.
Usage: python3 tools/analyze_music.py <audio> music/music_map.json
Uses the bundled imageio-ffmpeg binary for decoding; no guessing of BPM or title."""
import argparse, json, subprocess
from check_dependencies import require_dependencies, require_track
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('audio', help='Real project-approved audio file; absolute or relative to sample-project')
ap.add_argument('output', help='Analysis JSON path, relative to the current directory')
a = ap.parse_args()
src, out = str(require_track(ap, a.audio)), a.output
require_dependencies(ap, 'analyze_music')
import numpy as np
import imageio_ffmpeg
from scipy.signal import stft, find_peaks
FF = imageio_ffmpeg.get_ffmpeg_exe()
sr = 22050
raw = subprocess.run([FF,'-v','error','-i',src,'-ac','1','-ar',str(sr),'-f','f32le','-'],capture_output=True,check=True).stdout
x = np.frombuffer(raw, np.float32); dur = len(x)/sr
hop, n = 256, 2048
f, t, Z = stft(x, sr, nperseg=n, noverlap=n-hop); S = np.abs(Z); fr = sr/hop
low = (S[(f>=20)&(f<150)]**2).sum(0)
flux = np.r_[0, np.maximum(0, np.diff(np.log1p(S*100), axis=1)).sum(0)]
rms_db = 20*np.log10(np.sqrt((S**2).mean(0))+1e-9)
# 1) sections from smoothed loudness (2 s window), threshold midway
w = int(2*fr); sm = np.convolve(rms_db, np.ones(w)/w, 'same')
thr = (np.percentile(sm,10)+np.percentile(sm,90))/2
hi = sm > thr
edges = [0.0]
for i in range(1,len(hi)):
    if hi[i]!=hi[i-1]: edges.append(float(t[i]))
edges.append(dur)
# merge tiny segments (<4 s)
segs=[]
for a,b in zip(edges[:-1],edges[1:]):
    lvl = 'full' if sm[(t>=a)&(t<b)].mean()>thr else 'sparse'
    if b-a<4: lvl = segs[-1]['level'] if segs else None   # absorb tiny blips
    if segs and (segs[-1]['level']==lvl or segs[-1]['level'] is None):
        segs[-1]['end']=b; segs[-1]['level']=lvl or segs[-1]['level']
    else: segs.append({'start':a,'end':b,'level':lvl})
if segs[0]['level'] is None: segs[0]['level']='sparse'
# refine each boundary to the steepest loudness step within ±1.5 s (0.2 s window)
w2=int(0.2*fr); sm2=np.convolve(rms_db,np.ones(w2)/w2,'same'); d=np.r_[0,np.diff(sm2)]
d=np.convolve(d,np.ones(w2),'same')
for s in segs[1:]:
    m=(t>s['start']-1.5)&(t<s['start']+1.5)
    dd = d[m] if s['level']=='full' else -d[m]
    s['start']=float(t[m][np.argmax(dd)])
    if s['level']=='full':   # snap rise to the strongest onset just after
        m2=(t>s['start']-0.15)&(t<s['start']+0.25); s['start']=float(t[m2][np.argmax(flux[m2])])
for i in range(len(segs)-1): segs[i]['end']=segs[i+1]['start']
for s in segs: s['start']=round(s['start'],3); s['end']=round(s['end'],3)
# 2) beat period from onset autocorrelation over the 'full' parts
mask = np.zeros_like(flux,bool)
for s in segs:
    if s['level']=='full': mask |= (t>=s['start'])&(t<s['end'])
o = flux*mask; o=o-o[mask].mean(); o[~mask]=0
ac = np.correlate(o,o,'full')[len(o)-1:]
lags=np.arange(len(ac))/fr; m=(lags>0.3)&(lags<1.2)
p0=lags[m][np.argmax(ac[m])]
# refine period+phase by grid search maximizing onset strength at grid points
best=(-1,0,0)
first_full = next(s['start'] for s in segs if s['level']=='full')
for per in np.linspace(p0*0.99,p0*1.01,201):
    for ph in np.linspace(-0.08,0.08,33):
        g=np.arange(first_full+ph, dur, per)
        idx=np.clip((g*fr).astype(int),0,len(flux)-1)
        sc=(flux[idx]*mask[idx]).sum()
        if sc>best[0]: best=(sc,per,first_full+ph)
per, ph0 = best[1], best[2]
beats = [round(float(b),3) for b in np.arange(ph0 - per*int(ph0/per), dur, per)]
# 3) strong low-band onsets (kick-like) for snapping events
lf = np.r_[0,np.maximum(0,np.diff(np.log1p(low)))]
pk,_ = find_peaks(lf, height=np.percentile(lf,96), distance=int(0.2*fr))
peak = 20*np.log10(np.abs(x).max()+1e-12)
json.dump({'source':src,'duration':round(dur,3),'sample_rate_analysis':sr,
  'sections':segs,'beat_period':round(float(per),5),'bpm_measured':round(60/per,2),
  'downbeat_anchor':round(float(ph0),3),'beats':beats,
  'strong_onsets':[round(float(t[i]),3) for i in pk],'sample_peak_dbfs':round(float(peak),2),
  'note':'Measured by onset autocorrelation + grid fit; bar phase anchored at first full section.'},
  open(out,'w'),ensure_ascii=False,indent=1)
print(json.dumps({'duration':dur,'sections':segs,'bpm':60/per,'anchor':ph0},ensure_ascii=False))
