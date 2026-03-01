"""Tests for shieldops.security.vuln_prioritizer — VulnerabilityPrioritizer."""

from __future__ import annotations

from shieldops.security.vuln_prioritizer import (
    ExploitMaturity,
    RemediationStatus,
    VulnerabilityPrioritizer,
    VulnPriorityReport,
    VulnPriorityRule,
    VulnRecord,
    VulnSeverity,
)


def _engine(**kw) -> VulnerabilityPrioritizer:
    return VulnerabilityPrioritizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


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

    def test_maturity_weaponized(self):
        assert ExploitMaturity.WEAPONIZED == "weaponized"

    def test_maturity_poc_available(self):
        assert ExploitMaturity.POC_AVAILABLE == "poc_available"

    def test_maturity_theoretical(self):
        assert ExploitMaturity.THEORETICAL == "theoretical"

    def test_maturity_unproven(self):
        assert ExploitMaturity.UNPROVEN == "unproven"

    def test_maturity_not_applicable(self):
        assert ExploitMaturity.NOT_APPLICABLE == "not_applicable"

    def test_status_open(self):
        assert RemediationStatus.OPEN == "open"

    def test_status_in_progress(self):
        assert RemediationStatus.IN_PROGRESS == "in_progress"

    def test_status_patched(self):
        assert RemediationStatus.PATCHED == "patched"

    def test_status_mitigated(self):
        assert RemediationStatus.MITIGATED == "mitigated"

    def test_status_accepted(self):
        assert RemediationStatus.ACCEPTED == "accepted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_vuln_record_defaults(self):
        r = VulnRecord()
        assert r.id
        assert r.cve_id == ""
        assert r.vuln_severity == VulnSeverity.LOW
        assert r.exploit_maturity == ExploitMaturity.UNPROVEN
        assert r.remediation_status == RemediationStatus.OPEN
        assert r.cvss_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_vuln_priority_rule_defaults(self):
        ru = VulnPriorityRule()
        assert ru.id
        assert ru.cve_pattern == ""
        assert ru.vuln_severity == VulnSeverity.LOW
        assert ru.max_age_days == 0
        assert ru.auto_escalate is False
        assert ru.description == ""
        assert ru.created_at > 0

    def test_vuln_priority_report_defaults(self):
        r = VulnPriorityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.critical_count == 0
        assert r.avg_cvss_score == 0.0
        assert r.by_severity == {}
        assert r.by_maturity == {}
        assert r.by_status == {}
        assert r.urgent_vulns == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_vuln
# ---------------------------------------------------------------------------


