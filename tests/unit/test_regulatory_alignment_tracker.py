"""Tests for shieldops.compliance.regulatory_alignment_tracker — RegulatoryAlignmentTracker."""

from __future__ import annotations

from shieldops.compliance.regulatory_alignment_tracker import (
    AlignmentAnalysis,
    AlignmentRecord,
    AlignmentStatus,
    ComplianceRisk,
    Regulation,
    RegulatoryAlignmentReport,
    RegulatoryAlignmentTracker,
)


def _engine(**kw) -> RegulatoryAlignmentTracker:
    return RegulatoryAlignmentTracker(**kw)


class TestEnums:
    def test_regulation_gdpr(self):
        assert Regulation.GDPR == "gdpr"

    def test_regulation_ccpa(self):
        assert Regulation.CCPA == "ccpa"

    def test_regulation_sox(self):
        assert Regulation.SOX == "sox"

    def test_regulation_hipaa(self):
        assert Regulation.HIPAA == "hipaa"

    def test_regulation_pci_dss(self):
        assert Regulation.PCI_DSS == "pci_dss"

    def test_status_aligned(self):
        assert AlignmentStatus.ALIGNED == "aligned"

    def test_status_partially_aligned(self):
        assert AlignmentStatus.PARTIALLY_ALIGNED == "partially_aligned"

    def test_status_non_aligned(self):
        assert AlignmentStatus.NON_ALIGNED == "non_aligned"

    def test_status_in_progress(self):
        assert AlignmentStatus.IN_PROGRESS == "in_progress"

    def test_status_not_applicable(self):
        assert AlignmentStatus.NOT_APPLICABLE == "not_applicable"

    def test_risk_critical(self):
        assert ComplianceRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert ComplianceRisk.HIGH == "high"

    def test_risk_medium(self):
        assert ComplianceRisk.MEDIUM == "medium"

    def test_risk_low(self):
        assert ComplianceRisk.LOW == "low"

    def test_risk_minimal(self):
        assert ComplianceRisk.MINIMAL == "minimal"


class TestModels:
    def test_record_defaults(self):
        r = AlignmentRecord()
        assert r.id
        assert r.requirement_name == ""
        assert r.regulation == Regulation.GDPR
        assert r.alignment_status == AlignmentStatus.ALIGNED
        assert r.compliance_risk == ComplianceRisk.CRITICAL
        assert r.alignment_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AlignmentAnalysis()
        assert a.id
        assert a.requirement_name == ""
        assert a.regulation == Regulation.GDPR
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = RegulatoryAlignmentReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_alignment_score == 0.0
        assert r.by_regulation == {}
        assert r.by_status == {}
        assert r.by_risk == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_alignment(
            requirement_name="gdpr-data-processing",
            regulation=Regulation.GDPR,
            alignment_status=AlignmentStatus.ALIGNED,
            compliance_risk=ComplianceRisk.LOW,
            alignment_score=85.0,
            service="compliance-svc",
            team="legal",
        )
        assert r.requirement_name == "gdpr-data-processing"
        assert r.regulation == Regulation.GDPR
        assert r.alignment_score == 85.0
        assert r.service == "compliance-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_alignment(requirement_name=f"align-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_alignment(requirement_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_alignment(requirement_name="a")
        eng.record_alignment(requirement_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_regulation(self):
        eng = _engine()
        eng.record_alignment(requirement_name="a", regulation=Regulation.GDPR)
        eng.record_alignment(requirement_name="b", regulation=Regulation.HIPAA)
        assert len(eng.list_records(regulation=Regulation.GDPR)) == 1

    def test_filter_by_alignment_status(self):
        eng = _engine()
        eng.record_alignment(requirement_name="a", alignment_status=AlignmentStatus.ALIGNED)
        eng.record_alignment(requirement_name="b", alignment_status=AlignmentStatus.NON_ALIGNED)
        assert len(eng.list_records(alignment_status=AlignmentStatus.ALIGNED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_alignment(requirement_name="a", team="sec")
        eng.record_alignment(requirement_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_alignment(requirement_name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            requirement_name="test",
            analysis_score=88.5,
            breached=True,
            description="alignment gap",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(requirement_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_alignment(requirement_name="a", regulation=Regulation.GDPR, alignment_score=90.0)
        eng.record_alignment(requirement_name="b", regulation=Regulation.GDPR, alignment_score=70.0)
        result = eng.analyze_distribution()
        assert "gdpr" in result
        assert result["gdpr"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_alignment(requirement_name="a", alignment_score=60.0)
        eng.record_alignment(requirement_name="b", alignment_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_alignment(requirement_name="a", alignment_score=50.0)
        eng.record_alignment(requirement_name="b", alignment_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["alignment_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_alignment(requirement_name="a", service="auth", alignment_score=90.0)
        eng.record_alignment(requirement_name="b", service="api", alignment_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(requirement_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(requirement_name="a", analysis_score=20.0)
        eng.add_analysis(requirement_name="b", analysis_score=20.0)
        eng.add_analysis(requirement_name="c", analysis_score=80.0)
        eng.add_analysis(requirement_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_alignment(requirement_name="test", alignment_score=50.0)
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
        eng.record_alignment(requirement_name="test")
        eng.add_analysis(requirement_name="test")
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
        eng.record_alignment(requirement_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
