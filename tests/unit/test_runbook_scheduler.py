"""Tests for shieldops.playbooks.runbook_scheduler – RunbookScheduler."""

from __future__ import annotations

import time

import pytest

from shieldops.playbooks.runbook_scheduler import (
    RunbookScheduler,
    ScheduledRunbook,
    ScheduleExecution,
    ScheduleFrequency,
    ScheduleResult,
    ScheduleStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scheduler(**kwargs) -> RunbookScheduler:
    return RunbookScheduler(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_schedule_status_values(self):
        assert ScheduleStatus.PENDING == "pending"
        assert ScheduleStatus.READY == "ready"
        assert ScheduleStatus.EXECUTING == "executing"
        assert ScheduleStatus.COMPLETED == "completed"
        assert ScheduleStatus.FAILED == "failed"
        assert ScheduleStatus.CANCELLED == "cancelled"

    def test_schedule_frequency_values(self):
        assert ScheduleFrequency.ONCE == "once"
        assert ScheduleFrequency.DAILY == "daily"
        assert ScheduleFrequency.WEEKLY == "weekly"
        assert ScheduleFrequency.MONTHLY == "monthly"
        assert ScheduleFrequency.CRON == "cron"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_scheduled_runbook_defaults(self):
        now = time.time()
        sr = ScheduledRunbook(runbook_id="rb-001", name="clear-cache", scheduled_at=now)
        assert sr.id
        assert sr.runbook_id == "rb-001"
        assert sr.name == "clear-cache"
        assert sr.frequency == ScheduleFrequency.ONCE
        assert sr.cron_expression == ""
        assert sr.scheduled_at == now
        assert sr.environment == "production"
        assert sr.parameters == {}
        assert sr.status == ScheduleStatus.PENDING
        assert sr.created_by == ""
        assert sr.metadata == {}
        assert sr.created_at > 0

    def test_schedule_execution_defaults(self):
        ex = ScheduleExecution(schedule_id="sched-1")
        assert ex.id
        assert ex.schedule_id == "sched-1"
        assert ex.started_at > 0
        assert ex.completed_at is None
        assert ex.status == ScheduleStatus.EXECUTING
        assert ex.output == ""
        assert ex.error_message == ""

    def test_schedule_result_fields(self):
        sr = ScheduleResult(
            schedule_id="s1",
            execution_id="e1",
            success=True,
            duration_seconds=12.5,
            message="All clear",
        )
        assert sr.schedule_id == "s1"
        assert sr.execution_id == "e1"
        assert sr.success is True
        assert sr.duration_seconds == 12.5
        assert sr.message == "All clear"

    def test_schedule_result_defaults(self):
        sr = ScheduleResult(schedule_id="s1", execution_id="e1", success=False)
        assert sr.duration_seconds == 0.0
        assert sr.message == ""


# ---------------------------------------------------------------------------
# Schedule runbook
# ---------------------------------------------------------------------------


class TestScheduleRunbook:
    def test_basic(self):
        s = _scheduler()
        now = time.time() + 3600
        rb = s.schedule_runbook(runbook_id="rb-1", name="rotate-certs", scheduled_at=now)
        assert rb.runbook_id == "rb-1"
        assert rb.name == "rotate-certs"
        assert rb.scheduled_at == now
        assert rb.id

    def test_with_all_fields(self):
        s = _scheduler()
        now = time.time() + 3600
        rb = s.schedule_runbook(
            runbook_id="rb-2",
            name="db-backup",
            scheduled_at=now,
            frequency=ScheduleFrequency.DAILY,
            cron_expression="0 2 * * *",
            environment="staging",
            parameters={"database": "orders_db"},
            created_by="ops-team",
            metadata={"priority": "high"},
        )
        assert rb.frequency == ScheduleFrequency.DAILY
        assert rb.cron_expression == "0 2 * * *"
        assert rb.environment == "staging"
        assert rb.parameters["database"] == "orders_db"
        assert rb.created_by == "ops-team"
        assert rb.metadata["priority"] == "high"

    def test_max_limit(self):
        s = _scheduler(max_schedules=2)
        now = time.time() + 3600
        s.schedule_runbook(runbook_id="rb-1", name="n1", scheduled_at=now)
        s.schedule_runbook(runbook_id="rb-2", name="n2", scheduled_at=now)
        with pytest.raises(ValueError, match="Maximum schedules"):
            s.schedule_runbook(runbook_id="rb-3", name="n3", scheduled_at=now)

    def test_scheduled_in_past_allowed(self):
        s = _scheduler()
        past = time.time() - 3600
        rb = s.schedule_runbook(runbook_id="rb-1", name="past-job", scheduled_at=past)
        assert rb.id
        assert rb.scheduled_at == past


# ---------------------------------------------------------------------------
# Cancel schedule
# ---------------------------------------------------------------------------


class TestCancelSchedule:
    def test_success(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="temp", scheduled_at=time.time() + 3600)
        result = s.cancel_schedule(rb.id)
        assert result is not None
        assert result.status == ScheduleStatus.CANCELLED

    def test_not_found(self):
        s = _scheduler()
        assert s.cancel_schedule("nonexistent") is None

    def test_cancelled_schedule_not_due(self):
        s = _scheduler(lookahead_minutes=120)
        now = time.time()
        rb = s.schedule_runbook(runbook_id="rb-1", name="cancel-me", scheduled_at=now + 60)
        s.cancel_schedule(rb.id)
        due = s.get_due_runbooks()
        assert len(due) == 0


# ---------------------------------------------------------------------------
# Get schedule
# ---------------------------------------------------------------------------


class TestGetSchedule:
    def test_found(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        fetched = s.get_schedule(rb.id)
        assert fetched is not None
        assert fetched.id == rb.id

    def test_not_found(self):
        s = _scheduler()
        assert s.get_schedule("nonexistent") is None


# ---------------------------------------------------------------------------
# List schedules
# ---------------------------------------------------------------------------


class TestListSchedules:
    def test_all(self):
        s = _scheduler()
        now = time.time() + 3600
        s.schedule_runbook(runbook_id="rb-1", name="n1", scheduled_at=now)
        s.schedule_runbook(runbook_id="rb-2", name="n2", scheduled_at=now)
        assert len(s.list_schedules()) == 2

    def test_filter_by_status(self):
        s = _scheduler()
        now = time.time() + 3600
        rb1 = s.schedule_runbook(runbook_id="rb-1", name="n1", scheduled_at=now)
        s.schedule_runbook(runbook_id="rb-2", name="n2", scheduled_at=now)
        s.cancel_schedule(rb1.id)
        pending = s.list_schedules(status=ScheduleStatus.PENDING)
        assert len(pending) == 1
        cancelled = s.list_schedules(status=ScheduleStatus.CANCELLED)
        assert len(cancelled) == 1

    def test_empty(self):
        s = _scheduler()
        assert s.list_schedules() == []


# ---------------------------------------------------------------------------
# Get due runbooks
# ---------------------------------------------------------------------------


class TestGetDueRunbooks:
    def test_returns_pending_within_lookahead(self):
        s = _scheduler(lookahead_minutes=60)
        now = time.time()
        s.schedule_runbook(runbook_id="rb-1", name="due-now", scheduled_at=now + 30 * 60)
        due = s.get_due_runbooks()
        assert len(due) == 1
        assert due[0].name == "due-now"

    def test_excludes_future(self):
        s = _scheduler(lookahead_minutes=60)
        now = time.time()
        s.schedule_runbook(runbook_id="rb-1", name="far-future", scheduled_at=now + 7200)
        due = s.get_due_runbooks()
        assert len(due) == 0

    def test_includes_past_pending(self):
        s = _scheduler(lookahead_minutes=60)
        now = time.time()
        s.schedule_runbook(runbook_id="rb-1", name="overdue", scheduled_at=now - 600)
        due = s.get_due_runbooks()
        assert len(due) == 1
        assert due[0].name == "overdue"

    def test_excludes_non_pending(self):
        s = _scheduler(lookahead_minutes=120)
        now = time.time()
        rb = s.schedule_runbook(runbook_id="rb-1", name="executing", scheduled_at=now + 60)
        s.execute_scheduled(rb.id)
        due = s.get_due_runbooks()
        assert len(due) == 0


# ---------------------------------------------------------------------------
# Execute scheduled
# ---------------------------------------------------------------------------


class TestExecuteScheduled:
    def test_success(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="exec-me", scheduled_at=time.time() + 3600)
        execution = s.execute_scheduled(rb.id)
        assert execution is not None
        assert execution.schedule_id == rb.id
        assert execution.status == ScheduleStatus.EXECUTING
        assert execution.id
        # Schedule status should also update
        fetched = s.get_schedule(rb.id)
        assert fetched is not None
        assert fetched.status == ScheduleStatus.EXECUTING

    def test_not_found(self):
        s = _scheduler()
        assert s.execute_scheduled("nonexistent") is None


# ---------------------------------------------------------------------------
# Record result
# ---------------------------------------------------------------------------


class TestRecordResult:
    def test_success(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        execution = s.execute_scheduled(rb.id)
        assert execution is not None
        result = s.record_result(execution_id=execution.id, success=True, output="Completed OK")
        assert result is not None
        assert result.success is True
        assert result.message == "Completed OK"
        assert result.duration_seconds >= 0
        assert result.schedule_id == rb.id
        assert result.execution_id == execution.id

    def test_failure(self):
        s = _scheduler()
        rb = s.schedule_runbook(
            runbook_id="rb-1", name="fail-test", scheduled_at=time.time() + 3600
        )
        execution = s.execute_scheduled(rb.id)
        assert execution is not None
        result = s.record_result(
            execution_id=execution.id,
            success=False,
            error_message="Timeout after 300s",
        )
        assert result is not None
        assert result.success is False
        assert result.message == "Timeout after 300s"
        # Schedule should be marked failed
        fetched = s.get_schedule(rb.id)
        assert fetched is not None
        assert fetched.status == ScheduleStatus.FAILED

    def test_execution_not_found(self):
        s = _scheduler()
        result = s.record_result(execution_id="nonexistent", success=True)
        assert result is None

    def test_success_marks_schedule_completed(self):
        s = _scheduler()
        rb = s.schedule_runbook(
            runbook_id="rb-1", name="complete-me", scheduled_at=time.time() + 3600
        )
        execution = s.execute_scheduled(rb.id)
        assert execution is not None
        s.record_result(execution_id=execution.id, success=True, output="Done")
        fetched = s.get_schedule(rb.id)
        assert fetched is not None
        assert fetched.status == ScheduleStatus.COMPLETED


# ---------------------------------------------------------------------------
# Execution history
# ---------------------------------------------------------------------------


class TestGetExecutionHistory:
    def test_all(self):
        s = _scheduler()
        now = time.time() + 3600
        rb1 = s.schedule_runbook(runbook_id="rb-1", name="n1", scheduled_at=now)
        rb2 = s.schedule_runbook(runbook_id="rb-2", name="n2", scheduled_at=now)
        s.execute_scheduled(rb1.id)
        s.execute_scheduled(rb2.id)
        history = s.get_execution_history()
        assert len(history) == 2

    def test_filter_by_schedule_id(self):
        s = _scheduler()
        now = time.time() + 3600
        rb1 = s.schedule_runbook(runbook_id="rb-1", name="n1", scheduled_at=now)
        rb2 = s.schedule_runbook(runbook_id="rb-2", name="n2", scheduled_at=now)
        s.execute_scheduled(rb1.id)
        s.execute_scheduled(rb2.id)
        history = s.get_execution_history(schedule_id=rb1.id)
        assert len(history) == 1
        assert history[0].schedule_id == rb1.id

    def test_empty(self):
        s = _scheduler()
        assert s.get_execution_history() == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        s = _scheduler()
        st = s.get_stats()
        assert st["total_schedules"] == 0
        assert st["pending_schedules"] == 0
        assert st["completed_schedules"] == 0
        assert st["failed_schedules"] == 0
        assert st["cancelled_schedules"] == 0
        assert st["total_executions"] == 0

    def test_with_data(self):
        s = _scheduler()
        now = time.time() + 3600
        rb1 = s.schedule_runbook(runbook_id="rb-1", name="n1", scheduled_at=now)
        rb2 = s.schedule_runbook(runbook_id="rb-2", name="n2", scheduled_at=now)
        rb3 = s.schedule_runbook(runbook_id="rb-3", name="n3", scheduled_at=now)
        s.cancel_schedule(rb1.id)
        ex2 = s.execute_scheduled(rb2.id)
        assert ex2 is not None
        s.record_result(ex2.id, success=True, output="OK")
        ex3 = s.execute_scheduled(rb3.id)
        assert ex3 is not None
        s.record_result(ex3.id, success=False, error_message="Fail")
        st = s.get_stats()
        assert st["total_schedules"] == 3
        assert st["pending_schedules"] == 0
        assert st["completed_schedules"] == 1
        assert st["failed_schedules"] == 1
        assert st["cancelled_schedules"] == 1
        assert st["total_executions"] == 2
        assert st["lookahead_minutes"] == 60


# ---------------------------------------------------------------------------
# Additional coverage: edge cases and combined scenarios
# ---------------------------------------------------------------------------


class TestScheduleIsolation:
    def test_unique_schedule_ids(self):
        s = _scheduler()
        now = time.time() + 3600
        rb1 = s.schedule_runbook(runbook_id="rb-1", name="n1", scheduled_at=now)
        rb2 = s.schedule_runbook(runbook_id="rb-2", name="n2", scheduled_at=now)
        assert rb1.id != rb2.id

    def test_created_at_is_set(self):
        before = time.time()
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        after = time.time()
        assert before <= rb.created_at <= after

    def test_default_environment_is_production(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        assert rb.environment == "production"

    def test_default_frequency_is_once(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        assert rb.frequency == ScheduleFrequency.ONCE

    def test_parameters_persist(self):
        s = _scheduler()
        params = {"target": "redis-cluster", "max_nodes": 5}
        rb = s.schedule_runbook(
            runbook_id="rb-1",
            name="scale-redis",
            scheduled_at=time.time() + 3600,
            parameters=params,
        )
        fetched = s.get_schedule(rb.id)
        assert fetched is not None
        assert fetched.parameters["target"] == "redis-cluster"
        assert fetched.parameters["max_nodes"] == 5


class TestExecutionLifecycle:
    def test_execution_sets_started_at(self):
        before = time.time()
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        ex = s.execute_scheduled(rb.id)
        after = time.time()
        assert ex is not None
        assert before <= ex.started_at <= after

    def test_result_sets_completed_at(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        ex = s.execute_scheduled(rb.id)
        assert ex is not None
        before = time.time()
        result = s.record_result(ex.id, success=True, output="Done")
        after = time.time()
        assert result is not None
        # Check the execution was updated
        history = s.get_execution_history(schedule_id=rb.id)
        assert len(history) == 1
        assert history[0].completed_at is not None
        assert before <= history[0].completed_at <= after

    def test_execution_output_stored(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        ex = s.execute_scheduled(rb.id)
        assert ex is not None
        s.record_result(ex.id, success=True, output="Backup completed: 3.2GB")
        history = s.get_execution_history(schedule_id=rb.id)
        assert history[0].output == "Backup completed: 3.2GB"

    def test_execution_error_message_stored(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="test", scheduled_at=time.time() + 3600)
        ex = s.execute_scheduled(rb.id)
        assert ex is not None
        s.record_result(ex.id, success=False, error_message="Connection refused")
        history = s.get_execution_history(schedule_id=rb.id)
        assert history[0].error_message == "Connection refused"
        assert history[0].status == ScheduleStatus.FAILED

    def test_multiple_executions_same_schedule(self):
        s = _scheduler()
        rb = s.schedule_runbook(
            runbook_id="rb-1",
            name="recurring",
            scheduled_at=time.time() + 3600,
            frequency=ScheduleFrequency.DAILY,
        )
        ex1 = s.execute_scheduled(rb.id)
        assert ex1 is not None
        s.record_result(ex1.id, success=True, output="Run 1")
        # Reset status to pending for next run
        fetched = s.get_schedule(rb.id)
        assert fetched is not None
        fetched.status = ScheduleStatus.PENDING
        ex2 = s.execute_scheduled(rb.id)
        assert ex2 is not None
        s.record_result(ex2.id, success=True, output="Run 2")
        history = s.get_execution_history(schedule_id=rb.id)
        assert len(history) == 2


class TestDueRunbooksBoundary:
    def test_exactly_at_horizon(self):
        s = _scheduler(lookahead_minutes=60)
        now = time.time()
        # Schedule right at the horizon boundary
        s.schedule_runbook(
            runbook_id="rb-1",
            name="boundary",
            scheduled_at=now + 60 * 60,
        )
        due = s.get_due_runbooks()
        assert len(due) == 1

    def test_multiple_due_runbooks(self):
        s = _scheduler(lookahead_minutes=120)
        now = time.time()
        s.schedule_runbook(runbook_id="rb-1", name="soon-1", scheduled_at=now + 60)
        s.schedule_runbook(runbook_id="rb-2", name="soon-2", scheduled_at=now + 120)
        s.schedule_runbook(runbook_id="rb-3", name="later", scheduled_at=now + 9000)
        due = s.get_due_runbooks()
        assert len(due) == 2
        names = {d.name for d in due}
        assert "soon-1" in names
        assert "soon-2" in names


class TestCustomSchedulerConfig:
    def test_custom_max_schedules(self):
        s = _scheduler(max_schedules=10)
        st = s.get_stats()
        # Can still schedule up to 10
        assert st["total_schedules"] == 0

    def test_custom_lookahead(self):
        s = _scheduler(lookahead_minutes=30)
        st = s.get_stats()
        assert st["lookahead_minutes"] == 30

    def test_result_duration_calculated(self):
        s = _scheduler()
        rb = s.schedule_runbook(runbook_id="rb-1", name="timed", scheduled_at=time.time() + 3600)
        ex = s.execute_scheduled(rb.id)
        assert ex is not None
        result = s.record_result(ex.id, success=True, output="Quick")
        assert result is not None
        assert result.duration_seconds >= 0
