"""Tests for shieldops.analytics.security_kpi_tracker — SecurityKPITracker."""

from __future__ import annotations

from shieldops.analytics.security_kpi_tracker import (
    KPIAnalysis,
    KPICategory,
    KPIRecord,
    KPIReport,
    KPIStatus,
    MeasurementFrequency,
    SecurityKPITracker,
)


def _engine(**kw) -> SecurityKPITracker:
    return SecurityKPITracker(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert KPICategory.DETECTION == "detection"

    def test_e1_v2(self):
        assert KPICategory.RESPONSE == "response"

    def test_e1_v3(self):
        assert KPICategory.PREVENTION == "prevention"

    def test_e1_v4(self):
        assert KPICategory.COMPLIANCE == "compliance"

    def test_e1_v5(self):
        assert KPICategory.RISK == "risk"

    def test_e2_v1(self):
        assert MeasurementFrequency.REALTIME == "realtime"

    def test_e2_v2(self):
        assert MeasurementFrequency.DAILY == "daily"

    def test_e2_v3(self):
        assert MeasurementFrequency.WEEKLY == "weekly"

    def test_e2_v4(self):
        assert MeasurementFrequency.MONTHLY == "monthly"

    def test_e2_v5(self):
        assert MeasurementFrequency.QUARTERLY == "quarterly"

    def test_e3_v1(self):
        assert KPIStatus.ON_TARGET == "on_target"

    def test_e3_v2(self):
        assert KPIStatus.AT_RISK == "at_risk"

    def test_e3_v3(self):
        assert KPIStatus.MISSED == "missed"

    def test_e3_v4(self):
        assert KPIStatus.EXCEEDED == "exceeded"

    def test_e3_v5(self):
        assert KPIStatus.NOT_MEASURED == "not_measured"


class TestModels:
    def test_rec(self):
        r = KPIRecord()
        assert r.id and r.kpi_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = KPIAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = KPIReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_kpi(
            kpi_id="t",
            kpi_category=KPICategory.RESPONSE,
            measurement_frequency=MeasurementFrequency.DAILY,
            kpi_status=KPIStatus.AT_RISK,
            kpi_score=92.0,
            service="s",
            team="t",
        )
        assert r.kpi_id == "t" and r.kpi_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_kpi(kpi_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_kpi(kpi_id="t")
        assert eng.get_kpi(r.id) is not None

    def test_not_found(self):
        assert _engine().get_kpi("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_kpi(kpi_id="a")
        eng.record_kpi(kpi_id="b")
        assert len(eng.list_kpis()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_kpi(kpi_id="a", kpi_category=KPICategory.DETECTION)
        eng.record_kpi(kpi_id="b", kpi_category=KPICategory.RESPONSE)
        assert len(eng.list_kpis(kpi_category=KPICategory.DETECTION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_kpi(kpi_id="a", measurement_frequency=MeasurementFrequency.REALTIME)
        eng.record_kpi(kpi_id="b", measurement_frequency=MeasurementFrequency.DAILY)
        assert len(eng.list_kpis(measurement_frequency=MeasurementFrequency.REALTIME)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_kpi(kpi_id="a", team="x")
        eng.record_kpi(kpi_id="b", team="y")
        assert len(eng.list_kpis(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_kpi(kpi_id=f"t-{i}")
        assert len(eng.list_kpis(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            kpi_id="t", kpi_category=KPICategory.RESPONSE, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(kpi_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_kpi(kpi_id="a", kpi_category=KPICategory.DETECTION, kpi_score=90.0)
        eng.record_kpi(kpi_id="b", kpi_category=KPICategory.DETECTION, kpi_score=70.0)
        assert "detection" in eng.analyze_category_distribution()

    def test_empty(self):
        assert _engine().analyze_category_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(kpi_threshold=80.0)
        eng.record_kpi(kpi_id="a", kpi_score=60.0)
        eng.record_kpi(kpi_id="b", kpi_score=90.0)
        assert len(eng.identify_kpi_gaps()) == 1

    def test_sorted(self):
        eng = _engine(kpi_threshold=80.0)
        eng.record_kpi(kpi_id="a", kpi_score=50.0)
        eng.record_kpi(kpi_id="b", kpi_score=30.0)
        assert len(eng.identify_kpi_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_kpi(kpi_id="a", service="s1", kpi_score=80.0)
        eng.record_kpi(kpi_id="b", service="s2", kpi_score=60.0)
        assert eng.rank_by_kpi()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_kpi() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(kpi_id="t", analysis_score=float(v))
        assert eng.detect_kpi_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(kpi_id="t", analysis_score=float(v))
        assert eng.detect_kpi_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_kpi_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_kpi(kpi_id="t", kpi_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_kpi(kpi_id="t")
        eng.add_analysis(kpi_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_kpi(kpi_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_kpi(kpi_id="a")
        eng.record_kpi(kpi_id="b")
        eng.add_analysis(kpi_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
