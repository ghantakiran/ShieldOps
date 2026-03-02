"""Incident Containment Tracker — track containment actions with MTTC metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContainmentType(StrEnum):
    NETWORK_ISOLATION = "network_isolation"
    ACCOUNT_LOCKOUT = "account_lockout"
    SERVICE_SHUTDOWN = "service_shutdown"
    FIREWALL_BLOCK = "firewall_block"
    CREDENTIAL_REVOCATION = "credential_revocation"


class ContainmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    PENDING = "pending"


class UrgencyLevel(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SCHEDULED = "scheduled"


# --- Models ---


class ContainmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    containment_name: str = ""
    containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION
    containment_status: ContainmentStatus = ContainmentStatus.ACTIVE
    urgency_level: UrgencyLevel = UrgencyLevel.IMMEDIATE
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    containment_name: str = ""
    containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentContainmentTracker:
    """Track containment actions with MTTC metrics."""

    def __init__(
        self,
        max_records: int = 200000,
        effectiveness_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._effectiveness_threshold = effectiveness_threshold
        self._records: list[ContainmentRecord] = []
        self._analyses: list[ContainmentAnalysis] = []
        logger.info(
            "incident_containment_tracker.initialized",
            max_records=max_records,
            effectiveness_threshold=effectiveness_threshold,
        )

    def record_containment(
        self,
        containment_name: str,
        containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION,
        containment_status: ContainmentStatus = ContainmentStatus.ACTIVE,
        urgency_level: UrgencyLevel = UrgencyLevel.IMMEDIATE,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ContainmentRecord:
        record = ContainmentRecord(
            containment_name=containment_name,
            containment_type=containment_type,
            containment_status=containment_status,
            urgency_level=urgency_level,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_containment_tracker.containment_recorded",
            record_id=record.id,
            containment_name=containment_name,
            containment_type=containment_type.value,
            containment_status=containment_status.value,
        )
        return record

    def get_containment(self, record_id: str) -> ContainmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_containments(
        self,
        containment_type: ContainmentType | None = None,
        containment_status: ContainmentStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ContainmentRecord]:
        results = list(self._records)
        if containment_type is not None:
            results = [r for r in results if r.containment_type == containment_type]
        if containment_status is not None:
            results = [r for r in results if r.containment_status == containment_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        containment_name: str,
        containment_type: ContainmentType = ContainmentType.NETWORK_ISOLATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ContainmentAnalysis:
        analysis = ContainmentAnalysis(
            containment_name=containment_name,
            containment_type=containment_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "incident_containment_tracker.analysis_added",
            containment_name=containment_name,
            containment_type=containment_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_containment_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.containment_type.value
            type_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness_containments(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "containment_name": r.containment_name,
                        "containment_type": r.containment_type.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {"service": svc, "avg_effectiveness_score": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_containment_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ContainmentReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        for r in self._records:
            by_type[r.containment_type.value] = by_type.get(r.containment_type.value, 0) + 1
            by_status[r.containment_status.value] = by_status.get(r.containment_status.value, 0) + 1
            by_urgency[r.urgency_level.value] = by_urgency.get(r.urgency_level.value, 0) + 1
        low_effectiveness_count = sum(
            1 for r in self._records if r.effectiveness_score < self._effectiveness_threshold
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_effectiveness_containments()
        top_low_effectiveness = [o["containment_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_effectiveness_count > 0:
            recs.append(
                f"{low_effectiveness_count} containment(s) below effectiveness threshold "
                f"({self._effectiveness_threshold})"
            )
        if self._records and avg_effectiveness_score < self._effectiveness_threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._effectiveness_threshold})"
            )
        if not recs:
            recs.append("Incident containment effectiveness is healthy")
        return ContainmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_type=by_type,
            by_status=by_status,
            by_urgency=by_urgency,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("incident_containment_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.containment_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "effectiveness_threshold": self._effectiveness_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
