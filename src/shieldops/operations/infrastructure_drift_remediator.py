"""Infrastructure Drift Remediator
classify drift severity, compute remediation priority,
rank resources by drift risk."""

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
    STATE = "state"
    VERSION = "version"
    PERMISSION = "permission"


class RemediationAction(StrEnum):
    RECONCILE = "reconcile"
    OVERRIDE = "override"
    IGNORE = "ignore"
    ESCALATE = "escalate"


class DriftOrigin(StrEnum):
    MANUAL_CHANGE = "manual_change"
    FAILED_APPLY = "failed_apply"
    EXTERNAL_UPDATE = "external_update"
    PROVIDER_UPDATE = "provider_update"


# --- Models ---


class DriftRemediationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_name: str = ""
    drift_type: DriftType = DriftType.CONFIGURATION
    remediation_action: RemediationAction = RemediationAction.RECONCILE
    drift_origin: DriftOrigin = DriftOrigin.MANUAL_CHANGE
    severity_score: float = 0.0
    drift_detected_at: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftRemediationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    drift_type: DriftType = DriftType.CONFIGURATION
    computed_severity: float = 0.0
    remediation_priority: int = 0
    needs_escalation: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftRemediationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_severity: float = 0.0
    by_drift_type: dict[str, int] = Field(default_factory=dict)
    by_remediation_action: dict[str, int] = Field(default_factory=dict)
    by_drift_origin: dict[str, int] = Field(default_factory=dict)
    critical_resources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureDriftRemediator:
    """Classify drift severity, compute remediation
    priority, rank resources by drift risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DriftRemediationRecord] = []
        self._analyses: dict[str, DriftRemediationAnalysis] = {}
        logger.info(
            "infrastructure_drift_remediator.init",
            max_records=max_records,
        )

    def record_item(
        self,
        resource_id: str = "",
        resource_name: str = "",
        drift_type: DriftType = DriftType.CONFIGURATION,
        remediation_action: RemediationAction = (RemediationAction.RECONCILE),
        drift_origin: DriftOrigin = (DriftOrigin.MANUAL_CHANGE),
        severity_score: float = 0.0,
        drift_detected_at: float = 0.0,
        description: str = "",
    ) -> DriftRemediationRecord:
        record = DriftRemediationRecord(
            resource_id=resource_id,
            resource_name=resource_name,
            drift_type=drift_type,
            remediation_action=remediation_action,
            drift_origin=drift_origin,
            severity_score=severity_score,
            drift_detected_at=drift_detected_at,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "drift_remediation.record_added",
            record_id=record.id,
            resource_id=resource_id,
        )
        return record

    def process(self, key: str) -> DriftRemediationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        needs_esc = rec.remediation_action == RemediationAction.ESCALATE
        priority = 1 if rec.severity_score >= 80 else 2 if rec.severity_score >= 50 else 3
        analysis = DriftRemediationAnalysis(
            resource_id=rec.resource_id,
            drift_type=rec.drift_type,
            computed_severity=round(rec.severity_score, 2),
            remediation_priority=priority,
            needs_escalation=needs_esc,
            description=(f"Resource {rec.resource_id} severity {rec.severity_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> DriftRemediationReport:
        by_dt: dict[str, int] = {}
        by_ra: dict[str, int] = {}
        by_do: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.drift_type.value
            by_dt[k] = by_dt.get(k, 0) + 1
            k2 = r.remediation_action.value
            by_ra[k2] = by_ra.get(k2, 0) + 1
            k3 = r.drift_origin.value
            by_do[k3] = by_do.get(k3, 0) + 1
            scores.append(r.severity_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical = list({r.resource_id for r in self._records if r.severity_score >= 80})[:10]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical drifts found")
        if not recs:
            recs.append("No critical drifts detected")
        return DriftRemediationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_severity=avg,
            by_drift_type=by_dt,
            by_remediation_action=by_ra,
            by_drift_origin=by_do,
            critical_resources=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.drift_type.value
            dt_dist[k] = dt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "drift_type_distribution": dt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("infrastructure_drift_remediator.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def classify_drift_severity(
        self,
    ) -> list[dict[str, Any]]:
        """Classify drift severity per resource."""
        resource_scores: dict[str, list[float]] = {}
        resource_types: dict[str, str] = {}
        for r in self._records:
            resource_scores.setdefault(r.resource_id, []).append(r.severity_score)
            resource_types[r.resource_id] = r.drift_type.value
        results: list[dict[str, Any]] = []
        for rid, scores in resource_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            level = (
                "critical"
                if avg >= 80
                else "high"
                if avg >= 60
                else "medium"
                if avg >= 40
                else "low"
            )
            results.append(
                {
                    "resource_id": rid,
                    "drift_type": resource_types[rid],
                    "avg_severity": avg,
                    "severity_class": level,
                }
            )
        results.sort(
            key=lambda x: x["avg_severity"],
            reverse=True,
        )
        return results

    def compute_remediation_priority(
        self,
    ) -> list[dict[str, Any]]:
        """Compute remediation priority per resource."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.resource_id not in seen:
                seen.add(r.resource_id)
                priority = 1 if r.severity_score >= 80 else 2 if r.severity_score >= 50 else 3
                results.append(
                    {
                        "resource_id": r.resource_id,
                        "severity_score": (r.severity_score),
                        "priority": priority,
                        "action": (r.remediation_action.value),
                    }
                )
        results.sort(
            key=lambda x: x["priority"],
        )
        return results

    def rank_resources_by_drift_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank resources by aggregate drift risk."""
        resource_data: dict[str, float] = {}
        for r in self._records:
            resource_data[r.resource_id] = resource_data.get(r.resource_id, 0.0) + r.severity_score
        results: list[dict[str, Any]] = []
        for rid, total in resource_data.items():
            results.append(
                {
                    "resource_id": rid,
                    "aggregate_risk": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["aggregate_risk"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
