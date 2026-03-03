"""Tests for shieldops.security.security_observability_engine — SecurityObservabilityEngine."""

from __future__ import annotations

from shieldops.security.security_observability_engine import (
    ObservabilityGrade,
    SecObsAnalysis,
    SecObsMetric,
    SecObsRecord,
    SecObsSource,
    SecurityObservabilityEngine,
    SecurityObservabilityReport,
)


def _engine(**kw) -> SecurityObservabilityEngine:
    return SecurityObservabilityEngine(**kw)


class TestEnums:
    def test_sec_obs_metric_mttd(self):
        assert SecObsMetric.MTTD == "mttd"

    def test_sec_obs_metric_mttr(self):
        assert SecObsMetric.MTTR == "mttr"

    def test_sec_obs_metric_detection_coverage(self):
        assert SecObsMetric.DETECTION_COVERAGE == "detection_coverage"

    def test_sec_obs_metric_false_positive_rate(self):
        assert SecObsMetric.FALSE_POSITIVE_RATE == "false_positive_rate"

    def test_sec_obs_metric_alert_volume(self):
        assert SecObsMetric.ALERT_VOLUME == "alert_volume"

    def test_sec_obs_source_siem(self):
        assert SecObsSource.SIEM == "siem"

    def test_sec_obs_source_soar(self):
        assert SecObsSource.SOAR == "soar"

    def test_sec_obs_source_edr(self):
        assert SecObsSource.EDR == "edr"

    def test_sec_obs_source_ndr(self):
        assert SecObsSource.NDR == "ndr"

    def test_sec_obs_source_custom(self):
        assert SecObsSource.CUSTOM == "custom"

    def test_observability_grade_excellent(self):
        assert ObservabilityGrade.EXCELLENT == "excellent"

    def test_observability_grade_good(self):
        assert ObservabilityGrade.GOOD == "good"

    def test_observability_grade_adequate(self):
        assert ObservabilityGrade.ADEQUATE == "adequate"

    def test_observability_grade_poor(self):
        assert ObservabilityGrade.POOR == "poor"

    def test_observability_grade_failing(self):
        assert ObservabilityGrade.FAILING == "failing"


class TestModels:
    def test_record_defaults(self):
        r = SecObsRecord()
        assert r.id
        assert r.name == ""
        assert r.sec_obs_metric == SecObsMetric.MTTD
        assert r.sec_obs_source == SecObsSource.SIEM
        assert r.observability_grade == ObservabilityGrade.FAILING
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SecObsAnalysis()
        assert a.id
        assert a.name == ""
        assert a.sec_obs_metric == SecObsMetric.MTTD
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SecurityObservabilityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_sec_obs_metric == {}
        assert r.by_sec_obs_source == {}
        assert r.by_observability_grade == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            sec_obs_metric=SecObsMetric.MTTD,
            sec_obs_source=SecObsSource.SOAR,
            observability_grade=ObservabilityGrade.EXCELLENT,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.sec_obs_metric == SecObsMetric.MTTD
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

    def test_filter_by_sec_obs_metric(self):
        eng = _engine()
        eng.record_entry(name="a", sec_obs_metric=SecObsMetric.MTTD)
        eng.record_entry(name="b", sec_obs_metric=SecObsMetric.MTTR)
        assert len(eng.list_records(sec_obs_metric=SecObsMetric.MTTD)) == 1

    def test_filter_by_sec_obs_source(self):
        eng = _engine()
        eng.record_entry(name="a", sec_obs_source=SecObsSource.SIEM)
        eng.record_entry(name="b", sec_obs_source=SecObsSource.SOAR)
        assert len(eng.list_records(sec_obs_source=SecObsSource.SIEM)) == 1

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
        eng.record_entry(name="a", sec_obs_metric=SecObsMetric.MTTR, score=90.0)
        eng.record_entry(name="b", sec_obs_metric=SecObsMetric.MTTR, score=70.0)
        result = eng.analyze_distribution()
        assert "mttr" in result
        assert result["mttr"]["count"] == 2

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
