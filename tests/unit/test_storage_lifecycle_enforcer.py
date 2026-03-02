"""Tests for shieldops.billing.storage_lifecycle_enforcer."""

from __future__ import annotations

from shieldops.billing.storage_lifecycle_enforcer import (
    EnforcementMode,
    LifecycleAction,
    LifecycleAnalysis,
    LifecyclePolicyRecord,
    StorageLifecycleEnforcer,
    StorageLifecycleReport,
    StorageTier,
)


def _engine(**kw) -> StorageLifecycleEnforcer:
    return StorageLifecycleEnforcer(**kw)


class TestEnums:
    def test_storagetier_hot(self):
        assert StorageTier.HOT == "hot"

    def test_storagetier_warm(self):
        assert StorageTier.WARM == "warm"

    def test_storagetier_cool(self):
        assert StorageTier.COOL == "cool"

    def test_storagetier_cold(self):
        assert StorageTier.COLD == "cold"

    def test_storagetier_archive(self):
        assert StorageTier.ARCHIVE == "archive"

    def test_lifecycleaction_transition(self):
        assert LifecycleAction.TRANSITION == "transition"

    def test_lifecycleaction_delete(self):
        assert LifecycleAction.DELETE == "delete"

    def test_lifecycleaction_compress(self):
        assert LifecycleAction.COMPRESS == "compress"

    def test_lifecycleaction_replicate(self):
        assert LifecycleAction.REPLICATE == "replicate"

    def test_lifecycleaction_tag(self):
        assert LifecycleAction.TAG == "tag"

    def test_enforcementmode_strict(self):
        assert EnforcementMode.STRICT == "strict"

    def test_enforcementmode_advisory(self):
        assert EnforcementMode.ADVISORY == "advisory"

    def test_enforcementmode_dry_run(self):
        assert EnforcementMode.DRY_RUN == "dry_run"

    def test_enforcementmode_gradual(self):
        assert EnforcementMode.GRADUAL == "gradual"

    def test_enforcementmode_custom(self):
        assert EnforcementMode.CUSTOM == "custom"


class TestModels:
    def test_lifecycle_policy_record_defaults(self):
        r = LifecyclePolicyRecord()
        assert r.id
        assert r.storage_tier == StorageTier.HOT
        assert r.lifecycle_action == LifecycleAction.TRANSITION
        assert r.enforcement_mode == EnforcementMode.ADVISORY
        assert r.data_size_gb == 0.0
        assert r.cost_before == 0.0
        assert r.cost_after == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_lifecycle_analysis_defaults(self):
        a = LifecycleAnalysis()
        assert a.id
        assert a.storage_tier == StorageTier.HOT
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_storage_lifecycle_report_defaults(self):
        r = StorageLifecycleReport()
        assert r.id
        assert r.total_records == 0
        assert r.enforced_count == 0
        assert r.avg_cost_reduction == 0.0
        assert r.by_storage_tier == {}
        assert r.top_transitions == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordLifecyclePolicy:
    def test_basic(self):
        eng = _engine()
        r = eng.record_lifecycle_policy(
            storage_tier=StorageTier.COLD,
            lifecycle_action=LifecycleAction.TRANSITION,
            enforcement_mode=EnforcementMode.STRICT,
            data_size_gb=500.0,
            cost_before=100.0,
            cost_after=20.0,
            service="s3-archive",
            team="data",
        )
        assert r.storage_tier == StorageTier.COLD
        assert r.cost_before == 100.0
        assert r.team == "data"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_lifecycle_policy(storage_tier=StorageTier.HOT)
        assert len(eng._records) == 3


class TestGetLifecyclePolicy:
    def test_found(self):
        eng = _engine()
        r = eng.record_lifecycle_policy(cost_before=50.0, cost_after=10.0)
        result = eng.get_lifecycle_policy(r.id)
        assert result is not None
        assert result.cost_before == 50.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_lifecycle_policy("nonexistent") is None


class TestListLifecyclePolicies:
    def test_list_all(self):
        eng = _engine()
        eng.record_lifecycle_policy(storage_tier=StorageTier.HOT)
        eng.record_lifecycle_policy(storage_tier=StorageTier.COLD)
        assert len(eng.list_lifecycle_policies()) == 2

    def test_filter_by_tier(self):
        eng = _engine()
        eng.record_lifecycle_policy(storage_tier=StorageTier.HOT)
        eng.record_lifecycle_policy(storage_tier=StorageTier.ARCHIVE)
        results = eng.list_lifecycle_policies(storage_tier=StorageTier.HOT)
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_lifecycle_policy(lifecycle_action=LifecycleAction.TRANSITION)
        eng.record_lifecycle_policy(lifecycle_action=LifecycleAction.DELETE)
        results = eng.list_lifecycle_policies(lifecycle_action=LifecycleAction.TRANSITION)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_lifecycle_policy(team="data")
        eng.record_lifecycle_policy(team="platform")
        results = eng.list_lifecycle_policies(team="data")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_lifecycle_policy(storage_tier=StorageTier.COLD)
        assert len(eng.list_lifecycle_policies(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            storage_tier=StorageTier.ARCHIVE,
            analysis_score=80.0,
            threshold=60.0,
            breached=True,
            description="archive transition ready",
        )
        assert a.storage_tier == StorageTier.ARCHIVE
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(storage_tier=StorageTier.COLD)
        assert len(eng._analyses) == 2


class TestAnalyzeTierDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_lifecycle_policy(
            storage_tier=StorageTier.COLD, cost_before=100.0, cost_after=20.0
        )
        eng.record_lifecycle_policy(
            storage_tier=StorageTier.COLD, cost_before=200.0, cost_after=40.0
        )
        result = eng.analyze_tier_distribution()
        assert "cold" in result
        assert result["cold"]["count"] == 2
        assert result["cold"]["avg_cost_reduction"] == 120.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_tier_distribution() == {}


class TestIdentifyHighReductionPolicies:
    def test_detects_above_threshold(self):
        eng = _engine(cost_reduction_threshold=50.0)
        eng.record_lifecycle_policy(cost_before=200.0, cost_after=50.0)
        eng.record_lifecycle_policy(cost_before=30.0, cost_after=20.0)
        results = eng.identify_high_reduction_policies()
        assert len(results) == 1
        assert results[0]["cost_reduction"] == 150.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_reduction_policies() == []


class TestRankByCostReduction:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_lifecycle_policy(service="archive-svc", cost_before=500.0, cost_after=100.0)
        eng.record_lifecycle_policy(service="log-svc", cost_before=50.0, cost_after=30.0)
        results = eng.rank_by_cost_reduction()
        assert results[0]["service"] == "archive-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_reduction() == []


class TestDetectLifecycleTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_lifecycle_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_lifecycle_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_lifecycle_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_lifecycle_policy(
            storage_tier=StorageTier.ARCHIVE,
            lifecycle_action=LifecycleAction.TRANSITION,
            enforcement_mode=EnforcementMode.STRICT,
            cost_before=100.0,
            cost_after=10.0,
        )
        report = eng.generate_report()
        assert isinstance(report, StorageLifecycleReport)
        assert report.total_records == 1
        assert report.enforced_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_lifecycle_policy(storage_tier=StorageTier.COLD)
        eng.add_analysis(storage_tier=StorageTier.COLD)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["storage_tier_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_lifecycle_policy(
            storage_tier=StorageTier.COLD,
            service="archive",
            team="data",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "cold" in stats["storage_tier_distribution"]
