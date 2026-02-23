"""Change risk scoring based on historical deployment data and blast radius."""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class RiskLevel(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(enum.StrEnum):
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    INFRASTRUCTURE = "infrastructure"
    DATABASE_MIGRATION = "database_migration"
    FEATURE_FLAG = "feature_flag"


# -- Models --------------------------------------------------------------------


class ChangeRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    change_type: ChangeType
    description: str = ""
    author: str = ""
    environment: str = "production"
    files_changed: int = 0
    lines_changed: int = 0
    rollback_available: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class RiskScore(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    change_id: str
    service: str
    score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    factors: list[str] = Field(default_factory=list)
    recommendation: str = ""
    scored_at: float = Field(default_factory=time.time)


class RiskFactor(BaseModel):
    name: str
    weight: float = 1.0
    description: str = ""


# -- Scorer --------------------------------------------------------------------


_CHANGE_TYPE_WEIGHTS: dict[ChangeType, float] = {
    ChangeType.DATABASE_MIGRATION: 0.8,
    ChangeType.INFRASTRUCTURE: 0.6,
    ChangeType.DEPLOYMENT: 0.4,
    ChangeType.CONFIG_CHANGE: 0.3,
    ChangeType.FEATURE_FLAG: 0.2,
}

_ENVIRONMENT_WEIGHTS: dict[str, float] = {
    "production": 0.3,
    "staging": 0.1,
}


class ChangeRiskScorer:
    """Score changes for deployment risk based on historical data and blast radius.

    Parameters
    ----------
    max_records:
        Maximum change records to store.
    high_risk_threshold:
        Score threshold for high risk classification.
    critical_risk_threshold:
        Score threshold for critical risk classification.
    """

    def __init__(
        self,
        max_records: int = 10000,
        high_risk_threshold: float = 0.7,
        critical_risk_threshold: float = 0.9,
    ) -> None:
        self._records: dict[str, ChangeRecord] = {}
        self._scores: dict[str, RiskScore] = {}
        self._history: list[ChangeRecord] = []
        self._outcomes: dict[str, bool] = {}
        self._max_records = max_records
        self._high_risk_threshold = high_risk_threshold
        self._critical_risk_threshold = critical_risk_threshold

    def record_change(
        self,
        service: str,
        change_type: ChangeType,
        description: str = "",
        author: str = "",
        environment: str = "production",
        files_changed: int = 0,
        lines_changed: int = 0,
        rollback_available: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ChangeRecord:
        if len(self._records) >= self._max_records:
            raise ValueError(f"Maximum records limit reached: {self._max_records}")
        record = ChangeRecord(
            service=service,
            change_type=change_type,
            description=description,
            author=author,
            environment=environment,
            files_changed=files_changed,
            lines_changed=lines_changed,
            rollback_available=rollback_available,
            metadata=metadata or {},
        )
        self._records[record.id] = record
        self._history.append(record)
        logger.info(
            "change_recorded",
            change_id=record.id,
            service=service,
            change_type=change_type,
        )
        return record

    def _get_service_failure_rate(self, service: str) -> float:
        service_changes = [
            cid
            for cid, rec in self._records.items()
            if rec.service == service and cid in self._outcomes
        ]
        if not service_changes:
            return 0.0
        failures = sum(1 for cid in service_changes if not self._outcomes[cid])
        return failures / len(service_changes)

    def score_change(self, change_id: str) -> RiskScore:
        record = self._records.get(change_id)
        if record is None:
            raise ValueError(f"Change record not found: {change_id}")

        score = 0.0
        factors: list[str] = []

        # Change type weight
        type_weight = _CHANGE_TYPE_WEIGHTS.get(record.change_type, 0.3)
        score += type_weight
        factors.append(f"change_type={record.change_type}(+{type_weight})")

        # Environment weight
        env_weight = _ENVIRONMENT_WEIGHTS.get(record.environment, 0.05)
        score += env_weight
        factors.append(f"environment={record.environment}(+{env_weight})")

        # Files changed
        if record.files_changed > 50:
            score += 0.2
            factors.append(f"files_changed={record.files_changed}(+0.2)")

        # Lines changed
        if record.lines_changed > 500:
            score += 0.2
            factors.append(f"lines_changed={record.lines_changed}(+0.2)")

        # Rollback availability
        if not record.rollback_available:
            score += 0.2
            factors.append("no_rollback(+0.2)")

        # Historical failure rate
        failure_rate = self._get_service_failure_rate(record.service)
        if failure_rate > 0:
            score += failure_rate * 0.3
            factors.append(f"historical_failure_rate={failure_rate:.2f}(+{failure_rate * 0.3:.2f})")

        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))

        # Determine risk level
        if score >= self._critical_risk_threshold:
            risk_level = RiskLevel.CRITICAL
            recommendation = "Block deployment. Requires senior engineer review and approval."
        elif score >= self._high_risk_threshold:
            risk_level = RiskLevel.HIGH
            recommendation = "Proceed with caution. Ensure rollback plan and monitoring."
        elif score >= 0.4:
            risk_level = RiskLevel.MEDIUM
            recommendation = "Standard deployment with monitoring."
        else:
            risk_level = RiskLevel.LOW
            recommendation = "Low risk. Proceed normally."

        risk_score = RiskScore(
            change_id=change_id,
            service=record.service,
            score=round(score, 4),
            risk_level=risk_level,
            factors=factors,
            recommendation=recommendation,
        )
        self._scores[change_id] = risk_score
        logger.info(
            "change_scored",
            change_id=change_id,
            score=risk_score.score,
            risk_level=risk_level,
        )
        return risk_score

    def get_score(self, change_id: str) -> RiskScore | None:
        return self._scores.get(change_id)

    def get_service_risk_history(self, service: str) -> list[RiskScore]:
        return [s for s in self._scores.values() if s.service == service]

    def list_changes(
        self,
        service: str | None = None,
        change_type: ChangeType | None = None,
    ) -> list[ChangeRecord]:
        records = list(self._records.values())
        if service:
            records = [r for r in records if r.service == service]
        if change_type:
            records = [r for r in records if r.change_type == change_type]
        return records

    def get_high_risk_changes(self) -> list[RiskScore]:
        return [s for s in self._scores.values() if s.score >= self._high_risk_threshold]

    def mark_outcome(self, change_id: str, success: bool) -> None:
        if change_id not in self._records:
            raise ValueError(f"Change record not found: {change_id}")
        self._outcomes[change_id] = success
        logger.info(
            "change_outcome_recorded",
            change_id=change_id,
            success=success,
        )

    def get_stats(self) -> dict[str, Any]:
        total_scored = len(self._scores)
        high_risk = sum(1 for s in self._scores.values() if s.score >= self._high_risk_threshold)
        critical_risk = sum(
            1 for s in self._scores.values() if s.score >= self._critical_risk_threshold
        )
        total_outcomes = len(self._outcomes)
        failures = sum(1 for v in self._outcomes.values() if not v)
        return {
            "total_records": len(self._records),
            "total_scored": total_scored,
            "high_risk_changes": high_risk,
            "critical_risk_changes": critical_risk,
            "total_outcomes": total_outcomes,
            "total_failures": failures,
            "overall_failure_rate": (
                round(failures / total_outcomes, 4) if total_outcomes else 0.0
            ),
        }
