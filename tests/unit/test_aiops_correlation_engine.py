"""Tests for shieldops.observability.aiops_correlation_engine — AIOpsCorrelationEngine."""

from __future__ import annotations

from shieldops.observability.aiops_correlation_engine import (
    AIOpsCorrelationEngine,
    CorrelationReport,
    CorrelationResult,
    CorrelationStrength,
    PatternType,
    SignalRecord,
    SignalType,
)


def _engine(**kw) -> AIOpsCorrelationEngine:
    return AIOpsCorrelationEngine(**kw)


class TestEnums:
    def test_signal_type_metric(self):
        assert SignalType.METRIC == "metric"

    def test_signal_type_log(self):
        assert SignalType.LOG == "log"

    def test_signal_type_trace(self):
        assert SignalType.TRACE == "trace"

    def test_signal_type_event(self):
        assert SignalType.EVENT == "event"

    def test_signal_type_alert(self):
        assert SignalType.ALERT == "alert"

    def test_correlation_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_correlation_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_correlation_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_correlation_strength_none(self):
        assert CorrelationStrength.NONE == "none"

    def test_pattern_type_temporal(self):
        assert PatternType.TEMPORAL == "temporal"

    def test_pattern_type_causal(self):
        assert PatternType.CAUSAL == "causal"


class TestModels:
    def test_signal_record_defaults(self):
        r = SignalRecord()
        assert r.id
        assert r.name == ""
        assert r.signal_type == SignalType.METRIC
        assert r.source == ""
        assert r.value == 0.0
        assert r.tags == {}
        assert r.timestamp > 0

    def test_correlation_result_defaults(self):
        c = CorrelationResult()
        assert c.id
        assert c.strength == CorrelationStrength.NONE
        assert c.score == 0.0
        assert c.confidence == 0.0

    def test_correlation_report_defaults(self):
        r = CorrelationReport()
        assert r.total_signals == 0
        assert r.total_correlations == 0
        assert r.recommendations == []


class TestAddSignal:
    def test_basic(self):
        eng = _engine()
        s = eng.add_signal(name="cpu", signal_type=SignalType.METRIC, source="host-1", value=85.0)
        assert s.name == "cpu"
        assert s.value == 85.0

    def test_with_tags(self):
        eng = _engine()
        s = eng.add_signal(name="mem", tags={"env": "prod"})
        assert s.tags == {"env": "prod"}

    def test_eviction(self):
        eng = _engine(max_signals=3)
        for i in range(5):
            eng.add_signal(name=f"s-{i}")
        assert len(eng._signals) == 3


class TestCorrelateSignals:
    def test_correlate_same_source(self):
        eng = _engine()
        eng.add_signal(name="a", source="host-1", value=50.0)
        eng.add_signal(name="b", source="host-1", value=55.0)
        results = eng.correlate_signals()
        assert isinstance(results, list)

    def test_correlate_two_sources(self):
        eng = _engine(correlation_threshold=0.0)
        eng.add_signal(name="a", source="host-1", value=50.0)
        eng.add_signal(name="b", source="host-2", value=50.0)
        results = eng.correlate_signals()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.correlate_signals() == []


class TestDetectPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.add_signal(name="a", signal_type=SignalType.METRIC, value=50.0)
        eng.add_signal(name="b", signal_type=SignalType.METRIC, value=60.0)
        patterns = eng.detect_patterns()
        assert len(patterns) == 1
        assert patterns[0]["signal_type"] == "metric"

    def test_spike_detection(self):
        eng = _engine()
        eng.add_signal(name="a", value=10.0)
        eng.add_signal(name="b", value=100.0)
        eng.add_signal(name="c", value=10.0)
        patterns = eng.detect_patterns()
        assert patterns[0]["pattern"] in ("spike", "stable")

    def test_empty(self):
        eng = _engine()
        assert eng.detect_patterns() == []


class TestBuildCorrelationGraph:
    def test_empty(self):
        eng = _engine()
        graph = eng.build_correlation_graph()
        assert graph["node_count"] == 0
        assert graph["edge_count"] == 0

    def test_with_correlations(self):
        eng = _engine(correlation_threshold=0.0)
        eng.add_signal(name="a", source="h1", value=50.0)
        eng.add_signal(name="b", source="h2", value=50.0)
        eng.correlate_signals()
        graph = eng.build_correlation_graph()
        assert graph["node_count"] == 2
        assert graph["edge_count"] == 1


class TestScoreCorrelations:
    def test_empty(self):
        eng = _engine()
        result = eng.score_correlations()
        assert result["count"] == 0

    def test_with_data(self):
        eng = _engine(correlation_threshold=0.0)
        eng.add_signal(name="a", source="h1", value=50.0)
        eng.add_signal(name="b", source="h2", value=50.0)
        eng.correlate_signals()
        result = eng.score_correlations()
        assert result["count"] == 1


class TestGetRootCauseCandidates:
    def test_empty(self):
        eng = _engine()
        assert eng.get_root_cause_candidates() == []

    def test_with_data(self):
        eng = _engine(correlation_threshold=0.0)
        eng.add_signal(name="a", source="h1", value=50.0)
        eng.add_signal(name="b", source="h2", value=50.0)
        eng.correlate_signals()
        candidates = eng.get_root_cause_candidates()
        assert len(candidates) == 2


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_signals == 0

    def test_populated(self):
        eng = _engine()
        eng.add_signal(name="a", source="h1", value=50.0)
        report = eng.generate_report()
        assert report.total_signals == 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_signal(name="a")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._signals) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_signals"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_signal(name="a", source="h1")
        stats = eng.get_stats()
        assert stats["total_signals"] == 1
        assert stats["unique_sources"] == 1
