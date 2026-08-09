"""Run one real VideoExecutionPackage through local ComfyUI and FFmpeg."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from lfo.application.report import ExecutionReportService
from lfo.application.video_runtime import VideoRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=pathlib.Path)
    parser.add_argument("--workspace-root", type=pathlib.Path, default=pathlib.Path("workspace"))
    parser.add_argument("--db", type=pathlib.Path, default=None)
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Required to submit real generation jobs after validate and plan",
    )
    args = parser.parse_args()
    runtime = VideoRuntime(db_path=args.db, workspace_root=args.workspace_root)

    validation = runtime.validate(args.package)
    if not validation.valid:
        print(json.dumps({"valid": False, "errors": validation.errors}, ensure_ascii=False, indent=2))
        return 2
    plan = runtime.plan(args.package)
    print(json.dumps({
        "valid": True,
        "plan_id": plan.plan_id,
        "clips": plan.clip_plans,
        "warnings": plan.warnings,
        "error": plan.error,
    }, ensure_ascii=False, indent=2))
    if plan.error:
        return 2
    if not args.approve:
        print("Plan complete. Re-run with --approve to start real ComfyUI generation.")
        return 0

    result = runtime.execute(args.package, approval=True)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if result.run_id:
        report = ExecutionReportService(runtime.store).build(result.run_id)
        report_path = args.workspace_root / "runs" / result.run_id / "report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.to_json() + "\n", encoding="utf-8")
        print(f"Report: {report_path.resolve()}")
    return 0 if result.status == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
