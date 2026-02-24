"""Tests for shieldops.billing.storage_optimizer — StorageTierOptimizer."""

from __future__ import annotations

import time

from shieldops.billing.storage_optimizer import (
    AccessFrequency,
    MigrationStatus,
    StorageAsset,
    StorageClass,
    StorageOptimizationReport,
    StorageTierOptimizer,
    TierMigration,
)


def _engine(**kw) -> StorageTierOptimizer:
    return StorageTierOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # StorageClass (6)
    def test_storage_hot(self):
        assert StorageClass.HOT == "hot"

    def test_storage_warm(self):
        assert StorageClass.WARM == "warm"

    def test_storage_cold(self):
        assert StorageClass.COLD == "cold"

    def test_storage_archive(self):
        assert StorageClass.ARCHIVE == "archive"

    def test_storage_glacier(self):
        assert StorageClass.GLACIER == "glacier"

    def test_storage_infrequent(self):
        assert StorageClass.INFREQUENT == "infrequent"

    # MigrationStatus (5)
    def test_migration_pending(self):
        assert MigrationStatus.PENDING == "pending"

    def test_migration_in_progress(self):
        assert MigrationStatus.IN_PROGRESS == "in_progress"

    def test_migration_completed(self):
        assert MigrationStatus.COMPLETED == "completed"

    def test_migration_failed(self):
        assert MigrationStatus.FAILED == "failed"

    def test_migration_cancelled(self):
        assert MigrationStatus.CANCELLED == "cancelled"

    # AccessFrequency (6)
    def test_access_daily(self):
        assert AccessFrequency.DAILY == "daily"

    def test_access_weekly(self):
        assert AccessFrequency.WEEKLY == "weekly"

    def test_access_monthly(self):
        assert AccessFrequency.MONTHLY == "monthly"

    def test_access_quarterly(self):
        assert AccessFrequency.QUARTERLY == "quarterly"

    def test_access_yearly(self):
        assert AccessFrequency.YEARLY == "yearly"

    def test_access_never(self):
        assert AccessFrequency.NEVER == "never"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_storage_asset_defaults(self):
        a = StorageAsset(asset_name="bucket-1", current_tier=StorageClass.HOT)
        assert a.id
        assert a.size_gb == 0.0
        assert a.access_frequency == AccessFrequency.MONTHLY

    def test_tier_migration_defaults(self):
        m = TierMigration(
            asset_id="a-1",
            from_tier=StorageClass.HOT,
            to_tier=StorageClass.WARM,
        )
        assert m.id
        assert m.status == MigrationStatus.PENDING
        assert m.estimated_savings_monthly == 0.0

    def test_storage_optimization_report_defaults(self):
        r = StorageOptimizationReport()
        assert r.total_assets == 0
        assert r.estimated_total_savings == 0.0
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# register_asset
# ---------------------------------------------------------------------------


class TestRegisterAsset:
    def test_basic(self):
        eng = _engine()
        a = eng.register_asset("bucket-1", StorageClass.HOT, size_gb=100.0)
        assert a.asset_name == "bucket-1"
        assert a.current_tier == StorageClass.HOT

    def test_eviction(self):
        eng = _engine(max_assets=3)
        for i in range(5):
            eng.register_asset(f"bucket-{i}", StorageClass.HOT)
        assert len(eng._assets) == 3


# ---------------------------------------------------------------------------
# get_asset
# ---------------------------------------------------------------------------


class TestGetAsset:
    def test_found(self):
        eng = _engine()
        a = eng.register_asset("bucket-1", StorageClass.HOT)
        assert eng.get_asset(a.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_asset("nonexistent") is None


# ---------------------------------------------------------------------------
# list_assets
# ---------------------------------------------------------------------------


class TestListAssets:
    def test_list_all(self):
        eng = _engine()
        eng.register_asset("bucket-1", StorageClass.HOT)
        eng.register_asset("bucket-2", StorageClass.COLD)
        assert len(eng.list_assets()) == 2

    def test_filter_tier(self):
        eng = _engine()
        eng.register_asset("bucket-1", StorageClass.HOT)
        eng.register_asset("bucket-2", StorageClass.COLD)
        results = eng.list_assets(current_tier=StorageClass.HOT)
        assert len(results) == 1
        assert results[0].current_tier == StorageClass.HOT

    def test_filter_frequency(self):
        eng = _engine()
        eng.register_asset("bucket-1", StorageClass.HOT, access_frequency=AccessFrequency.DAILY)
        eng.register_asset("bucket-2", StorageClass.HOT, access_frequency=AccessFrequency.NEVER)
        results = eng.list_assets(access_frequency=AccessFrequency.NEVER)
        assert len(results) == 1
        assert results[0].access_frequency == AccessFrequency.NEVER


# ---------------------------------------------------------------------------
# recommend_tier_migrations
# ---------------------------------------------------------------------------


class TestRecommendTierMigrations:
    def test_glacier_for_never(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.NEVER,
            monthly_cost=100.0,
        )
        migrations = eng.recommend_tier_migrations()
        assert len(migrations) == 1
        assert migrations[0].to_tier == StorageClass.GLACIER
        assert migrations[0].estimated_savings_monthly == 60.0

    def test_cold_for_quarterly(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.QUARTERLY,
            monthly_cost=100.0,
        )
        migrations = eng.recommend_tier_migrations()
        assert len(migrations) == 1
        assert migrations[0].to_tier == StorageClass.COLD
        assert migrations[0].estimated_savings_monthly == 40.0

    def test_warm_for_hot_monthly(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.MONTHLY,
            monthly_cost=100.0,
        )
        migrations = eng.recommend_tier_migrations()
        assert len(migrations) == 1
        assert migrations[0].to_tier == StorageClass.WARM
        assert migrations[0].estimated_savings_monthly == 20.0

    def test_no_migration_needed(self):
        eng = _engine()
        # DAILY access on HOT tier: no migration rule matches
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.DAILY,
            monthly_cost=100.0,
        )
        migrations = eng.recommend_tier_migrations()
        assert len(migrations) == 0


