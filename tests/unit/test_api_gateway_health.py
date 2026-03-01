"""Tests for shieldops.topology.api_gateway_health — APIGatewayHealthMonitor."""

from __future__ import annotations

from shieldops.topology.api_gateway_health import (
    APIGatewayHealthMonitor,
    APIGatewayHealthReport,
    GatewayAlert,
    GatewayHealthRecord,
    GatewayIssue,
    GatewayMetric,
    GatewayStatus,
)


def _engine(**kw) -> APIGatewayHealthMonitor:
    return APIGatewayHealthMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_error_rate(self):
        assert GatewayMetric.ERROR_RATE == "error_rate"

    def test_metric_latency(self):
        assert GatewayMetric.LATENCY == "latency"

    def test_metric_throughput(self):
        assert GatewayMetric.THROUGHPUT == "throughput"

    def test_metric_rate_limit_hits(self):
        assert GatewayMetric.RATE_LIMIT_HITS == "rate_limit_hits"

    def test_metric_connection_pool(self):
        assert GatewayMetric.CONNECTION_POOL == "connection_pool"

    def test_status_healthy(self):
        assert GatewayStatus.HEALTHY == "healthy"

    def test_status_degraded(self):
        assert GatewayStatus.DEGRADED == "degraded"

    def test_status_overloaded(self):
        assert GatewayStatus.OVERLOADED == "overloaded"

    def test_status_failing(self):
        assert GatewayStatus.FAILING == "failing"

    def test_status_offline(self):
        assert GatewayStatus.OFFLINE == "offline"

    def test_issue_rate_limiting(self):
        assert GatewayIssue.RATE_LIMITING == "rate_limiting"

    def test_issue_timeout(self):
        assert GatewayIssue.TIMEOUT == "timeout"

    def test_issue_backend_error(self):
        assert GatewayIssue.BACKEND_ERROR == "backend_error"

    def test_issue_ssl_error(self):
        assert GatewayIssue.SSL_ERROR == "ssl_error"

    def test_issue_routing_failure(self):
        assert GatewayIssue.ROUTING_FAILURE == "routing_failure"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_gateway_health_record_defaults(self):
        r = GatewayHealthRecord()
        assert r.id
        assert r.gateway_id == ""
        assert r.gateway_metric == GatewayMetric.ERROR_RATE
        assert r.gateway_status == GatewayStatus.HEALTHY
        assert r.gateway_issue == GatewayIssue.RATE_LIMITING
        assert r.error_rate_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_gateway_alert_defaults(self):
        a = GatewayAlert()
        assert a.id
        assert a.alert_name == ""
        assert a.gateway_metric == GatewayMetric.ERROR_RATE
        assert a.error_threshold == 0.0
        assert a.avg_error_rate == 0.0
        assert a.description == ""
        assert a.created_at > 0

    def test_api_gateway_health_report_defaults(self):
        r = APIGatewayHealthReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_alerts == 0
        assert r.unhealthy_gateways == 0
        assert r.avg_error_rate == 0.0
        assert r.by_metric == {}
        assert r.by_status == {}
        assert r.by_issue == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_health
# ---------------------------------------------------------------------------


