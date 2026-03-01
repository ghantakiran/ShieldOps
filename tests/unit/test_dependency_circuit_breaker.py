"""Tests for shieldops.topology.dependency_circuit_breaker — DependencyCircuitBreakerMonitor."""

from __future__ import annotations

from shieldops.topology.dependency_circuit_breaker import (
    CircuitBreakerRecord,
    CircuitEvent,
    CircuitState,
    DependencyCircuitBreakerMonitor,
    DependencyCircuitBreakerReport,
    RecoveryStrategy,
    TripReason,
)


def _engine(**kw) -> DependencyCircuitBreakerMonitor:
    return DependencyCircuitBreakerMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_state_closed(self):
        assert CircuitState.CLOSED == "closed"

    def test_state_half_open(self):
        assert CircuitState.HALF_OPEN == "half_open"

    def test_state_open(self):
        assert CircuitState.OPEN == "open"

    def test_state_forced_open(self):
        assert CircuitState.FORCED_OPEN == "forced_open"

    def test_state_disabled(self):
        assert CircuitState.DISABLED == "disabled"

    def test_reason_timeout(self):
        assert TripReason.TIMEOUT == "timeout"

    def test_reason_error_rate(self):
        assert TripReason.ERROR_RATE == "error_rate"

    def test_reason_latency(self):
        assert TripReason.LATENCY == "latency"

    def test_reason_resource_exhaustion(self):
        assert TripReason.RESOURCE_EXHAUSTION == "resource_exhaustion"

    def test_reason_manual(self):
        assert TripReason.MANUAL == "manual"

    def test_strategy_automatic(self):
        assert RecoveryStrategy.AUTOMATIC == "automatic"

    def test_strategy_gradual(self):
        assert RecoveryStrategy.GRADUAL == "gradual"

    def test_strategy_manual(self):
        assert RecoveryStrategy.MANUAL == "manual"

    def test_strategy_fallback(self):
        assert RecoveryStrategy.FALLBACK == "fallback"

    def test_strategy_retry(self):
        assert RecoveryStrategy.RETRY == "retry"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_circuit_breaker_record_defaults(self):
        r = CircuitBreakerRecord()
        assert r.id
        assert r.circuit_id == ""
        assert r.circuit_state == CircuitState.CLOSED
        assert r.trip_reason == TripReason.TIMEOUT
        assert r.recovery_strategy == RecoveryStrategy.AUTOMATIC
        assert r.trip_count == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_circuit_event_defaults(self):
        m = CircuitEvent()
        assert m.id
        assert m.circuit_id == ""
        assert m.circuit_state == CircuitState.CLOSED
        assert m.event_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_dependency_circuit_breaker_report_defaults(self):
        r = DependencyCircuitBreakerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_events == 0
        assert r.open_circuits == 0
        assert r.avg_trip_count == 0.0
        assert r.by_state == {}
        assert r.by_reason == {}
        assert r.by_strategy == {}
        assert r.top_tripping == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_circuit
# ---------------------------------------------------------------------------


