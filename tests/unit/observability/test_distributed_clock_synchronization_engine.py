"""Tests for DistributedClockSynchronizationEngine."""

from __future__ import annotations

from shieldops.observability.distributed_clock_synchronization_engine import (
    ClockSource,
    ClockSyncAnalysis,
    ClockSyncRecord,
    ClockSyncReport,
    DistributedClockSynchronizationEngine,
    DriftSeverity,
    SyncStatus,
)


def test_add_record() -> None:
    engine = DistributedClockSynchronizationEngine()
    rec = engine.add_record(
        node_id="node-1",
        service_name="svc-a",
        clock_source=ClockSource.NTP,
        sync_status=SyncStatus.SYNCHRONIZED,
        drift_severity=DriftSeverity.LOW,
        drift_ms=0.5,
        offset_ms=0.1,
        jitter_ms=0.2,
        last_sync_ago_s=30.0,
    )
    assert isinstance(rec, ClockSyncRecord)
    assert rec.node_id == "node-1"
    assert rec.drift_ms == 0.5


def test_process() -> None:
    engine = DistributedClockSynchronizationEngine()
    rec = engine.add_record(
        node_id="node-2",
        service_name="svc-b",
        sync_status=SyncStatus.DRIFTING,
        drift_severity=DriftSeverity.HIGH,
        drift_ms=50.0,
        jitter_ms=5.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, ClockSyncAnalysis)
    assert result.node_id == "node-2"
    assert result.drift_detected is True
    assert result.sync_score < 100.0


def test_process_not_found() -> None:
    engine = DistributedClockSynchronizationEngine()
    result = engine.process("ghost-node")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = DistributedClockSynchronizationEngine()
    for node, src, status, sev, drift in [
        ("n1", ClockSource.NTP, SyncStatus.SYNCHRONIZED, DriftSeverity.LOW, 0.1),
        ("n2", ClockSource.PTP, SyncStatus.DRIFTING, DriftSeverity.HIGH, 30.0),
        ("n3", ClockSource.SYSTEM, SyncStatus.UNSYNCHRONIZED, DriftSeverity.CRITICAL, 200.0),
        ("n4", ClockSource.HYBRID, SyncStatus.UNKNOWN, DriftSeverity.MEDIUM, 5.0),
    ]:
        engine.add_record(
            node_id=node,
            clock_source=src,
            sync_status=status,
            drift_severity=sev,
            drift_ms=drift,
        )
    report = engine.generate_report()
    assert isinstance(report, ClockSyncReport)
    assert report.total_records == 4
    assert "ntp" in report.by_clock_source


def test_get_stats() -> None:
    engine = DistributedClockSynchronizationEngine()
    engine.add_record(sync_status=SyncStatus.SYNCHRONIZED, drift_ms=0.1)
    engine.add_record(sync_status=SyncStatus.DRIFTING, drift_ms=10.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "sync_status_distribution" in stats


def test_clear_data() -> None:
    engine = DistributedClockSynchronizationEngine()
    engine.add_record(node_id="n-x", drift_ms=1.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_evaluate_clock_synchronization() -> None:
    engine = DistributedClockSynchronizationEngine()
    engine.add_record(node_id="n1", drift_ms=0.5, jitter_ms=0.1, offset_ms=0.05)
    engine.add_record(node_id="n1", drift_ms=1.0, jitter_ms=0.2, offset_ms=0.1)
    engine.add_record(node_id="n2", drift_ms=100.0, jitter_ms=20.0, offset_ms=50.0)
    results = engine.evaluate_clock_synchronization()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "avg_drift_ms" in results[0]
    assert results[0]["avg_drift_ms"] >= results[-1]["avg_drift_ms"]


def test_detect_clock_drift() -> None:
    engine = DistributedClockSynchronizationEngine()
    engine.add_record(
        node_id="n1",
        sync_status=SyncStatus.DRIFTING,
        drift_ms=30.0,
        drift_severity=DriftSeverity.HIGH,
    )
    engine.add_record(
        node_id="n2",
        sync_status=SyncStatus.SYNCHRONIZED,
        drift_ms=0.1,
        drift_severity=DriftSeverity.LOW,
    )
    engine.add_record(
        node_id="n3",
        sync_status=SyncStatus.UNSYNCHRONIZED,
        drift_ms=200.0,
        drift_severity=DriftSeverity.CRITICAL,
    )
    results = engine.detect_clock_drift()
    assert isinstance(results, list)
    assert all(r["sync_status"] in ("drifting", "unsynchronized") for r in results)


def test_rank_nodes_by_drift_severity() -> None:
    engine = DistributedClockSynchronizationEngine()
    engine.add_record(
        node_id="n1", drift_severity=DriftSeverity.CRITICAL, drift_ms=200.0, service_name="svc-a"
    )
    engine.add_record(
        node_id="n2", drift_severity=DriftSeverity.LOW, drift_ms=0.1, service_name="svc-b"
    )
    engine.add_record(
        node_id="n3", drift_severity=DriftSeverity.HIGH, drift_ms=50.0, service_name="svc-c"
    )
    results = engine.rank_nodes_by_drift_severity()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["drift_severity_score"] >= results[-1]["drift_severity_score"]
