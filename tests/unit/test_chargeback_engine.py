"""Tests for shieldops.billing.chargeback_engine — CostChargebackEngine."""

from __future__ import annotations

from shieldops.billing.chargeback_engine import (
    AllocationMethod,
    AllocationRule,
    ChargebackRecord,
    ChargebackReport,
    ChargebackStatus,
    CostCategory,
    CostChargebackEngine,
)


def _engine(**kw) -> CostChargebackEngine:
    return CostChargebackEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AllocationMethod (5 values)

    def test_allocation_method_proportional_usage(self):
        assert AllocationMethod.PROPORTIONAL_USAGE == "proportional_usage"

    def test_allocation_method_equal_split(self):
        assert AllocationMethod.EQUAL_SPLIT == "equal_split"

    def test_allocation_method_headcount_based(self):
        assert AllocationMethod.HEADCOUNT_BASED == "headcount_based"

    def test_allocation_method_revenue_weighted(self):
        assert AllocationMethod.REVENUE_WEIGHTED == "revenue_weighted"

    def test_allocation_method_custom_formula(self):
        assert AllocationMethod.CUSTOM_FORMULA == "custom_formula"

    # ChargebackStatus (5 values)

    def test_chargeback_status_draft(self):
        assert ChargebackStatus.DRAFT == "draft"

    def test_chargeback_status_calculated(self):
        assert ChargebackStatus.CALCULATED == "calculated"

    def test_chargeback_status_reviewed(self):
        assert ChargebackStatus.REVIEWED == "reviewed"

    def test_chargeback_status_approved(self):
        assert ChargebackStatus.APPROVED == "approved"

    def test_chargeback_status_invoiced(self):
        assert ChargebackStatus.INVOICED == "invoiced"

    # CostCategory (5 values)

    def test_cost_category_compute(self):
        assert CostCategory.COMPUTE == "compute"

    def test_cost_category_storage(self):
        assert CostCategory.STORAGE == "storage"

    def test_cost_category_network(self):
        assert CostCategory.NETWORK == "network"

    def test_cost_category_licensing(self):
        assert CostCategory.LICENSING == "licensing"

    def test_cost_category_support(self):
        assert CostCategory.SUPPORT == "support"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_chargeback_record_defaults(self):
        rec = ChargebackRecord()
        assert rec.id
        assert rec.team == ""
        assert rec.department == ""
        assert rec.cost_category == CostCategory.COMPUTE
        assert rec.total_cost == 0.0
        assert rec.allocated_cost == 0.0
        assert rec.allocation_method == AllocationMethod.PROPORTIONAL_USAGE
        assert rec.billing_period == ""
        assert rec.status == ChargebackStatus.DRAFT
        assert rec.created_at > 0

    def test_allocation_rule_defaults(self):
        rule = AllocationRule()
        assert rule.id
        assert rule.cost_category == CostCategory.COMPUTE
        assert rule.method == AllocationMethod.PROPORTIONAL_USAGE
        assert rule.team == ""
        assert rule.weight == 0.0
        assert rule.is_active is True
        assert rule.created_at > 0

    def test_chargeback_report_defaults(self):
        report = ChargebackReport()
        assert report.total_cost == 0.0
        assert report.total_allocated == 0.0
        assert report.unallocated_cost == 0.0
        assert report.by_team == {}
        assert report.by_category == {}
        assert report.by_method == {}
        assert report.allocation_accuracy_pct == 0.0
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# record_cost
# -------------------------------------------------------------------


