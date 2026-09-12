# -*- coding: utf-8 -*-
"""画布 v55→v56：video_P006 填 P006 提示词 + 更新 desc（首帧接线已存在，不动）。"""
import io, json, urllib.request

BASE = "http://127.0.0.1:8765"
CID = "861ebeb3-0381-42fb-819a-c7b6ad8fecf0"
H3 = r'E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\ep001\h3_prompts.md'

def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json", "X-Canvas-Request": "1", "Origin": BASE})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

with io.open(H3, 'r', encoding='utf-8') as f:
    doc = f.read()
seg = doc[doc.index('<!-- P006 PROMPT START -->'):doc.index('<!-- P006 PROMPT END -->')]
prompt = seg[seg.index('```text\n') + len('```text\n'):seg.rindex('```')].strip()
print('P006 prompt chars:', len(prompt))

cv = http("GET", f"/api/canvases/{CID}")
cv = cv.get('canvas', cv)
version = cv['version']
g = cv['graph']
for n in g['nodes']:
    if n['id'] == 'video_P006':
        n['data']['prompt'] = prompt
        n['data']['description'] = ('P006 I2V：0-1.2 眩光脉冲（承接切黑「光刺进来」）→ 1.2 沈默猛然坐起喘气 → 4.5 老师粉笔敲黑板 3 次 → '
                                    '6.5-8.5 D009 唯一语音窗（老师侧影，不露正脸）→ 沈默低头 → 10-12 push-in 黑板右上角叠字区（干净留白）→ 12-14 冻结；'
                                    '黑板全程无字负约束（日期字后期 UI-001）；切黑 0.5s 由成片管线前置（黑场+音频静默）；'
                                    '成片入库工序=调色 sat1.6 + 前置黑场')

resp = http("PUT", f"/api/canvases/{CID}", {"version": version, "name": cv['name'], "graph": g})
print('PUT ok | submitted version:', version, '->', version + 1)
