"""Tests for shieldops.incidents.impact_quantifier."""

from __future__ import annotations

import pytest

from shieldops.incidents.impact_quantifier import (
    CostBreakdown,
    CostCategory,
    ImpactAssessment,
    ImpactDimension,
    ImpactReport,
    IncidentImpactQuantifier,
    QuantificationMethod,
)


def _engine(**kw) -> IncidentImpactQuantifier:
    return IncidentImpactQuantifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ImpactDimension (5 values)

    def test_dimension_revenue_loss(self):
        assert ImpactDimension.REVENUE_LOSS == "revenue_loss"

    def test_dimension_customer_impact(self):
        assert ImpactDimension.CUSTOMER_IMPACT == "customer_impact"

    def test_dimension_sla_credit(self):
        assert ImpactDimension.SLA_CREDIT == "sla_credit"

    def test_dimension_engineering_cost(self):
        assert ImpactDimension.ENGINEERING_COST == "engineering_cost"

    def test_dimension_reputation_damage(self):
        assert ImpactDimension.REPUTATION_DAMAGE == "reputation_damage"

    # QuantificationMethod (5 values)

    def test_method_direct_measurement(self):
        assert QuantificationMethod.DIRECT_MEASUREMENT == "direct_measurement"

    def test_method_estimation(self):
        assert QuantificationMethod.ESTIMATION == "estimation"

    def test_method_extrapolation(self):
        assert QuantificationMethod.EXTRAPOLATION == "extrapolation"

    def test_method_benchmark_based(self):
        assert QuantificationMethod.BENCHMARK_BASED == "benchmark_based"

    def test_method_manual_input(self):
        assert QuantificationMethod.MANUAL_INPUT == "manual_input"

    # CostCategory (5 values)

    def test_category_infrastructure(self):
        assert CostCategory.INFRASTRUCTURE == "infrastructure"

    def test_category_personnel(self):
        assert CostCategory.PERSONNEL == "personnel"

    def test_category_opportunity(self):
        assert CostCategory.OPPORTUNITY == "opportunity"

    def test_category_contractual_penalty(self):
        assert CostCategory.CONTRACTUAL_PENALTY == "contractual_penalty"

    def test_category_customer_churn(self):
        assert CostCategory.CUSTOMER_CHURN == "customer_churn"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_cost_breakdown_defaults(self):
        cb = CostBreakdown()
        assert cb.id
        assert cb.assessment_id == ""
        assert cb.category == CostCategory.INFRASTRUCTURE
        assert cb.amount_usd == 0.0
        assert cb.description == ""
        assert cb.method == QuantificationMethod.ESTIMATION
        assert cb.created_at > 0

    def test_impact_assessment_defaults(self):
        ia = ImpactAssessment()
        assert ia.id
        assert ia.incident_id == ""
        assert ia.service_name == ""
        assert ia.duration_minutes == 0.0
        assert ia.affected_customers == 0
        assert ia.total_cost_usd == 0.0
        assert ia.sla_credit_usd == 0.0
        assert ia.primary_dimension == ImpactDimension.REVENUE_LOSS
        assert ia.method == QuantificationMethod.ESTIMATION
        assert ia.severity == "medium"
        assert ia.created_at > 0

    def test_impact_report_defaults(self):
        ir = ImpactReport()
        assert ir.total_assessments == 0
        assert ir.total_cost_usd == 0.0
        assert ir.total_sla_credits_usd == 0.0
        assert ir.total_affected_customers == 0
        assert ir.by_dimension == {}
        assert ir.by_category == {}
        assert ir.avg_duration_minutes == 0.0
        assert ir.recommendations == []
        assert ir.generated_at > 0


# -------------------------------------------------------------------
# create_assessment
# -------------------------------------------------------------------


