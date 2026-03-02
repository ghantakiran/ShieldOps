"""Tests for shieldops.sla.slo_cross_correlation — SLOCrossCorrelation."""

from __future__ import annotations

from shieldops.sla.slo_cross_correlation import (
    CorrelationAnalysis,
    CorrelationRecord,
    CorrelationStrength,
    CorrelationType,
    SLOCategory,
    SLOCrossCorrelation,
    SLOCrossCorrelationReport,
)


def _engine(**kw) -> SLOCrossCorrelation:
    return SLOCrossCorrelation(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_positive(self):
        assert CorrelationType.POSITIVE == "positive"

    def test_type_negative(self):
        assert CorrelationType.NEGATIVE == "negative"

    def test_type_causal(self):
        assert CorrelationType.CAUSAL == "causal"

    def test_type_coincidental(self):
        assert CorrelationType.COINCIDENTAL == "coincidental"

    def test_type_unknown(self):
        assert CorrelationType.UNKNOWN == "unknown"

    def test_strength_very_strong(self):
        assert CorrelationStrength.VERY_STRONG == "very_strong"

    def test_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_strength_negligible(self):
        assert CorrelationStrength.NEGLIGIBLE == "negligible"

    def test_category_availability(self):
        assert SLOCategory.AVAILABILITY == "availability"

    def test_category_latency(self):
        assert SLOCategory.LATENCY == "latency"

    def test_category_throughput(self):
        assert SLOCategory.THROUGHPUT == "throughput"

    def test_category_error_rate(self):
        assert SLOCategory.ERROR_RATE == "error_rate"

    def test_category_saturation(self):
        assert SLOCategory.SATURATION == "saturation"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_correlation_record_defaults(self):
        r = CorrelationRecord()
        assert r.id
        assert r.slo_pair_name == ""
        assert r.correlation_type == CorrelationType.POSITIVE
        assert r.correlation_strength == CorrelationStrength.VERY_STRONG
        assert r.slo_category == SLOCategory.AVAILABILITY
        assert r.correlation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_correlation_analysis_defaults(self):
        a = CorrelationAnalysis()
        assert a.id
        assert a.slo_pair_name == ""
        assert a.correlation_type == CorrelationType.POSITIVE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_slo_cross_correlation_report_defaults(self):
        r = SLOCrossCorrelationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.weak_correlation_count == 0
        assert r.avg_correlation_score == 0.0
        assert r.by_type == {}
        assert r.by_strength == {}
        assert r.by_category == {}
        assert r.top_weak == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_correlation
# ---------------------------------------------------------------------------


class TestRecordCorrelation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_correlation(
            slo_pair_name="avail-latency",
            correlation_type=CorrelationType.CAUSAL,
            correlation_strength=CorrelationStrength.STRONG,
            slo_category=SLOCategory.LATENCY,
            correlation_score=85.0,
            service="api-gw",
            team="sre",
        )
        assert r.slo_pair_name == "avail-latency"
        assert r.correlation_type == CorrelationType.CAUSAL
        assert r.correlation_strength == CorrelationStrength.STRONG
        assert r.slo_category == SLOCategory.LATENCY
        assert r.correlation_score == 85.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_correlation(slo_pair_name=f"pair-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_correlation
# ---------------------------------------------------------------------------


class TestGetCorrelation:
    def test_found(self):
        eng = _engine()
        r = eng.record_correlation(
            slo_pair_name="avail-latency",
            correlation_strength=CorrelationStrength.WEAK,
        )
        result = eng.get_correlation(r.id)
        assert result is not None
        assert result.correlation_strength == CorrelationStrength.WEAK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_correlation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_correlations
# ---------------------------------------------------------------------------


class TestListCorrelations:
    def test_list_all(self):
        eng = _engine()
        eng.record_correlation(slo_pair_name="pair-1")
        eng.record_correlation(slo_pair_name="pair-2")
        assert len(eng.list_correlations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_correlation(
            slo_pair_name="pair-1",
            correlation_type=CorrelationType.POSITIVE,
        )
        eng.record_correlation(
            slo_pair_name="pair-2",
            correlation_type=CorrelationType.NEGATIVE,
        )
        results = eng.list_correlations(correlation_type=CorrelationType.POSITIVE)
        assert len(results) == 1

    def test_filter_by_strength(self):
        eng = _engine()
        eng.record_correlation(
            slo_pair_name="pair-1",
            correlation_strength=CorrelationStrength.VERY_STRONG,
        )
        eng.record_correlation(
            slo_pair_name="pair-2",
            correlation_strength=CorrelationStrength.WEAK,
        )
        results = eng.list_correlations(correlation_strength=CorrelationStrength.VERY_STRONG)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_correlation(slo_pair_name="pair-1", team="sre")
        eng.record_correlation(slo_pair_name="pair-2", team="platform")
        results = eng.list_correlations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_correlation(slo_pair_name=f"pair-{i}")
        assert len(eng.list_correlations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            slo_pair_name="avail-latency",
            correlation_type=CorrelationType.CAUSAL,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="correlation threshold exceeded",
        )
        assert a.slo_pair_name == "avail-latency"
        assert a.correlation_type == CorrelationType.CAUSAL
        assert a.analysis_score == 88.5
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(slo_pair_name=f"pair-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_correlation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCorrelationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation(
            slo_pair_name="pair-1",
            correlation_type=CorrelationType.POSITIVE,
            correlation_score=40.0,
        )
        eng.record_correlation(
            slo_pair_name="pair-2",
            correlation_type=CorrelationType.POSITIVE,
            correlation_score=60.0,
        )
        result = eng.analyze_correlation_distribution()
        assert "positive" in result
        assert result["positive"]["count"] == 2
        assert result["positive"]["avg_correlation_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_correlation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_weak_correlations
# ---------------------------------------------------------------------------


class TestIdentifyWeakCorrelations:
    def test_detects_below_threshold(self):
        eng = _engine(correlation_strength_threshold=70.0)
        eng.record_correlation(slo_pair_name="pair-1", correlation_score=50.0)
        eng.record_correlation(slo_pair_name="pair-2", correlation_score=90.0)
        results = eng.identify_weak_correlations()
        assert len(results) == 1
        assert results[0]["slo_pair_name"] == "pair-1"

    def test_sorted_ascending(self):
        eng = _engine(correlation_strength_threshold=70.0)
        eng.record_correlation(slo_pair_name="pair-1", correlation_score=50.0)
        eng.record_correlation(slo_pair_name="pair-2", correlation_score=20.0)
        results = eng.identify_weak_correlations()
        assert len(results) == 2
        assert results[0]["correlation_score"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_weak_correlations() == []


# ---------------------------------------------------------------------------
# rank_by_correlation
# ---------------------------------------------------------------------------


class TestRankByCorrelation:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_correlation(slo_pair_name="pair-1", service="api-gw", correlation_score=90.0)
        eng.record_correlation(slo_pair_name="pair-2", service="auth", correlation_score=30.0)
        results = eng.rank_by_correlation()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_correlation_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_correlation() == []


# ---------------------------------------------------------------------------
# detect_correlation_trends
# ---------------------------------------------------------------------------


class TestDetectCorrelationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(slo_pair_name="pair-1", analysis_score=50.0)
        result = eng.detect_correlation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(slo_pair_name="pair-1", analysis_score=20.0)
        eng.add_analysis(slo_pair_name="pair-2", analysis_score=20.0)
        eng.add_analysis(slo_pair_name="pair-3", analysis_score=80.0)
        eng.add_analysis(slo_pair_name="pair-4", analysis_score=80.0)
        result = eng.detect_correlation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_correlation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(correlation_strength_threshold=70.0)
        eng.record_correlation(
            slo_pair_name="avail-latency",
            correlation_type=CorrelationType.CAUSAL,
            correlation_strength=CorrelationStrength.WEAK,
            slo_category=SLOCategory.LATENCY,
            correlation_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SLOCrossCorrelationReport)
        assert report.total_records == 1
        assert report.weak_correlation_count == 1
        assert len(report.top_weak) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_correlation(slo_pair_name="pair-1")
        eng.add_analysis(slo_pair_name="pair-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            slo_pair_name="avail-latency",
            correlation_type=CorrelationType.POSITIVE,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "positive" in stats["type_distribution"]
