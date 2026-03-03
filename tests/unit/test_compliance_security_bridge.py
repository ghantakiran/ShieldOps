"""Tests for shieldops.compliance.compliance_security_bridge — ComplianceSecurityBridge."""

from __future__ import annotations

from shieldops.compliance.compliance_security_bridge import (
    BridgeAnalysis,
    BridgeRecord,
    BridgeSource,
    BridgeStatus,
    ComplianceSecurityBridge,
    ComplianceSecurityReport,
    ControlFramework,
)


def _engine(**kw) -> ComplianceSecurityBridge:
    return ComplianceSecurityBridge(**kw)


class TestEnums:
    def test_control_framework_nist_csf(self):
        assert ControlFramework.NIST_CSF == "nist_csf"

    def test_control_framework_soc2(self):
        assert ControlFramework.SOC2 == "soc2"

    def test_control_framework_iso27001(self):
        assert ControlFramework.ISO27001 == "iso27001"

    def test_control_framework_pci_dss(self):
        assert ControlFramework.PCI_DSS == "pci_dss"

    def test_control_framework_hipaa(self):
        assert ControlFramework.HIPAA == "hipaa"

    def test_bridge_source_detection_rules(self):
        assert BridgeSource.DETECTION_RULES == "detection_rules"

    def test_bridge_source_security_controls(self):
        assert BridgeSource.SECURITY_CONTROLS == "security_controls"

    def test_bridge_source_audit_evidence(self):
        assert BridgeSource.AUDIT_EVIDENCE == "audit_evidence"

    def test_bridge_source_policy(self):
        assert BridgeSource.POLICY == "policy"

    def test_bridge_source_manual(self):
        assert BridgeSource.MANUAL == "manual"

    def test_bridge_status_mapped(self):
        assert BridgeStatus.MAPPED == "mapped"

    def test_bridge_status_partial(self):
        assert BridgeStatus.PARTIAL == "partial"

    def test_bridge_status_unmapped(self):
        assert BridgeStatus.UNMAPPED == "unmapped"

    def test_bridge_status_obsolete(self):
        assert BridgeStatus.OBSOLETE == "obsolete"

    def test_bridge_status_review_needed(self):
        assert BridgeStatus.REVIEW_NEEDED == "review_needed"


class TestModels:
    def test_record_defaults(self):
        r = BridgeRecord()
        assert r.id
        assert r.name == ""
        assert r.control_framework == ControlFramework.NIST_CSF
        assert r.bridge_source == BridgeSource.DETECTION_RULES
        assert r.bridge_status == BridgeStatus.REVIEW_NEEDED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = BridgeAnalysis()
        assert a.id
        assert a.name == ""
        assert a.control_framework == ControlFramework.NIST_CSF
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ComplianceSecurityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_control_framework == {}
        assert r.by_bridge_source == {}
        assert r.by_bridge_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            control_framework=ControlFramework.NIST_CSF,
            bridge_source=BridgeSource.SECURITY_CONTROLS,
            bridge_status=BridgeStatus.MAPPED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.control_framework == ControlFramework.NIST_CSF
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_control_framework(self):
        eng = _engine()
        eng.record_entry(name="a", control_framework=ControlFramework.NIST_CSF)
        eng.record_entry(name="b", control_framework=ControlFramework.SOC2)
        assert len(eng.list_records(control_framework=ControlFramework.NIST_CSF)) == 1

    def test_filter_by_bridge_source(self):
        eng = _engine()
        eng.record_entry(name="a", bridge_source=BridgeSource.DETECTION_RULES)
        eng.record_entry(name="b", bridge_source=BridgeSource.SECURITY_CONTROLS)
        assert len(eng.list_records(bridge_source=BridgeSource.DETECTION_RULES)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", control_framework=ControlFramework.SOC2, score=90.0)
        eng.record_entry(name="b", control_framework=ControlFramework.SOC2, score=70.0)
        result = eng.analyze_distribution()
        assert "soc2" in result
        assert result["soc2"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
