"""Tests for shieldops.compliance.governance_framework_mapper — GovernanceFrameworkMapper."""

from __future__ import annotations

from shieldops.compliance.governance_framework_mapper import (
    ControlMaturity,
    Framework,
    FrameworkAnalysis,
    FrameworkMappingReport,
    FrameworkRecord,
    GovernanceFrameworkMapper,
    MappingStatus,
)


def _engine(**kw) -> GovernanceFrameworkMapper:
    return GovernanceFrameworkMapper(**kw)


class TestEnums:
    def test_framework_nist_csf(self):
        assert Framework.NIST_CSF == "nist_csf"

    def test_framework_iso_27001(self):
        assert Framework.ISO_27001 == "iso_27001"

    def test_framework_soc2(self):
        assert Framework.SOC2 == "soc2"

    def test_framework_hipaa(self):
        assert Framework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert Framework.PCI_DSS == "pci_dss"

    def test_status_mapped(self):
        assert MappingStatus.MAPPED == "mapped"

    def test_status_partial(self):
        assert MappingStatus.PARTIAL == "partial"

    def test_status_unmapped(self):
        assert MappingStatus.UNMAPPED == "unmapped"

    def test_status_not_applicable(self):
        assert MappingStatus.NOT_APPLICABLE == "not_applicable"

    def test_status_in_progress(self):
        assert MappingStatus.IN_PROGRESS == "in_progress"

    def test_maturity_initial(self):
        assert ControlMaturity.INITIAL == "initial"

    def test_maturity_repeatable(self):
        assert ControlMaturity.REPEATABLE == "repeatable"

    def test_maturity_defined(self):
        assert ControlMaturity.DEFINED == "defined"

    def test_maturity_managed(self):
        assert ControlMaturity.MANAGED == "managed"

    def test_maturity_optimized(self):
        assert ControlMaturity.OPTIMIZED == "optimized"


class TestModels:
    def test_record_defaults(self):
        r = FrameworkRecord()
        assert r.id
        assert r.control_name == ""
        assert r.framework == Framework.NIST_CSF
        assert r.mapping_status == MappingStatus.MAPPED
        assert r.control_maturity == ControlMaturity.OPTIMIZED
        assert r.mapping_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = FrameworkAnalysis()
        assert a.id
        assert a.control_name == ""
        assert a.framework == Framework.NIST_CSF
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = FrameworkMappingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_mapping_score == 0.0
        assert r.by_framework == {}
        assert r.by_status == {}
        assert r.by_maturity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mapping(
            control_name="nist-csf-mapping",
            framework=Framework.NIST_CSF,
            mapping_status=MappingStatus.MAPPED,
            control_maturity=ControlMaturity.MANAGED,
            mapping_score=85.0,
            service="grc-svc",
            team="governance",
        )
        assert r.control_name == "nist-csf-mapping"
        assert r.framework == Framework.NIST_CSF
        assert r.mapping_score == 85.0
        assert r.service == "grc-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(control_name=f"fw-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping(control_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping(control_name="a")
        eng.record_mapping(control_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_mapping(control_name="a", framework=Framework.NIST_CSF)
        eng.record_mapping(control_name="b", framework=Framework.SOC2)
        assert len(eng.list_records(framework=Framework.NIST_CSF)) == 1

    def test_filter_by_mapping_status(self):
        eng = _engine()
        eng.record_mapping(control_name="a", mapping_status=MappingStatus.UNMAPPED)
        eng.record_mapping(control_name="b", mapping_status=MappingStatus.MAPPED)
        assert len(eng.list_records(mapping_status=MappingStatus.UNMAPPED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mapping(control_name="a", team="sec")
        eng.record_mapping(control_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mapping(control_name=f"f-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            control_name="test",
            analysis_score=88.5,
            breached=True,
            description="mapping gap",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(control_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(control_name="a", framework=Framework.NIST_CSF, mapping_score=90.0)
        eng.record_mapping(control_name="b", framework=Framework.NIST_CSF, mapping_score=70.0)
        result = eng.analyze_distribution()
        assert "nist_csf" in result
        assert result["nist_csf"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_mapping(control_name="a", mapping_score=60.0)
        eng.record_mapping(control_name="b", mapping_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_mapping(control_name="a", mapping_score=50.0)
        eng.record_mapping(control_name="b", mapping_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["mapping_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_mapping(control_name="a", service="auth", mapping_score=90.0)
        eng.record_mapping(control_name="b", service="api", mapping_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(control_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(control_name="a", analysis_score=20.0)
        eng.add_analysis(control_name="b", analysis_score=20.0)
        eng.add_analysis(control_name="c", analysis_score=80.0)
        eng.add_analysis(control_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_mapping(control_name="test", mapping_score=50.0)
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
        eng.record_mapping(control_name="test")
        eng.add_analysis(control_name="test")
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
        eng.record_mapping(control_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