class TestRecordVuln:
    def test_basic(self):
        eng = _engine()
        r = eng.record_vuln(
            cve_id="CVE-2024-1234",
            vuln_severity=VulnSeverity.CRITICAL,
            exploit_maturity=ExploitMaturity.WEAPONIZED,
            remediation_status=RemediationStatus.OPEN,
            cvss_score=9.8,
            team="security",
        )
        assert r.cve_id == "CVE-2024-1234"
        assert r.vuln_severity == VulnSeverity.CRITICAL
        assert r.exploit_maturity == ExploitMaturity.WEAPONIZED
        assert r.remediation_status == RemediationStatus.OPEN
        assert r.cvss_score == 9.8
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_vuln(cve_id=f"CVE-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_vuln
# ---------------------------------------------------------------------------


class TestGetVuln:
    def test_found(self):
        eng = _engine()
        r = eng.record_vuln(
            cve_id="CVE-2024-1234",
            cvss_score=7.5,
        )
        result = eng.get_vuln(r.id)
        assert result is not None
        assert result.cvss_score == 7.5

    def test_not_found(self):
        eng = _engine()
        assert eng.get_vuln("nonexistent") is None


# ---------------------------------------------------------------------------
# list_vulns
# ---------------------------------------------------------------------------


class TestListVulns:
    def test_list_all(self):
        eng = _engine()
        eng.record_vuln(cve_id="CVE-001")
        eng.record_vuln(cve_id="CVE-002")
        assert len(eng.list_vulns()) == 2

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_vuln(
            cve_id="CVE-001",
            vuln_severity=VulnSeverity.CRITICAL,
        )
        eng.record_vuln(
            cve_id="CVE-002",
            vuln_severity=VulnSeverity.LOW,
        )
        results = eng.list_vulns(severity=VulnSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_maturity(self):
        eng = _engine()
        eng.record_vuln(
            cve_id="CVE-001",
            exploit_maturity=ExploitMaturity.WEAPONIZED,
        )
        eng.record_vuln(
            cve_id="CVE-002",
            exploit_maturity=ExploitMaturity.THEORETICAL,
        )
        results = eng.list_vulns(maturity=ExploitMaturity.WEAPONIZED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_vuln(cve_id="CVE-001", team="security")
        eng.record_vuln(cve_id="CVE-002", team="platform")
        results = eng.list_vulns(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_vuln(cve_id=f"CVE-{i}")
        assert len(eng.list_vulns(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            cve_pattern="CVE-2024-*",
            vuln_severity=VulnSeverity.HIGH,
            max_age_days=30,
            auto_escalate=True,
            description="Auto-escalate recent high vulns",
        )
        assert ru.cve_pattern == "CVE-2024-*"
        assert ru.vuln_severity == VulnSeverity.HIGH
        assert ru.max_age_days == 30
        assert ru.auto_escalate is True
        assert ru.description == "Auto-escalate recent high vulns"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(cve_pattern=f"CVE-{i}-*")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_severity_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeSeverityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_vuln(
            cve_id="CVE-001",
            vuln_severity=VulnSeverity.CRITICAL,
            cvss_score=9.5,
        )
        eng.record_vuln(
            cve_id="CVE-002",
            vuln_severity=VulnSeverity.CRITICAL,
            cvss_score=9.0,
        )
        result = eng.analyze_severity_distribution()
        assert "critical" in result
        assert result["critical"]["count"] == 2
        assert result["critical"]["avg_cvss"] == 9.25

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_severity_distribution() == {}


# ---------------------------------------------------------------------------
# identify_urgent_vulns
# ---------------------------------------------------------------------------


class TestIdentifyUrgentVulns:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_vuln(
            cve_id="CVE-001",
            vuln_severity=VulnSeverity.CRITICAL,
            cvss_score=5.0,
        )
        eng.record_vuln(
            cve_id="CVE-002",
            vuln_severity=VulnSeverity.LOW,
            cvss_score=2.0,
        )
        results = eng.identify_urgent_vulns()
        assert len(results) == 1
        assert results[0]["cve_id"] == "CVE-001"

    def test_detects_high_cvss(self):
        eng = _engine(critical_cvss_threshold=9.0)
        eng.record_vuln(
            cve_id="CVE-001",
            vuln_severity=VulnSeverity.HIGH,
            cvss_score=9.5,
        )
        results = eng.identify_urgent_vulns()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_urgent_vulns() == []


# ---------------------------------------------------------------------------
# rank_by_cvss
# ---------------------------------------------------------------------------


class TestRankByCvss:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_vuln(cve_id="CVE-001", team="security", cvss_score=9.0)
        eng.record_vuln(cve_id="CVE-002", team="security", cvss_score=8.0)
        eng.record_vuln(cve_id="CVE-003", team="platform", cvss_score=3.0)
        results = eng.rank_by_cvss()
        assert len(results) == 2
        assert results[0]["team"] == "security"
        assert results[0]["avg_cvss"] == 8.5

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cvss() == []


# ---------------------------------------------------------------------------
# detect_vuln_trends
# ---------------------------------------------------------------------------


class TestDetectVulnTrends:
    def test_stable(self):
        eng = _engine()
        for days in [30, 30, 30, 30]:
            eng.add_rule(cve_pattern="CVE-*", max_age_days=days)
        result = eng.detect_vuln_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for days in [10, 10, 30, 30]:
            eng.add_rule(cve_pattern="CVE-*", max_age_days=days)
        result = eng.detect_vuln_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_vuln_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_vuln(
            cve_id="CVE-2024-9999",
            vuln_severity=VulnSeverity.CRITICAL,
            exploit_maturity=ExploitMaturity.WEAPONIZED,
            cvss_score=9.8,
            team="security",
        )
        report = eng.generate_report()
        assert isinstance(report, VulnPriorityReport)
        assert report.total_records == 1
        assert report.critical_count == 1
        assert report.avg_cvss_score == 9.8
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_vuln(cve_id="CVE-001")
        eng.add_rule(cve_pattern="CVE-*")
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
        assert stats["severity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_vuln(
            cve_id="CVE-2024-5678",
            vuln_severity=VulnSeverity.HIGH,
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_cves"] == 1
        assert "high" in stats["severity_distribution"]
