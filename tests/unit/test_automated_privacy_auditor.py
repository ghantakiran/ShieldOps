"""Tests for shieldops.audit.automated_privacy_auditor — AutomatedPrivacyAuditor."""

from __future__ import annotations

from shieldops.audit.automated_privacy_auditor import (
    AuditAnalysis,
    AuditFinding,
    AuditRecord,
    AuditType,
    AutomatedPrivacyAuditor,
    PrivacyAuditReport,
    PrivacyControl,
)


def _engine(**kw) -> AutomatedPrivacyAuditor:
    return AutomatedPrivacyAuditor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_scheduled(self):
        assert AuditType.SCHEDULED == "scheduled"

    def test_type_triggered(self):
        assert AuditType.TRIGGERED == "triggered"

    def test_type_continuous(self):
        assert AuditType.CONTINUOUS == "continuous"

    def test_type_spot_check(self):
        assert AuditType.SPOT_CHECK == "spot_check"

    def test_type_annual(self):
        assert AuditType.ANNUAL == "annual"

    def test_control_data_minimization(self):
        assert PrivacyControl.DATA_MINIMIZATION == "data_minimization"

    def test_control_purpose_limitation(self):
        assert PrivacyControl.PURPOSE_LIMITATION == "purpose_limitation"

    def test_control_storage_limitation(self):
        assert PrivacyControl.STORAGE_LIMITATION == "storage_limitation"

    def test_control_accuracy(self):
        assert PrivacyControl.ACCURACY == "accuracy"

    def test_control_integrity(self):
        assert PrivacyControl.INTEGRITY == "integrity"

    def test_finding_compliant(self):
        assert AuditFinding.COMPLIANT == "compliant"

    def test_finding_minor_gap(self):
        assert AuditFinding.MINOR_GAP == "minor_gap"

    def test_finding_major_gap(self):
        assert AuditFinding.MAJOR_GAP == "major_gap"

    def test_finding_critical_violation(self):
        assert AuditFinding.CRITICAL_VIOLATION == "critical_violation"

    def test_finding_not_applicable(self):
        assert AuditFinding.NOT_APPLICABLE == "not_applicable"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_audit_record_defaults(self):
        r = AuditRecord()
        assert r.id
        assert r.audit_id == ""
        assert r.audit_type == AuditType.SCHEDULED
        assert r.privacy_control == PrivacyControl.DATA_MINIMIZATION
        assert r.audit_finding == AuditFinding.COMPLIANT
        assert r.control_score == 0.0
        assert r.auditor == ""
        assert r.business_unit == ""
        assert r.created_at > 0

    def test_audit_analysis_defaults(self):
        a = AuditAnalysis()
        assert a.id
        assert a.audit_id == ""
        assert a.audit_type == AuditType.SCHEDULED
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PrivacyAuditReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_control_score == 0.0
        assert r.by_audit_type == {}
        assert r.by_control == {}
        assert r.by_finding == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_audit / get_audit
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_audit(
            audit_id="audit-001",
            audit_type=AuditType.ANNUAL,
            privacy_control=PrivacyControl.ACCURACY,
            audit_finding=AuditFinding.MINOR_GAP,
            control_score=80.0,
            auditor="auditor-a",
            business_unit="finance",
        )
        assert r.audit_id == "audit-001"
        assert r.audit_type == AuditType.ANNUAL
        assert r.control_score == 80.0
        assert r.auditor == "auditor-a"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_audit(audit_id="audit-001", audit_type=AuditType.CONTINUOUS)
        result = eng.get_audit(r.id)
        assert result is not None
        assert result.audit_type == AuditType.CONTINUOUS

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_audit("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_audit(audit_id=f"audit-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_audits
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_audit(audit_id="a-001")
        eng.record_audit(audit_id="a-002")
        assert len(eng.list_audits()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_audit(audit_id="a-001", audit_type=AuditType.SCHEDULED)
        eng.record_audit(audit_id="a-002", audit_type=AuditType.TRIGGERED)
        results = eng.list_audits(audit_type=AuditType.SCHEDULED)
        assert len(results) == 1

    def test_filter_by_control(self):
        eng = _engine()
        eng.record_audit(audit_id="a-001", privacy_control=PrivacyControl.DATA_MINIMIZATION)
        eng.record_audit(audit_id="a-002", privacy_control=PrivacyControl.INTEGRITY)
        results = eng.list_audits(privacy_control=PrivacyControl.DATA_MINIMIZATION)
        assert len(results) == 1

    def test_filter_by_unit(self):
        eng = _engine()
        eng.record_audit(audit_id="a-001", business_unit="finance")
        eng.record_audit(audit_id="a-002", business_unit="legal")
        results = eng.list_audits(business_unit="finance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_audit(audit_id=f"a-{i}")
        assert len(eng.list_audits(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            audit_id="audit-001",
            audit_type=AuditType.SPOT_CHECK,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="control violation detected",
        )
        assert a.audit_id == "audit-001"
        assert a.audit_type == AuditType.SPOT_CHECK
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(audit_id=f"a-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(audit_id="audit-999", audit_type=AuditType.ANNUAL)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_control_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_audit(
            audit_id="a-001",
            privacy_control=PrivacyControl.ACCURACY,
            control_score=90.0,
        )
        eng.record_audit(
            audit_id="a-002",
            privacy_control=PrivacyControl.ACCURACY,
            control_score=70.0,
        )
        result = eng.analyze_control_distribution()
        assert "accuracy" in result
        assert result["accuracy"]["count"] == 2
        assert result["accuracy"]["avg_control_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_control_distribution() == {}


# ---------------------------------------------------------------------------
# identify_audit_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_audit(audit_id="a-001", control_score=60.0)
        eng.record_audit(audit_id="a-002", control_score=90.0)
        results = eng.identify_audit_gaps()
        assert len(results) == 1
        assert results[0]["audit_id"] == "a-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_audit(audit_id="a-001", control_score=50.0)
        eng.record_audit(audit_id="a-002", control_score=30.0)
        results = eng.identify_audit_gaps()
        assert results[0]["control_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_control
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_audit(audit_id="a-001", business_unit="finance", control_score=90.0)
        eng.record_audit(audit_id="a-002", business_unit="legal", control_score=50.0)
        results = eng.rank_by_control()
        assert results[0]["business_unit"] == "legal"
        assert results[0]["avg_control_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_control() == []


# ---------------------------------------------------------------------------
# detect_audit_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(audit_id="a-001", analysis_score=50.0)
        result = eng.detect_audit_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(audit_id="a-001", analysis_score=20.0)
        eng.add_analysis(audit_id="a-002", analysis_score=20.0)
        eng.add_analysis(audit_id="a-003", analysis_score=80.0)
        eng.add_analysis(audit_id="a-004", analysis_score=80.0)
        result = eng.detect_audit_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_audit_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_audit(
            audit_id="audit-001",
            audit_type=AuditType.TRIGGERED,
            privacy_control=PrivacyControl.DATA_MINIMIZATION,
            audit_finding=AuditFinding.CRITICAL_VIOLATION,
            control_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PrivacyAuditReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_audit(audit_id="a-001")
        eng.add_analysis(audit_id="a-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["audit_type_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(audit_id=f"a-{i}")
        assert len(eng._analyses) == 3
