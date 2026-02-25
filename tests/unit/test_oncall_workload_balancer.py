"""Tests for shieldops.incidents.oncall_workload_balancer."""

from __future__ import annotations

import pytest

from shieldops.incidents.oncall_workload_balancer import (
    LoadFactor,
    OnCallWorkloadBalancer,
    RebalanceAction,
    RebalanceSuggestion,
    WorkloadBalance,
    WorkloadRecord,
    WorkloadReport,
)


def _engine(**kw) -> OnCallWorkloadBalancer:
    return OnCallWorkloadBalancer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # WorkloadBalance (5 values)

    def test_balance_equitable(self):
        assert WorkloadBalance.EQUITABLE == "equitable"

    def test_balance_slightly_uneven(self):
        assert WorkloadBalance.SLIGHTLY_UNEVEN == "slightly_uneven"

    def test_balance_moderately_uneven(self):
        assert WorkloadBalance.MODERATELY_UNEVEN == "moderately_uneven"

    def test_balance_heavily_skewed(self):
        assert WorkloadBalance.HEAVILY_SKEWED == "heavily_skewed"

    def test_balance_critical_imbalance(self):
        assert WorkloadBalance.CRITICAL_IMBALANCE == "critical_imbalance"

    # LoadFactor (5 values)

    def test_factor_page_count(self):
        assert LoadFactor.PAGE_COUNT == "page_count"

    def test_factor_after_hours_pages(self):
        assert LoadFactor.AFTER_HOURS_PAGES == "after_hours_pages"

    def test_factor_incident_duration(self):
        assert LoadFactor.INCIDENT_DURATION == "incident_duration"

    def test_factor_weekend_shifts(self):
        assert LoadFactor.WEEKEND_SHIFTS == "weekend_shifts"

    def test_factor_escalation_count(self):
        assert LoadFactor.ESCALATION_COUNT == "escalation_count"

    # RebalanceAction (5 values)

    def test_action_no_change(self):
        assert RebalanceAction.NO_CHANGE == "no_change"

    def test_action_swap_shift(self):
        assert RebalanceAction.SWAP_SHIFT == "swap_shift"

    def test_action_add_secondary(self):
        assert RebalanceAction.ADD_SECONDARY == "add_secondary"

    def test_action_reduce_rotation(self):
        assert RebalanceAction.REDUCE_ROTATION == "reduce_rotation"

    def test_action_temporary_relief(self):
        assert RebalanceAction.TEMPORARY_RELIEF == "temporary_relief"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_workload_record_defaults(self):
        w = WorkloadRecord()
        assert w.id
        assert w.team_member == ""
        assert w.team_name == ""
        assert w.period_label == ""
        assert w.page_count == 0
        assert w.after_hours_pages == 0
        assert w.incident_duration_minutes == 0.0
        assert w.weekend_shifts == 0
        assert w.escalation_count == 0
        assert w.created_at > 0

    def test_rebalance_suggestion_defaults(self):
        s = RebalanceSuggestion()
        assert s.id
        assert s.team_name == ""
        assert s.action == RebalanceAction.NO_CHANGE
        assert s.from_member == ""
        assert s.to_member == ""
        assert s.reason == ""
        assert s.impact_score == 0.0
        assert s.created_at > 0

    def test_workload_report_defaults(self):
        r = WorkloadReport()
        assert r.total_records == 0
        assert r.total_suggestions == 0
        assert r.by_balance == {}
        assert r.by_action == {}
        assert r.overloaded_members == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_workload
# -------------------------------------------------------------------


