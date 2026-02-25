"""Tests for shieldops.billing.idle_resource_detector — IdleResourceDetector."""

from __future__ import annotations

from shieldops.billing.idle_resource_detector import (
    IdleClassification,
    IdleReport,
    IdleResourceDetector,
    IdleResourceRecord,
    IdleSummary,
    RecommendedAction,
    ResourceCategory,
)


def _engine(**kw) -> IdleResourceDetector:
    return IdleResourceDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # IdleClassification (5)
    def test_classification_active(self):
        assert IdleClassification.ACTIVE == "active"

    def test_classification_low_utilization(self):
        assert IdleClassification.LOW_UTILIZATION == "low_utilization"

    def test_classification_near_idle(self):
        assert IdleClassification.NEAR_IDLE == "near_idle"

    def test_classification_idle(self):
        assert IdleClassification.IDLE == "idle"

    def test_classification_zombie(self):
        assert IdleClassification.ZOMBIE == "zombie"

    # ResourceCategory (5)
    def test_category_compute(self):
        assert ResourceCategory.COMPUTE == "compute"

    def test_category_database(self):
        assert ResourceCategory.DATABASE == "database"

    def test_category_load_balancer(self):
        assert ResourceCategory.LOAD_BALANCER == "load_balancer"

    def test_category_cache(self):
        assert ResourceCategory.CACHE == "cache"

    def test_category_queue(self):
        assert ResourceCategory.QUEUE == "queue"

    # RecommendedAction (5)
    def test_action_keep(self):
        assert RecommendedAction.KEEP == "keep"

    def test_action_downsize(self):
        assert RecommendedAction.DOWNSIZE == "downsize"

    def test_action_hibernate(self):
        assert RecommendedAction.HIBERNATE == "hibernate"

    def test_action_terminate(self):
        assert RecommendedAction.TERMINATE == "terminate"

    def test_action_review(self):
        assert RecommendedAction.REVIEW == "review"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_idle_resource_record_defaults(self):
        r = IdleResourceRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.resource_name == ""
        assert r.category == ResourceCategory.COMPUTE
        assert r.classification == IdleClassification.ACTIVE
        assert r.recommended_action == RecommendedAction.REVIEW
        assert r.utilization_pct == 0.0
        assert r.cost_per_hour == 0.0
        assert r.idle_hours == 0.0
        assert r.wasted_cost == 0.0
        assert r.team == ""
        assert r.last_active_at == 0.0
        assert r.created_at > 0

    def test_idle_summary_defaults(self):
        s = IdleSummary()
        assert s.id
        assert s.team == ""
        assert s.total_resources == 0
        assert s.idle_count == 0
        assert s.total_wasted_cost == 0.0
        assert s.by_category == {}
        assert s.by_action == {}
        assert s.created_at > 0

    def test_idle_report_defaults(self):
        r = IdleReport()
        assert r.total_resources == 0
        assert r.idle_count == 0
        assert r.zombie_count == 0
        assert r.total_wasted_cost == 0.0
        assert r.by_classification == {}
        assert r.by_category == {}
        assert r.top_wasters == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_resource
# ---------------------------------------------------------------------------


