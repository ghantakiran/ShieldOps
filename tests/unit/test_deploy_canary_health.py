"""Tests for shieldops.changes.deploy_canary_health — DeployCanaryHealthMonitor."""

from __future__ import annotations

from shieldops.changes.deploy_canary_health import (
    CanaryComparison,
    CanaryDecision,
    CanaryHealth,
    CanaryHealthRecord,
    CanaryMetricType,
    DeployCanaryHealthMonitor,
    DeployCanaryHealthReport,
)


def _engine(**kw) -> DeployCanaryHealthMonitor:
    return DeployCanaryHealthMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_type_error_rate(self):
        assert CanaryMetricType.ERROR_RATE == "error_rate"

    def test_metric_type_latency(self):
        assert CanaryMetricType.LATENCY == "latency"

    def test_metric_type_throughput(self):
        assert CanaryMetricType.THROUGHPUT == "throughput"

    def test_metric_type_saturation(self):
        assert CanaryMetricType.SATURATION == "saturation"

    def test_metric_type_availability(self):
        assert CanaryMetricType.AVAILABILITY == "availability"

    def test_health_healthy(self):
        assert CanaryHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert CanaryHealth.DEGRADED == "degraded"

    def test_health_warning(self):
        assert CanaryHealth.WARNING == "warning"

    def test_health_critical(self):
        assert CanaryHealth.CRITICAL == "critical"

    def test_health_unknown(self):
        assert CanaryHealth.UNKNOWN == "unknown"

    def test_decision_promote(self):
        assert CanaryDecision.PROMOTE == "promote"

    def test_decision_rollback(self):
        assert CanaryDecision.ROLLBACK == "rollback"

    def test_decision_extend(self):
        assert CanaryDecision.EXTEND == "extend"

    def test_decision_pause(self):
        assert CanaryDecision.PAUSE == "pause"

    def test_decision_manual_review(self):
        assert CanaryDecision.MANUAL_REVIEW == "manual_review"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_canary_health_record_defaults(self):
        r = CanaryHealthRecord()
        assert r.id
        assert r.deployment_id == ""
        assert r.canary_metric_type == CanaryMetricType.ERROR_RATE
        assert r.canary_health == CanaryHealth.HEALTHY
        assert r.canary_decision == CanaryDecision.PROMOTE
        assert r.health_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_canary_comparison_defaults(self):
        c = CanaryComparison()
        assert c.id
        assert c.deployment_id == ""
        assert c.canary_metric_type == CanaryMetricType.ERROR_RATE
        assert c.comparison_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_deploy_canary_health_report_defaults(self):
        r = DeployCanaryHealthReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_comparisons == 0
        assert r.unhealthy_canaries == 0
        assert r.avg_health_score == 0.0
        assert r.by_metric_type == {}
        assert r.by_health == {}
        assert r.by_decision == {}
        assert r.top_unhealthy == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_canary
# ---------------------------------------------------------------------------


