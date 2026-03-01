"""Tests for shieldops.observability.alert_correlation_profiler — AlertCorrelationProfiler."""

from __future__ import annotations

from shieldops.observability.alert_correlation_profiler import (
    AlertCorrelationProfiler,
    AlertCorrelationReport,
    CorrelationMetric,
    CorrelationRecord,
    CorrelationScope,
    CorrelationStrength,
    CorrelationType,
)


def _engine(**kw) -> AlertCorrelationProfiler:
    return AlertCorrelationProfiler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_temporal(self):
        assert CorrelationType.TEMPORAL == "temporal"

    def test_type_causal(self):
        assert CorrelationType.CAUSAL == "causal"

    def test_type_symptomatic(self):
        assert CorrelationType.SYMPTOMATIC == "symptomatic"

    def test_type_cascading(self):
        assert CorrelationType.CASCADING == "cascading"

    def test_type_coincidental(self):
        assert CorrelationType.COINCIDENTAL == "coincidental"

    def test_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_strength_negligible(self):
        assert CorrelationStrength.NEGLIGIBLE == "negligible"

    def test_strength_unknown(self):
        assert CorrelationStrength.UNKNOWN == "unknown"

    def test_scope_same_service(self):
        assert CorrelationScope.SAME_SERVICE == "same_service"

    def test_scope_same_team(self):
        assert CorrelationScope.SAME_TEAM == "same_team"

    def test_scope_cross_service(self):
        assert CorrelationScope.CROSS_SERVICE == "cross_service"

    def test_scope_infrastructure(self):
        assert CorrelationScope.INFRASTRUCTURE == "infrastructure"

    def test_scope_platform(self):
        assert CorrelationScope.PLATFORM == "platform"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_correlation_record_defaults(self):
        r = CorrelationRecord()
        assert r.id
        assert r.correlation_id == ""
        assert r.correlation_type == CorrelationType.TEMPORAL
        assert r.correlation_strength == CorrelationStrength.UNKNOWN
        assert r.correlation_scope == CorrelationScope.SAME_SERVICE
        assert r.correlation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_correlation_metric_defaults(self):
        m = CorrelationMetric()
        assert m.id
        assert m.correlation_id == ""
        assert m.correlation_type == CorrelationType.TEMPORAL
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_alert_correlation_report_defaults(self):
        r = AlertCorrelationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.strong_correlations == 0
        assert r.avg_correlation_score == 0.0
        assert r.by_type == {}
        assert r.by_strength == {}
        assert r.by_scope == {}
        assert r.top_correlated == []
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
            correlation_id="COR-001",
            correlation_type=CorrelationType.CAUSAL,
            correlation_strength=CorrelationStrength.STRONG,
            correlation_scope=CorrelationScope.CROSS_SERVICE,
            correlation_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.correlation_id == "COR-001"
        assert r.correlation_type == CorrelationType.CAUSAL
        assert r.correlation_strength == CorrelationStrength.STRONG
        assert r.correlation_scope == CorrelationScope.CROSS_SERVICE
        assert r.correlation_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_correlation(correlation_id=f"COR-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_correlation
# ---------------------------------------------------------------------------


class TestGetCorrelation:
    def test_found(self):
        eng = _engine()
        r = eng.record_correlation(
            correlation_id="COR-001",
            correlation_strength=CorrelationStrength.STRONG,
        )
        result = eng.get_correlation(r.id)
        assert result is not None
        assert result.correlation_strength == CorrelationStrength.STRONG

    def test_not_found(self):
        eng = _engine()
        assert eng.get_correlation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_correlations
# ---------------------------------------------------------------------------


class TestListCorrelations:
    def test_list_all(self):
        eng = _engine()
        eng.record_correlation(correlation_id="COR-001")
        eng.record_correlation(correlation_id="COR-002")
        assert len(eng.list_correlations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_correlation(
            correlation_id="COR-001",
            correlation_type=CorrelationType.CAUSAL,
        )
        eng.record_correlation(
            correlation_id="COR-002",
            correlation_type=CorrelationType.TEMPORAL,
        )
        results = eng.list_correlations(
            correlation_type=CorrelationType.CAUSAL,
        )
        assert len(results) == 1

    def test_filter_by_strength(self):
        eng = _engine()
        eng.record_correlation(
            correlation_id="COR-001",
            correlation_strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            correlation_id="COR-002",
            correlation_strength=CorrelationStrength.WEAK,
        )
        results = eng.list_correlations(
            correlation_strength=CorrelationStrength.STRONG,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_correlation(correlation_id="COR-001", team="sre")
        eng.record_correlation(correlation_id="COR-002", team="platform")
        results = eng.list_correlations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_correlation(correlation_id=f"COR-{i}")
        assert len(eng.list_correlations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            correlation_id="COR-001",
            correlation_type=CorrelationType.CAUSAL,
            metric_score=75.0,
            threshold=50.0,
            breached=True,
            description="Causal correlation detected",
        )
        assert m.correlation_id == "COR-001"
        assert m.correlation_type == CorrelationType.CAUSAL
        assert m.metric_score == 75.0
        assert m.threshold == 50.0
        assert m.breached is True
        assert m.description == "Causal correlation detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(correlation_id=f"COR-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_correlation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCorrelationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation(
            correlation_id="COR-001",
            correlation_type=CorrelationType.CAUSAL,
            correlation_score=80.0,
        )
        eng.record_correlation(
            correlation_id="COR-002",
            correlation_type=CorrelationType.CAUSAL,
            correlation_score=60.0,
        )
        result = eng.analyze_correlation_distribution()
        assert "causal" in result
        assert result["causal"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_correlation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_strong_correlations
# ---------------------------------------------------------------------------


class TestIdentifyStrongCorrelations:
    def test_detects_strong(self):
        eng = _engine()
        eng.record_correlation(
            correlation_id="COR-001",
            correlation_strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            correlation_id="COR-002",
            correlation_strength=CorrelationStrength.WEAK,
        )
        results = eng.identify_strong_correlations()
        assert len(results) == 1
        assert results[0]["correlation_id"] == "COR-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_strong_correlations() == []


# ---------------------------------------------------------------------------
# rank_by_correlation_score
# ---------------------------------------------------------------------------


class TestRankByCorrelationScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_correlation(
            correlation_id="COR-001",
            service="api-gateway",
            correlation_score=90.0,
        )
        eng.record_correlation(
            correlation_id="COR-002",
            service="payments",
            correlation_score=30.0,
        )
        results = eng.rank_by_correlation_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_correlation_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_correlation_score() == []


# ---------------------------------------------------------------------------
# detect_correlation_trends
# ---------------------------------------------------------------------------


class TestDetectCorrelationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(
                correlation_id="COR-001",
                metric_score=50.0,
            )
        result = eng.detect_correlation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(correlation_id="COR-001", metric_score=30.0)
        eng.add_metric(correlation_id="COR-002", metric_score=30.0)
        eng.add_metric(correlation_id="COR-003", metric_score=80.0)
        eng.add_metric(correlation_id="COR-004", metric_score=80.0)
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
        eng = _engine()
        eng.record_correlation(
            correlation_id="COR-001",
            correlation_type=CorrelationType.CAUSAL,
            correlation_strength=CorrelationStrength.STRONG,
            correlation_scope=CorrelationScope.CROSS_SERVICE,
            correlation_score=85.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AlertCorrelationReport)
        assert report.total_records == 1
        assert report.strong_correlations == 1
        assert len(report.top_correlated) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_correlation(correlation_id="COR-001")
        eng.add_metric(correlation_id="COR-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            correlation_id="COR-001",
            correlation_type=CorrelationType.CAUSAL,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "causal" in stats["type_distribution"]
