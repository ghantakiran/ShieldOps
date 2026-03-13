"""Tests for CascadeFailureAnalyzer."""

import pytest

from shieldops.incidents.cascade_failure_analyzer import (
    CascadeFailureAnalysis,
    CascadeFailureAnalyzer,
    CascadeFailureRecord,
    CascadeFailureReport,
    CascadePhase,
    CascadeScope,
    FailureType,
)


@pytest.fixture
def engine():
    return CascadeFailureAnalyzer(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, CascadeFailureRecord)
    assert rec.cascade_phase == CascadePhase.TRIGGER


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        cascade_phase=CascadePhase.AMPLIFICATION,
        failure_type=FailureType.OVERLOAD,
        cascade_scope=CascadeScope.REGION,
        cascade_depth=5,
        propagation_time_seconds=10.0,
        trigger_service="db",
        affected_services=8,
    )
    assert rec.incident_id == "inc-1"
    assert rec.cascade_depth == 5


def test_add_record_ring_buffer():
    engine = CascadeFailureAnalyzer(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        cascade_depth=3,
        propagation_time_seconds=10,
        affected_services=5,
    )
    result = engine.process(rec.id)
    assert isinstance(result, CascadeFailureAnalysis)
    assert result.max_depth == 3
    assert result.propagation_speed == 0.5


def test_process_trigger(engine):
    rec = engine.add_record(cascade_phase=CascadePhase.TRIGGER)
    result = engine.process(rec.id)
    assert result.is_trigger is True


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, CascadeFailureReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(cascade_phase=CascadePhase.TRIGGER, cascade_depth=2)
    engine.add_record(cascade_phase=CascadePhase.PROPAGATION, cascade_depth=4)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_cascade_depth == 3.0


def test_get_stats(engine):
    engine.add_record(cascade_phase=CascadePhase.STABILIZATION)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "stabilization" in stats["phase_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_cascade_depth(engine):
    engine.add_record(incident_id="inc-1", cascade_depth=3)
    engine.add_record(incident_id="inc-1", cascade_depth=5)
    engine.add_record(incident_id="inc-2", cascade_depth=1)
    result = engine.compute_cascade_depth()
    assert len(result) == 2
    assert result[0]["max_depth"] == 5


def test_compute_cascade_depth_empty(engine):
    assert engine.compute_cascade_depth() == []


def test_detect_cascade_trigger_services(engine):
    engine.add_record(cascade_phase=CascadePhase.TRIGGER, trigger_service="db", affected_services=5)
    engine.add_record(cascade_phase=CascadePhase.TRIGGER, trigger_service="db", affected_services=3)
    engine.add_record(cascade_phase=CascadePhase.PROPAGATION, trigger_service="api")
    result = engine.detect_cascade_trigger_services()
    assert len(result) == 1
    assert result[0]["trigger_service"] == "db"
    assert result[0]["trigger_count"] == 2


def test_detect_cascade_trigger_services_empty(engine):
    assert engine.detect_cascade_trigger_services() == []


def test_rank_cascades_by_propagation_speed(engine):
    engine.add_record(incident_id="inc-1", affected_services=10, propagation_time_seconds=5)
    engine.add_record(incident_id="inc-2", affected_services=2, propagation_time_seconds=10)
    result = engine.rank_cascades_by_propagation_speed()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["propagation_speed"] >= result[1]["propagation_speed"]


def test_rank_cascades_by_propagation_speed_empty(engine):
    assert engine.rank_cascades_by_propagation_speed() == []


def test_enum_values():
    assert CascadePhase.AMPLIFICATION == "amplification"
    assert FailureType.DATA_CORRUPTION == "data_corruption"
    assert CascadeScope.GLOBAL == "global"