class TestCreateAssessment:
    def test_basic_create(self):
        eng = _engine()
        a = eng.create_assessment("inc-1", "svc-a")
        assert a.incident_id == "inc-1"
        assert a.service_name == "svc-a"
        assert len(eng.list_assessments()) == 1

    def test_create_assigns_unique_ids(self):
        eng = _engine()
        a1 = eng.create_assessment("inc-1")
        a2 = eng.create_assessment("inc-2")
        assert a1.id != a2.id

    def test_create_with_values(self):
        eng = _engine()
        a = eng.create_assessment(
            "inc-1",
            service_name="svc-a",
            duration_minutes=120.0,
            affected_customers=500,
            total_cost_usd=25000.0,
            sla_credit_usd=2000.0,
            primary_dimension=ImpactDimension.CUSTOMER_IMPACT,
            severity="critical",
        )
        assert a.duration_minutes == 120.0
        assert a.affected_customers == 500
        assert a.total_cost_usd == 25000.0
        assert a.sla_credit_usd == 2000.0
        assert a.primary_dimension == ImpactDimension.CUSTOMER_IMPACT
        assert a.severity == "critical"

    def test_eviction_at_max(self):
        eng = _engine(max_assessments=3)
        ids = []
        for i in range(4):
            a = eng.create_assessment(f"inc-{i}")
            ids.append(a.id)
        items = eng.list_assessments(limit=100)
        assert len(items) == 3
        found = {a.id for a in items}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_assessment
# -------------------------------------------------------------------


class TestGetAssessment:
    def test_get_existing(self):
        eng = _engine()
        a = eng.create_assessment("inc-1")
        found = eng.get_assessment(a.id)
        assert found is not None
        assert found.id == a.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# -------------------------------------------------------------------
