"""Tests for shieldops.incidents.escalation_optimizer — IncidentEscalationOptimizer."""

from __future__ import annotations

from shieldops.incidents.escalation_optimizer import (
    EscalationOptimizerReport,
    EscalationPath,
    EscalationRecord,
    IncidentEscalationOptimizer,
    OptimizationAction,
    PathEfficiency,
    PathRecommendation,
)


def _engine(**kw) -> IncidentEscalationOptimizer:
    return IncidentEscalationOptimizer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # EscalationPath (5)
    def test_path_direct_team(self):
        assert EscalationPath.DIRECT_TEAM == "direct_team"

    def test_path_manager_first(self):
        assert EscalationPath.MANAGER_FIRST == "manager_first"

    def test_path_cross_team(self):
        assert EscalationPath.CROSS_TEAM == "cross_team"

    def test_path_executive(self):
        assert EscalationPath.EXECUTIVE == "executive"

    def test_path_automated(self):
        assert EscalationPath.AUTOMATED == "automated"

    # PathEfficiency (5)
    def test_efficiency_optimal(self):
        assert PathEfficiency.OPTIMAL == "optimal"

    def test_efficiency_efficient(self):
        assert PathEfficiency.EFFICIENT == "efficient"

    def test_efficiency_adequate(self):
        assert PathEfficiency.ADEQUATE == "adequate"

    def test_efficiency_slow(self):
        assert PathEfficiency.SLOW == "slow"

    def test_efficiency_inefficient(self):
        assert PathEfficiency.INEFFICIENT == "inefficient"

    # OptimizationAction (5)
    def test_action_skip_tier(self):
        assert OptimizationAction.SKIP_TIER == "skip_tier"

    def test_action_parallel_notify(self):
        assert OptimizationAction.PARALLEL_NOTIFY == "parallel_notify"

    def test_action_auto_route(self):
        assert OptimizationAction.AUTO_ROUTE == "auto_route"

    def test_action_add_responder(self):
        assert OptimizationAction.ADD_RESPONDER == "add_responder"

    def test_action_no_change(self):
        assert OptimizationAction.NO_CHANGE == "no_change"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_escalation_record_defaults(self):
        r = EscalationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.path == EscalationPath.DIRECT_TEAM
        assert r.efficiency == PathEfficiency.ADEQUATE
        assert r.resolution_time_minutes == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_path_recommendation_defaults(self):
        r = PathRecommendation()
        assert r.id
        assert r.recommendation_name == ""
        assert r.path == EscalationPath.DIRECT_TEAM
        assert r.action == OptimizationAction.NO_CHANGE
        assert r.time_saved_minutes == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = EscalationOptimizerReport()
        assert r.total_records == 0
        assert r.total_recommendations == 0
        assert r.avg_resolution_time_min == 0.0
        assert r.by_path == {}
        assert r.by_efficiency == {}
        assert r.slow_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_escalation
# -------------------------------------------------------------------


