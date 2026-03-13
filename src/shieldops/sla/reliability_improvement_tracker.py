"""Reliability Improvement Tracker
compute improvement effectiveness, detect stalled
initiatives, rank initiatives by reliability gain."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class InitiativeStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STALLED = "stalled"


class ImprovementType(StrEnum):
    ARCHITECTURE = "architecture"
    PROCESS = "process"
    TOOLING = "tooling"
    TRAINING = "training"


class ImpactLevel(StrEnum):
    TRANSFORMATIVE = "transformative"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINIMAL = "minimal"


# --- Models ---


class ReliabilityImprovementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    initiative_id: str = ""
    initiative_status: InitiativeStatus = InitiativeStatus.PLANNED
    improvement_type: ImprovementType = ImprovementType.TOOLING
    impact_level: ImpactLevel = ImpactLevel.MODERATE
    reliability_before: float = 0.0
    reliability_after: float = 0.0
    effort_hours: float = 0.0
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReliabilityImprovementAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    initiative_id: str = ""
    effectiveness_score: float = 0.0
    initiative_status: InitiativeStatus = InitiativeStatus.PLANNED
    stalled: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReliabilityImprovementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_reliability_gain: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_improvement_type: dict[str, int] = Field(default_factory=dict)
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    stalled_initiatives: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReliabilityImprovementTracker:
    """Compute improvement effectiveness, detect stalled
    initiatives, rank by reliability gain."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ReliabilityImprovementRecord] = []
        self._analyses: dict[str, ReliabilityImprovementAnalysis] = {}
        logger.info(
            "reliability_improvement_tracker.init",
            max_records=max_records,
        )

    def add_record(
        self,
        initiative_id: str = "",
        initiative_status: InitiativeStatus = InitiativeStatus.PLANNED,
        improvement_type: ImprovementType = ImprovementType.TOOLING,
        impact_level: ImpactLevel = ImpactLevel.MODERATE,
        reliability_before: float = 0.0,
        reliability_after: float = 0.0,
        effort_hours: float = 0.0,
        team: str = "",
        description: str = "",
    ) -> ReliabilityImprovementRecord:
        record = ReliabilityImprovementRecord(
            initiative_id=initiative_id,
            initiative_status=initiative_status,
            improvement_type=improvement_type,
            impact_level=impact_level,
            reliability_before=reliability_before,
            reliability_after=reliability_after,
            effort_hours=effort_hours,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reliability_improvement_tracker.record_added",
            record_id=record.id,
            initiative_id=initiative_id,
        )
        return record

    def process(self, key: str) -> ReliabilityImprovementAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.initiative_id == rec.initiative_id)
        gain = rec.reliability_after - rec.reliability_before
        effectiveness = round((gain / rec.effort_hours) if rec.effort_hours else 0.0, 2)
        stalled = rec.initiative_status == InitiativeStatus.STALLED
        analysis = ReliabilityImprovementAnalysis(
            initiative_id=rec.initiative_id,
            effectiveness_score=effectiveness,
            initiative_status=rec.initiative_status,
            stalled=stalled,
            data_points=points,
            description=f"Initiative {rec.initiative_id} effectiveness {effectiveness}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ReliabilityImprovementReport:
        by_s: dict[str, int] = {}
        by_it: dict[str, int] = {}
        by_il: dict[str, int] = {}
        gains: list[float] = []
        for r in self._records:
            k = r.initiative_status.value
            by_s[k] = by_s.get(k, 0) + 1
            k2 = r.improvement_type.value
            by_it[k2] = by_it.get(k2, 0) + 1
            k3 = r.impact_level.value
            by_il[k3] = by_il.get(k3, 0) + 1
            gains.append(r.reliability_after - r.reliability_before)
        avg = round(sum(gains) / len(gains), 2) if gains else 0.0
        stalled = list(
            {
                r.initiative_id
                for r in self._records
                if r.initiative_status == InitiativeStatus.STALLED
            }
        )[:10]
        recs: list[str] = []
        if stalled:
            recs.append(f"{len(stalled)} stalled improvement initiatives")
        if not recs:
            recs.append("All improvement initiatives progressing")
        return ReliabilityImprovementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reliability_gain=avg,
            by_status=by_s,
            by_improvement_type=by_it,
            by_impact_level=by_il,
            stalled_initiatives=stalled,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            k = r.initiative_status.value
            status_dist[k] = status_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "status_distribution": status_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("reliability_improvement_tracker.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_improvement_effectiveness(
        self,
    ) -> list[dict[str, Any]]:
        """Compute improvement effectiveness per initiative."""
        init_data: dict[str, dict[str, float]] = {}
        init_types: dict[str, str] = {}
        for r in self._records:
            if r.initiative_id not in init_data:
                init_data[r.initiative_id] = {
                    "gain": 0.0,
                    "effort": 0.0,
                    "count": 0,
                }
            gain = r.reliability_after - r.reliability_before
            init_data[r.initiative_id]["gain"] += gain
            init_data[r.initiative_id]["effort"] += r.effort_hours
            init_data[r.initiative_id]["count"] += 1
            init_types[r.initiative_id] = r.improvement_type.value
        results: list[dict[str, Any]] = []
        for iid, data in init_data.items():
            effectiveness = round((data["gain"] / data["effort"]) if data["effort"] else 0.0, 2)
            results.append(
                {
                    "initiative_id": iid,
                    "improvement_type": init_types[iid],
                    "total_gain": round(data["gain"], 2),
                    "total_effort_hours": round(data["effort"], 2),
                    "effectiveness": effectiveness,
                    "data_points": int(data["count"]),
                }
            )
        results.sort(key=lambda x: x["effectiveness"], reverse=True)
        return results

    def detect_stalled_initiatives(
        self,
    ) -> list[dict[str, Any]]:
        """Detect stalled improvement initiatives."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.initiative_status == InitiativeStatus.STALLED and r.initiative_id not in seen:
                seen.add(r.initiative_id)
                results.append(
                    {
                        "initiative_id": r.initiative_id,
                        "improvement_type": r.improvement_type.value,
                        "effort_hours": r.effort_hours,
                        "reliability_gain": round(r.reliability_after - r.reliability_before, 2),
                    }
                )
        results.sort(key=lambda x: x["effort_hours"], reverse=True)
        return results

    def rank_initiatives_by_reliability_gain(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all initiatives by reliability gain."""
        init_data: dict[str, float] = {}
        init_types: dict[str, str] = {}
        for r in self._records:
            gain = r.reliability_after - r.reliability_before
            init_data[r.initiative_id] = init_data.get(r.initiative_id, 0.0) + gain
            init_types[r.initiative_id] = r.improvement_type.value
        results: list[dict[str, Any]] = []
        for iid, total in init_data.items():
            results.append(
                {
                    "initiative_id": iid,
                    "improvement_type": init_types[iid],
                    "total_gain": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_gain"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
