"""Tests for shieldops.compliance.evidence_automator."""

from __future__ import annotations

from shieldops.compliance.evidence_automator import (
    ComplianceEvidenceAutomator,
    ComplianceFramework,
    EvidenceAutomatorReport,
    EvidenceRecord,
    EvidenceRule,
    EvidenceSource,
    EvidenceStatus,
)


def _engine(**kw) -> ComplianceEvidenceAutomator:
    return ComplianceEvidenceAutomator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # EvidenceSource (5)
    def test_source_telemetry(self):
        assert EvidenceSource.PLATFORM_TELEMETRY == "platform_telemetry"

    def test_source_audit_logs(self):
        assert EvidenceSource.AUDIT_LOGS == "audit_logs"

    def test_source_config_snapshots(self):
        assert EvidenceSource.CONFIG_SNAPSHOTS == "config_snapshots"

    def test_source_access_records(self):
        assert EvidenceSource.ACCESS_RECORDS == "access_records"

    def test_source_scan_results(self):
        assert EvidenceSource.SCAN_RESULTS == "scan_results"

    # EvidenceStatus (5)
    def test_status_collected(self):
        assert EvidenceStatus.COLLECTED == "collected"

    def test_status_validated(self):
        assert EvidenceStatus.VALIDATED == "validated"

    def test_status_expired(self):
        assert EvidenceStatus.EXPIRED == "expired"

    def test_status_pending(self):
        assert EvidenceStatus.PENDING == "pending"

    def test_status_rejected(self):
        assert EvidenceStatus.REJECTED == "rejected"

    # ComplianceFramework (5)
    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_iso27001(self):
        assert ComplianceFramework.ISO27001 == "iso27001"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_evidence_record_defaults(self):
        r = EvidenceRecord()
        assert r.id
        assert r.control_name == ""
        assert r.source == EvidenceSource.PLATFORM_TELEMETRY
        assert r.status == EvidenceStatus.COLLECTED
        assert r.framework == ComplianceFramework.SOC2
        assert r.freshness_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_evidence_rule_defaults(self):
        r = EvidenceRule()
        assert r.id
        assert r.rule_name == ""
        assert r.source == EvidenceSource.PLATFORM_TELEMETRY
        assert r.framework == ComplianceFramework.SOC2
        assert r.collection_frequency_hours == 24
        assert r.retention_days == 365.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = EvidenceAutomatorReport()
        assert r.total_evidence == 0
        assert r.total_rules == 0
        assert r.collection_rate_pct == 0.0
        assert r.by_source == {}
        assert r.by_status == {}
        assert r.expired_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_evidence
# -------------------------------------------------------------------


