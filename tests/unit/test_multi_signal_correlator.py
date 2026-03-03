"""Tests for shieldops.observability.multi_signal_correlator — MultiSignalCorrelator."""

from __future__ import annotations

from shieldops.observability.multi_signal_correlator import (
    CorrelationAnalysis,
    CorrelationRecord,
    CorrelationStrength,
    CorrelationType,
    MultiSignalCorrelator,
    MultiSignalReport,
    SignalSource,
)


def _engine(**kw) -> MultiSignalCorrelator:
    return MultiSignalCorrelator(**kw)


class TestEnums:
    def test_correlation_type_temporal(self):
        assert CorrelationType.TEMPORAL == "temporal"

    def test_correlation_type_causal(self):
        assert CorrelationType.CAUSAL == "causal"

    def test_correlation_type_topological(self):
        assert CorrelationType.TOPOLOGICAL == "topological"

    def test_correlation_type_statistical(self):
        assert CorrelationType.STATISTICAL == "statistical"

    def test_correlation_type_pattern(self):
        assert CorrelationType.PATTERN == "pattern"

    def test_signal_source_metric_stream(self):
        assert SignalSource.METRIC_STREAM == "metric_stream"

    def test_signal_source_log_pipeline(self):
        assert SignalSource.LOG_PIPELINE == "log_pipeline"

    def test_signal_source_trace_backend(self):
        assert SignalSource.TRACE_BACKEND == "trace_backend"

    def test_signal_source_event_bus(self):
        assert SignalSource.EVENT_BUS == "event_bus"

    def test_signal_source_alert_system(self):
        assert SignalSource.ALERT_SYSTEM == "alert_system"

    def test_correlation_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_correlation_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_correlation_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_correlation_strength_tentative(self):
        assert CorrelationStrength.TENTATIVE == "tentative"

    def test_correlation_strength_none(self):
        assert CorrelationStrength.NONE == "none"


class TestModels:
    def test_record_defaults(self):
        r = CorrelationRecord()
        assert r.id
        assert r.name == ""
        assert r.correlation_type == CorrelationType.TEMPORAL
        assert r.signal_source == SignalSource.METRIC_STREAM
        assert r.correlation_strength == CorrelationStrength.NONE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = CorrelationAnalysis()
        assert a.id
        assert a.name == ""
        assert a.correlation_type == CorrelationType.TEMPORAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = MultiSignalReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_correlation_type == {}
        assert r.by_signal_source == {}
        assert r.by_correlation_strength == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            correlation_type=CorrelationType.TEMPORAL,
            signal_source=SignalSource.LOG_PIPELINE,
            correlation_strength=CorrelationStrength.STRONG,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.correlation_type == CorrelationType.TEMPORAL
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

    def test_filter_by_correlation_type(self):
        eng = _engine()
        eng.record_entry(name="a", correlation_type=CorrelationType.TEMPORAL)
        eng.record_entry(name="b", correlation_type=CorrelationType.CAUSAL)
        assert len(eng.list_records(correlation_type=CorrelationType.TEMPORAL)) == 1

    def test_filter_by_signal_source(self):
        eng = _engine()
        eng.record_entry(name="a", signal_source=SignalSource.METRIC_STREAM)
        eng.record_entry(name="b", signal_source=SignalSource.LOG_PIPELINE)
        assert len(eng.list_records(signal_source=SignalSource.METRIC_STREAM)) == 1

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
        eng.record_entry(name="a", correlation_type=CorrelationType.CAUSAL, score=90.0)
        eng.record_entry(name="b", correlation_type=CorrelationType.CAUSAL, score=70.0)
        result = eng.analyze_distribution()
        assert "causal" in result
        assert result["causal"]["count"] == 2

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
