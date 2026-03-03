"""Tests for shieldops.analytics.alert_quality_scorer — AlertQualityScorer."""

from __future__ import annotations

from shieldops.analytics.alert_quality_scorer import (
    AlertQualityAnalysis,
    AlertQualityRecord,
    AlertQualityReport,
    AlertQualityScorer,
    AlertSource,
    QualityDimension,
    QualityGrade,
)


def _engine(**kw) -> AlertQualityScorer:
    return AlertQualityScorer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert QualityDimension.ACCURACY == "accuracy"

    def test_e1_v2(self):
        assert QualityDimension.ACTIONABILITY == "actionability"

    def test_e1_v3(self):
        assert QualityDimension.TIMELINESS == "timeliness"

    def test_e1_v4(self):
        assert QualityDimension.CONTEXT == "context"

    def test_e1_v5(self):
        assert QualityDimension.DEDUPLICATION == "deduplication"

    def test_e2_v1(self):
        assert AlertSource.SIEM == "siem"

    def test_e2_v2(self):
        assert AlertSource.IDS == "ids"

    def test_e2_v3(self):
        assert AlertSource.EDR == "edr"

    def test_e2_v4(self):
        assert AlertSource.CUSTOM == "custom"

    def test_e2_v5(self):
        assert AlertSource.THIRD_PARTY == "third_party"

    def test_e3_v1(self):
        assert QualityGrade.EXCELLENT == "excellent"

    def test_e3_v2(self):
        assert QualityGrade.GOOD == "good"

    def test_e3_v3(self):
        assert QualityGrade.FAIR == "fair"

    def test_e3_v4(self):
        assert QualityGrade.POOR == "poor"

    def test_e3_v5(self):
        assert QualityGrade.CRITICAL == "critical"


class TestModels:
    def test_rec(self):
        r = AlertQualityRecord()
        assert r.id and r.quality_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = AlertQualityAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = AlertQualityReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_quality(
            quality_id="t",
            quality_dimension=QualityDimension.ACTIONABILITY,
            alert_source=AlertSource.IDS,
            quality_grade=QualityGrade.GOOD,
            quality_score=92.0,
            service="s",
            team="t",
        )
        assert r.quality_id == "t" and r.quality_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_quality(quality_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_quality(quality_id="t")
        assert eng.get_quality(r.id) is not None

    def test_not_found(self):
        assert _engine().get_quality("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_quality(quality_id="a")
        eng.record_quality(quality_id="b")
        assert len(eng.list_qualities()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_quality(quality_id="a", quality_dimension=QualityDimension.ACCURACY)
        eng.record_quality(quality_id="b", quality_dimension=QualityDimension.ACTIONABILITY)
        assert len(eng.list_qualities(quality_dimension=QualityDimension.ACCURACY)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_quality(quality_id="a", alert_source=AlertSource.SIEM)
        eng.record_quality(quality_id="b", alert_source=AlertSource.IDS)
        assert len(eng.list_qualities(alert_source=AlertSource.SIEM)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_quality(quality_id="a", team="x")
        eng.record_quality(quality_id="b", team="y")
        assert len(eng.list_qualities(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_quality(quality_id=f"t-{i}")
        assert len(eng.list_qualities(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            quality_id="t",
            quality_dimension=QualityDimension.ACTIONABILITY,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(quality_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_quality(
            quality_id="a", quality_dimension=QualityDimension.ACCURACY, quality_score=90.0
        )
        eng.record_quality(
            quality_id="b", quality_dimension=QualityDimension.ACCURACY, quality_score=70.0
        )
        assert "accuracy" in eng.analyze_dimension_distribution()

    def test_empty(self):
        assert _engine().analyze_dimension_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_quality(quality_id="a", quality_score=60.0)
        eng.record_quality(quality_id="b", quality_score=90.0)
        assert len(eng.identify_quality_gaps()) == 1

    def test_sorted(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_quality(quality_id="a", quality_score=50.0)
        eng.record_quality(quality_id="b", quality_score=30.0)
        assert len(eng.identify_quality_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_quality(quality_id="a", service="s1", quality_score=80.0)
        eng.record_quality(quality_id="b", service="s2", quality_score=60.0)
        assert eng.rank_by_quality()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_quality() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(quality_id="t", analysis_score=float(v))
        assert eng.detect_quality_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(quality_id="t", analysis_score=float(v))
        assert eng.detect_quality_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_quality_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_quality(quality_id="t", quality_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_quality(quality_id="t")
        eng.add_analysis(quality_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_quality(quality_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_quality(quality_id="a")
        eng.record_quality(quality_id="b")
        eng.add_analysis(quality_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
