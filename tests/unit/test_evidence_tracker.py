"""Tests for shieldops.audit.evidence_tracker — AuditEvidenceTracker."""

from __future__ import annotations

from shieldops.audit.evidence_tracker import (
    AuditEvidenceTracker,
    AuditFramework,
    EvidenceRecord,
    EvidenceRule,
    EvidenceStatus,
    EvidenceTrackerReport,
    EvidenceType,
)


def _engine(**kw) -> AuditEvidenceTracker:
    return AuditEvidenceTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_evidence_type_screenshot(self):
        assert EvidenceType.SCREENSHOT == "screenshot"

    def test_evidence_type_log_export(self):
        assert EvidenceType.LOG_EXPORT == "log_export"

    def test_evidence_type_config_snapshot(self):
        assert EvidenceType.CONFIG_SNAPSHOT == "config_snapshot"

    def test_evidence_type_approval_record(self):
        assert EvidenceType.APPROVAL_RECORD == "approval_record"

    def test_evidence_type_test_result(self):
        assert EvidenceType.TEST_RESULT == "test_result"

    def test_evidence_status_collected(self):
        assert EvidenceStatus.COLLECTED == "collected"

    def test_evidence_status_verified(self):
        assert EvidenceStatus.VERIFIED == "verified"

    def test_evidence_status_expired(self):
        assert EvidenceStatus.EXPIRED == "expired"

    def test_evidence_status_missing(self):
        assert EvidenceStatus.MISSING == "missing"

    def test_evidence_status_disputed(self):
        assert EvidenceStatus.DISPUTED == "disputed"

    def test_audit_framework_soc2(self):
        assert AuditFramework.SOC2 == "soc2"

    def test_audit_framework_hipaa(self):
        assert AuditFramework.HIPAA == "hipaa"

    def test_audit_framework_pci_dss(self):
        assert AuditFramework.PCI_DSS == "pci_dss"

    def test_audit_framework_iso_27001(self):
        assert AuditFramework.ISO_27001 == "iso_27001"

    def test_audit_framework_gdpr(self):
        assert AuditFramework.GDPR == "gdpr"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_evidence_record_defaults(self):
        r = EvidenceRecord()
        assert r.id
        assert r.control_id == ""
        assert r.evidence_type == EvidenceType.SCREENSHOT
        assert r.evidence_status == EvidenceStatus.MISSING
        assert r.audit_framework == AuditFramework.SOC2
        assert r.completeness_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_evidence_rule_defaults(self):
        p = EvidenceRule()
        assert p.id
        assert p.framework_pattern == ""
        assert p.audit_framework == AuditFramework.SOC2
        assert p.required_count == 0
        assert p.max_age_days == 365
        assert p.description == ""
        assert p.created_at > 0

    def test_evidence_tracker_report_defaults(self):
        r = EvidenceTrackerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.verified_count == 0
        assert r.avg_completeness == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_framework == {}
        assert r.missing_evidence == []
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
            control_id="CTRL-001",
            evidence_type=EvidenceType.LOG_EXPORT,
            evidence_status=EvidenceStatus.VERIFIED,
            audit_framework=AuditFramework.HIPAA,
            completeness_pct=95.0,
            team="compliance",
        )
        assert r.control_id == "CTRL-001"
        assert r.evidence_type == EvidenceType.LOG_EXPORT
        assert r.evidence_status == EvidenceStatus.VERIFIED
        assert r.audit_framework == AuditFramework.HIPAA
        assert r.completeness_pct == 95.0
        assert r.team == "compliance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_evidence(control_id=f"CTRL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_evidence
# ---------------------------------------------------------------------------


class TestGetEvidence:
    def test_found(self):
        eng = _engine()
        r = eng.record_evidence(
            control_id="CTRL-001",
            evidence_status=EvidenceStatus.COLLECTED,
        )
        result = eng.get_evidence(r.id)
        assert result is not None
        assert result.evidence_status == EvidenceStatus.COLLECTED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_evidence("nonexistent") is None


# ---------------------------------------------------------------------------
# list_evidence
# ---------------------------------------------------------------------------