class TestRecordWorkload:
    def test_basic_record(self):
        eng = _engine()
        w = eng.record_workload("alice", team_name="sre", page_count=10)
        assert w.team_member == "alice"
        assert w.team_name == "sre"
        assert w.page_count == 10
        assert len(eng.list_workloads()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        w1 = eng.record_workload("alice")
        w2 = eng.record_workload("bob")
        assert w1.id != w2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            w = eng.record_workload(f"member-{i}")
            ids.append(w.id)
        workloads = eng.list_workloads(limit=100)
        assert len(workloads) == 3
        found = {w.id for w in workloads}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_workload
# -------------------------------------------------------------------


class TestGetWorkload:
    def test_get_existing(self):
        eng = _engine()
        w = eng.record_workload("alice")
        found = eng.get_workload(w.id)
        assert found is not None
        assert found.id == w.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_workload("nonexistent") is None


# -------------------------------------------------------------------
# list_workloads
# -------------------------------------------------------------------


class TestListWorkloads:
    def test_list_all(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre")
        eng.record_workload("bob", team_name="platform")
        assert len(eng.list_workloads()) == 2

    def test_filter_by_team_name(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre")
        eng.record_workload("bob", team_name="platform")
        eng.record_workload("carol", team_name="sre")
        results = eng.list_workloads(team_name="sre")
        assert len(results) == 2
        assert all(w.team_name == "sre" for w in results)

    def test_filter_by_team_member(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre")
        eng.record_workload("bob", team_name="sre")
        results = eng.list_workloads(team_member="alice")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_workload(f"member-{i}")
        results = eng.list_workloads(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# compute_balance_score
# -------------------------------------------------------------------


class TestComputeBalanceScore:
    def test_no_records(self):
        eng = _engine()
        result = eng.compute_balance_score("sre")
        assert result["balance"] == "equitable"
        assert result["member_count"] == 0
        assert result["score"] == pytest.approx(100.0)

    def test_balanced_team(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre", page_count=10)
        eng.record_workload("bob", team_name="sre", page_count=10)
        result = eng.compute_balance_score("sre")
        assert result["balance"] == "equitable"
        assert result["score"] == pytest.approx(100.0)

    def test_imbalanced_team(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre", page_count=100)
        eng.record_workload("bob", team_name="sre", page_count=1)
        result = eng.compute_balance_score("sre")
        assert result["score"] < 50.0


# -------------------------------------------------------------------
# suggest_rebalance
# -------------------------------------------------------------------


class TestSuggestRebalance:
    def test_no_data(self):
        eng = _engine()
        s = eng.suggest_rebalance("sre")
        assert s.action == RebalanceAction.NO_CHANGE
        assert s.reason == "No workload data available"

    def test_single_member(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre", page_count=10)
        s = eng.suggest_rebalance("sre")
        assert s.action == RebalanceAction.ADD_SECONDARY

    def test_balanced_no_change(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre", page_count=10)
        eng.record_workload("bob", team_name="sre", page_count=10)
        s = eng.suggest_rebalance("sre")
        assert s.action == RebalanceAction.NO_CHANGE

    def test_imbalanced_swap_shift(self):
        eng = _engine(imbalance_threshold_pct=10.0)
        eng.record_workload("alice", team_name="sre", page_count=100)
        eng.record_workload("bob", team_name="sre", page_count=1)
        s = eng.suggest_rebalance("sre")
        assert s.action == RebalanceAction.SWAP_SHIFT


# -------------------------------------------------------------------
# list_suggestions
# -------------------------------------------------------------------


class TestListSuggestions:
    def test_list_all(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre")
        eng.record_workload("bob", team_name="platform")
        eng.suggest_rebalance("sre")
        eng.suggest_rebalance("platform")
        assert len(eng.list_suggestions()) == 2

    def test_filter_by_team_name(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre")
        eng.record_workload("bob", team_name="platform")
        eng.suggest_rebalance("sre")
        eng.suggest_rebalance("platform")
        results = eng.list_suggestions(team_name="sre")
        assert len(results) == 1
        assert results[0].team_name == "sre"


# -------------------------------------------------------------------
# identify_overloaded_members
# -------------------------------------------------------------------


class TestIdentifyOverloadedMembers:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_overloaded_members() == []

    def test_overloaded_detected(self):
        eng = _engine(imbalance_threshold_pct=10.0)
        eng.record_workload("alice", team_name="sre", page_count=100)
        eng.record_workload("bob", team_name="sre", page_count=5)
        eng.record_workload("carol", team_name="sre", page_count=5)
        overloaded = eng.identify_overloaded_members()
        assert len(overloaded) >= 1
        assert overloaded[0]["team_member"] == "alice"

    def test_no_overload_when_balanced(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre", page_count=10)
        eng.record_workload("bob", team_name="sre", page_count=10)
        overloaded = eng.identify_overloaded_members()
        assert len(overloaded) == 0


# -------------------------------------------------------------------
# compare_periods
# -------------------------------------------------------------------


class TestComparePeriods:
    def test_compare_two_periods(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre", period_label="Q1", page_count=10)
        eng.record_workload("bob", team_name="sre", period_label="Q2", page_count=20)
        results = eng.compare_periods(["Q1", "Q2"])
        assert len(results) == 2
        assert results[0]["period_label"] == "Q1"
        assert results[0]["total_pages"] == 10
        assert results[1]["total_pages"] == 20

    def test_compare_missing_period(self):
        eng = _engine()
        results = eng.compare_periods(["Q1"])
        assert len(results) == 1
        assert results[0]["record_count"] == 0
        assert results[0]["total_pages"] == 0


# -------------------------------------------------------------------
# generate_workload_report
# -------------------------------------------------------------------


class TestGenerateWorkloadReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre", page_count=50)
        eng.record_workload("bob", team_name="sre", page_count=5)
        eng.suggest_rebalance("sre")
        report = eng.generate_workload_report()
        assert report.total_records == 2
        assert report.total_suggestions == 1
        assert isinstance(report.by_balance, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_workload_report()
        assert report.total_records == 0
        assert report.total_suggestions == 0
        assert "On-call workload distribution is balanced" in report.recommendations


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre")
        eng.suggest_rebalance("sre")
        count = eng.clear_data()
        assert count == 1
        assert len(eng.list_workloads()) == 0
        assert len(eng.list_suggestions()) == 0

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
        assert stats["total_suggestions"] == 0
        assert stats["imbalance_threshold_pct"] == 30.0
        assert stats["unique_teams"] == 0

    def test_stats_populated(self):
        eng = _engine()
        eng.record_workload("alice", team_name="sre")
        eng.record_workload("bob", team_name="platform")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["unique_teams"] == 2