class TestRecordHealth:
    def test_basic(self):
        eng = _engine()
        r = eng.record_health(
            gateway_id="gw-001",
            gateway_metric=GatewayMetric.LATENCY,
            gateway_status=GatewayStatus.DEGRADED,
            gateway_issue=GatewayIssue.TIMEOUT,
            error_rate_pct=3.5,
            team="platform",
        )
        assert r.gateway_id == "gw-001"
        assert r.gateway_metric == GatewayMetric.LATENCY
        assert r.gateway_status == GatewayStatus.DEGRADED
        assert r.gateway_issue == GatewayIssue.TIMEOUT
        assert r.error_rate_pct == 3.5
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_health(gateway_id=f"gw-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_health
# ---------------------------------------------------------------------------


class TestGetHealth:
    def test_found(self):
        eng = _engine()
        r = eng.record_health(
            gateway_id="gw-001",
            gateway_status=GatewayStatus.FAILING,
        )
        result = eng.get_health(r.id)
        assert result is not None
        assert result.gateway_status == GatewayStatus.FAILING

    def test_not_found(self):
        eng = _engine()
        assert eng.get_health("nonexistent") is None


# ---------------------------------------------------------------------------
# list_health_records
# ---------------------------------------------------------------------------


class TestListHealthRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_health(gateway_id="gw-001")
        eng.record_health(gateway_id="gw-002")
        assert len(eng.list_health_records()) == 2

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_health(
            gateway_id="gw-001",
            gateway_metric=GatewayMetric.ERROR_RATE,
        )
        eng.record_health(
            gateway_id="gw-002",
            gateway_metric=GatewayMetric.LATENCY,
        )
        results = eng.list_health_records(metric=GatewayMetric.ERROR_RATE)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_health(
            gateway_id="gw-001",
            gateway_status=GatewayStatus.HEALTHY,
        )
        eng.record_health(
            gateway_id="gw-002",
            gateway_status=GatewayStatus.OFFLINE,
        )
        results = eng.list_health_records(status=GatewayStatus.HEALTHY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_health(gateway_id="gw-001", team="sre")
        eng.record_health(gateway_id="gw-002", team="platform")
        results = eng.list_health_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_health(gateway_id=f"gw-{i}")
        assert len(eng.list_health_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_alert
# ---------------------------------------------------------------------------


class TestAddAlert:
    def test_basic(self):
        eng = _engine()
        a = eng.add_alert(
            alert_name="high-error-rate",
            gateway_metric=GatewayMetric.ERROR_RATE,
            error_threshold=5.0,
            avg_error_rate=7.5,
            description="Error rate exceeds threshold",
        )
        assert a.alert_name == "high-error-rate"
        assert a.gateway_metric == GatewayMetric.ERROR_RATE
        assert a.error_threshold == 5.0
        assert a.avg_error_rate == 7.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_alert(alert_name=f"alert-{i}")
        assert len(eng._alerts) == 2


# ---------------------------------------------------------------------------
# analyze_gateway_performance
# ---------------------------------------------------------------------------


class TestAnalyzeGatewayPerformance:
    def test_with_data(self):
        eng = _engine()
        eng.record_health(
            gateway_id="gw-001",
            gateway_metric=GatewayMetric.ERROR_RATE,
            error_rate_pct=5.0,
        )
        eng.record_health(
            gateway_id="gw-002",
            gateway_metric=GatewayMetric.ERROR_RATE,
            error_rate_pct=3.0,
        )
        result = eng.analyze_gateway_performance()
        assert "error_rate" in result
        assert result["error_rate"]["count"] == 2
        assert result["error_rate"]["avg_error_rate"] == 4.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_gateway_performance() == {}


# ---------------------------------------------------------------------------
# identify_unhealthy_gateways
# ---------------------------------------------------------------------------


class TestIdentifyUnhealthyGateways:
    def test_detects_failing(self):
        eng = _engine()
        eng.record_health(
            gateway_id="gw-001",
            gateway_status=GatewayStatus.FAILING,
            error_rate_pct=15.0,
        )
        eng.record_health(
            gateway_id="gw-002",
            gateway_status=GatewayStatus.HEALTHY,
        )
        results = eng.identify_unhealthy_gateways()
        assert len(results) == 1
        assert results[0]["gateway_id"] == "gw-001"

    def test_detects_offline(self):
        eng = _engine()
        eng.record_health(
            gateway_id="gw-001",
            gateway_status=GatewayStatus.OFFLINE,
        )
        results = eng.identify_unhealthy_gateways()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unhealthy_gateways() == []


# ---------------------------------------------------------------------------
# rank_by_error_rate
# ---------------------------------------------------------------------------


class TestRankByErrorRate:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_health(gateway_id="gw-001", team="sre", error_rate_pct=10.0)
        eng.record_health(gateway_id="gw-002", team="sre", error_rate_pct=8.0)
        eng.record_health(gateway_id="gw-003", team="platform", error_rate_pct=3.0)
        results = eng.rank_by_error_rate()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_error_rate"] == 9.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_error_rate() == []


# ---------------------------------------------------------------------------
# detect_gateway_degradation
# ---------------------------------------------------------------------------


class TestDetectGatewayDegradation:
    def test_stable(self):
        eng = _engine()
        for s in [5.0, 5.0, 5.0, 5.0]:
            eng.add_alert(alert_name="a", avg_error_rate=s)
        result = eng.detect_gateway_degradation()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [2.0, 2.0, 12.0, 12.0]:
            eng.add_alert(alert_name="a", avg_error_rate=s)
        result = eng.detect_gateway_degradation()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_gateway_degradation()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_health(
            gateway_id="gw-001",
            gateway_status=GatewayStatus.FAILING,
            gateway_metric=GatewayMetric.ERROR_RATE,
            error_rate_pct=12.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, APIGatewayHealthReport)
        assert report.total_records == 1
        assert report.unhealthy_gateways == 1
        assert report.avg_error_rate == 12.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable limits" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_health(gateway_id="gw-001")
        eng.add_alert(alert_name="a1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._alerts) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_alerts"] == 0
        assert stats["metric_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_health(
            gateway_id="gw-001",
            gateway_metric=GatewayMetric.ERROR_RATE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_gateways"] == 1
        assert "error_rate" in stats["metric_distribution"]
