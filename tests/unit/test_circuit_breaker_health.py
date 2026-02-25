"""Tests for shieldops.topology.circuit_breaker_health — CircuitBreakerHealthMonitor."""

from __future__ import annotations

from shieldops.topology.circuit_breaker_health import (
    BreakerState,
    BreakerStateRecord,
    BreakerTransition,
    CircuitBreakerHealthMonitor,
    CircuitBreakerReport,
    RecoverySpeed,
    TripReason,
)


def _engine(**kw) -> CircuitBreakerHealthMonitor:
    return CircuitBreakerHealthMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BreakerState (5)
    def test_state_closed(self):
        assert BreakerState.CLOSED == "closed"

    def test_state_open(self):
        assert BreakerState.OPEN == "open"

    def test_state_half_open(self):
        assert BreakerState.HALF_OPEN == "half_open"

    def test_state_forced_open(self):
        assert BreakerState.FORCED_OPEN == "forced_open"

    def test_state_disabled(self):
        assert BreakerState.DISABLED == "disabled"

    # TripReason (5)
    def test_trip_error_rate(self):
        assert TripReason.ERROR_RATE == "error_rate"

    def test_trip_timeout(self):
        assert TripReason.TIMEOUT == "timeout"

    def test_trip_latency(self):
        assert TripReason.LATENCY == "latency"

    def test_trip_resource_exhaustion(self):
        assert TripReason.RESOURCE_EXHAUSTION == "resource_exhaustion"

    def test_trip_manual(self):
        assert TripReason.MANUAL == "manual"

    # RecoverySpeed (5)
    def test_recovery_fast(self):
        assert RecoverySpeed.FAST == "fast"

    def test_recovery_normal(self):
        assert RecoverySpeed.NORMAL == "normal"

    def test_recovery_slow(self):
        assert RecoverySpeed.SLOW == "slow"

    def test_recovery_stalled(self):
        assert RecoverySpeed.STALLED == "stalled"

    def test_recovery_not_recovering(self):
        assert RecoverySpeed.NOT_RECOVERING == "not_recovering"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_breaker_state_record_defaults(self):
        r = BreakerStateRecord()
        assert r.id
        assert r.service_name == ""
        assert r.state == BreakerState.CLOSED
        assert r.trip_reason == TripReason.ERROR_RATE
        assert r.error_rate_pct == 0.0
        assert r.recovery_speed == RecoverySpeed.NORMAL
        assert r.details == ""
        assert r.created_at > 0

    def test_breaker_transition_defaults(self):
        r = BreakerTransition()
        assert r.id
        assert r.service_name == ""
        assert r.from_state == BreakerState.CLOSED
        assert r.to_state == BreakerState.OPEN
        assert r.trip_reason == TripReason.ERROR_RATE
        assert r.duration_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_circuit_breaker_report_defaults(self):
        r = CircuitBreakerReport()
        assert r.total_states == 0
        assert r.total_transitions == 0
        assert r.avg_error_rate_pct == 0.0
        assert r.by_state == {}
        assert r.by_trip_reason == {}
        assert r.frequently_tripping_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_state
# -------------------------------------------------------------------


