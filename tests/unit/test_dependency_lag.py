"""Tests for shieldops.topology.dependency_lag — DependencyLagMonitor."""

from __future__ import annotations

from shieldops.topology.dependency_lag import (
    DependencyLagMonitor,
    DependencyLagRecord,
    DependencyLagReport,
    LagBaseline,
    LagCause,
    LagSeverity,
    PropagationDirection,
)


def _engine(**kw) -> DependencyLagMonitor:
    return DependencyLagMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # LagSeverity (5)
    def test_severity_normal(self):
        assert LagSeverity.NORMAL == "normal"

    def test_severity_elevated(self):
        assert LagSeverity.ELEVATED == "elevated"

    def test_severity_degraded(self):
        assert LagSeverity.DEGRADED == "degraded"

    def test_severity_severe(self):
        assert LagSeverity.SEVERE == "severe"

    def test_severity_critical(self):
        assert LagSeverity.CRITICAL == "critical"

    # PropagationDirection (5)
    def test_direction_upstream(self):
        assert PropagationDirection.UPSTREAM == "upstream"

    def test_direction_downstream(self):
        assert PropagationDirection.DOWNSTREAM == "downstream"

    def test_direction_lateral(self):
        assert PropagationDirection.LATERAL == "lateral"

    def test_direction_bidirectional(self):
        assert PropagationDirection.BIDIRECTIONAL == "bidirectional"

    def test_direction_isolated(self):
        assert PropagationDirection.ISOLATED == "isolated"

    # LagCause (5)
    def test_cause_network_congestion(self):
        assert LagCause.NETWORK_CONGESTION == "network_congestion"

    def test_cause_service_overload(self):
        assert LagCause.SERVICE_OVERLOAD == "service_overload"

    def test_cause_database_contention(self):
        assert LagCause.DATABASE_CONTENTION == "database_contention"

    def test_cause_queue_backlog(self):
        assert LagCause.QUEUE_BACKLOG == "queue_backlog"

    def test_cause_external_api(self):
        assert LagCause.EXTERNAL_API == "external_api"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_lag_record_defaults(self):
        r = DependencyLagRecord()
        assert r.id
        assert r.source_service == ""
        assert r.target_service == ""
        assert r.latency_ms == 0.0
        assert r.baseline_ms == 0.0
        assert r.lag_pct == 0.0
        assert r.severity == LagSeverity.NORMAL
        assert r.direction == PropagationDirection.DOWNSTREAM
        assert r.cause == LagCause.NETWORK_CONGESTION
        assert r.created_at > 0

    def test_lag_baseline_defaults(self):
        b = LagBaseline()
        assert b.id
        assert b.source_service == ""
        assert b.target_service == ""
        assert b.baseline_ms == 0.0
        assert b.p50_ms == 0.0
        assert b.p95_ms == 0.0
        assert b.p99_ms == 0.0
        assert b.created_at > 0

    def test_dependency_lag_report_defaults(self):
        r = DependencyLagReport()
        assert r.total_records == 0
        assert r.total_baselines == 0
        assert r.degraded_count == 0
        assert r.by_severity == {}
        assert r.by_cause == {}
        assert r.top_bottlenecks == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_lag
# ---------------------------------------------------------------------------


class TestRecordLag:
    def test_basic(self):
        eng = _engine()
        r = eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=150.0,
            baseline_ms=100.0,
        )
        assert r.source_service == "svc-a"
        assert r.target_service == "svc-b"
        assert r.latency_ms == 150.0
        assert r.baseline_ms == 100.0
        assert r.lag_pct == 50.0
        assert r.severity == LagSeverity.DEGRADED

    def test_with_params(self):
        eng = _engine()
        r = eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=50.0,
            baseline_ms=100.0,
            direction=PropagationDirection.UPSTREAM,
            cause=LagCause.DATABASE_CONTENTION,
        )
        assert r.direction == PropagationDirection.UPSTREAM
        assert r.cause == LagCause.DATABASE_CONTENTION
        # latency < baseline => negative lag, severity NORMAL (max(0, lag_pct) used)
        assert r.severity == LagSeverity.NORMAL

    def test_uses_stored_baseline(self):
        eng = _engine()
        eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        r = eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=200.0,
        )
        assert r.baseline_ms == 100.0
        assert r.lag_pct == 100.0
        assert r.severity == LagSeverity.SEVERE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_lag(
                source_service=f"svc-{i}",
                target_service="svc-target",
                latency_ms=100.0,
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_lag_record
# ---------------------------------------------------------------------------


class TestGetLagRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=100.0,
        )
        result = eng.get_lag_record(r.id)
        assert result is not None
        assert result.source_service == "svc-a"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_lag_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_lag_records
# ---------------------------------------------------------------------------


class TestListLagRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_lag(source_service="svc-a", target_service="svc-b", latency_ms=100.0)
        eng.record_lag(source_service="svc-c", target_service="svc-d", latency_ms=200.0)
        assert len(eng.list_lag_records()) == 2

    def test_filter_by_source_service(self):
        eng = _engine()
        eng.record_lag(source_service="svc-a", target_service="svc-b", latency_ms=100.0)
        eng.record_lag(source_service="svc-c", target_service="svc-d", latency_ms=200.0)
        results = eng.list_lag_records(source_service="svc-a")
        assert len(results) == 1
        assert results[0].source_service == "svc-a"

    def test_filter_by_target_service(self):
        eng = _engine()
        eng.record_lag(source_service="svc-a", target_service="svc-b", latency_ms=100.0)
        eng.record_lag(source_service="svc-c", target_service="svc-d", latency_ms=200.0)
        results = eng.list_lag_records(target_service="svc-d")
        assert len(results) == 1
        assert results[0].target_service == "svc-d"


