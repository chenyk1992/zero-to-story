from __future__ import annotations

import json

from lfo.application.report import ExecutionReportService
from lfo.execution import ExecutionStore
from lfo.execution.dag import TaskNode


def test_report_contains_revision_backend_hash_and_qc(tmp_path) -> None:
    store = ExecutionStore(tmp_path / "runtime.db")
    store.init_schema()
    revision = store.create_package_revision(
        package_id="pkg",
        project_title="Report",
        revision=2,
        content_hash="package-hash",
        raw_json="{}",
    )
    store.create_run(run_id="run", package_id="pkg", revision_id=revision, status="COMPLETED")
    store.create_snapshot(
        snapshot_id="snapshot",
        run_id="run",
        snapshot_hash="materialization-hash",
        snapshot_json="{}",
    )
    store.persist_tasks(
        "run",
        [
            TaskNode(
                "run.video",
                "video.generate",
                "clip-1:video.generate",
                metadata={
                    "backend_id": "comfyui.h3",
                    "backend_revision": "3.0.0",
                    "workflow_hash": "workflow-hash",
                    "operation": "video.text_to_video",
                },
            ),
            TaskNode(
                "run.qc",
                "media.qc",
                "clip-1:media.qc",
                dependencies=["run.video"],
            ),
        ],
    )
    store.transition_task("run.video", "READY", "SUCCEEDED")
    store.transition_task("run.qc", "BLOCKED", "SUCCEEDED")
    store.record_artifact(
        artifact_id="artifact-qc",
        task_id="run.qc",
        artifact_type="qc_video",
        file_hash="video-hash",
        metadata={"qc_passed": True, "qc_results": []},
    )

    report = ExecutionReportService(store).build("run").data
    assert report["package"]["revision"] == 2
    assert report["materialization_hash"] == "materialization-hash"
    assert report["clips"][0]["backend_selection"]["backend_id"] == "comfyui.h3"
    assert report["clips"][0]["qc"]["passed"] is True
    assert report["hash_lineage"][0]["file_hash"] == "video-hash"
    json.dumps(report)
