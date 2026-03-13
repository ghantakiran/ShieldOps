"""Cascade Failure Analyzer — compute cascade depth,
detect trigger services, rank by propagation speed."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CascadePhase(StrEnum):
    TRIGGER = "trigger"
    PROPAGATION = "propagation"
    AMPLIFICATION = "amplification"
    STABILIZATION = "stabilization"


class FailureType(StrEnum):
    TIMEOUT = "timeout"
    OVERLOAD = "overload"
    DATA_CORRUPTION = "data_corruption"
    DEPENDENCY = "dependency"


class CascadeScope(StrEnum):
    SERVICE = "service"
    CLUSTER = "cluster"
    REGION = "region"
    GLOBAL = "global"


# --- Models ---


class CascadeFailureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    cascade_phase: CascadePhase = CascadePhase.TRIGGER
    failure_type: FailureType = FailureType.TIMEOUT
    cascade_scope: CascadeScope = CascadeScope.SERVICE
    cascade_depth: int = 0
    propagation_time_seconds: float = 0.0
    trigger_service: str = ""
    affected_services: int = 0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CascadeFailureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    cascade_phase: CascadePhase = CascadePhase.TRIGGER
    max_depth: int = 0
    propagation_speed: float = 0.0
    is_trigger: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CascadeFailureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_cascade_depth: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_failure_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CascadeFailureAnalyzer:
    """Compute cascade depth, detect cascade trigger services,
    rank cascades by propagation speed."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CascadeFailureRecord] = []
        self._analyses: dict[str, CascadeFailureAnalysis] = {}
        logger.info(
            "cascade_failure_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        cascade_phase: CascadePhase = CascadePhase.TRIGGER,
        failure_type: FailureType = FailureType.TIMEOUT,
        cascade_scope: CascadeScope = CascadeScope.SERVICE,
        cascade_depth: int = 0,
        propagation_time_seconds: float = 0.0,
        trigger_service: str = "",
        affected_services: int = 0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> CascadeFailureRecord:
        record = CascadeFailureRecord(
            incident_id=incident_id,
            cascade_phase=cascade_phase,
            failure_type=failure_type,
            cascade_scope=cascade_scope,
            cascade_depth=cascade_depth,
            propagation_time_seconds=propagation_time_seconds,
            trigger_service=trigger_service,
            affected_services=affected_services,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cascade_failure.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> CascadeFailureAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.incident_id == rec.incident_id]
        max_depth = max((r.cascade_depth for r in related), default=0)
        speed = (
            round(rec.affected_services / rec.propagation_time_seconds, 2)
            if rec.propagation_time_seconds > 0
            else 0.0
        )
        is_trigger = rec.cascade_phase == CascadePhase.TRIGGER
        analysis = CascadeFailureAnalysis(
            incident_id=rec.incident_id,
            cascade_phase=rec.cascade_phase,
            max_depth=max_depth,
            propagation_speed=speed,
            is_trigger=is_trigger,
            description=f"Cascade {rec.incident_id} depth {max_depth}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CascadeFailureReport:
        by_ph: dict[str, int] = {}
        by_ft: dict[str, int] = {}
        by_sc: dict[str, int] = {}
        depths: list[int] = []
        for r in self._records:
            by_ph[r.cascade_phase.value] = by_ph.get(r.cascade_phase.value, 0) + 1
            by_ft[r.failure_type.value] = by_ft.get(r.failure_type.value, 0) + 1
            by_sc[r.cascade_scope.value] = by_sc.get(r.cascade_scope.value, 0) + 1
            depths.append(r.cascade_depth)
        avg = round(sum(depths) / len(depths), 2) if depths else 0.0
        recs: list[str] = []
        global_count = by_sc.get("global", 0)
        if global_count > 0:
            recs.append(f"{global_count} global-scope cascades require attention")
        if not recs:
            recs.append("Cascade failures within acceptable scope")
        return CascadeFailureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_cascade_depth=avg,
            by_phase=by_ph,
            by_failure_type=by_ft,
            by_scope=by_sc,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            k = r.cascade_phase.value
            phase_dist[k] = phase_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "phase_distribution": phase_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cascade_failure_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_cascade_depth(self) -> list[dict[str, Any]]:
        """Compute cascade depth per incident."""
        incident_depths: dict[str, list[int]] = {}
        for r in self._records:
            incident_depths.setdefault(r.incident_id, []).append(r.cascade_depth)
        results: list[dict[str, Any]] = []
        for iid, depths in incident_depths.items():
            results.append(
                {
                    "incident_id": iid,
                    "max_depth": max(depths),
                    "avg_depth": round(sum(depths) / len(depths), 2),
                    "record_count": len(depths),
                }
            )
        results.sort(key=lambda x: x["max_depth"], reverse=True)
        return results

    def detect_cascade_trigger_services(self) -> list[dict[str, Any]]:
        """Detect services that frequently trigger cascades."""
        trigger_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.cascade_phase == CascadePhase.TRIGGER:
                k = r.trigger_service
                if k not in trigger_data:
                    trigger_data[k] = {"count": 0, "incidents": set(), "total_affected": 0}
                trigger_data[k]["count"] += 1
                trigger_data[k]["incidents"].add(r.incident_id)
                trigger_data[k]["total_affected"] += r.affected_services
        results: list[dict[str, Any]] = []
        for svc, data in trigger_data.items():
            results.append(
                {
                    "trigger_service": svc,
                    "trigger_count": data["count"],
                    "unique_incidents": len(data["incidents"]),
                    "total_affected_services": data["total_affected"],
                }
            )
        results.sort(key=lambda x: x["trigger_count"], reverse=True)
        return results

    def rank_cascades_by_propagation_speed(self) -> list[dict[str, Any]]:
        """Rank cascades by propagation speed."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            speed = (
                round(r.affected_services / r.propagation_time_seconds, 2)
                if r.propagation_time_seconds > 0
                else 0.0
            )
            results.append(
                {
                    "incident_id": r.incident_id,
                    "cascade_scope": r.cascade_scope.value,
                    "propagation_speed": speed,
                    "affected_services": r.affected_services,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["propagation_speed"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
