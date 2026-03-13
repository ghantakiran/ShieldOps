"""Tests for RecoveryRunbookEffectivenessEngine."""

import pytest

from shieldops.operations.recovery_runbook_effectiveness_engine import (
    EffectivenessLevel,
    RecoveryRunbookEffectivenessEngine,
    RunbookEffectivenessAnalysis,
    RunbookEffectivenessRecord,
    RunbookEffectivenessReport,
    RunbookOutcome,
    RunbookType,
)


@pytest.fixture
def engine():
    return RecoveryRunbookEffectivenessEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_record_item_defaults(engine):
    rec = engine.record_item()
    assert isinstance(rec, RunbookEffectivenessRecord)
    assert rec.runbook_outcome == RunbookOutcome.SUCCESS


def test_record_item_custom(engine):
    rec = engine.record_item(
        name="restart-service",
        runbook_id="rb-1",
        runbook_outcome=RunbookOutcome.FAILURE,
        runbook_type=RunbookType.MANUAL,
        effectiveness_level=EffectivenessLevel.POOR,
        recovery_time_seconds=300,
        score=0.3,
    )
    assert rec.runbook_id == "rb-1"
    assert rec.score == 0.3


def test_record_item_ring_buffer():
    engine = RecoveryRunbookEffectivenessEngine(max_records=3)
    for i in range(5):
        engine.record_item(name=f"rb-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.record_item(runbook_id="rb-1")
    result = engine.process(rec.id)
    assert isinstance(result, RunbookEffectivenessAnalysis)
    assert result.runbook_id == "rb-1"


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, RunbookEffectivenessReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.record_item(runbook_outcome=RunbookOutcome.SUCCESS, score=80)
    engine.record_item(runbook_outcome=RunbookOutcome.FAILURE, score=20)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_score == 50.0


def test_get_stats(engine):
    engine.record_item(runbook_outcome=RunbookOutcome.PARTIAL)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "partial" in stats["outcome_distribution"]


def test_clear_data(engine):
    engine.record_item()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_runbook_success_rate(engine):
    engine.record_item(runbook_id="rb-1", runbook_outcome=RunbookOutcome.SUCCESS)
    engine.record_item(runbook_id="rb-1", runbook_outcome=RunbookOutcome.SUCCESS)
    engine.record_item(runbook_id="rb-1", runbook_outcome=RunbookOutcome.FAILURE)
    result = engine.compute_runbook_success_rate()
    assert len(result) == 1
    assert result[0]["success_rate"] == 0.67


def test_compute_runbook_success_rate_empty(engine):
    assert engine.compute_runbook_success_rate() == []


def test_detect_runbook_gaps(engine):
    engine.record_item(runbook_id="rb-1", runbook_outcome=RunbookOutcome.FAILURE)
    engine.record_item(runbook_id="rb-1", runbook_outcome=RunbookOutcome.FAILURE)
    engine.record_item(runbook_id="rb-1", runbook_outcome=RunbookOutcome.SUCCESS)
    result = engine.detect_runbook_gaps()
    assert len(result) == 1
    assert result[0]["failure_rate"] == 0.67


def test_detect_runbook_gaps_empty(engine):
    assert engine.detect_runbook_gaps() == []


def test_rank_runbooks_by_recovery_impact(engine):
    engine.record_item(
        runbook_id="rb-1",
        score=90,
        runbook_outcome=RunbookOutcome.SUCCESS,
        recovery_time_seconds=30,
    )
    engine.record_item(
        runbook_id="rb-2",
        score=50,
        runbook_outcome=RunbookOutcome.FAILURE,
        recovery_time_seconds=120,
    )
    result = engine.rank_runbooks_by_recovery_impact()
    assert len(result) == 2
    assert result[0]["rank"] == 1


def test_rank_runbooks_by_recovery_impact_empty(engine):
    assert engine.rank_runbooks_by_recovery_impact() == []


def test_enum_values():
    assert RunbookOutcome.SKIPPED == "skipped"
    assert RunbookType.HYBRID == "hybrid"
    assert EffectivenessLevel.EXCELLENT == "excellent"
