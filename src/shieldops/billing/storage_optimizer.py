"""Storage Tier Optimizer — storage class analysis, tier migration, cost optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StorageClass(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"
    GLACIER = "glacier"
    INFREQUENT = "infrequent"


class MigrationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AccessFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    NEVER = "never"


# --- Models ---


class StorageAsset(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str
    current_tier: StorageClass
    size_gb: float = 0.0
    last_accessed_at: float | None = None
    access_frequency: AccessFrequency = AccessFrequency.MONTHLY
    monthly_cost: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TierMigration(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str
    from_tier: StorageClass
    to_tier: StorageClass
    status: MigrationStatus = MigrationStatus.PENDING
    estimated_savings_monthly: float = 0.0
    created_at: float = Field(default_factory=time.time)


class StorageOptimizationReport(BaseModel):
    total_assets: int = 0
    total_size_gb: float = 0.0
    total_monthly_cost: float = 0.0
    migration_count: int = 0
    estimated_total_savings: float = 0.0
    tier_breakdown: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class StorageTierOptimizer:
    """Storage class analysis, tier migration recommendations, and cost optimization."""

    def __init__(
        self,
        max_assets: int = 100000,
        cold_threshold_days: int = 90,
    ) -> None:
        self._max_assets = max_assets
        self._cold_threshold_days = cold_threshold_days
        self._assets: list[StorageAsset] = []
        self._migrations: list[TierMigration] = []
        logger.info(
            "storage_optimizer.initialized",
            max_assets=max_assets,
            cold_threshold_days=cold_threshold_days,
        )

    def register_asset(
        self,
        asset_name: str,
        current_tier: StorageClass,
        size_gb: float = 0.0,
        last_accessed_at: float | None = None,
        access_frequency: AccessFrequency = AccessFrequency.MONTHLY,
        monthly_cost: float = 0.0,
    ) -> StorageAsset:
        asset = StorageAsset(
            asset_name=asset_name,
            current_tier=current_tier,
            size_gb=size_gb,
            last_accessed_at=last_accessed_at,
            access_frequency=access_frequency,
            monthly_cost=monthly_cost,
        )
        self._assets.append(asset)
        if len(self._assets) > self._max_assets:
            self._assets = self._assets[-self._max_assets :]
        logger.info(
            "storage_optimizer.asset_registered",
            asset_id=asset.id,
            asset_name=asset_name,
            current_tier=current_tier,
        )
        return asset

    def get_asset(self, asset_id: str) -> StorageAsset | None:
        for a in self._assets:
            if a.id == asset_id:
                return a
        return None

    def list_assets(
        self,
        current_tier: StorageClass | None = None,
        access_frequency: AccessFrequency | None = None,
        limit: int = 100,
    ) -> list[StorageAsset]:
        results = self._assets
        if current_tier is not None:
            results = [a for a in results if a.current_tier == current_tier]
        if access_frequency is not None:
            results = [a for a in results if a.access_frequency == access_frequency]
        return results[-limit:]

    def recommend_tier_migrations(self) -> list[TierMigration]:
        new_migrations: list[TierMigration] = []
        for asset in self._assets:
            to_tier: StorageClass | None = None
            savings_factor = 0.0

            if asset.access_frequency in (AccessFrequency.NEVER, AccessFrequency.YEARLY):
                to_tier = StorageClass.GLACIER
                savings_factor = 0.6
            elif asset.access_frequency == AccessFrequency.QUARTERLY:
                to_tier = StorageClass.COLD
                savings_factor = 0.4
            elif (
                asset.access_frequency == AccessFrequency.MONTHLY
                and asset.current_tier == StorageClass.HOT
            ):
                to_tier = StorageClass.WARM
                savings_factor = 0.2

            if to_tier is not None and to_tier != asset.current_tier:
                migration = TierMigration(
                    asset_id=asset.id,
                    from_tier=asset.current_tier,
                    to_tier=to_tier,
                    estimated_savings_monthly=round(asset.monthly_cost * savings_factor, 2),
                )
                new_migrations.append(migration)
                self._migrations.append(migration)

        logger.info(
            "storage_optimizer.migrations_recommended",
            count=len(new_migrations),
        )
        return new_migrations

    def get_migration(self, migration_id: str) -> TierMigration | None:
        for m in self._migrations:
            if m.id == migration_id:
                return m
        return None

    def update_migration_status(
        self,
        migration_id: str,
        status: MigrationStatus,
    ) -> bool:
        for m in self._migrations:
            if m.id == migration_id:
                m.status = status
                logger.info(
                    "storage_optimizer.migration_status_updated",
                    migration_id=migration_id,
                    status=status,
                )
                return True
        return False

    def detect_cold_data(self) -> list[StorageAsset]:
        now = time.time()
        threshold_seconds = self._cold_threshold_days * 86400
        return [
            a
            for a in self._assets
            if a.last_accessed_at is not None and (now - a.last_accessed_at) > threshold_seconds
        ]

    def estimate_savings(self) -> dict[str, Any]:
        pending = [m for m in self._migrations if m.status == MigrationStatus.PENDING]
        total = sum(m.estimated_savings_monthly for m in pending)
        by_target_tier: dict[str, float] = {}
        for m in pending:
            by_target_tier[m.to_tier] = (
                by_target_tier.get(m.to_tier, 0.0) + m.estimated_savings_monthly
            )
        return {
            "total_estimated_monthly_savings": round(total, 2),
            "pending_migration_count": len(pending),
            "by_target_tier": {k: round(v, 2) for k, v in by_target_tier.items()},
        }

    def generate_optimization_report(self) -> StorageOptimizationReport:
        tier_breakdown: dict[str, int] = {}
        total_size = 0.0
        total_cost = 0.0
        for a in self._assets:
            tier_breakdown[a.current_tier] = tier_breakdown.get(a.current_tier, 0) + 1
            total_size += a.size_gb
            total_cost += a.monthly_cost

        pending = [m for m in self._migrations if m.status == MigrationStatus.PENDING]
        estimated_savings = sum(m.estimated_savings_monthly for m in pending)

        recommendations: list[str] = []
        cold_assets = self.detect_cold_data()
        if cold_assets:
            recommendations.append(
                f"{len(cold_assets)} assets exceed {self._cold_threshold_days}-day "
                f"cold threshold — consider archival migration"
            )
        hot_count = tier_breakdown.get(StorageClass.HOT, 0)
        if hot_count > 0 and len(self._assets) > 0:
            hot_pct = hot_count / len(self._assets)
            if hot_pct > 0.5:
                recommendations.append(
                    f"{hot_pct:.0%} of assets in HOT tier — review access patterns "
                    f"for potential tier-down migration"
                )
        if pending:
            recommendations.append(
                f"{len(pending)} pending migrations could save ${estimated_savings:,.2f}/month"
            )

        return StorageOptimizationReport(
            total_assets=len(self._assets),
            total_size_gb=round(total_size, 2),
            total_monthly_cost=round(total_cost, 2),
            migration_count=len(self._migrations),
            estimated_total_savings=round(estimated_savings, 2),
            tier_breakdown=tier_breakdown,
            recommendations=recommendations,
        )

    def clear_data(self) -> None:
        self._assets.clear()
        self._migrations.clear()
        logger.info("storage_optimizer.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        tier_counts: dict[str, int] = {}
        for a in self._assets:
            tier_counts[a.current_tier] = tier_counts.get(a.current_tier, 0) + 1
        status_counts: dict[str, int] = {}
        for m in self._migrations:
            status_counts[m.status] = status_counts.get(m.status, 0) + 1
        return {
            "total_assets": len(self._assets),
            "total_migrations": len(self._migrations),
            "tier_distribution": tier_counts,
            "migration_status_distribution": status_counts,
            "max_assets": self._max_assets,
            "cold_threshold_days": self._cold_threshold_days,
        }
