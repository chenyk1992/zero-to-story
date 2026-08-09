"""Runtime scheduler — the core execution loop.

Finds READY tasks, acquires leases, creates attempts, dispatches to
handlers, and advances downstream tasks on success.
"""
from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

from lfo.execution.dag import TaskGraph
from lfo.execution.handlers import HandlerRegistry, HandlerResult
from lfo.execution.states import (
    AttemptState,
    TaskState,
    TransitionResult,
    is_valid_attempt_transition,
    is_valid_task_transition,
)


# ===========================================================================
# In-memory runtime state (for testing without SQLite)
# ===========================================================================

@dataclass
class RuntimeTask:
    """Mutable task state during execution."""

    task_id: str
    task_type: str
    logical_key: str
    status: str = TaskState.BLOCKED.value
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    attempt_ids: list[str] = field(default_factory=list)
    latest_attempt_id: str | None = None
    error: str | None = None
    retry_count: int = 0


@dataclass
class RuntimeAttempt:
    """Mutable attempt state during execution."""

    attempt_id: str
    task_id: str
    status: str = AttemptState.CREATED.value
    error: str | None = None
    artifact_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TickResult:
    """Result of a single scheduler tick."""

    tasks_processed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    tasks_advanced: int = 0
    errors: list[str] = field(default_factory=list)


