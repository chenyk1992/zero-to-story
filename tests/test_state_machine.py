"""Tests for the LFO state machine (TaskStatus, compute_project_state, etc.)."""

from lfo.core.state_machine import (
    TASK_ACTIVE_STATES,
    TASK_BLOCKING_STATES,
    TASK_TERMINAL_STATES,
    FailureClassification,
    SubmissionState,
    Task,
    TaskStatus,
    compute_project_state,
    merge_run_status,
)


def make_task(task_id: str, status: TaskStatus, **kwargs) -> Task:
    return Task(task_id=task_id, task_type="test", status=status, **kwargs)


class TestMergeRunStatus:
    def test_empty_tasks(self):
        assert merge_run_status([]) == "IDLE"

    def test_all_completed(self):
        tasks = [
            make_task("t1", TaskStatus.APPROVED),
            make_task("t2", TaskStatus.SUCCEEDED),
        ]
        assert merge_run_status(tasks) == "COMPLETED"

    def test_running_takes_precedence(self):
        tasks = [
            make_task("t1", TaskStatus.RUNNING),
            make_task("t2", TaskStatus.READY),
            make_task("t3", TaskStatus.APPROVED),
        ]
        assert merge_run_status(tasks) == "RUNNING"

    def test_waiting_user(self):
        tasks = [
            make_task("t1", TaskStatus.WAITING_USER),
            make_task("t2", TaskStatus.APPROVED),
        ]
        assert merge_run_status(tasks) == "WAITING_USER"

    def test_blocked(self):
        tasks = [
            make_task("t1", TaskStatus.FAILED_TERMINAL),
            make_task("t2", TaskStatus.APPROVED),
        ]
        assert merge_run_status(tasks) == "BLOCKED"

    def test_ready(self):
        tasks = [
            make_task("t1", TaskStatus.READY),
            make_task("t2", TaskStatus.APPROVED),
        ]
        assert merge_run_status(tasks) == "READY"

    def test_failed_retryable(self):
        tasks = [
            make_task("t1", TaskStatus.FAILED_RETRYABLE),
            make_task("t2", TaskStatus.APPROVED),
        ]
        assert merge_run_status(tasks) == "READY"


class TestComputeProjectState:
    def test_empty_project(self):
        state = compute_project_state([])
        assert state.run_status == "IDLE"
        assert state.attention_required is False

    def test_all_approved(self):
        tasks = [
            make_task("t1", TaskStatus.APPROVED),
            make_task("t2", TaskStatus.APPROVED),
        ]
        state = compute_project_state(tasks)
        assert state.run_status == "COMPLETED"
        assert state.attention_required is False

    def test_running_with_attention(self):
        tasks = [
            make_task("t1", TaskStatus.RUNNING),
            make_task("t2", TaskStatus.WAITING_USER),
            make_task("t3", TaskStatus.APPROVED),
        ]
        state = compute_project_state(tasks)
        assert state.run_status == "RUNNING"
        assert state.attention_required is True
        assert state.attention_count == 1
        assert "t2" in state.attention_scopes

    def test_blocked_project(self):
        tasks = [
            make_task("t1", TaskStatus.FAILED_TERMINAL),
            make_task("t2", TaskStatus.RUNNING),
        ]
        state = compute_project_state(tasks)
        assert state.run_status == "BLOCKED"

    def test_next_action(self):
        tasks = [make_task("t1", TaskStatus.WAITING_USER)]
        state = compute_project_state(tasks)
        assert state.next_action == "resolve_user_attention"

        tasks = [make_task("t1", TaskStatus.READY)]
        state = compute_project_state(tasks)
        assert state.next_action == "schedule_ready_tasks"


class TestTaskProperties:
    def test_terminal_states(self):
        assert make_task("t", TaskStatus.APPROVED).is_terminal is True
        assert make_task("t", TaskStatus.RUNNING).is_terminal is False

    def test_active_states(self):
        assert make_task("t", TaskStatus.RUNNING).is_active is True
        assert make_task("t", TaskStatus.QUEUED).is_active is True
        assert make_task("t", TaskStatus.READY).is_active is False

    def test_blocking_states(self):
        assert make_task("t", TaskStatus.WAITING_USER).blocks_downstream is True
        assert make_task("t", TaskStatus.FAILED_TERMINAL).blocks_downstream is True
        assert make_task("t", TaskStatus.RUNNING).blocks_downstream is False


class TestTaskStatusEnum:
    def test_values(self):
        assert TaskStatus.PLANNED.value == "PLANNED"
        assert TaskStatus.WAITING_USER.value == "WAITING_USER"
        assert SubmissionState.COMPLETED.value == "COMPLETED"
        assert FailureClassification.TRANSIENT.value == "transient"

    def test_waiting_assets_exists(self):
        assert TaskStatus.WAITING_ASSETS.value == "WAITING_ASSETS"

    def test_needs_rematerialization_exists(self):
        assert TaskStatus.NEEDS_REMATERIALIZATION.value == "NEEDS_REMATERIALIZATION"

    def test_waiting_assets_is_blocking(self):
        assert TaskStatus.WAITING_ASSETS in TASK_BLOCKING_STATES

    def test_needs_rematerialization_is_blocking(self):
        assert TaskStatus.NEEDS_REMATERIALIZATION in TASK_BLOCKING_STATES

    def test_waiting_assets_not_terminal(self):
        assert TaskStatus.WAITING_ASSETS not in TASK_TERMINAL_STATES

    def test_waiting_assets_not_active(self):
        assert TaskStatus.WAITING_ASSETS not in TASK_ACTIVE_STATES

    def test_waiting_assets_task_blocks_downstream(self):
        task = make_task("t1", TaskStatus.WAITING_ASSETS)
        assert task.blocks_downstream is True

    def test_needs_rematerialization_task_blocks_downstream(self):
        task = make_task("t1", TaskStatus.NEEDS_REMATERIALIZATION)
        assert task.blocks_downstream is True
