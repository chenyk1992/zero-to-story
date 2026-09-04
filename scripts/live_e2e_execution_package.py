"""Run one real VideoExecutionPackage through local ComfyUI and FFmpeg."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from lfo.application.video_runtime import VideoRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=pathlib.Path)
    parser.add_argument("--workspace-root", type=pathlib.Path, default=pathlib.Path("workspace"))
    parser.add_argument("--db", type=pathlib.Path, default=None)
    parser.add_argument(
        "--machine-id",
        default="",
        help="Saved machine profile used for ComfyUI/comfy-cli execution",
    )
    parser.add_argument(
        "--approved-sha256",
        required=True,
        help="Exact SHA-256 of the approved package file",
    )
    args = parser.parse_args()
    runtime = VideoRuntime(
        db_path=args.db,
        workspace_root=args.workspace_root,
        machine_id=args.machine_id,
    )

    validation = runtime.validate(args.package)
    if not validation.valid:
        print(json.dumps({"valid": False, "errors": validation.errors}, ensure_ascii=False, indent=2))
        return 2
    result = runtime.execute(args.package, approved_sha256=args.approved_sha256)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0 if result.status == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