class TestRecordResource:
    def test_active_resource(self):
        eng = _engine()
        rec = eng.record_resource(
            resource_id="i-abc123",
            resource_name="web-server-1",
            category=ResourceCategory.COMPUTE,
            utilization_pct=75.0,
            cost_per_hour=0.50,
            idle_hours=0.0,
            team="platform",
        )
        assert rec.resource_id == "i-abc123"
        assert rec.resource_name == "web-server-1"
        assert rec.classification == IdleClassification.ACTIVE
        assert rec.recommended_action == RecommendedAction.KEEP
        assert rec.wasted_cost == 0.0

    def test_idle_resource(self):
        eng = _engine()
        rec = eng.record_resource(
            resource_id="i-def456",
            resource_name="staging-db",
            category=ResourceCategory.DATABASE,
            utilization_pct=2.0,
            cost_per_hour=1.0,
            idle_hours=100.0,
            team="data",
        )
        assert rec.classification == IdleClassification.IDLE
        assert rec.wasted_cost == 100.0

    def test_zombie_resource(self):
        eng = _engine()
        rec = eng.record_resource(
            resource_id="i-ghi789",
            resource_name="orphan-lb",
            category=ResourceCategory.LOAD_BALANCER,
            utilization_pct=0.0,
            cost_per_hour=0.25,
            idle_hours=720.0,
            team="infra",
        )
        assert rec.classification == IdleClassification.ZOMBIE
        assert rec.recommended_action == RecommendedAction.TERMINATE
        assert rec.wasted_cost == 180.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_resource(
                resource_id=f"r-{i}",
                resource_name=f"res-{i}",
                utilization_pct=0.0,
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_resource
# ---------------------------------------------------------------------------


class TestGetResource:
    def test_found(self):
        eng = _engine()
        rec = eng.record_resource("r-1", "web-1", utilization_pct=50.0)
        result = eng.get_resource(rec.id)
        assert result is not None
        assert result.resource_id == "r-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_resource("nonexistent") is None


# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------


class TestListResources:
    def test_list_all(self):
        eng = _engine()
        eng.record_resource("r-1", "web-1", utilization_pct=80.0)
        eng.record_resource("r-2", "db-1", utilization_pct=0.0)
        assert len(eng.list_resources()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_resource("r-1", "web-1", category=ResourceCategory.COMPUTE, utilization_pct=80.0)
        eng.record_resource("r-2", "db-1", category=ResourceCategory.DATABASE, utilization_pct=50.0)
        results = eng.list_resources(category=ResourceCategory.COMPUTE)
        assert len(results) == 1
        assert results[0].resource_id == "r-1"

    def test_filter_by_classification(self):
        eng = _engine()
        eng.record_resource("r-1", "web-1", utilization_pct=80.0)
        eng.record_resource("r-2", "orphan", utilization_pct=0.0)
        results = eng.list_resources(classification=IdleClassification.ZOMBIE)
        assert len(results) == 1
        assert results[0].resource_id == "r-2"


# ---------------------------------------------------------------------------
# classify_utilization
# ---------------------------------------------------------------------------


class TestClassifyUtilization:
    def test_active_above_50(self):
        eng = _engine()
        assert eng.classify_utilization(50.0) == IdleClassification.ACTIVE
        assert eng.classify_utilization(99.0) == IdleClassification.ACTIVE

    def test_idle_above_zero_below_threshold(self):
        eng = _engine(idle_threshold_pct=5.0)
        assert eng.classify_utilization(2.0) == IdleClassification.IDLE

    def test_zombie_zero(self):
        eng = _engine()
        assert eng.classify_utilization(0.0) == IdleClassification.ZOMBIE


# ---------------------------------------------------------------------------
# recommend_action
# ---------------------------------------------------------------------------


class TestRecommendAction:
    def test_terminate_zombie(self):
        eng = _engine()
        rec = eng.record_resource("r-1", "orphan", utilization_pct=0.0, idle_hours=500.0)
        result = eng.recommend_action(rec.id)
        assert result["recommended_action"] == RecommendedAction.TERMINATE.value
        assert result["classification"] == IdleClassification.ZOMBIE.value

    def test_keep_active(self):
        eng = _engine()
        rec = eng.record_resource("r-2", "prod-web", utilization_pct=80.0)
        result = eng.recommend_action(rec.id)
        assert result["recommended_action"] == RecommendedAction.KEEP.value


# ---------------------------------------------------------------------------
# calculate_wasted_cost
# ---------------------------------------------------------------------------


class TestCalculateWastedCost:
    def test_has_waste(self):
        eng = _engine()
        eng.record_resource(
            "r-1", "orphan-1", utilization_pct=0.0, cost_per_hour=1.0, idle_hours=100.0
        )
        eng.record_resource(
            "r-2", "orphan-2", utilization_pct=0.0, cost_per_hour=0.5, idle_hours=200.0
        )
        result = eng.calculate_wasted_cost()
        assert result["total_wasted_cost"] == 200.0
        assert result["annual_projected_waste"] == 2400.0
        assert "by_category" in result
        assert "by_classification" in result

    def test_no_waste(self):
        eng = _engine()
        eng.record_resource("r-1", "prod-web", utilization_pct=80.0, cost_per_hour=1.0)
        result = eng.calculate_wasted_cost()
        assert result["total_wasted_cost"] == 0.0


# ---------------------------------------------------------------------------
# summarize_by_team
# ---------------------------------------------------------------------------


class TestSummarizeByTeam:
    def test_multiple_teams(self):
        eng = _engine()
        eng.record_resource(
            "r-1", "web-1", utilization_pct=0.0, cost_per_hour=1.0, idle_hours=10.0, team="platform"
        )
        eng.record_resource(
            "r-2", "db-1", utilization_pct=0.0, cost_per_hour=2.0, idle_hours=20.0, team="data"
        )
        eng.record_resource("r-3", "web-2", utilization_pct=80.0, team="platform")
        summaries = eng.summarize_by_team()
        assert len(summaries) == 2
        teams = {s.team for s in summaries}
        assert "platform" in teams
        assert "data" in teams

    def test_single_team(self):
        eng = _engine()
        eng.record_resource(
            "r-1", "web-1", utilization_pct=0.0, cost_per_hour=1.0, idle_hours=10.0, team="infra"
        )
        summaries = eng.summarize_by_team()
        assert len(summaries) == 1
        assert summaries[0].team == "infra"
        assert summaries[0].total_resources == 1


# ---------------------------------------------------------------------------
# rank_by_waste
# ---------------------------------------------------------------------------


class TestRankByWaste:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_resource(
            "r-1", "small-waste", utilization_pct=0.0, cost_per_hour=0.10, idle_hours=100.0
        )
        eng.record_resource(
            "r-2", "big-waste", utilization_pct=0.0, cost_per_hour=5.0, idle_hours=200.0
        )
        ranked = eng.rank_by_waste()
        assert len(ranked) == 2
        assert ranked[0]["resource_name"] == "big-waste"
        assert ranked[0]["wasted_cost"] > ranked[1]["wasted_cost"]

    def test_no_waste(self):
        eng = _engine()
        eng.record_resource("r-1", "prod-web", utilization_pct=80.0)
        ranked = eng.rank_by_waste()
        assert ranked == []


# ---------------------------------------------------------------------------
# generate_idle_report
# ---------------------------------------------------------------------------


class TestGenerateIdleReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_resource(
            "r-1",
            "zombie-1",
            utilization_pct=0.0,
            cost_per_hour=1.0,
            idle_hours=100.0,
            team="infra",
        )
        eng.record_resource(
            "r-2", "active-1", utilization_pct=80.0, cost_per_hour=2.0, team="platform"
        )
        eng.record_resource(
            "r-3", "idle-1", utilization_pct=2.0, cost_per_hour=0.5, idle_hours=50.0, team="data"
        )
        report = eng.generate_idle_report()
        assert report.total_resources == 3
        assert report.idle_count == 2  # zombie + idle
        assert report.zombie_count == 1
        assert report.total_wasted_cost > 0
        assert len(report.by_classification) > 0
        assert len(report.by_category) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_idle_report()
        assert report.total_resources == 0
        assert report.idle_count == 0
        assert report.zombie_count == 0
        assert report.total_wasted_cost == 0.0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_resource("r-1", "web-1", utilization_pct=0.0)
        assert len(eng._records) == 1
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["idle_threshold_pct"] == 5.0
        assert stats["classification_distribution"] == {}
        assert stats["category_distribution"] == {}
        assert stats["total_wasted_cost"] == 0.0

    def test_populated(self):
        eng = _engine()
        eng.record_resource("r-1", "web-1", category=ResourceCategory.COMPUTE, utilization_pct=80.0)
        eng.record_resource(
            "r-2",
            "db-1",
            category=ResourceCategory.DATABASE,
            utilization_pct=0.0,
            cost_per_hour=1.0,
            idle_hours=10.0,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert len(stats["classification_distribution"]) > 0
        assert len(stats["category_distribution"]) == 2
        assert stats["total_wasted_cost"] == 10.0
