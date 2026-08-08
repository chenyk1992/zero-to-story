"""Tests for Wave 2-C: Retry & Remediation."""
from __future__ import annotations

from lfo.core.retry import (
    RemediationPlanner,
    RetryBudget,
    RetryPolicy,
    classify_failure,
)
from lfo.core.state_machine import FailureClassification


class TestRetryPolicy:
    def test_should_retry_transient_within_limit(self):
        policy = RetryPolicy(max_transient_retries=3)
        assert policy.should_retry_transient(0) is True
        assert policy.should_retry_transient(2) is True
        assert policy.should_retry_transient(3) is False

    def test_should_retry_persistent_within_limit(self):
        policy = RetryPolicy(max_persistent_retries=2)
        assert policy.should_retry_persistent(0) is True
        assert policy.should_retry_persistent(1) is True
        assert policy.should_retry_persistent(2) is False

    def test_backoff_exponential(self):
        policy = RetryPolicy(backoff_base_sec=1.0, backoff_multiplier=2.0, backoff_max_sec=60.0)
        assert policy.backoff_delay(0) == 1.0
        assert policy.backoff_delay(1) == 2.0
        assert policy.backoff_delay(2) == 4.0
        assert policy.backoff_delay(3) == 8.0

    def test_backoff_capped(self):
        policy = RetryPolicy(backoff_base_sec=1.0, backoff_multiplier=10.0, backoff_max_sec=50.0)
        assert policy.backoff_delay(0) == 1.0
        assert policy.backoff_delay(1) == 10.0
        assert policy.backoff_delay(2) == 50.0  # capped
        assert policy.backoff_delay(3) == 50.0

    def test_should_retry_general(self):
        policy = RetryPolicy(max_attempts=3)
        assert policy.should_retry(0) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is False


class TestRetryBudget:
    def test_can_retry_task_within_limit(self):
        budget = RetryBudget(max_retries_per_task=3)
        assert budget.can_retry_task("t1", 0) is True
        assert budget.can_retry_task("t1", 2) is True
        assert budget.can_retry_task("t1", 3) is False

    def test_can_retry_project_within_limit(self):
        budget = RetryBudget(max_retries_per_project=5)
        assert budget.can_retry_project("p1") is True
        for _ in range(5):
            budget.record_retry("p1")
        assert budget.can_retry_project("p1") is False

    def test_remaining_project_retries(self):
        budget = RetryBudget(max_retries_per_project=10)
        assert budget.remaining_project_retries("p1") == 10
        budget.record_retry("p1")
        budget.record_retry("p1")
        assert budget.remaining_project_retries("p1") == 8


class TestRemediationPlanner:
    def test_transient_retry_approved(self):
        planner = RemediationPlanner()
        action = planner.plan(
            task_id="t1", project_id="p1",
            failure_classification=FailureClassification.TRANSIENT,
            attempt_count=0,
            error_message="Connection timeout",
        )
        assert action.action_type == "retry_transient"
        assert action.delay_sec > 0

    def test_transient_retry_exhausted(self):
        policy = RetryPolicy(max_transient_retries=2)
        planner = RemediationPlanner(policy=policy)
        action = planner.plan(
            task_id="t1", project_id="p1",
            failure_classification=FailureClassification.TRANSIENT,
            attempt_count=2,
            error_message="Timeout",
        )
        assert action.action_type == "fail_terminal"

    def test_persistent_retry_approved(self):
        planner = RemediationPlanner()
        action = planner.plan(
            task_id="t1", project_id="p1",
            failure_classification=FailureClassification.PERSISTENT,
            attempt_count=0,
            persistent_retry_count=0,
            error_message="Asset not found",
        )
        assert action.action_type == "retry_persistent"
        assert action.new_params is not None

    def test_persistent_retry_exhausted(self):
        policy = RetryPolicy(max_persistent_retries=1)
        planner = RemediationPlanner(policy=policy)
        action = planner.plan(
            task_id="t1", project_id="p1",
            failure_classification=FailureClassification.PERSISTENT,
            attempt_count=1,
            persistent_retry_count=1,
            error_message="Asset not found",
        )
        assert action.action_type == "fail_terminal"

    def test_exhausted_fails_immediately(self):
        planner = RemediationPlanner()
        action = planner.plan(
            task_id="t1", project_id="p1",
            failure_classification=FailureClassification.EXHAUSTED,
            attempt_count=0,
            error_message="Out of disk space",
        )
        assert action.action_type == "fail_terminal"

    def test_budget_exhaustion(self):
        budget = RetryBudget(max_retries_per_project=1)
        planner = RemediationPlanner(budget=budget)
        # First retry consumes budget
        action1 = planner.plan(
            task_id="t1", project_id="p1",
            failure_classification=FailureClassification.TRANSIENT,
            attempt_count=0,
            error_message="Timeout",
        )
        assert action1.action_type == "retry_transient"
        # Second retry: budget exhausted
        action2 = planner.plan(
            task_id="t2", project_id="p1",
            failure_classification=FailureClassification.TRANSIENT,
            attempt_count=0,
            error_message="Timeout",
        )
        assert action2.action_type == "fail_terminal"


class TestClassifyFailure:
    def test_transient_keywords(self):
        assert classify_failure("Connection timeout") == FailureClassification.TRANSIENT
        assert classify_failure("Rate limit exceeded") == FailureClassification.TRANSIENT
        assert classify_failure("WebSocket disconnected") == FailureClassification.TRANSIENT
        assert classify_failure("503 Service Unavailable") == FailureClassification.TRANSIENT

    def test_exhausted_keywords(self):
        assert classify_failure("Out of disk space") == FailureClassification.EXHAUSTED
        assert classify_failure("Quota exceeded") == FailureClassification.EXHAUSTED
        assert classify_failure("Out of memory") == FailureClassification.EXHAUSTED

    def test_persistent_default(self):
        assert classify_failure("Asset not found") == FailureClassification.PERSISTENT
        assert classify_failure("Unknown error") == FailureClassification.PERSISTENT
