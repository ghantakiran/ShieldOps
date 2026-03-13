"""Tests for IncidentCostAttributionEngine."""

import pytest

from shieldops.incidents.incident_cost_attribution_engine import (
    CostCategory,
    CostPeriod,
    CostSeverity,
    IncidentCostAnalysis,
    IncidentCostAttributionEngine,
    IncidentCostRecord,
    IncidentCostReport,
)


@pytest.fixture
def engine():
    return IncidentCostAttributionEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, IncidentCostRecord)
    assert rec.cost_category == CostCategory.ENGINEERING_TIME


def test_add_record_custom(engine):
    rec = engine.add_record(
        incident_id="inc-1",
        cost_category=CostCategory.REVENUE_LOSS,
        cost_period=CostPeriod.HOURLY,
        cost_severity=CostSeverity.CRITICAL,
        cost_amount=50000.0,
        service="payments",
    )
    assert rec.incident_id == "inc-1"
    assert rec.cost_amount == 50000.0


def test_add_record_ring_buffer():
    engine = IncidentCostAttributionEngine(max_records=3)
    for i in range(5):
        engine.add_record(incident_id=f"inc-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(incident_id="inc-1", cost_amount=5000, cost_severity=CostSeverity.LOW)
    result = engine.process(rec.id)
    assert isinstance(result, IncidentCostAnalysis)
    assert result.total_cost == 5000.0


def test_process_high_cost(engine):
    rec = engine.add_record(
        incident_id="inc-1", cost_amount=15000, cost_severity=CostSeverity.CRITICAL
    )
    result = engine.process(rec.id)
    assert result.is_high_cost is True


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, IncidentCostReport)
    assert report.total_records == 0
    assert report.total_cost == 0.0


def test_generate_report_with_data(engine):
    engine.add_record(cost_category=CostCategory.ENGINEERING_TIME, cost_amount=1000)
    engine.add_record(cost_category=CostCategory.REVENUE_LOSS, cost_amount=5000)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.total_cost == 6000.0


def test_get_stats(engine):
    engine.add_record(cost_category=CostCategory.SLA_PENALTY)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "sla_penalty" in stats["category_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_incident_cost_breakdown(engine):
    engine.add_record(
        incident_id="inc-1", cost_category=CostCategory.ENGINEERING_TIME, cost_amount=1000
    )
    engine.add_record(
        incident_id="inc-1", cost_category=CostCategory.REVENUE_LOSS, cost_amount=5000
    )
    result = engine.compute_incident_cost_breakdown()
    assert len(result) == 1
    assert result[0]["total_cost"] == 6000.0
    assert "engineering_time" in result[0]["breakdown"]


def test_compute_incident_cost_breakdown_empty(engine):
    assert engine.compute_incident_cost_breakdown() == []


def test_detect_high_cost_patterns(engine):
    engine.add_record(service="api", cost_amount=10000)
    engine.add_record(service="web", cost_amount=1000)
    result = engine.detect_high_cost_patterns()
    assert len(result) >= 1
    assert result[0]["service"] == "api"


def test_detect_high_cost_patterns_empty(engine):
    assert engine.detect_high_cost_patterns() == []


def test_rank_incidents_by_total_cost(engine):
    engine.add_record(incident_id="inc-1", cost_amount=10000)
    engine.add_record(incident_id="inc-2", cost_amount=500)
    result = engine.rank_incidents_by_total_cost()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["total_cost"] >= result[1]["total_cost"]


def test_rank_incidents_by_total_cost_empty(engine):
    assert engine.rank_incidents_by_total_cost() == []


def test_enum_values():
    assert CostCategory.INFRASTRUCTURE == "infrastructure"
    assert CostPeriod.MONTHLY == "monthly"
    assert CostSeverity.LOW == "low"
