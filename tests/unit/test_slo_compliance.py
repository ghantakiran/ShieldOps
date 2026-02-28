"""Tests for shieldops.sla.slo_compliance — SLOComplianceChecker."""

from __future__ import annotations

from shieldops.sla.slo_compliance import (
    CompliancePeriod,
    ComplianceRecord,
    ComplianceStatus,
    ComplianceViolation,
    SLOComplianceChecker,
    SLOComplianceReport,
    SLOType,
)


def _engine(**kw) -> SLOComplianceChecker:
    return SLOComplianceChecker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ComplianceStatus (5)
    def test_status_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_status_at_risk(self):
        assert ComplianceStatus.AT_RISK == "at_risk"

    def test_status_non_compliant(self):
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"

    def test_status_critical_breach(self):
        assert ComplianceStatus.CRITICAL_BREACH == "critical_breach"

    def test_status_unknown(self):
        assert ComplianceStatus.UNKNOWN == "unknown"

    # SLOType (5)
    def test_type_availability(self):
        assert SLOType.AVAILABILITY == "availability"

    def test_type_latency(self):
        assert SLOType.LATENCY == "latency"

    def test_type_error_rate(self):
        assert SLOType.ERROR_RATE == "error_rate"

    def test_type_throughput(self):
        assert SLOType.THROUGHPUT == "throughput"

    def test_type_durability(self):
        assert SLOType.DURABILITY == "durability"

    # CompliancePeriod (5)
    def test_period_hourly(self):
        assert CompliancePeriod.HOURLY == "hourly"

    def test_period_daily(self):
        assert CompliancePeriod.DAILY == "daily"

    def test_period_weekly(self):
        assert CompliancePeriod.WEEKLY == "weekly"

    def test_period_monthly(self):
        assert CompliancePeriod.MONTHLY == "monthly"

    def test_period_quarterly(self):
        assert CompliancePeriod.QUARTERLY == "quarterly"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_compliance_record_defaults(self):
        r = ComplianceRecord()
        assert r.id
        assert r.service_name == ""
        assert r.slo_name == ""
        assert r.slo_type == SLOType.AVAILABILITY
        assert r.period == CompliancePeriod.DAILY
        assert r.status == ComplianceStatus.COMPLIANT
        assert r.compliance_pct == 100.0
        assert r.target_pct == 99.0
        assert r.details == ""
        assert r.created_at > 0

    def test_compliance_violation_defaults(self):
        r = ComplianceViolation()
        assert r.id
        assert r.service_name == ""
        assert r.slo_name == ""
        assert r.slo_type == SLOType.AVAILABILITY
        assert r.status == ComplianceStatus.NON_COMPLIANT
        assert r.breach_pct == 0.0
        assert r.duration_minutes == 0.0
        assert r.root_cause == ""
        assert r.resolved is False
        assert r.created_at > 0

    def test_slo_compliance_report_defaults(self):
        r = SLOComplianceReport()
        assert r.total_compliances == 0
        assert r.total_violations == 0
        assert r.overall_compliance_pct == 0.0
        assert r.by_status == {}
        assert r.by_slo_type == {}
        assert r.non_compliant_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_compliance
# -------------------------------------------------------------------