# ---------------------------------------------------------------------------
# get_migration
# ---------------------------------------------------------------------------


class TestGetMigration:
    def test_found(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.NEVER,
            monthly_cost=50.0,
        )
        migrations = eng.recommend_tier_migrations()
        assert eng.get_migration(migrations[0].id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_migration("nonexistent") is None


# ---------------------------------------------------------------------------
# update_migration_status
# ---------------------------------------------------------------------------


class TestUpdateMigrationStatus:
    def test_success(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.NEVER,
            monthly_cost=50.0,
        )
        migrations = eng.recommend_tier_migrations()
        result = eng.update_migration_status(migrations[0].id, MigrationStatus.COMPLETED)
        assert result is True
        assert migrations[0].status == MigrationStatus.COMPLETED

    def test_not_found(self):
        eng = _engine()
        assert eng.update_migration_status("bad-id", MigrationStatus.COMPLETED) is False


# ---------------------------------------------------------------------------
# detect_cold_data
# ---------------------------------------------------------------------------


class TestDetectColdData:
    def test_none(self):
        eng = _engine(cold_threshold_days=90)
        eng.register_asset("bucket-1", StorageClass.HOT, last_accessed_at=time.time())
        assert len(eng.detect_cold_data()) == 0

    def test_some_cold(self):
        eng = _engine(cold_threshold_days=90)
        # Last accessed 120 days ago => exceeds 90-day threshold
        old_ts = time.time() - (120 * 86400)
        eng.register_asset("bucket-1", StorageClass.HOT, last_accessed_at=old_ts)
        eng.register_asset("bucket-2", StorageClass.HOT, last_accessed_at=time.time())
        cold = eng.detect_cold_data()
        assert len(cold) == 1
        assert cold[0].asset_name == "bucket-1"


# ---------------------------------------------------------------------------
# estimate_savings
# ---------------------------------------------------------------------------


class TestEstimateSavings:
    def test_empty(self):
        eng = _engine()
        savings = eng.estimate_savings()
        assert savings["total_estimated_monthly_savings"] == 0.0
        assert savings["pending_migration_count"] == 0

    def test_with_data(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.NEVER,
            monthly_cost=100.0,
        )
        eng.recommend_tier_migrations()
        savings = eng.estimate_savings()
        assert savings["total_estimated_monthly_savings"] == 60.0
        assert savings["pending_migration_count"] == 1


# ---------------------------------------------------------------------------
# generate_optimization_report
# ---------------------------------------------------------------------------


class TestGenerateOptimizationReport:
    def test_basic_report(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            size_gb=500.0,
            monthly_cost=100.0,
            access_frequency=AccessFrequency.NEVER,
        )
        eng.recommend_tier_migrations()
        report = eng.generate_optimization_report()
        assert report.total_assets == 1
        assert report.total_size_gb == 500.0
        assert report.migration_count == 1
        assert report.estimated_total_savings > 0.0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.NEVER,
            monthly_cost=50.0,
        )
        eng.recommend_tier_migrations()
        eng.clear_data()
        assert len(eng._assets) == 0
        assert len(eng._migrations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assets"] == 0
        assert stats["total_migrations"] == 0

    def test_populated(self):
        eng = _engine()
        eng.register_asset(
            "bucket-1",
            StorageClass.HOT,
            access_frequency=AccessFrequency.NEVER,
            monthly_cost=50.0,
        )
        eng.recommend_tier_migrations()
        stats = eng.get_stats()
        assert stats["total_assets"] == 1
        assert stats["total_migrations"] == 1
