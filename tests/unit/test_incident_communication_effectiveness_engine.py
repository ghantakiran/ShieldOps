"""Tests for IncidentCommunicationEffectivenessEngine."""

import pytest

from shieldops.incidents.incident_communication_effectiveness_engine import (
    CommunicationChannel,
    CommunicationEffectivenessAnalysis,
    CommunicationEffectivenessRecord,
    CommunicationEffectivenessReport,
    CommunicationQuality,
    IncidentCommunicationEffectivenessEngine,
    StakeholderType,
)


@pytest.fixture
def engine():
    return IncidentCommunicationEffectivenessEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, CommunicationEffectivenessRecord)
    assert rec.channel == CommunicationChannel.SLACK


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        channel=CommunicationChannel.PAGERDUTY,
        quality=CommunicationQuality.EXCELLENT,
        stakeholder_type=StakeholderType.CUSTOMER,
        response_time_seconds=30,
        update_count=5,
        comms_score=95.0,
    )
    assert rec.incident_id == "inc-1"
    assert rec.comms_score == 95.0


def test_add_record_ring_buffer():
    engine = IncidentCommunicationEffectivenessEngine(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(incident_id="inc-1", comms_score=80.0)
    result = engine.process(rec.id)
    assert isinstance(result, CommunicationEffectivenessAnalysis)
    assert result.avg_score == 80.0


def test_process_with_gaps(engine):
    rec = engine.add_record(quality=CommunicationQuality.POOR)
    result = engine.process(rec.id)
    assert result.has_gaps is True


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, CommunicationEffectivenessReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(channel=CommunicationChannel.SLACK, comms_score=80)
    engine.add_record(channel=CommunicationChannel.EMAIL, comms_score=60)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_comms_score == 70.0


def test_get_stats(engine):
    engine.add_record(channel=CommunicationChannel.STATUSPAGE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "statuspage" in stats["channel_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_communication_scores(engine):
    engine.add_record(incident_id="inc-1", comms_score=90)
    engine.add_record(incident_id="inc-1", comms_score=70)
    engine.add_record(incident_id="inc-2", comms_score=50)
    result = engine.compute_communication_scores()
    assert len(result) == 2
    assert result[0]["avg_comms_score"] >= result[1]["avg_comms_score"]


def test_compute_communication_scores_empty(engine):
    assert engine.compute_communication_scores() == []


def test_detect_communication_gaps(engine):
    engine.add_record(
        incident_id="inc-1",
        channel=CommunicationChannel.SLACK,
        quality=CommunicationQuality.POOR,
    )
    result = engine.detect_communication_gaps()
    assert len(result) == 1
    assert result[0]["incident_id"] == "inc-1"
    assert len(result[0]["missing_channels"]) > 0


def test_detect_communication_gaps_empty(engine):
    assert engine.detect_communication_gaps() == []


def test_rank_incidents_by_comms_quality(engine):
    engine.add_record(incident_id="inc-1", comms_score=90)
    engine.add_record(incident_id="inc-2", comms_score=40)
    result = engine.rank_incidents_by_comms_quality()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["avg_comms_score"] >= result[1]["avg_comms_score"]


def test_rank_incidents_by_comms_quality_empty(engine):
    assert engine.rank_incidents_by_comms_quality() == []


def test_enum_values():
    assert CommunicationChannel.PAGERDUTY == "pagerduty"
    assert CommunicationQuality.FAIR == "fair"
    assert StakeholderType.EXTERNAL == "external"
