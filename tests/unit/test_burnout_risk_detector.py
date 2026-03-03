"""Tests for shieldops.analytics.burnout_risk_detector."""

from __future__ import annotations

from shieldops.analytics.burnout_risk_detector import (
    BurnoutAnalysis,
    BurnoutIndicator,
    BurnoutRecord,
    BurnoutReport,
    BurnoutRiskDetector,
    InterventionType,
    RiskLevel,
)


def _engine(**kw) -> BurnoutRiskDetector:
    return BurnoutRiskDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_indicator_overtime(self):
        assert BurnoutIndicator.OVERTIME == "overtime"

    def test_indicator_page_frequency(self):
        assert BurnoutIndicator.PAGE_FREQUENCY == "page_frequency"

    def test_indicator_context_switches(self):
        assert BurnoutIndicator.CONTEXT_SWITCHES == "context_switches"

    def test_indicator_meeting_load(self):
        assert BurnoutIndicator.MEETING_LOAD == "meeting_load"

    def test_indicator_incident_exposure(self):
        assert BurnoutIndicator.INCIDENT_EXPOSURE == "incident_exposure"

    def test_risk_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_moderate(self):
        assert RiskLevel.MODERATE == "moderate"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_minimal(self):
        assert RiskLevel.MINIMAL == "minimal"

    def test_intervention_immediate(self):
        assert InterventionType.IMMEDIATE == "immediate"

    def test_intervention_short_term(self):
        assert InterventionType.SHORT_TERM == "short_term"

    def test_intervention_medium_term(self):
        assert InterventionType.MEDIUM_TERM == "medium_term"

    def test_intervention_long_term(self):
        assert InterventionType.LONG_TERM == "long_term"

    def test_intervention_preventive(self):
        assert InterventionType.PREVENTIVE == "preventive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_burnout_record_defaults(self):
        r = BurnoutRecord()
        assert r.id
        assert r.engineer == ""
        assert r.team == ""
        assert r.burnout_indicator == BurnoutIndicator.OVERTIME
        assert r.risk_level == RiskLevel.MINIMAL
        assert r.intervention_type == InterventionType.PREVENTIVE
        assert r.risk_score == 0.0
        assert r.overtime_hours == 0.0
        assert r.created_at > 0

    def test_burnout_analysis_defaults(self):
        a = BurnoutAnalysis()
        assert a.id
        assert a.engineer == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_burnout_report_defaults(self):
        r = BurnoutReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_indicator == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_burnout / get_burnout
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_burnout(
            engineer="alice",
            team="sre",
            burnout_indicator=BurnoutIndicator.OVERTIME,
            risk_level=RiskLevel.HIGH,
            intervention_type=InterventionType.IMMEDIATE,
            risk_score=80.0,
            overtime_hours=20.0,
        )
        assert r.engineer == "alice"
        assert r.burnout_indicator == BurnoutIndicator.OVERTIME
        assert r.risk_score == 80.0
        assert r.overtime_hours == 20.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_burnout(engineer="bob", risk_score=60.0)
        found = eng.get_burnout(r.id)
        assert found is not None
        assert found.risk_score == 60.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_burnout("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_burnout(engineer=f"eng-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_burnouts
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_burnout(engineer="alice")
        eng.record_burnout(engineer="bob")
        assert len(eng.list_burnouts()) == 2

    def test_filter_by_indicator(self):
        eng = _engine()
        eng.record_burnout(engineer="alice", burnout_indicator=BurnoutIndicator.OVERTIME)
        eng.record_burnout(engineer="bob", burnout_indicator=BurnoutIndicator.MEETING_LOAD)
        results = eng.list_burnouts(burnout_indicator=BurnoutIndicator.OVERTIME)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_burnout(engineer="alice", team="sre")
        eng.record_burnout(engineer="bob", team="platform")
        results = eng.list_burnouts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_burnout(engineer=f"eng-{i}")
        assert len(eng.list_burnouts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            engineer="alice",
            burnout_indicator=BurnoutIndicator.PAGE_FREQUENCY,
            analysis_score=70.0,
            threshold=50.0,
            breached=True,
            description="high page rate",
        )
        assert a.engineer == "alice"
        assert a.analysis_score == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(engineer=f"eng-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(engineer="alice")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_burnout(
            engineer="alice",
            burnout_indicator=BurnoutIndicator.OVERTIME,
            risk_score=70.0,
        )
        eng.record_burnout(
            engineer="bob",
            burnout_indicator=BurnoutIndicator.OVERTIME,
            risk_score=50.0,
        )
        result = eng.analyze_distribution()
        assert "overtime" in result
        assert result["overtime"]["count"] == 2
        assert result["overtime"]["avg_risk_score"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_burnout_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_burnout(engineer="alice", risk_score=80.0)
        eng.record_burnout(engineer="bob", risk_score=40.0)
        results = eng.identify_burnout_gaps()
        assert len(results) == 1
        assert results[0]["engineer"] == "alice"

    def test_sorted_descending(self):
        eng = _engine(threshold=50.0)
        eng.record_burnout(engineer="alice", risk_score=90.0)
        eng.record_burnout(engineer="bob", risk_score=70.0)
        results = eng.identify_burnout_gaps()
        assert results[0]["risk_score"] == 90.0


# ---------------------------------------------------------------------------
# rank_by_risk
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_burnout(engineer="alice", risk_score=30.0)
        eng.record_burnout(engineer="bob", risk_score=80.0)
        results = eng.rank_by_risk()
        assert results[0]["engineer"] == "bob"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# ---------------------------------------------------------------------------
# detect_burnout_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(engineer="alice", analysis_score=50.0)
        result = eng.detect_burnout_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(engineer="a", analysis_score=20.0)
        eng.add_analysis(engineer="b", analysis_score=20.0)
        eng.add_analysis(engineer="c", analysis_score=80.0)
        eng.add_analysis(engineer="d", analysis_score=80.0)
        result = eng.detect_burnout_trends()
        assert result["trend"] == "worsening"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_burnout_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_burnout(
            engineer="alice",
            burnout_indicator=BurnoutIndicator.OVERTIME,
            risk_level=RiskLevel.CRITICAL,
            risk_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, BurnoutReport)
        assert report.total_records == 1
        assert report.gap_count == 1
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
        eng.record_burnout(engineer="alice")
        eng.add_analysis(engineer="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_burnout(engineer="alice", team="sre")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_engineers"] == 1
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(engineer=f"eng-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
