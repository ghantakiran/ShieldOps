"""Tests for IncidentRecurrencePatternEngine."""

import pytest

from shieldops.incidents.incident_recurrence_pattern_engine import (
    IncidentRecurrencePatternEngine,
    PatternScope,
    RecurrencePatternAnalysis,
    RecurrencePatternRecord,
    RecurrencePatternReport,
    RecurrenceRisk,
    RecurrenceType,
)


@pytest.fixture
def engine():
    return IncidentRecurrencePatternEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, RecurrencePatternRecord)
    assert rec.recurrence_type == RecurrenceType.SIMILAR


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        recurrence_type=RecurrenceType.EXACT,
        pattern_scope=PatternScope.ORGANIZATION,
        recurrence_risk=RecurrenceRisk.CRITICAL,
        occurrence_count=5,
        pattern_signature="db-timeout-pattern",
    )
    assert rec.incident_id == "inc-1"
    assert rec.occurrence_count == 5


def test_add_record_ring_buffer():
    engine = IncidentRecurrencePatternEngine(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(
        incident_id="inc-1", pattern_signature="sig-1", recurrence_risk=RecurrenceRisk.HIGH
    )
    result = engine.process(rec.id)
    assert isinstance(result, RecurrencePatternAnalysis)
    assert result.is_systemic is True


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, RecurrencePatternReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(recurrence_type=RecurrenceType.EXACT, occurrence_count=3)
    engine.add_record(recurrence_type=RecurrenceType.SIMILAR, occurrence_count=1)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_occurrence_count == 2.0


def test_get_stats(engine):
    engine.add_record(recurrence_type=RecurrenceType.SEASONAL)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "seasonal" in stats["recurrence_type_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_recurrence_frequency(engine):
    engine.add_record(pattern_signature="sig-1", occurrence_count=3, incident_id="inc-1")
    engine.add_record(pattern_signature="sig-1", occurrence_count=2, incident_id="inc-2")
    engine.add_record(pattern_signature="sig-2", occurrence_count=1, incident_id="inc-3")
    result = engine.compute_recurrence_frequency()
    assert len(result) == 2
    assert result[0]["pattern_signature"] == "sig-1"


def test_compute_recurrence_frequency_empty(engine):
    assert engine.compute_recurrence_frequency() == []


def test_detect_systemic_patterns(engine):
    engine.add_record(pattern_scope=PatternScope.SERVICE, service="api", team="sre")
    engine.add_record(pattern_scope=PatternScope.SERVICE, service="web", team="platform")
    result = engine.detect_systemic_patterns()
    assert len(result) == 1
    assert result[0]["scope"] == "service"


def test_detect_systemic_patterns_empty(engine):
    assert engine.detect_systemic_patterns() == []


def test_rank_recurrence_clusters(engine):
    engine.add_record(pattern_signature="sig-1", occurrence_count=5)
    engine.add_record(pattern_signature="sig-2", occurrence_count=2)
    result = engine.rank_recurrence_clusters()
    assert len(result) == 2
    assert result[0]["rank"] == 1


def test_rank_recurrence_clusters_empty(engine):
    assert engine.rank_recurrence_clusters() == []


def test_enum_values():
    assert RecurrenceType.SEASONAL == "seasonal"
    assert PatternScope.INFRASTRUCTURE == "infrastructure"
    assert RecurrenceRisk.LOW == "low"
