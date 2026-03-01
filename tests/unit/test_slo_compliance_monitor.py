"""Tests for shieldops.sla.slo_compliance_monitor — SLOComplianceMonitor."""

from __future__ import annotations

from shieldops.sla.slo_compliance_monitor import (
    ComplianceCheck,
    ComplianceMetric,
    ComplianceRecord,
    ComplianceState,
    MonitoringFrequency,
    SLOComplianceMonitor,
    SLOComplianceReport,
)


def _engine(**kw) -> SLOComplianceMonitor:
    return SLOComplianceMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_state_compliant(self):
        assert ComplianceState.COMPLIANT == "compliant"

    def test_state_at_risk(self):
        assert ComplianceState.AT_RISK == "at_risk"

    def test_state_non_compliant(self):
        assert ComplianceState.NON_COMPLIANT == "non_compliant"

    def test_state_grace_period(self):
        assert ComplianceState.GRACE_PERIOD == "grace_period"

    def test_state_exempt(self):
        assert ComplianceState.EXEMPT == "exempt"

    def test_metric_availability(self):
        assert ComplianceMetric.AVAILABILITY == "availability"

    def test_metric_latency(self):
        assert ComplianceMetric.LATENCY == "latency"

    def test_metric_error_rate(self):
        assert ComplianceMetric.ERROR_RATE == "error_rate"

    def test_metric_throughput(self):
        assert ComplianceMetric.THROUGHPUT == "throughput"

    def test_metric_saturation(self):
        assert ComplianceMetric.SATURATION == "saturation"

    def test_frequency_real_time(self):
        assert MonitoringFrequency.REAL_TIME == "real_time"

    def test_frequency_minute(self):
        assert MonitoringFrequency.MINUTE == "minute"

    def test_frequency_hourly(self):
        assert MonitoringFrequency.HOURLY == "hourly"

    def test_frequency_daily(self):
        assert MonitoringFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert MonitoringFrequency.WEEKLY == "weekly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_compliance_record_defaults(self):
        r = ComplianceRecord()
        assert r.id
        assert r.slo_id == ""
        assert r.compliance_state == ComplianceState.COMPLIANT
        assert r.compliance_metric == ComplianceMetric.AVAILABILITY
        assert r.monitoring_frequency == MonitoringFrequency.REAL_TIME
        assert r.compliance_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_compliance_check_defaults(self):
        c = ComplianceCheck()
        assert c.id
        assert c.slo_id == ""
        assert c.compliance_state == ComplianceState.COMPLIANT
        assert c.check_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_slo_compliance_report_defaults(self):
        r = SLOComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_checks == 0
        assert r.non_compliant_count == 0
        assert r.avg_compliance_pct == 0.0
        assert r.by_state == {}
        assert r.by_metric == {}
        assert r.by_frequency == {}
        assert r.top_non_compliant == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_compliance
# ---------------------------------------------------------------------------


