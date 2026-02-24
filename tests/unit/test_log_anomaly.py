"""Tests for shieldops.analytics.log_anomaly — LogAnomalyDetector."""

from __future__ import annotations

from shieldops.analytics.log_anomaly import (
    AnomalySeverity,
    AnomalySummary,
    AnomalyType,
    DetectionMethod,
    LogAnomaly,
    LogAnomalyDetector,
    LogPattern,
)


def _engine(**kw) -> LogAnomalyDetector:
    return LogAnomalyDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_volume_spike(self):
        assert AnomalyType.VOLUME_SPIKE == "volume_spike"

    def test_type_new_pattern(self):
        assert AnomalyType.NEW_PATTERN == "new_pattern"

    def test_type_error_rate_surge(self):
        assert AnomalyType.ERROR_RATE_SURGE == "error_rate_surge"

    def test_type_pattern_disappearance(self):
        assert AnomalyType.PATTERN_DISAPPEARANCE == "pattern_disappearance"

    def test_type_frequency_shift(self):
        assert AnomalyType.FREQUENCY_SHIFT == "frequency_shift"

    def test_severity_info(self):
        assert AnomalySeverity.INFO == "info"

    def test_severity_low(self):
        assert AnomalySeverity.LOW == "low"

    def test_severity_medium(self):
        assert AnomalySeverity.MEDIUM == "medium"

    def test_severity_high(self):
        assert AnomalySeverity.HIGH == "high"

    def test_severity_critical(self):
        assert AnomalySeverity.CRITICAL == "critical"

    def test_method_statistical(self):
        assert DetectionMethod.STATISTICAL == "statistical"

    def test_method_pattern_matching(self):
        assert DetectionMethod.PATTERN_MATCHING == "pattern_matching"

    def test_method_frequency(self):
        assert DetectionMethod.FREQUENCY_ANALYSIS == "frequency_analysis"

    def test_method_baseline(self):
        assert DetectionMethod.BASELINE_COMPARISON == "baseline_comparison"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_log_pattern_defaults(self):
        p = LogPattern()
        assert p.id
        assert p.count == 0
        assert p.level == "info"

    def test_log_anomaly_defaults(self):
        a = LogAnomaly()
        assert a.anomaly_type == AnomalyType.VOLUME_SPIKE
        assert a.acknowledged is False

    def test_anomaly_summary_defaults(self):
        s = AnomalySummary()
        assert s.total_anomalies == 0
        assert s.unacknowledged == 0


# ---------------------------------------------------------------------------
# register_pattern
# ---------------------------------------------------------------------------


class TestRegisterPattern:
    def test_basic_register(self):
        eng = _engine()
        p = eng.register_pattern("ERROR.*timeout")
        assert p.pattern == "ERROR.*timeout"

    def test_unique_ids(self):
        eng = _engine()
        p1 = eng.register_pattern("pattern1")
        p2 = eng.register_pattern("pattern2")
        assert p1.id != p2.id

    def test_eviction_at_max(self):
        eng = _engine(max_patterns=3)
        for i in range(5):
            eng.register_pattern(f"p{i}")
        assert len(eng._patterns) == 3

    def test_with_service(self):
        eng = _engine()
        p = eng.register_pattern("err", service="api-gateway")
        assert p.service == "api-gateway"


# ---------------------------------------------------------------------------
# submit_log_batch
# ---------------------------------------------------------------------------


class TestSubmitLogBatch:
    def test_basic_batch(self):
        eng = _engine()
        result = eng.submit_log_batch("svc-a", [{"message": "hello"}])
        assert result["processed"] == 1

    def test_batch_updates_pattern_count(self):
        eng = _engine()
        eng.register_pattern("hello", service="svc-a")
        eng.submit_log_batch("svc-a", [{"message": "hello world"}])
        assert eng._patterns[0].count == 1

    def test_new_pattern_auto_registered(self):
        eng = _engine()
        initial = len(eng._patterns)
        eng.submit_log_batch("svc-a", [{"message": "new_unique_msg"}])
        assert len(eng._patterns) > initial


