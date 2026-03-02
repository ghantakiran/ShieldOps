"""Team Capacity Planner — plan team capacity, identify overloaded teams and burnout risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CapacityStatus(StrEnum):
    AVAILABLE = "available"
    LOADED = "loaded"
    OVERLOADED = "overloaded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class LoadCategory(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    TOIL = "toil"
    PROJECT_WORK = "project_work"
    ON_CALL = "on_call"
    TRAINING = "training"


class BurnoutRisk(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class CapacityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str = ""
    capacity_status: CapacityStatus = CapacityStatus.AVAILABLE
    load_category: LoadCategory = LoadCategory.INCIDENT_RESPONSE
    burnout_risk: BurnoutRisk = BurnoutRisk.MINIMAL
    utilization_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str = ""
    capacity_status: CapacityStatus = CapacityStatus.AVAILABLE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TeamCapacityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    overloaded_count: int = 0
    avg_utilization_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_overloaded: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamCapacityPlanner:
    """Plan team capacity, identify overloaded teams and burnout risk."""

    def __init__(
        self,
        max_records: int = 200000,
        capacity_utilization_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._capacity_utilization_threshold = capacity_utilization_threshold
        self._records: list[CapacityRecord] = []
        self._assessments: list[CapacityAssessment] = []
        logger.info(
            "team_capacity_planner.initialized",
            max_records=max_records,
            capacity_utilization_threshold=capacity_utilization_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_capacity(
        self,
        team_name: str,
        capacity_status: CapacityStatus = CapacityStatus.AVAILABLE,
        load_category: LoadCategory = LoadCategory.INCIDENT_RESPONSE,
        burnout_risk: BurnoutRisk = BurnoutRisk.MINIMAL,
        utilization_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CapacityRecord:
        record = CapacityRecord(
            team_name=team_name,
            capacity_status=capacity_status,
            load_category=load_category,
            burnout_risk=burnout_risk,
            utilization_score=utilization_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "team_capacity_planner.capacity_recorded",
            record_id=record.id,
            team_name=team_name,
            capacity_status=capacity_status.value,
            load_category=load_category.value,
        )
        return record

    def get_capacity(self, record_id: str) -> CapacityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_capacity_records(
        self,
        capacity_status: CapacityStatus | None = None,
        load_category: LoadCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CapacityRecord]:
        results = list(self._records)
        if capacity_status is not None:
            results = [r for r in results if r.capacity_status == capacity_status]
        if load_category is not None:
            results = [r for r in results if r.load_category == load_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        team_name: str,
        capacity_status: CapacityStatus = CapacityStatus.AVAILABLE,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CapacityAssessment:
        assessment = CapacityAssessment(
            team_name=team_name,
            capacity_status=capacity_status,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "team_capacity_planner.assessment_added",
            team_name=team_name,
            capacity_status=capacity_status.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_capacity_distribution(self) -> dict[str, Any]:
        """Group by capacity_status; return count and avg utilization_score."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.capacity_status.value
            status_data.setdefault(key, []).append(r.utilization_score)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_utilization_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_overloaded_teams(self) -> list[dict[str, Any]]:
        """Return records where utilization_score > capacity_utilization_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_score > self._capacity_utilization_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "team_name": r.team_name,
                        "capacity_status": r.capacity_status.value,
                        "utilization_score": r.utilization_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["utilization_score"], reverse=True)

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by service, avg utilization_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.utilization_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_utilization_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_score"], reverse=True)
        return results

    def detect_capacity_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> TeamCapacityReport:
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_status[r.capacity_status.value] = by_status.get(r.capacity_status.value, 0) + 1
            by_category[r.load_category.value] = by_category.get(r.load_category.value, 0) + 1
            by_risk[r.burnout_risk.value] = by_risk.get(r.burnout_risk.value, 0) + 1
        overloaded_count = sum(
            1 for r in self._records if r.utilization_score > self._capacity_utilization_threshold
        )
        scores = [r.utilization_score for r in self._records]
        avg_utilization_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        overloaded_list = self.identify_overloaded_teams()
        top_overloaded = [o["team_name"] for o in overloaded_list[:5]]
        recs: list[str] = []
        if self._records and overloaded_count > 0:
            recs.append(
                f"{overloaded_count} team(s) exceed utilization threshold "
                f"({self._capacity_utilization_threshold})"
            )
        if self._records and avg_utilization_score > self._capacity_utilization_threshold:
            recs.append(
                f"Avg utilization score {avg_utilization_score} above threshold "
                f"({self._capacity_utilization_threshold})"
            )
        if not recs:
            recs.append("Team capacity utilization levels are healthy")
        return TeamCapacityReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            overloaded_count=overloaded_count,
            avg_utilization_score=avg_utilization_score,
            by_status=by_status,
            by_category=by_category,
            by_risk=by_risk,
            top_overloaded=top_overloaded,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("team_capacity_planner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.capacity_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "capacity_utilization_threshold": self._capacity_utilization_threshold,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
