"""Tests for shieldops.security.network_segmentation_analyzer — NetworkSegmentationAnalyzer."""

from __future__ import annotations

from shieldops.security.network_segmentation_analyzer import (
    AnalysisType,
    NetworkSegmentationAnalyzer,
    NetworkSegmentationReport,
    SegmentationAnalysis,
    SegmentationRecord,
    SegmentRisk,
    SegmentScope,
)


def _engine(**kw) -> NetworkSegmentationAnalyzer:
    return NetworkSegmentationAnalyzer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert SegmentScope.VLAN == "vlan"

    def test_e1_v2(self):
        assert SegmentScope.SUBNET == "subnet"

    def test_e1_v3(self):
        assert SegmentScope.ZONE == "zone"

    def test_e1_v4(self):
        assert SegmentScope.MICROSEGMENT == "microsegment"

    def test_e1_v5(self):
        assert SegmentScope.OVERLAY == "overlay"

    def test_e2_v1(self):
        assert AnalysisType.CONNECTIVITY == "connectivity"

    def test_e2_v2(self):
        assert AnalysisType.ISOLATION == "isolation"

    def test_e2_v3(self):
        assert AnalysisType.COMPLIANCE == "compliance"

    def test_e2_v4(self):
        assert AnalysisType.DRIFT == "drift"

    def test_e2_v5(self):
        assert AnalysisType.IMPACT == "impact"

    def test_e3_v1(self):
        assert SegmentRisk.CRITICAL == "critical"

    def test_e3_v2(self):
        assert SegmentRisk.HIGH == "high"

    def test_e3_v3(self):
        assert SegmentRisk.MEDIUM == "medium"

    def test_e3_v4(self):
        assert SegmentRisk.LOW == "low"

    def test_e3_v5(self):
        assert SegmentRisk.NONE == "none"


class TestModels:
    def test_rec(self):
        r = SegmentationRecord()
        assert r.id and r.segmentation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = SegmentationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = NetworkSegmentationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_segmentation(
            segmentation_id="t",
            segment_scope=SegmentScope.SUBNET,
            analysis_type=AnalysisType.ISOLATION,
            segment_risk=SegmentRisk.HIGH,
            segmentation_score=92.0,
            service="s",
            team="t",
        )
        assert r.segmentation_id == "t" and r.segmentation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_segmentation(segmentation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_segmentation(segmentation_id="t")
        assert eng.get_segmentation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_segmentation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="a")
        eng.record_segmentation(segmentation_id="b")
        assert len(eng.list_segmentations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="a", segment_scope=SegmentScope.VLAN)
        eng.record_segmentation(segmentation_id="b", segment_scope=SegmentScope.SUBNET)
        assert len(eng.list_segmentations(segment_scope=SegmentScope.VLAN)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="a", analysis_type=AnalysisType.CONNECTIVITY)
        eng.record_segmentation(segmentation_id="b", analysis_type=AnalysisType.ISOLATION)
        assert len(eng.list_segmentations(analysis_type=AnalysisType.CONNECTIVITY)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="a", team="x")
        eng.record_segmentation(segmentation_id="b", team="y")
        assert len(eng.list_segmentations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_segmentation(segmentation_id=f"t-{i}")
        assert len(eng.list_segmentations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            segmentation_id="t",
            segment_scope=SegmentScope.SUBNET,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(segmentation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_segmentation(
            segmentation_id="a", segment_scope=SegmentScope.VLAN, segmentation_score=90.0
        )
        eng.record_segmentation(
            segmentation_id="b", segment_scope=SegmentScope.VLAN, segmentation_score=70.0
        )
        assert "vlan" in eng.analyze_segmentation_distribution()

    def test_empty(self):
        assert _engine().analyze_segmentation_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(segmentation_gap_threshold=80.0)
        eng.record_segmentation(segmentation_id="a", segmentation_score=60.0)
        eng.record_segmentation(segmentation_id="b", segmentation_score=90.0)
        assert len(eng.identify_segmentation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(segmentation_gap_threshold=80.0)
        eng.record_segmentation(segmentation_id="a", segmentation_score=50.0)
        eng.record_segmentation(segmentation_id="b", segmentation_score=30.0)
        assert len(eng.identify_segmentation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="a", service="s1", segmentation_score=80.0)
        eng.record_segmentation(segmentation_id="b", service="s2", segmentation_score=60.0)
        assert eng.rank_by_segmentation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_segmentation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(segmentation_id="t", analysis_score=float(v))
        assert eng.detect_segmentation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(segmentation_id="t", analysis_score=float(v))
        assert eng.detect_segmentation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_segmentation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="t", segmentation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="t")
        eng.add_analysis(segmentation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_segmentation(segmentation_id="a")
        eng.record_segmentation(segmentation_id="b")
        eng.add_analysis(segmentation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
