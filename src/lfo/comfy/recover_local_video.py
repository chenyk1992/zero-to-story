# ruff: noqa: RUF001
"""Explicitly release a stopped local producer without inventing its outcome."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from lfo.canvas.client import CanvasClient
from lfo.canvas.settings import CanvasSettings
from lfo.comfy.admission import release_recovered_video_submission


def main() -> None:
    parser = argparse.ArgumentParser(description="核验本地原视频并有审计地释放占用；不生成、不确认采用")
    parser.add_argument("run_id")
    parser.add_argument("--audit", help="重用已写入的恢复审计，处理中断后接续")
    parser.add_argument("--video")
    parser.add_argument("--sha256")
    parser.add_argument("--server-restarted-at")
    parser.add_argument("--restart-evidence")
    args = parser.parse_args()
    client = CanvasClient(CanvasSettings.resolve())
    if args.audit:
        if any((args.video, args.sha256, args.server_restarted_at, args.restart_evidence)):
            parser.error("--audit 不能与新的核验参数同时使用")
        audit_path = args.audit
    else:
        if not all((args.video, args.sha256, args.server_restarted_at, args.restart_evidence)):
            parser.error("需要原视频、SHA-256、实际重启时间及实际观察证据")
        run = client.request("GET", f"/api/runs/{args.run_id}")
        proof = release_recovered_video_submission(
            run,
            video=Path(args.video),
            expected_sha256=args.sha256,
            server_restarted_at=datetime.fromisoformat(args.server_restarted_at),
            restart_evidence=args.restart_evidence,
        )
        audit_path = proof["audit_path"]
        # Make the durable audit discoverable even if the Canvas call fails.
        print(json.dumps({"audit_path": audit_path, "canvas_release_pending": True}, ensure_ascii=False), flush=True)
    result = client.request("POST", f"/api/runs/{args.run_id}/release-verified-local-resource", {"audit_path": audit_path})
    print(json.dumps({"run_id": result["id"], "status": result["status"],
                      "resource_released": result["resource_released"],
                      "provider_terminal_status": "unknown", "audit_path": audit_path}, ensure_ascii=False))


if __name__ == "__main__":
    main()
