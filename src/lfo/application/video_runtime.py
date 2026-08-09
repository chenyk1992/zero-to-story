"""VideoRuntime — the Python facade for the LFO v1 runtime.

This is the primary entry point for programmatic use:
    run = VideoRuntime().execute("execution-package.json")

Also provides validate, plan, status, retry, cancel, review, export.
"""
from __future__ import annotations

import pathlib
import uuid
from dataclasses import dataclass, field
from typing import Any

from lfo.backends.registry import BackendRegistry
from lfo.core.canonical import hash_value
from lfo.execution.dag import build_dag
from lfo.execution.handlers import default_fake_registry
from lfo.execution.materializer import MaterializationError, materialize
from lfo.execution.runtime import Runtime
from lfo.contracts.package import VideoExecutionPackage, validate_package
from lfo.contracts.errors import ValidationResult


@dataclass
class ValidationResult2:
    """Result of validate() call."""

    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PlanResult:
    """Result of plan() call — a dry-run materialization."""

    plan_id: str
    clip_plans: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backend_summary: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None


@dataclass
class RunResult:
    """Result of execute() call."""

    run_id: str
    status: str
    clip_count: int = 0
    error: str | None = None


@dataclass
class StatusResult:
    """Result of status() call."""

    run_id: str
    status: str
    tasks: dict[str, str] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ReviewResult:
    """Result of review() call."""

    review_id: str
    decision: str
    error: str | None = None


@dataclass
class ExportResult2:
    """Result of export() call."""

    export_id: str
    status: str
    file_path: str | None = None
    error: str | None = None


