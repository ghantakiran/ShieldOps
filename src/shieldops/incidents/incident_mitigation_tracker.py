"""Incident Mitigation Tracker — track mitigation actions and effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MitigationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPLIED = "applied"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled_back"


class MitigationCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    NETWORK = "network"
    DATABASE = "database"
    CONFIGURATION = "configuration"


class MitigationUrgency(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFERRED = "deferred"


# --- Models ---


class MitigationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    mitigation_status: MitigationStatus = MitigationStatus.PENDING
    mitigation_category: MitigationCategory = MitigationCategory.INFRASTRUCTURE
    mitigation_urgency: MitigationUrgency = MitigationUrgency.CRITICAL
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MitigationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    mitigation_status: MitigationStatus = MitigationStatus.PENDING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentMitigationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentMitigationTracker:
    """Track mitigation actions, analyze effectiveness, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        effectiveness_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._effectiveness_threshold = effectiveness_threshold
        self._records: list[MitigationRecord] = []
        self._analyses: list[MitigationAnalysis] = []
        logger.info(
            "incident_mitigation_tracker.initialized",
            max_records=max_records,
            effectiveness_threshold=effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mitigation(
        self,
        incident_id: str,
        mitigation_status: MitigationStatus = MitigationStatus.PENDING,
        mitigation_category: MitigationCategory = MitigationCategory.INFRASTRUCTURE,
        mitigation_urgency: MitigationUrgency = MitigationUrgency.CRITICAL,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MitigationRecord:
        record = MitigationRecord(
            incident_id=incident_id,
            mitigation_status=mitigation_status,
            mitigation_category=mitigation_category,
            mitigation_urgency=mitigation_urgency,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_mitigation_tracker.mitigation_recorded",
            record_id=record.id,
            incident_id=incident_id,
            mitigation_status=mitigation_status.value,
            mitigation_category=mitigation_category.value,
        )
        return record

    def get_mitigation(self, record_id: str) -> MitigationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mitigations(
        self,
        mitigation_status: MitigationStatus | None = None,
        mitigation_category: MitigationCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MitigationRecord]:
        results = list(self._records)
        if mitigation_status is not None:
            results = [r for r in results if r.mitigation_status == mitigation_status]
        if mitigation_category is not None:
            results = [r for r in results if r.mitigation_category == mitigation_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        incident_id: str,
        mitigation_status: MitigationStatus = MitigationStatus.PENDING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MitigationAnalysis:
        analysis = MitigationAnalysis(
            incident_id=incident_id,
            mitigation_status=mitigation_status,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "incident_mitigation_tracker.analysis_added",
            incident_id=incident_id,
            mitigation_status=mitigation_status.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_mitigation_distribution(self) -> dict[str, Any]:
        """Group by mitigation_status; return count and avg score."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.mitigation_status.value
            status_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness(self) -> list[dict[str, Any]]:
        """Return mitigations where effectiveness_score < effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "mitigation_status": r.mitigation_status.value,
                        "mitigation_category": r.mitigation_category.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["effectiveness_score"], reverse=False)
        return results

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort asc (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                    "mitigation_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"], reverse=False)
        return results

    def detect_mitigation_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.analysis_score for a in self._analyses]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> IncidentMitigationReport:
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        for r in self._records:
            by_status[r.mitigation_status.value] = by_status.get(r.mitigation_status.value, 0) + 1
            by_category[r.mitigation_category.value] = (
                by_category.get(r.mitigation_category.value, 0) + 1
            )
            by_urgency[r.mitigation_urgency.value] = (
                by_urgency.get(r.mitigation_urgency.value, 0) + 1
            )
        low_effectiveness_count = sum(
            1 for r in self._records if r.effectiveness_score < self._effectiveness_threshold
        )
        avg_effectiveness = (
            round(
                sum(r.effectiveness_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low_eff = self.identify_low_effectiveness()
        top_low_effectiveness = [p["incident_id"] for p in low_eff]
        recs: list[str] = []
        if low_eff:
            recs.append(
                f"{len(low_eff)} low-effectiveness mitigation(s) detected — review strategies"
            )
        below = sum(
            1 for r in self._records if r.effectiveness_score < self._effectiveness_threshold
        )
        if below > 0:
            recs.append(
                f"{below} mitigation(s) below effectiveness threshold "
                f"({self._effectiveness_threshold}%)"
            )
        if not recs:
            recs.append("Mitigation effectiveness levels are acceptable")
        return IncidentMitigationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness,
            by_status=by_status,
            by_category=by_category,
            by_urgency=by_urgency,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("incident_mitigation_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.mitigation_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "effectiveness_threshold": self._effectiveness_threshold,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
