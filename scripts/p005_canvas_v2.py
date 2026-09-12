# -*- coding: utf-8 -*-
"""画布 v54→v55：P005 v2 上画布——首帧资产换合成版 + prompt 换视线揭示版。"""
import io, json, urllib.request

BASE = "http://127.0.0.1:8765"
CID = "861ebeb3-0381-42fb-819a-c7b6ad8fecf0"
H3 = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\h3_prompts.md'

def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json", "X-Canvas-Request": "1",
                 "Origin": BASE})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

# 1) 提取 v2 提示词
with io.open(H3, 'r', encoding='utf-8') as f:
    doc = f.read()
seg = doc[doc.index('<!-- P005 PROMPT START -->'):doc.index('<!-- P005 PROMPT END -->')]
prompt = seg[seg.index('```text\n') + len('```text\n'):seg.rindex('```')].strip()
print('v2 prompt chars:', len(prompt))

# 2) 读画布
cv = http("GET", f"/api/canvases/{CID}")
cv = cv.get('canvas', cv)
version = cv['version']
g = cv['graph']
for n in g['nodes']:
    if n['id'] == 'asset_first_P005':
        n['data']['asset']['name'] = 'P005_first_frame_v2_mother_ambient.png'
        n['data']['asset']['path'] = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\assets\first_frames\P005_first_frame_v2_mother_ambient.png'
        n['data']['label'] = 'P005 首帧 v2（母亲反光隐约在场）'
        n['data']['description'] = 'P004 末帧 + 母亲反光 patch 合成（blur2px/alpha0.35/羽化14px）：视线揭示版前置——反光开场即隐约在场'
    if n['id'] == 'video_P005':
        n['data']['prompt'] = prompt
        n['data']['description'] = ('P005 v2 视线揭示版：0-3.5 静止（母亲反光已隐约在玻璃）→ 4.3 叹气 → 5.4 摆手 → '
                                    '5.9-8.4 D008（全片唯一语音窗）→ 7.2 教练侧头瞥玻璃 → 7.8-10.5 焦点随视线转移到反光（rack focus 有动因）→ '
                                    '9.8 钢琴+雨渐入 → 12-14 冻结在玻璃画面；色彩 vivid/暖冷对比，禁黑白观感；单镜 fixed 禁切镜禁推近')

# 3) PUT
resp = http("PUT", f"/api/canvases/{CID}", {"version": version, "name": cv['name'], "graph": g})
print('PUT resp keys:', sorted(resp.keys()) if isinstance(resp, dict) else type(resp))
print('submitted version:', version, '->', version + 1)
