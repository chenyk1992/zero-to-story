import sys
sys.path.insert(0, 'src')
from lfo.comfy.client import ComfyApiClient
c = ComfyApiClient()
q = c.get_queue()
running = q.get('queue_running', [])
pending = q.get('queue_pending', [])
print(f'ComfyUI queue: {len(running)} running, {len(pending)} pending')
