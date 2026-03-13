"""Tests for MitigationEfficacyTracker."""

import pytest

from shieldops.incidents.mitigation_efficacy_tracker import (
    EfficacyLevel,
    MitigationEfficacyAnalysis,
    MitigationEfficacyRecord,
    MitigationEfficacyReport,
    MitigationEfficacyTracker,
    MitigationResult,
    MitigationType,
)


@pytest.fixture
def engine():
    return MitigationEfficacyTracker(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, MitigationEfficacyRecord)
    assert rec.mitigation_result == MitigationResult.EFFECTIVE


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        mitigation_result=MitigationResult.COUNTERPRODUCTIVE,
        mitigation_type=MitigationType.MANUAL,
        efficacy_level=EfficacyLevel.NONE,
        strategy_name="rollback",
        time_to_mitigate_seconds=600,
        efficacy_score=0.1,
    )
    assert rec.incident_id == "inc-1"
    assert rec.efficacy_score == 0.1


def test_add_record_ring_buffer():
    engine = MitigationEfficacyTracker(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(strategy_name="restart", mitigation_result=MitigationResult.EFFECTIVE)
    result = engine.process(rec.id)
    assert isinstance(result, MitigationEfficacyAnalysis)
    assert result.success_rate == 1.0
    assert result.is_ineffective is False


def test_process_ineffective(engine):
    rec = engine.add_record(mitigation_result=MitigationResult.INEFFECTIVE)
    result = engine.process(rec.id)
    assert result.is_ineffective is True


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, MitigationEfficacyReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(mitigation_result=MitigationResult.EFFECTIVE, efficacy_score=0.9)
    engine.add_record(mitigation_result=MitigationResult.INEFFECTIVE, efficacy_score=0.1)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_efficacy_score == 0.5


def test_get_stats(engine):
    engine.add_record(mitigation_result=MitigationResult.PARTIALLY_EFFECTIVE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "partially_effective" in stats["result_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_mitigation_success_rate(engine):
    engine.add_record(strategy_name="restart", mitigation_result=MitigationResult.EFFECTIVE)
    engine.add_record(strategy_name="restart", mitigation_result=MitigationResult.EFFECTIVE)
    engine.add_record(strategy_name="restart", mitigation_result=MitigationResult.INEFFECTIVE)
    result = engine.compute_mitigation_success_rate()
    assert len(result) == 1
    assert result[0]["success_rate"] == 0.67


def test_compute_mitigation_success_rate_empty(engine):
    assert engine.compute_mitigation_success_rate() == []


def test_detect_ineffective_mitigations(engine):
    engine.add_record(strategy_name="scale-up", mitigation_result=MitigationResult.INEFFECTIVE)
    engine.add_record(strategy_name="scale-up", mitigation_result=MitigationResult.INEFFECTIVE)
    engine.add_record(strategy_name="scale-up", mitigation_result=MitigationResult.EFFECTIVE)
    result = engine.detect_ineffective_mitigations()
    assert len(result) == 1
    assert result[0]["ineffective_rate"] == 0.67


def test_detect_ineffective_mitigations_empty(engine):
    assert engine.detect_ineffective_mitigations() == []


def test_rank_strategies_by_efficacy(engine):
    engine.add_record(strategy_name="restart", efficacy_score=0.9)
    engine.add_record(strategy_name="rollback", efficacy_score=0.4)
    result = engine.rank_strategies_by_efficacy()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["avg_efficacy_score"] >= result[1]["avg_efficacy_score"]


def test_rank_strategies_by_efficacy_empty(engine):
    assert engine.rank_strategies_by_efficacy() == []


def test_enum_values():
    assert MitigationResult.COUNTERPRODUCTIVE == "counterproductive"
    assert MitigationType.ESCALATION == "escalation"
    assert EfficacyLevel.NONE == "none"