class TestRecordCanary:
    def test_basic(self):
        eng = _engine()
        r = eng.record_canary(
            deployment_id="DEP-001",
            canary_metric_type=CanaryMetricType.LATENCY,
            canary_health=CanaryHealth.WARNING,
            canary_decision=CanaryDecision.EXTEND,
            health_score=65.0,
            service="api-gateway",
            team="sre",
        )
        assert r.deployment_id == "DEP-001"
        assert r.canary_metric_type == CanaryMetricType.LATENCY
        assert r.canary_health == CanaryHealth.WARNING
        assert r.canary_decision == CanaryDecision.EXTEND
        assert r.health_score == 65.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_canary(deployment_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_canary
# ---------------------------------------------------------------------------


class TestGetCanary:
    def test_found(self):
        eng = _engine()
        r = eng.record_canary(
            deployment_id="DEP-001",
            canary_health=CanaryHealth.CRITICAL,
        )
        result = eng.get_canary(r.id)
        assert result is not None
        assert result.canary_health == CanaryHealth.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_canary("nonexistent") is None


# ---------------------------------------------------------------------------
# list_canaries
# ---------------------------------------------------------------------------


class TestListCanaries:
    def test_list_all(self):
        eng = _engine()
        eng.record_canary(deployment_id="DEP-001")
        eng.record_canary(deployment_id="DEP-002")
        assert len(eng.list_canaries()) == 2

    def test_filter_by_metric_type(self):
        eng = _engine()
        eng.record_canary(
            deployment_id="DEP-001",
            canary_metric_type=CanaryMetricType.LATENCY,
        )
        eng.record_canary(
            deployment_id="DEP-002",
            canary_metric_type=CanaryMetricType.THROUGHPUT,
        )
        results = eng.list_canaries(metric_type=CanaryMetricType.LATENCY)
        assert len(results) == 1

    def test_filter_by_health(self):
        eng = _engine()
        eng.record_canary(
            deployment_id="DEP-001",
            canary_health=CanaryHealth.CRITICAL,
        )
        eng.record_canary(
            deployment_id="DEP-002",
            canary_health=CanaryHealth.HEALTHY,
        )
        results = eng.list_canaries(health=CanaryHealth.CRITICAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_canary(deployment_id="DEP-001", service="api")
        eng.record_canary(deployment_id="DEP-002", service="web")
        results = eng.list_canaries(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_canary(deployment_id="DEP-001", team="sre")
        eng.record_canary(deployment_id="DEP-002", team="platform")
        results = eng.list_canaries(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_canary(deployment_id=f"DEP-{i}")
        assert len(eng.list_canaries(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_comparison
# ---------------------------------------------------------------------------


class TestAddComparison:
    def test_basic(self):
        eng = _engine()
        c = eng.add_comparison(
            deployment_id="DEP-001",
            canary_metric_type=CanaryMetricType.ERROR_RATE,
            comparison_score=75.0,
            threshold=80.0,
            breached=False,
            description="Error rate within limits",
        )
        assert c.deployment_id == "DEP-001"
        assert c.canary_metric_type == CanaryMetricType.ERROR_RATE
        assert c.comparison_score == 75.0
        assert c.threshold == 80.0
        assert c.breached is False
        assert c.description == "Error rate within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_comparison(deployment_id=f"DEP-{i}")
        assert len(eng._comparisons) == 2


# ---------------------------------------------------------------------------
# analyze_canary_health
# ---------------------------------------------------------------------------


class TestAnalyzeCanaryHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_canary(
            deployment_id="DEP-001",
            canary_metric_type=CanaryMetricType.LATENCY,
            health_score=70.0,
        )
        eng.record_canary(
            deployment_id="DEP-002",
            canary_metric_type=CanaryMetricType.LATENCY,
            health_score=90.0,
        )
        result = eng.analyze_canary_health()
        assert "latency" in result
        assert result["latency"]["count"] == 2
        assert result["latency"]["avg_health_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_canary_health() == {}


# ---------------------------------------------------------------------------
# identify_unhealthy_canaries
# ---------------------------------------------------------------------------


class TestIdentifyUnhealthyCanaries:
    def test_detects_unhealthy(self):
        eng = _engine()
        eng.record_canary(
            deployment_id="DEP-001",
            canary_health=CanaryHealth.CRITICAL,
        )
        eng.record_canary(
            deployment_id="DEP-002",
            canary_health=CanaryHealth.HEALTHY,
        )
        results = eng.identify_unhealthy_canaries()
        assert len(results) == 1
        assert results[0]["deployment_id"] == "DEP-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unhealthy_canaries() == []


# ---------------------------------------------------------------------------
# rank_by_health_score
# ---------------------------------------------------------------------------


class TestRankByHealthScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_canary(deployment_id="DEP-001", service="api", health_score=90.0)
        eng.record_canary(deployment_id="DEP-002", service="api", health_score=80.0)
        eng.record_canary(deployment_id="DEP-003", service="web", health_score=50.0)
        results = eng.rank_by_health_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_health_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_health_score() == []


# ---------------------------------------------------------------------------
# detect_health_trends
# ---------------------------------------------------------------------------


class TestDetectHealthTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_comparison(deployment_id="DEP-001", comparison_score=val)
        result = eng.detect_health_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_comparison(deployment_id="DEP-001", comparison_score=val)
        result = eng.detect_health_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_health_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_canary(
            deployment_id="DEP-001",
            canary_metric_type=CanaryMetricType.LATENCY,
            canary_health=CanaryHealth.CRITICAL,
            health_score=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DeployCanaryHealthReport)
        assert report.total_records == 1
        assert report.unhealthy_canaries == 1
        assert report.avg_health_score == 50.0
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
        eng.record_canary(deployment_id="DEP-001")
        eng.add_comparison(deployment_id="DEP-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._comparisons) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_comparisons"] == 0
        assert stats["metric_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_canary(
            deployment_id="DEP-001",
            canary_metric_type=CanaryMetricType.LATENCY,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_deployments"] == 1
        assert "latency" in stats["metric_type_distribution"]
