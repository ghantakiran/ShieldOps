"""Tests for shieldops.billing.right_sizer — CapacityRightSizer."""

from __future__ import annotations

from shieldops.billing.right_sizer import (
    CapacityRightSizer,
    ConfidenceLevel,
    ResourceType,
    RightSizingSummary,
    SizingAction,
    SizingRecommendation,
    UtilizationSample,
)


def _engine(**kw) -> CapacityRightSizer:
    return CapacityRightSizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ResourceType (6)
    def test_resource_compute(self):
        assert ResourceType.COMPUTE == "compute"

    def test_resource_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_gpu(self):
        assert ResourceType.GPU == "gpu"

    def test_resource_database(self):
        assert ResourceType.DATABASE == "database"

    # SizingAction (5)
    def test_action_downsize(self):
        assert SizingAction.DOWNSIZE == "downsize"

    def test_action_upsize(self):
        assert SizingAction.UPSIZE == "upsize"

    def test_action_maintain(self):
        assert SizingAction.MAINTAIN == "maintain"

    def test_action_terminate(self):
        assert SizingAction.TERMINATE == "terminate"

    def test_action_reserve(self):
        assert SizingAction.RESERVE == "reserve"

    # ConfidenceLevel (4)
    def test_confidence_high(self):
        assert ConfidenceLevel.HIGH == "high"

    def test_confidence_medium(self):
        assert ConfidenceLevel.MEDIUM == "medium"

    def test_confidence_low(self):
        assert ConfidenceLevel.LOW == "low"

    def test_confidence_insufficient_data(self):
        assert ConfidenceLevel.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_utilization_sample_defaults(self):
        s = UtilizationSample(resource_id="r-1", resource_type=ResourceType.COMPUTE)
        assert s.id
        assert s.utilization_pct == 0.0
        assert s.cost_per_hour == 0.0

    def test_sizing_recommendation_defaults(self):
        r = SizingRecommendation(
            resource_id="r-1",
            resource_type=ResourceType.COMPUTE,
            action=SizingAction.MAINTAIN,
            confidence=ConfidenceLevel.HIGH,
        )
        assert r.id
        assert r.estimated_monthly_savings == 0.0
        assert r.reason == ""

    def test_right_sizing_summary_defaults(self):
        s = RightSizingSummary()
        assert s.total_resources_analyzed == 0
        assert s.total_estimated_monthly_savings == 0.0
        assert s.recommendations == []


# ---------------------------------------------------------------------------
# record_utilization
# ---------------------------------------------------------------------------


class TestRecordUtilization:
    def test_basic_record(self):
        eng = _engine()
        s = eng.record_utilization(
            resource_id="r-1",
            resource_type=ResourceType.COMPUTE,
            utilization_pct=0.5,
        )
        assert s.resource_id == "r-1"
        assert s.utilization_pct == 0.5

    def test_unique_ids(self):
        eng = _engine()
        s1 = eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        s2 = eng.record_utilization("r-2", ResourceType.COMPUTE, 0.6)
        assert s1.id != s2.id

    def test_eviction_at_max(self):
        eng = _engine(max_samples=3)
        for i in range(5):
            eng.record_utilization(f"r-{i}", ResourceType.COMPUTE, 0.5)
        assert len(eng._samples) == 3


# ---------------------------------------------------------------------------
# get_sample
# ---------------------------------------------------------------------------


