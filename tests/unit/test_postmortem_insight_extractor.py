"""Tests for PostmortemInsightExtractor."""

import pytest

from shieldops.incidents.postmortem_insight_extractor import (
    InsightPriority,
    InsightType,
    PostmortemInsightAnalysis,
    PostmortemInsightExtractor,
    PostmortemInsightRecord,
    PostmortemInsightReport,
    ThemeCategory,
)


@pytest.fixture
def engine():
    return PostmortemInsightExtractor(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, PostmortemInsightRecord)
    assert rec.insight_type == InsightType.ROOT_CAUSE


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        insight_type=InsightType.PREVENTION,
        theme_category=ThemeCategory.CODE,
        insight_priority=InsightPriority.CRITICAL,
        prevention_score=0.95,
        insight_text="Add circuit breaker",
    )
    assert rec.incident_id == "inc-1"
    assert rec.prevention_score == 0.95


def test_add_record_ring_buffer():
    engine = PostmortemInsightExtractor(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(incident_id="inc-1", prevention_score=0.8)
    result = engine.process(rec.id)
    assert isinstance(result, PostmortemInsightAnalysis)
    assert result.prevention_value == 0.8


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, PostmortemInsightReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(insight_type=InsightType.ROOT_CAUSE, prevention_score=0.7)
    engine.add_record(insight_type=InsightType.ACTION_ITEM, prevention_score=0.9)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_prevention_score == 0.8


def test_get_stats(engine):
    engine.add_record(insight_type=InsightType.CONTRIBUTING_FACTOR)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "contributing_factor" in stats["insight_type_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_extract_actionable_insights(engine):
    engine.add_record(
        insight_type=InsightType.ROOT_CAUSE, prevention_score=0.8, insight_text="DB timeout"
    )
    engine.add_record(
        insight_type=InsightType.ROOT_CAUSE, prevention_score=0.6, insight_text="Memory leak"
    )
    engine.add_record(
        insight_type=InsightType.ACTION_ITEM, prevention_score=0.9, insight_text="Add alerts"
    )
    result = engine.extract_actionable_insights()
    assert len(result) == 2


def test_extract_actionable_insights_empty(engine):
    assert engine.extract_actionable_insights() == []


def test_detect_recurring_themes(engine):
    engine.add_record(incident_id="inc-1", theme_category=ThemeCategory.INFRASTRUCTURE)
    engine.add_record(incident_id="inc-2", theme_category=ThemeCategory.INFRASTRUCTURE)
    engine.add_record(incident_id="inc-3", theme_category=ThemeCategory.CODE)
    result = engine.detect_recurring_themes()
    assert len(result) == 1
    assert result[0]["theme"] == "infrastructure"


def test_detect_recurring_themes_empty(engine):
    assert engine.detect_recurring_themes() == []


def test_rank_insights_by_prevention_value(engine):
    engine.add_record(incident_id="inc-1", prevention_score=0.9)
    engine.add_record(incident_id="inc-2", prevention_score=0.5)
    result = engine.rank_insights_by_prevention_value()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["prevention_score"] >= result[1]["prevention_score"]


def test_rank_insights_by_prevention_value_empty(engine):
    assert engine.rank_insights_by_prevention_value() == []


def test_enum_values():
    assert InsightType.PREVENTION == "prevention"
    assert ThemeCategory.HUMAN == "human"
    assert InsightPriority.CRITICAL == "critical"
