"""Mux rendered frames with the designated track.
python3 tools/encode.py --frames frames/full --start 0 --end 130 --track music/approved-track.m4a --out out/film.mp4 [--audio master|copy]
master (default): original track, trimmed to [start,end], -1.5 dB headroom (source decodes to +3.65 dBFS),
                  3 s fade-out only when end reaches the track end; AAC 256k.
copy: bit-exact original AAC stream (no fade; only valid for the full 0-130 s range)."""
import argparse, os, subprocess
from check_dependencies import require_dependencies, require_track
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('--frames', default='frames/full'); ap.add_argument('--start', type=float, default=0)
ap.add_argument('--end', type=float, default=130); ap.add_argument('--fps', type=int, default=30); ap.add_argument('--out', default='out/film.mp4')
ap.add_argument('--audio', choices=['master', 'copy'], default='master'); ap.add_argument('--track', required=True, help='Project-approved audio file; absolute or relative to the sample project'); ap.add_argument('--audio-start', type=float, default=0); ap.add_argument('--crf', default='16')
a = ap.parse_args(); j = lambda p: os.path.join(ROOT, p)
require_track(ap, a.track)
require_dependencies(ap, 'encode')
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
f0 = round(a.start * a.fps); dur = a.end - a.start
cmd = [FF, '-y', '-v', 'error', '-framerate', str(a.fps), '-start_number', str(f0), '-i', j(a.frames + '/f%05d.jpg'), '-ss', f'{a.audio_start:.3f}', '-t', f'{dur:.3f}', '-i', j(a.track),
       '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', a.crf, '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-r', str(a.fps), '-movflags', '+faststart']
if a.audio == 'copy': cmd += ['-c:a', 'copy']
else:
    af = 'volume=-1.5dB'
    if a.end >= 129.9: af += f',afade=t=out:st={dur-3:.3f}:d=3'
    cmd += ['-af', af, '-c:a', 'aac', '-b:a', '256k', '-ar', '44100']
cmd += ['-t', f'{dur:.3f}', j(a.out)]
subprocess.run(cmd, check=True); print('wrote', a.out)
