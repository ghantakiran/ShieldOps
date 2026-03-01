"""Capacity Headroom Analyzer — analyze remaining capacity headroom, predict exhaustion."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    CONNECTIONS = "connections"


class HeadroomLevel(StrEnum):
    AMPLE = "ample"
    ADEQUATE = "adequate"
    TIGHT = "tight"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


class GrowthRate(StrEnum):
    RAPID = "rapid"
    MODERATE = "moderate"
    SLOW = "slow"
    STABLE = "stable"
    DECLINING = "declining"


# --- Models ---


class HeadroomRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: ResourceType = ResourceType.CPU
    headroom_level: HeadroomLevel = HeadroomLevel.AMPLE
    growth_rate: GrowthRate = GrowthRate.STABLE
    headroom_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class HeadroomProjection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: ResourceType = ResourceType.CPU
    projected_days: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityHeadroomReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_projections: int = 0
    critical_resources: int = 0
    avg_headroom_pct: float = 0.0
    by_resource_type: dict[str, int] = Field(default_factory=dict)
    by_headroom: dict[str, int] = Field(default_factory=dict)
    by_growth: dict[str, int] = Field(default_factory=dict)
    top_at_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityHeadroomAnalyzer:
    """Analyze remaining capacity headroom, predict when capacity runs out."""

    def __init__(
        self,
        max_records: int = 200000,
        min_headroom_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._min_headroom_pct = min_headroom_pct
        self._records: list[HeadroomRecord] = []
        self._projections: list[HeadroomProjection] = []
        logger.info(
            "capacity_headroom.initialized",
            max_records=max_records,
            min_headroom_pct=min_headroom_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_headroom(
        self,
        resource_id: str,
        resource_type: ResourceType = ResourceType.CPU,
        headroom_level: HeadroomLevel = HeadroomLevel.AMPLE,
        growth_rate: GrowthRate = GrowthRate.STABLE,
        headroom_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> HeadroomRecord:
        record = HeadroomRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            headroom_level=headroom_level,
            growth_rate=growth_rate,
            headroom_pct=headroom_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_headroom.headroom_recorded",
            record_id=record.id,
            resource_id=resource_id,
            resource_type=resource_type.value,
            headroom_level=headroom_level.value,
        )
        return record

    def get_headroom(self, record_id: str) -> HeadroomRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_headroom(
        self,
        resource_type: ResourceType | None = None,
        level: HeadroomLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[HeadroomRecord]:
        results = list(self._records)
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        if level is not None:
            results = [r for r in results if r.headroom_level == level]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_projection(
        self,
        resource_id: str,
        resource_type: ResourceType = ResourceType.CPU,
        projected_days: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> HeadroomProjection:
        projection = HeadroomProjection(
            resource_id=resource_id,
            resource_type=resource_type,
            projected_days=projected_days,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._projections.append(projection)
        if len(self._projections) > self._max_records:
            self._projections = self._projections[-self._max_records :]
        logger.info(
            "capacity_headroom.projection_added",
            resource_id=resource_id,
            resource_type=resource_type.value,
            projected_days=projected_days,
        )
        return projection

    # -- domain operations --------------------------------------------------

    def analyze_headroom_distribution(self) -> dict[str, Any]:
        """Group by resource_type; return count and avg headroom_pct."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.resource_type.value
            type_data.setdefault(key, []).append(r.headroom_pct)
        result: dict[str, Any] = {}
        for rtype, pcts in type_data.items():
            result[rtype] = {
                "count": len(pcts),
                "avg_headroom_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_critical_resources(self) -> list[dict[str, Any]]:
        """Return records where headroom_level is CRITICAL or EXHAUSTED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.headroom_level in {HeadroomLevel.CRITICAL, HeadroomLevel.EXHAUSTED}:
                results.append(
                    {
                        "record_id": r.id,
                        "resource_id": r.resource_id,
                        "resource_type": r.resource_type.value,
                        "headroom_level": r.headroom_level.value,
                        "headroom_pct": r.headroom_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_headroom(self) -> list[dict[str, Any]]:
        """Group by resource_id, avg headroom_pct, sort ascending."""
        resource_pcts: dict[str, list[float]] = {}
        for r in self._records:
            resource_pcts.setdefault(r.resource_id, []).append(r.headroom_pct)
        results: list[dict[str, Any]] = []
        for resource_id, pcts in resource_pcts.items():
            results.append(
                {
                    "resource_id": resource_id,
                    "avg_headroom_pct": round(sum(pcts) / len(pcts), 2),
                }
            )
        results.sort(key=lambda x: x["avg_headroom_pct"])
        return results

    def detect_headroom_trends(self) -> dict[str, Any]:
        """Split-half comparison on projected_days; delta threshold 5.0."""
        if len(self._projections) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [p.projected_days for p in self._projections]
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

    def generate_report(self) -> CapacityHeadroomReport:
        by_resource_type: dict[str, int] = {}
        by_headroom: dict[str, int] = {}
        by_growth: dict[str, int] = {}
        for r in self._records:
            by_resource_type[r.resource_type.value] = (
                by_resource_type.get(r.resource_type.value, 0) + 1
            )
            by_headroom[r.headroom_level.value] = by_headroom.get(r.headroom_level.value, 0) + 1
            by_growth[r.growth_rate.value] = by_growth.get(r.growth_rate.value, 0) + 1
        critical_resources = sum(
            1
            for r in self._records
            if r.headroom_level in {HeadroomLevel.CRITICAL, HeadroomLevel.EXHAUSTED}
        )
        pcts = [r.headroom_pct for r in self._records]
        avg_headroom_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        rankings = self.rank_by_headroom()
        top_at_risk = [rk["resource_id"] for rk in rankings[:5]]
        recs: list[str] = []
        if self._records:
            low_headroom = sum(1 for r in self._records if r.headroom_pct < self._min_headroom_pct)
            if low_headroom > 0:
                recs.append(
                    f"{low_headroom} resource(s) below minimum headroom ({self._min_headroom_pct}%)"
                )
        if critical_resources > 0:
            recs.append(f"{critical_resources} critical/exhausted resource(s) — scale or optimize")
        if not recs:
            recs.append("Capacity headroom levels are healthy")
        return CapacityHeadroomReport(
            total_records=len(self._records),
            total_projections=len(self._projections),
            critical_resources=critical_resources,
            avg_headroom_pct=avg_headroom_pct,
            by_resource_type=by_resource_type,
            by_headroom=by_headroom,
            by_growth=by_growth,
            top_at_risk=top_at_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._projections.clear()
        logger.info("capacity_headroom.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_projections": len(self._projections),
            "min_headroom_pct": self._min_headroom_pct,
            "resource_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
