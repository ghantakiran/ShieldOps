"""Tests for shieldops.incidents.incident_cost — IncidentCostCalculator."""

from __future__ import annotations

from shieldops.incidents.incident_cost import (
    CostBreakdown,
    CostComponent,
    CostSeverity,
    CostTrend,
    IncidentCostCalculator,
    IncidentCostRecord,
    IncidentCostReport,
)


def _engine(**kw) -> IncidentCostCalculator:
    return IncidentCostCalculator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CostComponent (5)
    def test_component_downtime_revenue(self):
        assert CostComponent.DOWNTIME_REVENUE == "downtime_revenue"

    def test_component_engineering_hours(self):
        assert CostComponent.ENGINEERING_HOURS == "engineering_hours"

    def test_component_customer_impact(self):
        assert CostComponent.CUSTOMER_IMPACT == "customer_impact"

    def test_component_sla_penalty(self):
        assert CostComponent.SLA_PENALTY == "sla_penalty"

    def test_component_remediation(self):
        assert CostComponent.REMEDIATION == "remediation"

    # CostSeverity (5)
    def test_severity_catastrophic(self):
        assert CostSeverity.CATASTROPHIC == "catastrophic"

    def test_severity_major(self):
        assert CostSeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert CostSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert CostSeverity.MINOR == "minor"

    def test_severity_negligible(self):
        assert CostSeverity.NEGLIGIBLE == "negligible"

    # CostTrend (5)
    def test_trend_increasing(self):
        assert CostTrend.INCREASING == "increasing"

    def test_trend_stable(self):
        assert CostTrend.STABLE == "stable"

    def test_trend_decreasing(self):
        assert CostTrend.DECREASING == "decreasing"

    def test_trend_volatile(self):
        assert CostTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert CostTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_cost_record_defaults(self):
        r = IncidentCostRecord()
        assert r.id
        assert r.service_name == ""
        assert r.component == CostComponent.DOWNTIME_REVENUE
        assert r.severity == CostSeverity.MODERATE
        assert r.total_cost == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_cost_breakdown_defaults(self):
        r = CostBreakdown()
        assert r.id
        assert r.breakdown_name == ""
        assert r.component == CostComponent.DOWNTIME_REVENUE
        assert r.severity == CostSeverity.MODERATE
        assert r.amount == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_cost_report_defaults(self):
        r = IncidentCostReport()
        assert r.total_costs == 0
        assert r.total_breakdowns == 0
        assert r.avg_cost == 0.0
        assert r.by_component == {}
        assert r.by_severity == {}
        assert r.high_cost_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_cost
# -------------------------------------------------------------------


class TestRecordCost:
    def test_basic(self):
        eng = _engine()
        r = eng.record_cost(
            "svc-a",
            component=CostComponent.DOWNTIME_REVENUE,
            severity=CostSeverity.MAJOR,
        )
        assert r.service_name == "svc-a"
        assert r.component == CostComponent.DOWNTIME_REVENUE

    def test_with_total_cost(self):
        eng = _engine()
        r = eng.record_cost("svc-b", total_cost=15000.0)
        assert r.total_cost == 15000.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_cost(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_cost
# -------------------------------------------------------------------


class TestGetCost:
    def test_found(self):
        eng = _engine()
        r = eng.record_cost("svc-a")
        assert eng.get_cost(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_cost("nonexistent") is None


# -------------------------------------------------------------------
# list_costs
# -------------------------------------------------------------------


class TestListCosts:
    def test_list_all(self):
        eng = _engine()
        eng.record_cost("svc-a")
        eng.record_cost("svc-b")
        assert len(eng.list_costs()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_cost("svc-a")
        eng.record_cost("svc-b")
        results = eng.list_costs(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_component(self):
        eng = _engine()
        eng.record_cost("svc-a", component=CostComponent.SLA_PENALTY)
        eng.record_cost("svc-b", component=CostComponent.DOWNTIME_REVENUE)
        results = eng.list_costs(component=CostComponent.SLA_PENALTY)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_breakdown
# -------------------------------------------------------------------


class TestAddBreakdown:
    def test_basic(self):
        eng = _engine()
        b = eng.add_breakdown(
            "bd-1",
            component=CostComponent.ENGINEERING_HOURS,
            severity=CostSeverity.MAJOR,
            amount=5000.0,
            description="Engineering time",
        )
        assert b.breakdown_name == "bd-1"
        assert b.amount == 5000.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_breakdown(f"bd-{i}")
        assert len(eng._breakdowns) == 2


# -------------------------------------------------------------------
# analyze_cost_by_service
# -------------------------------------------------------------------


class TestAnalyzeCostByService:
    def test_with_data(self):
        eng = _engine()
        eng.record_cost("svc-a", total_cost=12000.0, severity=CostSeverity.MAJOR)
        eng.record_cost("svc-a", total_cost=8000.0, severity=CostSeverity.MINOR)
        result = eng.analyze_cost_by_service("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_records"] == 2
        assert result["avg_cost"] == 10000.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_cost_by_service("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_costly_incidents
# -------------------------------------------------------------------


class TestIdentifyCostlyIncidents:
    def test_with_costly(self):
        eng = _engine()
        eng.record_cost("svc-a", total_cost=15000.0)
        eng.record_cost("svc-a", total_cost=20000.0)
        eng.record_cost("svc-b", total_cost=500.0)
        results = eng.identify_costly_incidents()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_costly_incidents() == []


# -------------------------------------------------------------------
# rank_by_total_cost
# -------------------------------------------------------------------


class TestRankByTotalCost:
    def test_with_data(self):
        eng = _engine()
        eng.record_cost("svc-a", total_cost=20000.0)
        eng.record_cost("svc-a", total_cost=10000.0)
        eng.record_cost("svc-b", total_cost=500.0)
        results = eng.rank_by_total_cost()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_total_cost"] == 15000.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_total_cost() == []


# -------------------------------------------------------------------
# detect_cost_trends
# -------------------------------------------------------------------


class TestDetectCostTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_cost("svc-a")
        eng.record_cost("svc-b")
        results = eng.detect_cost_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["trend_detected"] is True

    def test_no_trends(self):
        eng = _engine()
        eng.record_cost("svc-a")
        assert eng.detect_cost_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_cost("svc-a", severity=CostSeverity.MAJOR, total_cost=12000.0)
        eng.record_cost("svc-b", severity=CostSeverity.MINOR, total_cost=500.0)
        eng.add_breakdown("bd-1")
        report = eng.generate_report()
        assert report.total_costs == 2
        assert report.total_breakdowns == 1
        assert report.by_component != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_costs == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_cost("svc-a")
        eng.add_breakdown("bd-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._breakdowns) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_costs"] == 0
        assert stats["total_breakdowns"] == 0
        assert stats["component_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_cost("svc-a", component=CostComponent.DOWNTIME_REVENUE)
        eng.record_cost("svc-b", component=CostComponent.SLA_PENALTY)
        eng.add_breakdown("bd-1")
        stats = eng.get_stats()
        assert stats["total_costs"] == 2
        assert stats["total_breakdowns"] == 1
        assert stats["unique_services"] == 2