class TestRecordCost:
    def test_basic_record(self):
        eng = _engine()
        rec = eng.record_cost("team-a", total_cost=500.0)
        assert rec.team == "team-a"
        assert rec.total_cost == 500.0
        assert len(eng.list_records()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.record_cost("team-a")
        r2 = eng.record_cost("team-b")
        assert r1.id != r2.id

    def test_record_with_params(self):
        eng = _engine()
        rec = eng.record_cost(
            "team-a",
            department="engineering",
            cost_category=CostCategory.STORAGE,
            total_cost=1000.0,
            billing_period="2026-01",
        )
        assert rec.department == "engineering"
        assert rec.cost_category == CostCategory.STORAGE
        assert rec.billing_period == "2026-01"

    def test_eviction_at_max_records(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            rec = eng.record_cost(f"team-{i}")
            ids.append(rec.id)
        records = eng.list_records(limit=100)
        assert len(records) == 3
        found = {r.id for r in records}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_get_existing(self):
        eng = _engine()
        rec = eng.record_cost("team-a")
        found = eng.get_record(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_cost("team-a")
        eng.record_cost("team-b")
        eng.record_cost("team-c")
        assert len(eng.list_records()) == 3

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_cost("team-a")
        eng.record_cost("team-b")
        eng.record_cost("team-a")
        results = eng.list_records(team="team-a")
        assert len(results) == 2
        assert all(r.team == "team-a" for r in results)

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_cost(
            "t",
            cost_category=CostCategory.COMPUTE,
        )
        eng.record_cost(
            "t",
            cost_category=CostCategory.STORAGE,
        )
        eng.record_cost(
            "t",
            cost_category=CostCategory.COMPUTE,
        )
        results = eng.list_records(
            cost_category=CostCategory.COMPUTE,
        )
        assert len(results) == 2

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_cost(f"team-{i}")
        results = eng.list_records(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# create_rule
# -------------------------------------------------------------------


class TestCreateRule:
    def test_basic_rule(self):
        eng = _engine()
        rule = eng.create_rule(
            cost_category=CostCategory.COMPUTE,
            team="team-a",
            weight=0.6,
        )
        assert rule.team == "team-a"
        assert rule.weight == 0.6
        assert rule.is_active is True

    def test_rule_unique_id(self):
        eng = _engine()
        r1 = eng.create_rule(team="a")
        r2 = eng.create_rule(team="b")
        assert r1.id != r2.id


# -------------------------------------------------------------------
# allocate_costs
# -------------------------------------------------------------------


class TestAllocateCosts:
    def test_allocate_with_rule(self):
        eng = _engine()
        eng.record_cost(
            "team-a",
            cost_category=CostCategory.COMPUTE,
            total_cost=1000.0,
            billing_period="2026-01",
        )
        eng.create_rule(
            cost_category=CostCategory.COMPUTE,
            team="team-a",
            weight=0.5,
        )
        records = eng.allocate_costs("2026-01")
        assert len(records) == 1
        assert records[0].allocated_cost > 0
        assert records[0].status == ChargebackStatus.CALCULATED

    def test_allocate_no_rules(self):
        eng = _engine()
        eng.record_cost(
            "team-a",
            total_cost=500.0,
            billing_period="2026-01",
        )
        records = eng.allocate_costs("2026-01")
        assert len(records) == 1
        assert records[0].allocated_cost == 500.0

    def test_allocate_empty_period(self):
        eng = _engine()
        records = eng.allocate_costs("2099-01")
        assert records == []


# -------------------------------------------------------------------
# calculate_team_share
# -------------------------------------------------------------------


class TestCalculateTeamShare:
    def test_basic_share(self):
        eng = _engine()
        eng.record_cost(
            "team-a",
            total_cost=1000.0,
        )
        eng.record_cost(
            "team-a",
            total_cost=500.0,
        )
        share = eng.calculate_team_share("team-a")
        assert share["team"] == "team-a"
        assert share["total_cost"] == 1500.0
        assert share["record_count"] == 2

    def test_empty_team(self):
        eng = _engine()
        share = eng.calculate_team_share("nobody")
        assert share["total_cost"] == 0.0
        assert share["record_count"] == 0


# -------------------------------------------------------------------
# detect_allocation_anomalies
# -------------------------------------------------------------------


class TestDetectAllocationAnomalies:
    def test_finds_anomaly(self):
        eng = _engine(unallocated_threshold_pct=5.0)
        rec = eng.record_cost(
            "team-a",
            total_cost=1000.0,
        )
        rec.allocated_cost = 500.0
        anomalies = eng.detect_allocation_anomalies()
        assert len(anomalies) == 1
        assert anomalies[0]["team"] == "team-a"

    def test_no_anomalies(self):
        eng = _engine()
        rec = eng.record_cost(
            "team-a",
            total_cost=1000.0,
        )
        rec.allocated_cost = 1000.0
        anomalies = eng.detect_allocation_anomalies()
        assert len(anomalies) == 0


# -------------------------------------------------------------------
# compare_periods
# -------------------------------------------------------------------


class TestComparePeriods:
    def test_basic_compare(self):
        eng = _engine()
        eng.record_cost(
            "team-a",
            total_cost=1000.0,
            billing_period="2026-01",
        )
        eng.record_cost(
            "team-a",
            total_cost=1500.0,
            billing_period="2026-02",
        )
        result = eng.compare_periods(
            "2026-01",
            "2026-02",
        )
        assert result["total_a"] == 1000.0
        assert result["total_b"] == 1500.0
        assert result["change"] == 500.0
        assert result["change_pct"] == 50.0

    def test_compare_empty_periods(self):
        eng = _engine()
        result = eng.compare_periods(
            "2099-01",
            "2099-02",
        )
        assert result["total_a"] == 0.0
        assert result["change"] == 0.0
        assert result["change_pct"] == 0.0


# -------------------------------------------------------------------
# generate_chargeback_report
# -------------------------------------------------------------------


class TestGenerateChargebackReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_cost(
            "team-a",
            cost_category=CostCategory.COMPUTE,
            total_cost=1000.0,
        )
        eng.record_cost(
            "team-b",
            cost_category=CostCategory.STORAGE,
            total_cost=500.0,
        )
        report = eng.generate_chargeback_report()
        assert report.total_cost == 1500.0
        assert isinstance(report.by_team, dict)
        assert isinstance(report.by_category, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_chargeback_report()
        assert report.total_cost == 0.0
        assert report.total_allocated == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_cost("team-a")
        eng.record_cost("team-b")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_records()) == 0

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
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["unallocated_threshold_pct"] == 5.0
        assert stats["team_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_cost("team-a")
        eng.record_cost("team-b")
        eng.record_cost("team-a")
        eng.create_rule(team="team-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 3
        assert stats["total_rules"] == 1
        assert stats["team_distribution"]["team-a"] == 2
        assert stats["team_distribution"]["team-b"] == 1
