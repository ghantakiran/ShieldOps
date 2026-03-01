"""Tests for shieldops.operations.runbook_exec_tracker — RunbookExecutionTracker."""

from __future__ import annotations

from shieldops.operations.runbook_exec_tracker import (
    ExecutionMode,
    ExecutionPhase,
    ExecutionRecord,
    ExecutionResult,
    ExecutionStep,
    RunbookExecutionReport,
    RunbookExecutionTracker,
)


def _engine(**kw) -> RunbookExecutionTracker:
    return RunbookExecutionTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ExecutionResult (5)
    def test_result_success(self):
        assert ExecutionResult.SUCCESS == "success"

    def test_result_partial_success(self):
        assert ExecutionResult.PARTIAL_SUCCESS == "partial_success"

    def test_result_failed(self):
        assert ExecutionResult.FAILED == "failed"

    def test_result_aborted(self):
        assert ExecutionResult.ABORTED == "aborted"

    def test_result_timeout(self):
        assert ExecutionResult.TIMEOUT == "timeout"

    # ExecutionMode (5)
    def test_mode_manual(self):
        assert ExecutionMode.MANUAL == "manual"

    def test_mode_automated(self):
        assert ExecutionMode.AUTOMATED == "automated"

    def test_mode_hybrid(self):
        assert ExecutionMode.HYBRID == "hybrid"

    def test_mode_scheduled(self):
        assert ExecutionMode.SCHEDULED == "scheduled"

    def test_mode_triggered(self):
        assert ExecutionMode.TRIGGERED == "triggered"

    # ExecutionPhase (5)
    def test_phase_preparation(self):
        assert ExecutionPhase.PREPARATION == "preparation"

    def test_phase_execution(self):
        assert ExecutionPhase.EXECUTION == "execution"

    def test_phase_verification(self):
        assert ExecutionPhase.VERIFICATION == "verification"

    def test_phase_cleanup(self):
        assert ExecutionPhase.CLEANUP == "cleanup"

    def test_phase_rollback(self):
        assert ExecutionPhase.ROLLBACK == "rollback"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_execution_record_defaults(self):
        r = ExecutionRecord()
        assert r.id
        assert r.runbook_id == ""
        assert r.result == ExecutionResult.SUCCESS
        assert r.mode == ExecutionMode.MANUAL
        assert r.duration_minutes == 0.0
        assert r.team == ""
        assert r.service == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_execution_step_defaults(self):
        s = ExecutionStep()
        assert s.id
        assert s.execution_id == ""
        assert s.phase == ExecutionPhase.EXECUTION
        assert s.step_name == ""
        assert s.duration_minutes == 0.0
        assert s.success is True
        assert s.created_at > 0

    def test_report_defaults(self):
        r = RunbookExecutionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_steps == 0
        assert r.success_rate_pct == 0.0
        assert r.avg_duration_minutes == 0.0
        assert r.by_result == {}
        assert r.by_mode == {}
        assert r.failed_runbooks == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_execution
# -------------------------------------------------------------------


