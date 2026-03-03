"""Tests for shieldops.security.detection_gap_prioritizer — DetectionGapPrioritizer."""

from __future__ import annotations

from shieldops.security.detection_gap_prioritizer import (
    DetectionGapAnalysis,
    DetectionGapPrioritizer,
    DetectionGapRecord,
    DetectionGapReport,
    GapCategory,
    GapSeverity,
    PrioritizationFactor,
)


def _engine(**kw) -> DetectionGapPrioritizer:
    return DetectionGapPrioritizer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert GapCategory.TECHNIQUE_COVERAGE == "technique_coverage"

    def test_e1_v2(self):
        assert GapCategory.DATA_SOURCE == "data_source"

    def test_e1_v3(self):
        assert GapCategory.PLATFORM == "platform"

    def test_e1_v4(self):
        assert GapCategory.ENVIRONMENT == "environment"

    def test_e1_v5(self):
        assert GapCategory.THREAT_ACTOR == "threat_actor"

    def test_e2_v1(self):
        assert PrioritizationFactor.LIKELIHOOD == "likelihood"

    def test_e2_v2(self):
        assert PrioritizationFactor.IMPACT == "impact"

    def test_e2_v3(self):
        assert PrioritizationFactor.EXPLOITABILITY == "exploitability"

    def test_e2_v4(self):
        assert PrioritizationFactor.ASSET_VALUE == "asset_value"

    def test_e2_v5(self):
        assert PrioritizationFactor.THREAT_INTEL == "threat_intel"

    def test_e3_v1(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_e3_v2(self):
        assert GapSeverity.HIGH == "high"

    def test_e3_v3(self):
        assert GapSeverity.MEDIUM == "medium"

    def test_e3_v4(self):
        assert GapSeverity.LOW == "low"

    def test_e3_v5(self):
        assert GapSeverity.ACCEPTABLE == "acceptable"


class TestModels:
    def test_rec(self):
        r = DetectionGapRecord()
        assert r.id and r.gap_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = DetectionGapAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = DetectionGapReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_gap(
            gap_id="t",
            gap_category=GapCategory.DATA_SOURCE,
            prioritization_factor=PrioritizationFactor.IMPACT,
            gap_severity=GapSeverity.HIGH,
            gap_score=92.0,
            service="s",
            team="t",
        )
        assert r.gap_id == "t" and r.gap_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(gap_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_gap(gap_id="t")
        assert eng.get_gap(r.id) is not None

    def test_not_found(self):
        assert _engine().get_gap("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_gap(gap_id="a")
        eng.record_gap(gap_id="b")
        assert len(eng.list_gaps()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_gap(gap_id="a", gap_category=GapCategory.TECHNIQUE_COVERAGE)
        eng.record_gap(gap_id="b", gap_category=GapCategory.DATA_SOURCE)
        assert len(eng.list_gaps(gap_category=GapCategory.TECHNIQUE_COVERAGE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_gap(gap_id="a", prioritization_factor=PrioritizationFactor.LIKELIHOOD)
        eng.record_gap(gap_id="b", prioritization_factor=PrioritizationFactor.IMPACT)
        assert len(eng.list_gaps(prioritization_factor=PrioritizationFactor.LIKELIHOOD)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_gap(gap_id="a", team="x")
        eng.record_gap(gap_id="b", team="y")
        assert len(eng.list_gaps(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_gap(gap_id=f"t-{i}")
        assert len(eng.list_gaps(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            gap_id="t", gap_category=GapCategory.DATA_SOURCE, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(gap_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_gap(gap_id="a", gap_category=GapCategory.TECHNIQUE_COVERAGE, gap_score=90.0)
        eng.record_gap(gap_id="b", gap_category=GapCategory.TECHNIQUE_COVERAGE, gap_score=70.0)
        assert "technique_coverage" in eng.analyze_category_distribution()

    def test_empty(self):
        assert _engine().analyze_category_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(gap_threshold=80.0)
        eng.record_gap(gap_id="a", gap_score=60.0)
        eng.record_gap(gap_id="b", gap_score=90.0)
        assert len(eng.identify_gap_gaps()) == 1

    def test_sorted(self):
        eng = _engine(gap_threshold=80.0)
        eng.record_gap(gap_id="a", gap_score=50.0)
        eng.record_gap(gap_id="b", gap_score=30.0)
        assert len(eng.identify_gap_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_gap(gap_id="a", service="s1", gap_score=80.0)
        eng.record_gap(gap_id="b", service="s2", gap_score=60.0)
        assert eng.rank_by_gap()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_gap() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(gap_id="t", analysis_score=float(v))
        assert eng.detect_gap_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(gap_id="t", analysis_score=float(v))
        assert eng.detect_gap_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_gap_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_gap(gap_id="t", gap_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_gap(gap_id="t")
        eng.add_analysis(gap_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_gap(gap_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_gap(gap_id="a")
        eng.record_gap(gap_id="b")
        eng.add_analysis(gap_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
