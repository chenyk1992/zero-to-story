# -*- coding: utf-8 -*-
"""Create asset_first_P007 node (P006 tail frame) and wire it to video_P007.first_frame. Idempotent."""
import copy, json, urllib.request

BASE = "http://127.0.0.1:8765"
CID = "861ebeb3-0381-42fb-819a-c7b6ad8fecf0"
PNG = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\assets\first_frames\P007_first_frame_from_P006_tail.png"

def api(method, path, body=None):
    headers = {"Content-Type": "application/json"}
    if method in {"POST", "PUT"}:
        headers["X-Canvas-Request"] = "1"
    req = urllib.request.Request(BASE + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

cur = api("GET", f"/api/canvases/{CID}")
graph = cur["graph"]
ids = {n.get("id") for n in graph["nodes"]}
eids = {e.get("id") for e in graph["edges"]}

# 以 video_P007 位置为基准放 asset 节点（其左侧 420px）
vp7 = next(n for n in graph["nodes"] if n.get("id") == "video_P007")
pos = vp7.get("position") or {"x": 0, "y": 0}
ax, ay = pos["x"] - 420, pos["y"]

if "asset_first_P007" not in ids:
    tmpl = next(n for n in graph["nodes"] if n.get("id") == "asset_first_P003")
    node = copy.deepcopy(tmpl)
    node["id"] = "asset_first_P007"
    node["position"] = {"x": ax, "y": ay}
    d = node["data"]
    d["asset"] = {"kind": "image", "name": "P007_first_frame_from_P006_tail.png", "path": PNG}
    d["description"] = "P006 run 8d7eb676 末帧 f_0345（黑板中近景+老师侧身+沈默前景低头；master ACCEPT @2026-09-12），2026-09-12 提取。"
    d["label"] = "P007 首帧（P006 尾帧提取）"
    d["panel_id"] = "P007"
    graph["nodes"].append(node)
    print("node asset_first_P007 created at", ax, ay)
else:
    print("node asset_first_P007 already exists")

if "e_first_P007" not in eids:
    graph["edges"].append({"id": "e_first_P007", "source": "asset_first_P007",
                           "sourceHandle": "output", "target": "video_P007",
                           "targetHandle": "first_frame"})
    print("edge e_first_P007 created")
else:
    print("edge e_first_P007 already exists")

upd = api("PUT", f"/api/canvases/{CID}",
          {"version": cur["version"], "name": cur.get("name", ""), "graph": graph})
print("saved, version:", upd["version"], "nodes:", len(upd["graph"]["nodes"]), "edges:", len(upd["graph"]["edges"]))
