"""Tests for shieldops.operations.gameday_execution_engine."""

from __future__ import annotations

from shieldops.operations.gameday_execution_engine import (
    GamedayAnalysis,
    GamedayExecutionEngine,
    GamedayExecutionReport,
    GamedayPhase,
    GamedaySession,
    ParticipantRole,
    ScenarioComplexity,
)


def _engine(**kw) -> GamedayExecutionEngine:
    return GamedayExecutionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_phase_planning(self):
        assert GamedayPhase.PLANNING == "planning"

    def test_phase_briefing(self):
        assert GamedayPhase.BRIEFING == "briefing"

    def test_phase_execution(self):
        assert GamedayPhase.EXECUTION == "execution"

    def test_phase_observation(self):
        assert GamedayPhase.OBSERVATION == "observation"

    def test_phase_debrief(self):
        assert GamedayPhase.DEBRIEF == "debrief"

    def test_complexity_simple(self):
        assert ScenarioComplexity.SIMPLE == "simple"

    def test_complexity_moderate(self):
        assert ScenarioComplexity.MODERATE == "moderate"

    def test_complexity_complex(self):
        assert ScenarioComplexity.COMPLEX == "complex"

    def test_complexity_multi_system(self):
        assert ScenarioComplexity.MULTI_SYSTEM == "multi_system"

    def test_complexity_enterprise(self):
        assert ScenarioComplexity.ENTERPRISE == "enterprise"

    def test_role_facilitator(self):
        assert ParticipantRole.FACILITATOR == "facilitator"

    def test_role_observer(self):
        assert ParticipantRole.OBSERVER == "observer"

    def test_role_responder(self):
        assert ParticipantRole.RESPONDER == "responder"

    def test_role_stakeholder(self):
        assert ParticipantRole.STAKEHOLDER == "stakeholder"

    def test_role_scribe(self):
        assert ParticipantRole.SCRIBE == "scribe"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_gameday_session_defaults(self):
        r = GamedaySession()
        assert r.id
        assert r.phase == GamedayPhase.PLANNING
        assert r.complexity == ScenarioComplexity.MODERATE
        assert r.participant_role == ParticipantRole.RESPONDER
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_gameday_analysis_defaults(self):
        a = GamedayAnalysis()
        assert a.id
        assert a.phase == GamedayPhase.PLANNING
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_gameday_execution_report_defaults(self):
        r = GamedayExecutionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_phase == {}
        assert r.by_complexity == {}
        assert r.by_role == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._threshold == 50.0
        assert eng._records == []
        assert eng._analyses == []

    def test_custom_max_records(self):
        eng = _engine(max_records=6000)
        assert eng._max_records == 6000

    def test_custom_threshold(self):
        eng = _engine(threshold=65.0)
        assert eng._threshold == 65.0


# ---------------------------------------------------------------------------
# record_session / get_session
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_session(
            service="platform-gd",
            phase=GamedayPhase.EXECUTION,
            complexity=ScenarioComplexity.ENTERPRISE,
            participant_role=ParticipantRole.FACILITATOR,
            score=82.0,
            team="sre",
        )
        assert r.service == "platform-gd"
        assert r.phase == GamedayPhase.EXECUTION
        assert r.complexity == ScenarioComplexity.ENTERPRISE
        assert r.participant_role == ParticipantRole.FACILITATOR
        assert r.score == 82.0
        assert r.team == "sre"

    def test_record_stored(self):
        eng = _engine()
        eng.record_session(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_session(service="svc-a", score=68.0)
        result = eng.get_session(r.id)
        assert result is not None
        assert result.score == 68.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_session("nonexistent") is None


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_session(service="svc-a")
        eng.record_session(service="svc-b")
        assert len(eng.list_sessions()) == 2

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_session(service="svc-a", phase=GamedayPhase.PLANNING)
        eng.record_session(service="svc-b", phase=GamedayPhase.DEBRIEF)
        results = eng.list_sessions(phase=GamedayPhase.PLANNING)
        assert len(results) == 1

    def test_filter_by_complexity(self):
        eng = _engine()
        eng.record_session(service="svc-a", complexity=ScenarioComplexity.SIMPLE)
        eng.record_session(service="svc-b", complexity=ScenarioComplexity.COMPLEX)
        results = eng.list_sessions(complexity=ScenarioComplexity.SIMPLE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_session(service="svc-a", team="sre")
        eng.record_session(service="svc-b", team="security")
        assert len(eng.list_sessions(team="sre")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_session(service=f"svc-{i}")
        assert len(eng.list_sessions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            phase=GamedayPhase.OBSERVATION,
            analysis_score=55.0,
            threshold=50.0,
            breached=True,
            description="observation gaps noted",
        )
        assert a.phase == GamedayPhase.OBSERVATION
        assert a.analysis_score == 55.0
        assert a.breached is True

    def test_stored(self):
        eng = _engine()
        eng.add_analysis()
        assert len(eng._analyses) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _ in range(5):
            eng.add_analysis()
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_session(service="s1", phase=GamedayPhase.EXECUTION, score=80.0)
        eng.record_session(service="s2", phase=GamedayPhase.EXECUTION, score=60.0)
        result = eng.analyze_distribution()
        assert "execution" in result
        assert result["execution"]["count"] == 2
        assert result["execution"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_readiness_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_session(service="svc-a", score=60.0)
        eng.record_session(service="svc-b", score=90.0)
        results = eng.identify_readiness_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_session(service="svc-a", score=55.0)
        eng.record_session(service="svc-b", score=35.0)
        results = eng.identify_readiness_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_session(service="svc-a", score=90.0)
        eng.record_session(service="svc-b", score=40.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_score_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_score_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_session(
            service="svc-a",
            phase=GamedayPhase.BRIEFING,
            complexity=ScenarioComplexity.MULTI_SYSTEM,
            participant_role=ParticipantRole.SCRIBE,
            score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, GamedayExecutionReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_session(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_session(
            service="svc-a",
            phase=GamedayPhase.PLANNING,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "planning" in stats["phase_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_session(service=f"svc-{i}")
        assert len(eng._records) == 3