# ---------------------------------------------------------------------------
# detect_anomalies
# ---------------------------------------------------------------------------


class TestDetectAnomalies:
    def test_no_anomalies_when_empty(self):
        eng = _engine()
        assert eng.detect_anomalies() == []

    def test_volume_spike_detected(self):
        eng = _engine(sensitivity=0.7)
        p = eng.register_pattern("spike_pattern")
        eng.set_baseline("spike_pattern", 5.0)
        # Manually bump count
        p.count = 50
        anomalies = eng.detect_anomalies()
        spike_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.VOLUME_SPIKE]
        assert len(spike_anomalies) >= 1

    def test_error_rate_surge_detected(self):
        eng = _engine(sensitivity=0.5)
        eng.register_pattern("err1", level="error")
        eng._patterns[0].count = 100
        anomalies = eng.detect_anomalies()
        error_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.ERROR_RATE_SURGE]
        assert len(error_anomalies) >= 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_pattern("p1", service="svc-a")
        eng.register_pattern("p2", service="svc-b")
        eng.set_baseline("p1", 1.0)
        eng._patterns[0].count = 100
        anomalies = eng.detect_anomalies(service="svc-a")
        for a in anomalies:
            assert a.service == "svc-a" or a.service == "all"


# ---------------------------------------------------------------------------
# get / list / acknowledge anomalies
# ---------------------------------------------------------------------------


class TestGetAnomaly:
    def test_found(self):
        eng = _engine(sensitivity=0.5)
        eng.register_pattern("err", level="error")
        eng._patterns[0].count = 100
        anomalies = eng.detect_anomalies()
        if anomalies:
            assert eng.get_anomaly(anomalies[0].id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_anomaly("nonexistent") is None


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine(sensitivity=0.5)
        eng.register_pattern("err", level="error")
        eng._patterns[0].count = 100
        eng.detect_anomalies()
        assert len(eng.list_anomalies()) >= 1


class TestAcknowledgeAnomaly:
    def test_acknowledge(self):
        eng = _engine(sensitivity=0.5)
        eng.register_pattern("err", level="error")
        eng._patterns[0].count = 100
        anomalies = eng.detect_anomalies()
        if anomalies:
            assert eng.acknowledge_anomaly(anomalies[0].id) is True

    def test_acknowledge_not_found(self):
        eng = _engine()
        assert eng.acknowledge_anomaly("nonexistent") is False


# ---------------------------------------------------------------------------
# baseline / pattern stats / trending / stats
# ---------------------------------------------------------------------------


class TestSetBaseline:
    def test_set_baseline(self):
        eng = _engine()
        result = eng.set_baseline("pattern1", 10.0)
        assert result["baseline_rate"] == 10.0


class TestPatternStats:
    def test_found(self):
        eng = _engine()
        p = eng.register_pattern("test_pattern")
        stats = eng.get_pattern_stats(p.id)
        assert stats is not None
        assert stats["pattern"] == "test_pattern"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_pattern_stats("nonexistent") is None


class TestTrendingPatterns:
    def test_trending(self):
        eng = _engine()
        p1 = eng.register_pattern("high")
        p2 = eng.register_pattern("low")
        p1.count = 100
        p2.count = 5
        trending = eng.get_trending_patterns(limit=2)
        assert len(trending) == 2
        assert trending[0]["count"] == 100


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_patterns"] == 0
        assert stats["total_anomalies"] == 0

    def test_populated_stats(self):
        eng = _engine(sensitivity=0.5)
        eng.register_pattern("err", level="error")
        eng._patterns[0].count = 100
        eng.detect_anomalies()
        stats = eng.get_stats()
        assert stats["total_patterns"] >= 1
        assert stats["total_anomalies"] >= 1
