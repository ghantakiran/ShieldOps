"""Tests for shieldops.sla.slo_aggregator — SLOAggregationDashboard."""

from __future__ import annotations

from shieldops.sla.slo_aggregator import (
    AggregationLevel,
    AggregationRecord,
    AggregationRule,
    AggregationWindow,
    ComplianceStatus,
    SLOAggregationDashboard,
    SLOAggregationReport,
)


def _engine(**kw) -> SLOAggregationDashboard:
    return SLOAggregationDashboard(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AggregationLevel (5)
    def test_level_platform(self):
        assert AggregationLevel.PLATFORM == "platform"

    def test_level_team(self):
        assert AggregationLevel.TEAM == "team"

    def test_level_service(self):
        assert AggregationLevel.SERVICE == "service"

    def test_level_endpoint(self):
        assert AggregationLevel.ENDPOINT == "endpoint"

    def test_level_custom(self):
        assert AggregationLevel.CUSTOM == "custom"

    # ComplianceStatus (5)
    def test_status_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_status_at_risk(self):
        assert ComplianceStatus.AT_RISK == "at_risk"

    def test_status_breaching(self):
        assert ComplianceStatus.BREACHING == "breaching"

    def test_status_unknown(self):
        assert ComplianceStatus.UNKNOWN == "unknown"

    def test_status_exempt(self):
        assert ComplianceStatus.EXEMPT == "exempt"

    # AggregationWindow (5)
    def test_window_hourly(self):
        assert AggregationWindow.HOURLY == "hourly"

    def test_window_daily(self):
        assert AggregationWindow.DAILY == "daily"

    def test_window_weekly(self):
        assert AggregationWindow.WEEKLY == "weekly"

    def test_window_monthly(self):
        assert AggregationWindow.MONTHLY == "monthly"

    def test_window_quarterly(self):
        assert AggregationWindow.QUARTERLY == "quarterly"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_aggregation_record_defaults(self):
        r = AggregationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.level == AggregationLevel.PLATFORM
        assert r.status == ComplianceStatus.COMPLIANT
        assert r.window == AggregationWindow.HOURLY
        assert r.compliance_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_aggregation_rule_defaults(self):
        r = AggregationRule()
        assert r.id
        assert r.rule_name == ""
        assert r.level == AggregationLevel.SERVICE
        assert r.status == ComplianceStatus.COMPLIANT
        assert r.target_compliance_pct == 99.9
        assert r.evaluation_window_hours == 24.0
        assert r.created_at > 0

    def test_slo_aggregation_report_defaults(self):
        r = SLOAggregationReport()
        assert r.total_aggregations == 0
        assert r.total_rules == 0
        assert r.compliant_rate_pct == 0.0
        assert r.by_level == {}
        assert r.by_status == {}
        assert r.breaching_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_aggregation
# -------------------------------------------------------------------


class TestRecordAggregation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_aggregation("api-gateway", level=AggregationLevel.SERVICE)
        assert r.service_name == "api-gateway"
        assert r.level == AggregationLevel.SERVICE

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_aggregation(
            "payment-service",
            level=AggregationLevel.ENDPOINT,
            status=ComplianceStatus.BREACHING,
            window=AggregationWindow.DAILY,
            compliance_pct=88.5,
            details="SLO breach on payment endpoint",
        )
        assert r.status == ComplianceStatus.BREACHING
        assert r.window == AggregationWindow.DAILY
        assert r.compliance_pct == 88.5
        assert r.details == "SLO breach on payment endpoint"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_aggregation(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_aggregation
# -------------------------------------------------------------------


class TestGetAggregation:
    def test_found(self):
        eng = _engine()
        r = eng.record_aggregation("api-gateway")
        assert eng.get_aggregation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_aggregation("nonexistent") is None


# -------------------------------------------------------------------
# list_aggregations
# -------------------------------------------------------------------


class TestListAggregations:
    def test_list_all(self):
        eng = _engine()
        eng.record_aggregation("svc-a")
        eng.record_aggregation("svc-b")
        assert len(eng.list_aggregations()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_aggregation("svc-a")
        eng.record_aggregation("svc-b")
        results = eng.list_aggregations(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_aggregation("svc-a", level=AggregationLevel.PLATFORM)
        eng.record_aggregation("svc-b", level=AggregationLevel.TEAM)
        results = eng.list_aggregations(level=AggregationLevel.TEAM)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rl = eng.add_rule(
            "slo-compliance",
            level=AggregationLevel.SERVICE,
            status=ComplianceStatus.COMPLIANT,
            target_compliance_pct=99.9,
            evaluation_window_hours=48.0,
        )
        assert rl.rule_name == "slo-compliance"
        assert rl.level == AggregationLevel.SERVICE
        assert rl.target_compliance_pct == 99.9

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_compliance_status
# -------------------------------------------------------------------


class TestAnalyzeComplianceStatus:
    def test_with_data(self):
        eng = _engine(min_compliance_pct=90.0)
        eng.record_aggregation("svc-a", compliance_pct=95.0)
        eng.record_aggregation("svc-a", compliance_pct=85.0)
        eng.record_aggregation("svc-a", compliance_pct=100.0)
        result = eng.analyze_compliance_status("svc-a")
        assert result["avg_compliance"] == 93.33
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_compliance_status("unknown-svc")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_compliance_pct=90.0)
        eng.record_aggregation("svc-a", compliance_pct=95.0)
        eng.record_aggregation("svc-a", compliance_pct=99.0)
        result = eng.analyze_compliance_status("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_at_risk_slos
# -------------------------------------------------------------------


class TestIdentifyAtRiskSlos:
    def test_with_at_risk(self):
        eng = _engine()
        eng.record_aggregation("svc-a", status=ComplianceStatus.AT_RISK)
        eng.record_aggregation("svc-a", status=ComplianceStatus.BREACHING)
        eng.record_aggregation("svc-b", status=ComplianceStatus.COMPLIANT)
        results = eng.identify_at_risk_slos()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["risk_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_at_risk_slos() == []

    def test_single_at_risk_not_returned(self):
        eng = _engine()
        eng.record_aggregation("svc-a", status=ComplianceStatus.AT_RISK)
        assert eng.identify_at_risk_slos() == []


# -------------------------------------------------------------------
# rank_by_compliance_rate
# -------------------------------------------------------------------


class TestRankByComplianceRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_aggregation("svc-a", compliance_pct=80.0)
        eng.record_aggregation("svc-b", compliance_pct=99.0)
        results = eng.rank_by_compliance_rate()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_compliance_pct"] == 99.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance_rate() == []


# -------------------------------------------------------------------
# detect_compliance_trends
# -------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_aggregation("svc-a")
        eng.record_aggregation("svc-b")
        results = eng.detect_compliance_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_compliance_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_aggregation("svc-a")
        assert eng.detect_compliance_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_aggregation("svc-a", status=ComplianceStatus.BREACHING)
        eng.record_aggregation("svc-b", status=ComplianceStatus.COMPLIANT)
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_aggregations == 2
        assert report.total_rules == 1
        assert report.by_level != {}
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_aggregations == 0
        assert report.compliant_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_aggregation("svc-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_aggregations"] == 0
        assert stats["total_rules"] == 0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_compliance_pct=95.0)
        eng.record_aggregation("svc-a", level=AggregationLevel.PLATFORM)
        eng.record_aggregation("svc-b", level=AggregationLevel.TEAM)
        eng.add_rule("rule-1")
        stats = eng.get_stats()
        assert stats["total_aggregations"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_compliance_pct"] == 95.0
