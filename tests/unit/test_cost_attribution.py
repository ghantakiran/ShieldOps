"""Tests for shieldops.billing.cost_attribution -- CostAttributionEngine."""

from __future__ import annotations

import pytest

from shieldops.billing.cost_attribution import (
    AllocationMethod,
    CostAllocationRule,
    CostAttributionEngine,
    CostEntry,
    ReportPeriod,
    TeamCostReport,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _engine(**kwargs) -> CostAttributionEngine:
    return CostAttributionEngine(**kwargs)


def _engine_with_tag_rule(
    team: str = "platform",
    match_tags: dict[str, str] | None = None,
) -> tuple[CostAttributionEngine, CostAllocationRule]:
    eng = _engine()
    rule = eng.create_rule(
        name="tag-rule",
        team=team,
        method=AllocationMethod.TAG_BASED,
        match_tags=match_tags or {"team": "platform"},
    )
    return eng, rule


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_allocation_tag_based(self):
        assert AllocationMethod.TAG_BASED == "tag_based"

    def test_allocation_proportional(self):
        assert AllocationMethod.PROPORTIONAL == "proportional"

    def test_allocation_fixed(self):
        assert AllocationMethod.FIXED == "fixed"

    def test_allocation_custom(self):
        assert AllocationMethod.CUSTOM == "custom"

    def test_report_period_daily(self):
        assert ReportPeriod.DAILY == "daily"

    def test_report_period_weekly(self):
        assert ReportPeriod.WEEKLY == "weekly"

    def test_report_period_monthly(self):
        assert ReportPeriod.MONTHLY == "monthly"

    def test_report_period_quarterly(self):
        assert ReportPeriod.QUARTERLY == "quarterly"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_cost_allocation_rule_defaults(self):
        r = CostAllocationRule(name="r", team="t")
        assert r.id
        assert r.method == AllocationMethod.TAG_BASED
        assert r.match_tags == {}
        assert r.match_services == []
        assert r.proportion == 1.0
        assert r.created_at > 0

    def test_cost_entry_defaults(self):
        e = CostEntry(service="ec2", amount=100.0)
        assert e.id
        assert e.resource_id == ""
        assert e.currency == "USD"
        assert e.tags == {}
        assert e.period == ""
        assert e.recorded_at > 0

    def test_team_cost_report_defaults(self):
        t = TeamCostReport(team="sre")
        assert t.total_cost == 0.0
        assert t.currency == "USD"
        assert t.services == {}
        assert t.period == ""
        assert t.generated_at > 0


# -------------------------------------------------------------------
# Create rule
# -------------------------------------------------------------------


class TestCreateRule:
    def test_create_basic(self):
        eng = _engine()
        r = eng.create_rule(name="basic", team="sre")
        assert r.name == "basic"
        assert r.team == "sre"
        assert r.id

    def test_create_tag_based(self):
        eng = _engine()
        r = eng.create_rule(
            name="tag-r",
            team="sre",
            method=AllocationMethod.TAG_BASED,
            match_tags={"team": "sre"},
        )
        assert r.method == AllocationMethod.TAG_BASED
        assert r.match_tags == {"team": "sre"}

    def test_create_proportional(self):
        eng = _engine()
        r = eng.create_rule(
            name="prop",
            team="sre",
            method=AllocationMethod.PROPORTIONAL,
            proportion=0.5,
        )
        assert r.proportion == 0.5

    def test_create_fixed_with_services(self):
        eng = _engine()
        r = eng.create_rule(
            name="fixed",
            team="sre",
            method=AllocationMethod.FIXED,
            match_services=["ec2", "rds"],
        )
        assert r.match_services == ["ec2", "rds"]

    def test_create_multiple_rules(self):
        eng = _engine()
        eng.create_rule(name="r1", team="sre")
        eng.create_rule(name="r2", team="dev")
        assert len(eng.list_rules()) == 2

    def test_create_rule_exceeds_limit(self):
        eng = _engine(max_rules=2)
        eng.create_rule(name="r1", team="sre")
        eng.create_rule(name="r2", team="dev")
        with pytest.raises(ValueError, match="Maximum rules limit"):
            eng.create_rule(name="r3", team="ops")


# -------------------------------------------------------------------
# Record cost
# -------------------------------------------------------------------


class TestRecordCost:
    def test_record_basic(self):
        eng = _engine()
        e = eng.record_cost(service="ec2", amount=150.0)
        assert e.service == "ec2"
        assert e.amount == 150.0

    def test_record_with_tags(self):
        eng = _engine()
        e = eng.record_cost(
            service="rds",
            amount=200.0,
            tags={"team": "sre"},
        )
        assert e.tags["team"] == "sre"

    def test_record_with_period(self):
        eng = _engine()
        e = eng.record_cost(
            service="ec2",
            amount=50.0,
            period="2026-01",
        )
        assert e.period == "2026-01"

    def test_record_with_resource_id(self):
        eng = _engine()
        e = eng.record_cost(
            service="ec2",
            amount=75.0,
            resource_id="i-abc123",
        )
        assert e.resource_id == "i-abc123"

    def test_record_trims_to_max(self):
        eng = _engine(max_entries=3)
        for i in range(5):
            eng.record_cost(service="ec2", amount=float(i))
        entries = eng.list_entries(limit=100)
        assert len(entries) == 3
        # Oldest trimmed; remaining are amounts 2, 3, 4
        assert entries[0].amount == 2.0


# -------------------------------------------------------------------
# Allocate costs (tag-based)
# -------------------------------------------------------------------


class TestAllocateCostsTagBased:
    def test_tag_match_allocates(self):
        eng, _ = _engine_with_tag_rule(
            team="platform",
            match_tags={"team": "platform"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "platform"},
        )
        reports = eng.allocate_costs()
        assert len(reports) == 1
        assert reports[0].team == "platform"
        assert reports[0].total_cost == 100.0

    def test_tag_no_match_no_allocation(self):
        eng, _ = _engine_with_tag_rule(
            team="platform",
            match_tags={"team": "platform"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "other"},
        )
        reports = eng.allocate_costs()
        assert len(reports) == 0

    def test_tag_empty_match_tags_never_matches(self):
        eng = _engine()
        eng.create_rule(
            name="empty",
            team="sre",
            method=AllocationMethod.TAG_BASED,
            match_tags={},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "sre"},
        )
        reports = eng.allocate_costs()
        assert len(reports) == 0

    def test_multiple_entries_same_team(self):
        eng, _ = _engine_with_tag_rule(
            team="sre",
            match_tags={"team": "sre"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "sre"},
        )
        eng.record_cost(
            service="rds",
            amount=200.0,
            tags={"team": "sre"},
        )
        reports = eng.allocate_costs()
        assert len(reports) == 1
        assert reports[0].total_cost == 300.0
        assert reports[0].services["ec2"] == 100.0
        assert reports[0].services["rds"] == 200.0


