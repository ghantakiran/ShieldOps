"""Tests for shieldops.operations.blast_radius_predictor."""

from __future__ import annotations

from shieldops.operations.blast_radius_predictor import (
    BlastRadiusPrediction,
    BlastRadiusPredictor,
    BlastRadiusReport,
    ConfidenceLevel,
    ImpactType,
    RadiusAnalysis,
    RadiusScope,
)


def _engine(**kw) -> BlastRadiusPredictor:
    return BlastRadiusPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_impact_service_degradation(self):
        assert ImpactType.SERVICE_DEGRADATION == "service_degradation"

    def test_impact_outage(self):
        assert ImpactType.OUTAGE == "outage"

    def test_impact_data_loss(self):
        assert ImpactType.DATA_LOSS == "data_loss"

    def test_impact_latency_spike(self):
        assert ImpactType.LATENCY_SPIKE == "latency_spike"

    def test_impact_cascade_failure(self):
        assert ImpactType.CASCADE_FAILURE == "cascade_failure"

    def test_scope_single_service(self):
        assert RadiusScope.SINGLE_SERVICE == "single_service"

    def test_scope_team(self):
        assert RadiusScope.TEAM == "team"

    def test_scope_domain(self):
        assert RadiusScope.DOMAIN == "domain"

    def test_scope_platform(self):
        assert RadiusScope.PLATFORM == "platform"

    def test_scope_customer_facing(self):
        assert RadiusScope.CUSTOMER_FACING == "customer_facing"

    def test_confidence_high(self):
        assert ConfidenceLevel.HIGH == "high"

    def test_confidence_medium(self):
        assert ConfidenceLevel.MEDIUM == "medium"

    def test_confidence_low(self):
        assert ConfidenceLevel.LOW == "low"

    def test_confidence_estimated(self):
        assert ConfidenceLevel.ESTIMATED == "estimated"

    def test_confidence_unknown(self):
        assert ConfidenceLevel.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_blast_radius_prediction_defaults(self):
        r = BlastRadiusPrediction()
        assert r.id
        assert r.impact_type == ImpactType.SERVICE_DEGRADATION
        assert r.radius_scope == RadiusScope.SINGLE_SERVICE
        assert r.confidence_level == ConfidenceLevel.HIGH
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_radius_analysis_defaults(self):
        a = RadiusAnalysis()
        assert a.id
        assert a.impact_type == ImpactType.SERVICE_DEGRADATION
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_blast_radius_report_defaults(self):
        r = BlastRadiusReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_impact_type == {}
        assert r.by_scope == {}
        assert r.by_confidence == {}
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
        eng = _engine(max_records=5000)
        assert eng._max_records == 5000

    def test_custom_threshold(self):
        eng = _engine(threshold=60.0)
        assert eng._threshold == 60.0


# ---------------------------------------------------------------------------
# record_prediction / get_prediction
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_prediction(
            service="payment-svc",
            impact_type=ImpactType.OUTAGE,
            radius_scope=RadiusScope.PLATFORM,
            confidence_level=ConfidenceLevel.MEDIUM,
            score=65.0,
            team="infra",
        )
        assert r.service == "payment-svc"
        assert r.impact_type == ImpactType.OUTAGE
        assert r.radius_scope == RadiusScope.PLATFORM
        assert r.confidence_level == ConfidenceLevel.MEDIUM
        assert r.score == 65.0
        assert r.team == "infra"

    def test_record_stored(self):
        eng = _engine()
        eng.record_prediction(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_prediction(service="svc-a", score=55.0)
        result = eng.get_prediction(r.id)
        assert result is not None
        assert result.score == 55.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_predictions
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction(service="svc-a")
        eng.record_prediction(service="svc-b")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_impact_type(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", impact_type=ImpactType.OUTAGE)
        eng.record_prediction(service="svc-b", impact_type=ImpactType.DATA_LOSS)
        results = eng.list_predictions(impact_type=ImpactType.OUTAGE)
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", radius_scope=RadiusScope.SINGLE_SERVICE)
        eng.record_prediction(service="svc-b", radius_scope=RadiusScope.PLATFORM)
        results = eng.list_predictions(radius_scope=RadiusScope.SINGLE_SERVICE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", team="infra")
        eng.record_prediction(service="svc-b", team="security")
        assert len(eng.list_predictions(team="infra")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_prediction(service=f"svc-{i}")
        assert len(eng.list_predictions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            impact_type=ImpactType.CASCADE_FAILURE,
            analysis_score=45.0,
            threshold=50.0,
            breached=True,
            description="cascade detected",
        )
        assert a.impact_type == ImpactType.CASCADE_FAILURE
        assert a.analysis_score == 45.0
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
        eng.record_prediction(service="s1", impact_type=ImpactType.OUTAGE, score=90.0)
        eng.record_prediction(service="s2", impact_type=ImpactType.OUTAGE, score=70.0)
        result = eng.analyze_distribution()
        assert "outage" in result
        assert result["outage"]["count"] == 2
        assert result["outage"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_radius_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_prediction(service="svc-a", score=60.0)
        eng.record_prediction(service="svc-b", score=90.0)
        results = eng.identify_radius_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_prediction(service="svc-a", score=50.0)
        eng.record_prediction(service="svc-b", score=30.0)
        results = eng.identify_radius_gaps()
        assert results[0]["score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", score=90.0)
        eng.record_prediction(service="svc-b", score=40.0)
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
        eng.record_prediction(
            service="svc-a",
            impact_type=ImpactType.LATENCY_SPIKE,
            radius_scope=RadiusScope.DOMAIN,
            confidence_level=ConfidenceLevel.LOW,
            score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, BlastRadiusReport)
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
        eng.record_prediction(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_prediction(
            service="svc-a",
            impact_type=ImpactType.SERVICE_DEGRADATION,
            team="infra",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "service_degradation" in stats["impact_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(service=f"svc-{i}")
        assert len(eng._records) == 3
