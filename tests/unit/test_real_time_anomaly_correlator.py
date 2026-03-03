"""Tests for shieldops.observability.real_time_anomaly_correlator — RealTimeAnomalyCorrelator."""

from __future__ import annotations

from shieldops.observability.real_time_anomaly_correlator import (
    AnomalyAnalysis,
    AnomalyCorrelation,
    AnomalyRecord,
    AnomalySource,
    AnomalyType,
    RealTimeAnomalyCorrelator,
    RealTimeAnomalyReport,
)


def _engine(**kw) -> RealTimeAnomalyCorrelator:
    return RealTimeAnomalyCorrelator(**kw)


class TestEnums:
    def test_anomaly_type_spike(self):
        assert AnomalyType.SPIKE == "spike"

    def test_anomaly_type_drop(self):
        assert AnomalyType.DROP == "drop"

    def test_anomaly_type_drift(self):
        assert AnomalyType.DRIFT == "drift"

    def test_anomaly_type_pattern_break(self):
        assert AnomalyType.PATTERN_BREAK == "pattern_break"

    def test_anomaly_type_seasonal(self):
        assert AnomalyType.SEASONAL == "seasonal"

    def test_anomaly_source_metric_stream(self):
        assert AnomalySource.METRIC_STREAM == "metric_stream"

    def test_anomaly_source_log_pipeline(self):
        assert AnomalySource.LOG_PIPELINE == "log_pipeline"

    def test_anomaly_source_trace_analysis(self):
        assert AnomalySource.TRACE_ANALYSIS == "trace_analysis"

    def test_anomaly_source_user_report(self):
        assert AnomalySource.USER_REPORT == "user_report"

    def test_anomaly_source_ml_model(self):
        assert AnomalySource.ML_MODEL == "ml_model"

    def test_anomaly_correlation_confirmed(self):
        assert AnomalyCorrelation.CONFIRMED == "confirmed"

    def test_anomaly_correlation_probable(self):
        assert AnomalyCorrelation.PROBABLE == "probable"

    def test_anomaly_correlation_possible(self):
        assert AnomalyCorrelation.POSSIBLE == "possible"

    def test_anomaly_correlation_coincidental(self):
        assert AnomalyCorrelation.COINCIDENTAL == "coincidental"

    def test_anomaly_correlation_unrelated(self):
        assert AnomalyCorrelation.UNRELATED == "unrelated"


class TestModels:
    def test_record_defaults(self):
        r = AnomalyRecord()
        assert r.id
        assert r.name == ""
        assert r.anomaly_type == AnomalyType.SPIKE
        assert r.anomaly_source == AnomalySource.METRIC_STREAM
        assert r.anomaly_correlation == AnomalyCorrelation.UNRELATED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AnomalyAnalysis()
        assert a.id
        assert a.name == ""
        assert a.anomaly_type == AnomalyType.SPIKE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = RealTimeAnomalyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_anomaly_type == {}
        assert r.by_anomaly_source == {}
        assert r.by_anomaly_correlation == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            anomaly_type=AnomalyType.SPIKE,
            anomaly_source=AnomalySource.LOG_PIPELINE,
            anomaly_correlation=AnomalyCorrelation.CONFIRMED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.anomaly_type == AnomalyType.SPIKE
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

    def test_filter_by_anomaly_type(self):
        eng = _engine()
        eng.record_entry(name="a", anomaly_type=AnomalyType.SPIKE)
        eng.record_entry(name="b", anomaly_type=AnomalyType.DROP)
        assert len(eng.list_records(anomaly_type=AnomalyType.SPIKE)) == 1

    def test_filter_by_anomaly_source(self):
        eng = _engine()
        eng.record_entry(name="a", anomaly_source=AnomalySource.METRIC_STREAM)
        eng.record_entry(name="b", anomaly_source=AnomalySource.LOG_PIPELINE)
        assert len(eng.list_records(anomaly_source=AnomalySource.METRIC_STREAM)) == 1

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
        eng.record_entry(name="a", anomaly_type=AnomalyType.DROP, score=90.0)
        eng.record_entry(name="b", anomaly_type=AnomalyType.DROP, score=70.0)
        result = eng.analyze_distribution()
        assert "drop" in result
        assert result["drop"]["count"] == 2

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
