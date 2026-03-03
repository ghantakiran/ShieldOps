"""K8s RBAC Drift Detector — detect unauthorized RBAC changes in Kubernetes clusters."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RBACResource(StrEnum):
    ROLE = "role"
    CLUSTER_ROLE = "cluster_role"
    BINDING = "binding"
    SERVICE_ACCOUNT = "service_account"
    NAMESPACE = "namespace"


class DriftType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    ESCALATED = "escalated"
    UNAUTHORIZED = "unauthorized"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class RBACDriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drift_id: str = ""
    rbac_resource: RBACResource = RBACResource.ROLE
    drift_type: DriftType = DriftType.ADDED
    drift_severity: DriftSeverity = DriftSeverity.CRITICAL
    drift_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RBACDriftAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drift_id: str = ""
    rbac_resource: RBACResource = RBACResource.ROLE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RBACDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_drift_score: float = 0.0
    by_resource: dict[str, int] = Field(default_factory=dict)
    by_drift_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class K8sRBACDriftDetector:
    """Detect unauthorized RBAC changes, privilege escalations, and drift in Kubernetes clusters."""

    def __init__(
        self,
        max_records: int = 200000,
        drift_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._drift_gap_threshold = drift_gap_threshold
        self._records: list[RBACDriftRecord] = []
        self._analyses: list[RBACDriftAnalysis] = []
        logger.info(
            "k8s_rbac_drift_detector.initialized",
            max_records=max_records,
            drift_gap_threshold=drift_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_drift(
        self,
        drift_id: str,
        rbac_resource: RBACResource = RBACResource.ROLE,
        drift_type: DriftType = DriftType.ADDED,
        drift_severity: DriftSeverity = DriftSeverity.CRITICAL,
        drift_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RBACDriftRecord:
        record = RBACDriftRecord(
            drift_id=drift_id,
            rbac_resource=rbac_resource,
            drift_type=drift_type,
            drift_severity=drift_severity,
            drift_score=drift_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "k8s_rbac_drift_detector.drift_recorded",
            record_id=record.id,
            drift_id=drift_id,
            rbac_resource=rbac_resource.value,
            drift_type=drift_type.value,
        )
        return record

    def get_drift(self, record_id: str) -> RBACDriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
        self,
        rbac_resource: RBACResource | None = None,
        drift_type: DriftType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RBACDriftRecord]:
        results = list(self._records)
        if rbac_resource is not None:
            results = [r for r in results if r.rbac_resource == rbac_resource]
        if drift_type is not None:
            results = [r for r in results if r.drift_type == drift_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        drift_id: str,
        rbac_resource: RBACResource = RBACResource.ROLE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RBACDriftAnalysis:
        analysis = RBACDriftAnalysis(
            drift_id=drift_id,
            rbac_resource=rbac_resource,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "k8s_rbac_drift_detector.analysis_added",
            drift_id=drift_id,
            rbac_resource=rbac_resource.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_resource_distribution(self) -> dict[str, Any]:
        """Group by rbac_resource; return count and avg drift_score."""
        resource_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.rbac_resource.value
            resource_data.setdefault(key, []).append(r.drift_score)
        result: dict[str, Any] = {}
        for resource, scores in resource_data.items():
            result[resource] = {
                "count": len(scores),
                "avg_drift_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_drift_gaps(self) -> list[dict[str, Any]]:
        """Return records where drift_score < drift_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.drift_score < self._drift_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "drift_id": r.drift_id,
                        "rbac_resource": r.rbac_resource.value,
                        "drift_score": r.drift_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["drift_score"])

    def rank_by_drift(self) -> list[dict[str, Any]]:
        """Group by service, avg drift_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.drift_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_drift_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_drift_score"])
        return results

    def detect_drift_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RBACDriftReport:
        by_resource: dict[str, int] = {}
        by_drift_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_resource[r.rbac_resource.value] = by_resource.get(r.rbac_resource.value, 0) + 1
            by_drift_type[r.drift_type.value] = by_drift_type.get(r.drift_type.value, 0) + 1
            by_severity[r.drift_severity.value] = by_severity.get(r.drift_severity.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.drift_score < self._drift_gap_threshold)
        scores = [r.drift_score for r in self._records]
        avg_drift_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_drift_gaps()
        top_gaps = [o["drift_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} drift(s) below detection threshold ({self._drift_gap_threshold})"
            )
        if self._records and avg_drift_score < self._drift_gap_threshold:
            recs.append(
                f"Avg drift score {avg_drift_score} below threshold ({self._drift_gap_threshold})"
            )
        if not recs:
            recs.append("K8s RBAC drift detection is healthy")
        return RBACDriftReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_drift_score=avg_drift_score,
            by_resource=by_resource,
            by_drift_type=by_drift_type,
            by_severity=by_severity,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("k8s_rbac_drift_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        resource_dist: dict[str, int] = {}
        for r in self._records:
            key = r.rbac_resource.value
            resource_dist[key] = resource_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "drift_gap_threshold": self._drift_gap_threshold,
            "resource_distribution": resource_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