# list_assessments
# -------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.create_assessment("inc-1")
        eng.create_assessment("inc-2")
        eng.create_assessment("inc-3")
        assert len(eng.list_assessments()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_assessment("inc-1", service_name="svc-a")
        eng.create_assessment("inc-2", service_name="svc-b")
        eng.create_assessment("inc-3", service_name="svc-a")
        results = eng.list_assessments(service_name="svc-a")
        assert len(results) == 2
        assert all(a.service_name == "svc-a" for a in results)

    def test_filter_by_severity(self):
        eng = _engine()
        eng.create_assessment("inc-1", severity="critical")
        eng.create_assessment("inc-2", severity="low")
        results = eng.list_assessments(severity="critical")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.create_assessment(f"inc-{i}")
        results = eng.list_assessments(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# add_cost_breakdown
# -------------------------------------------------------------------


class TestAddCostBreakdown:
    def test_add_success(self):
        eng = _engine()
        a = eng.create_assessment("inc-1")
        bd = eng.add_cost_breakdown(
            a.id,
            category=CostCategory.PERSONNEL,
            amount_usd=5000.0,
            description="Oncall engineer time",
        )
        assert bd is not None
        assert bd.assessment_id == a.id
        assert bd.amount_usd == 5000.0

    def test_add_not_found(self):
        eng = _engine()
        assert eng.add_cost_breakdown("nonexistent") is None


# -------------------------------------------------------------------
# calculate_total_impact
# -------------------------------------------------------------------


class TestCalculateTotalImpact:
    def test_with_breakdowns(self):
        eng = _engine(default_hourly_rate_usd=100.0)
        a = eng.create_assessment(
            "inc-1",
            total_cost_usd=10000.0,
            duration_minutes=60.0,
        )
        eng.add_cost_breakdown(a.id, amount_usd=2000.0)
        result = eng.calculate_total_impact(a.id)
        assert result["found"] is True
        assert result["base_cost_usd"] == 10000.0
        assert result["breakdown_cost_usd"] == 2000.0
        assert result["engineering_cost_usd"] == pytest.approx(100.0, abs=0.01)
        assert result["total_usd"] == pytest.approx(12100.0, abs=0.01)

    def test_not_found(self):
        eng = _engine()
        result = eng.calculate_total_impact("nonexistent")
        assert result["found"] is False
        assert result["total_usd"] == 0.0


# -------------------------------------------------------------------
# estimate_sla_credit
# -------------------------------------------------------------------


class TestEstimateSlaCredit:
    def test_credit_due(self):
        eng = _engine()
        # 1440 minutes = 1 day of downtime
        a = eng.create_assessment("inc-1", duration_minutes=1440.0)
        result = eng.estimate_sla_credit(
            a.id,
            sla_target_pct=99.9,
            monthly_contract_usd=10000.0,
        )
        assert result["found"] is True
        assert result["credit_usd"] > 0

    def test_no_credit_when_within_sla(self):
        eng = _engine()
        # Very short outage - within SLA
        a = eng.create_assessment("inc-1", duration_minutes=1.0)
        result = eng.estimate_sla_credit(
            a.id,
            sla_target_pct=99.9,
            monthly_contract_usd=10000.0,
        )
        assert result["found"] is True
        assert result["credit_usd"] == 0.0

    def test_not_found(self):
        eng = _engine()
        result = eng.estimate_sla_credit("nonexistent")
        assert result["found"] is False


# -------------------------------------------------------------------
# estimate_customer_impact
# -------------------------------------------------------------------


class TestEstimateCustomerImpact:
    def test_with_affected_customers(self):
        eng = _engine()
        a = eng.create_assessment("inc-1", affected_customers=500)
        result = eng.estimate_customer_impact(a.id, total_customers=10000)
        assert result["found"] is True
        assert result["affected_pct"] == pytest.approx(5.0, abs=0.01)

    def test_not_found(self):
        eng = _engine()
        result = eng.estimate_customer_impact("nonexistent")
        assert result["found"] is False


# -------------------------------------------------------------------
# compare_incidents
# -------------------------------------------------------------------


class TestCompareIncidents:
    def test_compare_multiple(self):
        eng = _engine()
        a1 = eng.create_assessment("inc-1", total_cost_usd=5000.0)
        a2 = eng.create_assessment("inc-2", total_cost_usd=15000.0)
        results = eng.compare_incidents([a1.id, a2.id])
        assert len(results) == 2
        assert results[0]["total_cost_usd"] == 15000.0

    def test_compare_with_missing(self):
        eng = _engine()
        a1 = eng.create_assessment("inc-1")
        results = eng.compare_incidents([a1.id, "nonexistent"])
        assert len(results) == 1


# -------------------------------------------------------------------
# generate_impact_report
# -------------------------------------------------------------------


class TestGenerateImpactReport:
    def test_basic_report(self):
        eng = _engine()
        eng.create_assessment(
            "inc-1",
            total_cost_usd=5000.0,
            duration_minutes=30.0,
            affected_customers=100,
        )
        eng.create_assessment(
            "inc-2",
            total_cost_usd=8000.0,
            duration_minutes=60.0,
            affected_customers=200,
        )
        report = eng.generate_impact_report()
        assert report.total_assessments == 2
        assert report.total_cost_usd == pytest.approx(13000.0)
        assert report.total_affected_customers == 300
        assert isinstance(report.by_dimension, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_impact_report()
        assert report.total_assessments == 0
        assert report.total_cost_usd == 0.0
        assert report.avg_duration_minutes == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.create_assessment("inc-1")
        eng.create_assessment("inc-2")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_assessments()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_breakdowns"] == 0
        assert stats["default_hourly_rate"] == 150.0
        assert stats["dimension_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.create_assessment(
            "inc-1",
            primary_dimension=ImpactDimension.REVENUE_LOSS,
        )
        eng.create_assessment(
            "inc-2",
            primary_dimension=ImpactDimension.CUSTOMER_IMPACT,
        )
        a = eng.create_assessment("inc-3")
        eng.add_cost_breakdown(a.id, amount_usd=1000.0)
        stats = eng.get_stats()
        assert stats["total_assessments"] == 3
        assert stats["total_breakdowns"] == 1
        assert len(stats["dimension_distribution"]) == 2
