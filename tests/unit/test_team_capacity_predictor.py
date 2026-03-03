"""Tests for shieldops.analytics.team_capacity_predictor."""

from __future__ import annotations

from shieldops.analytics.team_capacity_predictor import (
    CapacityAnalysis,
    CapacityDimension,
    CapacityRecord,
    CapacityReport,
    PredictionHorizon,
    TeamCapacityPredictor,
    UtilizationLevel,
)


def _engine(**kw) -> TeamCapacityPredictor:
    return TeamCapacityPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_engineering(self):
        assert CapacityDimension.ENGINEERING == "engineering"

    def test_dimension_operations(self):
        assert CapacityDimension.OPERATIONS == "operations"

    def test_dimension_security(self):
        assert CapacityDimension.SECURITY == "security"

    def test_dimension_management(self):
        assert CapacityDimension.MANAGEMENT == "management"

    def test_dimension_support(self):
        assert CapacityDimension.SUPPORT == "support"

    def test_utilization_over(self):
        assert UtilizationLevel.OVER == "over"

    def test_utilization_high(self):
        assert UtilizationLevel.HIGH == "high"

    def test_utilization_optimal(self):
        assert UtilizationLevel.OPTIMAL == "optimal"

    def test_utilization_low(self):
        assert UtilizationLevel.LOW == "low"

    def test_utilization_idle(self):
        assert UtilizationLevel.IDLE == "idle"

    def test_horizon_week(self):
        assert PredictionHorizon.WEEK == "week"

    def test_horizon_month(self):
        assert PredictionHorizon.MONTH == "month"

    def test_horizon_quarter(self):
        assert PredictionHorizon.QUARTER == "quarter"

    def test_horizon_half_year(self):
        assert PredictionHorizon.HALF_YEAR == "half_year"

    def test_horizon_year(self):
        assert PredictionHorizon.YEAR == "year"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_capacity_record_defaults(self):
        r = CapacityRecord()
        assert r.id
        assert r.team == ""
        assert r.dimension == CapacityDimension.ENGINEERING
        assert r.utilization_level == UtilizationLevel.OPTIMAL
        assert r.horizon == PredictionHorizon.MONTH
        assert r.utilization_score == 0.0
        assert r.headcount == 0
        assert r.created_at > 0

    def test_capacity_analysis_defaults(self):
        a = CapacityAnalysis()
        assert a.id
        assert a.team == ""
        assert a.dimension == CapacityDimension.ENGINEERING
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_capacity_report_defaults(self):
        r = CapacityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_utilization_score == 0.0
        assert r.by_dimension == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_capacity / get_capacity
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_capacity(
            team="platform",
            dimension=CapacityDimension.SECURITY,
            utilization_level=UtilizationLevel.HIGH,
            horizon=PredictionHorizon.QUARTER,
            utilization_score=80.0,
            headcount=5,
        )
        assert r.team == "platform"
        assert r.dimension == CapacityDimension.SECURITY
        assert r.utilization_level == UtilizationLevel.HIGH
        assert r.utilization_score == 80.0
        assert r.headcount == 5

    def test_get_found(self):
        eng = _engine()
        r = eng.record_capacity(team="sre", utilization_score=70.0)
        found = eng.get_capacity(r.id)
        assert found is not None
        assert found.utilization_score == 70.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_capacity("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_capacity(team=f"team-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_capacities
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_capacity(team="sre")
        eng.record_capacity(team="platform")
        assert len(eng.list_capacities()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_capacity(team="sre", dimension=CapacityDimension.ENGINEERING)
        eng.record_capacity(team="noc", dimension=CapacityDimension.OPERATIONS)
        results = eng.list_capacities(dimension=CapacityDimension.ENGINEERING)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_capacity(team="sre")
        eng.record_capacity(team="platform")
        results = eng.list_capacities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_capacity(team=f"team-{i}")
        assert len(eng.list_capacities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            team="sre",
            dimension=CapacityDimension.SECURITY,
            analysis_score=75.0,
            threshold=50.0,
            breached=True,
            description="over capacity",
        )
        assert a.team == "sre"
        assert a.analysis_score == 75.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(team=f"team-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(team="sre")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_capacity(
            team="sre",
            dimension=CapacityDimension.ENGINEERING,
            utilization_score=80.0,
        )
        eng.record_capacity(
            team="noc",
            dimension=CapacityDimension.ENGINEERING,
            utilization_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "engineering" in result
        assert result["engineering"]["count"] == 2
        assert result["engineering"]["avg_utilization_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_capacity_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=70.0)
        eng.record_capacity(team="sre", utilization_score=40.0)
        eng.record_capacity(team="platform", utilization_score=90.0)
        results = eng.identify_capacity_gaps()
        assert len(results) == 1
        assert results[0]["team"] == "sre"

    def test_sorted_ascending(self):
        eng = _engine(threshold=70.0)
        eng.record_capacity(team="a", utilization_score=50.0)
        eng.record_capacity(team="b", utilization_score=30.0)
        results = eng.identify_capacity_gaps()
        assert results[0]["utilization_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_utilization
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_capacity(team="alpha", utilization_score=90.0)
        eng.record_capacity(team="beta", utilization_score=40.0)
        results = eng.rank_by_utilization()
        assert results[0]["team"] == "beta"
        assert results[0]["avg_utilization_score"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# ---------------------------------------------------------------------------
# detect_capacity_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(team="sre", analysis_score=50.0)
        result = eng.detect_capacity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(team="a", analysis_score=20.0)
        eng.add_analysis(team="b", analysis_score=20.0)
        eng.add_analysis(team="c", analysis_score=80.0)
        eng.add_analysis(team="d", analysis_score=80.0)
        result = eng.detect_capacity_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_capacity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=70.0)
        eng.record_capacity(
            team="sre",
            dimension=CapacityDimension.ENGINEERING,
            utilization_level=UtilizationLevel.LOW,
            utilization_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CapacityReport)
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
        eng.record_capacity(team="sre")
        eng.add_analysis(team="sre")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_capacity(team="sre", dimension=CapacityDimension.ENGINEERING)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "engineering" in stats["dimension_distribution"]
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(team=f"team-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
