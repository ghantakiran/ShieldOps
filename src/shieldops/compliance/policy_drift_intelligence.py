"""Policy Drift Intelligence — policy drift detection and alignment."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftType(StrEnum):
    CONFIGURATION = "configuration"
    PERMISSION = "permission"
    NETWORK = "network"
    ENCRYPTION = "encryption"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DriftSource(StrEnum):
    MANUAL_CHANGE = "manual_change"
    DEPLOYMENT = "deployment"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


# --- Models ---


class DriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    drift_type: DriftType = DriftType.CONFIGURATION
    drift_severity: DriftSeverity = DriftSeverity.MEDIUM
    drift_source: DriftSource = DriftSource.UNKNOWN
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    drift_type: DriftType = DriftType.CONFIGURATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_drift_type: dict[str, int] = Field(default_factory=dict)
    by_drift_severity: dict[str, int] = Field(default_factory=dict)
    by_drift_source: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyDriftIntelligence:
    """Policy Drift Intelligence
    for drift detection and alignment.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DriftRecord] = []
        self._analyses: list[DriftAnalysis] = []
        logger.info(
            "policy_drift_intelligence.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        drift_type: DriftType = DriftType.CONFIGURATION,
        drift_severity: DriftSeverity = (DriftSeverity.MEDIUM),
        drift_source: DriftSource = DriftSource.UNKNOWN,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DriftRecord:
        record = DriftRecord(
            name=name,
            drift_type=drift_type,
            drift_severity=drift_severity,
            drift_source=drift_source,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_drift_intelligence.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> DriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        drift_type: DriftType | None = None,
        drift_severity: DriftSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DriftRecord]:
        results = list(self._records)
        if drift_type is not None:
            results = [r for r in results if r.drift_type == drift_type]
        if drift_severity is not None:
            results = [r for r in results if r.drift_severity == drift_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        drift_type: DriftType = DriftType.CONFIGURATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DriftAnalysis:
        analysis = DriftAnalysis(
            name=name,
            drift_type=drift_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "policy_drift_intelligence.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def detect_policy_drift(
        self,
    ) -> list[dict[str, Any]]:
        """Detect policy drifts by severity and type."""
        sev_weight = {
            "critical": 4.0,
            "high": 3.0,
            "medium": 2.0,
            "low": 1.0,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            weight = sev_weight.get(r.drift_severity.value, 1.0)
            drift_risk = round(weight * (100 - r.score) / 100, 2)
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "drift_type": r.drift_type.value,
                    "severity": r.drift_severity.value,
                    "source": r.drift_source.value,
                    "drift_risk": drift_risk,
                    "service": r.service,
                }
            )
        results.sort(key=lambda x: x["drift_risk"], reverse=True)
        return results

    def compute_drift_velocity(
        self,
    ) -> dict[str, Any]:
        """Compute rate of drift accumulation."""
        if len(self._records) < 4:
            return {
                "velocity": 0.0,
                "reason": "insufficient_data",
            }
        mid = len(self._records) // 2
        first = self._records[:mid]
        second = self._records[mid:]
        first_drifts = sum(1 for r in first if r.score < self._threshold)
        second_drifts = sum(1 for r in second if r.score < self._threshold)
        first_rate = round(first_drifts / len(first) * 100, 2)
        second_rate = round(second_drifts / len(second) * 100, 2)
        return {
            "velocity": round(second_rate - first_rate, 2),
            "first_half_drift_rate": first_rate,
            "second_half_drift_rate": second_rate,
            "trend": "accelerating"
            if second_rate > first_rate
            else "decelerating"
            if second_rate < first_rate
            else "stable",
        }

    def recommend_policy_alignment(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend alignment actions for drifted policies."""
        type_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            if r.score < self._threshold:
                type_data.setdefault(r.drift_type.value, []).append(
                    {
                        "name": r.name,
                        "score": r.score,
                        "severity": r.drift_severity.value,
                        "source": r.drift_source.value,
                    }
                )
        recs: list[dict[str, Any]] = []
        for dtype, entries in type_data.items():
            avg_score = round(sum(e["score"] for e in entries) / len(entries), 2)
            critical = sum(1 for e in entries if e["severity"] == "critical")
            recs.append(
                {
                    "drift_type": dtype,
                    "drifted_count": len(entries),
                    "critical_count": critical,
                    "avg_score": avg_score,
                    "recommendation": (
                        f"Realign {len(entries)} {dtype} policies ({critical} critical)"
                    ),
                    "priority": "critical" if critical > 0 else "high",
                }
            )
        recs.sort(key=lambda x: x["avg_score"])
        return recs

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> PolicyDriftReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.drift_type.value] = by_e1.get(r.drift_type.value, 0) + 1
            by_e2[r.drift_severity.value] = by_e2.get(r.drift_severity.value, 0) + 1
            by_e3[r.drift_source.value] = by_e3.get(r.drift_source.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Policy Drift Intelligence is healthy")
        return PolicyDriftReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_drift_type=by_e1,
            by_drift_severity=by_e2,
            by_drift_source=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("policy_drift_intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drift_type.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "drift_type_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
