#!/usr/bin/env python3
"""按显式画布、Panel 与参考资产顺序更新 R2V 草稿；不会提交生成。

--canvas ID --panel P001 --refs asset-a,asset-b --prompt-file prompts.md
提示词文件使用 ## P001 标题和 text 代码块，可用 --anchor 指定其他标题。
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'http://127.0.0.1:8765'

TAG_RE = re.compile(r'^##\s+(?P<anchor>[A-Za-z0-9]+)[^\n]*\n(?P<body>.*?)(?=\n##\s|\Z)', re.S | re.M)
PROMPT_RE = re.compile(r'```text\n(?P<prompt>.*?)\n```', re.S)


def api(method: str, path: str, body: dict | None = None) -> dict:
    hdr = {'Content-Type': 'application/json', 'X-Canvas-Request': '1', 'Origin': BASE}
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    req = urllib.request.Request(f'{BASE}{path}', data=data, headers=hdr, method=method)
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode('utf-8'))


def extract_prompt(md_path: Path, anchor: str) -> str:
    md = md_path.read_text(encoding='utf-8')
    for m in TAG_RE.finditer(md):
        if m.group('anchor') != anchor:
            continue
        pm = PROMPT_RE.search(m.group('body'))
        if pm:
            return pm.group('prompt')
    raise SystemExit(f'在 {md_path} 里找不到 {anchor} 的 ```text 提示词块')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--canvas', required=True)
    ap.add_argument('--panel', required=True)
    ap.add_argument('--node-id', help='目标视频节点的稳定 ID，默认 video_<panel>')
    ap.add_argument('--refs', required=True, help='逗号分隔的资产节点 id，顺序即 <Picture 1..n>')
    ap.add_argument('--prompt-file', required=True)
    ap.add_argument('--anchor', default=None, help='提示词文件里的段落锚（默认 = panel）')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    node_id = args.node_id or f'video_{args.panel}'
    refs = [r.strip() for r in args.refs.split(',') if r.strip()]
    if not refs or len(set(refs)) != len(refs):
        raise SystemExit('需要至少一个参考资产，且不得重复')
    prompt = extract_prompt(Path(args.prompt_file), args.anchor or args.panel)
    slots = {int(value) for value in re.findall(r'<Picture (\d+)>', prompt)}
    if slots != set(range(1, len(refs) + 1)):
        raise SystemExit('提示词 Picture 标签必须与参考素材顺序及数量一致')

    d = api('GET', f'/api/canvases/{args.canvas}')
    version, nodes, edges = d['version'], d['graph']['nodes'], d['graph']['edges']
    idx = {n['id']: n for n in nodes}
    if node_id not in idx:
        raise SystemExit(f'缺节点 {node_id}')
    for r in refs:
        if r not in idx:
            raise SystemExit(f'缺参考资产节点 {r}')
    print(f'① 画布 v{version}：{len(nodes)} 节点 / {len(edges)} 边；目标 {node_id}（原 mode={idx[node_id]["data"].get("mode")}）')

    before = len(edges)
    edges[:] = [e for e in edges if not (e['target'] == node_id and e['targetHandle'] in ('first_frame', 'last_frame', 'reference_image'))]
    print(f'② 移除 first/last_frame 边：{before - len(edges)} 条（r2v 不接受）')

    existing_ids = {edge['id'] for edge in edges}
    for i, src in enumerate(refs, start=1):
        edge_id = f'r2v:{node_id}:{i}'
        if edge_id in existing_ids:
            raise SystemExit(f'边 ID 冲突，未保存：{edge_id}')
        edges.append({'id': edge_id, 'source': src, 'sourceHandle': 'output',
                      'target': node_id, 'targetHandle': 'reference_image'})
    print(f'③ 追加 {len(refs)} 条 reference_image 边（槽位 = <Picture 1..{len(refs)}>）')
    for i, src in enumerate(refs, start=1):
        nm = (idx[src]['data'].get('asset') or {}).get('name') or idx[src]['data'].get('label', '')
        print(f'    <Picture {i}> ← {src}  {nm}')

    idx[node_id]['data']['mode'] = 'r2v'
    idx[node_id]['data']['prompt'] = prompt
    print(f'④ {node_id} → mode=r2v，提示词 {len(prompt)} 字符')

    if args.dry_run:
        print('（dry-run，不落盘）')
        return 0

    try:
        res = api('PUT', f'/api/canvases/{args.canvas}',
                  {'version': version, 'graph': d['graph'], 'name': d['name']})
        print(f'⑤ PUT 完成，画布 v{res.get("version")}')
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            raise SystemExit('画布已有并发修改，本次未保存。重新运行以读取完整新版本并重新应用修改。') from exc
        raise

    chk = api('GET', f'/api/canvases/{args.canvas}')
    cn = {n['id']: n for n in chk['graph']['nodes']}
    ins = [e for e in chk['graph']['edges'] if e['target'] == node_id]
    ref_edges = [e for e in ins if e['targetHandle'] == 'reference_image']
    print(f'⑥ 复核 v{chk["version"]}：mode={cn[node_id]["data"]["mode"]}，'
          f'reference_image={len(ref_edges)}（应 {len(refs)}），'
          f'first_frame={len([e for e in ins if e["targetHandle"] == "first_frame"])}（应 0）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
