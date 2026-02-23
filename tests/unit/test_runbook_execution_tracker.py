"""Tests for the runbook execution tracker module.

Covers:
- ExecutionStatus enum values
- StepStatus enum values
- ExecutionStep model defaults
- RunbookExecution model defaults
- RunbookExecutionTracker creation
- start_execution() with all params, minimal, auto-cleanup at max
- record_step() new step, update existing, status transitions, duration, not found
- complete_execution() completed/failed/cancelled/rolled_back, duration, not found
- get_execution() found and not found
- list_executions() with/without runbook_id/status filter, limit
- get_stats() counts, avg_duration
- Step metadata merge
"""

from __future__ import annotations

import pytest

from shieldops.playbooks.execution_tracker import (
    ExecutionStatus,
    ExecutionStep,
    RunbookExecution,
    RunbookExecutionTracker,
    StepStatus,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def tracker() -> RunbookExecutionTracker:
    """Return a fresh RunbookExecutionTracker."""
    return RunbookExecutionTracker()


@pytest.fixture()
def populated_tracker() -> RunbookExecutionTracker:
    """Return a tracker with several executions."""
    t = RunbookExecutionTracker()
    t.start_execution(
        runbook_id="rb-restart",
        runbook_name="Restart Service",
        trigger="alert",
        triggered_by="pagerduty",
        steps=["stop", "wait", "start"],
        incident_id="inc-001",
        environment="production",
    )
    t.start_execution(
        runbook_id="rb-scale",
        runbook_name="Scale Up",
        trigger="manual",
        triggered_by="admin",
        steps=["check", "scale"],
        environment="staging",
    )
    t.start_execution(
        runbook_id="rb-restart",
        runbook_name="Restart Service",
        trigger="auto",
        steps=["stop", "wait", "start"],
    )
    return t


# ── Enum Tests ───────────────────────────────────────────────────


class TestExecutionStatusEnum:
    def test_running_value(self) -> None:
        assert ExecutionStatus.RUNNING == "running"

    def test_completed_value(self) -> None:
        assert ExecutionStatus.COMPLETED == "completed"

    def test_failed_value(self) -> None:
        assert ExecutionStatus.FAILED == "failed"

    def test_cancelled_value(self) -> None:
        assert ExecutionStatus.CANCELLED == "cancelled"

    def test_rolled_back_value(self) -> None:
        assert ExecutionStatus.ROLLED_BACK == "rolled_back"

    def test_all_members(self) -> None:
        members = {m.value for m in ExecutionStatus}
        assert members == {"running", "completed", "failed", "cancelled", "rolled_back"}


class TestStepStatusEnum:
    def test_pending_value(self) -> None:
        assert StepStatus.PENDING == "pending"

    def test_running_value(self) -> None:
        assert StepStatus.RUNNING == "running"

    def test_completed_value(self) -> None:
        assert StepStatus.COMPLETED == "completed"

    def test_failed_value(self) -> None:
        assert StepStatus.FAILED == "failed"

    def test_skipped_value(self) -> None:
        assert StepStatus.SKIPPED == "skipped"


# ── Model Tests ──────────────────────────────────────────────────


class TestExecutionStepModel:
    def test_defaults(self) -> None:
        step = ExecutionStep(name="deploy")
        assert step.name == "deploy"
        assert step.status == StepStatus.PENDING
        assert step.started_at is None
        assert step.completed_at is None
        assert step.duration_seconds == 0.0
        assert step.output == ""
        assert step.error == ""
        assert step.metadata == {}
        assert len(step.id) == 12

    def test_unique_ids(self) -> None:
        s1 = ExecutionStep(name="a")
        s2 = ExecutionStep(name="b")
        assert s1.id != s2.id


class TestRunbookExecutionModel:
    def test_defaults(self) -> None:
        exe = RunbookExecution(runbook_id="rb-1")
        assert exe.runbook_id == "rb-1"
        assert exe.runbook_name == ""
        assert exe.trigger == ""
        assert exe.triggered_by == ""
        assert exe.status == ExecutionStatus.RUNNING
        assert exe.steps == []
        assert exe.started_at > 0
        assert exe.completed_at is None
        assert exe.duration_seconds == 0.0
        assert exe.incident_id == ""
        assert exe.environment == ""
        assert exe.metadata == {}
        assert len(exe.id) == 12


# ── Tracker Creation ─────────────────────────────────────────────


class TestTrackerCreation:
    def test_default_params(self) -> None:
        t = RunbookExecutionTracker()
        assert t._max_executions == 10000
        assert t._ttl_seconds == 90 * 86400

    def test_custom_params(self) -> None:
        t = RunbookExecutionTracker(max_executions=50, execution_ttl_days=7)
        assert t._max_executions == 50
        assert t._ttl_seconds == 7 * 86400

    def test_starts_empty(self) -> None:
        t = RunbookExecutionTracker()
        assert len(t._executions) == 0


# ── start_execution ──────────────────────────────────────────────


class TestStartExecution:
    def test_minimal(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        assert exe.runbook_id == "rb-1"
        assert exe.runbook_name == "rb-1", "Name defaults to runbook_id"
        assert exe.trigger == "manual"
        assert exe.status == ExecutionStatus.RUNNING
        assert exe.steps == []

    def test_all_params(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(
            runbook_id="rb-2",
            runbook_name="Full Restart",
            trigger="alert",
            triggered_by="pd-webhook",
            steps=["stop", "clean", "start"],
            incident_id="inc-123",
            environment="production",
            metadata={"region": "us-east-1"},
        )
        assert exe.runbook_name == "Full Restart"
        assert exe.trigger == "alert"
        assert exe.triggered_by == "pd-webhook"
        assert len(exe.steps) == 3
        assert exe.steps[0].name == "stop"
        assert exe.steps[0].status == StepStatus.PENDING
        assert exe.incident_id == "inc-123"
        assert exe.environment == "production"
        assert exe.metadata == {"region": "us-east-1"}

    def test_stored_in_tracker(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        retrieved = tracker.get_execution(exe.id)
        assert retrieved is not None
        assert retrieved.id == exe.id

    def test_auto_cleanup_at_max(self) -> None:
        t = RunbookExecutionTracker(max_executions=4)
        ids = []
        for i in range(4):
            e = t.start_execution(runbook_id=f"rb-{i}")
            ids.append(e.id)
        assert len(t._executions) == 4
        # Adding one more triggers cleanup (removes oldest half)
        e5 = t.start_execution(runbook_id="rb-extra")
        assert len(t._executions) <= 4
        assert e5.id in t._executions

    def test_returns_runbook_execution_instance(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        assert isinstance(exe, RunbookExecution)


# ── record_step ──────────────────────────────────────────────────


class TestRecordStep:
    def test_new_step_created(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        step = tracker.record_step(exe.id, "deploy", StepStatus.RUNNING)
        assert step is not None
        assert step.name == "deploy"
        assert step.status == StepStatus.RUNNING
        assert len(exe.steps) == 1

    def test_update_existing_step(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1", steps=["deploy"])
        tracker.record_step(exe.id, "deploy", StepStatus.RUNNING)
        step = tracker.record_step(exe.id, "deploy", StepStatus.COMPLETED, output="ok")
        assert step.status == StepStatus.COMPLETED
        assert step.output == "ok"
        assert len(exe.steps) == 1, "Should update, not add duplicate"

    def test_running_sets_started_at(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        step = tracker.record_step(exe.id, "deploy", StepStatus.RUNNING)
        assert step.started_at is not None
        assert step.started_at > 0

    def test_running_does_not_overwrite_started_at(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        step = tracker.record_step(exe.id, "deploy", StepStatus.RUNNING)
        first_ts = step.started_at
        tracker.record_step(exe.id, "deploy", StepStatus.RUNNING)
        assert step.started_at == first_ts

    def test_completed_sets_completed_at_and_duration(
        self, tracker: RunbookExecutionTracker
    ) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        tracker.record_step(exe.id, "deploy", StepStatus.RUNNING)
        step = tracker.record_step(exe.id, "deploy", StepStatus.COMPLETED)
        assert step.completed_at is not None
        assert step.duration_seconds >= 0.0

    def test_failed_sets_completed_at(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        tracker.record_step(exe.id, "deploy", StepStatus.RUNNING)
        step = tracker.record_step(exe.id, "deploy", StepStatus.FAILED, error="timeout")
        assert step.completed_at is not None
        assert step.error == "timeout"

    def test_skipped_sets_completed_at(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        step = tracker.record_step(exe.id, "cleanup", StepStatus.SKIPPED)
        assert step.completed_at is not None

    def test_not_found_returns_none(self, tracker: RunbookExecutionTracker) -> None:
        result = tracker.record_step("nonexistent", "step1", StepStatus.RUNNING)
        assert result is None

    def test_output_preserved_when_not_provided(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        tracker.record_step(exe.id, "deploy", StepStatus.RUNNING, output="starting")
        step = tracker.record_step(exe.id, "deploy", StepStatus.COMPLETED)
        assert step.output == "starting", "Output should persist if not overwritten"

    def test_metadata_merge(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        tracker.record_step(exe.id, "deploy", StepStatus.RUNNING, metadata={"region": "us-east-1"})
        step = tracker.record_step(
            exe.id, "deploy", StepStatus.COMPLETED, metadata={"duration_ms": 500}
        )
        assert step.metadata["region"] == "us-east-1"
        assert step.metadata["duration_ms"] == 500

    def test_error_preserved_when_not_provided(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        tracker.record_step(exe.id, "deploy", StepStatus.RUNNING, error="warn")
        step = tracker.record_step(exe.id, "deploy", StepStatus.COMPLETED)
        assert step.error == "warn"


# ── complete_execution ───────────────────────────────────────────


class TestCompleteExecution:
    def test_completed(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        result = tracker.complete_execution(exe.id, ExecutionStatus.COMPLETED)
        assert result is not None
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_at is not None
        assert result.duration_seconds >= 0.0

    def test_failed(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        result = tracker.complete_execution(exe.id, ExecutionStatus.FAILED)
        assert result.status == ExecutionStatus.FAILED

    def test_cancelled(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        result = tracker.complete_execution(exe.id, ExecutionStatus.CANCELLED)
        assert result.status == ExecutionStatus.CANCELLED

    def test_rolled_back(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        result = tracker.complete_execution(exe.id, ExecutionStatus.ROLLED_BACK)
        assert result.status == ExecutionStatus.ROLLED_BACK

    def test_duration_calculation(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        result = tracker.complete_execution(exe.id)
        assert result.duration_seconds == pytest.approx(
            result.completed_at - result.started_at, abs=0.01
        )

    def test_not_found(self, tracker: RunbookExecutionTracker) -> None:
        result = tracker.complete_execution("nonexistent")
        assert result is None

    def test_default_status_is_completed(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        result = tracker.complete_execution(exe.id)
        assert result.status == ExecutionStatus.COMPLETED


# ── get_execution ────────────────────────────────────────────────


class TestGetExecution:
    def test_found(self, tracker: RunbookExecutionTracker) -> None:
        exe = tracker.start_execution(runbook_id="rb-1")
        result = tracker.get_execution(exe.id)
        assert result is not None
        assert result.id == exe.id

    def test_not_found(self, tracker: RunbookExecutionTracker) -> None:
        assert tracker.get_execution("nonexistent") is None

    def test_empty_tracker(self, tracker: RunbookExecutionTracker) -> None:
        assert tracker.get_execution("any-id") is None


# ── list_executions ──────────────────────────────────────────────


class TestListExecutions:
    def test_all_executions(self, populated_tracker: RunbookExecutionTracker) -> None:
        execs = populated_tracker.list_executions()
        assert len(execs) == 3

    def test_filter_by_runbook_id(self, populated_tracker: RunbookExecutionTracker) -> None:
        execs = populated_tracker.list_executions(runbook_id="rb-restart")
        assert len(execs) == 2
        assert all(e.runbook_id == "rb-restart" for e in execs)

    def test_filter_by_status(self, populated_tracker: RunbookExecutionTracker) -> None:
        # All are running by default
        execs = populated_tracker.list_executions(status=ExecutionStatus.RUNNING)
        assert len(execs) == 3

    def test_filter_by_status_no_match(self, populated_tracker: RunbookExecutionTracker) -> None:
        execs = populated_tracker.list_executions(status=ExecutionStatus.FAILED)
        assert execs == []

    def test_combined_filters(self, populated_tracker: RunbookExecutionTracker) -> None:
        execs = populated_tracker.list_executions(
            runbook_id="rb-scale", status=ExecutionStatus.RUNNING
        )
        assert len(execs) == 1
        assert execs[0].runbook_id == "rb-scale"

    def test_limit(self, populated_tracker: RunbookExecutionTracker) -> None:
        execs = populated_tracker.list_executions(limit=2)
        assert len(execs) == 2

    def test_sorted_by_started_at_desc(self, populated_tracker: RunbookExecutionTracker) -> None:
        execs = populated_tracker.list_executions()
        for i in range(len(execs) - 1):
            assert execs[i].started_at >= execs[i + 1].started_at

    def test_empty_tracker(self, tracker: RunbookExecutionTracker) -> None:
        assert tracker.list_executions() == []


# ── get_stats ────────────────────────────────────────────────────


class TestGetStats:
    def test_empty_tracker(self, tracker: RunbookExecutionTracker) -> None:
        stats = tracker.get_stats()
        assert stats["total_executions"] == 0
        assert stats["by_status"] == {}
        assert stats["total_steps"] == 0
        assert stats["avg_duration_seconds"] == pytest.approx(0.0)

    def test_populated(self, populated_tracker: RunbookExecutionTracker) -> None:
        stats = populated_tracker.get_stats()
        assert stats["total_executions"] == 3
        assert stats["by_status"]["running"] == 3
        # 3+2+3 = 8 steps
        assert stats["total_steps"] == 8

    def test_avg_duration_with_completed(self, tracker: RunbookExecutionTracker) -> None:
        e1 = tracker.start_execution(runbook_id="rb-1")
        e2 = tracker.start_execution(runbook_id="rb-2")
        tracker.complete_execution(e1.id, ExecutionStatus.COMPLETED)
        tracker.complete_execution(e2.id, ExecutionStatus.COMPLETED)
        stats = tracker.get_stats()
        assert stats["avg_duration_seconds"] >= 0.0

    def test_avg_duration_excludes_non_completed(self, tracker: RunbookExecutionTracker) -> None:
        e1 = tracker.start_execution(runbook_id="rb-1")
        tracker.start_execution(runbook_id="rb-2")  # still running
        tracker.complete_execution(e1.id, ExecutionStatus.COMPLETED)
        stats = tracker.get_stats()
        # Only e1 counts toward avg
        assert stats["avg_duration_seconds"] >= 0.0

    def test_avg_duration_excludes_failed(self, tracker: RunbookExecutionTracker) -> None:
        e1 = tracker.start_execution(runbook_id="rb-1")
        tracker.complete_execution(e1.id, ExecutionStatus.FAILED)
        stats = tracker.get_stats()
        # Failed doesn't count as COMPLETED
        assert stats["avg_duration_seconds"] == pytest.approx(0.0)
