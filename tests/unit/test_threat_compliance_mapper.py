"""Tests for shieldops.compliance.threat_compliance_mapper — ThreatComplianceMapper."""

from __future__ import annotations

from shieldops.compliance.threat_compliance_mapper import (
    ComplianceFramework,
    ControlEffectiveness,
    MappingStatus,
    ThreatComplianceMapper,
    ThreatComplianceMapperAnalysis,
    ThreatComplianceMapperRecord,
    ThreatComplianceMapperReport,
)


def _engine(**kw) -> ThreatComplianceMapper:
    return ThreatComplianceMapper(**kw)


class TestEnums:
    def test_compliance_framework_first(self):
        assert ComplianceFramework.NIST_CSF == "nist_csf"

    def test_compliance_framework_second(self):
        assert ComplianceFramework.ISO_27001 == "iso_27001"

    def test_compliance_framework_third(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_compliance_framework_fourth(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_compliance_framework_fifth(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_mapping_status_first(self):
        assert MappingStatus.MAPPED == "mapped"

    def test_mapping_status_second(self):
        assert MappingStatus.PARTIAL == "partial"

    def test_mapping_status_third(self):
        assert MappingStatus.UNMAPPED == "unmapped"

    def test_mapping_status_fourth(self):
        assert MappingStatus.IN_REVIEW == "in_review"

    def test_mapping_status_fifth(self):
        assert MappingStatus.DEPRECATED == "deprecated"

    def test_control_effectiveness_first(self):
        assert ControlEffectiveness.EFFECTIVE == "effective"

    def test_control_effectiveness_second(self):
        assert ControlEffectiveness.PARTIALLY_EFFECTIVE == "partially_effective"

    def test_control_effectiveness_third(self):
        assert ControlEffectiveness.INEFFECTIVE == "ineffective"

    def test_control_effectiveness_fourth(self):
        assert ControlEffectiveness.NOT_IMPLEMENTED == "not_implemented"

    def test_control_effectiveness_fifth(self):
        assert ControlEffectiveness.NOT_APPLICABLE == "not_applicable"


class TestModels:
    def test_record_defaults(self):
        r = ThreatComplianceMapperRecord()
        assert r.id
        assert r.name == ""
        assert r.compliance_framework == ComplianceFramework.NIST_CSF
        assert r.mapping_status == MappingStatus.MAPPED
        assert r.control_effectiveness == ControlEffectiveness.EFFECTIVE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ThreatComplianceMapperAnalysis()
        assert a.id
        assert a.name == ""
        assert a.compliance_framework == ComplianceFramework.NIST_CSF
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ThreatComplianceMapperReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_compliance_framework == {}
        assert r.by_mapping_status == {}
        assert r.by_control_effectiveness == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            compliance_framework=ComplianceFramework.NIST_CSF,
            mapping_status=MappingStatus.PARTIAL,
            control_effectiveness=ControlEffectiveness.INEFFECTIVE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.compliance_framework == ComplianceFramework.NIST_CSF
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_compliance_framework(self):
        eng = _engine()
        eng.record_item(name="a", compliance_framework=ComplianceFramework.ISO_27001)
        eng.record_item(name="b", compliance_framework=ComplianceFramework.NIST_CSF)
        assert len(eng.list_records(compliance_framework=ComplianceFramework.ISO_27001)) == 1

    def test_filter_by_mapping_status(self):
        eng = _engine()
        eng.record_item(name="a", mapping_status=MappingStatus.MAPPED)
        eng.record_item(name="b", mapping_status=MappingStatus.PARTIAL)
        assert len(eng.list_records(mapping_status=MappingStatus.MAPPED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
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
        eng.record_item(name="a", compliance_framework=ComplianceFramework.ISO_27001, score=90.0)
        eng.record_item(name="b", compliance_framework=ComplianceFramework.ISO_27001, score=70.0)
        result = eng.analyze_distribution()
        assert "iso_27001" in result
        assert result["iso_27001"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
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
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
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
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
