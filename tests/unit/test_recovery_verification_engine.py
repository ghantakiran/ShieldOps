"""Tests for RecoveryVerificationEngine."""

import pytest

from shieldops.incidents.recovery_verification_engine import (
    RecoveryScope,
    RecoveryStatus,
    RecoveryVerificationAnalysis,
    RecoveryVerificationEngine,
    RecoveryVerificationRecord,
    RecoveryVerificationReport,
    VerificationMethod,
)


@pytest.fixture
def engine():
    return RecoveryVerificationEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, RecoveryVerificationRecord)
    assert rec.recovery_status == RecoveryStatus.PENDING
    assert rec.verification_method == VerificationMethod.HEALTH_CHECK


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        recovery_status=RecoveryStatus.COMPLETE,
        verification_method=VerificationMethod.SLI_COMPARISON,
        recovery_scope=RecoveryScope.FULL,
        completeness_pct=100.0,
        service="api",
    )
    assert rec.incident_id == "inc-1"
    assert rec.completeness_pct == 100.0


def test_add_record_ring_buffer():
    engine = RecoveryVerificationEngine(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(incident_id="inc-1", completeness_pct=85.0)
    result = engine.process(rec.id)
    assert isinstance(result, RecoveryVerificationAnalysis)
    assert result.incident_id == "inc-1"


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, RecoveryVerificationReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(recovery_status=RecoveryStatus.COMPLETE, completeness_pct=100)
    engine.add_record(recovery_status=RecoveryStatus.PARTIAL, completeness_pct=60)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_completeness == 80.0


def test_get_stats(engine):
    engine.add_record(recovery_status=RecoveryStatus.FAILED)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "failed" in stats["status_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_verify_recovery_completeness(engine):
    engine.add_record(
        incident_id="inc-1", recovery_status=RecoveryStatus.COMPLETE, completeness_pct=100
    )
    engine.add_record(
        incident_id="inc-1", recovery_status=RecoveryStatus.COMPLETE, completeness_pct=95
    )
    result = engine.verify_recovery_completeness()
    assert len(result) == 1
    assert result[0]["incident_id"] == "inc-1"


def test_verify_recovery_completeness_empty(engine):
    assert engine.verify_recovery_completeness() == []


def test_detect_partial_recoveries(engine):
    engine.add_record(
        incident_id="inc-1", recovery_status=RecoveryStatus.PARTIAL, completeness_pct=50
    )
    engine.add_record(
        incident_id="inc-2", recovery_status=RecoveryStatus.COMPLETE, completeness_pct=100
    )
    result = engine.detect_partial_recoveries()
    assert len(result) == 1
    assert result[0]["incident_id"] == "inc-1"


def test_detect_partial_recoveries_empty(engine):
    assert engine.detect_partial_recoveries() == []


def test_rank_recoveries_by_effectiveness(engine):
    engine.add_record(incident_id="inc-1", completeness_pct=90)
    engine.add_record(incident_id="inc-2", completeness_pct=50)
    result = engine.rank_recoveries_by_effectiveness()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["avg_effectiveness"] >= result[1]["avg_effectiveness"]


def test_rank_recoveries_by_effectiveness_empty(engine):
    assert engine.rank_recoveries_by_effectiveness() == []


def test_enum_values():
    assert RecoveryStatus.COMPLETE == "complete"
    assert VerificationMethod.SYNTHETIC == "synthetic"
    assert RecoveryScope.DEGRADED == "degraded"