class TestRecordState:
    def test_basic(self):
        eng = _engine()
        r = eng.record_state("payment-svc", error_rate_pct=5.2)
        assert r.service_name == "payment-svc"
        assert r.error_rate_pct == 5.2
        assert r.state == BreakerState.CLOSED

    def test_with_state_and_recovery(self):
        eng = _engine()
        r = eng.record_state(
            "user-svc",
            state=BreakerState.OPEN,
            trip_reason=TripReason.TIMEOUT,
            recovery_speed=RecoverySpeed.SLOW,
        )
        assert r.state == BreakerState.OPEN
        assert r.trip_reason == TripReason.TIMEOUT
        assert r.recovery_speed == RecoverySpeed.SLOW

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_state(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_state
# -------------------------------------------------------------------


class TestGetState:
    def test_found(self):
        eng = _engine()
        r = eng.record_state("svc")
        assert eng.get_state(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_state("nonexistent") is None


# -------------------------------------------------------------------
# list_states
# -------------------------------------------------------------------


class TestListStates:
    def test_list_all(self):
        eng = _engine()
        eng.record_state("svc-a")
        eng.record_state("svc-b")
        assert len(eng.list_states()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_state("svc-a")
        eng.record_state("svc-b")
        results = eng.list_states(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_state(self):
        eng = _engine()
        eng.record_state("svc-a", state=BreakerState.CLOSED)
        eng.record_state("svc-b", state=BreakerState.OPEN)
        results = eng.list_states(state=BreakerState.OPEN)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# record_transition
# -------------------------------------------------------------------


class TestRecordTransition:
    def test_basic(self):
        eng = _engine()
        t = eng.record_transition("payment-svc", duration_seconds=30.5)
        assert t.service_name == "payment-svc"
        assert t.from_state == BreakerState.CLOSED
        assert t.to_state == BreakerState.OPEN
        assert t.duration_seconds == 30.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_transition(f"svc-{i}")
        assert len(eng._transitions) == 2


# -------------------------------------------------------------------
# analyze_breaker_health
# -------------------------------------------------------------------


class TestAnalyzeBreakerHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_state("svc-a", state=BreakerState.CLOSED, error_rate_pct=2.0)
        eng.record_state("svc-a", state=BreakerState.OPEN, error_rate_pct=50.0)
        eng.record_transition("svc-a")
        result = eng.analyze_breaker_health("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_states"] == 2
        assert result["total_transitions"] == 1
        assert result["avg_error_rate_pct"] == 26.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_breaker_health("unknown")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_frequently_tripping
# -------------------------------------------------------------------


class TestIdentifyFrequentlyTripping:
    def test_above_threshold(self):
        eng = _engine(max_trip_count_24h=2)
        for _ in range(5):
            eng.record_transition("svc-a")
        eng.record_transition("svc-b")
        results = eng.identify_frequently_tripping()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["trip_count"] == 5

    def test_below_threshold(self):
        eng = _engine(max_trip_count_24h=10)
        eng.record_transition("svc-a")
        results = eng.identify_frequently_tripping()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_frequently_tripping() == []


# -------------------------------------------------------------------
# detect_slow_recoveries
# -------------------------------------------------------------------


class TestDetectSlowRecoveries:
    def test_with_slow(self):
        eng = _engine()
        eng.record_state("svc-a", recovery_speed=RecoverySpeed.SLOW)
        eng.record_state("svc-b", recovery_speed=RecoverySpeed.STALLED)
        eng.record_state("svc-c", recovery_speed=RecoverySpeed.NORMAL)
        results = eng.detect_slow_recoveries()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.detect_slow_recoveries() == []


# -------------------------------------------------------------------
# rank_by_impact
# -------------------------------------------------------------------


class TestRankByImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_state("svc-a", state=BreakerState.OPEN)
        eng.record_state("svc-a", state=BreakerState.OPEN)
        eng.record_transition("svc-a")
        eng.record_state("svc-b", state=BreakerState.FORCED_OPEN)
        eng.record_transition("svc-b")
        eng.record_transition("svc-b")
        results = eng.rank_by_impact()
        assert len(results) == 2
        # svc-a: open_count=2 * 2 + trans=1 = 5
        # svc-b: open_count=1 * 2 + trans=2 = 4
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["impact_score"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_trip_count_24h=1)
        eng.record_state(
            "svc-a", state=BreakerState.OPEN, error_rate_pct=50.0, recovery_speed=RecoverySpeed.SLOW
        )
        eng.record_transition("svc-a")
        eng.record_transition("svc-a")
        report = eng.generate_report()
        assert report.total_states == 1
        assert report.total_transitions == 2
        assert report.avg_error_rate_pct == 50.0
        assert report.by_state != {}
        assert report.frequently_tripping_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_states == 0
        assert "good" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_state("svc")
        eng.record_transition("svc")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._transitions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_states"] == 0
        assert stats["total_transitions"] == 0
        assert stats["state_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_state("svc-a")
        eng.record_state("svc-b")
        eng.record_transition("svc-a")
        stats = eng.get_stats()
        assert stats["total_states"] == 2
        assert stats["total_transitions"] == 1
        assert stats["unique_services"] == 2
        assert stats["max_trip_count_24h"] == 10
