import json
import requests
import uuid

# Use the API format file directly (already has proper structure)
path = r'C:\Users\Administrator\.minimax\v2\assets\2026\08\07\11-22-57-667-asset_20260807-112257-667_59dad3505b9e_93a97c80-video_minimax_h3_t2v_api.json'
wf = json.loads(open(path, encoding='utf-8').read())

print('class_types:', set(v.get('class_type') for v in wf.values()))
print('node count:', len(wf))

client_id = uuid.uuid4().hex[:8]
r = requests.post('http://127.0.0.1:8188/prompt', json={'prompt': wf, 'client_id': client_id}, timeout=30)
print('status:', r.status_code)
print('body:', r.text[:1500])
