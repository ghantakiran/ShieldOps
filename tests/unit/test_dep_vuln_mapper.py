"""Tests for shieldops.topology.dep_vuln_mapper — DependencyVulnerabilityMapper."""

from __future__ import annotations

from shieldops.topology.dep_vuln_mapper import (
    DependencyType,
    DependencyVulnerabilityMapper,
    DepVulnMapperReport,
    RemediationStatus,
    VulnDependencyDetail,
    VulnMappingRecord,
    VulnSeverity,
)


def _engine(**kw) -> DependencyVulnerabilityMapper:
    return DependencyVulnerabilityMapper(**kw)


class TestEnums:
    def test_severity_critical(self):
        assert VulnSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert VulnSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert VulnSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert VulnSeverity.LOW == "low"

    def test_severity_informational(self):
        assert VulnSeverity.INFORMATIONAL == "informational"

    def test_dep_type_direct(self):
        assert DependencyType.DIRECT == "direct"

    def test_dep_type_transitive(self):
        assert DependencyType.TRANSITIVE == "transitive"

    def test_dep_type_dev_only(self):
        assert DependencyType.DEV_ONLY == "dev_only"

    def test_dep_type_optional(self):
        assert DependencyType.OPTIONAL == "optional"

    def test_dep_type_peer(self):
        assert DependencyType.PEER == "peer"

    def test_remediation_patched(self):
        assert RemediationStatus.PATCHED == "patched"

    def test_remediation_pending(self):
        assert RemediationStatus.PENDING == "pending"

    def test_remediation_no_fix(self):
        assert RemediationStatus.NO_FIX == "no_fix"

    def test_remediation_mitigated(self):
        assert RemediationStatus.MITIGATED == "mitigated"

    def test_remediation_accepted(self):
        assert RemediationStatus.ACCEPTED == "accepted"


class TestModels:
    def test_vuln_mapping_record_defaults(self):
        r = VulnMappingRecord()
        assert r.id
        assert r.dependency_name == ""
        assert r.vuln_id == ""
        assert r.severity == VulnSeverity.MEDIUM
        assert r.dependency_type == DependencyType.DIRECT
        assert r.remediation_status == RemediationStatus.PENDING
        assert r.risk_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_vuln_dependency_detail_defaults(self):
        d = VulnDependencyDetail()
        assert d.id
        assert d.dependency_name == ""
        assert d.vuln_id == ""
        assert d.affected_version == ""
        assert d.fixed_version == ""
        assert d.description == ""
        assert d.created_at > 0

    def test_report_defaults(self):
        r = DepVulnMapperReport()
        assert r.total_mappings == 0
        assert r.total_details == 0
        assert r.avg_risk_score == 0.0
        assert r.by_severity == {}
        assert r.by_remediation_status == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordMapping:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mapping("requests", vuln_id="CVE-2023-001", risk_score=75.0)
        assert r.dependency_name == "requests"
        assert r.vuln_id == "CVE-2023-001"
        assert r.risk_score == 75.0

    def test_with_severity(self):
        eng = _engine()
        r = eng.record_mapping("flask", severity=VulnSeverity.CRITICAL)
        assert r.severity == VulnSeverity.CRITICAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(f"dep-{i}")
        assert len(eng._records) == 3


class TestGetMapping:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping("requests")
        assert eng.get_mapping(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mapping("nonexistent") is None


class TestListMappings:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping("dep-a")
        eng.record_mapping("dep-b")
        assert len(eng.list_mappings()) == 2

    def test_filter_by_dependency(self):
        eng = _engine()
        eng.record_mapping("dep-a")
        eng.record_mapping("dep-b")
        results = eng.list_mappings(dependency_name="dep-a")
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_mapping("dep-a", severity=VulnSeverity.CRITICAL)
        eng.record_mapping("dep-b", severity=VulnSeverity.LOW)
        results = eng.list_mappings(severity=VulnSeverity.CRITICAL)
        assert len(results) == 1


class TestAddDependencyDetail:
    def test_basic(self):
        eng = _engine()
        d = eng.add_dependency_detail("requests", vuln_id="CVE-2023-001", affected_version="2.27.1")
        assert d.dependency_name == "requests"
        assert d.vuln_id == "CVE-2023-001"
        assert d.affected_version == "2.27.1"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_dependency_detail(f"dep-{i}")
        assert len(eng._details) == 2


class TestAnalyzeVulnBySeverity:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping("dep-a", severity=VulnSeverity.CRITICAL, risk_score=90.0)
        eng.record_mapping("dep-b", severity=VulnSeverity.CRITICAL, risk_score=80.0)
        result = eng.analyze_vuln_by_severity(VulnSeverity.CRITICAL)
        assert result["severity"] == "critical"
        assert result["total"] == 2
        assert result["avg_risk_score"] == 85.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_vuln_by_severity(VulnSeverity.CRITICAL)
        assert result["status"] == "no_data"


class TestIdentifyCriticalDependencies:
    def test_with_critical(self):
        eng = _engine()
        eng.record_mapping("dep-a", severity=VulnSeverity.CRITICAL, risk_score=95.0)
        eng.record_mapping("dep-b", severity=VulnSeverity.LOW, risk_score=10.0)
        results = eng.identify_critical_dependencies()
        assert len(results) == 1
        assert results[0]["dependency_name"] == "dep-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_dependencies() == []


class TestRankByRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping("dep-a", risk_score=30.0)
        eng.record_mapping("dep-b", risk_score=80.0)
        results = eng.rank_by_risk_score()
        assert results[0]["dependency_name"] == "dep-b"
        assert results[0]["risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


class TestDetectVulnTrends:
    def test_increasing(self):
        eng = _engine()
        for i in range(5):
            eng.record_mapping("dep-a", risk_score=float(10 + i * 10))
        results = eng.detect_vuln_trends()
        assert len(results) == 1
        assert results[0]["dependency_name"] == "dep-a"
        assert results[0]["risk_trend"] == "increasing"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_vuln_trends() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping("dep-a", severity=VulnSeverity.CRITICAL, risk_score=90.0)
        eng.record_mapping("dep-b", severity=VulnSeverity.LOW, risk_score=10.0)
        eng.add_dependency_detail("dep-a", vuln_id="CVE-2023-001")
        report = eng.generate_report()
        assert report.total_mappings == 2
        assert report.total_details == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_mappings == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_mapping("dep-a")
        eng.add_dependency_detail("dep-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._details) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_mappings"] == 0
        assert stats["total_details"] == 0
        assert stats["severity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_mapping("dep-a", severity=VulnSeverity.CRITICAL)
        eng.record_mapping("dep-b", severity=VulnSeverity.LOW)
        eng.add_dependency_detail("dep-a")
        stats = eng.get_stats()
        assert stats["total_mappings"] == 2
        assert stats["total_details"] == 1
        assert stats["unique_dependencies"] == 2
