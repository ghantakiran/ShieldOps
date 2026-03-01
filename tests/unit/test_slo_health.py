"""Tests for shieldops.sla.slo_health — SLOHealthDashboard."""

from __future__ import annotations

from shieldops.sla.slo_health import (
    HealthStatus,
    SLOCategory,
    SLOHealthDashboard,
    SLOHealthRecord,
    SLOHealthReport,
    SLOHealthRule,
    TrendDirection,
)


def _engine(**kw) -> SLOHealthDashboard:
    return SLOHealthDashboard(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_healthy(self):
        assert HealthStatus.HEALTHY == "healthy"

    def test_status_degraded(self):
        assert HealthStatus.DEGRADED == "degraded"

    def test_status_at_risk(self):
        assert HealthStatus.AT_RISK == "at_risk"

    def test_status_breaching(self):
        assert HealthStatus.BREACHING == "breaching"

    def test_status_unknown(self):
        assert HealthStatus.UNKNOWN == "unknown"

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

    def test_trend_improving(self):
        assert TrendDirection.IMPROVING == "improving"

    def test_trend_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_trend_declining(self):
        assert TrendDirection.DECLINING == "declining"

    def test_trend_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert TrendDirection.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_slo_health_record_defaults(self):
        r = SLOHealthRecord()
        assert r.id
        assert r.service_name == ""
        assert r.health_status == HealthStatus.UNKNOWN
        assert r.slo_category == SLOCategory.AVAILABILITY
        assert r.trend_direction == TrendDirection.STABLE
        assert r.health_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_slo_health_rule_defaults(self):
        ru = SLOHealthRule()
        assert ru.id
        assert ru.service_pattern == ""
        assert ru.slo_category == SLOCategory.AVAILABILITY
        assert ru.min_score == 0.0
        assert ru.alert_on_breach is True
        assert ru.description == ""
        assert ru.created_at > 0

    def test_slo_health_report_defaults(self):
        r = SLOHealthReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.healthy_count == 0
        assert r.avg_health_score == 0.0
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.by_trend == {}
        assert r.at_risk_services == []
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
            service_name="api-gateway",
            health_status=HealthStatus.HEALTHY,
            slo_category=SLOCategory.LATENCY,
            trend_direction=TrendDirection.IMPROVING,
            health_score=95.0,
            team="sre",
        )
        assert r.service_name == "api-gateway"
        assert r.health_status == HealthStatus.HEALTHY
        assert r.slo_category == SLOCategory.LATENCY
        assert r.trend_direction == TrendDirection.IMPROVING
        assert r.health_score == 95.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_health(service_name=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_health
# ---------------------------------------------------------------------------


class TestGetHealth:
    def test_found(self):
        eng = _engine()
        r = eng.record_health(
            service_name="api-gateway",
            health_score=92.0,
        )
        result = eng.get_health(r.id)
        assert result is not None
        assert result.health_score == 92.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_health("nonexistent") is None


# ---------------------------------------------------------------------------
# list_health_records
# ---------------------------------------------------------------------------


class TestListHealthRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_health(service_name="svc-1")
        eng.record_health(service_name="svc-2")
        assert len(eng.list_health_records()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_health(
            service_name="svc-1",
            health_status=HealthStatus.HEALTHY,
        )
        eng.record_health(
            service_name="svc-2",
            health_status=HealthStatus.BREACHING,
        )
        results = eng.list_health_records(status=HealthStatus.HEALTHY)
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_health(
            service_name="svc-1",
            slo_category=SLOCategory.LATENCY,
        )
        eng.record_health(
            service_name="svc-2",
            slo_category=SLOCategory.ERROR_RATE,
        )
        results = eng.list_health_records(category=SLOCategory.LATENCY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_health(service_name="svc-1", team="sre")
        eng.record_health(service_name="svc-2", team="platform")
        results = eng.list_health_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_health(service_name=f"svc-{i}")
        assert len(eng.list_health_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            service_pattern="api-*",
            slo_category=SLOCategory.AVAILABILITY,
            min_score=99.0,
            alert_on_breach=True,
            description="Critical API SLO",
        )
        assert ru.service_pattern == "api-*"
        assert ru.slo_category == SLOCategory.AVAILABILITY
        assert ru.min_score == 99.0
        assert ru.alert_on_breach is True
        assert ru.description == "Critical API SLO"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(service_pattern=f"svc-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_health_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeHealthDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_health(
            service_name="svc-1",
            health_status=HealthStatus.HEALTHY,
            health_score=95.0,
        )
        eng.record_health(
            service_name="svc-2",
            health_status=HealthStatus.HEALTHY,
            health_score=85.0,
        )
        result = eng.analyze_health_distribution()
        assert "healthy" in result
        assert result["healthy"]["count"] == 2
        assert result["healthy"]["avg_health_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_health_distribution() == {}


# ---------------------------------------------------------------------------
# identify_at_risk
# ---------------------------------------------------------------------------


class TestIdentifyAtRisk:
    def test_detects_at_risk(self):
        eng = _engine()
        eng.record_health(
            service_name="svc-1",
            health_status=HealthStatus.AT_RISK,
        )
        eng.record_health(
            service_name="svc-2",
            health_status=HealthStatus.HEALTHY,
        )
        results = eng.identify_at_risk()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-1"

    def test_detects_breaching(self):
        eng = _engine()
        eng.record_health(
            service_name="svc-1",
            health_status=HealthStatus.BREACHING,
        )
        results = eng.identify_at_risk()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_at_risk() == []


# ---------------------------------------------------------------------------
# rank_by_health_score
# ---------------------------------------------------------------------------


class TestRankByHealthScore:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_health(service_name="svc-1", team="sre", health_score=95.0)
        eng.record_health(service_name="svc-2", team="sre", health_score=85.0)
        eng.record_health(service_name="svc-3", team="platform", health_score=60.0)
        results = eng.rank_by_health_score()
        assert len(results) == 2
        assert results[0]["team"] == "platform"
        assert results[0]["avg_health_score"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_health_score() == []


# ---------------------------------------------------------------------------
# detect_health_trends
# ---------------------------------------------------------------------------


class TestDetectHealthTrends:
    def test_stable(self):
        eng = _engine()
        for score in [80.0, 80.0, 80.0, 80.0]:
            eng.add_rule(service_pattern="s", min_score=score)
        result = eng.detect_health_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [70.0, 70.0, 90.0, 90.0]:
            eng.add_rule(service_pattern="s", min_score=score)
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
        eng.record_health(
            service_name="svc-1",
            health_status=HealthStatus.AT_RISK,
            health_score=50.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SLOHealthReport)
        assert report.total_records == 1
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
        eng.record_health(service_name="svc-1")
        eng.add_rule(service_pattern="s1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_health(
            service_name="svc-1",
            health_status=HealthStatus.DEGRADED,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "degraded" in stats["status_distribution"]
