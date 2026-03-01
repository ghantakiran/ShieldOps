"""Incident Blast Radius Analyzer — assess blast radius scope, impact vectors, and containment."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BlastRadiusScope(StrEnum):
    SINGLE_SERVICE = "single_service"
    MULTI_SERVICE = "multi_service"
    TEAM_WIDE = "team_wide"
    REGION_WIDE = "region_wide"
    PLATFORM_WIDE = "platform_wide"


class ImpactVector(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    DATA_INTEGRITY = "data_integrity"
    SECURITY = "security"
    CUSTOMER_EXPERIENCE = "customer_experience"


class ContainmentStatus(StrEnum):
    CONTAINED = "contained"
    SPREADING = "spreading"
    MITIGATED = "mitigated"
    ESCALATING = "escalating"
    RESOLVED = "resolved"


# --- Models ---


class BlastRadiusRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    blast_radius_scope: BlastRadiusScope = BlastRadiusScope.SINGLE_SERVICE
    impact_vector: ImpactVector = ImpactVector.AVAILABILITY
    containment_status: ContainmentStatus = ContainmentStatus.CONTAINED
    blast_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactZone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    zone_name: str = ""
    blast_radius_scope: BlastRadiusScope = BlastRadiusScope.SINGLE_SERVICE
    impact_threshold: float = 0.0
    avg_blast_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BlastRadiusReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_zones: int = 0
    high_radius_incidents: int = 0
    avg_blast_score: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_impact_vector: dict[str, int] = Field(default_factory=dict)
    by_containment: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentBlastRadiusAnalyzer:
    """Assess blast radius scope, impact vectors, and containment for incidents."""

    def __init__(
        self,
        max_records: int = 200000,
        max_blast_radius_score: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._max_blast_radius_score = max_blast_radius_score
        self._records: list[BlastRadiusRecord] = []
        self._zones: list[ImpactZone] = []
        logger.info(
            "blast_radius.initialized",
            max_records=max_records,
            max_blast_radius_score=max_blast_radius_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_blast_radius(
        self,
        incident_id: str,
        blast_radius_scope: BlastRadiusScope = BlastRadiusScope.SINGLE_SERVICE,
        impact_vector: ImpactVector = ImpactVector.AVAILABILITY,
        containment_status: ContainmentStatus = ContainmentStatus.CONTAINED,
        blast_score: float = 0.0,
        team: str = "",
    ) -> BlastRadiusRecord:
        record = BlastRadiusRecord(
            incident_id=incident_id,
            blast_radius_scope=blast_radius_scope,
            impact_vector=impact_vector,
            containment_status=containment_status,
            blast_score=blast_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "blast_radius.recorded",
            record_id=record.id,
            incident_id=incident_id,
            blast_radius_scope=blast_radius_scope.value,
            impact_vector=impact_vector.value,
        )
        return record

    def get_blast_radius(self, record_id: str) -> BlastRadiusRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_blast_radii(
        self,
        scope: BlastRadiusScope | None = None,
        vector: ImpactVector | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BlastRadiusRecord]:
        results = list(self._records)
        if scope is not None:
            results = [r for r in results if r.blast_radius_scope == scope]
        if vector is not None:
            results = [r for r in results if r.impact_vector == vector]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_impact_zone(
        self,
        zone_name: str,
        blast_radius_scope: BlastRadiusScope = BlastRadiusScope.SINGLE_SERVICE,
        impact_threshold: float = 0.0,
        avg_blast_score: float = 0.0,
        description: str = "",
    ) -> ImpactZone:
        zone = ImpactZone(
            zone_name=zone_name,
            blast_radius_scope=blast_radius_scope,
            impact_threshold=impact_threshold,
            avg_blast_score=avg_blast_score,
            description=description,
        )
        self._zones.append(zone)
        if len(self._zones) > self._max_records:
            self._zones = self._zones[-self._max_records :]
        logger.info(
            "blast_radius.zone_added",
            zone_name=zone_name,
            blast_radius_scope=blast_radius_scope.value,
            impact_threshold=impact_threshold,
        )
        return zone

    # -- domain operations --------------------------------------------------

    def analyze_blast_patterns(self) -> dict[str, Any]:
        """Group by scope; return count and avg blast score per scope level."""
        scope_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.blast_radius_scope.value
            scope_data.setdefault(key, []).append(r.blast_score)
        result: dict[str, Any] = {}
        for scope, scores in scope_data.items():
            result[scope] = {
                "count": len(scores),
                "avg_blast_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_radius_incidents(self) -> list[dict[str, Any]]:
        """Return records where scope is REGION_WIDE or PLATFORM_WIDE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.blast_radius_scope in (
                BlastRadiusScope.REGION_WIDE,
                BlastRadiusScope.PLATFORM_WIDE,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "blast_radius_scope": r.blast_radius_scope.value,
                        "blast_score": r.blast_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_blast_score(self) -> list[dict[str, Any]]:
        """Group by team, avg blast score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.blast_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_blast_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_blast_score"], reverse=True)
        return results

    def detect_containment_failures(self) -> dict[str, Any]:
        """Split-half on avg_blast_score; delta threshold 5.0."""
        if len(self._zones) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [z.avg_blast_score for z in self._zones]
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

    def generate_report(self) -> BlastRadiusReport:
        by_scope: dict[str, int] = {}
        by_impact_vector: dict[str, int] = {}
        by_containment: dict[str, int] = {}
        for r in self._records:
            by_scope[r.blast_radius_scope.value] = by_scope.get(r.blast_radius_scope.value, 0) + 1
            by_impact_vector[r.impact_vector.value] = (
                by_impact_vector.get(r.impact_vector.value, 0) + 1
            )
            by_containment[r.containment_status.value] = (
                by_containment.get(r.containment_status.value, 0) + 1
            )
        high_count = sum(
            1
            for r in self._records
            if r.blast_radius_scope
            in (BlastRadiusScope.REGION_WIDE, BlastRadiusScope.PLATFORM_WIDE)
        )
        avg_score = (
            round(sum(r.blast_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_blast_score()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_score > self._max_blast_radius_score:
            recs.append(
                f"Avg blast score {avg_score} exceeds threshold ({self._max_blast_radius_score})"
            )
        if high_count > 0:
            recs.append(f"{high_count} high-radius incident(s) detected — review containment")
        if not recs:
            recs.append("Blast radius is within acceptable limits")
        return BlastRadiusReport(
            total_records=len(self._records),
            total_zones=len(self._zones),
            high_radius_incidents=high_count,
            avg_blast_score=avg_score,
            by_scope=by_scope,
            by_impact_vector=by_impact_vector,
            by_containment=by_containment,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._zones.clear()
        logger.info("blast_radius.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.blast_radius_scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_zones": len(self._zones),
            "max_blast_radius_score": self._max_blast_radius_score,
            "scope_distribution": scope_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
