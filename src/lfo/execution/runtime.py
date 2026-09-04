"""Runtime scheduler — the core execution loop.

Finds READY tasks, acquires leases, creates attempts, dispatches to
handlers, and advances downstream tasks on success.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from lfo.execution import ExecutionStore
from lfo.execution.dag import TaskGraph
from lfo.execution.handlers import RECOVERY_ACTIONS, HandlerRegistry, HandlerResult
from lfo.execution.states import (
    AttemptState,
    TaskState,
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
        self.artifacts_by_task: dict[str, dict[str, Any]] = {}
        self._worker_id = f"worker-{uuid.uuid4().hex[:8]}"

    def load_graph(self, graph: TaskGraph) -> None:
        """Load a task graph into the runtime."""
        graph.validate()
        self.tasks.clear()
        self.attempts.clear()
        self.artifacts_by_task.clear()
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
                retryable=False,
                failure_class="creative_input",
                recovery_action="block_for_user",
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
        if result.artifact_metadata:
            self.artifacts_by_task[task_id] = dict(result.artifact_metadata)

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
        recovery_action = result.recovery_action
        if recovery_action is not None and recovery_action not in RECOVERY_ACTIONS:
            # Do not let an extension invent a new retry route after the
            # production lock.  Unknown actions fail closed and remain
            # visible in the report for the operator/Skill to correct.
            task.metadata["requested_recovery_action"] = recovery_action
            recovery_action = "block_for_user"
        if result.error:
            task.metadata["last_failure"] = result.error
        if result.artifact_metadata:
            # Preserve objective QC evidence even when the handler rejects
            # the artifact.  It is kept in task metadata so the persistent
            # report can show why a prompt rewrite or retry was requested.
            task.metadata["failure_evidence"] = dict(result.artifact_metadata)
        if result.failure_class is not None:
            task.metadata["failure_class"] = result.failure_class
        if recovery_action is not None:
            task.metadata["recovery_action"] = recovery_action

        if recovery_action == "rewrite_prompt":
            # A content/audio/boundary verdict pauses the exact Clip's
            # generation task and requests a new H3 prompt revision.  If the
            # failing task is downstream (for example audio.mix), it is kept
            # retryable while the generation task becomes the single waiting
            # gate.  No downstream task can publish a tail frame while the
            # prompt is waiting, and no storyboard mutation is possible here.
            target = self._prompt_revision_target(task)
            if target is None:
                task.status = TaskState.FAILED_TERMINAL.value
                task.metadata["failure_class"] = result.failure_class or "user_attention"
                task.metadata["recovery_action"] = "block_for_user"
                task.metadata["last_failure"] = result.error
                task.metadata["prompt_revision_required"] = False
            else:
                task.metadata["prompt_revision_task_id"] = target.task_id
                target.status = TaskState.WAITING_PROMPT_REVISION.value
                if target is not task:
                    task.status = TaskState.FAILED_RETRYABLE.value
                target.metadata["failure_class"] = result.failure_class or "generation_quality"
                target.metadata["recovery_action"] = "rewrite_prompt"
                target.metadata["last_failure"] = result.error
                target.metadata["prompt_revision_required"] = True
                if result.artifact_metadata:
                    target.metadata["failure_evidence"] = dict(result.artifact_metadata)
                target.error = result.error
        elif recovery_action == "block_for_user":
            task.status = TaskState.FAILED_TERMINAL.value
            task.metadata["failure_class"] = result.failure_class or "user_attention"
            task.metadata["recovery_action"] = "block_for_user"
        elif not result.retryable or task.retry_count > self.max_retries:
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
        # A prompt-quality/audio verdict is a creative correction point, not
        # a transient backend failure.  Re-running the same downstream task
        # would reuse the same generated media and usually reproduce the same
        # defect; the only permitted recovery is the prompt-revision route.
        if task.metadata.get("recovery_action") == "rewrite_prompt":
            return False
        task.status = TaskState.READY.value
        # Populate input_artifacts from dependencies so downstream handlers
        # (the generation gate and audio.mix) receive their upstream file_path.
        task.metadata["input_artifacts"] = {
            dep_id: dict(self.artifacts_by_task.get(dep_id, {}))
            for dep_id in task.dependencies
        }
        return True

    def _prompt_revision_target(self, task: RuntimeTask) -> RuntimeTask | None:
        """Resolve the generation task that owns a Clip's prompt.

        Audio, generation-gate and optional upscale failures all point back to
        this task through DAG metadata.  Keeping the route here prevents a
        prompt revision from being accidentally applied to an audio or global
        assembly task.
        """

        candidate_id = task.metadata.get("generation_task_id")
        if isinstance(candidate_id, str):
            candidate = self.tasks.get(candidate_id)
            if candidate is not None and candidate.task_type == "video.generate":
                if (
                    candidate.status not in {
                        TaskState.FAILED_TERMINAL.value,
                        TaskState.CANCELLED.value,
                    }
                    and isinstance(candidate.metadata.get("production_lock"), dict)
                    and candidate.metadata["production_lock"].get("status") == "LOCKED"
                ):
                    return candidate
                return None
        if task.task_type == "video.generate":
            if (
                task.status not in {
                    TaskState.FAILED_TERMINAL.value,
                    TaskState.CANCELLED.value,
                }
                and isinstance(task.metadata.get("production_lock"), dict)
                and task.metadata["production_lock"].get("status") == "LOCKED"
            ):
                return task
            return None
        clip_id = task.metadata.get("clip_id")
        if isinstance(clip_id, str) and clip_id:
            for candidate in self.tasks.values():
                if (
                    candidate.task_type == "video.generate"
                    and candidate.metadata.get("clip_id") == clip_id
                    and candidate.status not in {
                        TaskState.FAILED_TERMINAL.value,
                        TaskState.CANCELLED.value,
                    }
                    and isinstance(candidate.metadata.get("production_lock"), dict)
                    and candidate.metadata["production_lock"].get("status") == "LOCKED"
                ):
                    return candidate
        return None

    def _reset_clip_for_prompt_revision(self, target: RuntimeTask) -> None:
        """Invalidate all outputs downstream of a revised generation task.

        A prompt rewrite changes the generated video, so every derived
        artifact (upscale, generation gate, audio mix, boundary evidence,
        timeline and export) must be recomputed.  The dependency walk also
        reaches later Clips that consume this Clip's tail frame.  Subtitle
        rendering is deliberately preserved because it is compiled solely
        from the locked subtitle cues and does not read the generated video.
        No plan field is changed by this invalidation.
        """

        reverse: dict[str, list[str]] = {task_id: [] for task_id in self.tasks}
        for task in self.tasks.values():
            for dependency in task.dependencies:
                if dependency in reverse:
                    reverse[dependency].append(task.task_id)

        descendants: list[RuntimeTask] = []
        queue = list(reverse.get(target.task_id, []))
        seen: set[str] = set()
        while queue:
            task_id = queue.pop(0)
            if task_id in seen:
                continue
            seen.add(task_id)
            descendant = self.tasks.get(task_id)
            if descendant is None:
                continue
            descendants.append(descendant)
            queue.extend(reverse.get(task_id, []))

        for descendant in descendants:
            if descendant.task_type == "subtitle.render":
                # Subtitles are an immutable text sidecar/burn-in input.  If
                # they have not run yet, their existing BLOCKED dependency
                # will be advanced after the new generation gate succeeds.
                continue
            if descendant.status in {
                TaskState.FAILED_TERMINAL.value,
                TaskState.CANCELLED.value,
            }:
                continue
            descendant.status = TaskState.BLOCKED.value
            descendant.error = None
            descendant.metadata.pop("prompt_revision_required", None)
            descendant.metadata.pop("failure_class", None)
            descendant.metadata.pop("recovery_action", None)
            descendant.metadata.pop("last_failure", None)
            descendant.metadata.pop("failure_evidence", None)
            descendant.metadata["input_artifacts"] = {}
            self.artifacts_by_task.pop(descendant.task_id, None)

        target.status = TaskState.READY.value
        target.error = None
        target.metadata.pop("failure_evidence", None)
        self.artifacts_by_task.pop(target.task_id, None)
        target.metadata["input_artifacts"] = {
            dep_id: dict(self.artifacts_by_task.get(dep_id, {}))
            for dep_id in target.dependencies
        }

    def provide_prompt_revision(
        self,
        task_id: str,
        prompt: str,
        *,
        plan_hash: str | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> bool:
        """Apply one H3 prompt revision without changing the locked plan.

        The prompt is supplied by the creative ``h3-prompt-writing`` layer;
        LFO only checks the production-plan hash, revision budget and task
        state before making the clip READY again.
        """

        task = self.tasks.get(task_id)
        if task is None or task.status != TaskState.WAITING_PROMPT_REVISION.value:
            return False
        if not isinstance(prompt, str) or not prompt.strip():
            return False
        lock = task.metadata.get("production_lock")
        if not isinstance(lock, dict) or lock.get("status") != "LOCKED":
            return False
        expected_plan_hash = task.metadata.get("plan_hash")
        aggregate_plan_hash = task.metadata.get("aggregate_plan_hash")
        accepted_plan_hashes = {
            value
            for value in (expected_plan_hash, aggregate_plan_hash)
            if isinstance(value, str) and value
        }
        if not accepted_plan_hashes or plan_hash not in accepted_plan_hashes:
            return False
        # Validate all optional mutable fields before changing the prompt so a
        # malformed revision is rejected atomically.  The caller can safely
        # retry with corrected values without consuming the one revision slot
        # or leaving a half-applied prompt in durable metadata.
        if negative_prompt is not None and not isinstance(negative_prompt, str):
            return False
        if seed is not None and (
            not isinstance(seed, int) or isinstance(seed, bool)
        ):
            return False
        max_revisions = 1
        if isinstance(lock, dict):
            candidate = lock.get("max_prompt_revisions", 1)
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                max_revisions = candidate
        current = task.metadata.get("prompt_revision", 0)
        if not isinstance(current, int) or isinstance(current, bool) or current < 0:
            current = 0
        if current >= max_revisions:
            task.metadata["recovery_action"] = "block_for_user"
            task.metadata["failure_class"] = "prompt_revision_budget"
            task.metadata["prompt_revision_required"] = False
            task.status = TaskState.FAILED_TERMINAL.value
            task.error = "Prompt revision budget exhausted"
            return False

        # Preserve the complete H3 prompt byte-for-byte (including intentional
        # section newlines); only whitespace-only submissions are rejected.
        task.metadata["prompt"] = prompt
        task.metadata["prompt_hash"] = hashlib.sha256(
            task.metadata["prompt"].encode("utf-8")
        ).hexdigest()
        if negative_prompt is not None:
            task.metadata["negative_prompt"] = negative_prompt
        if seed is not None:
            task.metadata["seed"] = seed
        task.metadata["prompt_revision"] = current + 1
        task.metadata["prompt_revision_required"] = False
        task.metadata["recovery_action"] = "prompt_revision_applied"
        task.metadata["failure_class"] = None
        task.error = None
        self._reset_clip_for_prompt_revision(task)
        task.metadata["input_artifacts"] = {
            dep_id: dict(self.artifacts_by_task.get(dep_id, {}))
            for dep_id in task.dependencies
        }
        return True

    def _advance_downstream(self, completed_task_id: str) -> list[str]:
        """Check if any BLOCKED tasks can now become READY.

        A task becomes READY when all its dependencies are SUCCEEDED.
        """
        advanced: list[str] = []
        for task in self.tasks.values():
            if task.status != TaskState.BLOCKED.value:
                continue
            # A missing dependency is a graph integrity problem, never a
            # reason to treat the dependency set as empty.
            if all(
                dep_id in self.tasks
                and self.tasks[dep_id].status == TaskState.SUCCEEDED.value
                for dep_id in task.dependencies
            ):
                task.status = TaskState.READY.value
                task.metadata["input_artifacts"] = {
                    dep_id: dict(self.artifacts_by_task.get(dep_id, {}))
                    for dep_id in task.dependencies
                }
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

            # The generation-quality stage is a gate. A handler can execute
            # successfully while its verdict rejects the upstream artifact;
            # that must never be recorded as task success.
            if handler_result.success and not (
                task.task_type == "media.qc" and handler_result.qc_passed is False
            ):
                advanced = self.handle_success(task.task_id, attempt_id, handler_result)
                result.tasks_succeeded += 1
                result.tasks_advanced += len(advanced)
            else:
                if handler_result.success:
                    handler_result = HandlerResult(
                        success=False,
                        error=handler_result.error or "Generation quality gate failed",
                        retryable=False,
                        artifact_type=handler_result.artifact_type,
                        artifact_metadata=handler_result.artifact_metadata,
                        qc_passed=False,
                        failure_class=handler_result.failure_class or "execution_transient",
                        recovery_action=handler_result.recovery_action or "retry_same",
                    )
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
            if (
                task.status == TaskState.FAILED_RETRYABLE.value
                and task.metadata.get("recovery_action") != "rewrite_prompt"
            ):
                task.status = TaskState.READY.value
                count += 1
        return count

    def cancel(self, task_ids: list[str] | None = None) -> int:
        """Cancel executable tasks, optionally restricted to an explicit scope."""
        targets = task_ids if task_ids is not None else list(self.tasks)
        cancelled = 0
        for task_id in targets:
            task = self.tasks.get(task_id)
            if task is None or task.status in {
                TaskState.SUCCEEDED.value,
                TaskState.FAILED_TERMINAL.value,
                TaskState.CANCELLED.value,
            }:
                continue
            task.status = TaskState.CANCELLED.value
            cancelled += 1
        return cancelled

    def is_stalled(self) -> bool:
        """True when no work can progress but the runtime is not terminal."""
        return not self.is_complete() and not self.find_ready_tasks()


class PersistentRuntime(Runtime):
    """Runtime facade backed by :class:`ExecutionStore`.

    This keeps scheduling semantics identical to the in-memory Runtime while
    making task state, attempts and successful artifacts durable. A fresh
    process can call ``restore`` and continue the same run without relying on
    process-local dictionaries.
    """

    def __init__(self, store: ExecutionStore, handler_registry: HandlerRegistry,
                 run_id: str, max_retries: int = 3, lease_ttl_seconds: int = 300) -> None:
        super().__init__(handler_registry, max_retries, lease_ttl_seconds)
        self.store = store
        self.run_id = run_id
        self.store.init_schema()

    def load_graph(self, graph: TaskGraph, *, persist: bool = True) -> None:
        super().load_graph(graph)
        if persist:
            self.store.persist_tasks(self.run_id, graph.tasks)

    def restore(self) -> None:
        """Hydrate scheduler state and dependency metadata from persistent rows."""
        self.store.recover_interrupted_tasks(self.run_id)
        rows = self.store.list_tasks(self.run_id)
        conn = self.store.connect()
        self.tasks.clear()
        self.attempts.clear()
        self.artifacts_by_task.clear()
        for row in rows:
            deps = conn.execute(
                "SELECT depends_on FROM task_dependencies WHERE task_id=? ORDER BY depends_on",
                (row["task_id"],),
            ).fetchall()
            task_error = row.get("error")
            retry_count = row.get("retry_count")
            self.tasks[str(row["task_id"])] = RuntimeTask(
                task_id=str(row["task_id"]), task_type=str(row["task_type"]),
                logical_key=str(row["logical_key"]), status=str(row["status"]),
                dependencies=[str(dep["depends_on"]) for dep in deps],
                metadata=json.loads(str(row.get("metadata") or "{}")),
                error=task_error if isinstance(task_error, str) else None,
                retry_count=int(retry_count) if isinstance(retry_count, int | str) else 0,
            )
        for row in conn.execute(
            "SELECT * FROM attempts WHERE task_id IN (SELECT task_id FROM tasks WHERE run_id=?)", (self.run_id,)
        ).fetchall():
            attempt_error = row["error"]
            attempt = RuntimeAttempt(
                attempt_id=str(row["attempt_id"]), task_id=str(row["task_id"]),
                status=str(row["status"]),
                error=attempt_error if isinstance(attempt_error, str) else None,
            )
            self.attempts[attempt.attempt_id] = attempt
            task = self.tasks[attempt.task_id]
            task.attempt_ids.append(attempt.attempt_id)
            task.latest_attempt_id = attempt.attempt_id
        for row in conn.execute(
            "SELECT task_id, metadata FROM artifacts WHERE task_id IN (SELECT task_id FROM tasks WHERE run_id=?) ORDER BY created_at", (self.run_id,)
        ).fetchall():
            self.artifacts_by_task[str(row["task_id"])] = json.loads(str(row["metadata"]))

    def acquire_lease(self, task_id: str) -> bool:
        expires = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            seconds=self.lease_ttl_seconds
        )).strftime("%Y-%m-%dT%H:%M:%fZ")
        lease_id = self.store.acquire_task_lease(
            task_id=task_id, worker_id=self._worker_id, expires_at=expires,
        )
        if lease_id is None:
            return False
        task = self.tasks[task_id]
        task.status = TaskState.RUNNING.value
        task.metadata["lease_id"] = lease_id
        return True

    def create_attempt(self, task_id: str) -> str:
        attempt_id = super().create_attempt(task_id)
        task = self.tasks[task_id]
        self.store.create_attempt(
            attempt_id=attempt_id, task_id=task_id,
            idempotency_key=f"{self.run_id}:{task.logical_key}:{task.retry_count}",
        )
        return attempt_id

    def handle_success(self, task_id: str, attempt_id: str, result: HandlerResult) -> list[str]:
        advanced = super().handle_success(task_id, attempt_id, result)
        task = self.tasks[task_id]
        provider_job_id = result.artifact_metadata.get("provider_job_id")
        self.store.transition_attempt(
            attempt_id,
            "CREATED",
            "SUCCEEDED",
            "handler succeeded",
            provider_job_id=provider_job_id if isinstance(provider_job_id, str) else None,
        )
        self.store.transition_task(task_id, "RUNNING", "SUCCEEDED", "handler succeeded")
        if result.artifact_type:
            metadata = dict(result.artifact_metadata)
            self.store.record_artifact(
                artifact_id=f"artifact-{uuid.uuid4().hex}", task_id=task_id,
                attempt_id=attempt_id, artifact_type=result.artifact_type,
                file_path=metadata.get("file_path"), file_hash=metadata.get("file_hash"),
                media_type=metadata.get("media_type"), metadata=metadata,
            )
        for downstream_id in advanced:
            self.store.transition_task(downstream_id, "BLOCKED", "READY", "dependencies satisfied")
            self.store.update_task_metadata(downstream_id, self.tasks[downstream_id].metadata)
        lease_id = task.metadata.get("lease_id")
        if isinstance(lease_id, str):
            self.store.release_task_lease(lease_id)
        return advanced

    def handle_failure(self, task_id: str, attempt_id: str, result: HandlerResult) -> None:
        before_states, before_metadata = self._persisted_task_snapshot()
        super().handle_failure(task_id, attempt_id, result)
        provider_job_id = result.artifact_metadata.get("provider_job_id")
        self.store.transition_attempt(
            attempt_id,
            "CREATED",
            "FAILED",
            result.error,
            error=result.error,
            provider_job_id=provider_job_id if isinstance(provider_job_id, str) else None,
        )
        self.store.update_task_retry_count(
            task_id,
            self.tasks[task_id].retry_count,
        )
        self._persist_task_changes(
            before_states,
            before_metadata,
            reason="handler failure routed by recovery policy",
        )
        task = self.tasks[task_id]
        lease_id = task.metadata.get("lease_id")
        if isinstance(lease_id, str):
            self.store.release_task_lease(lease_id)

    def retry(self, task_id: str) -> bool:
        if not super().retry(task_id):
            return False
        self.store.transition_task(task_id, "FAILED_RETRYABLE", "READY", "manual retry")
        # Persist input_artifacts so subsequent retries see upstream artifacts
        self.store.update_task_metadata(task_id, self.tasks[task_id].metadata)
        return True

    def provide_prompt_revision(
        self,
        task_id: str,
        prompt: str,
        *,
        plan_hash: str | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> bool:
        before_states, before_metadata = self._persisted_task_snapshot()
        applied = super().provide_prompt_revision(
            task_id,
            prompt,
            plan_hash=plan_hash,
            negative_prompt=negative_prompt,
            seed=seed,
        )
        self._persist_task_changes(
            before_states,
            before_metadata,
            reason=(
                "approved prompt revision applied without changing locked plan"
                if applied
                else "prompt revision budget exhausted"
            ),
        )
        return applied

    def _persisted_task_snapshot(
        self,
    ) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        """Capture durable task state before an in-memory state mutation."""

        states: dict[str, str] = {}
        metadata: dict[str, dict[str, Any]] = {}
        for row in self.store.list_tasks(self.run_id):
            task_id = str(row["task_id"])
            states[task_id] = str(row["status"])
            try:
                value = json.loads(str(row.get("metadata") or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                value = {}
            metadata[task_id] = value if isinstance(value, dict) else {}
        return states, metadata

    def _persist_task_changes(
        self,
        before_states: dict[str, str],
        before_metadata: dict[str, dict[str, Any]],
        *,
        reason: str,
    ) -> None:
        """Persist every task changed by a recovery operation.

        Prompt revisions can move a successful generation task back to
        ``WAITING_PROMPT_REVISION`` and invalidate global descendants.  A
        single-task CAS update would leave those changes only in memory and a
        process restart could then resume from stale media.  Persist state and
        metadata together for every changed task instead.
        """

        for task_id, task in self.tasks.items():
            previous_state = before_states.get(task_id)
            if previous_state is None:
                continue
            if task.status != previous_state:
                self.store.transition_task(
                    task_id,
                    previous_state,
                    task.status,
                    reason,
                    error=task.error,
                )
            if task.metadata != before_metadata.get(task_id, {}):
                self.store.update_task_metadata(task_id, task.metadata)
