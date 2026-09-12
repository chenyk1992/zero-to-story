# -*- coding: utf-8 -*-
"""画布 v57→v58：video_P007 填 P007 提示词 + 更新 desc（首帧接线 v57 已完成，不动）。"""
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
seg = doc[doc.index('<!-- P007 PROMPT START -->'):doc.index('<!-- P007 PROMPT END -->')]
prompt = seg[seg.index('```text\n') + len('```text\n'):seg.rindex('```')].strip()
print('P007 prompt chars:', len(prompt))

cv = http("GET", f"/api/canvases/{CID}")
cv = cv.get('canvas', cv)
version = cv['version']
g = cv['graph']
for n in g['nodes']:
    if n['id'] == 'video_P007':
        n['data']['prompt'] = prompt
        n['data']['description'] = ('P007 v2 I2V【v2=master REJECT 修复：v1 林燃正对镜头咧嘴说话，破第四面墙——v2 凑近对象=沈默，'
                                    '脸四分之三侧面朝画左、视线锁定沈默、负约束禁对镜头】；首帧=P006 真实尾帧（f_0345，master ACCEPT）；'
                                    '0-2.5 后拉定场（黑板中近景→含沈默课桌）→ 2.5-5.5 翻看无老茧手背近景（EV013）→ 5.5-7.5 随视线扫向窗外操场 → '
                                    '7.5 林燃大脸凑近沈默+push-in → 7.5-10.0 D010 唯一语音窗（林燃对沈默说）→ 10.5-14 冻结；'
                                    '黑板全程无字负约束（日期字后期 UI-001）；轻快日系 BGM 低垫（蓝图 state_after）；'
                                    '成片入库工序=低于色彩验收线才调色')
        n['data']['panel_id'] = 'P007'

resp = http("PUT", f"/api/canvases/{CID}", {"version": version, "name": cv['name'], "graph": g})
print('PUT ok | submitted version:', version, '->', version + 1)
