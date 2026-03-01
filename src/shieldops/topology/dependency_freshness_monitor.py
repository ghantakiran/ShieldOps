"""Dependency Freshness Monitor — monitor dependency version freshness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FreshnessLevel(StrEnum):
    CURRENT = "current"
    RECENT = "recent"
    OUTDATED = "outdated"
    STALE = "stale"
    ABANDONED = "abandoned"


class DependencyCategory(StrEnum):
    RUNTIME = "runtime"
    BUILD = "build"
    TEST = "test"
    SECURITY = "security"
    OPTIONAL = "optional"


class UpdateUrgency(StrEnum):
    CRITICAL_SECURITY = "critical_security"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


# --- Models ---


class FreshnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_id: str = ""
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    dependency_category: DependencyCategory = DependencyCategory.RUNTIME
    update_urgency: UpdateUrgency = UpdateUrgency.NONE
    versions_behind: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FreshnessCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_id: str = ""
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    staleness_days: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyFreshnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_checks: int = 0
    stale_dependencies: int = 0
    avg_versions_behind: float = 0.0
    by_freshness: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    top_stale: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyFreshnessMonitor:
    """Monitor dependency version freshness, detect stale dependencies."""

    def __init__(
        self,
        max_records: int = 200000,
        max_stale_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_stale_pct = max_stale_pct
        self._records: list[FreshnessRecord] = []
        self._checks: list[FreshnessCheck] = []
        logger.info(
            "dependency_freshness_monitor.initialized",
            max_records=max_records,
            max_stale_pct=max_stale_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_freshness(
        self,
        dependency_id: str,
        freshness_level: FreshnessLevel = FreshnessLevel.CURRENT,
        dependency_category: DependencyCategory = DependencyCategory.RUNTIME,
        update_urgency: UpdateUrgency = UpdateUrgency.NONE,
        versions_behind: int = 0,
        service: str = "",
        team: str = "",
    ) -> FreshnessRecord:
        record = FreshnessRecord(
            dependency_id=dependency_id,
            freshness_level=freshness_level,
            dependency_category=dependency_category,
            update_urgency=update_urgency,
            versions_behind=versions_behind,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_freshness_monitor.freshness_recorded",
            record_id=record.id,
            dependency_id=dependency_id,
            freshness_level=freshness_level.value,
            dependency_category=dependency_category.value,
        )
        return record

    def get_freshness(self, record_id: str) -> FreshnessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_freshness(
        self,
        level: FreshnessLevel | None = None,
        category: DependencyCategory | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FreshnessRecord]:
        results = list(self._records)
        if level is not None:
            results = [r for r in results if r.freshness_level == level]
        if category is not None:
            results = [r for r in results if r.dependency_category == category]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_check(
        self,
        dependency_id: str,
        freshness_level: FreshnessLevel = FreshnessLevel.CURRENT,
        staleness_days: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FreshnessCheck:
        check = FreshnessCheck(
            dependency_id=dependency_id,
            freshness_level=freshness_level,
            staleness_days=staleness_days,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_records:
            self._checks = self._checks[-self._max_records :]
        logger.info(
            "dependency_freshness_monitor.check_added",
            dependency_id=dependency_id,
            freshness_level=freshness_level.value,
            staleness_days=staleness_days,
        )
        return check

    # -- domain operations --------------------------------------------------

    def analyze_freshness_distribution(self) -> dict[str, Any]:
        """Group by freshness level; return count and avg versions_behind."""
        level_data: dict[str, list[int]] = {}
        for r in self._records:
            key = r.freshness_level.value
            level_data.setdefault(key, []).append(r.versions_behind)
        result: dict[str, Any] = {}
        for level, versions in level_data.items():
            result[level] = {
                "count": len(versions),
                "avg_versions_behind": round(sum(versions) / len(versions), 2),
            }
        return result

    def identify_stale_dependencies(self) -> list[dict[str, Any]]:
        """Return records where freshness is STALE or ABANDONED."""
        stale_set = {FreshnessLevel.STALE, FreshnessLevel.ABANDONED}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.freshness_level in stale_set:
                results.append(
                    {
                        "record_id": r.id,
                        "dependency_id": r.dependency_id,
                        "freshness_level": r.freshness_level.value,
                        "dependency_category": r.dependency_category.value,
                        "versions_behind": r.versions_behind,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_staleness(self) -> list[dict[str, Any]]:
        """Group by service, avg versions_behind, sort descending."""
        svc_versions: dict[str, list[int]] = {}
        for r in self._records:
            svc_versions.setdefault(r.service, []).append(r.versions_behind)
        results: list[dict[str, Any]] = []
        for service, versions in svc_versions.items():
            results.append(
                {
                    "service": service,
                    "avg_versions_behind": round(sum(versions) / len(versions), 2),
                    "dependency_count": len(versions),
                }
            )
        results.sort(key=lambda x: x["avg_versions_behind"], reverse=True)
        return results

    def detect_freshness_trends(self) -> dict[str, Any]:
        """Split-half comparison on staleness_days; delta threshold 5.0."""
        if len(self._checks) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [c.staleness_days for c in self._checks]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DependencyFreshnessReport:
        by_freshness: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        for r in self._records:
            by_freshness[r.freshness_level.value] = by_freshness.get(r.freshness_level.value, 0) + 1
            by_category[r.dependency_category.value] = (
                by_category.get(r.dependency_category.value, 0) + 1
            )
            by_urgency[r.update_urgency.value] = by_urgency.get(r.update_urgency.value, 0) + 1
        stale_deps = sum(
            1
            for r in self._records
            if r.freshness_level in {FreshnessLevel.STALE, FreshnessLevel.ABANDONED}
        )
        avg_versions = (
            round(sum(r.versions_behind for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_staleness()
        top_stale = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if stale_deps > 0:
            recs.append(f"{stale_deps} stale dependency(ies) detected — review update schedule")
        stale_pct = round(stale_deps / len(self._records) * 100, 2) if self._records else 0.0
        if stale_pct > self._max_stale_pct:
            recs.append(
                f"Stale dependency rate {stale_pct}% exceeds threshold ({self._max_stale_pct}%)"
            )
        if not recs:
            recs.append("Dependency freshness levels are healthy")
        return DependencyFreshnessReport(
            total_records=len(self._records),
            total_checks=len(self._checks),
            stale_dependencies=stale_deps,
            avg_versions_behind=avg_versions,
            by_freshness=by_freshness,
            by_category=by_category,
            by_urgency=by_urgency,
            top_stale=top_stale,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._checks.clear()
        logger.info("dependency_freshness_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        freshness_dist: dict[str, int] = {}
        for r in self._records:
            key = r.freshness_level.value
            freshness_dist[key] = freshness_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_checks": len(self._checks),
            "max_stale_pct": self._max_stale_pct,
            "freshness_distribution": freshness_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
