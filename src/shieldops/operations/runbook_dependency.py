"""Runbook Dependency Mapper — map runbook dependencies, detect circular and broken chains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyType(StrEnum):
    PREREQUISITE = "prerequisite"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    OPTIONAL = "optional"
    FALLBACK = "fallback"


class DependencyHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BROKEN = "broken"
    CIRCULAR = "circular"
    UNKNOWN = "unknown"


class RunbookScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    PLATFORM = "platform"
    REGION = "region"
    GLOBAL = "global"


# --- Models ---


class RunbookDepRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    dependency_type: DependencyType = DependencyType.PREREQUISITE
    dependency_health: DependencyHealth = DependencyHealth.UNKNOWN
    runbook_scope: RunbookScope = RunbookScope.SERVICE
    dependency_count: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    dependency_type: DependencyType = DependencyType.PREREQUISITE
    check_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookDependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_checks: int = 0
    broken_count: int = 0
    avg_dependency_count: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_broken: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookDependencyMapper:
    """Map runbook dependencies, detect circular and broken chains."""

    def __init__(
        self,
        max_records: int = 200000,
        max_broken_dependency_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_broken_dependency_pct = max_broken_dependency_pct
        self._records: list[RunbookDepRecord] = []
        self._metrics: list[DependencyCheck] = []
        logger.info(
            "runbook_dependency.initialized",
            max_records=max_records,
            max_broken_dependency_pct=max_broken_dependency_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_dependency(
        self,
        runbook_id: str,
        dependency_type: DependencyType = DependencyType.PREREQUISITE,
        dependency_health: DependencyHealth = DependencyHealth.UNKNOWN,
        runbook_scope: RunbookScope = RunbookScope.SERVICE,
        dependency_count: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RunbookDepRecord:
        record = RunbookDepRecord(
            runbook_id=runbook_id,
            dependency_type=dependency_type,
            dependency_health=dependency_health,
            runbook_scope=runbook_scope,
            dependency_count=dependency_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_dependency.dependency_recorded",
            record_id=record.id,
            runbook_id=runbook_id,
            dependency_type=dependency_type.value,
            dependency_health=dependency_health.value,
        )
        return record

    def get_dependency(self, record_id: str) -> RunbookDepRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dependencies(
        self,
        dep_type: DependencyType | None = None,
        health: DependencyHealth | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RunbookDepRecord]:
        results = list(self._records)
        if dep_type is not None:
            results = [r for r in results if r.dependency_type == dep_type]
        if health is not None:
            results = [r for r in results if r.dependency_health == health]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_check(
        self,
        runbook_id: str,
        dependency_type: DependencyType = DependencyType.PREREQUISITE,
        check_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DependencyCheck:
        metric = DependencyCheck(
            runbook_id=runbook_id,
            dependency_type=dependency_type,
            check_score=check_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "runbook_dependency.check_added",
            runbook_id=runbook_id,
            dependency_type=dependency_type.value,
            check_score=check_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_dependency_distribution(self) -> dict[str, Any]:
        """Group by dependency_type; return count and avg dependency_count."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dependency_type.value
            type_data.setdefault(key, []).append(r.dependency_count)
        result: dict[str, Any] = {}
        for dtype, counts in type_data.items():
            result[dtype] = {
                "count": len(counts),
                "avg_dependency_count": round(sum(counts) / len(counts), 2),
            }
        return result

    def identify_broken_dependencies(self) -> list[dict[str, Any]]:
        """Return records where dependency_health == BROKEN or CIRCULAR."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.dependency_health in (DependencyHealth.BROKEN, DependencyHealth.CIRCULAR):
                results.append(
                    {
                        "record_id": r.id,
                        "runbook_id": r.runbook_id,
                        "dependency_type": r.dependency_type.value,
                        "dependency_count": r.dependency_count,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_dependency_count(self) -> list[dict[str, Any]]:
        """Group by service, total dependency_count, sort descending."""
        svc_counts: dict[str, list[float]] = {}
        for r in self._records:
            svc_counts.setdefault(r.service, []).append(r.dependency_count)
        results: list[dict[str, Any]] = []
        for svc, counts in svc_counts.items():
            results.append(
                {
                    "service": svc,
                    "total_dependency_count": round(sum(counts), 2),
                }
            )
        results.sort(key=lambda x: x["total_dependency_count"], reverse=True)
        return results

    def detect_dependency_trends(self) -> dict[str, Any]:
        """Split-half comparison on check_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.check_score for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> RunbookDependencyReport:
        by_type: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_type[r.dependency_type.value] = by_type.get(r.dependency_type.value, 0) + 1
            by_health[r.dependency_health.value] = by_health.get(r.dependency_health.value, 0) + 1
            by_scope[r.runbook_scope.value] = by_scope.get(r.runbook_scope.value, 0) + 1
        broken_count = sum(
            1
            for r in self._records
            if r.dependency_health in (DependencyHealth.BROKEN, DependencyHealth.CIRCULAR)
        )
        counts = [r.dependency_count for r in self._records]
        avg_dependency_count = round(sum(counts) / len(counts), 2) if counts else 0.0
        rankings = self.rank_by_dependency_count()
        top_broken = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if broken_count > 0:
            recs.append(
                f"{broken_count} broken/circular dependency(ies) detected"
                f" (max acceptable {self._max_broken_dependency_pct}%)"
            )
        degraded = sum(1 for r in self._records if r.dependency_health == DependencyHealth.DEGRADED)
        if degraded > 0:
            recs.append(f"{degraded} degraded dependency(ies) — investigate")
        if not recs:
            recs.append("Runbook dependency health is acceptable")
        return RunbookDependencyReport(
            total_records=len(self._records),
            total_checks=len(self._metrics),
            broken_count=broken_count,
            avg_dependency_count=avg_dependency_count,
            by_type=by_type,
            by_health=by_health,
            by_scope=by_scope,
            top_broken=top_broken,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("runbook_dependency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dependency_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_broken_dependency_pct": self._max_broken_dependency_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
