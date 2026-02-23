"""Deployment Risk Predictor — predicts risk based on historical patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactor(StrEnum):
    CHANGE_SIZE = "change_size"
    TIME_OF_DAY = "time_of_day"
    SERVICE_COMPLEXITY = "service_complexity"
    RECENT_FAILURES = "recent_failures"
    DEPENDENCY_COUNT = "dependency_count"


# --- Models ---


class DeploymentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    version: str
    change_size: int = 0
    deployer: str = ""
    success: bool = True
    rollback_needed: bool = False
    duration_seconds: float = 0.0
    deployed_at: float = Field(default_factory=time.time)


class RiskAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    version: str = ""
    overall_risk: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    factors: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    assessed_at: float = Field(default_factory=time.time)


# --- Predictor ---


class DeploymentRiskPredictor:
    """Predicts deployment risk from historical deployment patterns."""

    def __init__(
        self,
        max_records: int = 100000,
        max_assessments: int = 50000,
    ) -> None:
        self._max_records = max_records
        self._max_assessments = max_assessments
        self._records: list[DeploymentRecord] = []
        self._assessments: dict[str, RiskAssessment] = {}
        logger.info(
            "deployment_risk_predictor.initialized",
            max_records=max_records,
            max_assessments=max_assessments,
        )

    def record_deployment(
        self,
        service: str,
        version: str,
        **kw: Any,
    ) -> DeploymentRecord:
        """Record a deployment outcome."""
        rec = DeploymentRecord(service=service, version=version, **kw)
        self._records.append(rec)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deployment_risk_predictor.deployment_recorded",
            record_id=rec.id,
            service=service,
            version=version,
            success=rec.success,
        )
        return rec

    def _service_records(self, service: str) -> list[DeploymentRecord]:
        """Return all records for a given service."""
        return [r for r in self._records if r.service == service]

    def _recent_failure_rate(self, service: str, window: int = 10) -> float:
        """Failure rate over the last *window* deployments."""
        recs = self._service_records(service)[-window:]
        if not recs:
            return 0.0
        failures = sum(1 for r in recs if not r.success)
        return failures / len(recs)

    def _rollback_rate(self, service: str) -> float:
        """Historical rollback rate for a service."""
        recs = self._service_records(service)
        if not recs:
            return 0.0
        rollbacks = sum(1 for r in recs if r.rollback_needed)
        return rollbacks / len(recs)

    def _change_size_factor(self, change_size: int) -> float:
        """Normalize change_size into a 0-1 factor."""
        if change_size <= 0:
            return 0.0
        if change_size < 50:
            return 0.2
        if change_size < 200:
            return 0.5
        if change_size < 500:
            return 0.7
        return 1.0

    def _risk_level_from_score(self, score: float) -> RiskLevel:
        """Map a 0-100 score to a risk level."""
        if score < 25:
            return RiskLevel.LOW
        if score < 50:
            return RiskLevel.MEDIUM
        if score < 75:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    def assess_risk(
        self,
        service: str,
        version: str = "",
        change_size: int = 0,
    ) -> RiskAssessment:
        """Assess the risk of an upcoming deployment."""
        failure_rate = self._recent_failure_rate(service)
        rollback_rate = self._rollback_rate(service)
        cs_factor = self._change_size_factor(change_size)

        # Weighted score: failures 40%, change_size 30%, rollback 30%
        score = failure_rate * 40 + cs_factor * 30 + rollback_rate * 30
        score = min(round(score, 2), 100.0)
        level = self._risk_level_from_score(score)

        factors: dict[str, Any] = {
            RiskFactor.RECENT_FAILURES: round(failure_rate, 4),
            RiskFactor.CHANGE_SIZE: cs_factor,
            "rollback_rate": round(rollback_rate, 4),
        }

        recommendations: list[str] = []
        if failure_rate > 0.3:
            recommendations.append("High recent failure rate; consider extra review.")
        if cs_factor >= 0.7:
            recommendations.append("Large change size; consider incremental rollout.")
        if rollback_rate > 0.2:
            recommendations.append("Frequent rollbacks; verify rollback plan is ready.")
        if level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            recommendations.append("Deploy during a maintenance window with monitoring.")

        assessment = RiskAssessment(
            service=service,
            version=version,
            overall_risk=level,
            risk_score=score,
            factors=factors,
            recommendations=recommendations,
        )
        self._assessments[assessment.id] = assessment
        if len(self._assessments) > self._max_assessments:
            oldest = next(iter(self._assessments))
            del self._assessments[oldest]

        logger.info(
            "deployment_risk_predictor.risk_assessed",
            assessment_id=assessment.id,
            service=service,
            risk_score=score,
            overall_risk=level,
        )
        return assessment

    def get_service_history(
        self,
        service: str,
        limit: int = 50,
    ) -> list[DeploymentRecord]:
        """Return deployment history for a service."""
        recs = self._service_records(service)
        return recs[-limit:]

    def get_failure_rate(self, service: str) -> float:
        """Overall failure rate for a service."""
        recs = self._service_records(service)
        if not recs:
            return 0.0
        failures = sum(1 for r in recs if not r.success)
        return round(failures / len(recs), 4)

    def get_assessment(
        self,
        assessment_id: str,
    ) -> RiskAssessment | None:
        """Retrieve an assessment by ID."""
        return self._assessments.get(assessment_id)

    def list_assessments(
        self,
        service: str | None = None,
        risk: str | None = None,
    ) -> list[RiskAssessment]:
        """List assessments with optional filters."""
        results = list(self._assessments.values())
        if service is not None:
            results = [a for a in results if a.service == service]
        if risk is not None:
            results = [a for a in results if a.overall_risk == risk]
        return results

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        services: set[str] = set()
        total_success = 0
        total_rollback = 0
        for r in self._records:
            services.add(r.service)
            if r.success:
                total_success += 1
            if r.rollback_needed:
                total_rollback += 1
        total = len(self._records)
        return {
            "total_records": total,
            "total_assessments": len(self._assessments),
            "services_tracked": len(services),
            "overall_success_rate": (round(total_success / total, 4) if total else 0.0),
            "overall_rollback_rate": (round(total_rollback / total, 4) if total else 0.0),
        }
