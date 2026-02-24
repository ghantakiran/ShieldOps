"""Tests for shieldops.operations.runbook_effectiveness — RunbookEffectivenessAnalyzer.

Covers EffectivenessRating, FailureReason, and ImprovementType enums,
RunbookOutcome / EffectivenessScore / EffectivenessReport models, and all
RunbookEffectivenessAnalyzer operations including outcome recording,
effectiveness scoring, decay detection, failure analysis, improvement
suggestions, ranking, and report generation.
"""

from __future__ import annotations

from shieldops.operations.runbook_effectiveness import (
    EffectivenessRating,
    EffectivenessReport,
    EffectivenessScore,
    FailureReason,
    ImprovementType,
    RunbookEffectivenessAnalyzer,
    RunbookOutcome,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> RunbookEffectivenessAnalyzer:
    return RunbookEffectivenessAnalyzer(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of EffectivenessRating, FailureReason, and ImprovementType."""

    # -- EffectivenessRating (5 members) --------------------------------------

    def test_rating_excellent(self):
        assert EffectivenessRating.EXCELLENT == "excellent"

    def test_rating_good(self):
        assert EffectivenessRating.GOOD == "good"

    def test_rating_fair(self):
        assert EffectivenessRating.FAIR == "fair"

    def test_rating_poor(self):
        assert EffectivenessRating.POOR == "poor"

    def test_rating_ineffective(self):
        assert EffectivenessRating.INEFFECTIVE == "ineffective"

    # -- FailureReason (6 members) --------------------------------------------

    def test_failure_outdated_steps(self):
        assert FailureReason.OUTDATED_STEPS == "outdated_steps"

    def test_failure_missing_context(self):
        assert FailureReason.MISSING_CONTEXT == "missing_context"

    def test_failure_wrong_diagnosis(self):
        assert FailureReason.WRONG_DIAGNOSIS == "wrong_diagnosis"

    def test_failure_permission_error(self):
        assert FailureReason.PERMISSION_ERROR == "permission_error"

    def test_failure_timeout(self):
        assert FailureReason.TIMEOUT == "timeout"

    def test_failure_infrastructure_change(self):
        assert FailureReason.INFRASTRUCTURE_CHANGE == "infrastructure_change"

    # -- ImprovementType (5 members) ------------------------------------------

    def test_improvement_add_step(self):
        assert ImprovementType.ADD_STEP == "add_step"

    def test_improvement_remove_step(self):
        assert ImprovementType.REMOVE_STEP == "remove_step"

    def test_improvement_update_command(self):
        assert ImprovementType.UPDATE_COMMAND == "update_command"

    def test_improvement_add_validation(self):
        assert ImprovementType.ADD_VALIDATION == "add_validation"

    def test_improvement_automate(self):
        assert ImprovementType.AUTOMATE == "automate"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_runbook_outcome_defaults(self):
        o = RunbookOutcome()
        assert o.id
        assert o.runbook_id == ""
        assert o.runbook_name == ""
        assert o.executed_by == ""
        assert o.success is True
        assert o.execution_time_seconds == 0.0
        assert o.failure_reason is None
        assert o.notes == ""
        assert o.executed_at > 0

    def test_effectiveness_score_defaults(self):
        s = EffectivenessScore()
        assert s.id
        assert s.runbook_id == ""
        assert s.runbook_name == ""
        assert s.total_executions == 0
        assert s.success_count == 0
        assert s.avg_execution_time == 0.0
        assert s.success_rate == 0.0
        assert s.rating == EffectivenessRating.FAIR
        assert s.trend == "stable"
        assert s.calculated_at > 0

    def test_effectiveness_report_defaults(self):
        r = EffectivenessReport()
        assert r.total_runbooks == 0
        assert r.total_executions == 0
        assert r.avg_success_rate == 0.0
        assert r.decaying_count == 0
        assert r.rating_distribution == {}
        assert r.top_failure_reasons == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# RecordOutcome
# ===========================================================================


class TestRecordOutcome:
    """Test RunbookEffectivenessAnalyzer.record_outcome."""

    def test_basic_outcome(self):
        eng = _engine()
        o = eng.record_outcome(
            runbook_id="rb-001",
            runbook_name="Restart Service",
            executed_by="alice",
            success=True,
            execution_time_seconds=45.0,
            notes="Completed without issues",
        )
        assert o.id
        assert o.runbook_id == "rb-001"
        assert o.runbook_name == "Restart Service"
        assert o.executed_by == "alice"
        assert o.success is True
        assert o.execution_time_seconds == 45.0
        assert o.notes == "Completed without issues"

    def test_eviction_on_overflow(self):
        eng = _engine(max_outcomes=2)
        eng.record_outcome(runbook_id="rb-1", runbook_name="RB1", executed_by="a")
        eng.record_outcome(runbook_id="rb-2", runbook_name="RB2", executed_by="b")
        o3 = eng.record_outcome(runbook_id="rb-3", runbook_name="RB3", executed_by="c")
        outcomes = eng.list_outcomes(limit=10)
        assert len(outcomes) == 2
        assert outcomes[-1].id == o3.id


# ===========================================================================
# GetOutcome
# ===========================================================================


class TestGetOutcome:
    """Test RunbookEffectivenessAnalyzer.get_outcome."""

    def test_found(self):
        eng = _engine()
        o = eng.record_outcome(
            runbook_id="rb-001",
            runbook_name="Scale Up",
            executed_by="bob",
        )
        assert eng.get_outcome(o.id) is o

    def test_not_found(self):
        eng = _engine()
        assert eng.get_outcome("nonexistent-id") is None


# ===========================================================================
# ListOutcomes
# ===========================================================================


class TestListOutcomes:
    """Test RunbookEffectivenessAnalyzer.list_outcomes with various filters."""

    def test_all_outcomes(self):
        eng = _engine()
        eng.record_outcome(runbook_id="rb-1", runbook_name="RB1", executed_by="a")
        eng.record_outcome(runbook_id="rb-2", runbook_name="RB2", executed_by="b")
        assert len(eng.list_outcomes()) == 2

    def test_filter_by_runbook_id(self):
        eng = _engine()
        eng.record_outcome(runbook_id="rb-1", runbook_name="RB1", executed_by="a")
        eng.record_outcome(runbook_id="rb-2", runbook_name="RB2", executed_by="b")
        eng.record_outcome(runbook_id="rb-1", runbook_name="RB1", executed_by="c")
        results = eng.list_outcomes(runbook_id="rb-1")
        assert len(results) == 2
        assert all(o.runbook_id == "rb-1" for o in results)

    def test_filter_by_success(self):
        eng = _engine()
        eng.record_outcome(
            runbook_id="rb-1",
            runbook_name="RB1",
            executed_by="a",
            success=True,
        )
        eng.record_outcome(
            runbook_id="rb-2",
            runbook_name="RB2",
            executed_by="b",
            success=False,
            failure_reason=FailureReason.TIMEOUT,
        )
        successes = eng.list_outcomes(success=True)
        assert len(successes) == 1
        assert successes[0].success is True
        failures = eng.list_outcomes(success=False)
        assert len(failures) == 1
        assert failures[0].success is False


# ===========================================================================
# CalculateEffectiveness
# ===========================================================================


class TestCalculateEffectiveness:
    """Test RunbookEffectivenessAnalyzer.calculate_effectiveness."""

    def test_high_success_rate_excellent(self):
        eng = _engine()
        for _ in range(10):
            eng.record_outcome(
                runbook_id="rb-1",
                runbook_name="Restart",
                executed_by="ops",
                success=True,
                execution_time_seconds=30.0,
            )
        score = eng.calculate_effectiveness("rb-1")
        assert score.runbook_id == "rb-1"
        assert score.total_executions == 10
        assert score.success_count == 10
        assert score.success_rate == 100.0
        assert score.rating == EffectivenessRating.EXCELLENT

    def test_low_success_rate_poor(self):
        eng = _engine()
        # 2 successes + 3 failures = 40% -> POOR
        for _ in range(2):
            eng.record_outcome(
                runbook_id="rb-2",
                runbook_name="FailProne",
                executed_by="ops",
                success=True,
                execution_time_seconds=10.0,
            )
        for _ in range(3):
            eng.record_outcome(
                runbook_id="rb-2",
                runbook_name="FailProne",
                executed_by="ops",
                success=False,
                execution_time_seconds=60.0,
                failure_reason=FailureReason.TIMEOUT,
            )
        score = eng.calculate_effectiveness("rb-2")
        assert score.success_rate == 40.0
        assert score.rating == EffectivenessRating.POOR


# ===========================================================================
# DetectRunbookDecay
# ===========================================================================


class TestDetectRunbookDecay:
    """Test RunbookEffectivenessAnalyzer.detect_runbook_decay."""

    def test_decaying_runbook(self):
        eng = _engine(decay_window_days=365)
        # Older half: all successes
        for _ in range(4):
            eng.record_outcome(
                runbook_id="rb-decay",
                runbook_name="Decaying",
                executed_by="ops",
                success=True,
                execution_time_seconds=10.0,
            )
        # Recent half: all failures -> declining trend
        for _ in range(4):
            eng.record_outcome(
                runbook_id="rb-decay",
                runbook_name="Decaying",
                executed_by="ops",
                success=False,
                execution_time_seconds=60.0,
                failure_reason=FailureReason.OUTDATED_STEPS,
            )
        decaying = eng.detect_runbook_decay()
        assert len(decaying) >= 1
        assert decaying[0].runbook_id == "rb-decay"
        assert decaying[0].trend == "declining"


# ===========================================================================
# AnalyzeFailurePatterns
# ===========================================================================


class TestAnalyzeFailurePatterns:
    """Test RunbookEffectivenessAnalyzer.analyze_failure_patterns."""

    def test_multiple_failure_reasons(self):
        eng = _engine()
        for _ in range(3):
            eng.record_outcome(
                runbook_id="rb-1",
                runbook_name="RB1",
                executed_by="ops",
                success=False,
                failure_reason=FailureReason.OUTDATED_STEPS,
            )
        eng.record_outcome(
            runbook_id="rb-2",
            runbook_name="RB2",
            executed_by="ops",
            success=False,
            failure_reason=FailureReason.TIMEOUT,
        )
        patterns = eng.analyze_failure_patterns()
        assert len(patterns) == 2
        # Sorted by count descending
        assert patterns[0]["failure_reason"] == "outdated_steps"
        assert patterns[0]["count"] == 3
        assert patterns[1]["failure_reason"] == "timeout"
        assert patterns[1]["count"] == 1
        assert patterns[0]["pct_of_failures"] == 75.0


# ===========================================================================
# SuggestImprovements
# ===========================================================================


class TestSuggestImprovements:
    """Test RunbookEffectivenessAnalyzer.suggest_improvements."""

    def test_runbook_with_outdated_steps_failures(self):
        eng = _engine()
        for _ in range(3):
            eng.record_outcome(
                runbook_id="rb-old",
                runbook_name="OldRunbook",
                executed_by="ops",
                success=False,
                failure_reason=FailureReason.OUTDATED_STEPS,
            )
        suggestions = eng.suggest_improvements("rb-old")
        assert len(suggestions) >= 1
        s = suggestions[0]
        assert s["failure_reason"] == "outdated_steps"
        assert s["improvement_type"] == "update_command"
        assert s["occurrence_count"] == 3
        assert s["priority"] == "high"


# ===========================================================================
# RankRunbooks
# ===========================================================================


class TestRankRunbooks:
    """Test RunbookEffectivenessAnalyzer.rank_runbooks_by_effectiveness."""

    def test_multiple_runbooks_ranked(self):
        eng = _engine()
        # rb-good: 100% success
        for _ in range(5):
            eng.record_outcome(
                runbook_id="rb-good",
                runbook_name="GoodRB",
                executed_by="ops",
                success=True,
            )
        # rb-bad: 0% success
        for _ in range(5):
            eng.record_outcome(
                runbook_id="rb-bad",
                runbook_name="BadRB",
                executed_by="ops",
                success=False,
                failure_reason=FailureReason.WRONG_DIAGNOSIS,
            )
        ranked = eng.rank_runbooks_by_effectiveness()
        assert len(ranked) == 2
        assert ranked[0].runbook_id == "rb-good"
        assert ranked[0].success_rate == 100.0
        assert ranked[1].runbook_id == "rb-bad"
        assert ranked[1].success_rate == 0.0


# ===========================================================================
# GenerateEffectivenessReport
# ===========================================================================


class TestGenerateEffectivenessReport:
    """Test RunbookEffectivenessAnalyzer.generate_effectiveness_report."""

    def test_basic_report(self):
        eng = _engine()
        for _ in range(5):
            eng.record_outcome(
                runbook_id="rb-1",
                runbook_name="Scale",
                executed_by="ops",
                success=True,
                execution_time_seconds=20.0,
            )
        eng.record_outcome(
            runbook_id="rb-2",
            runbook_name="Restart",
            executed_by="ops",
            success=False,
            failure_reason=FailureReason.TIMEOUT,
        )
        report = eng.generate_effectiveness_report()
        assert isinstance(report, EffectivenessReport)
        assert report.total_runbooks == 2
        assert report.total_executions == 6
        assert report.avg_success_rate > 0
        assert report.generated_at > 0
        assert len(report.rating_distribution) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test RunbookEffectivenessAnalyzer.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.record_outcome(runbook_id="rb-1", runbook_name="RB1", executed_by="ops")
        eng.clear_data()
        assert len(eng.list_outcomes()) == 0
        stats = eng.get_stats()
        assert stats["total_outcomes"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test RunbookEffectivenessAnalyzer.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_outcomes"] == 0
        assert stats["unique_runbooks"] == 0
        assert stats["unique_executors"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_count"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_outcome(
            runbook_id="rb-1",
            runbook_name="RB1",
            executed_by="alice",
            success=True,
        )
        eng.record_outcome(
            runbook_id="rb-2",
            runbook_name="RB2",
            executed_by="bob",
            success=False,
            failure_reason=FailureReason.PERMISSION_ERROR,
        )
        stats = eng.get_stats()
        assert stats["total_outcomes"] == 2
        assert stats["unique_runbooks"] == 2
        assert stats["unique_executors"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