class TestListEvidence:
    def test_list_all(self):
        eng = _engine()
        eng.record_evidence(control_id="CTRL-001")
        eng.record_evidence(control_id="CTRL-002")
        assert len(eng.list_evidence()) == 2

    def test_filter_by_evidence_type(self):
        eng = _engine()
        eng.record_evidence(
            control_id="CTRL-001",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        eng.record_evidence(
            control_id="CTRL-002",
            evidence_type=EvidenceType.TEST_RESULT,
        )
        results = eng.list_evidence(evidence_type=EvidenceType.SCREENSHOT)
        assert len(results) == 1

    def test_filter_by_evidence_status(self):
        eng = _engine()
        eng.record_evidence(
            control_id="CTRL-001",
            evidence_status=EvidenceStatus.VERIFIED,
        )
        eng.record_evidence(
            control_id="CTRL-002",
            evidence_status=EvidenceStatus.MISSING,
        )
        results = eng.list_evidence(evidence_status=EvidenceStatus.VERIFIED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_evidence(control_id="CTRL-001", team="compliance")
        eng.record_evidence(control_id="CTRL-002", team="security")
        results = eng.list_evidence(team="compliance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_evidence(control_id=f"CTRL-{i}")
        assert len(eng.list_evidence(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            framework_pattern="soc2-*",
            audit_framework=AuditFramework.PCI_DSS,
            required_count=5,
            max_age_days=180,
            description="PCI DSS evidence rule",
        )
        assert p.framework_pattern == "soc2-*"
        assert p.audit_framework == AuditFramework.PCI_DSS
        assert p.required_count == 5
        assert p.max_age_days == 180

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(framework_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_evidence_coverage
# ---------------------------------------------------------------------------


class TestAnalyzeEvidenceCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_evidence(
            control_id="CTRL-001",
            evidence_type=EvidenceType.SCREENSHOT,
            completeness_pct=80.0,
        )
        eng.record_evidence(
            control_id="CTRL-002",
            evidence_type=EvidenceType.SCREENSHOT,
            completeness_pct=60.0,
        )
        result = eng.analyze_evidence_coverage()
        assert "screenshot" in result
        assert result["screenshot"]["count"] == 2
        assert result["screenshot"]["avg_completeness"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_evidence_coverage() == {}


# ---------------------------------------------------------------------------
# identify_missing_evidence
# ---------------------------------------------------------------------------


class TestIdentifyMissingEvidence:
    def test_detects_missing_and_expired(self):
        eng = _engine()
        eng.record_evidence(
            control_id="CTRL-001",
            evidence_status=EvidenceStatus.MISSING,
        )
        eng.record_evidence(
            control_id="CTRL-002",
            evidence_status=EvidenceStatus.VERIFIED,
        )
        eng.record_evidence(
            control_id="CTRL-003",
            evidence_status=EvidenceStatus.EXPIRED,
        )
        results = eng.identify_missing_evidence()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_missing_evidence() == []


# ---------------------------------------------------------------------------
# rank_by_completeness
# ---------------------------------------------------------------------------


class TestRankByCompleteness:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_evidence(
            control_id="CTRL-001",
            team="compliance",
            completeness_pct=95.0,
        )
        eng.record_evidence(
            control_id="CTRL-002",
            team="security",
            completeness_pct=40.0,
        )
        results = eng.rank_by_completeness()
        assert len(results) == 2
        assert results[0]["team"] == "security"
        assert results[0]["avg_completeness"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completeness() == []


# ---------------------------------------------------------------------------
# detect_evidence_trends
# ---------------------------------------------------------------------------


class TestDetectEvidenceTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_evidence(control_id="CTRL", completeness_pct=pct)
        result = eng.detect_evidence_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [40.0, 40.0, 60.0, 60.0]:
            eng.record_evidence(control_id="CTRL", completeness_pct=pct)
        result = eng.detect_evidence_trends()
        assert result["trend"] == "increasing"
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
        eng = _engine(min_completeness_pct=90.0)
        eng.record_evidence(
            control_id="CTRL-001",
            evidence_type=EvidenceType.LOG_EXPORT,
            evidence_status=EvidenceStatus.MISSING,
            completeness_pct=50.0,
            team="compliance",
        )
        report = eng.generate_report()
        assert isinstance(report, EvidenceTrackerReport)
        assert report.total_records == 1
        assert report.verified_count == 0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "on track" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_evidence(control_id="CTRL-001")
        eng.add_rule(framework_pattern="p1")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_evidence(
            control_id="CTRL-001",
            evidence_type=EvidenceType.CONFIG_SNAPSHOT,
            team="compliance",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_controls"] == 1
        assert "config_snapshot" in stats["type_distribution"]
