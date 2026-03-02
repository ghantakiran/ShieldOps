"""Tests for shieldops.compliance.continuous_compliance_monitor — ContinuousComplianceMonitor."""

from __future__ import annotations

from shieldops.compliance.continuous_compliance_monitor import (
    ComplianceMonitorAnalysis,
    ComplianceMonitorRecord,
    ComplianceMonitorReport,
    ContinuousComplianceMonitor,
    DriftSeverity,
    Framework,
    MonitoringFrequency,
)


def _engine(**kw) -> ContinuousComplianceMonitor:
    return ContinuousComplianceMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_framework_soc2(self):
        assert Framework.SOC2 == "soc2"

    def test_framework_gdpr(self):
        assert Framework.GDPR == "gdpr"

    def test_framework_hipaa(self):
        assert Framework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert Framework.PCI_DSS == "pci_dss"

    def test_framework_nist_csf(self):
        assert Framework.NIST_CSF == "nist_csf"

    def test_driftseverity_critical(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_driftseverity_high(self):
        assert DriftSeverity.HIGH == "high"

    def test_driftseverity_medium(self):
        assert DriftSeverity.MEDIUM == "medium"

    def test_driftseverity_low(self):
        assert DriftSeverity.LOW == "low"

    def test_driftseverity_informational(self):
        assert DriftSeverity.INFORMATIONAL == "informational"

    def test_monitoringfrequency_real_time(self):
        assert MonitoringFrequency.REAL_TIME == "real_time"

    def test_monitoringfrequency_hourly(self):
        assert MonitoringFrequency.HOURLY == "hourly"

    def test_monitoringfrequency_daily(self):
        assert MonitoringFrequency.DAILY == "daily"

    def test_monitoringfrequency_weekly(self):
        assert MonitoringFrequency.WEEKLY == "weekly"

    def test_monitoringfrequency_monthly(self):
        assert MonitoringFrequency.MONTHLY == "monthly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_compliancemonitorrecord_defaults(self):
        r = ComplianceMonitorRecord()
        assert r.id
        assert r.control_name == ""
        assert r.compliance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_compliancemonitoranalysis_defaults(self):
        c = ComplianceMonitorAnalysis()
        assert c.id
        assert c.control_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_compliancemonitorreport_defaults(self):
        r = ComplianceMonitorReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_compliance_count == 0
        assert r.avg_compliance_score == 0
        assert r.by_framework == {}
        assert r.by_severity == {}
        assert r.by_frequency == {}
        assert r.top_low_compliance == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_control
# ---------------------------------------------------------------------------


class TestRecordControl:
    def test_basic(self):
        eng = _engine()
        r = eng.record_control(
            control_name="test-item",
            framework=Framework.GDPR,
            compliance_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.control_name == "test-item"
        assert r.compliance_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_control(control_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_control
# ---------------------------------------------------------------------------


class TestGetControl:
    def test_found(self):
        eng = _engine()
        r = eng.record_control(control_name="test-item")
        result = eng.get_control(r.id)
        assert result is not None
        assert result.control_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_control("nonexistent") is None


# ---------------------------------------------------------------------------
# list_controls
# ---------------------------------------------------------------------------


class TestListControls:
    def test_list_all(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001")
        eng.record_control(control_name="ITEM-002")
        assert len(eng.list_controls()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", framework=Framework.SOC2)
        eng.record_control(control_name="ITEM-002", framework=Framework.GDPR)
        results = eng.list_controls(framework=Framework.SOC2)
        assert len(results) == 1

    def test_filter_by_drift_severity(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", drift_severity=DriftSeverity.CRITICAL)
        eng.record_control(control_name="ITEM-002", drift_severity=DriftSeverity.HIGH)
        results = eng.list_controls(drift_severity=DriftSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", team="security")
        eng.record_control(control_name="ITEM-002", team="platform")
        results = eng.list_controls(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_control(control_name=f"ITEM-{i}")
        assert len(eng.list_controls(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            control_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.control_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(control_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_framework_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", framework=Framework.SOC2, compliance_score=90.0)
        eng.record_control(control_name="ITEM-002", framework=Framework.SOC2, compliance_score=70.0)
        result = eng.analyze_framework_distribution()
        assert "soc2" in result
        assert result["soc2"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_framework_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_compliance_controls
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(compliance_drift_threshold=85.0)
        eng.record_control(control_name="ITEM-001", compliance_score=30.0)
        eng.record_control(control_name="ITEM-002", compliance_score=90.0)
        results = eng.identify_low_compliance_controls()
        assert len(results) == 1
        assert results[0]["control_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(compliance_drift_threshold=85.0)
        eng.record_control(control_name="ITEM-001", compliance_score=50.0)
        eng.record_control(control_name="ITEM-002", compliance_score=30.0)
        results = eng.identify_low_compliance_controls()
        assert len(results) == 2
        assert results[0]["compliance_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_compliance_controls() == []


# ---------------------------------------------------------------------------
# rank_by_compliance_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", service="auth-svc", compliance_score=90.0)
        eng.record_control(control_name="ITEM-002", service="api-gw", compliance_score=50.0)
        results = eng.rank_by_compliance_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance_score() == []


# ---------------------------------------------------------------------------
# detect_compliance_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(control_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(control_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(control_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(control_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(control_name="ITEM-004", analysis_score=80.0)
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
        eng = _engine(compliance_drift_threshold=85.0)
        eng.record_control(control_name="test-item", compliance_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, ComplianceMonitorReport)
        assert report.total_records == 1
        assert report.low_compliance_count == 1
        assert len(report.top_low_compliance) == 1
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
        eng.record_control(control_name="ITEM-001")
        eng.add_analysis(control_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_control(
            control_name="ITEM-001",
            framework=Framework.SOC2,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
