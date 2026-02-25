"""Tests for shieldops.analytics.metric_rca — MetricRootCauseAnalyzer."""

from __future__ import annotations

from shieldops.analytics.metric_rca import (
    CausalConfidence,
    CauseCategory,
    MetricAnomaly,
    MetricRCAReport,
    MetricRootCauseAnalyzer,
    MetricType,
    RootCauseHypothesis,
)


def _engine(**kw) -> MetricRootCauseAnalyzer:
    return MetricRootCauseAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # CauseCategory (5)
    def test_cause_deployment(self):
        assert CauseCategory.DEPLOYMENT == "deployment"

    def test_cause_config_change(self):
        assert CauseCategory.CONFIG_CHANGE == "config_change"

    def test_cause_dependency_degradation(self):
        assert CauseCategory.DEPENDENCY_DEGRADATION == "dependency_degradation"

    def test_cause_resource_contention(self):
        assert CauseCategory.RESOURCE_CONTENTION == "resource_contention"

    def test_cause_external_factor(self):
        assert CauseCategory.EXTERNAL_FACTOR == "external_factor"

    # CausalConfidence (5)
    def test_confidence_confirmed(self):
        assert CausalConfidence.CONFIRMED == "confirmed"

    def test_confidence_probable(self):
        assert CausalConfidence.PROBABLE == "probable"

    def test_confidence_possible(self):
        assert CausalConfidence.POSSIBLE == "possible"

    def test_confidence_unlikely(self):
        assert CausalConfidence.UNLIKELY == "unlikely"

    def test_confidence_unknown(self):
        assert CausalConfidence.UNKNOWN == "unknown"

    # MetricType (5)
    def test_type_latency(self):
        assert MetricType.LATENCY == "latency"

    def test_type_error_rate(self):
        assert MetricType.ERROR_RATE == "error_rate"

    def test_type_cpu_usage(self):
        assert MetricType.CPU_USAGE == "cpu_usage"

    def test_type_memory_usage(self):
        assert MetricType.MEMORY_USAGE == "memory_usage"

    def test_type_throughput(self):
        assert MetricType.THROUGHPUT == "throughput"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_metric_anomaly_defaults(self):
        a = MetricAnomaly()
        assert a.id
        assert a.service == ""
        assert a.metric_type == MetricType.LATENCY
        assert a.baseline_value == 0.0
        assert a.anomaly_value == 0.0
        assert a.deviation_pct == 0.0
        assert a.resolved is False
        assert a.created_at > 0

    def test_root_cause_hypothesis_defaults(self):
        h = RootCauseHypothesis()
        assert h.id
        assert h.anomaly_id == ""
        assert h.cause_category == CauseCategory.DEPLOYMENT
        assert h.confidence == CausalConfidence.UNKNOWN
        assert h.confidence_score == 0.0
        assert h.description == ""
        assert h.correlated_changes == []
        assert h.created_at > 0

    def test_metric_rca_report_defaults(self):
        r = MetricRCAReport()
        assert r.total_anomalies == 0
        assert r.resolved_count == 0
        assert r.total_hypotheses == 0
        assert r.by_cause_category == {}
        assert r.by_metric_type == {}
        assert r.avg_deviation_pct == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_anomaly
# ---------------------------------------------------------------------------


class TestRecordAnomaly:
    def test_basic(self):
        eng = _engine()
        a = eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        assert a.service == "api-gw"
        assert a.metric_type == MetricType.LATENCY
        assert a.deviation_pct == 0.0

    def test_with_deviation(self):
        eng = _engine()
        a = eng.record_anomaly(
            service="api-gw",
            metric_type=MetricType.CPU_USAGE,
            baseline_value=50.0,
            anomaly_value=80.0,
        )
        # deviation = abs(80-50)/50 * 100 = 60.0
        assert a.deviation_pct == 60.0

    def test_zero_baseline_no_division_error(self):
        eng = _engine()
        a = eng.record_anomaly(
            service="svc",
            metric_type=MetricType.ERROR_RATE,
            baseline_value=0.0,
            anomaly_value=5.0,
        )
        assert a.deviation_pct == 0.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_anomaly(service=f"svc-{i}", metric_type=MetricType.LATENCY)
        assert len(eng._anomalies) == 3


# ---------------------------------------------------------------------------
# get_anomaly
# ---------------------------------------------------------------------------


class TestGetAnomaly:
    def test_found(self):
        eng = _engine()
        a = eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        result = eng.get_anomaly(a.id)
        assert result is not None
        assert result.service == "api-gw"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_anomaly("nonexistent") is None