# -------------------------------------------------------------------
# Allocate costs (proportional & fixed)
# -------------------------------------------------------------------


class TestAllocateProportionalFixed:
    def test_proportional_half(self):
        eng = _engine()
        eng.create_rule(
            name="half",
            team="sre",
            method=AllocationMethod.PROPORTIONAL,
            proportion=0.5,
        )
        eng.record_cost(service="ec2", amount=200.0)
        reports = eng.allocate_costs()
        assert reports[0].total_cost == 100.0

    def test_fixed_matches_service(self):
        eng = _engine()
        eng.create_rule(
            name="fixed",
            team="sre",
            method=AllocationMethod.FIXED,
            match_services=["rds"],
        )
        eng.record_cost(service="rds", amount=150.0)
        eng.record_cost(service="ec2", amount=100.0)
        reports = eng.allocate_costs()
        assert len(reports) == 1
        assert reports[0].total_cost == 150.0

    def test_fixed_no_service_filter_matches_all(self):
        eng = _engine()
        eng.create_rule(
            name="all",
            team="shared",
            method=AllocationMethod.FIXED,
        )
        eng.record_cost(service="ec2", amount=50.0)
        eng.record_cost(service="rds", amount=100.0)
        reports = eng.allocate_costs()
        assert reports[0].total_cost == 150.0

    def test_custom_matches_tags_and_services(self):
        eng = _engine()
        eng.create_rule(
            name="custom",
            team="data",
            method=AllocationMethod.CUSTOM,
            match_tags={"env": "prod"},
            match_services=["rds"],
        )
        eng.record_cost(
            service="rds",
            amount=300.0,
            tags={"env": "prod"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"env": "prod"},
        )
        reports = eng.allocate_costs()
        assert len(reports) == 1
        assert reports[0].total_cost == 300.0


# -------------------------------------------------------------------
# Get team report
# -------------------------------------------------------------------


class TestGetTeamReport:
    def test_basic_report(self):
        eng, _ = _engine_with_tag_rule(
            team="sre",
            match_tags={"team": "sre"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "sre"},
        )
        rpt = eng.get_team_report("sre")
        assert rpt.team == "sre"
        assert rpt.total_cost == 100.0

    def test_report_with_period_filter(self):
        eng, _ = _engine_with_tag_rule(
            team="sre",
            match_tags={"team": "sre"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "sre"},
            period="2026-01",
        )
        eng.record_cost(
            service="ec2",
            amount=200.0,
            tags={"team": "sre"},
            period="2026-02",
        )
        rpt = eng.get_team_report("sre", period="2026-01")
        assert rpt.total_cost == 100.0
        assert rpt.period == "2026-01"

    def test_report_no_matching_entries(self):
        eng = _engine()
        eng.create_rule(
            name="r",
            team="sre",
            method=AllocationMethod.TAG_BASED,
            match_tags={"team": "sre"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "dev"},
        )
        rpt = eng.get_team_report("sre")
        assert rpt.total_cost == 0.0

    def test_report_services_breakdown(self):
        eng, _ = _engine_with_tag_rule(
            team="sre",
            match_tags={"team": "sre"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "sre"},
        )
        eng.record_cost(
            service="rds",
            amount=200.0,
            tags={"team": "sre"},
        )
        rpt = eng.get_team_report("sre")
        assert rpt.services["ec2"] == 100.0
        assert rpt.services["rds"] == 200.0


