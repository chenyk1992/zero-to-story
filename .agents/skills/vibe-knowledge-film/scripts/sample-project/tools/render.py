"""Deterministic frame renderer.
python3 tools/render.py frames  --start 0 --end 130 --workers 6 --out frames/full
python3 tools/render.py stills  --times 3,12,20 --out out/keyframes
Frame f is rendered at t = f / fps; output is independent of wall-clock speed."""
import argparse, asyncio, functools, http.server, os, socketserver, threading, time, json
from check_dependencies import require_dependencies, require_chromium
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Q, directory=ROOT)
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h); s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start(); return s.server_address[1]
LAUNCH = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-accelerated-2d-canvas', '--disable-gpu-vsync']
async def open_page(b, port):
    pg = await b.new_page(viewport={'width': WIDTH, 'height': HEIGHT, 'device_scale_factor': 1})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    await pg.goto(f'http://127.0.0.1:{port}/src/index.html?w={WIDTH}&h={HEIGHT}' + ('&draft=1' if DRAFT else ''))
    for _ in range(300):
        if await pg.evaluate('window.filmReady === true'): break
        if errs: raise RuntimeError('page error: ' + '; '.join(errs))
        await asyncio.sleep(.1)
    else: raise RuntimeError('film not ready: ' + '; '.join(errs))
    facts = await pg.evaluate('({w:document.getElementById("bg").width,h:document.getElementById("bg").height,glW:document.getElementById("gl").width,draft:new URLSearchParams(location.search).get("draft")})')
    if facts['w'] != WIDTH or facts['h'] != HEIGHT or facts['glW'] != WIDTH or facts['draft'] != ('1' if DRAFT else None):
        raise RuntimeError(f'actual render params mismatch: {facts}, expected {WIDTH}x{HEIGHT}, draft={DRAFT}')
    return pg, errs
import base64
async def shoot(pg, t, path, fmt):
    if os.path.exists(path) and fmt == 'jpeg':
        try:
            with Image.open(path) as im:
                if im.size == (WIDTH, HEIGHT) and im.format == 'JPEG': return False
        except Exception: pass
    url = await pg.evaluate(f'window.grabFrame({t:.6f}, {1 if fmt == "png" else 0.93})')
    with open(path, 'wb') as f: f.write(base64.b64decode(url.split(',', 1)[1]))
    return True
WIDTH, HEIGHT, DRAFT = 1920, 1080, False
async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['frames', 'stills', 'report'])
    ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float, default=130)
    ap.add_argument('--fps', type=int, default=30); ap.add_argument('--workers', type=int, default=2); ap.add_argument('--width', type=int, default=1920); ap.add_argument('--height', type=int, default=1080); ap.add_argument('--draft', action='store_true')
    ap.add_argument('--times', default=''); ap.add_argument('--out', default='frames/full')
    global WIDTH, HEIGHT, DRAFT, Image
    a = ap.parse_args()
    require_dependencies(ap, 'render')
    from playwright.async_api import async_playwright
    from PIL import Image
    WIDTH, HEIGHT, DRAFT = a.width, a.height, a.draft
    async with async_playwright() as p:
        require_chromium(ap, p.chromium.executable_path)
        os.makedirs(os.path.join(ROOT, a.out), exist_ok=True); port = serve()
        b = await p.chromium.launch(args=LAUNCH)
        if a.mode == 'report':
            pg, _ = await open_page(b, port); print(json.dumps(await pg.evaluate('window.captionReport()'), ensure_ascii=False, indent=0)); return
        if a.mode == 'stills':
            pg, errs = await open_page(b, port)
            for t in [float(x) for x in a.times.split(',')]:
                await shoot(pg, t, os.path.join(ROOT, a.out, f't{t:07.2f}.png'), 'png')
            if errs: print('ERRORS', errs)
            return
        f0, f1 = round(a.start * a.fps), round(a.end * a.fps)
        frames = list(range(f0, f1)); t0 = time.time(); done = [0]
        async def worker(wi):
            pg, errs = await open_page(b, port)
            for f in frames[wi::a.workers]:
                await shoot(pg, f / a.fps, os.path.join(ROOT, a.out, f'f{f:05d}.jpg'), 'jpeg'); done[0] += 1
                if done[0] % 300 == 0: print(f'{done[0]}/{len(frames)} frames, {time.time()-t0:.0f}s', flush=True)
            if errs: raise RuntimeError('page errors: ' + '; '.join(errs[:5]))
        await asyncio.gather(*[worker(i) for i in range(a.workers)])
        print(f'rendered {len(frames)} frames in {time.time()-t0:.1f}s')
if __name__ == "__main__": asyncio.run(main())