class VideoRuntime:
    """Python facade for the LFO v1 video runtime.

    In production, this would use ExecutionStore for persistence. Here we
    use in-memory state for integration testing.
    """

    def __init__(self, registry: BackendRegistry | None = None) -> None:
        self.registry = registry or BackendRegistry()
        self._runs: dict[str, dict[str, Any]] = {}  # run_id -> run state

    def validate(self, path: pathlib.Path | str) -> ValidationResult2:
        """Validate a package file without importing or executing.

        Checks schema, paths, and capability requirements.
        """
        p = pathlib.Path(path)
        if not p.exists():
            return ValidationResult2(valid=False, errors=[{"path": str(path), "message": "File not found", "code": "not_found"}])

        try:
            data = p.read_text(encoding="utf-8")
            import json
            package_data = json.loads(data)
        except Exception as e:
            return ValidationResult2(valid=False, errors=[{"path": str(path), "message": str(e), "code": "parse_error"}])

        result = validate_package(package_data)
        return ValidationResult2(
            valid=result.ok,
            errors=[e.to_dict() for e in result.errors()],
        )

    def plan(self, path: pathlib.Path | str) -> PlanResult:
        """Import assets and generate a materialization plan without executing."""
        p = pathlib.Path(path)
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"

        if not p.exists():
            return PlanResult(plan_id=plan_id, error="File not found")

        try:
            import json
            data = json.loads(p.read_text(encoding="utf-8"))
            package = VideoExecutionPackage.from_dict(data)
        except Exception as e:
            return PlanResult(plan_id=plan_id, error=str(e))

        pkg_hash = hash_value(package.to_dict())

        try:
            mat = materialize(
                run_id=plan_id,
                package=package,
                package_hash=pkg_hash,
                registry=self.registry,
            )
        except MaterializationError as e:
            return PlanResult(plan_id=plan_id, error=e.message, warnings=e.details)

        clip_plans = []
        for clip in mat.clips:
            clip_plans.append({
                "clip_id": clip.clip_id,
                "operation": clip.operation,
                "backend_id": clip.backend_id,
                "backend_revision": clip.backend_revision,
                "workflow_hash": clip.workflow_hash,
                "duration_ms": clip.duration_ms,
                "reference_count": len(clip.resolved_references),
            })

        backends = [
            {"backend_id": c.backend_id, "revision": c.backend_revision}
            for c in mat.clips
        ]

        return PlanResult(
            plan_id=plan_id,
            clip_plans=clip_plans,
            warnings=mat.warnings,
            backend_summary=backends,
        )

    def execute(
        self,
        path: pathlib.Path | str,
        approval: bool = False,
    ) -> RunResult:
        """Create or restore a Run from a package file."""
        p = pathlib.Path(path)
        if not p.exists():
            return RunResult(run_id="", status="FAILED", error="File not found")

        try:
            import json
            data = json.loads(p.read_text(encoding="utf-8"))
            package = VideoExecutionPackage.from_dict(data)
        except Exception as e:
            return RunResult(run_id="", status="FAILED", error=str(e))

        pkg_hash = hash_value(package.to_dict())
        run_id = f"run-{uuid.uuid4().hex[:12]}"

        try:
            mat = materialize(
                run_id=run_id,
                package=package,
                package_hash=pkg_hash,
                registry=self.registry,
            )
        except MaterializationError as e:
            return RunResult(run_id=run_id, status="FAILED", error=e.message)

        # Build DAG and run
        graph = build_dag(mat)
        rt = Runtime(default_fake_registry())
        rt.load_graph(graph)

        max_ticks = 100
        ticks = 0
        while not rt.is_complete() and ticks < max_ticks:
            rt.tick()
            ticks += 1

        # Store run state
        self._runs[run_id] = {
            "graph": graph,
            "runtime": rt,
            "materialization": mat,
            "status": "COMPLETED" if not rt.has_failures() else "FAILED",
        }

        return RunResult(
            run_id=run_id,
            status=self._runs[run_id]["status"],
            clip_count=len(mat.clips),
        )

    def status(self, run_id: str) -> StatusResult:
        """Get the status of a run."""
        run = self._runs.get(run_id)
        if run is None:
            return StatusResult(run_id=run_id, status="UNKNOWN", error="Run not found")
        rt = run["runtime"]
        tasks = {tid: t.status for tid, t in rt.tasks.items()}
        return StatusResult(
            run_id=run_id,
            status=run["status"],
            tasks=tasks,
        )

    def retry(self, run_id: str, scope: str | None = None) -> RunResult:
        """Retry a failed run or a specific clip."""
        run = self._runs.get(run_id)
        if run is None:
            return RunResult(run_id=run_id, status="FAILED", error="Run not found")

        rt = run["runtime"]
        reset_count = rt.reset_retryable()
        if reset_count == 0:
            return RunResult(run_id=run_id, status=run["status"], error="No retryable tasks")

        # Re-tick
        max_ticks = 100
        ticks = 0
        while not rt.is_complete() and ticks < max_ticks:
            rt.tick()
            ticks += 1

        run["status"] = "COMPLETED" if not rt.has_failures() else "FAILED"
        return RunResult(
            run_id=run_id,
            status=run["status"],
            clip_count=len(run["materialization"].clips),
        )

    def cancel(self, run_id: str) -> None:
        """Cancel a run."""
        run = self._runs.get(run_id)
        if run is None:
            return
        run["status"] = "CANCELLED"

    def review(self, run_id: str, target: str, decision: str) -> ReviewResult:
        """Submit a review decision."""
        review_id = f"rev-{uuid.uuid4().hex[:8]}"
        if decision not in ("approved", "rejected"):
            return ReviewResult(review_id=review_id, decision=decision, error="Invalid decision")
        return ReviewResult(review_id=review_id, decision=decision)

    def export(self, run_id: str) -> ExportResult2:
        """Export a completed run."""
        run = self._runs.get(run_id)
        if run is None:
            return ExportResult2(export_id="", status="FAILED", error="Run not found")
        if run["status"] != "COMPLETED":
            return ExportResult2(export_id="", status="FAILED", error=f"Run is {run['status']}")
        export_id = f"exp-{uuid.uuid4().hex[:8]}"
        return ExportResult2(export_id=export_id, status="READY", file_path=f"/tmp/{run_id}.mp4")
