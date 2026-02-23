"""Tests for shieldops.analytics.anomaly_correlation — AnomalyCorrelationEngine."""

from __future__ import annotations

import time

from shieldops.analytics.anomaly_correlation import (
    AnomalyCorrelationEngine,
    AnomalyEvent,
    AnomalyType,
    CorrelationResult,
    CorrelationRule,
    CorrelationStrength,
)


def _engine(**kw) -> AnomalyCorrelationEngine:
    return AnomalyCorrelationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # AnomalyType (6 values)

    def test_anomaly_type_metric_spike(self):
        assert AnomalyType.METRIC_SPIKE == "metric_spike"

    def test_anomaly_type_metric_drop(self):
        assert AnomalyType.METRIC_DROP == "metric_drop"

    def test_anomaly_type_error_burst(self):
        assert AnomalyType.ERROR_BURST == "error_burst"

    def test_anomaly_type_latency(self):
        assert AnomalyType.LATENCY == "latency"

    def test_anomaly_type_saturation(self):
        assert AnomalyType.SATURATION == "saturation"

    def test_anomaly_type_traffic_anomaly(self):
        assert AnomalyType.TRAFFIC_ANOMALY == "traffic_anomaly"

    # CorrelationStrength (4 values)

    def test_correlation_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_correlation_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_correlation_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_correlation_strength_definitive(self):
        assert CorrelationStrength.DEFINITIVE == "definitive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_anomaly_event_defaults(self):
        ev = AnomalyEvent(service="web", anomaly_type=AnomalyType.LATENCY)
        assert ev.id
        assert ev.service == "web"
        assert ev.metric_name == ""
        assert ev.value == 0.0
        assert ev.baseline == 0.0
        assert ev.deviation_pct == 0.0
        assert ev.timestamp > 0
        assert ev.metadata == {}

    def test_correlation_result_defaults(self):
        cr = CorrelationResult()
        assert cr.id
        assert cr.anomaly_ids == []
        assert cr.services == []
        assert cr.root_cause_service == ""
        assert cr.correlation_strength == CorrelationStrength.WEAK
        assert cr.time_window_seconds == 0.0
        assert cr.description == ""
        assert cr.detected_at > 0

    def test_correlation_rule_defaults(self):
        rule = CorrelationRule(name="r1", source_service="a", target_service="b")
        assert rule.id
        assert rule.name == "r1"
        assert rule.max_delay_seconds == 300.0
        assert rule.min_confidence == 0.5
        assert rule.enabled is True
        assert rule.created_at > 0


# ---------------------------------------------------------------------------
# record_anomaly
# ---------------------------------------------------------------------------


class TestRecordAnomaly:
    def test_basic_record(self):
        eng = _engine()
        ev = eng.record_anomaly("web", AnomalyType.LATENCY)
        assert ev.service == "web"
        assert ev.anomaly_type == AnomalyType.LATENCY
        assert len(eng.list_anomalies()) == 1

    def test_record_with_fields(self):
        eng = _engine()
        ev = eng.record_anomaly(
            "db",
            AnomalyType.METRIC_SPIKE,
            metric_name="cpu",
            value=95.0,
            baseline=50.0,
            deviation_pct=90.0,
        )
        assert ev.metric_name == "cpu"
        assert ev.value == 95.0
        assert ev.baseline == 50.0
        assert ev.deviation_pct == 90.0

    def test_record_trims_to_max(self):
        eng = _engine(max_events=3)
        eng.record_anomaly("s1", AnomalyType.LATENCY)
        eng.record_anomaly("s2", AnomalyType.LATENCY)
        eng.record_anomaly("s3", AnomalyType.LATENCY)
        eng.record_anomaly("s4", AnomalyType.LATENCY)
        assert len(eng.list_anomalies()) == 3


# ---------------------------------------------------------------------------
# create_rule
# ---------------------------------------------------------------------------


class TestCreateRule:
    def test_basic_rule(self):
        eng = _engine()
        rule = eng.create_rule("r1", "web", "db")
        assert rule.name == "r1"
        assert rule.source_service == "web"
        assert rule.target_service == "db"
        assert rule.enabled is True

    def test_rule_with_params(self):
        eng = _engine()
        rule = eng.create_rule("r2", "api", "cache", max_delay_seconds=60.0, min_confidence=0.8)
        assert rule.max_delay_seconds == 60.0
        assert rule.min_confidence == 0.8


# ---------------------------------------------------------------------------
# correlate
# ---------------------------------------------------------------------------


