"""Tests for shieldops.incidents.incident_replay — IncidentReplayEngine."""

from __future__ import annotations

from shieldops.incidents.incident_replay import (
    IncidentReplayEngine,
    IncidentReplayReport,
    ReplayFidelity,
    ReplayMode,
    ReplayOutcome,
    ReplayRecord,
    ReplayScenario,
)


def _engine(**kw) -> IncidentReplayEngine:
    return IncidentReplayEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ReplayMode (5)
    def test_mode_full_replay(self):
        assert ReplayMode.FULL_REPLAY == "full_replay"

    def test_mode_accelerated(self):
        assert ReplayMode.ACCELERATED == "accelerated"

    def test_mode_step_by_step(self):
        assert ReplayMode.STEP_BY_STEP == "step_by_step"

    def test_mode_summary(self):
        assert ReplayMode.SUMMARY == "summary"

    def test_mode_random_access(self):
        assert ReplayMode.RANDOM_ACCESS == "random_access"

    # ReplayFidelity (5)
    def test_fidelity_exact(self):
        assert ReplayFidelity.EXACT == "exact"

    def test_fidelity_high(self):
        assert ReplayFidelity.HIGH == "high"

    def test_fidelity_moderate(self):
        assert ReplayFidelity.MODERATE == "moderate"

    def test_fidelity_low(self):
        assert ReplayFidelity.LOW == "low"

    def test_fidelity_approximate(self):
        assert ReplayFidelity.APPROXIMATE == "approximate"

    # ReplayOutcome (5)
    def test_outcome_completed(self):
        assert ReplayOutcome.COMPLETED == "completed"

    def test_outcome_paused(self):
        assert ReplayOutcome.PAUSED == "paused"

    def test_outcome_failed(self):
        assert ReplayOutcome.FAILED == "failed"

    def test_outcome_skipped(self):
        assert ReplayOutcome.SKIPPED == "skipped"

    def test_outcome_timeout(self):
        assert ReplayOutcome.TIMEOUT == "timeout"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_replay_record_defaults(self):
        r = ReplayRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.mode == ReplayMode.FULL_REPLAY
        assert r.fidelity == ReplayFidelity.EXACT
        assert r.outcome == ReplayOutcome.COMPLETED
        assert r.effectiveness_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_replay_scenario_defaults(self):
        r = ReplayScenario()
        assert r.id
        assert r.scenario_name == ""
        assert r.mode == ReplayMode.FULL_REPLAY
        assert r.fidelity == ReplayFidelity.HIGH
        assert r.target_audience == ""
        assert r.max_participants == 10
        assert r.created_at > 0

    def test_incident_replay_report_defaults(self):
        r = IncidentReplayReport()
        assert r.total_replays == 0
        assert r.total_scenarios == 0
        assert r.completion_rate_pct == 0.0
        assert r.by_mode == {}
        assert r.by_outcome == {}
        assert r.failed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_replay
# -------------------------------------------------------------------


