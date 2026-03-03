"""Tests for shieldops.sla.availability_impact_modeler."""

from __future__ import annotations

from shieldops.sla.availability_impact_modeler import (
    AvailabilityImpact,
    AvailabilityImpactModeler,
    AvailabilityImpactReport,
    ImpactAnalysis,
    ImpactDuration,
    ModelingApproach,
    SeverityTier,
)


def _engine(**kw) -> AvailabilityImpactModeler:
    return AvailabilityImpactModeler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_duration_minutes(self):
        assert ImpactDuration.MINUTES == "minutes"

    def test_duration_hours(self):
        assert ImpactDuration.HOURS == "hours"

    def test_duration_half_day(self):
        assert ImpactDuration.HALF_DAY == "half_day"

    def test_duration_full_day(self):
        assert ImpactDuration.FULL_DAY == "full_day"

    def test_duration_multi_day(self):
        assert ImpactDuration.MULTI_DAY == "multi_day"

    def test_severity_p1(self):
        assert SeverityTier.P1 == "p1"

    def test_severity_p2(self):
        assert SeverityTier.P2 == "p2"

    def test_severity_p3(self):
        assert SeverityTier.P3 == "p3"

    def test_severity_p4(self):
        assert SeverityTier.P4 == "p4"

    def test_severity_p5(self):
        assert SeverityTier.P5 == "p5"

    def test_approach_historical(self):
        assert ModelingApproach.HISTORICAL == "historical"

    def test_approach_simulation(self):
        assert ModelingApproach.SIMULATION == "simulation"

    def test_approach_statistical(self):
        assert ModelingApproach.STATISTICAL == "statistical"

    def test_approach_ml_based(self):
        assert ModelingApproach.ML_BASED == "ml_based"

    def test_approach_expert(self):
        assert ModelingApproach.EXPERT == "expert"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_availability_impact_defaults(self):
        r = AvailabilityImpact()
        assert r.id
        assert r.impact_duration == ImpactDuration.MINUTES
        assert r.severity_tier == SeverityTier.P3
        assert r.modeling_approach == ModelingApproach.HISTORICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_analysis_defaults(self):
        a = ImpactAnalysis()
        assert a.id
        assert a.impact_duration == ImpactDuration.MINUTES
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_availability_impact_report_defaults(self):
        r = AvailabilityImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_duration == {}
        assert r.by_severity == {}
        assert r.by_approach == {}
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
        eng = _engine(max_records=4000)
        assert eng._max_records == 4000

    def test_custom_threshold(self):
        eng = _engine(threshold=60.0)
        assert eng._threshold == 60.0


# ---------------------------------------------------------------------------
# record_impact / get_impact
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_impact(
            service="checkout-svc",
            impact_duration=ImpactDuration.HOURS,
            severity_tier=SeverityTier.P1,
            modeling_approach=ModelingApproach.ML_BASED,
            score=88.0,
            team="sre",
        )
        assert r.service == "checkout-svc"
        assert r.impact_duration == ImpactDuration.HOURS
        assert r.severity_tier == SeverityTier.P1
        assert r.modeling_approach == ModelingApproach.ML_BASED
        assert r.score == 88.0
        assert r.team == "sre"

    def test_record_stored(self):
        eng = _engine()
        eng.record_impact(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_impact(service="svc-a", score=72.0)
        result = eng.get_impact(r.id)
        assert result is not None
        assert result.score == 72.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# ---------------------------------------------------------------------------
# list_impacts
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact(service="svc-a")
        eng.record_impact(service="svc-b")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_duration(self):
        eng = _engine()
        eng.record_impact(service="svc-a", impact_duration=ImpactDuration.MINUTES)
        eng.record_impact(service="svc-b", impact_duration=ImpactDuration.FULL_DAY)
        results = eng.list_impacts(impact_duration=ImpactDuration.MINUTES)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_impact(service="svc-a", severity_tier=SeverityTier.P1)
        eng.record_impact(service="svc-b", severity_tier=SeverityTier.P5)
        results = eng.list_impacts(severity_tier=SeverityTier.P1)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_impact(service="svc-a", team="sre")
        eng.record_impact(service="svc-b", team="platform")
        assert len(eng.list_impacts(team="sre")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_impact(service=f"svc-{i}")
        assert len(eng.list_impacts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            impact_duration=ImpactDuration.MULTI_DAY,
            analysis_score=30.0,
            threshold=50.0,
            breached=True,
            description="multi-day impact detected",
        )
        assert a.impact_duration == ImpactDuration.MULTI_DAY
        assert a.analysis_score == 30.0
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
        eng.record_impact(service="s1", impact_duration=ImpactDuration.HOURS, score=80.0)
        eng.record_impact(service="s2", impact_duration=ImpactDuration.HOURS, score=60.0)
        result = eng.analyze_distribution()
        assert "hours" in result
        assert result["hours"]["count"] == 2
        assert result["hours"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_sla_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_impact(service="svc-a", score=60.0)
        eng.record_impact(service="svc-b", score=90.0)
        results = eng.identify_sla_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_impact(service="svc-a", score=55.0)
        eng.record_impact(service="svc-b", score=35.0)
        results = eng.identify_sla_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_impact(service="svc-a", score=90.0)
        eng.record_impact(service="svc-b", score=40.0)
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
        eng.record_impact(
            service="svc-a",
            impact_duration=ImpactDuration.FULL_DAY,
            severity_tier=SeverityTier.P2,
            modeling_approach=ModelingApproach.STATISTICAL,
            score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AvailabilityImpactReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_impact(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_impact(
            service="svc-a",
            impact_duration=ImpactDuration.MINUTES,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "minutes" in stats["duration_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(service=f"svc-{i}")
        assert len(eng._records) == 3
