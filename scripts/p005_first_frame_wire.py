# -*- coding: utf-8 -*-
"""Create asset_first_P005 node (P004 tail frame) and wire it to video_P005.first_frame. Idempotent."""
import copy, json, urllib.request

BASE = "http://127.0.0.1:8765"
CID = "861ebeb3-0381-42fb-819a-c7b6ad8fecf0"
PNG = r"E:\ideaProjects\zero-to-story\workspace\projects\开不了口的事\assets\first_frames\P005_first_frame_from_P004_tail.png"

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

if "asset_first_P005" not in ids:
    tmpl = next(n for n in graph["nodes"] if n.get("id") == "asset_first_P003")
    node = copy.deepcopy(tmpl)
    node["id"] = "asset_first_P005"
    node["position"] = {"x": 40, "y": 1930}
    d = node["data"]
    d["asset"] = {"kind": "image", "name": "P005_first_frame_from_P004_tail.png", "path": PNG}
    d["description"] = "P004 run 91636a6f 末帧（双人构图留白锁定末态，INCONCLUSIVE 暂定可用），2026-09-12 提取。"
    d["label"] = "P005 首帧（P004 尾帧提取）"
    d["panel_id"] = "P005"
    graph["nodes"].append(node)
    print("node asset_first_P005 created")
else:
    print("node asset_first_P005 already exists")

if "e_first_P005" not in eids:
    graph["edges"].append({"id": "e_first_P005", "source": "asset_first_P005",
                           "sourceHandle": "output", "target": "video_P005",
                           "targetHandle": "first_frame"})
    print("edge e_first_P005 created")
else:
    print("edge e_first_P005 already exists")

upd = api("PUT", f"/api/canvases/{CID}",
          {"version": cur["version"], "name": cur.get("name", ""), "graph": graph})
print("saved, version:", upd["version"], "nodes:", len(upd["graph"]["nodes"]), "edges:", len(upd["graph"]["edges"]))