class TestRecordEvidence:
    def test_basic(self):
        eng = _engine()
        r = eng.record_evidence(
            "ctrl-a",
            source=EvidenceSource.AUDIT_LOGS,
            status=EvidenceStatus.COLLECTED,
        )
        assert r.control_name == "ctrl-a"
        assert r.source == EvidenceSource.AUDIT_LOGS

    def test_with_framework(self):
        eng = _engine()
        r = eng.record_evidence(
            "ctrl-b",
            framework=ComplianceFramework.HIPAA,
        )
        assert r.framework == ComplianceFramework.HIPAA

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_evidence(f"ctrl-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_evidence
# -------------------------------------------------------------------


class TestGetEvidence:
    def test_found(self):
        eng = _engine()
        r = eng.record_evidence("ctrl-a")
        assert eng.get_evidence(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_evidence("nonexistent") is None


# -------------------------------------------------------------------
# list_evidence
# -------------------------------------------------------------------


class TestListEvidence:
    def test_list_all(self):
        eng = _engine()
        eng.record_evidence("ctrl-a")
        eng.record_evidence("ctrl-b")
        assert len(eng.list_evidence()) == 2

    def test_filter_by_control(self):
        eng = _engine()
        eng.record_evidence("ctrl-a")
        eng.record_evidence("ctrl-b")
        results = eng.list_evidence(control_name="ctrl-a")
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_evidence(
            "ctrl-a",
            source=EvidenceSource.AUDIT_LOGS,
        )
        eng.record_evidence(
            "ctrl-b",
            source=EvidenceSource.SCAN_RESULTS,
        )
        results = eng.list_evidence(
            source=EvidenceSource.AUDIT_LOGS,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            "collect-audit-logs",
            source=EvidenceSource.AUDIT_LOGS,
            framework=ComplianceFramework.SOC2,
            collection_frequency_hours=12,
            retention_days=730.0,
        )
        assert r.rule_name == "collect-audit-logs"
        assert r.collection_frequency_hours == 12

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_evidence_coverage
# -------------------------------------------------------------------


class TestAnalyzeEvidenceCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_evidence(
            "ctrl-a",
            status=EvidenceStatus.COLLECTED,
        )
        eng.record_evidence(
            "ctrl-a",
            status=EvidenceStatus.EXPIRED,
        )
        result = eng.analyze_evidence_coverage("ctrl-a")
        assert result["control_name"] == "ctrl-a"
        assert result["evidence_count"] == 2
        assert result["collection_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_evidence_coverage("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_expired_evidence
# -------------------------------------------------------------------


class TestIdentifyExpiredEvidence:
    def test_with_expired(self):
        eng = _engine()
        eng.record_evidence(
            "ctrl-a",
            status=EvidenceStatus.EXPIRED,
        )
        eng.record_evidence(
            "ctrl-a",
            status=EvidenceStatus.EXPIRED,
        )
        eng.record_evidence(
            "ctrl-b",
            status=EvidenceStatus.COLLECTED,
        )
        results = eng.identify_expired_evidence()
        assert len(results) == 1
        assert results[0]["control_name"] == "ctrl-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_expired_evidence() == []


# -------------------------------------------------------------------
# rank_by_freshness
# -------------------------------------------------------------------


class TestRankByFreshness:
    def test_with_data(self):
        eng = _engine()
        eng.record_evidence("ctrl-a", freshness_score=90.0)
        eng.record_evidence("ctrl-a", freshness_score=80.0)
        eng.record_evidence("ctrl-b", freshness_score=50.0)
        results = eng.rank_by_freshness()
        assert results[0]["control_name"] == "ctrl-a"
        assert results[0]["avg_freshness"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_freshness() == []


# -------------------------------------------------------------------
# detect_evidence_gaps
# -------------------------------------------------------------------


class TestDetectEvidenceGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_evidence(
                "ctrl-a",
                status=EvidenceStatus.EXPIRED,
            )
        eng.record_evidence(
            "ctrl-b",
            status=EvidenceStatus.COLLECTED,
        )
        results = eng.detect_evidence_gaps()
        assert len(results) == 1
        assert results[0]["control_name"] == "ctrl-a"
        assert results[0]["gap_detected"] is True

    def test_no_gaps(self):
        eng = _engine()
        eng.record_evidence(
            "ctrl-a",
            status=EvidenceStatus.EXPIRED,
        )
        assert eng.detect_evidence_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_evidence(
            "ctrl-a",
            status=EvidenceStatus.COLLECTED,
        )
        eng.record_evidence(
            "ctrl-b",
            status=EvidenceStatus.EXPIRED,
        )
        eng.record_evidence(
            "ctrl-b",
            status=EvidenceStatus.EXPIRED,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_evidence == 3
        assert report.total_rules == 1
        assert report.by_source != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_evidence == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_evidence("ctrl-a")
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
        assert stats["total_evidence"] == 0
        assert stats["total_rules"] == 0
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_evidence(
            "ctrl-a",
            source=EvidenceSource.AUDIT_LOGS,
        )
        eng.record_evidence(
            "ctrl-b",
            source=EvidenceSource.SCAN_RESULTS,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_evidence"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_controls"] == 2