class TestRecordCompliance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_compliance(
            "api",
            slo_name="availability-99",
            slo_type=SLOType.AVAILABILITY,
            compliance_pct=99.5,
        )
        assert r.service_name == "api"
        assert r.slo_name == "availability-99"
        assert r.compliance_pct == 99.5

    def test_with_status(self):
        eng = _engine()
        r = eng.record_compliance(
            "db",
            status=ComplianceStatus.NON_COMPLIANT,
            compliance_pct=95.0,
            target_pct=99.0,
        )
        assert r.status == ComplianceStatus.NON_COMPLIANT
        assert r.target_pct == 99.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_compliance(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_compliance
# -------------------------------------------------------------------


class TestGetCompliance:
    def test_found(self):
        eng = _engine()
        r = eng.record_compliance("api")
        assert eng.get_compliance(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_compliance("nonexistent") is None


# -------------------------------------------------------------------
# list_compliances
# -------------------------------------------------------------------


class TestListCompliances:
    def test_list_all(self):
        eng = _engine()
        eng.record_compliance("api")
        eng.record_compliance("db")
        assert len(eng.list_compliances()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_compliance("api")
        eng.record_compliance("db")
        results = eng.list_compliances(service_name="api")
        assert len(results) == 1

    def test_filter_by_slo_type(self):
        eng = _engine()
        eng.record_compliance("api", slo_type=SLOType.AVAILABILITY)
        eng.record_compliance("api", slo_type=SLOType.LATENCY)
        results = eng.list_compliances(slo_type=SLOType.LATENCY)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_violation
# -------------------------------------------------------------------


class TestAddViolation:
    def test_basic(self):
        eng = _engine()
        v = eng.add_violation(
            "api",
            slo_name="availability-99",
            breach_pct=2.5,
            duration_minutes=30.0,
            root_cause="DB outage",
        )
        assert v.service_name == "api"
        assert v.breach_pct == 2.5
        assert v.root_cause == "DB outage"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_violation(f"svc-{i}")
        assert len(eng._violations) == 2


# -------------------------------------------------------------------
# analyze_compliance_by_service
# -------------------------------------------------------------------


class TestAnalyzeComplianceByService:
    def test_with_data(self):
        eng = _engine(min_compliance_pct=99.0)
        eng.record_compliance("api", compliance_pct=99.5, status=ComplianceStatus.COMPLIANT)
        eng.record_compliance("api", compliance_pct=98.0, status=ComplianceStatus.NON_COMPLIANT)
        result = eng.analyze_compliance_by_service("api")
        assert result["service_name"] == "api"
        assert result["total_slos"] == 2
        assert result["avg_compliance_pct"] == 98.75

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_compliance_by_service("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_non_compliant_slos
# -------------------------------------------------------------------


class TestIdentifyNonCompliantSlos:
    def test_with_non_compliant(self):
        eng = _engine()
        eng.record_compliance(
            "api",
            slo_name="avail",
            status=ComplianceStatus.NON_COMPLIANT,
            compliance_pct=97.0,
            target_pct=99.0,
        )
        eng.record_compliance("db", status=ComplianceStatus.COMPLIANT, compliance_pct=99.9)
        results = eng.identify_non_compliant_slos()
        assert len(results) == 1
        assert results[0]["service_name"] == "api"
        assert results[0]["deficit_pct"] == 2.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant_slos() == []


# -------------------------------------------------------------------
# rank_by_compliance_score
# -------------------------------------------------------------------


class TestRankByComplianceScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_compliance("api", compliance_pct=99.9)
        eng.record_compliance("db", compliance_pct=95.0)
        results = eng.rank_by_compliance_score()
        assert results[0]["service_name"] == "api"
        assert results[0]["avg_compliance_pct"] == 99.9

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance_score() == []


# -------------------------------------------------------------------
# detect_compliance_trends
# -------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_degrading_trend(self):
        eng = _engine()
        # 2 out of last 3 records are non-compliant
        eng.record_compliance("api", status=ComplianceStatus.COMPLIANT, compliance_pct=99.5)
        eng.record_compliance("api", status=ComplianceStatus.NON_COMPLIANT, compliance_pct=97.0)
        eng.record_compliance("api", status=ComplianceStatus.CRITICAL_BREACH, compliance_pct=94.0)
        results = eng.detect_compliance_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "api"
        assert results[0]["degradation_detected"] is True

    def test_compliant_no_trend(self):
        eng = _engine()
        eng.record_compliance("api", status=ComplianceStatus.COMPLIANT, compliance_pct=99.9)
        assert eng.detect_compliance_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_compliance_pct=99.0)
        eng.record_compliance("api", compliance_pct=99.9, status=ComplianceStatus.COMPLIANT)
        eng.record_compliance(
            "db", compliance_pct=95.0, status=ComplianceStatus.NON_COMPLIANT, target_pct=99.0
        )
        eng.add_violation("db", breach_pct=4.0)
        report = eng.generate_report()
        assert report.total_compliances == 2
        assert report.total_violations == 1
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_compliances == 0
        assert report.recommendations != []


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_compliance("api")
        eng.add_violation("api")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._violations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_compliances"] == 0
        assert stats["total_violations"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_compliance("api", status=ComplianceStatus.COMPLIANT)
        eng.record_compliance("db", status=ComplianceStatus.NON_COMPLIANT)
        eng.add_violation("db")
        stats = eng.get_stats()
        assert stats["total_compliances"] == 2
        assert stats["total_violations"] == 1
        assert stats["unique_services"] == 2