class TestGetSample:
    def test_found(self):
        eng = _engine()
        s = eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        assert eng.get_sample(s.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_sample("nonexistent") is None


# ---------------------------------------------------------------------------
# list_samples
# ---------------------------------------------------------------------------


class TestListSamples:
    def test_list_all(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        eng.record_utilization("r-2", ResourceType.MEMORY, 0.6)
        assert len(eng.list_samples()) == 2

    def test_filter_resource_id(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        eng.record_utilization("r-2", ResourceType.COMPUTE, 0.6)
        results = eng.list_samples(resource_id="r-1")
        assert len(results) == 1
        assert results[0].resource_id == "r-1"

    def test_filter_resource_type(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        eng.record_utilization("r-2", ResourceType.MEMORY, 0.6)
        results = eng.list_samples(resource_type=ResourceType.MEMORY)
        assert len(results) == 1
        assert results[0].resource_type == ResourceType.MEMORY


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------


class TestGenerateRecommendations:
    def test_downsize(self):
        eng = _engine(underutil_threshold=0.3)
        # avg_util = 0.2 < 0.3 => DOWNSIZE
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.2, cost_per_hour=1.0)
        recs = eng.generate_recommendations()
        assert len(recs) == 1
        assert recs[0].action == SizingAction.DOWNSIZE
        assert recs[0].estimated_monthly_savings > 0.0

    def test_upsize(self):
        eng = _engine()
        # avg_util = 0.9 > 0.85 => UPSIZE
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.9)
        recs = eng.generate_recommendations()
        assert len(recs) == 1
        assert recs[0].action == SizingAction.UPSIZE

    def test_terminate(self):
        eng = _engine()
        # avg_util = 0.02 < 0.05 => TERMINATE
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.02)
        recs = eng.generate_recommendations()
        assert len(recs) == 1
        assert recs[0].action == SizingAction.TERMINATE

    def test_maintain(self):
        eng = _engine()
        # avg_util = 0.5 => MAINTAIN (between 0.3 and 0.85)
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        recs = eng.generate_recommendations()
        assert len(recs) == 1
        assert recs[0].action == SizingAction.MAINTAIN


# ---------------------------------------------------------------------------
# get_recommendation
# ---------------------------------------------------------------------------


class TestGetRecommendation:
    def test_found(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        recs = eng.generate_recommendations()
        assert eng.get_recommendation(recs[0].id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_recommendation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_recommendations
# ---------------------------------------------------------------------------


class TestListRecommendations:
    def test_list_all(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        eng.record_utilization("r-2", ResourceType.COMPUTE, 0.9)
        eng.generate_recommendations()
        assert len(eng.list_recommendations()) == 2

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)  # MAINTAIN
        eng.record_utilization("r-2", ResourceType.COMPUTE, 0.9)  # UPSIZE
        eng.generate_recommendations()
        results = eng.list_recommendations(action=SizingAction.UPSIZE)
        assert len(results) == 1
        assert results[0].action == SizingAction.UPSIZE


# ---------------------------------------------------------------------------
# estimate_savings
# ---------------------------------------------------------------------------


class TestEstimateSavings:
    def test_empty(self):
        eng = _engine()
        savings = eng.estimate_savings()
        assert savings["total_monthly_savings"] == 0.0

    def test_with_savings(self):
        eng = _engine(underutil_threshold=0.3)
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.2, cost_per_hour=1.0)
        eng.generate_recommendations()
        savings = eng.estimate_savings()
        assert savings["total_monthly_savings"] > 0.0


# ---------------------------------------------------------------------------
# analyze_utilization_trends
# ---------------------------------------------------------------------------


class TestAnalyzeUtilizationTrends:
    def test_basic_trends(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.3)
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        trends = eng.analyze_utilization_trends("r-1")
        assert trends["sample_count"] == 2
        assert trends["avg_utilization"] == 0.4
        assert trends["min_utilization"] == 0.3
        assert trends["max_utilization"] == 0.5


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    def test_basic_summary(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        eng.generate_recommendations()
        summary = eng.generate_summary()
        assert summary.total_resources_analyzed == 1
        assert summary.maintain_count == 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        eng.generate_recommendations()
        eng.clear_data()
        assert len(eng._samples) == 0
        assert len(eng._recommendations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_samples"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["unique_resources"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_utilization("r-1", ResourceType.COMPUTE, 0.5)
        eng.record_utilization("r-2", ResourceType.MEMORY, 0.9)
        eng.generate_recommendations()
        stats = eng.get_stats()
        assert stats["total_samples"] == 2
        assert stats["total_recommendations"] == 2
        assert stats["unique_resources"] == 2
