"""Wave 2-C: Retry & Remediation.

RetryPolicy: defines retry rules (max attempts, backoff, transient vs persistent).
RemediationPlanner: decides retry strategy based on failure classification.
RetryBudget: caps total retries per project/task.
AttemptSelection: picks the best attempt for re-execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lfo.core.state_machine import FailureClassification


@dataclass
class RetryPolicy:
    """Defines how many times and under what conditions a task can be retried."""

    max_attempts: int = 3
    max_transient_retries: int = 2
    max_persistent_retries: int = 1
    backoff_base_sec: float = 1.0
    backoff_max_sec: float = 60.0
    backoff_multiplier: float = 2.0

    def should_retry_transient(self, attempt_count: int) -> bool:
        """Can we retry with the same contract (same idempotency_key)?"""
        return attempt_count < self.max_transient_retries

    def should_retry_persistent(self, persistent_count: int) -> bool:
        """Can we retry with a modified contract (new idempotency_key)?"""
        return persistent_count < self.max_persistent_retries

    def should_retry(self, attempt_count: int) -> bool:
        """General retry gate."""
        return attempt_count < self.max_attempts

    def backoff_delay(self, attempt_index: int) -> float:
        """Exponential backoff with cap."""
        delay = self.backoff_base_sec * (self.backoff_multiplier ** attempt_index)
        return min(delay, self.backoff_max_sec)


@dataclass
class RetryBudget:
    """Caps total retries to prevent runaway loops."""

    max_retries_per_task: int = 5
    max_retries_per_project: int = 50
    _project_counts: dict[str, int] = field(default_factory=dict)

    def can_retry_task(self, task_id: str, current_attempts: int) -> bool:
        """Check if this task has budget left."""
        return current_attempts < self.max_retries_per_task

    def can_retry_project(self, project_id: str) -> bool:
        """Check if the project has budget left."""
        return self._project_counts.get(project_id, 0) < self.max_retries_per_project

    def record_retry(self, project_id: str) -> None:
        """Consume one retry from the project budget."""
        self._project_counts[project_id] = self._project_counts.get(project_id, 0) + 1

    def remaining_project_retries(self, project_id: str) -> int:
        return max(0, self.max_retries_per_project - self._project_counts.get(project_id, 0))


@dataclass
class RemediationAction:
    """A planned retry action."""

    action_type: str  # 'retry_transient' | 'retry_persistent' | 'fail_terminal'
    reason: str
    new_params: dict | None = None  # modified params for persistent retry
    delay_sec: float = 0.0


class RemediationPlanner:
    """Decides retry strategy based on failure classification."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        budget: RetryBudget | None = None,
    ) -> None:
        self.policy = policy or RetryPolicy()
        self.budget = budget or RetryBudget()

    def plan(
        self,
        task_id: str,
        project_id: str,
        failure_classification: FailureClassification,
        attempt_count: int,
        persistent_retry_count: int = 0,
        error_message: str = "",
    ) -> RemediationAction:
        """Decide what to do next after a failure."""

        # Check budget first
        if not self.budget.can_retry_project(project_id):
            return RemediationAction(
                action_type="fail_terminal",
                reason="Project retry budget exhausted",
            )

        if not self.budget.can_retry_task(task_id, attempt_count):
            return RemediationAction(
                action_type="fail_terminal",
                reason=f"Task retry budget exhausted ({attempt_count} attempts)",
            )

        if failure_classification == FailureClassification.TRANSIENT:
            return self._plan_transient(task_id, project_id, attempt_count, error_message)
        elif failure_classification == FailureClassification.PERSISTENT:
            return self._plan_persistent(task_id, project_id, attempt_count, persistent_retry_count, error_message)
        else:
            return RemediationAction(
                action_type="fail_terminal",
                reason=f"Failure classified as {failure_classification.value}: {error_message}",
            )

    def _plan_transient(
        self,
        task_id: str,
        project_id: str,
        attempt_count: int,
        error_message: str,
    ) -> RemediationAction:
        if not self.policy.should_retry_transient(attempt_count):
            return RemediationAction(
                action_type="fail_terminal",
                reason=f"Transient retry limit reached ({attempt_count}/{self.policy.max_transient_retries})",
            )

        delay = self.policy.backoff_delay(attempt_count)
        self.budget.record_retry(project_id)
        return RemediationAction(
            action_type="retry_transient",
            reason=f"Transient failure (attempt {attempt_count}): {error_message}",
            delay_sec=delay,
        )

    def _plan_persistent(
        self,
        task_id: str,
        project_id: str,
        attempt_count: int,
        persistent_retry_count: int,
        error_message: str,
    ) -> RemediationAction:
        if not self.policy.should_retry_persistent(persistent_retry_count):
            return RemediationAction(
                action_type="fail_terminal",
                reason=f"Persistent retry limit reached ({persistent_retry_count}/{self.policy.max_persistent_retries})",
            )

        delay = self.policy.backoff_delay(persistent_retry_count)
        self.budget.record_retry(project_id)
        return RemediationAction(
            action_type="retry_persistent",
            reason=f"Persistent failure (retry {persistent_retry_count}): {error_message}",
            new_params={"_retry_reason": error_message, "_retry_index": persistent_retry_count},
            delay_sec=delay,
        )


def classify_failure(error_message: str) -> FailureClassification:
    """Classify a failure based on error message heuristics."""
    error_lower = error_message.lower()

    # Transient: network, timeout, resource temporarily unavailable
    transient_keywords = [
        "timeout", "connection", "unavailable", "rate limit", "429", "503",
        "temporarily", "retry", "econnreset", "socket", "websocket",
    ]
    for kw in transient_keywords:
        if kw in error_lower:
            return FailureClassification.TRANSIENT

    # Exhausted: quota, disk space, out of memory
    exhausted_keywords = [
        "quota", "disk space", "out of memory", "oom", "no space",
        "forbidden", "unauthorized", "403", "401",
    ]
    for kw in exhausted_keywords:
        if kw in error_lower:
            return FailureClassification.EXHAUSTED

    # Default: persistent (needs contract change)
    return FailureClassification.PERSISTENT