class TestRecordReplay:
    def test_basic(self):
        eng = _engine()
        r = eng.record_replay("INC-001", mode=ReplayMode.FULL_REPLAY)
        assert r.incident_id == "INC-001"
        assert r.mode == ReplayMode.FULL_REPLAY

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_replay(
            "INC-002",
            mode=ReplayMode.ACCELERATED,
            fidelity=ReplayFidelity.HIGH,
            outcome=ReplayOutcome.FAILED,
            effectiveness_score=75.0,
            details="Failed due to missing data",
        )
        assert r.outcome == ReplayOutcome.FAILED
        assert r.fidelity == ReplayFidelity.HIGH
        assert r.effectiveness_score == 75.0
        assert r.details == "Failed due to missing data"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_replay(f"INC-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_replay
# -------------------------------------------------------------------


class TestGetReplay:
    def test_found(self):
        eng = _engine()
        r = eng.record_replay("INC-001")
        assert eng.get_replay(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_replay("nonexistent") is None


# -------------------------------------------------------------------
# list_replays
# -------------------------------------------------------------------


class TestListReplays:
    def test_list_all(self):
        eng = _engine()
        eng.record_replay("INC-001")
        eng.record_replay("INC-002")
        assert len(eng.list_replays()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_replay("INC-001")
        eng.record_replay("INC-002")
        results = eng.list_replays(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"

    def test_filter_by_mode(self):
        eng = _engine()
        eng.record_replay("INC-001", mode=ReplayMode.FULL_REPLAY)
        eng.record_replay("INC-002", mode=ReplayMode.ACCELERATED)
        results = eng.list_replays(mode=ReplayMode.ACCELERATED)
        assert len(results) == 1
        assert results[0].incident_id == "INC-002"


# -------------------------------------------------------------------
# add_scenario
# -------------------------------------------------------------------


class TestAddScenario:
    def test_basic(self):
        eng = _engine()
        s = eng.add_scenario(
            "outage-drill",
            mode=ReplayMode.STEP_BY_STEP,
            fidelity=ReplayFidelity.HIGH,
            target_audience="SRE team",
            max_participants=20,
        )
        assert s.scenario_name == "outage-drill"
        assert s.mode == ReplayMode.STEP_BY_STEP
        assert s.max_participants == 20

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_scenario(f"scenario-{i}")
        assert len(eng._scenarios) == 2


# -------------------------------------------------------------------
# analyze_replay_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeReplayEffectiveness:
    def test_with_data(self):
        eng = _engine(min_effectiveness_pct=50.0)
        eng.record_replay("INC-001", outcome=ReplayOutcome.COMPLETED)
        eng.record_replay("INC-001", outcome=ReplayOutcome.COMPLETED)
        eng.record_replay("INC-001", outcome=ReplayOutcome.FAILED)
        result = eng.analyze_replay_effectiveness("INC-001")
        assert result["applied_rate"] == 66.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_replay_effectiveness("unknown")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_effectiveness_pct=50.0)
        eng.record_replay("INC-001", outcome=ReplayOutcome.COMPLETED)
        eng.record_replay("INC-001", outcome=ReplayOutcome.COMPLETED)
        result = eng.analyze_replay_effectiveness("INC-001")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_training_gaps
# -------------------------------------------------------------------


class TestIdentifyTrainingGaps:
    def test_with_gaps(self):
        eng = _engine()
        eng.record_replay("INC-001", outcome=ReplayOutcome.FAILED)
        eng.record_replay("INC-001", outcome=ReplayOutcome.TIMEOUT)
        eng.record_replay("INC-002", outcome=ReplayOutcome.COMPLETED)
        results = eng.identify_training_gaps()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"
        assert results[0]["failure_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_training_gaps() == []

    def test_single_failure_not_returned(self):
        eng = _engine()
        eng.record_replay("INC-001", outcome=ReplayOutcome.FAILED)
        assert eng.identify_training_gaps() == []


# -------------------------------------------------------------------
# rank_by_learning_value
# -------------------------------------------------------------------


class TestRankByLearningValue:
    def test_with_data(self):
        eng = _engine()
        eng.record_replay("INC-001", effectiveness_score=20.0)
        eng.record_replay("INC-002", effectiveness_score=90.0)
        results = eng.rank_by_learning_value()
        assert results[0]["incident_id"] == "INC-002"
        assert results[0]["avg_effectiveness_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_learning_value() == []


# -------------------------------------------------------------------
# detect_replay_patterns
# -------------------------------------------------------------------


class TestDetectReplayPatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_replay("INC-001")
        eng.record_replay("INC-002")
        results = eng.detect_replay_patterns()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"
        assert results[0]["replay_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_replay_patterns() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_replay("INC-001")
        assert eng.detect_replay_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_replay("INC-001", outcome=ReplayOutcome.FAILED)
        eng.record_replay("INC-002", outcome=ReplayOutcome.COMPLETED)
        eng.add_scenario("scenario-1")
        report = eng.generate_report()
        assert report.total_replays == 2
        assert report.total_scenarios == 1
        assert report.by_mode != {}
        assert report.by_outcome != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_replays == 0
        assert report.completion_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_replay("INC-001")
        eng.add_scenario("scenario-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._scenarios) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_replays"] == 0
        assert stats["total_scenarios"] == 0
        assert stats["mode_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_effectiveness_pct=70.0)
        eng.record_replay("INC-001", mode=ReplayMode.FULL_REPLAY)
        eng.record_replay("INC-002", mode=ReplayMode.ACCELERATED)
        eng.add_scenario("scenario-1")
        stats = eng.get_stats()
        assert stats["total_replays"] == 2
        assert stats["total_scenarios"] == 1
        assert stats["unique_incidents"] == 2
        assert stats["min_effectiveness_pct"] == 70.0