class Runtime:
    """In-memory runtime scheduler for testing.

    In production this would use ExecutionStore for persistence, but the
    logic is identical: find READY tasks, acquire lease, create attempt,
    dispatch, advance.
    """

    def __init__(
        self,
        handler_registry: HandlerRegistry,
        max_retries: int = 3,
        lease_ttl_seconds: int = 300,
    ) -> None:
        self.handlers = handler_registry
        self.max_retries = max_retries
        self.lease_ttl_seconds = lease_ttl_seconds
        self.tasks: dict[str, RuntimeTask] = {}
        self.attempts: dict[str, RuntimeAttempt] = {}
        self._worker_id = f"worker-{uuid.uuid4().hex[:8]}"

    def load_graph(self, graph: TaskGraph) -> None:
        """Load a task graph into the runtime."""
        self.tasks.clear()
        for node in graph.tasks:
            self.tasks[node.task_id] = RuntimeTask(
                task_id=node.task_id,
                task_type=node.task_type,
                logical_key=node.logical_key,
                status=TaskState.BLOCKED.value if node.dependencies else TaskState.READY.value,
                dependencies=list(node.dependencies),
                metadata=dict(node.metadata),
            )

    def find_ready_tasks(self) -> list[RuntimeTask]:
        """Find tasks that are in READY state."""
        return [t for t in self.tasks.values() if t.status == TaskState.READY.value]

    def find_blocked_tasks(self) -> list[RuntimeTask]:
        """Find tasks that are in BLOCKED state."""
        return [t for t in self.tasks.values() if t.status == TaskState.BLOCKED.value]

    def acquire_lease(self, task_id: str) -> bool:
        """Acquire a lease for a task. Returns True if successful.

        In this in-memory implementation, we simply check the task is
        still in READY state. The real implementation uses task_leases
        table with CAS.
        """
        task = self.tasks.get(task_id)
        if task is None:
            return False
        if task.status != TaskState.READY.value:
            return False
        # Mark as RUNNING to prevent double-acquire
        task.status = TaskState.RUNNING.value
        return True

    def create_attempt(self, task_id: str) -> str:
        """Create a new attempt for a task. Returns attempt_id."""
        attempt_id = f"att-{uuid.uuid4().hex[:12]}"
        attempt = RuntimeAttempt(attempt_id=attempt_id, task_id=task_id)
        self.attempts[attempt_id] = attempt
        task = self.tasks[task_id]
        task.attempt_ids.append(attempt_id)
        task.latest_attempt_id = attempt_id
        return attempt_id

    def dispatch(self, task_id: str, attempt_id: str) -> HandlerResult:
        """Dispatch a task attempt to its handler."""
        task = self.tasks[task_id]
        handler = self.handlers.get(task.task_type)
        if handler is None:
            return HandlerResult(
                success=False,
                error=f"No handler for task type {task.task_type}",
                retryable=True,
            )
        return handler.execute(
            task_id=task_id,
            task_type=task.task_type,
            logical_key=task.logical_key,
            metadata=task.metadata,
            attempt_id=attempt_id,
        )

    def handle_success(
        self,
        task_id: str,
        attempt_id: str,
        result: HandlerResult,
    ) -> list[str]:
        """Handle a successful task execution.

        Returns the list of task_ids that were advanced from BLOCKED to READY.
        """
        task = self.tasks[task_id]
        attempt = self.attempts[attempt_id]
        attempt.status = AttemptState.SUCCEEDED.value
        if result.artifact_metadata:
            attempt.artifact_metadata = result.artifact_metadata

        task.status = TaskState.SUCCEEDED.value
        task.error = None

        # Advance downstream tasks
        return self._advance_downstream(task_id)

    def handle_failure(
        self,
        task_id: str,
        attempt_id: str,
        result: HandlerResult,
    ) -> None:
        """Handle a failed task execution."""
        task = self.tasks[task_id]
        attempt = self.attempts[attempt_id]
        attempt.status = AttemptState.FAILED.value
        attempt.error = result.error
        task.error = result.error
        task.retry_count += 1

        if not result.retryable or task.retry_count > self.max_retries:
            task.status = TaskState.FAILED_TERMINAL.value
        else:
            task.status = TaskState.FAILED_RETRYABLE.value

    def retry(self, task_id: str) -> bool:
        """Manually retry a FAILED_RETRYABLE task — reset to READY."""
        task = self.tasks.get(task_id)
        if task is None:
            return False
        if task.status != TaskState.FAILED_RETRYABLE.value:
            return False
        task.status = TaskState.READY.value
        return True

    def _advance_downstream(self, completed_task_id: str) -> list[str]:
        """Check if any BLOCKED tasks can now become READY.

        A task becomes READY when all its dependencies are SUCCEEDED.
        """
        advanced: list[str] = []
        for task in self.tasks.values():
            if task.status != TaskState.BLOCKED.value:
                continue
            if all(
                self.tasks[dep_id].status == TaskState.SUCCEEDED.value
                for dep_id in task.dependencies
                if dep_id in self.tasks
            ):
                task.status = TaskState.READY.value
                advanced.append(task.task_id)
        return advanced

    def tick(self) -> TickResult:
        """Run one scheduling cycle: find READY tasks, execute them.

        This is a simplified synchronous tick for testing. A real
        implementation would be async with lease timeouts.
        """
        result = TickResult()
        ready = self.find_ready_tasks()
        result.tasks_processed = len(ready)

        for task in ready:
            if not self.acquire_lease(task.task_id):
                continue
            attempt_id = self.create_attempt(task.task_id)
            handler_result = self.dispatch(task.task_id, attempt_id)

            if handler_result.success:
                advanced = self.handle_success(task.task_id, attempt_id, handler_result)
                result.tasks_succeeded += 1
                result.tasks_advanced += len(advanced)
            else:
                self.handle_failure(task.task_id, attempt_id, handler_result)
                result.tasks_failed += 1

        return result

    def is_complete(self) -> bool:
        """Check if all tasks are in a terminal state."""
        from lfo.execution.states import TASK_TERMINAL_STATES
        return all(t.status in {s.value for s in TASK_TERMINAL_STATES} for t in self.tasks.values())

    def has_failures(self) -> bool:
        """Check if any task has FAILED_TERMINAL."""
        return any(t.status == TaskState.FAILED_TERMINAL.value for t in self.tasks.values())

    def reset_retryable(self) -> int:
        """Reset all FAILED_RETRYABLE tasks to READY. Returns count."""
        count = 0
        for task in self.tasks.values():
            if task.status == TaskState.FAILED_RETRYABLE.value:
                task.status = TaskState.READY.value
                count += 1
        return count