class TestRecordCircuit:
    def test_basic(self):
        eng = _engine()
        r = eng.record_circuit(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
            trip_reason=TripReason.ERROR_RATE,
            recovery_strategy=RecoveryStrategy.GRADUAL,
            trip_count=15.0,
            service="api-gateway",
            team="sre",
        )
        assert r.circuit_id == "CB-001"
        assert r.circuit_state == CircuitState.OPEN
        assert r.trip_reason == TripReason.ERROR_RATE
        assert r.recovery_strategy == RecoveryStrategy.GRADUAL
        assert r.trip_count == 15.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_circuit(circuit_id=f"CB-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_circuit
# ---------------------------------------------------------------------------


class TestGetCircuit:
    def test_found(self):
        eng = _engine()
        r = eng.record_circuit(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
        )
        result = eng.get_circuit(r.id)
        assert result is not None
        assert result.circuit_state == CircuitState.OPEN

    def test_not_found(self):
        eng = _engine()
        assert eng.get_circuit("nonexistent") is None


# ---------------------------------------------------------------------------
# list_circuits
# ---------------------------------------------------------------------------


class TestListCircuits:
    def test_list_all(self):
        eng = _engine()
        eng.record_circuit(circuit_id="CB-001")
        eng.record_circuit(circuit_id="CB-002")
        assert len(eng.list_circuits()) == 2

    def test_filter_by_state(self):
        eng = _engine()
        eng.record_circuit(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
        )
        eng.record_circuit(
            circuit_id="CB-002",
            circuit_state=CircuitState.CLOSED,
        )
        results = eng.list_circuits(
            state=CircuitState.OPEN,
        )
        assert len(results) == 1

    def test_filter_by_reason(self):
        eng = _engine()
        eng.record_circuit(
            circuit_id="CB-001",
            trip_reason=TripReason.TIMEOUT,
        )
        eng.record_circuit(
            circuit_id="CB-002",
            trip_reason=TripReason.ERROR_RATE,
        )
        results = eng.list_circuits(
            reason=TripReason.TIMEOUT,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_circuit(circuit_id="CB-001", service="api-gateway")
        eng.record_circuit(circuit_id="CB-002", service="auth-svc")
        results = eng.list_circuits(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_circuit(circuit_id="CB-001", team="sre")
        eng.record_circuit(circuit_id="CB-002", team="platform")
        results = eng.list_circuits(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_circuit(circuit_id=f"CB-{i}")
        assert len(eng.list_circuits(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_event
# ---------------------------------------------------------------------------


class TestAddEvent:
    def test_basic(self):
        eng = _engine()
        m = eng.add_event(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
            event_score=85.0,
            threshold=90.0,
            breached=True,
            description="Circuit tripped due to errors",
        )
        assert m.circuit_id == "CB-001"
        assert m.circuit_state == CircuitState.OPEN
        assert m.event_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Circuit tripped due to errors"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_event(circuit_id=f"CB-{i}")
        assert len(eng._events) == 2


# ---------------------------------------------------------------------------
# analyze_circuit_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCircuitDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_circuit(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
            trip_count=10.0,
        )
        eng.record_circuit(
            circuit_id="CB-002",
            circuit_state=CircuitState.OPEN,
            trip_count=20.0,
        )
        result = eng.analyze_circuit_distribution()
        assert "open" in result
        assert result["open"]["count"] == 2
        assert result["open"]["avg_trip_count"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_circuit_distribution() == {}


# ---------------------------------------------------------------------------
# identify_open_circuits
# ---------------------------------------------------------------------------


class TestIdentifyOpenCircuits:
    def test_detects_open(self):
        eng = _engine()
        eng.record_circuit(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
        )
        eng.record_circuit(
            circuit_id="CB-002",
            circuit_state=CircuitState.CLOSED,
        )
        results = eng.identify_open_circuits()
        assert len(results) == 1
        assert results[0]["circuit_id"] == "CB-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_open_circuits() == []


# ---------------------------------------------------------------------------
# rank_by_trip_count
# ---------------------------------------------------------------------------


class TestRankByTripCount:
    def test_ranked(self):
        eng = _engine()
        eng.record_circuit(
            circuit_id="CB-001",
            service="api-gateway",
            trip_count=20.0,
        )
        eng.record_circuit(
            circuit_id="CB-002",
            service="api-gateway",
            trip_count=10.0,
        )
        eng.record_circuit(
            circuit_id="CB-003",
            service="auth-svc",
            trip_count=5.0,
        )
        results = eng.rank_by_trip_count()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["total_trip_count"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_trip_count() == []


# ---------------------------------------------------------------------------
# detect_circuit_trends
# ---------------------------------------------------------------------------


class TestDetectCircuitTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_event(circuit_id="CB-1", event_score=val)
        result = eng.detect_circuit_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [10.0, 10.0, 50.0, 50.0]:
            eng.add_event(circuit_id="CB-1", event_score=val)
        result = eng.detect_circuit_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_circuit_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_circuit(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
            trip_reason=TripReason.ERROR_RATE,
            recovery_strategy=RecoveryStrategy.GRADUAL,
            trip_count=15.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DependencyCircuitBreakerReport)
        assert report.total_records == 1
        assert report.open_circuits == 1
        assert len(report.top_tripping) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_circuit(circuit_id="CB-001")
        eng.add_event(circuit_id="CB-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._events) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_events"] == 0
        assert stats["state_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_circuit(
            circuit_id="CB-001",
            circuit_state=CircuitState.OPEN,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "open" in stats["state_distribution"]