# -------------------------------------------------------------------
# List / delete rules
# -------------------------------------------------------------------


class TestRuleManagement:
    def test_list_rules_empty(self):
        eng = _engine()
        assert eng.list_rules() == []

    def test_list_rules_filter_by_team(self):
        eng = _engine()
        eng.create_rule(name="r1", team="sre")
        eng.create_rule(name="r2", team="dev")
        sre_rules = eng.list_rules(team="sre")
        assert len(sre_rules) == 1
        assert sre_rules[0].team == "sre"

    def test_delete_rule_success(self):
        eng = _engine()
        r = eng.create_rule(name="r", team="sre")
        assert eng.delete_rule(r.id) is True
        assert len(eng.list_rules()) == 0

    def test_delete_rule_not_found(self):
        eng = _engine()
        assert eng.delete_rule("nonexistent") is False

    def test_delete_reduces_count(self):
        eng = _engine()
        r1 = eng.create_rule(name="r1", team="sre")
        eng.create_rule(name="r2", team="dev")
        eng.delete_rule(r1.id)
        assert len(eng.list_rules()) == 1


# -------------------------------------------------------------------
# List entries
# -------------------------------------------------------------------


class TestListEntries:
    def test_list_empty(self):
        eng = _engine()
        assert eng.list_entries() == []

    def test_list_with_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_cost(service="ec2", amount=float(i))
        entries = eng.list_entries(limit=3)
        assert len(entries) == 3

    def test_list_filter_by_service(self):
        eng = _engine()
        eng.record_cost(service="ec2", amount=100.0)
        eng.record_cost(service="rds", amount=200.0)
        entries = eng.list_entries(service="rds")
        assert len(entries) == 1
        assert entries[0].service == "rds"

    def test_list_returns_latest(self):
        eng = _engine()
        for i in range(5):
            eng.record_cost(service="ec2", amount=float(i))
        entries = eng.list_entries(limit=2)
        assert entries[0].amount == 3.0
        assert entries[1].amount == 4.0


# -------------------------------------------------------------------
# Unattributed costs
# -------------------------------------------------------------------


class TestUnattributedCosts:
    def test_all_unattributed_when_no_rules(self):
        eng = _engine()
        eng.record_cost(service="ec2", amount=100.0)
        unattr = eng.get_unattributed_costs()
        assert len(unattr) == 1

    def test_none_unattributed_when_all_match(self):
        eng = _engine()
        eng.create_rule(
            name="all",
            team="shared",
            method=AllocationMethod.FIXED,
        )
        eng.record_cost(service="ec2", amount=100.0)
        unattr = eng.get_unattributed_costs()
        assert len(unattr) == 0

    def test_partial_unattributed(self):
        eng, _ = _engine_with_tag_rule(
            team="sre",
            match_tags={"team": "sre"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "sre"},
        )
        eng.record_cost(
            service="rds",
            amount=200.0,
            tags={"team": "dev"},
        )
        unattr = eng.get_unattributed_costs()
        assert len(unattr) == 1
        assert unattr[0].service == "rds"


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        eng = _engine()
        s = eng.get_stats()
        assert s["total_rules"] == 0
        assert s["total_entries"] == 0
        assert s["total_cost"] == 0.0
        assert s["unattributed_entries"] == 0
        assert s["teams"] == 0

    def test_stats_with_data(self):
        eng = _engine()
        eng.create_rule(name="r1", team="sre")
        eng.create_rule(name="r2", team="dev")
        eng.record_cost(service="ec2", amount=100.0)
        eng.record_cost(service="rds", amount=200.0)
        s = eng.get_stats()
        assert s["total_rules"] == 2
        assert s["total_entries"] == 2
        assert s["total_cost"] == 300.0
        assert s["teams"] == 2

    def test_stats_unattributed_count(self):
        eng, _ = _engine_with_tag_rule(
            team="sre",
            match_tags={"team": "sre"},
        )
        eng.record_cost(
            service="ec2",
            amount=100.0,
            tags={"team": "sre"},
        )
        eng.record_cost(service="rds", amount=200.0, tags={})
        s = eng.get_stats()
        assert s["unattributed_entries"] == 1