class TestRecordEscalation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_escalation(
            "svc-a",
            path=EscalationPath.CROSS_TEAM,
            efficiency=PathEfficiency.OPTIMAL,
        )
        assert r.service_name == "svc-a"
        assert r.path == EscalationPath.CROSS_TEAM

    def test_with_resolution_time(self):
        eng = _engine()
        r = eng.record_escalation("svc-b", resolution_time_minutes=45.0)
        assert r.resolution_time_minutes == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_escalation(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_escalation
# -------------------------------------------------------------------


class TestGetEscalation:
    def test_found(self):
        eng = _engine()
        r = eng.record_escalation("svc-a")
        assert eng.get_escalation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_escalation("nonexistent") is None


# -------------------------------------------------------------------
# list_escalations
# -------------------------------------------------------------------


class TestListEscalations:
    def test_list_all(self):
        eng = _engine()
        eng.record_escalation("svc-a")
        eng.record_escalation("svc-b")
        assert len(eng.list_escalations()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_escalation("svc-a")
        eng.record_escalation("svc-b")
        results = eng.list_escalations(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_path(self):
        eng = _engine()
        eng.record_escalation("svc-a", path=EscalationPath.EXECUTIVE)
        eng.record_escalation("svc-b", path=EscalationPath.DIRECT_TEAM)
        results = eng.list_escalations(path=EscalationPath.EXECUTIVE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_recommendation
# -------------------------------------------------------------------


class TestAddRecommendation:
    def test_basic(self):
        eng = _engine()
        r = eng.add_recommendation(
            "rec-1",
            path=EscalationPath.AUTOMATED,
            action=OptimizationAction.SKIP_TIER,
            time_saved_minutes=10.0,
        )
        assert r.recommendation_name == "rec-1"
        assert r.time_saved_minutes == 10.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_recommendation(f"rec-{i}")
        assert len(eng._recommendations) == 2


# -------------------------------------------------------------------
# analyze_escalation_efficiency
# -------------------------------------------------------------------


class TestAnalyzeEscalationEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_escalation("svc-a", resolution_time_minutes=20.0, efficiency=PathEfficiency.SLOW)
        eng.record_escalation(
            "svc-a",
            resolution_time_minutes=10.0,
            efficiency=PathEfficiency.OPTIMAL,
        )
        result = eng.analyze_escalation_efficiency("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_records"] == 2
        assert result["avg_resolution_time_min"] == 15.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_escalation_efficiency("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_escalation_time_min=30.0)
        eng.record_escalation("svc-a", resolution_time_minutes=25.0)
        result = eng.analyze_escalation_efficiency("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_slow_escalations
# -------------------------------------------------------------------


class TestIdentifySlowEscalations:
    def test_with_slow(self):
        eng = _engine()
        eng.record_escalation("svc-a", efficiency=PathEfficiency.SLOW)
        eng.record_escalation("svc-a", efficiency=PathEfficiency.INEFFICIENT)
        eng.record_escalation("svc-b", efficiency=PathEfficiency.OPTIMAL)
        results = eng.identify_slow_escalations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_escalations() == []


# -------------------------------------------------------------------
# rank_by_resolution_time
# -------------------------------------------------------------------


class TestRankByResolutionTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_escalation("svc-a", resolution_time_minutes=50.0)
        eng.record_escalation("svc-a", resolution_time_minutes=30.0)
        eng.record_escalation("svc-b", resolution_time_minutes=10.0)
        results = eng.rank_by_resolution_time()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_resolution_time_min"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_resolution_time() == []


# -------------------------------------------------------------------
# detect_escalation_patterns
# -------------------------------------------------------------------


class TestDetectEscalationPatterns:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_escalation("svc-a")
        eng.record_escalation("svc-b")
        results = eng.detect_escalation_patterns()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_escalation("svc-a")
        assert eng.detect_escalation_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_escalation("svc-a", efficiency=PathEfficiency.SLOW, resolution_time_minutes=40.0)
        eng.record_escalation(
            "svc-b",
            efficiency=PathEfficiency.OPTIMAL,
            resolution_time_minutes=10.0,
        )
        eng.add_recommendation("rec-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_recommendations == 1
        assert report.by_path != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.recommendations[0] == "Escalation optimization meets targets"

    def test_exceeds_threshold(self):
        eng = _engine(max_escalation_time_min=10.0)
        eng.record_escalation("svc-a", resolution_time_minutes=50.0)
        report = eng.generate_report()
        assert "exceeds" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_escalation("svc-a")
        eng.add_recommendation("rec-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._recommendations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["path_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_escalation("svc-a", path=EscalationPath.DIRECT_TEAM)
        eng.record_escalation("svc-b", path=EscalationPath.EXECUTIVE)
        eng.add_recommendation("rec-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_recommendations"] == 1
        assert stats["unique_services"] == 2
