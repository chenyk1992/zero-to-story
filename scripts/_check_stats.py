import sys
sys.path.insert(0, 'src')
from lfo.comfy.client import ComfyApiClient
c = ComfyApiClient()
s = c.get_system_stats()
d = s['devices'][0]
print(f"VRAM free: {d['vram_free']/1024**3:.1f} GB")
print(f"VRAM total: {d['vram_total']/1024**3:.1f} GB")
q = c.get_queue()
running = q.get('queue_running', [])
pending = q.get('queue_pending', [])
print(f"Queue: {len(running)} running, {len(pending)} pending")
if running:
    for r in running[:3]:
        print(f"  - prompt_id={r}")