class TestCorrelate:
    def test_finds_correlated_anomalies(self):
        eng = _engine(correlation_window_seconds=10)
        now = time.time()
        eng.record_anomaly("web", AnomalyType.LATENCY, timestamp=now)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE, timestamp=now + 1)
        eng.record_anomaly("cache", AnomalyType.ERROR_BURST, timestamp=now + 2)
        results = eng.correlate()
        assert len(results) == 1
        assert len(results[0].anomaly_ids) == 3
        assert set(results[0].services) == {"web", "db", "cache"}

    def test_no_correlations_distant_timestamps(self):
        eng = _engine(correlation_window_seconds=5)
        now = time.time()
        eng.record_anomaly("web", AnomalyType.LATENCY, timestamp=now)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE, timestamp=now + 1000)
        results = eng.correlate()
        assert len(results) == 0

    def test_root_cause_is_earliest(self):
        eng = _engine(correlation_window_seconds=10)
        now = time.time()
        eng.record_anomaly("db", AnomalyType.SATURATION, timestamp=now)
        eng.record_anomaly("web", AnomalyType.LATENCY, timestamp=now + 2)
        results = eng.correlate()
        assert len(results) == 1
        assert results[0].root_cause_service == "db"


# ---------------------------------------------------------------------------
# get_correlations
# ---------------------------------------------------------------------------


class TestGetCorrelations:
    def _populate(self, eng: AnomalyCorrelationEngine) -> None:
        now = time.time()
        eng.record_anomaly("web", AnomalyType.LATENCY, timestamp=now)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE, timestamp=now + 1)
        eng.correlate()

    def test_get_all(self):
        eng = _engine(correlation_window_seconds=10)
        self._populate(eng)
        assert len(eng.get_correlations()) == 1

    def test_get_by_service(self):
        eng = _engine(correlation_window_seconds=10)
        self._populate(eng)
        assert len(eng.get_correlations(service="web")) == 1
        assert len(eng.get_correlations(service="nonexistent")) == 0

    def test_get_by_strength(self):
        eng = _engine(correlation_window_seconds=10)
        self._populate(eng)
        # 2 anomalies => WEAK
        assert len(eng.get_correlations(min_strength=CorrelationStrength.WEAK)) == 1
        assert len(eng.get_correlations(min_strength=CorrelationStrength.STRONG)) == 0


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_list_all(self):
        eng = _engine()
        eng.create_rule("r1", "a", "b")
        eng.create_rule("r2", "c", "d", enabled=False)
        assert len(eng.list_rules()) == 2

    def test_list_enabled_only(self):
        eng = _engine()
        eng.create_rule("r1", "a", "b")
        eng.create_rule("r2", "c", "d", enabled=False)
        enabled = eng.list_rules(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].name == "r1"


# ---------------------------------------------------------------------------
# delete_rule
# ---------------------------------------------------------------------------


class TestDeleteRule:
    def test_delete_existing(self):
        eng = _engine()
        rule = eng.create_rule("r1", "a", "b")
        assert eng.delete_rule(rule.id) is True
        assert len(eng.list_rules()) == 0

    def test_delete_nonexistent(self):
        eng = _engine()
        assert eng.delete_rule("nonexistent") is False


# ---------------------------------------------------------------------------
# list_anomalies
# ---------------------------------------------------------------------------


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine()
        eng.record_anomaly("web", AnomalyType.LATENCY)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE)
        assert len(eng.list_anomalies()) == 2

    def test_list_by_service(self):
        eng = _engine()
        eng.record_anomaly("web", AnomalyType.LATENCY)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE)
        results = eng.list_anomalies(service="web")
        assert len(results) == 1
        assert results[0].service == "web"

    def test_list_by_type(self):
        eng = _engine()
        eng.record_anomaly("web", AnomalyType.LATENCY)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE)
        results = eng.list_anomalies(anomaly_type=AnomalyType.LATENCY)
        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.LATENCY

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_anomaly(f"svc{i}", AnomalyType.LATENCY)
        results = eng.list_anomalies(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# clear_anomalies
# ---------------------------------------------------------------------------


class TestClearAnomalies:
    def test_clear_all(self):
        eng = _engine()
        eng.record_anomaly("web", AnomalyType.LATENCY)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE)
        removed = eng.clear_anomalies()
        assert removed == 2
        assert len(eng.list_anomalies()) == 0

    def test_clear_before_timestamp(self):
        eng = _engine()
        now = time.time()
        eng.record_anomaly("web", AnomalyType.LATENCY, timestamp=now - 100)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE, timestamp=now)
        removed = eng.clear_anomalies(before_timestamp=now - 50)
        assert removed == 1
        assert len(eng.list_anomalies()) == 1

    def test_clear_empty(self):
        eng = _engine()
        removed = eng.clear_anomalies()
        assert removed == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 0
        assert stats["total_correlations"] == 0
        assert stats["total_rules"] == 0
        assert stats["services_affected"] == 0
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine(correlation_window_seconds=10)
        now = time.time()
        eng.record_anomaly("web", AnomalyType.LATENCY, timestamp=now)
        eng.record_anomaly("db", AnomalyType.METRIC_SPIKE, timestamp=now + 1)
        eng.create_rule("r1", "web", "db")
        eng.correlate()
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 2
        assert stats["total_correlations"] == 1
        assert stats["total_rules"] == 1
        assert stats["services_affected"] == 2
        assert AnomalyType.LATENCY in stats["type_distribution"]
        assert AnomalyType.METRIC_SPIKE in stats["type_distribution"]