class TestRecordCompliance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_compliance(
            slo_id="SLO-001",
            compliance_state=ComplianceState.COMPLIANT,
            compliance_metric=ComplianceMetric.AVAILABILITY,
            monitoring_frequency=MonitoringFrequency.REAL_TIME,
            compliance_pct=99.5,
            service="api-gw",
            team="sre",
        )
        assert r.slo_id == "SLO-001"
        assert r.compliance_state == ComplianceState.COMPLIANT
        assert r.compliance_metric == ComplianceMetric.AVAILABILITY
        assert r.monitoring_frequency == MonitoringFrequency.REAL_TIME
        assert r.compliance_pct == 99.5
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_compliance(slo_id=f"SLO-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_compliance
# ---------------------------------------------------------------------------


class TestGetCompliance:
    def test_found(self):
        eng = _engine()
        r = eng.record_compliance(
            slo_id="SLO-001",
            compliance_state=ComplianceState.NON_COMPLIANT,
        )
        result = eng.get_compliance(r.id)
        assert result is not None
        assert result.compliance_state == ComplianceState.NON_COMPLIANT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_compliance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_compliance
# ---------------------------------------------------------------------------


class TestListCompliance:
    def test_list_all(self):
        eng = _engine()
        eng.record_compliance(slo_id="SLO-001")
        eng.record_compliance(slo_id="SLO-002")
        assert len(eng.list_compliance()) == 2

    def test_filter_by_state(self):
        eng = _engine()
        eng.record_compliance(
            slo_id="SLO-001",
            compliance_state=ComplianceState.COMPLIANT,
        )
        eng.record_compliance(
            slo_id="SLO-002",
            compliance_state=ComplianceState.NON_COMPLIANT,
        )
        results = eng.list_compliance(
            state=ComplianceState.COMPLIANT,
        )
        assert len(results) == 1

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_compliance(
            slo_id="SLO-001",
            compliance_metric=ComplianceMetric.AVAILABILITY,
        )
        eng.record_compliance(
            slo_id="SLO-002",
            compliance_metric=ComplianceMetric.LATENCY,
        )
        results = eng.list_compliance(
            metric=ComplianceMetric.AVAILABILITY,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_compliance(slo_id="SLO-001", service="api-gw")
        eng.record_compliance(slo_id="SLO-002", service="auth")
        results = eng.list_compliance(service="api-gw")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_compliance(slo_id=f"SLO-{i}")
        assert len(eng.list_compliance(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_check
# ---------------------------------------------------------------------------


class TestAddCheck:
    def test_basic(self):
        eng = _engine()
        c = eng.add_check(
            slo_id="SLO-001",
            compliance_state=ComplianceState.AT_RISK,
            check_score=85.0,
            threshold=95.0,
            breached=True,
            description="availability below target",
        )
        assert c.slo_id == "SLO-001"
        assert c.compliance_state == ComplianceState.AT_RISK
        assert c.check_score == 85.0
        assert c.threshold == 95.0
        assert c.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_check(slo_id=f"SLO-{i}")
        assert len(eng._checks) == 2


# ---------------------------------------------------------------------------
# analyze_compliance_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeComplianceDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_compliance(
            slo_id="SLO-001",
            compliance_state=ComplianceState.COMPLIANT,
            compliance_pct=99.0,
        )
        eng.record_compliance(
            slo_id="SLO-002",
            compliance_state=ComplianceState.COMPLIANT,
            compliance_pct=98.0,
        )
        result = eng.analyze_compliance_distribution()
        assert "compliant" in result
        assert result["compliant"]["count"] == 2
        assert result["compliant"]["avg_compliance_pct"] == 98.5

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_compliance_distribution() == {}


# ---------------------------------------------------------------------------
# identify_non_compliant
# ---------------------------------------------------------------------------


class TestIdentifyNonCompliant:
    def test_detects_non_compliant_and_at_risk(self):
        eng = _engine()
        eng.record_compliance(
            slo_id="SLO-001",
            compliance_state=ComplianceState.NON_COMPLIANT,
        )
        eng.record_compliance(
            slo_id="SLO-002",
            compliance_state=ComplianceState.AT_RISK,
        )
        eng.record_compliance(
            slo_id="SLO-003",
            compliance_state=ComplianceState.COMPLIANT,
        )
        results = eng.identify_non_compliant()
        assert len(results) == 2
        assert results[0]["slo_id"] == "SLO-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant() == []


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankByCompliance:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_compliance(slo_id="SLO-001", service="api-gw", compliance_pct=99.0)
        eng.record_compliance(slo_id="SLO-002", service="auth", compliance_pct=85.0)
        results = eng.rank_by_compliance()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_compliance_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_compliance_trends
# ---------------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_check(slo_id="SLO-001", check_score=50.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_check(slo_id="SLO-001", check_score=20.0)
        eng.add_check(slo_id="SLO-002", check_score=20.0)
        eng.add_check(slo_id="SLO-003", check_score=80.0)
        eng.add_check(slo_id="SLO-004", check_score=80.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_compliance(
            slo_id="SLO-001",
            compliance_state=ComplianceState.NON_COMPLIANT,
            compliance_metric=ComplianceMetric.AVAILABILITY,
            monitoring_frequency=MonitoringFrequency.REAL_TIME,
            compliance_pct=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SLOComplianceReport)
        assert report.total_records == 1
        assert report.non_compliant_count == 1
        assert len(report.top_non_compliant) == 1
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
        eng.record_compliance(slo_id="SLO-001")
        eng.add_check(slo_id="SLO-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._checks) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_checks"] == 0
        assert stats["state_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_compliance(
            slo_id="SLO-001",
            compliance_state=ComplianceState.COMPLIANT,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "compliant" in stats["state_distribution"]
