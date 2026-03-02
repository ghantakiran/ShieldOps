"""Tests for compliance_evidence_automator_v2 — ComplianceEvidenceAutomatorV2."""

from __future__ import annotations

from shieldops.compliance.compliance_evidence_automator_v2 import (
    CollectionStatus,
    ComplianceEvidenceAutomatorV2,
    ComplianceEvidenceReport,
    ComplianceFramework,
    EvidenceAnalysis,
    EvidenceRecord,
    EvidenceType,
)


def _engine(**kw) -> ComplianceEvidenceAutomatorV2:
    return ComplianceEvidenceAutomatorV2(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_log_export(self):
        assert EvidenceType.LOG_EXPORT == "log_export"

    def test_type_configuration_snapshot(self):
        assert EvidenceType.CONFIGURATION_SNAPSHOT == "configuration_snapshot"

    def test_type_access_review(self):
        assert EvidenceType.ACCESS_REVIEW == "access_review"

    def test_type_vulnerability_scan(self):
        assert EvidenceType.VULNERABILITY_SCAN == "vulnerability_scan"

    def test_type_policy_document(self):
        assert EvidenceType.POLICY_DOCUMENT == "policy_document"

    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_nist_csf(self):
        assert ComplianceFramework.NIST_CSF == "nist_csf"

    def test_status_collected(self):
        assert CollectionStatus.COLLECTED == "collected"

    def test_status_pending(self):
        assert CollectionStatus.PENDING == "pending"

    def test_status_failed(self):
        assert CollectionStatus.FAILED == "failed"

    def test_status_expired(self):
        assert CollectionStatus.EXPIRED == "expired"

    def test_status_validated(self):
        assert CollectionStatus.VALIDATED == "validated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_evidence_record_defaults(self):
        r = EvidenceRecord()
        assert r.id
        assert r.evidence_name == ""
        assert r.evidence_type == EvidenceType.LOG_EXPORT
        assert r.compliance_framework == ComplianceFramework.SOC2
        assert r.collection_status == CollectionStatus.COLLECTED
        assert r.completeness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_evidence_analysis_defaults(self):
        c = EvidenceAnalysis()
        assert c.id
        assert c.evidence_name == ""
        assert c.evidence_type == EvidenceType.LOG_EXPORT
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_compliance_evidence_report_defaults(self):
        r = ComplianceEvidenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.incomplete_count == 0
        assert r.avg_completeness_score == 0.0
        assert r.by_type == {}
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.top_incomplete == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_evidence
# ---------------------------------------------------------------------------


class TestRecordEvidence:
    def test_basic(self):
        eng = _engine()
        r = eng.record_evidence(
            evidence_name="audit-log-export-q1",
            evidence_type=EvidenceType.CONFIGURATION_SNAPSHOT,
            compliance_framework=ComplianceFramework.GDPR,
            collection_status=CollectionStatus.PENDING,
            completeness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.evidence_name == "audit-log-export-q1"
        assert r.evidence_type == EvidenceType.CONFIGURATION_SNAPSHOT
        assert r.compliance_framework == ComplianceFramework.GDPR
        assert r.collection_status == CollectionStatus.PENDING
        assert r.completeness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_evidence(evidence_name=f"EV-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_evidence
# ---------------------------------------------------------------------------


class TestGetEvidence:
    def test_found(self):
        eng = _engine()
        r = eng.record_evidence(
            evidence_name="audit-log-export-q1",
            collection_status=CollectionStatus.COLLECTED,
        )
        result = eng.get_evidence(r.id)
        assert result is not None
        assert result.collection_status == CollectionStatus.COLLECTED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_evidence("nonexistent") is None


# ---------------------------------------------------------------------------
# list_evidence
# ---------------------------------------------------------------------------


class TestListEvidence:
    def test_list_all(self):
        eng = _engine()
        eng.record_evidence(evidence_name="EV-001")
        eng.record_evidence(evidence_name="EV-002")
        assert len(eng.list_evidence()) == 2

    def test_filter_by_evidence_type(self):
        eng = _engine()
        eng.record_evidence(
            evidence_name="EV-001",
            evidence_type=EvidenceType.LOG_EXPORT,
        )
        eng.record_evidence(
            evidence_name="EV-002",
            evidence_type=EvidenceType.ACCESS_REVIEW,
        )
        results = eng.list_evidence(evidence_type=EvidenceType.LOG_EXPORT)
        assert len(results) == 1

    def test_filter_by_compliance_framework(self):
        eng = _engine()
        eng.record_evidence(
            evidence_name="EV-001",
            compliance_framework=ComplianceFramework.SOC2,
        )
        eng.record_evidence(
            evidence_name="EV-002",
            compliance_framework=ComplianceFramework.HIPAA,
        )
        results = eng.list_evidence(
            compliance_framework=ComplianceFramework.SOC2,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_evidence(evidence_name="EV-001", team="security")
        eng.record_evidence(evidence_name="EV-002", team="platform")
        results = eng.list_evidence(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_evidence(evidence_name=f"EV-{i}")
        assert len(eng.list_evidence(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            evidence_name="audit-log-export-q1",
            evidence_type=EvidenceType.CONFIGURATION_SNAPSHOT,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="incomplete evidence detected",
        )
        assert a.evidence_name == "audit-log-export-q1"
        assert a.evidence_type == EvidenceType.CONFIGURATION_SNAPSHOT
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(evidence_name=f"EV-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_evidence_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeEvidenceDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_evidence(
            evidence_name="EV-001",
            evidence_type=EvidenceType.LOG_EXPORT,
            completeness_score=90.0,
        )
        eng.record_evidence(
            evidence_name="EV-002",
            evidence_type=EvidenceType.LOG_EXPORT,
            completeness_score=70.0,
        )
        result = eng.analyze_evidence_distribution()
        assert "log_export" in result
        assert result["log_export"]["count"] == 2
        assert result["log_export"]["avg_completeness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_evidence_distribution() == {}


# ---------------------------------------------------------------------------
# identify_incomplete_evidence
# ---------------------------------------------------------------------------


class TestIdentifyIncompleteEvidence:
    def test_detects_below_threshold(self):
        eng = _engine(completeness_threshold=80.0)
        eng.record_evidence(evidence_name="EV-001", completeness_score=60.0)
        eng.record_evidence(evidence_name="EV-002", completeness_score=90.0)
        results = eng.identify_incomplete_evidence()
        assert len(results) == 1
        assert results[0]["evidence_name"] == "EV-001"

    def test_sorted_ascending(self):
        eng = _engine(completeness_threshold=80.0)
        eng.record_evidence(evidence_name="EV-001", completeness_score=50.0)
        eng.record_evidence(evidence_name="EV-002", completeness_score=30.0)
        results = eng.identify_incomplete_evidence()
        assert len(results) == 2
        assert results[0]["completeness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_incomplete_evidence() == []


# ---------------------------------------------------------------------------
# rank_by_completeness
# ---------------------------------------------------------------------------


class TestRankByCompleteness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_evidence(evidence_name="EV-001", service="auth-svc", completeness_score=90.0)
        eng.record_evidence(evidence_name="EV-002", service="api-gw", completeness_score=50.0)
        results = eng.rank_by_completeness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_completeness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completeness() == []


# ---------------------------------------------------------------------------
# detect_evidence_trends
# ---------------------------------------------------------------------------


class TestDetectEvidenceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(evidence_name="EV-001", analysis_score=50.0)
        result = eng.detect_evidence_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(evidence_name="EV-001", analysis_score=20.0)
        eng.add_analysis(evidence_name="EV-002", analysis_score=20.0)
        eng.add_analysis(evidence_name="EV-003", analysis_score=80.0)
        eng.add_analysis(evidence_name="EV-004", analysis_score=80.0)
        result = eng.detect_evidence_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_evidence_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(completeness_threshold=80.0)
        eng.record_evidence(
            evidence_name="audit-log-export-q1",
            evidence_type=EvidenceType.CONFIGURATION_SNAPSHOT,
            compliance_framework=ComplianceFramework.GDPR,
            collection_status=CollectionStatus.PENDING,
            completeness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ComplianceEvidenceReport)
        assert report.total_records == 1
        assert report.incomplete_count == 1
        assert len(report.top_incomplete) == 1
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
        eng.record_evidence(evidence_name="EV-001")
        eng.add_analysis(evidence_name="EV-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_evidence(
            evidence_name="EV-001",
            evidence_type=EvidenceType.LOG_EXPORT,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "log_export" in stats["type_distribution"]
