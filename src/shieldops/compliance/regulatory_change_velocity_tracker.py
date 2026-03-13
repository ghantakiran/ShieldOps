"""Regulatory Change Velocity Tracker
compute change velocity by jurisdiction, detect high-impact
changes, rank regulations by change frequency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Jurisdiction(StrEnum):
    US_FEDERAL = "us_federal"
    EU = "eu"
    UK = "uk"
    APAC = "apac"


class ChangeType(StrEnum):
    NEW_REQUIREMENT = "new_requirement"
    AMENDMENT = "amendment"
    REPEAL = "repeal"
    GUIDANCE = "guidance"


# --- Models ---


class RegulatoryChangeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_id: str = ""
    change_impact: ChangeImpact = ChangeImpact.LOW
    jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL
    change_type: ChangeType = ChangeType.AMENDMENT
    velocity_score: float = 0.0
    affected_controls: int = 0
    regulation_name: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryChangeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_id: str = ""
    jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL
    computed_velocity: float = 0.0
    is_high_impact: bool = False
    change_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryChangeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_velocity_score: float = 0.0
    by_change_impact: dict[str, int] = Field(default_factory=dict)
    by_jurisdiction: dict[str, int] = Field(default_factory=dict)
    by_change_type: dict[str, int] = Field(default_factory=dict)
    high_impact_regulations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryChangeVelocityTracker:
    """Compute change velocity by jurisdiction, detect
    high-impact changes, rank regulations by frequency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RegulatoryChangeRecord] = []
        self._analyses: dict[str, RegulatoryChangeAnalysis] = {}
        logger.info(
            "regulatory_change_velocity_tracker.init",
            max_records=max_records,
        )

    def add_record(
        self,
        regulation_id: str = "",
        change_impact: ChangeImpact = ChangeImpact.LOW,
        jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL,
        change_type: ChangeType = ChangeType.AMENDMENT,
        velocity_score: float = 0.0,
        affected_controls: int = 0,
        regulation_name: str = "",
        description: str = "",
    ) -> RegulatoryChangeRecord:
        record = RegulatoryChangeRecord(
            regulation_id=regulation_id,
            change_impact=change_impact,
            jurisdiction=jurisdiction,
            change_type=change_type,
            velocity_score=velocity_score,
            affected_controls=affected_controls,
            regulation_name=regulation_name,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulatory_change_velocity.record_added",
            record_id=record.id,
            regulation_id=regulation_id,
        )
        return record

    def process(self, key: str) -> RegulatoryChangeAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        changes = sum(1 for r in self._records if r.regulation_id == rec.regulation_id)
        is_high = rec.change_impact in (ChangeImpact.CRITICAL, ChangeImpact.HIGH)
        analysis = RegulatoryChangeAnalysis(
            regulation_id=rec.regulation_id,
            jurisdiction=rec.jurisdiction,
            computed_velocity=round(rec.velocity_score, 2),
            is_high_impact=is_high,
            change_count=changes,
            description=f"Regulation {rec.regulation_id} velocity {rec.velocity_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RegulatoryChangeReport:
        by_ci: dict[str, int] = {}
        by_j: dict[str, int] = {}
        by_ct: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.change_impact.value
            by_ci[k] = by_ci.get(k, 0) + 1
            k2 = r.jurisdiction.value
            by_j[k2] = by_j.get(k2, 0) + 1
            k3 = r.change_type.value
            by_ct[k3] = by_ct.get(k3, 0) + 1
            scores.append(r.velocity_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high = list(
            {
                r.regulation_id
                for r in self._records
                if r.change_impact in (ChangeImpact.CRITICAL, ChangeImpact.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-impact regulations detected")
        if not recs:
            recs.append("No high-impact regulatory changes detected")
        return RegulatoryChangeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_velocity_score=avg,
            by_change_impact=by_ci,
            by_jurisdiction=by_j,
            by_change_type=by_ct,
            high_impact_regulations=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        j_dist: dict[str, int] = {}
        for r in self._records:
            k = r.jurisdiction.value
            j_dist[k] = j_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "jurisdiction_distribution": j_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("regulatory_change_velocity_tracker.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_change_velocity_by_jurisdiction(
        self,
    ) -> list[dict[str, Any]]:
        """Compute change velocity per jurisdiction."""
        j_scores: dict[str, list[float]] = {}
        j_counts: dict[str, int] = {}
        for r in self._records:
            j_scores.setdefault(r.jurisdiction.value, []).append(r.velocity_score)
            j_counts[r.jurisdiction.value] = j_counts.get(r.jurisdiction.value, 0) + 1
        results: list[dict[str, Any]] = []
        for jur, scores in j_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "jurisdiction": jur,
                    "avg_velocity": avg,
                    "total_changes": j_counts[jur],
                }
            )
        results.sort(key=lambda x: x["avg_velocity"], reverse=True)
        return results

    def detect_high_impact_changes(
        self,
    ) -> list[dict[str, Any]]:
        """Detect high-impact regulatory changes."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.change_impact in (ChangeImpact.CRITICAL, ChangeImpact.HIGH)
                and r.regulation_id not in seen
            ):
                seen.add(r.regulation_id)
                results.append(
                    {
                        "regulation_id": r.regulation_id,
                        "change_impact": r.change_impact.value,
                        "jurisdiction": r.jurisdiction.value,
                        "affected_controls": r.affected_controls,
                    }
                )
        results.sort(key=lambda x: x["affected_controls"], reverse=True)
        return results

    def rank_regulations_by_change_frequency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank regulations by frequency of changes."""
        reg_counts: dict[str, int] = {}
        reg_jurisdictions: dict[str, str] = {}
        for r in self._records:
            reg_counts[r.regulation_id] = reg_counts.get(r.regulation_id, 0) + 1
            reg_jurisdictions[r.regulation_id] = r.jurisdiction.value
        results: list[dict[str, Any]] = []
        for rid, count in reg_counts.items():
            results.append(
                {
                    "regulation_id": rid,
                    "jurisdiction": reg_jurisdictions[rid],
                    "change_count": count,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["change_count"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
