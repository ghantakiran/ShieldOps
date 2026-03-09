"""InfrastructureDriftIntelligenceV2

Advanced drift detection, root cause classification,
auto-remediation planning, compliance impact analysis.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftCategory(StrEnum):
    CONFIGURATION = "configuration"
    SECURITY_GROUP = "security_group"
    IAM_POLICY = "iam_policy"
    RESOURCE_TAG = "resource_tag"
    NETWORK = "network"
    STORAGE = "storage"
    COMPUTE = "compute"


class DriftRootCause(StrEnum):
    MANUAL_CHANGE = "manual_change"
    AUTO_SCALING = "auto_scaling"
    PROVIDER_UPDATE = "provider_update"
    FAILED_APPLY = "failed_apply"
    EXTERNAL_TOOL = "external_tool"
    UNKNOWN = "unknown"


class RemediationAction(StrEnum):
    AUTO_REVERT = "auto_revert"
    IMPORT_STATE = "import_state"
    UPDATE_CODE = "update_code"
    MANUAL_REVIEW = "manual_review"
    IGNORE = "ignore"


# --- Models ---


class InfrastructureDriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: str = ""
    resource_id: str = ""
    category: DriftCategory = DriftCategory.CONFIGURATION
    root_cause: DriftRootCause = DriftRootCause.UNKNOWN
    remediation_action: RemediationAction = RemediationAction.MANUAL_REVIEW
    drift_score: float = 0.0
    compliance_impact: bool = False
    properties_drifted: int = 0
    detected_by: str = ""
    environment: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class InfrastructureDriftAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: DriftCategory = DriftCategory.CONFIGURATION
    analysis_score: float = 0.0
    total_drifts: int = 0
    auto_remediated: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InfrastructureDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    compliance_impacted: int = 0
    auto_remediable: int = 0
    avg_drift_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_root_cause: dict[str, int] = Field(default_factory=dict)
    by_remediation: dict[str, int] = Field(default_factory=dict)
    top_drifted_resources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureDriftIntelligenceV2:
    """Advanced infrastructure drift detection.

    Root cause classification and auto-remediation.
    """

    def __init__(
        self,
        max_records: int = 200000,
        drift_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._drift_threshold = drift_threshold
        self._records: list[InfrastructureDriftRecord] = []
        self._analyses: list[InfrastructureDriftAnalysis] = []
        logger.info(
            "infrastructure.drift.intelligence.v2.initialized",
            max_records=max_records,
            drift_threshold=drift_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        resource_type: str = "",
        resource_id: str = "",
        category: DriftCategory = DriftCategory.CONFIGURATION,
        root_cause: DriftRootCause = DriftRootCause.UNKNOWN,
        remediation_action: RemediationAction = RemediationAction.MANUAL_REVIEW,
        drift_score: float = 0.0,
        compliance_impact: bool = False,
        properties_drifted: int = 0,
        detected_by: str = "",
        environment: str = "",
        service: str = "",
        team: str = "",
    ) -> InfrastructureDriftRecord:
        record = InfrastructureDriftRecord(
            name=name,
            resource_type=resource_type,
            resource_id=resource_id,
            category=category,
            root_cause=root_cause,
            remediation_action=remediation_action,
            drift_score=drift_score,
            compliance_impact=compliance_impact,
            properties_drifted=properties_drifted,
            detected_by=detected_by,
            environment=environment,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "infrastructure.drift.intelligence.v2.item_recorded",
            record_id=record.id,
            name=name,
            category=category.value,
            root_cause=root_cause.value,
        )
        return record

    def get_record(self, record_id: str) -> InfrastructureDriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        category: DriftCategory | None = None,
        root_cause: DriftRootCause | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[InfrastructureDriftRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if root_cause is not None:
            results = [r for r in results if r.root_cause == root_cause]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        category: DriftCategory = DriftCategory.CONFIGURATION,
        analysis_score: float = 0.0,
        total_drifts: int = 0,
        auto_remediated: int = 0,
        description: str = "",
    ) -> InfrastructureDriftAnalysis:
        analysis = InfrastructureDriftAnalysis(
            name=name,
            category=category,
            analysis_score=analysis_score,
            total_drifts=total_drifts,
            auto_remediated=auto_remediated,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "infrastructure.drift.intelligence.v2.analysis_added",
            name=name,
            category=category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def classify_root_causes(self) -> dict[str, Any]:
        cause_data: dict[str, list[float]] = {}
        for r in self._records:
            cause_data.setdefault(r.root_cause.value, []).append(r.drift_score)
        result: dict[str, Any] = {}
        for cause, scores in cause_data.items():
            result[cause] = {
                "count": len(scores),
                "avg_drift_score": round(sum(scores) / len(scores), 2),
                "max_drift_score": round(max(scores), 2),
            }
        return result

    def assess_compliance_impact(self) -> list[dict[str, Any]]:
        impacted: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_impact:
                impacted.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "resource_type": r.resource_type,
                        "category": r.category.value,
                        "drift_score": r.drift_score,
                        "environment": r.environment,
                        "remediation_action": r.remediation_action.value,
                    }
                )
        return sorted(impacted, key=lambda x: x["drift_score"], reverse=True)

    def plan_auto_remediation(self) -> list[dict[str, Any]]:
        auto_plans: list[dict[str, Any]] = []
        for r in self._records:
            if r.remediation_action in (
                RemediationAction.AUTO_REVERT,
                RemediationAction.IMPORT_STATE,
            ):
                auto_plans.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "resource_id": r.resource_id,
                        "action": r.remediation_action.value,
                        "drift_score": r.drift_score,
                        "properties_drifted": r.properties_drifted,
                        "risk_level": "high" if r.compliance_impact else "low",
                    }
                )
        return sorted(auto_plans, key=lambda x: x["drift_score"], reverse=True)

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> InfrastructureDriftReport:
        by_cat: dict[str, int] = {}
        by_cause: dict[str, int] = {}
        by_rem: dict[str, int] = {}
        for r in self._records:
            by_cat[r.category.value] = by_cat.get(r.category.value, 0) + 1
            by_cause[r.root_cause.value] = by_cause.get(r.root_cause.value, 0) + 1
            by_rem[r.remediation_action.value] = by_rem.get(r.remediation_action.value, 0) + 1
        compliance_hit = sum(1 for r in self._records if r.compliance_impact)
        auto_rem = sum(
            1
            for r in self._records
            if r.remediation_action
            in (RemediationAction.AUTO_REVERT, RemediationAction.IMPORT_STATE)
        )
        scores = [r.drift_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        env_drifts: dict[str, int] = {}
        for r in self._records:
            env_drifts[r.resource_type] = env_drifts.get(r.resource_type, 0) + 1
        top_drifted = sorted(env_drifts, key=env_drifts.get, reverse=True)[:5]  # type: ignore[arg-type]
        recs: list[str] = []
        if compliance_hit > 0:
            recs.append(
                f"{compliance_hit} drift(s) have compliance impact — prioritize remediation"
            )
        manual_count = sum(1 for r in self._records if r.root_cause == DriftRootCause.MANUAL_CHANGE)
        if manual_count > 0:
            recs.append(f"{manual_count} manual change(s) detected — enforce IaC-only workflows")
        if avg_score > self._drift_threshold:
            recs.append(f"Avg drift score {avg_score} exceeds threshold {self._drift_threshold}")
        if not recs:
            recs.append("Infrastructure drift intelligence is healthy — minimal drift detected")
        return InfrastructureDriftReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            compliance_impacted=compliance_hit,
            auto_remediable=auto_rem,
            avg_drift_score=avg_score,
            by_category=by_cat,
            by_root_cause=by_cause,
            by_remediation=by_rem,
            top_drifted_resources=top_drifted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("infrastructure.drift.intelligence.v2.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            cat_dist[r.category.value] = cat_dist.get(r.category.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "drift_threshold": self._drift_threshold,
            "category_distribution": cat_dist,
            "unique_environments": len({r.environment for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
