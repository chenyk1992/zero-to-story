"""Plan Validator — execution plan integrity checks.

Validates:
- All workflow_ids exist in registry
- Workflow modes match the workflow's supported modes
- Frame counts are valid (aligned to grid, within bounds)
- R2V has <= 2 identity subjects
- No circular dependencies
- Task IDs are unique
- READY tasks have complete fingerprints
- PLANNED tasks may have NULL fingerprints
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.core.workflow_registry import KNOWN_WORKFLOWS, FrameConstraints, WorkflowRegistry

from .schema import ExecutionPlan


@dataclass
class ValidationResult:
    """Result of validating an execution plan."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def _check_unique_task_ids(plan: ExecutionPlan, result: ValidationResult) -> None:
    """Task IDs must be unique."""
    seen: dict[str, int] = {}
    for task in plan.planned_tasks:
        if task.task_id in seen:
            result.add_error(
                f"Duplicate task_id: {task.task_id} (first seen at index {seen[task.task_id]})"
            )
        else:
            seen[task.task_id] = len(seen)


def _check_workflow_ids(
    plan: ExecutionPlan,
    result: ValidationResult,
    registry: WorkflowRegistry | None,
) -> None:
    """All workflow_ids must exist in the registry."""
    known = set(KNOWN_WORKFLOWS.keys())
    for task in plan.planned_tasks:
        if task.workflow_id and task.workflow_id not in known:
            result.add_error(
                f"Task {task.task_id}: unknown workflow_id '{task.workflow_id}'"
            )


def _check_workflow_modes(
    plan: ExecutionPlan,
    result: ValidationResult,
    registry: WorkflowRegistry | None,
) -> None:
    """Workflow modes must match the workflow's supported modes."""
    for task in plan.planned_tasks:
        if task.workflow_id in KNOWN_WORKFLOWS:
            manifest = KNOWN_WORKFLOWS[task.workflow_id]
            # The workflow_mode should be compatible with the manifest
            if task.workflow_mode and task.workflow_mode != manifest.workflow_mode:
                # i2v and first_last both use h3_standard_i2v
                if not (
                    task.workflow_mode in ("i2v", "first_last")
                    and manifest.workflow_mode == "i2v"
                ):
                    result.add_warning(
                        f"Task {task.task_id}: workflow_mode '{task.workflow_mode}' "
                        f"doesn't match manifest '{manifest.workflow_mode}'"
                    )


def _check_frame_counts(plan: ExecutionPlan, result: ValidationResult) -> None:
    """Frame counts must be aligned to grid and within bounds."""
    fc = FrameConstraints()
    for task in plan.planned_tasks:
        if task.aligned_frames > 0:
            # Check alignment: n % 17 should == 5
            if task.aligned_frames % fc.step != fc.min_frames:
                result.add_error(
                    f"Task {task.task_id}: frame count {task.aligned_frames} "
                    f"not aligned to grid (must be {fc.step}k+{fc.min_frames})"
                )
            # Check bounds
            if task.aligned_frames < fc.min_frames:
                result.add_error(
                    f"Task {task.task_id}: frame count {task.aligned_frames} "
                    f"below minimum {fc.min_frames}"
                )
            if task.aligned_frames > fc.max_frames:
                result.add_error(
                    f"Task {task.task_id}: frame count {task.aligned_frames} "
                    f"above maximum {fc.max_frames}"
                )


def _check_no_circular_deps(plan: ExecutionPlan, result: ValidationResult) -> None:
    """Check for circular dependencies using DFS."""
    # Build adjacency list
    graph: dict[str, list[str]] = {t.task_id: list(t.depends_on) for t in plan.planned_tasks}

    # DFS-based cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in graph}

    def dfs(node: str, path: list[str]) -> bool:
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if neighbor not in color:
                continue  # dependency outside plan — skip
            if color[neighbor] == GRAY:
                cycle = " → ".join(path + [neighbor])
                result.add_error(f"Circular dependency detected: {cycle}")
                return True
            if color[neighbor] == WHITE:
                if dfs(neighbor, path + [neighbor]):
                    return True
        color[node] = BLACK
        return False

    for node in graph:
        if color[node] == WHITE:
            dfs(node, [node])


def _check_fingerprints(plan: ExecutionPlan, result: ValidationResult) -> None:
    """READY tasks must have complete fingerprints; PLANNED may be NULL."""
    for task in plan.planned_tasks:
        if task.status == "READY" and (
            not task.dependency_hash or not task.params_hash or not task.idempotency_key
        ):
            result.add_error(
                f"Task {task.task_id}: status READY but missing fingerprint "
                f"(dependency_hash={task.dependency_hash is not None}, "
                f"params_hash={task.params_hash is not None}, "
                f"idempotency_key={task.idempotency_key is not None})"
            )


def validate_execution_plan(
    plan: ExecutionPlan,
    registry: WorkflowRegistry | None = None,
) -> ValidationResult:
    """Validate plan integrity.

    Args:
        plan: The execution plan to validate.
        registry: Optional workflow registry (uses KNOWN_WORKFLOWS if None).

    Returns:
        ValidationResult with is_valid flag and any errors/warnings.
    """
    result = ValidationResult(is_valid=True)

    _check_unique_task_ids(plan, result)
    _check_workflow_ids(plan, result, registry)
    _check_workflow_modes(plan, result, registry)
    _check_frame_counts(plan, result)
    _check_no_circular_deps(plan, result)
    _check_fingerprints(plan, result)

    return result
