"""Tests for IncidentLifecycleStateEngine."""

import pytest

from shieldops.incidents.incident_lifecycle_state_engine import (
    IncidentLifecycleStateEngine,
    IncidentPhase,
    LifecycleStateAnalysis,
    LifecycleStateRecord,
    LifecycleStateReport,
    Severity,
    TrackingMode,
)


@pytest.fixture
def engine():
    return IncidentLifecycleStateEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, LifecycleStateRecord)
    assert rec.phase == IncidentPhase.DETECTED
    assert rec.severity == Severity.MEDIUM


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        phase=IncidentPhase.RESOLVED,
        severity=Severity.CRITICAL,
        tracking_mode=TrackingMode.BATCH,
        dwell_time_seconds=120.0,
        service="api",
        team="sre",
    )
    assert rec.incident_id == "inc-1"
    assert rec.phase == IncidentPhase.RESOLVED
    assert rec.severity == Severity.CRITICAL
    assert rec.dwell_time_seconds == 120.0


def test_add_record_ring_buffer():
    engine = IncidentLifecycleStateEngine(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3
    assert engine._records[0].incident_id == "inc-2"


def test_process_found(engine):
    rec = engine.add_record(incident_id="inc-1", dwell_time_seconds=100.0)
    result = engine.process(rec.id)
    assert isinstance(result, LifecycleStateAnalysis)
    assert result.incident_id == "inc-1"
    assert rec.id in engine._analyses


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, LifecycleStateReport)
    assert report.total_records == 0
    assert report.avg_dwell_time == 0.0


def test_generate_report_with_data(engine):
    engine.add_record(phase=IncidentPhase.DETECTED, severity=Severity.HIGH, dwell_time_seconds=60)
    engine.add_record(phase=IncidentPhase.TRIAGED, severity=Severity.LOW, dwell_time_seconds=120)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_dwell_time == 90.0
    assert "detected" in report.by_phase
    assert "triaged" in report.by_phase


def test_get_stats(engine):
    engine.add_record(phase=IncidentPhase.MITIGATED)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "mitigated" in stats["phase_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []
    assert engine._analyses == {}


def test_compute_phase_dwell_times(engine):
    engine.add_record(phase=IncidentPhase.DETECTED, dwell_time_seconds=60)
    engine.add_record(phase=IncidentPhase.DETECTED, dwell_time_seconds=120)
    engine.add_record(phase=IncidentPhase.TRIAGED, dwell_time_seconds=30)
    result = engine.compute_phase_dwell_times()
    assert len(result) == 2
    assert result[0]["avg_dwell_seconds"] >= result[1]["avg_dwell_seconds"]


def test_compute_phase_dwell_times_empty(engine):
    result = engine.compute_phase_dwell_times()
    assert result == []


def test_detect_lifecycle_bottlenecks(engine):
    engine.add_record(phase=IncidentPhase.DETECTED, dwell_time_seconds=10)
    engine.add_record(phase=IncidentPhase.TRIAGED, dwell_time_seconds=500)
    result = engine.detect_lifecycle_bottlenecks()
    assert len(result) >= 1
    assert result[0]["phase"] == "triaged"


def test_detect_lifecycle_bottlenecks_empty(engine):
    result = engine.detect_lifecycle_bottlenecks()
    assert result == []


def test_rank_incidents_by_resolution_velocity(engine):
    engine.add_record(incident_id="inc-1", dwell_time_seconds=60)
    engine.add_record(incident_id="inc-2", dwell_time_seconds=120)
    result = engine.rank_incidents_by_resolution_velocity()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["resolution_velocity"] >= result[1]["resolution_velocity"]


def test_rank_incidents_by_resolution_velocity_empty(engine):
    result = engine.rank_incidents_by_resolution_velocity()
    assert result == []


def test_enum_values():
    assert IncidentPhase.CLOSED == "closed"
    assert Severity.CRITICAL == "critical"
    assert TrackingMode.SNAPSHOT == "snapshot"
