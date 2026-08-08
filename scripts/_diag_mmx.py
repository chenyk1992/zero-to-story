import sys
sys.path.insert(0, 'src')
from lfo.storyboard.decompose import MmxLLMClient
c = MmxLLMClient(model='MiniMax-M3', max_tokens=512, timeout_sec=60)
# Test with a small system + long user
sys_msg = "You are a JSON API. Reply with one JSON object only. First char must be { and last char must be }."
user_msg = ("A" * 5000) + ' OUTPUT JSON: {"ok": true}'
out = c.complete(sys_msg, user_msg)
print('len:', len(out))
print('--- OUTPUT (first 800) ---')
print(out[:800])
