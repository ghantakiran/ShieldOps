"""Tests for shieldops.audit.audit_readiness_scorer — AuditReadinessScorer."""

from __future__ import annotations

from shieldops.audit.audit_readiness_scorer import (
    AuditReadinessReport,
    AuditReadinessScorer,
    AuditType,
    ReadinessAnalysis,
    ReadinessArea,
    ReadinessGrade,
    ReadinessRecord,
)


def _engine(**kw) -> AuditReadinessScorer:
    return AuditReadinessScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_audittype_soc2_type2(self):
        assert AuditType.SOC2_TYPE2 == "soc2_type2"

    def test_audittype_iso_27001(self):
        assert AuditType.ISO_27001 == "iso_27001"

    def test_audittype_pci_dss(self):
        assert AuditType.PCI_DSS == "pci_dss"

    def test_audittype_hipaa(self):
        assert AuditType.HIPAA == "hipaa"

    def test_audittype_gdpr(self):
        assert AuditType.GDPR == "gdpr"

    def test_readinessarea_documentation(self):
        assert ReadinessArea.DOCUMENTATION == "documentation"

    def test_readinessarea_evidence(self):
        assert ReadinessArea.EVIDENCE == "evidence"

    def test_readinessarea_controls(self):
        assert ReadinessArea.CONTROLS == "controls"

    def test_readinessarea_processes(self):
        assert ReadinessArea.PROCESSES == "processes"

    def test_readinessarea_personnel(self):
        assert ReadinessArea.PERSONNEL == "personnel"

    def test_readinessgrade_audit_ready(self):
        assert ReadinessGrade.AUDIT_READY == "audit_ready"

    def test_readinessgrade_mostly_ready(self):
        assert ReadinessGrade.MOSTLY_READY == "mostly_ready"

    def test_readinessgrade_needs_work(self):
        assert ReadinessGrade.NEEDS_WORK == "needs_work"

    def test_readinessgrade_significant_gaps(self):
        assert ReadinessGrade.SIGNIFICANT_GAPS == "significant_gaps"

    def test_readinessgrade_not_ready(self):
        assert ReadinessGrade.NOT_READY == "not_ready"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_readinessrecord_defaults(self):
        r = ReadinessRecord()
        assert r.id
        assert r.audit_name == ""
        assert r.readiness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_readinessanalysis_defaults(self):
        c = ReadinessAnalysis()
        assert c.id
        assert c.audit_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_auditreadinessreport_defaults(self):
        r = AuditReadinessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_readiness_count == 0
        assert r.avg_readiness_score == 0
        assert r.by_type == {}
        assert r.by_area == {}
        assert r.by_grade == {}
        assert r.top_low_readiness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_readiness
# ---------------------------------------------------------------------------


class TestRecordReadiness:
    def test_basic(self):
        eng = _engine()
        r = eng.record_readiness(
            audit_name="test-item",
            audit_type=AuditType.ISO_27001,
            readiness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.audit_name == "test-item"
        assert r.readiness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_readiness(audit_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_readiness
# ---------------------------------------------------------------------------


class TestGetReadiness:
    def test_found(self):
        eng = _engine()
        r = eng.record_readiness(audit_name="test-item")
        result = eng.get_readiness(r.id)
        assert result is not None
        assert result.audit_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_readiness("nonexistent") is None


# ---------------------------------------------------------------------------
# list_readiness
# ---------------------------------------------------------------------------


class TestListReadiness:
    def test_list_all(self):
        eng = _engine()
        eng.record_readiness(audit_name="ITEM-001")
        eng.record_readiness(audit_name="ITEM-002")
        assert len(eng.list_readiness()) == 2

    def test_filter_by_audit_type(self):
        eng = _engine()
        eng.record_readiness(audit_name="ITEM-001", audit_type=AuditType.SOC2_TYPE2)
        eng.record_readiness(audit_name="ITEM-002", audit_type=AuditType.ISO_27001)
        results = eng.list_readiness(audit_type=AuditType.SOC2_TYPE2)
        assert len(results) == 1

    def test_filter_by_readiness_area(self):
        eng = _engine()
        eng.record_readiness(audit_name="ITEM-001", readiness_area=ReadinessArea.DOCUMENTATION)
        eng.record_readiness(audit_name="ITEM-002", readiness_area=ReadinessArea.EVIDENCE)
        results = eng.list_readiness(readiness_area=ReadinessArea.DOCUMENTATION)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_readiness(audit_name="ITEM-001", team="security")
        eng.record_readiness(audit_name="ITEM-002", team="platform")
        results = eng.list_readiness(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_readiness(audit_name=f"ITEM-{i}")
        assert len(eng.list_readiness(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            audit_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.audit_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(audit_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_type_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_readiness(
            audit_name="ITEM-001", audit_type=AuditType.SOC2_TYPE2, readiness_score=90.0
        )
        eng.record_readiness(
            audit_name="ITEM-002", audit_type=AuditType.SOC2_TYPE2, readiness_score=70.0
        )
        result = eng.analyze_type_distribution()
        assert "soc2_type2" in result
        assert result["soc2_type2"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_readiness_audits
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(readiness_threshold=75.0)
        eng.record_readiness(audit_name="ITEM-001", readiness_score=30.0)
        eng.record_readiness(audit_name="ITEM-002", readiness_score=90.0)
        results = eng.identify_low_readiness_audits()
        assert len(results) == 1
        assert results[0]["audit_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(readiness_threshold=75.0)
        eng.record_readiness(audit_name="ITEM-001", readiness_score=50.0)
        eng.record_readiness(audit_name="ITEM-002", readiness_score=30.0)
        results = eng.identify_low_readiness_audits()
        assert len(results) == 2
        assert results[0]["readiness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_readiness_audits() == []


# ---------------------------------------------------------------------------
# rank_by_readiness_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_readiness(audit_name="ITEM-001", service="auth-svc", readiness_score=90.0)
        eng.record_readiness(audit_name="ITEM-002", service="api-gw", readiness_score=50.0)
        results = eng.rank_by_readiness_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_readiness_score() == []


# ---------------------------------------------------------------------------
# detect_readiness_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(audit_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(audit_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(audit_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(audit_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(audit_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_readiness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(readiness_threshold=75.0)
        eng.record_readiness(audit_name="test-item", readiness_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, AuditReadinessReport)
        assert report.total_records == 1
        assert report.low_readiness_count == 1
        assert len(report.top_low_readiness) == 1
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
        eng.record_readiness(audit_name="ITEM-001")
        eng.add_analysis(audit_name="ITEM-001")
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
        eng.record_readiness(
            audit_name="ITEM-001",
            audit_type=AuditType.SOC2_TYPE2,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
