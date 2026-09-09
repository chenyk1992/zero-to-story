"""Run the local canvas or call its shared API from any local agent host."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lfo.canvas.client import CanvasClient
from lfo.canvas.settings import CanvasSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="项目节点画布")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--media-root", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="启动本地页面和服务")
    commands.add_parser("open", help="后台启动或找到当前项目画布")
    commands.add_parser("mcp", help="通过 STDIO 提供项目画布工具")
    call = commands.add_parser("call", help="调用与页面共用的 API；正文从 JSON 文件读取")
    call.add_argument("method", choices=["GET", "POST", "PUT"])
    call.add_argument("path")
    call.add_argument("--body-file", type=Path)
    args = parser.parse_args(argv)
    settings = CanvasSettings.resolve(args.project, args.data_dir, args.media_root, args.port)
    try:
        if args.command == "serve":
            from lfo.canvas.server import serve

            serve(settings)
        elif args.command == "mcp":
            from lfo.canvas.mcp_server import create_mcp

            create_mcp(settings).run(transport="stdio")
        elif args.command == "open":
            print(json.dumps({"url": CanvasClient(settings).ensure_server()}, ensure_ascii=False))
        else:
            body = (
                json.loads(args.body_file.read_text(encoding="utf-8-sig"))
                if args.body_file
                else None
            )
            result = CanvasClient(settings).request(args.method, args.path, body)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
