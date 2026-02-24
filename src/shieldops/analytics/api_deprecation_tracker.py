"""API Deprecation Tracker — version lifecycle, sunset timelines, migration progress."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class APILifecycleStage(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET_PLANNED = "sunset_planned"
    SUNSET_IN_PROGRESS = "sunset_in_progress"
    RETIRED = "retired"


class MigrationStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    OPTED_OUT = "opted_out"


class DeprecationUrgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    OVERDUE = "overdue"


# --- Models ---


class APIVersionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    version: str = ""
    stage: APILifecycleStage = APILifecycleStage.ACTIVE
    deprecated_at: float = 0.0
    sunset_date: float = 0.0
    replacement_version: str = ""
    consumer_count: int = 0
    created_at: float = Field(default_factory=time.time)


class ConsumerMigration(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_version_id: str = ""
    consumer_name: str = ""
    status: MigrationStatus = MigrationStatus.NOT_STARTED
    started_at: float = 0.0
    completed_at: float = 0.0
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class DeprecationReport(BaseModel):
    total_apis: int = 0
    deprecated_count: int = 0
    sunset_count: int = 0
    retired_count: int = 0
    overdue_count: int = 0
    avg_migration_progress: float = 0.0
    stage_distribution: dict[str, int] = Field(default_factory=dict)
    urgency_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class APIDeprecationTracker:
    """Track API version lifecycles, sunset timelines, and consumer migration progress."""

    def __init__(
        self,
        max_records: int = 100000,
        sunset_warning_days: int = 30,
    ) -> None:
        self._max_records = max_records
        self._sunset_warning_days = sunset_warning_days
        self._api_versions: list[APIVersionRecord] = []
        self._migrations: list[ConsumerMigration] = []
        logger.info(
            "api_deprecation.initialized",
            max_records=max_records,
            sunset_warning_days=sunset_warning_days,
        )

    def register_api_version(
        self,
        api_name: str,
        version: str,
        stage: APILifecycleStage = APILifecycleStage.ACTIVE,
        deprecated_at: float = 0.0,
        sunset_date: float = 0.0,
        replacement_version: str = "",
        consumer_count: int = 0,
    ) -> APIVersionRecord:
        """Register an API version with its lifecycle metadata."""
        record = APIVersionRecord(
            api_name=api_name,
            version=version,
            stage=stage,
            deprecated_at=deprecated_at,
            sunset_date=sunset_date,
            replacement_version=replacement_version,
            consumer_count=consumer_count,
        )
        self._api_versions.append(record)
        if len(self._api_versions) > self._max_records:
            self._api_versions = self._api_versions[-self._max_records :]
        logger.info(
            "api_deprecation.version_registered",
            version_id=record.id,
            api_name=api_name,
            version=version,
            stage=stage,
        )
        return record

    def get_api_version(self, version_id: str) -> APIVersionRecord | None:
        """Retrieve a single API version record by ID."""
        for v in self._api_versions:
            if v.id == version_id:
                return v
        return None

    def list_api_versions(
        self,
        stage: APILifecycleStage | None = None,
        api_name: str | None = None,
        limit: int = 100,
    ) -> list[APIVersionRecord]:
        """List API version records with optional filtering."""
        results = list(self._api_versions)
        if stage is not None:
            results = [v for v in results if v.stage == stage]
        if api_name is not None:
            results = [v for v in results if v.api_name == api_name]
        return results[-limit:]

    def register_consumer_migration(
        self,
        api_version_id: str,
        consumer_name: str,
    ) -> ConsumerMigration:
        """Register a consumer that needs to migrate off a deprecated API version."""
        migration = ConsumerMigration(
            api_version_id=api_version_id,
            consumer_name=consumer_name,
        )
        self._migrations.append(migration)
        if len(self._migrations) > self._max_records:
            self._migrations = self._migrations[-self._max_records :]
        logger.info(
            "api_deprecation.migration_registered",
            migration_id=migration.id,
            api_version_id=api_version_id,
            consumer_name=consumer_name,
        )
        return migration

    def update_migration_status(
        self,
        migration_id: str,
        status: MigrationStatus,
        notes: str = "",
    ) -> bool:
        """Update the migration status for a consumer."""
        for m in self._migrations:
            if m.id == migration_id:
                m.status = status
                m.notes = notes
                if status == MigrationStatus.IN_PROGRESS and m.started_at == 0.0:
                    m.started_at = time.time()
                if status == MigrationStatus.COMPLETED and m.completed_at == 0.0:
                    m.completed_at = time.time()
                logger.info(
                    "api_deprecation.migration_updated",
                    migration_id=migration_id,
                    status=status,
                )
                return True
        return False

    def detect_overdue_sunsets(self) -> list[APIVersionRecord]:
        """Find API versions whose sunset date has passed but are not yet RETIRED.

        These represent APIs that should have been fully decommissioned but remain
        in a non-retired state, indicating stalled migration or oversight.
        """
        now = time.time()
        overdue = [
            v
            for v in self._api_versions
            if v.sunset_date > 0 and v.sunset_date < now and v.stage != APILifecycleStage.RETIRED
        ]
        overdue.sort(key=lambda v: v.sunset_date)
        logger.info(
            "api_deprecation.overdue_detected",
            overdue_count=len(overdue),
        )
        return overdue

    def calculate_migration_progress(self, api_version_id: str) -> dict[str, Any]:
        """Calculate migration completion progress for a specific API version.

        Returns counts per migration status and overall completion percentage.
        Completion is the ratio of COMPLETED migrations to total tracked consumers.
        """
        migrations = [m for m in self._migrations if m.api_version_id == api_version_id]
        total = len(migrations)
        if total == 0:
            return {
                "api_version_id": api_version_id,
                "total_consumers": 0,
                "status_breakdown": {},
                "completion_pct": 0.0,
            }

        status_counts: dict[str, int] = {}
        for m in migrations:
            key = m.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        completed = status_counts.get(MigrationStatus.COMPLETED.value, 0)
        completion_pct = round(completed / total * 100, 2)

        return {
            "api_version_id": api_version_id,
            "total_consumers": total,
            "status_breakdown": status_counts,
            "completion_pct": completion_pct,
        }

    def assess_deprecation_urgency(self, api_version_id: str) -> dict[str, Any]:
        """Assess how urgently consumers need to migrate off an API version.

        Urgency thresholds based on days until sunset:
            < 0 days   -> OVERDUE
            < 7 days   -> CRITICAL
            < 30 days  -> HIGH
            < 90 days  -> MEDIUM
            >= 90 days -> LOW
        """
        version = self.get_api_version(api_version_id)
        if version is None:
            return {
                "api_version_id": api_version_id,
                "urgency": DeprecationUrgency.LOW.value,
                "days_until_sunset": None,
                "message": "API version not found",
            }

        if version.sunset_date <= 0:
            return {
                "api_version_id": api_version_id,
                "api_name": version.api_name,
                "version": version.version,
                "urgency": DeprecationUrgency.LOW.value,
                "days_until_sunset": None,
                "message": "No sunset date configured",
            }

        now = time.time()
        days_remaining = (version.sunset_date - now) / 86400

        if days_remaining < 0:
            urgency = DeprecationUrgency.OVERDUE
            days_ago = abs(int(days_remaining))
            message = f"Sunset was {days_ago} day(s) ago — immediate action required"
        elif days_remaining < 7:
            urgency = DeprecationUrgency.CRITICAL
            message = f"Only {int(days_remaining)} day(s) until sunset — escalate migrations"
        elif days_remaining < 30:
            urgency = DeprecationUrgency.HIGH
            message = f"{int(days_remaining)} day(s) until sunset — accelerate migration efforts"
        elif days_remaining < 90:
            urgency = DeprecationUrgency.MEDIUM
            message = f"{int(days_remaining)} day(s) until sunset — plan migrations"
        else:
            urgency = DeprecationUrgency.LOW
            message = f"{int(days_remaining)} day(s) until sunset — migrations can proceed normally"

        progress = self.calculate_migration_progress(api_version_id)

        return {
            "api_version_id": api_version_id,
            "api_name": version.api_name,
            "version": version.version,
            "urgency": urgency.value,
            "days_until_sunset": round(days_remaining, 1),
            "migration_completion_pct": progress["completion_pct"],
            "consumer_count": version.consumer_count,
            "message": message,
        }

    def generate_deprecation_report(self) -> DeprecationReport:
        """Generate a comprehensive API deprecation and migration report."""
        total = len(self._api_versions)

        # Stage distribution
        stage_dist: dict[str, int] = {}
        for v in self._api_versions:
            key = v.stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1

        deprecated_count = stage_dist.get(APILifecycleStage.DEPRECATED.value, 0)
        sunset_count = stage_dist.get(APILifecycleStage.SUNSET_PLANNED.value, 0) + stage_dist.get(
            APILifecycleStage.SUNSET_IN_PROGRESS.value, 0
        )
        retired_count = stage_dist.get(APILifecycleStage.RETIRED.value, 0)

        # Overdue sunsets
        overdue = self.detect_overdue_sunsets()
        overdue_count = len(overdue)

        # Urgency distribution across non-active, non-retired APIs
        urgency_dist: dict[str, int] = {}
        migration_pcts: list[float] = []
        non_terminal = [
            v
            for v in self._api_versions
            if v.stage not in (APILifecycleStage.ACTIVE, APILifecycleStage.RETIRED)
        ]
        for v in non_terminal:
            assessment = self.assess_deprecation_urgency(v.id)
            urg = assessment["urgency"]
            urgency_dist[urg] = urgency_dist.get(urg, 0) + 1
            progress = self.calculate_migration_progress(v.id)
            migration_pcts.append(progress["completion_pct"])

        avg_migration = (
            round(sum(migration_pcts) / len(migration_pcts), 2) if migration_pcts else 0.0
        )

        # Build recommendations
        recommendations: list[str] = []
        if overdue_count > 0:
            overdue_names = [f"{v.api_name} {v.version}" for v in overdue[:5]]
            recommendations.append(
                f"{overdue_count} API version(s) are past sunset date: {', '.join(overdue_names)}"
            )

        critical_urgent = urgency_dist.get(DeprecationUrgency.CRITICAL.value, 0)
        if critical_urgent > 0:
            recommendations.append(
                f"{critical_urgent} API version(s) at CRITICAL urgency — sunset within 7 days"
            )

        blocked_migrations = sum(1 for m in self._migrations if m.status == MigrationStatus.BLOCKED)
        if blocked_migrations > 0:
            recommendations.append(
                f"{blocked_migrations} consumer migration(s) are BLOCKED — "
                f"investigate and resolve blockers"
            )

        if avg_migration < 50.0 and non_terminal:
            recommendations.append(
                f"Average migration progress is {avg_migration}% — increase migration velocity"
            )

        not_started = sum(1 for m in self._migrations if m.status == MigrationStatus.NOT_STARTED)
        if not_started > 0:
            recommendations.append(
                f"{not_started} consumer(s) have not started migration — "
                f"notify teams and set deadlines"
            )

        report = DeprecationReport(
            total_apis=total,
            deprecated_count=deprecated_count,
            sunset_count=sunset_count,
            retired_count=retired_count,
            overdue_count=overdue_count,
            avg_migration_progress=avg_migration,
            stage_distribution=stage_dist,
            urgency_distribution=urgency_dist,
            recommendations=recommendations,
        )
        logger.info(
            "api_deprecation.report_generated",
            total_apis=total,
            deprecated_count=deprecated_count,
            overdue_count=overdue_count,
            avg_migration_progress=avg_migration,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored API version records and migrations."""
        self._api_versions.clear()
        self._migrations.clear()
        logger.info("api_deprecation.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored API versions and migrations."""
        api_names: set[str] = set()
        stages: dict[str, int] = {}
        for v in self._api_versions:
            api_names.add(v.api_name)
            stages[v.stage.value] = stages.get(v.stage.value, 0) + 1

        migration_statuses: dict[str, int] = {}
        for m in self._migrations:
            key = m.status.value
            migration_statuses[key] = migration_statuses.get(key, 0) + 1

        return {
            "total_api_versions": len(self._api_versions),
            "total_migrations": len(self._migrations),
            "unique_api_names": len(api_names),
            "stage_distribution": stages,
            "migration_status_distribution": migration_statuses,
        }
