"""Tests for shieldops.compliance.licensing_audit_tracker."""

from __future__ import annotations

from shieldops.compliance.licensing_audit_tracker import (
    AuditScope,
    LicenseAnalysis,
    LicenseAuditRecord,
    LicenseStatus,
    LicensingAuditReport,
    LicensingAuditTracker,
    RemediationAction,
)


def _engine(**kw) -> LicensingAuditTracker:
    return LicensingAuditTracker(**kw)


class TestEnums:
    def test_licensestatus_compliant(self):
        assert LicenseStatus.COMPLIANT == "compliant"

    def test_licensestatus_non_compliant(self):
        assert LicenseStatus.NON_COMPLIANT == "non_compliant"

    def test_licensestatus_expiring(self):
        assert LicenseStatus.EXPIRING == "expiring"

    def test_licensestatus_expired(self):
        assert LicenseStatus.EXPIRED == "expired"

    def test_licensestatus_under_review(self):
        assert LicenseStatus.UNDER_REVIEW == "under_review"

    def test_auditscope_full(self):
        assert AuditScope.FULL == "full"

    def test_auditscope_targeted(self):
        assert AuditScope.TARGETED == "targeted"

    def test_auditscope_spot_check(self):
        assert AuditScope.SPOT_CHECK == "spot_check"

    def test_auditscope_renewal(self):
        assert AuditScope.RENEWAL == "renewal"

    def test_auditscope_vendor(self):
        assert AuditScope.VENDOR == "vendor"

    def test_remediationaction_purchase(self):
        assert RemediationAction.PURCHASE == "purchase"

    def test_remediationaction_remove(self):
        assert RemediationAction.REMOVE == "remove"

    def test_remediationaction_downgrade(self):
        assert RemediationAction.DOWNGRADE == "downgrade"

    def test_remediationaction_negotiate(self):
        assert RemediationAction.NEGOTIATE == "negotiate"

    def test_remediationaction_waiver(self):
        assert RemediationAction.WAIVER == "waiver"


class TestModels:
    def test_license_audit_record_defaults(self):
        r = LicenseAuditRecord()
        assert r.id
        assert r.license_status == LicenseStatus.UNDER_REVIEW
        assert r.audit_scope == AuditScope.FULL
        assert r.remediation_action == RemediationAction.PURCHASE
        assert r.license_count == 0
        assert r.used_count == 0
        assert r.cost == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_license_analysis_defaults(self):
        a = LicenseAnalysis()
        assert a.id
        assert a.license_status == LicenseStatus.UNDER_REVIEW
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_licensing_audit_report_defaults(self):
        r = LicensingAuditReport()
        assert r.id
        assert r.total_records == 0
        assert r.non_compliant_count == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_license_status == {}
        assert r.top_violations == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordLicenseAudit:
    def test_basic(self):
        eng = _engine()
        r = eng.record_license_audit(
            license_status=LicenseStatus.NON_COMPLIANT,
            audit_scope=AuditScope.TARGETED,
            remediation_action=RemediationAction.PURCHASE,
            license_count=100,
            used_count=120,
            cost=5000.0,
            service="adobe-cc",
            team="design",
        )
        assert r.license_status == LicenseStatus.NON_COMPLIANT
        assert r.used_count == 120
        assert r.team == "design"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_license_audit(license_status=LicenseStatus.COMPLIANT)
        assert len(eng._records) == 3


class TestGetLicenseAudit:
    def test_found(self):
        eng = _engine()
        r = eng.record_license_audit(cost=2500.0)
        result = eng.get_license_audit(r.id)
        assert result is not None
        assert result.cost == 2500.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_license_audit("nonexistent") is None


class TestListLicenseAudits:
    def test_list_all(self):
        eng = _engine()
        eng.record_license_audit(license_status=LicenseStatus.COMPLIANT)
        eng.record_license_audit(license_status=LicenseStatus.NON_COMPLIANT)
        assert len(eng.list_license_audits()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_license_audit(license_status=LicenseStatus.COMPLIANT)
        eng.record_license_audit(license_status=LicenseStatus.NON_COMPLIANT)
        results = eng.list_license_audits(license_status=LicenseStatus.COMPLIANT)
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_license_audit(audit_scope=AuditScope.FULL)
        eng.record_license_audit(audit_scope=AuditScope.VENDOR)
        results = eng.list_license_audits(audit_scope=AuditScope.FULL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_license_audit(team="design")
        eng.record_license_audit(team="engineering")
        results = eng.list_license_audits(team="design")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_license_audit(license_status=LicenseStatus.COMPLIANT)
        assert len(eng.list_license_audits(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            license_status=LicenseStatus.EXPIRED,
            analysis_score=95.0,
            threshold=80.0,
            breached=True,
            description="expired license detected",
        )
        assert a.license_status == LicenseStatus.EXPIRED
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(license_status=LicenseStatus.COMPLIANT)
        assert len(eng._analyses) == 2


class TestAnalyzeStatusDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_license_audit(license_status=LicenseStatus.COMPLIANT, cost=500.0)
        eng.record_license_audit(license_status=LicenseStatus.COMPLIANT, cost=300.0)
        result = eng.analyze_status_distribution()
        assert "compliant" in result
        assert result["compliant"]["count"] == 2
        assert result["compliant"]["avg_cost"] == 400.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_status_distribution() == {}


class TestIdentifyNonCompliantLicenses:
    def test_detects_non_compliant(self):
        eng = _engine()
        eng.record_license_audit(license_status=LicenseStatus.NON_COMPLIANT)
        eng.record_license_audit(license_status=LicenseStatus.COMPLIANT)
        results = eng.identify_non_compliant_licenses()
        assert len(results) == 1

    def test_detects_expired(self):
        eng = _engine()
        eng.record_license_audit(license_status=LicenseStatus.EXPIRED)
        results = eng.identify_non_compliant_licenses()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant_licenses() == []


class TestRankByCost:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_license_audit(service="enterprise-tool", cost=10000.0)
        eng.record_license_audit(service="small-tool", cost=500.0)
        results = eng.rank_by_cost()
        assert results[0]["service"] == "enterprise-tool"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost() == []


class TestDetectComplianceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_license_audit(
            license_status=LicenseStatus.NON_COMPLIANT,
            audit_scope=AuditScope.FULL,
            remediation_action=RemediationAction.PURCHASE,
            cost=5000.0,
        )
        report = eng.generate_report()
        assert isinstance(report, LicensingAuditReport)
        assert report.total_records == 1
        assert report.non_compliant_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_license_audit(license_status=LicenseStatus.COMPLIANT)
        eng.add_analysis(license_status=LicenseStatus.COMPLIANT)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["license_status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_license_audit(
            license_status=LicenseStatus.COMPLIANT,
            service="tool-a",
            team="design",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "compliant" in stats["license_status_distribution"]
