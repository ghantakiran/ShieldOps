"""Tests for shieldops.operations.workload_balancer — TeamWorkloadBalancer."""

from __future__ import annotations

from shieldops.operations.workload_balancer import (
    BalanceStatus,
    RebalanceAction,
    TeamWorkloadBalancer,
    WorkloadAssignment,
    WorkloadBalancerReport,
    WorkloadRecord,
    WorkloadType,
)


def _engine(**kw) -> TeamWorkloadBalancer:
    return TeamWorkloadBalancer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # WorkloadType (5)
    def test_type_incidents(self):
        assert WorkloadType.INCIDENTS == "incidents"

    def test_type_deployments(self):
        assert WorkloadType.DEPLOYMENTS == "deployments"

    def test_type_on_call(self):
        assert WorkloadType.ON_CALL == "on_call"

    def test_type_projects(self):
        assert WorkloadType.PROJECTS == "projects"

    def test_type_maintenance(self):
        assert WorkloadType.MAINTENANCE == "maintenance"

    # BalanceStatus (5)
    def test_status_balanced(self):
        assert BalanceStatus.BALANCED == "balanced"

    def test_status_slightly_unbalanced(self):
        assert BalanceStatus.SLIGHTLY_UNBALANCED == "slightly_unbalanced"

    def test_status_unbalanced(self):
        assert BalanceStatus.UNBALANCED == "unbalanced"

    def test_status_heavily_unbalanced(self):
        assert BalanceStatus.HEAVILY_UNBALANCED == "heavily_unbalanced"

    def test_status_critical(self):
        assert BalanceStatus.CRITICAL == "critical"

    # RebalanceAction (5)
    def test_action_redistribute(self):
        assert RebalanceAction.REDISTRIBUTE == "redistribute"

    def test_action_defer(self):
        assert RebalanceAction.DEFER == "defer"

    def test_action_escalate(self):
        assert RebalanceAction.ESCALATE == "escalate"

    def test_action_automate(self):
        assert RebalanceAction.AUTOMATE == "automate"

    def test_action_no_action(self):
        assert RebalanceAction.NO_ACTION == "no_action"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_workload_record_defaults(self):
        r = WorkloadRecord()
        assert r.id
        assert r.team_name == ""
        assert r.workload_type == WorkloadType.INCIDENTS
        assert r.status == BalanceStatus.BALANCED
        assert r.workload_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_workload_assignment_defaults(self):
        r = WorkloadAssignment()
        assert r.id
        assert r.assignment_name == ""
        assert r.workload_type == WorkloadType.INCIDENTS
        assert r.action == RebalanceAction.NO_ACTION
        assert r.impact_score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_workload_balancer_report_defaults(self):
        r = WorkloadBalancerReport()
        assert r.total_workloads == 0
        assert r.total_assignments == 0
        assert r.avg_workload_score_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.overloaded_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_workload
# -------------------------------------------------------------------


class TestRecordWorkload:
    def test_basic(self):
        eng = _engine()
        r = eng.record_workload(
            "team-alpha",
            workload_type=WorkloadType.INCIDENTS,
            status=BalanceStatus.BALANCED,
            workload_score=25.0,
            details="nominal",
        )
        assert r.team_name == "team-alpha"
        assert r.workload_score == 25.0
        assert r.id

    def test_stored(self):
        eng = _engine()
        eng.record_workload("team-alpha")
        assert len(eng._records) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_workload(f"team-{i}")
        assert len(eng._records) == 2

    def test_multiple_teams(self):
        eng = _engine()
        eng.record_workload("team-alpha")
        eng.record_workload("team-beta")
        assert len(eng._records) == 2


# -------------------------------------------------------------------
# get_workload
# -------------------------------------------------------------------


class TestGetWorkload:
    def test_found(self):
        eng = _engine()
        r = eng.record_workload("team-alpha")
        result = eng.get_workload(r.id)
        assert result is not None
        assert result.id == r.id

    def test_not_found(self):
        eng = _engine()
        assert eng.get_workload("nonexistent") is None


