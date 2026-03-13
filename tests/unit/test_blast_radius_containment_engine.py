"""Tests for BlastRadiusContainmentEngine."""

import pytest

from shieldops.incidents.blast_radius_containment_engine import (
    BlastLevel,
    BlastRadiusAnalysis,
    BlastRadiusContainmentEngine,
    BlastRadiusRecord,
    BlastRadiusReport,
    ContainmentStatus,
    ContainmentStrategy,
)


@pytest.fixture
def engine():
    return BlastRadiusContainmentEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, BlastRadiusRecord)
    assert rec.containment_status == ContainmentStatus.UNKNOWN
    assert rec.blast_level == BlastLevel.MEDIUM


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        containment_status=ContainmentStatus.CONTAINED,
        blast_level=BlastLevel.CRITICAL,
        containment_strategy=ContainmentStrategy.TRAFFIC_DIVERT,
        affected_services=5,
    )
    assert rec.incident_id == "inc-1"
    assert rec.affected_services == 5


def test_add_record_ring_buffer():
    engine = BlastRadiusContainmentEngine(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        containment_status=ContainmentStatus.CONTAINED,
    )
    result = engine.process(rec.id)
    assert isinstance(result, BlastRadiusAnalysis)
    assert result.effectiveness_score == 1.0
    assert result.is_expanding is False


def test_process_spreading(engine):
    rec = engine.add_record(containment_status=ContainmentStatus.SPREADING)
    result = engine.process(rec.id)
    assert result.is_expanding is True


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, BlastRadiusReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(containment_status=ContainmentStatus.CONTAINED, affected_services=3)
    engine.add_record(containment_status=ContainmentStatus.SPREADING, affected_services=7)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_affected_services == 5.0


def test_get_stats(engine):
    engine.add_record(containment_status=ContainmentStatus.ISOLATED)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "isolated" in stats["containment_status_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_containment_effectiveness(engine):
    engine.add_record(
        containment_strategy=ContainmentStrategy.NETWORK_ISOLATION,
        containment_status=ContainmentStatus.CONTAINED,
        containment_time_seconds=30,
    )
    engine.add_record(
        containment_strategy=ContainmentStrategy.NETWORK_ISOLATION,
        containment_status=ContainmentStatus.SPREADING,
        containment_time_seconds=60,
    )
    result = engine.compute_containment_effectiveness()
    assert len(result) == 1
    assert result[0]["effectiveness_rate"] == 0.5


def test_compute_containment_effectiveness_empty(engine):
    assert engine.compute_containment_effectiveness() == []


def test_detect_blast_radius_expansion(engine):
    engine.add_record(
        incident_id="inc-1", containment_status=ContainmentStatus.SPREADING, affected_services=10
    )
    engine.add_record(incident_id="inc-2", containment_status=ContainmentStatus.CONTAINED)
    result = engine.detect_blast_radius_expansion()
    assert len(result) == 1
    assert result[0]["incident_id"] == "inc-1"


def test_detect_blast_radius_expansion_empty(engine):
    assert engine.detect_blast_radius_expansion() == []


def test_rank_incidents_by_blast_scope(engine):
    engine.add_record(incident_id="inc-1", affected_services=10)
    engine.add_record(incident_id="inc-2", affected_services=3)
    result = engine.rank_incidents_by_blast_scope()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["max_affected_services"] >= result[1]["max_affected_services"]


def test_enum_values():
    assert ContainmentStatus.CONTAINED == "contained"
    assert BlastLevel.CRITICAL == "critical"
    assert ContainmentStrategy.RATE_LIMIT == "rate_limit"
