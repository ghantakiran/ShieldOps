"""Maintenance Impact Analyzer — analyze impact of maintenance windows on SLAs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaintenanceType(StrEnum):
    PLANNED = "planned"
    EMERGENCY = "emergency"
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"


class ImpactLevel(StrEnum):
    FULL_OUTAGE = "full_outage"
    PARTIAL_DEGRADATION = "partial_degradation"
    MINOR_IMPACT = "minor_impact"
    NO_IMPACT = "no_impact"
    IMPROVED = "improved"


class MaintenanceOutcome(StrEnum):
    SUCCESSFUL = "successful"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    EXTENDED = "extended"
    CANCELLED = "cancelled"


# --- Models ---


class MaintenanceImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    window_id: str = ""
    maintenance_type: MaintenanceType = MaintenanceType.PLANNED
    impact_level: ImpactLevel = ImpactLevel.NO_IMPACT
    maintenance_outcome: MaintenanceOutcome = MaintenanceOutcome.SUCCESSFUL
    impact_minutes: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DowntimeAttribution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    window_id: str = ""
    maintenance_type: MaintenanceType = MaintenanceType.PLANNED
    downtime_minutes: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MaintenanceImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_attributions: int = 0
    high_impact_count: int = 0
    avg_impact_minutes: float = 0.0
    by_maintenance_type: dict[str, int] = Field(default_factory=dict)
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_impacted: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MaintenanceImpactAnalyzer:
    """Analyze impact of maintenance windows on SLAs, track downtime attribution."""

    def __init__(
        self,
        max_records: int = 200000,
        max_impact_minutes: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._max_impact_minutes = max_impact_minutes
        self._records: list[MaintenanceImpactRecord] = []
        self._attributions: list[DowntimeAttribution] = []
        logger.info(
            "maintenance_impact.initialized",
            max_records=max_records,
            max_impact_minutes=max_impact_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_maintenance(
        self,
        window_id: str,
        maintenance_type: MaintenanceType = MaintenanceType.PLANNED,
        impact_level: ImpactLevel = ImpactLevel.NO_IMPACT,
        maintenance_outcome: MaintenanceOutcome = MaintenanceOutcome.SUCCESSFUL,
        impact_minutes: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MaintenanceImpactRecord:
        record = MaintenanceImpactRecord(
            window_id=window_id,
            maintenance_type=maintenance_type,
            impact_level=impact_level,
            maintenance_outcome=maintenance_outcome,
            impact_minutes=impact_minutes,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "maintenance_impact.maintenance_recorded",
            record_id=record.id,
            window_id=window_id,
            maintenance_type=maintenance_type.value,
            impact_level=impact_level.value,
        )
        return record

    def get_maintenance(self, record_id: str) -> MaintenanceImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_maintenances(
        self,
        maintenance_type: MaintenanceType | None = None,
        impact_level: ImpactLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MaintenanceImpactRecord]:
        results = list(self._records)
        if maintenance_type is not None:
            results = [r for r in results if r.maintenance_type == maintenance_type]
        if impact_level is not None:
            results = [r for r in results if r.impact_level == impact_level]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_attribution(
        self,
        window_id: str,
        maintenance_type: MaintenanceType = MaintenanceType.PLANNED,
        downtime_minutes: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DowntimeAttribution:
        attribution = DowntimeAttribution(
            window_id=window_id,
            maintenance_type=maintenance_type,
            downtime_minutes=downtime_minutes,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._attributions.append(attribution)
        if len(self._attributions) > self._max_records:
            self._attributions = self._attributions[-self._max_records :]
        logger.info(
            "maintenance_impact.attribution_added",
            window_id=window_id,
            maintenance_type=maintenance_type.value,
            downtime_minutes=downtime_minutes,
        )
        return attribution

    # -- domain operations --------------------------------------------------

    def analyze_maintenance_impact(self) -> dict[str, Any]:
        """Group by maintenance type; return count and avg impact minutes per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.maintenance_type.value
            type_data.setdefault(key, []).append(r.impact_minutes)
        result: dict[str, Any] = {}
        for mtype, minutes in type_data.items():
            result[mtype] = {
                "count": len(minutes),
                "avg_impact_minutes": round(sum(minutes) / len(minutes), 2),
            }
        return result

    def identify_high_impact_windows(self) -> list[dict[str, Any]]:
        """Return records where impact_level is FULL_OUTAGE or PARTIAL_DEGRADATION."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_level in (
                ImpactLevel.FULL_OUTAGE,
                ImpactLevel.PARTIAL_DEGRADATION,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "window_id": r.window_id,
                        "maintenance_type": r.maintenance_type.value,
                        "impact_level": r.impact_level.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_impact_minutes(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg impact minutes."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.impact_minutes)
        results: list[dict[str, Any]] = []
        for service, minutes in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(minutes),
                    "avg_impact_minutes": round(sum(minutes) / len(minutes), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_minutes"], reverse=True)
        return results

    def detect_impact_trends(self) -> dict[str, Any]:
        """Split-half on downtime_minutes; delta threshold 5.0."""
        if len(self._attributions) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [a.downtime_minutes for a in self._attributions]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
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

    def generate_report(self) -> MaintenanceImpactReport:
        by_maintenance_type: dict[str, int] = {}
        by_impact_level: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_maintenance_type[r.maintenance_type.value] = (
                by_maintenance_type.get(r.maintenance_type.value, 0) + 1
            )
            by_impact_level[r.impact_level.value] = by_impact_level.get(r.impact_level.value, 0) + 1
            by_outcome[r.maintenance_outcome.value] = (
                by_outcome.get(r.maintenance_outcome.value, 0) + 1
            )
        high_impact_count = sum(
            1
            for r in self._records
            if r.impact_level in (ImpactLevel.FULL_OUTAGE, ImpactLevel.PARTIAL_DEGRADATION)
        )
        minutes = [r.impact_minutes for r in self._records]
        avg_minutes = round(sum(minutes) / len(minutes), 2) if minutes else 0.0
        rankings = self.rank_by_impact_minutes()
        top_impacted = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        high_impact_rate = (
            round(high_impact_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if avg_minutes > self._max_impact_minutes:
            recs.append(
                f"Average impact {avg_minutes} min exceeds threshold"
                f" ({self._max_impact_minutes} min)"
            )
        if high_impact_count > 0:
            recs.append(f"{high_impact_count} high-impact maintenance(s) detected — review windows")
        if high_impact_rate > 20.0:
            recs.append(f"High impact rate {high_impact_rate}% — consider rolling deployments")
        if not recs:
            recs.append("Maintenance impact is within acceptable limits")
        return MaintenanceImpactReport(
            total_records=len(self._records),
            total_attributions=len(self._attributions),
            high_impact_count=high_impact_count,
            avg_impact_minutes=avg_minutes,
            by_maintenance_type=by_maintenance_type,
            by_impact_level=by_impact_level,
            by_outcome=by_outcome,
            top_impacted=top_impacted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._attributions.clear()
        logger.info("maintenance_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.maintenance_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_attributions": len(self._attributions),
            "max_impact_minutes": self._max_impact_minutes,
            "maintenance_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_windows": len({r.window_id for r in self._records}),
        }
