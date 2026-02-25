"""API Versioning Health Monitor — track API version health and sunset compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VersionStatus(StrEnum):
    CURRENT = "current"
    SUPPORTED = "supported"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


class MigrationProgress(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    MOSTLY_COMPLETE = "mostly_complete"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class SunsetRisk(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OVERDUE = "overdue"
    CRITICAL = "critical"
    NO_DEADLINE = "no_deadline"


# --- Models ---


class APIVersionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    version: str = ""
    status: VersionStatus = VersionStatus.CURRENT
    consumer_count: int = 0
    sunset_days_remaining: int = -1
    traffic_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class VersionMigration(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    from_version: str = ""
    to_version: str = ""
    progress: MigrationProgress = MigrationProgress.NOT_STARTED
    consumer_migrated_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class APIVersionHealthReport(BaseModel):
    total_versions: int = 0
    total_migrations: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    deprecated_count: int = 0
    sunset_risk_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class APIVersionHealthMonitor:
    """Track API version health, migration progress, and sunset compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        sunset_warning_days: int = 30,
    ) -> None:
        self._max_records = max_records
        self._sunset_warning_days = sunset_warning_days
        self._records: list[APIVersionRecord] = []
        self._migrations: list[VersionMigration] = []
        logger.info(
            "api_version_health.initialized",
            max_records=max_records,
            sunset_warning_days=sunset_warning_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_version(
        self,
        api_name: str,
        version: str,
        status: VersionStatus = VersionStatus.CURRENT,
        consumer_count: int = 0,
        sunset_days_remaining: int = -1,
        traffic_pct: float = 0.0,
        details: str = "",
    ) -> APIVersionRecord:
        record = APIVersionRecord(
            api_name=api_name,
            version=version,
            status=status,
            consumer_count=consumer_count,
            sunset_days_remaining=sunset_days_remaining,
            traffic_pct=traffic_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "api_version_health.version_recorded",
            record_id=record.id,
            api_name=api_name,
            version=version,
            status=status.value,
        )
        return record

    def get_version(self, record_id: str) -> APIVersionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_versions(
        self,
        api_name: str | None = None,
        status: VersionStatus | None = None,
        limit: int = 50,
    ) -> list[APIVersionRecord]:
        results = list(self._records)
        if api_name is not None:
            results = [r for r in results if r.api_name == api_name]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    def record_migration(
        self,
        api_name: str,
        from_version: str,
        to_version: str,
        progress: MigrationProgress = MigrationProgress.NOT_STARTED,
        consumer_migrated_pct: float = 0.0,
        details: str = "",
    ) -> VersionMigration:
        migration = VersionMigration(
            api_name=api_name,
            from_version=from_version,
            to_version=to_version,
            progress=progress,
            consumer_migrated_pct=consumer_migrated_pct,
            details=details,
        )
        self._migrations.append(migration)
        if len(self._migrations) > self._max_records:
            self._migrations = self._migrations[-self._max_records :]
        logger.info(
            "api_version_health.migration_recorded",
            api_name=api_name,
            from_version=from_version,
            to_version=to_version,
            progress=progress.value,
        )
        return migration

    # -- domain operations -----------------------------------------------

    def identify_sunset_risks(self) -> list[dict[str, Any]]:
        """Find API versions approaching or past sunset deadlines."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in (VersionStatus.DEPRECATED, VersionStatus.SUNSET):
                if r.sunset_days_remaining < 0:
                    risk = SunsetRisk.NO_DEADLINE
                elif r.sunset_days_remaining == 0:
                    risk = SunsetRisk.OVERDUE
                elif r.sunset_days_remaining <= self._sunset_warning_days:
                    risk = SunsetRisk.AT_RISK
                else:
                    risk = SunsetRisk.ON_TRACK
                if risk != SunsetRisk.ON_TRACK:
                    results.append(
                        {
                            "api_name": r.api_name,
                            "version": r.version,
                            "status": r.status.value,
                            "sunset_days_remaining": r.sunset_days_remaining,
                            "consumer_count": r.consumer_count,
                            "risk": risk.value,
                        }
                    )
        results.sort(key=lambda x: x["sunset_days_remaining"])
        return results

    def track_migration_progress(self) -> list[dict[str, Any]]:
        """Track progress of all active migrations."""
        results: list[dict[str, Any]] = []
        for m in self._migrations:
            results.append(
                {
                    "api_name": m.api_name,
                    "from_version": m.from_version,
                    "to_version": m.to_version,
                    "progress": m.progress.value,
                    "consumer_migrated_pct": m.consumer_migrated_pct,
                }
            )
        results.sort(key=lambda x: x["consumer_migrated_pct"])
        return results

    def identify_zombie_versions(self) -> list[dict[str, Any]]:
        """Find retired/sunset versions still receiving traffic."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in (VersionStatus.SUNSET, VersionStatus.RETIRED) and (
                r.traffic_pct > 0 or r.consumer_count > 0
            ):
                results.append(
                    {
                        "api_name": r.api_name,
                        "version": r.version,
                        "status": r.status.value,
                        "traffic_pct": r.traffic_pct,
                        "consumer_count": r.consumer_count,
                    }
                )
        results.sort(key=lambda x: x["traffic_pct"], reverse=True)
        return results

    def rank_apis_by_version_health(self) -> list[dict[str, Any]]:
        """Rank APIs by version health."""
        api_versions: dict[str, list[str]] = {}
        api_deprecated: dict[str, int] = {}
        for r in self._records:
            api_versions.setdefault(r.api_name, []).append(r.status.value)
            if r.status in (VersionStatus.DEPRECATED, VersionStatus.SUNSET):
                api_deprecated[r.api_name] = api_deprecated.get(r.api_name, 0) + 1
        results: list[dict[str, Any]] = []
        for api, statuses in api_versions.items():
            dep = api_deprecated.get(api, 0)
            health = round(((len(statuses) - dep) / max(len(statuses), 1)) * 100, 2)
            results.append(
                {
                    "api_name": api,
                    "total_versions": len(statuses),
                    "deprecated_sunset": dep,
                    "health_score": health,
                }
            )
        results.sort(key=lambda x: x["health_score"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> APIVersionHealthReport:
        by_status: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        deprecated = sum(
            1 for r in self._records if r.status in (VersionStatus.DEPRECATED, VersionStatus.SUNSET)
        )
        sunset_risks = len(self.identify_sunset_risks())
        recs: list[str] = []
        if sunset_risks > 0:
            recs.append(f"{sunset_risks} API version(s) at sunset risk")
        zombies = len(self.identify_zombie_versions())
        if zombies > 0:
            recs.append(f"{zombies} zombie version(s) still receiving traffic")
        if not recs:
            recs.append("API version health is good")
        return APIVersionHealthReport(
            total_versions=len(self._records),
            total_migrations=len(self._migrations),
            by_status=by_status,
            deprecated_count=deprecated,
            sunset_risk_count=sunset_risks,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._migrations.clear()
        logger.info("api_version_health.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_versions": len(self._records),
            "total_migrations": len(self._migrations),
            "sunset_warning_days": self._sunset_warning_days,
            "status_distribution": status_dist,
            "unique_apis": len({r.api_name for r in self._records}),
        }