class TestRecordExecution:
    def test_basic(self):
        eng = _engine()
        r = eng.record_execution(
            "rb-001",
            result=ExecutionResult.SUCCESS,
            mode=ExecutionMode.AUTOMATED,
            duration_minutes=15.0,
            team="sre",
        )
        assert r.runbook_id == "rb-001"
        assert r.result == ExecutionResult.SUCCESS
        assert r.duration_minutes == 15.0
        assert r.team == "sre"

    def test_service_stored(self):
        eng = _engine()
        r = eng.record_execution("rb-002", service="payments")
        assert r.service == "payments"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_execution(f"rb-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_execution
# -------------------------------------------------------------------


class TestGetExecution:
    def test_found(self):
        eng = _engine()
        r = eng.record_execution("rb-001")
        assert eng.get_execution(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_execution("nonexistent") is None


# -------------------------------------------------------------------
# list_executions
# -------------------------------------------------------------------


class TestListExecutions:
    def test_list_all(self):
        eng = _engine()
        eng.record_execution("rb-001")
        eng.record_execution("rb-002")
        assert len(eng.list_executions()) == 2

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_execution("rb-001", result=ExecutionResult.FAILED)
        eng.record_execution("rb-002", result=ExecutionResult.SUCCESS)
        results = eng.list_executions(result=ExecutionResult.FAILED)
        assert len(results) == 1

    def test_filter_by_mode(self):
        eng = _engine()
        eng.record_execution("rb-001", mode=ExecutionMode.AUTOMATED)
        eng.record_execution("rb-002", mode=ExecutionMode.MANUAL)
        results = eng.list_executions(mode=ExecutionMode.AUTOMATED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_execution("rb-001", team="sre")
        eng.record_execution("rb-002", team="frontend")
        results = eng.list_executions(team="sre")
        assert len(results) == 1


# -------------------------------------------------------------------
# add_step
# -------------------------------------------------------------------


class TestAddStep:
    def test_basic(self):
        eng = _engine()
        s = eng.add_step(
            "exec-id-1",
            phase=ExecutionPhase.VERIFICATION,
            step_name="health-check",
            duration_minutes=2.5,
            success=True,
        )
        assert s.execution_id == "exec-id-1"
        assert s.phase == ExecutionPhase.VERIFICATION
        assert s.step_name == "health-check"
        assert s.success is True

    def test_failed_step(self):
        eng = _engine()
        s = eng.add_step("exec-id-2", success=False)
        assert s.success is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_step(f"exec-{i}")
        assert len(eng._steps) == 2


# -------------------------------------------------------------------
# analyze_execution_success
# -------------------------------------------------------------------


class TestAnalyzeExecutionSuccess:
    def test_groups_by_runbook(self):
        eng = _engine()
        eng.record_execution("rb-001", result=ExecutionResult.SUCCESS)
        eng.record_execution("rb-001", result=ExecutionResult.FAILED)
        eng.record_execution("rb-002", result=ExecutionResult.SUCCESS)
        results = eng.analyze_execution_success()
        rbs = {r["runbook_id"] for r in results}
        assert "rb-001" in rbs and "rb-002" in rbs

    def test_success_rate_calculation(self):
        eng = _engine()
        eng.record_execution("rb-001", result=ExecutionResult.SUCCESS)
        eng.record_execution("rb-001", result=ExecutionResult.SUCCESS)
        eng.record_execution("rb-001", result=ExecutionResult.FAILED)
        results = eng.analyze_execution_success()
        rb = next(r for r in results if r["runbook_id"] == "rb-001")
        assert abs(rb["success_rate_pct"] - 66.67) < 0.1

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_execution_success() == []


# -------------------------------------------------------------------
# identify_failing_runbooks
# -------------------------------------------------------------------


class TestIdentifyFailingRunbooks:
    def test_finds_below_threshold(self):
        eng = _engine(min_success_rate_pct=80.0)
        eng.record_execution("rb-bad", result=ExecutionResult.FAILED)
        eng.record_execution("rb-bad", result=ExecutionResult.FAILED)
        eng.record_execution("rb-bad", result=ExecutionResult.SUCCESS)
        eng.record_execution("rb-good", result=ExecutionResult.SUCCESS)
        results = eng.identify_failing_runbooks()
        rbs = [r["runbook_id"] for r in results]
        assert "rb-bad" in rbs
        assert "rb-good" not in rbs

    def test_empty_when_all_passing(self):
        eng = _engine(min_success_rate_pct=80.0)
        eng.record_execution("rb-001", result=ExecutionResult.SUCCESS)
        assert eng.identify_failing_runbooks() == []

    def test_empty_no_records(self):
        eng = _engine()
        assert eng.identify_failing_runbooks() == []


# -------------------------------------------------------------------
# rank_by_duration
# -------------------------------------------------------------------


class TestRankByDuration:
    def test_sorted_desc(self):
        eng = _engine()
        eng.record_execution("rb-001", team="sre", duration_minutes=30.0)
        eng.record_execution("rb-002", team="frontend", duration_minutes=5.0)
        results = eng.rank_by_duration()
        assert results[0]["team"] == "sre"

    def test_averages_correctly(self):
        eng = _engine()
        eng.record_execution("rb-001", team="ops", duration_minutes=20.0)
        eng.record_execution("rb-002", team="ops", duration_minutes=40.0)
        results = eng.rank_by_duration()
        assert results[0]["avg_duration_minutes"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_duration() == []


# -------------------------------------------------------------------
# detect_execution_trends
# -------------------------------------------------------------------


class TestDetectExecutionTrends:
    def test_detects_slower(self):
        eng = _engine()
        for _ in range(3):
            eng.record_execution("rb-001", duration_minutes=5.0)
        for _ in range(3):
            eng.record_execution("rb-001", duration_minutes=25.0)
        results = eng.detect_execution_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "slower"

    def test_no_trend_below_delta(self):
        eng = _engine()
        for _ in range(4):
            eng.record_execution("rb-001", duration_minutes=10.0)
        results = eng.detect_execution_trends()
        assert results == []

    def test_too_few_records(self):
        eng = _engine()
        eng.record_execution("rb-001")
        assert eng.detect_execution_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_success_rate_pct=80.0)
        eng.record_execution("rb-001", result=ExecutionResult.FAILED, team="sre")
        eng.record_execution("rb-002", result=ExecutionResult.SUCCESS, team="sre")
        eng.add_step("exec-id-1", phase=ExecutionPhase.ROLLBACK)
        report = eng.generate_report()
        assert isinstance(report, RunbookExecutionReport)
        assert report.total_records == 2
        assert report.total_steps == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable" in report.recommendations[0]

    def test_success_rate_computed(self):
        eng = _engine()
        eng.record_execution("rb-001", result=ExecutionResult.SUCCESS)
        eng.record_execution("rb-002", result=ExecutionResult.SUCCESS)
        report = eng.generate_report()
        assert report.success_rate_pct == 100.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_execution("rb-001")
        eng.add_step("exec-id-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._steps) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_executions"] == 0
        assert stats["total_steps"] == 0
        assert stats["result_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_execution("rb-001", result=ExecutionResult.SUCCESS)
        eng.record_execution("rb-002", result=ExecutionResult.FAILED)
        eng.add_step("exec-id-1")
        stats = eng.get_stats()
        assert stats["total_executions"] == 2
        assert stats["total_steps"] == 1
        assert stats["unique_runbooks"] == 2
