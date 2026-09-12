# -*- coding: utf-8 -*-
"""把 h3_prompts.md 里标记包裹的提示词填入画布 video 节点并可选提交 Comfy run。

用法:
  python scripts/put_video_prompt.py <canvas_id> <node_id> <md_path> <START_MARKER> <END_MARKER> \
      [--submit] [--set-desc "新描述"]

- 提取标记之间的 ```text 围栏内容作为 prompt（去掉围栏行）。
- GET 画布 → 改目标节点 data.prompt（及可选 data.description）→ 带 X-Canvas-Request 全量 PUT。
- --submit 时以 PUT 返回的新版本 POST /api/canvases/{cid}/runs。
"""
import json
import re
import sys
import uuid
import urllib.request

BASE = "http://127.0.0.1:8765"


def http(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"X-Canvas-Request": "1"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def extract_prompt(md_path: str, start_marker: str, end_marker: str) -> str:
    text = open(md_path, encoding="utf-8").read()
    i = text.index(start_marker) + len(start_marker)
    j = text.index(end_marker)
    block = text[i:j].strip()
    m = re.search(r"```text\s*\n(.*?)\n```", block, re.S)
    if not m:
        raise SystemExit("ERROR: no ```text fence inside markers")
    return m.group(1).strip()


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 5:
        raise SystemExit(__doc__)
    canvas_id, node_id, md_path, start_marker, end_marker = args[:5]
    submit = "--submit" in args
    desc = None
    if "--set-desc" in args:
        desc = args[args.index("--set-desc") + 1]

    prompt = extract_prompt(md_path, start_marker, end_marker)
    print(f"extracted prompt chars: {len(prompt)}")

    canvas = http("GET", f"/api/canvases/{canvas_id}")
    graph = canvas["graph"]
    nodes = graph["nodes"]
    if isinstance(nodes, dict):
        node = nodes[node_id]
    else:
        node = next(n for n in nodes if n.get("id") == node_id)
    node.setdefault("data", {})["prompt"] = prompt
    if desc is not None:
        node["data"]["description"] = desc

    updated = http(
        "PUT",
        f"/api/canvases/{canvas_id}",
        {"version": canvas["version"], "name": canvas.get("name"), "graph": graph},
    )
    new_version = updated["version"]
    print(f"PUT ok: canvas version {canvas['version']} -> {new_version}")

    if submit:
        run = http(
            "POST",
            f"/api/canvases/{canvas_id}/runs",
            {"node_id": node_id, "version": new_version, "request_id": uuid.uuid4().hex},
        )
        print("run submitted:", json.dumps({k: run.get(k) for k in ("id", "request_id", "status", "stage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
