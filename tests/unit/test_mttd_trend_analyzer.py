"""Tests for shieldops.analytics.mttd_trend_analyzer — MTTDTrendAnalyzer."""

from __future__ import annotations

from shieldops.analytics.mttd_trend_analyzer import (
    DetectionSource,
    MetricPeriod,
    MTTDAnalysis,
    MTTDRecord,
    MTTDReport,
    MTTDTrendAnalyzer,
    TrendDirection,
)


def _engine(**kw) -> MTTDTrendAnalyzer:
    return MTTDTrendAnalyzer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert DetectionSource.SIEM == "siem"

    def test_e1_v2(self):
        assert DetectionSource.EDR == "edr"

    def test_e1_v3(self):
        assert DetectionSource.NDR == "ndr"

    def test_e1_v4(self):
        assert DetectionSource.MANUAL == "manual"

    def test_e1_v5(self):
        assert DetectionSource.AUTOMATED == "automated"

    def test_e2_v1(self):
        assert MetricPeriod.HOURLY == "hourly"

    def test_e2_v2(self):
        assert MetricPeriod.DAILY == "daily"

    def test_e2_v3(self):
        assert MetricPeriod.WEEKLY == "weekly"

    def test_e2_v4(self):
        assert MetricPeriod.MONTHLY == "monthly"

    def test_e2_v5(self):
        assert MetricPeriod.QUARTERLY == "quarterly"

    def test_e3_v1(self):
        assert TrendDirection.IMPROVING == "improving"

    def test_e3_v2(self):
        assert TrendDirection.STABLE == "stable"

    def test_e3_v3(self):
        assert TrendDirection.DEGRADING == "degrading"

    def test_e3_v4(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_e3_v5(self):
        assert TrendDirection.INSUFFICIENT == "insufficient"


class TestModels:
    def test_rec(self):
        r = MTTDRecord()
        assert r.id and r.detection_time_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = MTTDAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = MTTDReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_mttd(
            mttd_id="t",
            detection_source=DetectionSource.EDR,
            metric_period=MetricPeriod.DAILY,
            trend_direction=TrendDirection.STABLE,
            detection_time_score=92.0,
            service="s",
            team="t",
        )
        assert r.mttd_id == "t" and r.detection_time_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mttd(mttd_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_mttd(mttd_id="t")
        assert eng.get_mttd(r.id) is not None

    def test_not_found(self):
        assert _engine().get_mttd("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_mttd(mttd_id="a")
        eng.record_mttd(mttd_id="b")
        assert len(eng.list_mttds()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_mttd(mttd_id="a", detection_source=DetectionSource.SIEM)
        eng.record_mttd(mttd_id="b", detection_source=DetectionSource.EDR)
        assert len(eng.list_mttds(detection_source=DetectionSource.SIEM)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_mttd(mttd_id="a", metric_period=MetricPeriod.HOURLY)
        eng.record_mttd(mttd_id="b", metric_period=MetricPeriod.DAILY)
        assert len(eng.list_mttds(metric_period=MetricPeriod.HOURLY)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_mttd(mttd_id="a", team="x")
        eng.record_mttd(mttd_id="b", team="y")
        assert len(eng.list_mttds(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mttd(mttd_id=f"t-{i}")
        assert len(eng.list_mttds(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            mttd_id="t", detection_source=DetectionSource.EDR, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(mttd_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_mttd(
            mttd_id="a", detection_source=DetectionSource.SIEM, detection_time_score=90.0
        )
        eng.record_mttd(
            mttd_id="b", detection_source=DetectionSource.SIEM, detection_time_score=70.0
        )
        assert "siem" in eng.analyze_source_distribution()

    def test_empty(self):
        assert _engine().analyze_source_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_time_threshold=80.0)
        eng.record_mttd(mttd_id="a", detection_time_score=60.0)
        eng.record_mttd(mttd_id="b", detection_time_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_time_threshold=80.0)
        eng.record_mttd(mttd_id="a", detection_time_score=50.0)
        eng.record_mttd(mttd_id="b", detection_time_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_mttd(mttd_id="a", service="s1", detection_time_score=80.0)
        eng.record_mttd(mttd_id="b", service="s2", detection_time_score=60.0)
        assert eng.rank_by_detection_time()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection_time() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(mttd_id="t", analysis_score=float(v))
        assert eng.detect_mttd_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(mttd_id="t", analysis_score=float(v))
        assert eng.detect_mttd_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_mttd_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_mttd(mttd_id="t", detection_time_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_mttd(mttd_id="t")
        eng.add_analysis(mttd_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_mttd(mttd_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_mttd(mttd_id="a")
        eng.record_mttd(mttd_id="b")
        eng.add_analysis(mttd_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