# ---------------------------------------------------------------------------
# list_anomalies
# ---------------------------------------------------------------------------


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine()
        eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        eng.record_anomaly(service="payment-svc", metric_type=MetricType.ERROR_RATE)
        assert len(eng.list_anomalies()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        eng.record_anomaly(service="payment-svc", metric_type=MetricType.ERROR_RATE)
        results = eng.list_anomalies(service="api-gw")
        assert len(results) == 1
        assert results[0].service == "api-gw"

    def test_filter_by_metric_type(self):
        eng = _engine()
        eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        eng.record_anomaly(service="payment-svc", metric_type=MetricType.ERROR_RATE)
        results = eng.list_anomalies(metric_type=MetricType.ERROR_RATE)
        assert len(results) == 1
        assert results[0].metric_type == MetricType.ERROR_RATE


# ---------------------------------------------------------------------------
# analyze_root_cause
# ---------------------------------------------------------------------------


class TestAnalyzeRootCause:
    def test_large_deviation_deployment(self):
        eng = _engine()
        a = eng.record_anomaly(
            service="api-gw",
            metric_type=MetricType.LATENCY,
            baseline_value=10.0,
            anomaly_value=25.0,
        )
        # deviation = 150% -> DEPLOYMENT cause
        hyp = eng.analyze_root_cause(a.id)
        assert hyp.cause_category == CauseCategory.DEPLOYMENT
        assert hyp.confidence_score == 0.85
        assert hyp.confidence == CausalConfidence.PROBABLE

    def test_cpu_resource_contention(self):
        eng = _engine()
        a = eng.record_anomaly(
            service="worker",
            metric_type=MetricType.CPU_USAGE,
            baseline_value=50.0,
            anomaly_value=70.0,
        )
        # deviation=40%, <100 -> resource contention branch
        hyp = eng.analyze_root_cause(a.id)
        assert hyp.cause_category == CauseCategory.RESOURCE_CONTENTION
        assert hyp.confidence_score == 0.7

    def test_anomaly_not_found(self):
        eng = _engine()
        hyp = eng.analyze_root_cause("nonexistent")
        assert hyp.cause_category == CauseCategory.EXTERNAL_FACTOR
        assert hyp.confidence == CausalConfidence.UNKNOWN
        assert hyp.confidence_score == 0.1


# ---------------------------------------------------------------------------
# correlate_with_changes
# ---------------------------------------------------------------------------


class TestCorrelateWithChanges:
    def test_correlated(self):
        eng = _engine()
        a = eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        result = eng.correlate_with_changes(a.id, changes=["deploy-v2.1"])
        assert result["found"] is True
        assert result["correlated"] is True
        assert result["correlation_score"] == 0.8

    def test_no_changes(self):
        eng = _engine()
        a = eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        result = eng.correlate_with_changes(a.id)
        assert result["found"] is True
        assert result["correlated"] is False
        assert result["correlation_score"] == 0.3

    def test_anomaly_not_found(self):
        eng = _engine()
        result = eng.correlate_with_changes("nonexistent")
        assert result["found"] is False


# ---------------------------------------------------------------------------
# rank_hypotheses
# ---------------------------------------------------------------------------


class TestRankHypotheses:
    def test_ranked_order(self):
        eng = _engine()
        a = eng.record_anomaly(
            service="api-gw",
            metric_type=MetricType.LATENCY,
            baseline_value=10.0,
            anomaly_value=25.0,
        )
        eng.analyze_root_cause(a.id)
        ranked = eng.rank_hypotheses(a.id)
        assert len(ranked) == 1
        assert ranked[0]["hypothesis_id"]
        assert ranked[0]["cause_category"] == "deployment"

    def test_empty_for_unknown_anomaly(self):
        eng = _engine()
        assert eng.rank_hypotheses("nonexistent") == []


# ---------------------------------------------------------------------------
# mark_resolved
# ---------------------------------------------------------------------------


class TestMarkResolved:
    def test_mark_resolved(self):
        eng = _engine()
        a = eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        result = eng.mark_resolved(a.id)
        assert result["found"] is True
        assert result["resolved"] is True
        assert a.resolved is True

    def test_not_found(self):
        eng = _engine()
        result = eng.mark_resolved("nonexistent")
        assert result["found"] is False


# ---------------------------------------------------------------------------
# get_cause_trends
# ---------------------------------------------------------------------------


class TestGetCauseTrends:
    def test_with_hypotheses(self):
        eng = _engine()
        a = eng.record_anomaly(
            service="api-gw",
            metric_type=MetricType.CPU_USAGE,
            baseline_value=50.0,
            anomaly_value=70.0,
        )
        eng.analyze_root_cause(a.id)
        trends = eng.get_cause_trends()
        assert "resource_contention" in trends
        assert trends["resource_contention"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.get_cause_trends() == {}


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        a1 = eng.record_anomaly(
            service="api-gw",
            metric_type=MetricType.LATENCY,
            baseline_value=10.0,
            anomaly_value=25.0,
        )
        a2 = eng.record_anomaly(
            service="payment-svc",
            metric_type=MetricType.CPU_USAGE,
            baseline_value=50.0,
            anomaly_value=70.0,
        )
        eng.analyze_root_cause(a1.id)
        eng.analyze_root_cause(a2.id)
        report = eng.generate_report()
        assert isinstance(report, MetricRCAReport)
        assert report.total_anomalies == 2
        assert report.total_hypotheses == 2
        assert report.resolved_count == 0
        assert len(report.by_cause_category) > 0
        assert len(report.by_metric_type) == 2
        assert report.avg_deviation_pct > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_anomalies == 0
        assert report.total_hypotheses == 0
        assert "No significant metric anomalies detected" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        a = eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        eng.analyze_root_cause(a.id)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._anomalies) == 0
        assert len(eng._hypotheses) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 0
        assert stats["total_hypotheses"] == 0
        assert stats["cause_distribution"] == {}
        assert stats["unique_services"] == 0
        assert stats["resolved"] == 0

    def test_populated(self):
        eng = _engine()
        a = eng.record_anomaly(service="api-gw", metric_type=MetricType.LATENCY)
        eng.analyze_root_cause(a.id)
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 1
        assert stats["total_hypotheses"] == 1
        assert stats["deviation_threshold_pct"] == 25.0
        assert stats["unique_services"] == 1
        assert len(stats["cause_distribution"]) > 0
