"""Topology Drift Detector — detect topology drift from desired state."""

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
    SERVICE_MISMATCH = "service_mismatch"
    CONFIG_DIVERGENCE = "config_divergence"
    VERSION_SKEW = "version_skew"
    DEPENDENCY_SHIFT = "dependency_shift"
    CAPACITY_IMBALANCE = "capacity_imbalance"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    COSMETIC = "cosmetic"


class DriftOrigin(StrEnum):
    MANUAL_CHANGE = "manual_change"
    AUTOMATION_FAILURE = "automation_failure"
    SCALING_EVENT = "scaling_event"
    DEPLOYMENT = "deployment"
    UNKNOWN = "unknown"


# --- Models ---


class DriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drift_id: str = ""
    drift_type: DriftType = DriftType.SERVICE_MISMATCH
    drift_severity: DriftSeverity = DriftSeverity.LOW
    drift_origin: DriftOrigin = DriftOrigin.UNKNOWN
    drift_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drift_id: str = ""
    drift_type: DriftType = DriftType.SERVICE_MISMATCH
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TopologyDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    critical_drifts: int = 0
    avg_drift_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_origin: dict[str, int] = Field(default_factory=dict)
    top_drifting: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TopologyDriftDetector:
    """Detect topology drift from desired state and track drift severity."""

    def __init__(
        self,
        max_records: int = 200000,
        max_critical_drift_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_critical_drift_pct = max_critical_drift_pct
        self._records: list[DriftRecord] = []
        self._assessments: list[DriftAssessment] = []
        logger.info(
            "topology_drift_detector.initialized",
            max_records=max_records,
            max_critical_drift_pct=max_critical_drift_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_drift(
        self,
        drift_id: str,
        drift_type: DriftType = DriftType.SERVICE_MISMATCH,
        drift_severity: DriftSeverity = DriftSeverity.LOW,
        drift_origin: DriftOrigin = DriftOrigin.UNKNOWN,
        drift_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DriftRecord:
        record = DriftRecord(
            drift_id=drift_id,
            drift_type=drift_type,
            drift_severity=drift_severity,
            drift_origin=drift_origin,
            drift_score=drift_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "topology_drift_detector.drift_recorded",
            record_id=record.id,
            drift_id=drift_id,
            drift_type=drift_type.value,
            drift_severity=drift_severity.value,
        )
        return record

    def get_drift(self, record_id: str) -> DriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
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

    def add_assessment(
        self,
        drift_id: str,
        drift_type: DriftType = DriftType.SERVICE_MISMATCH,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DriftAssessment:
        assessment = DriftAssessment(
            drift_id=drift_id,
            drift_type=drift_type,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "topology_drift_detector.assessment_added",
            drift_id=drift_id,
            drift_type=drift_type.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_drift_distribution(self) -> dict[str, Any]:
        """Group by drift_type; return count and avg drift_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.drift_type.value
            type_data.setdefault(key, []).append(r.drift_score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
                "count": len(scores),
                "avg_drift_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_critical_drifts(self) -> list[dict[str, Any]]:
        """Return drifts where severity is CRITICAL or HIGH."""
        critical_severities = {
            DriftSeverity.CRITICAL,
            DriftSeverity.HIGH,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.drift_severity in critical_severities:
                results.append(
                    {
                        "record_id": r.id,
                        "drift_id": r.drift_id,
                        "drift_type": r.drift_type.value,
                        "drift_severity": r.drift_severity.value,
                        "drift_score": r.drift_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["drift_score"], reverse=True)
        return results

    def rank_by_drift_score(self) -> list[dict[str, Any]]:
        """Group by service, avg drift_score, sort desc."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.drift_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_drift_score": round(sum(scores) / len(scores), 2),
                    "drift_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_drift_score"], reverse=True)
        return results

    def detect_drift_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> TopologyDriftReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_origin: dict[str, int] = {}
        for r in self._records:
            by_type[r.drift_type.value] = by_type.get(r.drift_type.value, 0) + 1
            by_severity[r.drift_severity.value] = by_severity.get(r.drift_severity.value, 0) + 1
            by_origin[r.drift_origin.value] = by_origin.get(r.drift_origin.value, 0) + 1
        critical_drifts = sum(
            1
            for r in self._records
            if r.drift_severity in {DriftSeverity.CRITICAL, DriftSeverity.HIGH}
        )
        avg_drift = (
            round(
                sum(r.drift_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical = self.identify_critical_drifts()
        top_drifting = [c["drift_id"] for c in critical]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical drift(s) detected — review topology state")
        high_drift = sum(1 for r in self._records if r.drift_score > self._max_critical_drift_pct)
        if high_drift > 0:
            recs.append(
                f"{high_drift} drift(s) above critical threshold ({self._max_critical_drift_pct}%)"
            )
        if not recs:
            recs.append("Topology drift levels are acceptable")
        return TopologyDriftReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            critical_drifts=critical_drifts,
            avg_drift_score=avg_drift,
            by_type=by_type,
            by_severity=by_severity,
            by_origin=by_origin,
            top_drifting=top_drifting,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("topology_drift_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_critical_drift_pct": self._max_critical_drift_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
