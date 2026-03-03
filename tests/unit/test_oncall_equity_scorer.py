"""Tests for shieldops.operations.oncall_equity_scorer."""

from __future__ import annotations

from shieldops.operations.oncall_equity_scorer import (
    CompensationType,
    EquityAnalysis,
    EquityMetric,
    EquityRecord,
    EquityReport,
    FairnessLevel,
    OncallEquityScorer,
)


def _engine(**kw) -> OncallEquityScorer:
    return OncallEquityScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_page_distribution(self):
        assert EquityMetric.PAGE_DISTRIBUTION == "page_distribution"

    def test_metric_hours_worked(self):
        assert EquityMetric.HOURS_WORKED == "hours_worked"

    def test_metric_weekend_ratio(self):
        assert EquityMetric.WEEKEND_RATIO == "weekend_ratio"

    def test_metric_night_ratio(self):
        assert EquityMetric.NIGHT_RATIO == "night_ratio"

    def test_metric_incident_severity(self):
        assert EquityMetric.INCIDENT_SEVERITY == "incident_severity"

    def test_fairness_equitable(self):
        assert FairnessLevel.EQUITABLE == "equitable"

    def test_fairness_slight_imbalance(self):
        assert FairnessLevel.SLIGHT_IMBALANCE == "slight_imbalance"

    def test_fairness_moderate_imbalance(self):
        assert FairnessLevel.MODERATE_IMBALANCE == "moderate_imbalance"

    def test_fairness_severe_imbalance(self):
        assert FairnessLevel.SEVERE_IMBALANCE == "severe_imbalance"

    def test_fairness_critical(self):
        assert FairnessLevel.CRITICAL == "critical"

    def test_compensation_time_off(self):
        assert CompensationType.TIME_OFF == "time_off"

    def test_compensation_bonus(self):
        assert CompensationType.BONUS == "bonus"

    def test_compensation_rotation(self):
        assert CompensationType.ROTATION == "rotation"

    def test_compensation_reduced_load(self):
        assert CompensationType.REDUCED_LOAD == "reduced_load"

    def test_compensation_none(self):
        assert CompensationType.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_equity_record_defaults(self):
        r = EquityRecord()
        assert r.id
        assert r.engineer == ""
        assert r.team == ""
        assert r.equity_metric == EquityMetric.PAGE_DISTRIBUTION
        assert r.fairness_level == FairnessLevel.EQUITABLE
        assert r.compensation_type == CompensationType.NONE
        assert r.equity_score == 0.0
        assert r.page_count == 0
        assert r.created_at > 0

    def test_equity_analysis_defaults(self):
        a = EquityAnalysis()
        assert a.id
        assert a.engineer == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_equity_report_defaults(self):
        r = EquityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_equity_score == 0.0
        assert r.by_metric == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_equity / get_equity
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_equity(
            engineer="alice",
            team="sre",
            equity_metric=EquityMetric.NIGHT_RATIO,
            fairness_level=FairnessLevel.SEVERE_IMBALANCE,
            compensation_type=CompensationType.TIME_OFF,
            equity_score=30.0,
            page_count=42,
        )
        assert r.engineer == "alice"
        assert r.equity_metric == EquityMetric.NIGHT_RATIO
        assert r.equity_score == 30.0
        assert r.page_count == 42

    def test_get_found(self):
        eng = _engine()
        r = eng.record_equity(engineer="bob", equity_score=55.0)
        found = eng.get_equity(r.id)
        assert found is not None
        assert found.equity_score == 55.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_equity("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_equity(engineer=f"eng-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_equities
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_equity(engineer="alice")
        eng.record_equity(engineer="bob")
        assert len(eng.list_equities()) == 2

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_equity(engineer="alice", equity_metric=EquityMetric.PAGE_DISTRIBUTION)
        eng.record_equity(engineer="bob", equity_metric=EquityMetric.NIGHT_RATIO)
        results = eng.list_equities(equity_metric=EquityMetric.PAGE_DISTRIBUTION)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_equity(engineer="alice", team="sre")
        eng.record_equity(engineer="bob", team="platform")
        results = eng.list_equities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_equity(engineer=f"eng-{i}")
        assert len(eng.list_equities(limit=4)) == 4


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            engineer="alice",
            equity_metric=EquityMetric.WEEKEND_RATIO,
            analysis_score=25.0,
            threshold=50.0,
            breached=True,
            description="weekend imbalance",
        )
        assert a.engineer == "alice"
        assert a.analysis_score == 25.0
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
        eng.record_equity(
            engineer="alice",
            equity_metric=EquityMetric.PAGE_DISTRIBUTION,
            equity_score=60.0,
        )
        eng.record_equity(
            engineer="bob",
            equity_metric=EquityMetric.PAGE_DISTRIBUTION,
            equity_score=40.0,
        )
        result = eng.analyze_distribution()
        assert "page_distribution" in result
        assert result["page_distribution"]["count"] == 2
        assert result["page_distribution"]["avg_equity_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_equity_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_equity(engineer="alice", equity_score=30.0)
        eng.record_equity(engineer="bob", equity_score=80.0)
        results = eng.identify_equity_gaps()
        assert len(results) == 1
        assert results[0]["engineer"] == "alice"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_equity(engineer="alice", equity_score=50.0)
        eng.record_equity(engineer="bob", equity_score=20.0)
        results = eng.identify_equity_gaps()
        assert results[0]["equity_score"] == 20.0


# ---------------------------------------------------------------------------
# rank_by_equity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_equity(engineer="alice", equity_score=80.0)
        eng.record_equity(engineer="bob", equity_score=30.0)
        results = eng.rank_by_equity()
        assert results[0]["engineer"] == "bob"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_equity() == []


# ---------------------------------------------------------------------------
# detect_equity_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(engineer="alice", analysis_score=50.0)
        result = eng.detect_equity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(engineer="a", analysis_score=20.0)
        eng.add_analysis(engineer="b", analysis_score=20.0)
        eng.add_analysis(engineer="c", analysis_score=80.0)
        eng.add_analysis(engineer="d", analysis_score=80.0)
        result = eng.detect_equity_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_equity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_equity(
            engineer="alice",
            equity_metric=EquityMetric.PAGE_DISTRIBUTION,
            fairness_level=FairnessLevel.CRITICAL,
            equity_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, EquityReport)
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
        eng.record_equity(engineer="alice")
        eng.add_analysis(engineer="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_equity(engineer="alice", team="sre")
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