# -------------------------------------------------------------------
# list_workloads
# -------------------------------------------------------------------


class TestListWorkloads:
    def test_list_all(self):
        eng = _engine()
        eng.record_workload("team-alpha")
        eng.record_workload("team-beta")
        assert len(eng.list_workloads()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_workload("team-alpha")
        eng.record_workload("team-beta")
        results = eng.list_workloads(team_name="team-alpha")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_workload("team-alpha", workload_type=WorkloadType.ON_CALL)
        eng.record_workload("team-beta", workload_type=WorkloadType.INCIDENTS)
        results = eng.list_workloads(workload_type=WorkloadType.ON_CALL)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_assignment
# -------------------------------------------------------------------


class TestAddAssignment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assignment(
            "redistribute-oncall",
            workload_type=WorkloadType.ON_CALL,
            action=RebalanceAction.REDISTRIBUTE,
            impact_score=60.0,
            description="Redistribute on-call shifts",
        )
        assert a.assignment_name == "redistribute-oncall"
        assert a.impact_score == 60.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_assignment(f"assign-{i}")
        assert len(eng._assignments) == 2


# -------------------------------------------------------------------
# analyze_workload_by_team
# -------------------------------------------------------------------


class TestAnalyzeWorkloadByTeam:
    def test_with_data(self):
        eng = _engine()
        eng.record_workload("team-alpha", workload_score=80.0, status=BalanceStatus.CRITICAL)
        eng.record_workload("team-alpha", workload_score=60.0, status=BalanceStatus.BALANCED)
        result = eng.analyze_workload_by_team("team-alpha")
        assert result["team_name"] == "team-alpha"
        assert result["total_records"] == 2
        assert result["avg_workload_score"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_workload_by_team("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_overloaded_teams
# -------------------------------------------------------------------


class TestIdentifyOverloadedTeams:
    def test_with_overloaded(self):
        eng = _engine()
        eng.record_workload("team-alpha", status=BalanceStatus.CRITICAL)
        eng.record_workload("team-alpha", status=BalanceStatus.HEAVILY_UNBALANCED)
        eng.record_workload("team-beta", status=BalanceStatus.BALANCED)
        results = eng.identify_overloaded_teams()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-alpha"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overloaded_teams() == []


# -------------------------------------------------------------------
# rank_by_workload_score
# -------------------------------------------------------------------


class TestRankByWorkloadScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_workload("team-alpha", workload_score=90.0)
        eng.record_workload("team-alpha", workload_score=80.0)
        eng.record_workload("team-beta", workload_score=30.0)
        results = eng.rank_by_workload_score()
        assert results[0]["team_name"] == "team-alpha"
        assert results[0]["avg_workload_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_workload_score() == []


# -------------------------------------------------------------------
# detect_workload_imbalance
# -------------------------------------------------------------------


class TestDetectWorkloadImbalance:
    def test_with_imbalances(self):
        eng = _engine()
        for _ in range(5):
            eng.record_workload("team-alpha")
        eng.record_workload("team-beta")
        results = eng.detect_workload_imbalance()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-alpha"
        assert results[0]["imbalance_detected"] is True

    def test_no_imbalances(self):
        eng = _engine()
        eng.record_workload("team-alpha")
        assert eng.detect_workload_imbalance() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_workload("team-alpha", status=BalanceStatus.CRITICAL, workload_score=90.0)
        eng.record_workload("team-beta", status=BalanceStatus.BALANCED, workload_score=20.0)
        eng.add_assignment("assign-1")
        report = eng.generate_report()
        assert report.total_workloads == 2
        assert report.total_assignments == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_workloads == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_workload("team-alpha")
        eng.add_assignment("assign-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._assignments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_workloads"] == 0
        assert stats["total_assignments"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_workload("team-alpha", workload_type=WorkloadType.INCIDENTS)
        eng.record_workload("team-beta", workload_type=WorkloadType.ON_CALL)
        eng.add_assignment("assign-1")
        stats = eng.get_stats()
        assert stats["total_workloads"] == 2
        assert stats["total_assignments"] == 1
        assert stats["unique_teams"] == 2
