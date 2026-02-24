"""Tests for shieldops.operations.runbook_engine — RunbookExecutionEngine."""

from __future__ import annotations

from shieldops.operations.runbook_engine import (
    ExecutionStep,
    ExecutionSummary,
    RunbookExecution,
    RunbookExecutionEngine,
    RunbookStatus,
    StepOutcome,
    TriggerType,
)


def _engine(**kw) -> RunbookExecutionEngine:
    return RunbookExecutionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_pending(self):
        assert RunbookStatus.PENDING == "pending"

    def test_status_running(self):
        assert RunbookStatus.RUNNING == "running"

    def test_status_paused(self):
        assert RunbookStatus.PAUSED == "paused"

    def test_status_completed(self):
        assert RunbookStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert RunbookStatus.FAILED == "failed"

    def test_status_cancelled(self):
        assert RunbookStatus.CANCELLED == "cancelled"

    def test_outcome_success(self):
        assert StepOutcome.SUCCESS == "success"

    def test_outcome_failure(self):
        assert StepOutcome.FAILURE == "failure"

    def test_outcome_skipped(self):
        assert StepOutcome.SKIPPED == "skipped"

    def test_outcome_timeout(self):
        assert StepOutcome.TIMEOUT == "timeout"

    def test_outcome_manual(self):
        assert StepOutcome.MANUAL_OVERRIDE == "manual_override"

    def test_trigger_manual(self):
        assert TriggerType.MANUAL == "manual"

    def test_trigger_alert(self):
        assert TriggerType.ALERT == "alert"

    def test_trigger_schedule(self):
        assert TriggerType.SCHEDULE == "schedule"

    def test_trigger_incident(self):
        assert TriggerType.INCIDENT == "incident"

    def test_trigger_api(self):
        assert TriggerType.API == "api"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_execution_defaults(self):
        e = RunbookExecution()
        assert e.id
        assert e.status == RunbookStatus.PENDING
        assert e.current_step == 0

    def test_step_defaults(self):
        s = ExecutionStep()
        assert s.outcome == StepOutcome.SUCCESS

    def test_summary_defaults(self):
        s = ExecutionSummary()
        assert s.total_executions == 0
        assert s.success_rate == 0.0


# ---------------------------------------------------------------------------
# start_execution
# ---------------------------------------------------------------------------


class TestStartExecution:
    def test_basic_start(self):
        eng = _engine()
        ex = eng.start_execution("restart-service")
        assert ex.runbook_name == "restart-service"
        assert ex.status == RunbookStatus.RUNNING

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.start_execution("rb1")
        e2 = eng.start_execution("rb2")
        assert e1.id != e2.id

    def test_eviction_at_max(self):
        eng = _engine(max_executions=3)
        for i in range(5):
            eng.start_execution(f"rb{i}")
        assert len(eng._executions) == 3

    def test_with_context(self):
        eng = _engine()
        ex = eng.start_execution("rb1", context={"env": "prod"})
        assert ex.context == {"env": "prod"}


# ---------------------------------------------------------------------------
# get / list executions
# ---------------------------------------------------------------------------


class TestGetExecution:
    def test_found(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        assert eng.get_execution(ex.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_execution("nonexistent") is None


class TestListExecutions:
    def test_list_all(self):
        eng = _engine()
        eng.start_execution("rb1")
        eng.start_execution("rb2")
        assert len(eng.list_executions()) == 2

    def test_filter_by_name(self):
        eng = _engine()
        eng.start_execution("rb1")
        eng.start_execution("rb2")
        results = eng.list_executions(runbook_name="rb1")
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.start_execution("rb1")
        results = eng.list_executions(status=RunbookStatus.RUNNING)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# record_step
# ---------------------------------------------------------------------------


class TestRecordStep:
    def test_basic_step(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        step = eng.record_step(ex.id, name="Check health")
        assert step is not None
        assert step.name == "Check health"

    def test_step_increments_counter(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        eng.record_step(ex.id, name="Step 1")
        eng.record_step(ex.id, name="Step 2")
        assert ex.current_step == 2

    def test_failure_sets_failed(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        eng.record_step(ex.id, name="Fail", outcome=StepOutcome.FAILURE)
        assert ex.status == RunbookStatus.FAILED

    def test_step_invalid_execution(self):
        eng = _engine()
        assert eng.record_step("bad_id") is None


# ---------------------------------------------------------------------------
# pause / resume / cancel / complete
# ---------------------------------------------------------------------------


class TestPauseExecution:
    def test_pause(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        assert eng.pause_execution(ex.id) is True
        assert ex.status == RunbookStatus.PAUSED

    def test_pause_non_running(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        eng.complete_execution(ex.id)
        assert eng.pause_execution(ex.id) is False


class TestResumeExecution:
    def test_resume(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        eng.pause_execution(ex.id)
        assert eng.resume_execution(ex.id) is True
        assert ex.status == RunbookStatus.RUNNING

    def test_resume_non_paused(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        assert eng.resume_execution(ex.id) is False


class TestCancelExecution:
    def test_cancel(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        assert eng.cancel_execution(ex.id) is True
        assert ex.status == RunbookStatus.CANCELLED

    def test_cancel_completed(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        eng.complete_execution(ex.id)
        assert eng.cancel_execution(ex.id) is False


class TestCompleteExecution:
    def test_complete(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        assert eng.complete_execution(ex.id) is True
        assert ex.status == RunbookStatus.COMPLETED

    def test_complete_failed(self):
        eng = _engine()
        ex = eng.start_execution("rb1")
        eng.record_step(ex.id, outcome=StepOutcome.FAILURE)
        assert eng.complete_execution(ex.id) is False


# ---------------------------------------------------------------------------
# success_rate / stats
# ---------------------------------------------------------------------------


class TestSuccessRate:
    def test_empty(self):
        eng = _engine()
        rate = eng.get_success_rate()
        assert rate["total"] == 0

    def test_with_data(self):
        eng = _engine()
        ex1 = eng.start_execution("rb1")
        eng.complete_execution(ex1.id)
        ex2 = eng.start_execution("rb2")
        eng.record_step(ex2.id, outcome=StepOutcome.FAILURE)
        rate = eng.get_success_rate()
        assert rate["completed"] == 1
        assert rate["failed"] == 1


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_executions"] == 0

    def test_populated_stats(self):
        eng = _engine()
        ex = eng.start_execution("rb1", trigger=TriggerType.ALERT)
        eng.record_step(ex.id, name="step1")
        stats = eng.get_stats()
        assert stats["total_executions"] == 1
        assert stats["total_steps"] == 1