# ---------------------------------------------------------------------------
# set_baseline
# ---------------------------------------------------------------------------


class TestSetBaseline:
    def test_basic(self):
        eng = _engine()
        b = eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        assert b.source_service == "svc-a"
        assert b.target_service == "svc-b"
        assert b.baseline_ms == 100.0
        assert b.p50_ms == 0.0

    def test_with_percentiles(self):
        eng = _engine()
        b = eng.set_baseline(
            "svc-a",
            "svc-b",
            baseline_ms=100.0,
            p50_ms=95.0,
            p95_ms=180.0,
            p99_ms=350.0,
        )
        assert b.p50_ms == 95.0
        assert b.p95_ms == 180.0
        assert b.p99_ms == 350.0

    def test_stores_in_baselines_dict(self):
        eng = _engine()
        eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        assert "svc-a->svc-b" in eng._baselines


# ---------------------------------------------------------------------------
# detect_degradation
# ---------------------------------------------------------------------------


class TestDetectDegradation:
    def test_degraded(self):
        eng = _engine(degradation_threshold_pct=50.0)
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=200.0,
            baseline_ms=100.0,
        )
        result = eng.detect_degradation("svc-a", "svc-b")
        assert result["degraded"] is True
        assert result["lag_pct"] == 100.0
        assert result["severity"] == "severe"

    def test_not_degraded(self):
        eng = _engine(degradation_threshold_pct=50.0)
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=110.0,
            baseline_ms=100.0,
        )
        result = eng.detect_degradation("svc-a", "svc-b")
        assert result["degraded"] is False
        assert result["lag_pct"] == 10.0

    def test_no_records(self):
        eng = _engine()
        result = eng.detect_degradation("svc-a", "svc-b")
        assert result["degraded"] is False
        assert result["reason"] == "no records"


# ---------------------------------------------------------------------------
# trace_propagation_chain
# ---------------------------------------------------------------------------


class TestTracePropagationChain:
    def test_chain_found(self):
        eng = _engine()
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=200.0,
            baseline_ms=100.0,
        )
        eng.record_lag(
            source_service="svc-b",
            target_service="svc-c",
            latency_ms=300.0,
            baseline_ms=100.0,
        )
        chain = eng.trace_propagation_chain("svc-a")
        assert len(chain) == 2
        assert chain[0]["source"] == "svc-a"
        assert chain[0]["target"] == "svc-b"
        assert chain[1]["source"] == "svc-b"
        assert chain[1]["target"] == "svc-c"

    def test_no_chain(self):
        eng = _engine()
        chain = eng.trace_propagation_chain("svc-a")
        assert chain == []


# ---------------------------------------------------------------------------
# identify_bottleneck_services
# ---------------------------------------------------------------------------


class TestIdentifyBottleneckServices:
    def test_has_bottleneck(self):
        eng = _engine(degradation_threshold_pct=50.0)
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=200.0,
            baseline_ms=100.0,
        )
        eng.record_lag(
            source_service="svc-c",
            target_service="svc-b",
            latency_ms=250.0,
            baseline_ms=100.0,
        )
        results = eng.identify_bottleneck_services()
        assert len(results) == 1
        assert results[0]["service"] == "svc-b"
        assert results[0]["occurrence_count"] == 2

    def test_no_bottleneck(self):
        eng = _engine(degradation_threshold_pct=50.0)
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=110.0,
            baseline_ms=100.0,
        )
        results = eng.identify_bottleneck_services()
        assert results == []


# ---------------------------------------------------------------------------
# compare_to_baseline
# ---------------------------------------------------------------------------


class TestCompareToBaseline:
    def test_has_baseline_and_records(self):
        eng = _engine()
        eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=180.0,
        )
        result = eng.compare_to_baseline("svc-a", "svc-b")
        assert result["has_baseline"] is True
        assert result["baseline_ms"] == 100.0
        assert result["current_ms"] == 180.0
        assert result["deviation_pct"] == 80.0

    def test_no_baseline(self):
        eng = _engine()
        result = eng.compare_to_baseline("svc-a", "svc-b")
        assert result["has_baseline"] is False

    def test_baseline_no_records(self):
        eng = _engine()
        eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        result = eng.compare_to_baseline("svc-a", "svc-b")
        assert result["has_baseline"] is True
        assert result["current_ms"] == 0.0
        assert result["deviation_pct"] == 0.0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=200.0,
            baseline_ms=100.0,
        )
        eng.record_lag(
            source_service="svc-c",
            target_service="svc-d",
            latency_ms=500.0,
            baseline_ms=100.0,
            cause=LagCause.SERVICE_OVERLOAD,
        )
        eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        report = eng.generate_report()
        assert isinstance(report, DependencyLagReport)
        assert report.total_records == 2
        assert report.total_baselines == 1
        assert report.degraded_count >= 1
        assert len(report.by_severity) > 0
        assert len(report.by_cause) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.degraded_count == 0
        assert "All dependency latencies within normal range" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=100.0,
        )
        eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._baselines) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_baselines"] == 0
        assert stats["severity_distribution"] == {}
        assert stats["unique_pairs"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_lag(
            source_service="svc-a",
            target_service="svc-b",
            latency_ms=200.0,
            baseline_ms=100.0,
        )
        eng.set_baseline("svc-a", "svc-b", baseline_ms=100.0)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["total_baselines"] == 1
        assert stats["degradation_threshold_pct"] == 50.0
        assert stats["unique_pairs"] == 1
        assert len(stats["severity_distribution"]) > 0
