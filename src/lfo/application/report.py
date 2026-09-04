"""Structured run reports for operators and Skill callers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lfo.execution import ExecutionStore


@dataclass(frozen=True)
class RunReport:
    data: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True)


class ExecutionReportService:
    """Build a complete report exclusively from persistent runtime state."""

    def __init__(self, store: ExecutionStore) -> None:
        self.store = store

    def build(self, run_id: str) -> RunReport:
        run = self.store.get_run(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        revision = self.store.get_package_revision(str(run["revision_id"]))
        tasks = self.store.list_tasks(run_id)
        attempts = self.store.list_attempts(run_id)
        artifacts = self.store.list_artifacts(run_id)
        attempts_by_task: dict[str, list[dict[str, Any]]] = {}
        for attempt in attempts:
            attempts_by_task.setdefault(str(attempt["task_id"]), []).append(attempt)
        artifacts_by_task: dict[str, list[dict[str, Any]]] = {}
        for artifact in artifacts:
            parsed = dict(artifact)
            parsed["metadata"] = _json_object(artifact.get("metadata"))
            artifacts_by_task.setdefault(str(artifact["task_id"]), []).append(parsed)

        clips: dict[str, dict[str, Any]] = {}
        task_reports: list[dict[str, Any]] = []
        for task in tasks:
            metadata = _json_object(task.get("metadata"))
            logical_key = str(task["logical_key"])
            clip_id = logical_key.split(":", 1)[0] if ":" in logical_key else None
            task_artifacts = artifacts_by_task.get(str(task["task_id"]), [])
            task_report = {
                "task_id": task["task_id"],
                "logical_key": logical_key,
                "task_type": task["task_type"],
                "status": task["status"],
                "error": task.get("error"),
                "recovery": {
                    key: metadata.get(key)
                    for key in (
                        "failure_class",
                        "recovery_action",
                        "prompt_revision",
                        "prompt_revision_required",
                        "plan_hash",
                        "failure_evidence",
                    )
                    if key in metadata
                },
                "attempts": attempts_by_task.get(str(task["task_id"]), []),
                "artifacts": task_artifacts,
            }
            task_reports.append(task_report)
            if clip_id is not None:
                clip = clips.setdefault(
                    clip_id,
                    {
                        "clip_id": clip_id,
                        "tasks": [],
                        "backend_selection": None,
                        "qc": None,
                        "audio_qc": None,
                    },
                )
                clip["tasks"].append({"type": task["task_type"], "status": task["status"]})
                if task["task_type"] == "video.generate":
                    clip["backend_selection"] = {
                        "backend_id": metadata.get("backend_id"),
                        "backend_revision": metadata.get("backend_revision"),
                        "workflow_hash": metadata.get("workflow_hash"),
                        "operation": metadata.get("operation"),
                        "reason": "selected capability satisfied the immutable clip requirements",
                    }
                if task["task_type"] == "media.qc":
                    qc_metadata = task_artifacts[-1]["metadata"] if task_artifacts else {}
                    clip["qc"] = {
                        "passed": qc_metadata.get("qc_passed"),
                        "scope": qc_metadata.get("qc_scope", ["generation_quality"]),
                        "results": qc_metadata.get("qc_results", []),
                        "status": task["status"],
                    }
                if task["task_type"] == "audio.mix":
                    audio_metadata = (
                        task_artifacts[-1]["metadata"]
                        if task_artifacts
                        else _json_object(metadata.get("failure_evidence"))
                    )
                    clip["audio_qc"] = audio_metadata.get("audio_quality_qc")

        connection = self.store.connect()
        lineage = [
            dict(row)
            for row in connection.execute(
                """SELECT le.* FROM lineage_edges le
                   JOIN artifacts target ON target.artifact_id=le.target_artifact_id
                   JOIN tasks t ON t.task_id=target.task_id WHERE t.run_id=?
                   ORDER BY le.edge_id""",
                (run_id,),
            ).fetchall()
        ]
        snapshot = connection.execute(
            "SELECT snapshot_hash FROM run_snapshots WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return RunReport(
            {
                "run": dict(run),
                "package": {
                    "package_id": run["package_id"],
                    "revision_id": run["revision_id"],
                    "revision": revision.get("revision") if revision else None,
                    "content_hash": revision.get("content_hash") if revision else None,
                },
                "materialization_hash": snapshot["snapshot_hash"] if snapshot else None,
                "clips": sorted(clips.values(), key=lambda item: item["clip_id"]),
                "tasks": task_reports,
                "hash_lineage": [
                    {
                        "artifact_id": artifact["artifact_id"],
                        "file_hash": artifact.get("file_hash"),
                        "task_id": artifact["task_id"],
                    }
                    for artifact in artifacts
                ],
                "lineage_edges": lineage,
                "export": self.store.latest_export(run_id),
            }
        )


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}
