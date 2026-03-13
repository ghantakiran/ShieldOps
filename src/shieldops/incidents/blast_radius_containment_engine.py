"""Blast Radius Containment Engine — compute containment effectiveness,
detect blast radius expansion, rank incidents by blast scope."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContainmentStatus(StrEnum):
    CONTAINED = "contained"
    SPREADING = "spreading"
    ISOLATED = "isolated"
    UNKNOWN = "unknown"


class BlastLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContainmentStrategy(StrEnum):
    NETWORK_ISOLATION = "network_isolation"
    SERVICE_SHUTDOWN = "service_shutdown"
    TRAFFIC_DIVERT = "traffic_divert"
    RATE_LIMIT = "rate_limit"


# --- Models ---


class BlastRadiusRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    containment_status: ContainmentStatus = ContainmentStatus.UNKNOWN
    blast_level: BlastLevel = BlastLevel.MEDIUM
    containment_strategy: ContainmentStrategy = ContainmentStrategy.NETWORK_ISOLATION
    affected_services: int = 0
    containment_time_seconds: float = 0.0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BlastRadiusAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    containment_status: ContainmentStatus = ContainmentStatus.UNKNOWN
    effectiveness_score: float = 0.0
    is_expanding: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BlastRadiusReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_affected_services: float = 0.0
    by_containment_status: dict[str, int] = Field(default_factory=dict)
    by_blast_level: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class BlastRadiusContainmentEngine:
    """Compute containment effectiveness, detect blast radius
    expansion, rank incidents by blast scope."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BlastRadiusRecord] = []
        self._analyses: dict[str, BlastRadiusAnalysis] = {}
        logger.info(
            "blast_radius_containment_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        containment_status: ContainmentStatus = ContainmentStatus.UNKNOWN,
        blast_level: BlastLevel = BlastLevel.MEDIUM,
        containment_strategy: ContainmentStrategy = ContainmentStrategy.NETWORK_ISOLATION,
        affected_services: int = 0,
        containment_time_seconds: float = 0.0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> BlastRadiusRecord:
        record = BlastRadiusRecord(
            incident_id=incident_id,
            containment_status=containment_status,
            blast_level=blast_level,
            containment_strategy=containment_strategy,
            affected_services=affected_services,
            containment_time_seconds=containment_time_seconds,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "blast_radius_containment.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> BlastRadiusAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_expanding = rec.containment_status == ContainmentStatus.SPREADING
        effectiveness = (
            1.0
            if rec.containment_status == ContainmentStatus.CONTAINED
            else (0.5 if rec.containment_status == ContainmentStatus.ISOLATED else 0.0)
        )
        analysis = BlastRadiusAnalysis(
            incident_id=rec.incident_id,
            containment_status=rec.containment_status,
            effectiveness_score=round(effectiveness, 2),
            is_expanding=is_expanding,
            description=f"Incident {rec.incident_id} blast level {rec.blast_level.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> BlastRadiusReport:
        by_cs: dict[str, int] = {}
        by_bl: dict[str, int] = {}
        by_st: dict[str, int] = {}
        svc_counts: list[int] = []
        for r in self._records:
            by_cs[r.containment_status.value] = by_cs.get(r.containment_status.value, 0) + 1
            by_bl[r.blast_level.value] = by_bl.get(r.blast_level.value, 0) + 1
            by_st[r.containment_strategy.value] = by_st.get(r.containment_strategy.value, 0) + 1
            svc_counts.append(r.affected_services)
        avg = round(sum(svc_counts) / len(svc_counts), 2) if svc_counts else 0.0
        recs: list[str] = []
        spreading = by_cs.get("spreading", 0)
        if spreading > 0:
            recs.append(f"{spreading} incidents with expanding blast radius")
        if not recs:
            recs.append("Blast radius containment within acceptable limits")
        return BlastRadiusReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_affected_services=avg,
            by_containment_status=by_cs,
            by_blast_level=by_bl,
            by_strategy=by_st,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            k = r.containment_status.value
            status_dist[k] = status_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "containment_status_distribution": status_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("blast_radius_containment_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_containment_effectiveness(self) -> list[dict[str, Any]]:
        """Compute containment effectiveness per strategy."""
        strategy_results: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = r.containment_strategy.value
            if k not in strategy_results:
                strategy_results[k] = {"contained": 0, "total": 0, "times": []}
            strategy_results[k]["total"] += 1
            if r.containment_status == ContainmentStatus.CONTAINED:
                strategy_results[k]["contained"] += 1
            strategy_results[k]["times"].append(r.containment_time_seconds)
        results: list[dict[str, Any]] = []
        for strategy, data in strategy_results.items():
            rate = round(data["contained"] / data["total"], 2) if data["total"] > 0 else 0.0
            avg_time = round(sum(data["times"]) / len(data["times"]), 2) if data["times"] else 0.0
            results.append(
                {
                    "strategy": strategy,
                    "effectiveness_rate": rate,
                    "avg_containment_time": avg_time,
                    "total_uses": data["total"],
                }
            )
        results.sort(key=lambda x: x["effectiveness_rate"], reverse=True)
        return results

    def detect_blast_radius_expansion(self) -> list[dict[str, Any]]:
        """Detect incidents where blast radius is expanding."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.containment_status == ContainmentStatus.SPREADING and r.incident_id not in seen:
                seen.add(r.incident_id)
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "blast_level": r.blast_level.value,
                        "affected_services": r.affected_services,
                        "service": r.service,
                    }
                )
        results.sort(key=lambda x: x["affected_services"], reverse=True)
        return results

    def rank_incidents_by_blast_scope(self) -> list[dict[str, Any]]:
        """Rank incidents by total blast scope."""
        incident_data: dict[str, int] = {}
        incident_levels: dict[str, str] = {}
        for r in self._records:
            incident_data[r.incident_id] = max(
                incident_data.get(r.incident_id, 0), r.affected_services
            )
            incident_levels[r.incident_id] = r.blast_level.value
        results: list[dict[str, Any]] = []
        for iid, svc_count in incident_data.items():
            results.append(
                {
                    "incident_id": iid,
                    "blast_level": incident_levels[iid],
                    "max_affected_services": svc_count,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["max_affected_services"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
