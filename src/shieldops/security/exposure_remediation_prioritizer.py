"""Exposure Remediation Prioritizer — prioritize exposure remediation by risk and effort."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RemediationAction(StrEnum):
    PATCH = "patch"
    RECONFIGURE = "reconfigure"
    DECOMMISSION = "decommission"
    RESTRICT_ACCESS = "restrict_access"
    MONITOR = "monitor"


class RemediationEffort(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTENSIVE = "extensive"


class RemediationUrgency(StrEnum):
    IMMEDIATE = "immediate"
    URGENT = "urgent"
    PLANNED = "planned"
    SCHEDULED = "scheduled"
    OPTIONAL = "optional"


# --- Models ---


class RemediationPriorityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exposure_name: str = ""
    remediation_action: RemediationAction = RemediationAction.PATCH
    remediation_effort: RemediationEffort = RemediationEffort.MEDIUM
    remediation_urgency: RemediationUrgency = RemediationUrgency.PLANNED
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationPriorityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exposure_name: str = ""
    remediation_action: RemediationAction = RemediationAction.PATCH
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationPriorityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_effort: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ExposureRemediationPrioritizer:
    """Prioritize exposure remediation by risk reduction impact and effort."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[RemediationPriorityRecord] = []
        self._analyses: list[RemediationPriorityAnalysis] = []
        logger.info(
            "exposure_remediation_prioritizer.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_priority(
        self,
        exposure_name: str,
        remediation_action: RemediationAction = RemediationAction.PATCH,
        remediation_effort: RemediationEffort = RemediationEffort.MEDIUM,
        remediation_urgency: RemediationUrgency = RemediationUrgency.PLANNED,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RemediationPriorityRecord:
        record = RemediationPriorityRecord(
            exposure_name=exposure_name,
            remediation_action=remediation_action,
            remediation_effort=remediation_effort,
            remediation_urgency=remediation_urgency,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "exposure_remediation_prioritizer.priority_recorded",
            record_id=record.id,
            exposure_name=exposure_name,
            remediation_action=remediation_action.value,
            remediation_urgency=remediation_urgency.value,
        )
        return record

    def get_priority(self, record_id: str) -> RemediationPriorityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_priorities(
        self,
        remediation_action: RemediationAction | None = None,
        remediation_urgency: RemediationUrgency | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RemediationPriorityRecord]:
        results = list(self._records)
        if remediation_action is not None:
            results = [r for r in results if r.remediation_action == remediation_action]
        if remediation_urgency is not None:
            results = [r for r in results if r.remediation_urgency == remediation_urgency]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        exposure_name: str,
        remediation_action: RemediationAction = RemediationAction.PATCH,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RemediationPriorityAnalysis:
        analysis = RemediationPriorityAnalysis(
            exposure_name=exposure_name,
            remediation_action=remediation_action,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "exposure_remediation_prioritizer.analysis_added",
            exposure_name=exposure_name,
            remediation_action=remediation_action.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by remediation_action; return count and avg risk_score."""
        action_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.remediation_action.value
            action_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for action, scores in action_data.items():
            result[action] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "exposure_name": r.exposure_name,
                        "remediation_action": r.remediation_action.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> RemediationPriorityReport:
        by_action: dict[str, int] = {}
        by_effort: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        for r in self._records:
            by_action[r.remediation_action.value] = by_action.get(r.remediation_action.value, 0) + 1
            by_effort[r.remediation_effort.value] = by_effort.get(r.remediation_effort.value, 0) + 1
            by_urgency[r.remediation_urgency.value] = (
                by_urgency.get(r.remediation_urgency.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["exposure_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} remediation(s) below risk threshold ({self._risk_threshold})")
        if self._records and avg_risk_score < self._risk_threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._risk_threshold})")
        if not recs:
            recs.append("Exposure remediation prioritization is healthy")
        return RemediationPriorityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_action=by_action,
            by_effort=by_effort,
            by_urgency=by_urgency,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("exposure_remediation_prioritizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.remediation_action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "action_distribution": action_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
