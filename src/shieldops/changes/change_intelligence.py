"""Change Intelligence Analyzer — ML-informed change risk scoring, safety gating."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeRiskLevel(StrEnum):
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class ChangeOutcome(StrEnum):
    SUCCESS = "success"
    DEGRADATION = "degradation"
    INCIDENT = "incident"
    ROLLBACK = "rollback"
    UNKNOWN = "unknown"


class SafetyGate(StrEnum):
    PASS = "pass"  # noqa: S105
    CONDITIONAL_PASS = "conditional_pass"  # noqa: S105
    HOLD = "hold"
    BLOCK = "block"


# --- Models ---


class ChangeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_type: str = "deployment"
    service: str = ""
    description: str = ""
    author: str = ""
    risk_level: ChangeRiskLevel = ChangeRiskLevel.LOW
    outcome: ChangeOutcome = ChangeOutcome.UNKNOWN
    files_changed: int = 0
    lines_changed: int = 0
    has_db_migration: bool = False
    has_config_change: bool = False
    is_rollback: bool = False
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


class RiskPrediction(BaseModel):
    change_id: str = ""
    risk_level: ChangeRiskLevel = ChangeRiskLevel.LOW
    risk_score: float = 0.0
    risk_factors: list[str] = Field(default_factory=list)
    historical_success_rate: float = 0.0
    recommendation: str = ""


class SafetyGateDecision(BaseModel):
    change_id: str = ""
    gate: SafetyGate = SafetyGate.PASS
    reasons: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    decided_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeIntelligenceAnalyzer:
    """ML-informed change risk scoring, outcome correlation, deployment safety gating."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 0.6,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._changes: list[ChangeRecord] = []
        logger.info(
            "change_intelligence.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    def record_change(
        self,
        change_type: str = "deployment",
        service: str = "",
        description: str = "",
        author: str = "",
        files_changed: int = 0,
        lines_changed: int = 0,
        has_db_migration: bool = False,
        has_config_change: bool = False,
        is_rollback: bool = False,
    ) -> ChangeRecord:
        change = ChangeRecord(
            change_type=change_type,
            service=service,
            description=description,
            author=author,
            files_changed=files_changed,
            lines_changed=lines_changed,
            has_db_migration=has_db_migration,
            has_config_change=has_config_change,
            is_rollback=is_rollback,
        )
        self._changes.append(change)
        if len(self._changes) > self._max_records:
            self._changes = self._changes[-self._max_records :]
        logger.info(
            "change_intelligence.change_recorded",
            change_id=change.id,
            service=service,
            change_type=change_type,
        )
        return change

    def get_change(self, change_id: str) -> ChangeRecord | None:
        for c in self._changes:
            if c.id == change_id:
                return c
        return None

    def list_changes(
        self,
        service: str | None = None,
        outcome: ChangeOutcome | None = None,
        limit: int = 100,
    ) -> list[ChangeRecord]:
        results = list(self._changes)
        if service is not None:
            results = [c for c in results if c.service == service]
        if outcome is not None:
            results = [c for c in results if c.outcome == outcome]
        return results[-limit:]

    def predict_risk(self, change_id: str) -> RiskPrediction | None:
        change = self.get_change(change_id)
        if change is None:
            return None
        risk_factors: list[str] = []
        score = 0.0
        # File/line heuristics
        if change.files_changed > 20:
            risk_factors.append("Large number of files changed")
            score += 0.2
        elif change.files_changed > 10:
            risk_factors.append("Moderate number of files changed")
            score += 0.1
        if change.lines_changed > 1000:
            risk_factors.append("Large code diff")
            score += 0.2
        elif change.lines_changed > 500:
            risk_factors.append("Moderate code diff")
            score += 0.1
        if change.has_db_migration:
            risk_factors.append("Contains database migration")
            score += 0.25
        if change.has_config_change:
            risk_factors.append("Contains configuration change")
            score += 0.1
        if change.is_rollback:
            risk_factors.append("Is a rollback")
            score += 0.15
        # Historical success rate for this service
        svc_changes = [
            c
            for c in self._changes
            if c.service == change.service and c.outcome != ChangeOutcome.UNKNOWN
        ]
        if svc_changes:
            successes = sum(1 for c in svc_changes if c.outcome == ChangeOutcome.SUCCESS)
            hist_rate = round(successes / len(svc_changes) * 100, 1)
            if hist_rate < 80:
                risk_factors.append(f"Low historical success rate: {hist_rate}%")
                score += 0.15
        else:
            hist_rate = 0.0
        score = min(1.0, score)
        # Determine risk level
        if score >= 0.8:
            risk_level = ChangeRiskLevel.EXTREME
        elif score >= 0.6:
            risk_level = ChangeRiskLevel.HIGH
        elif score >= 0.4:
            risk_level = ChangeRiskLevel.MODERATE
        elif score >= 0.2:
            risk_level = ChangeRiskLevel.LOW
        else:
            risk_level = ChangeRiskLevel.NEGLIGIBLE
        change.risk_level = risk_level
        if score >= self._risk_threshold:
            rec = "High risk — require additional review and staged rollout"
        elif score >= 0.4:
            rec = "Moderate risk — standard review process"
        else:
            rec = "Low risk — proceed with standard deployment"
        return RiskPrediction(
            change_id=change_id,
            risk_level=risk_level,
            risk_score=round(score, 3),
            risk_factors=risk_factors,
            historical_success_rate=hist_rate,
            recommendation=rec,
        )

    def evaluate_safety_gate(self, change_id: str) -> SafetyGateDecision | None:
        prediction = self.predict_risk(change_id)
        if prediction is None:
            return None
        reasons: list[str] = list(prediction.risk_factors)
        conditions: list[str] = []
        if prediction.risk_level == ChangeRiskLevel.EXTREME:
            gate = SafetyGate.BLOCK
        elif prediction.risk_level == ChangeRiskLevel.HIGH:
            gate = SafetyGate.HOLD
            conditions.append("Requires senior engineer approval")
        elif prediction.risk_level == ChangeRiskLevel.MODERATE:
            gate = SafetyGate.CONDITIONAL_PASS
            conditions.append("Deploy to staging first")
        else:
            gate = SafetyGate.PASS
        return SafetyGateDecision(
            change_id=change_id,
            gate=gate,
            reasons=reasons,
            conditions=conditions,
        )

    def record_outcome(
        self,
        change_id: str,
        outcome: ChangeOutcome,
    ) -> bool:
        change = self.get_change(change_id)
        if change is None:
            return False
        change.outcome = outcome
        change.completed_at = time.time()
        logger.info(
            "change_intelligence.outcome_recorded",
            change_id=change_id,
            outcome=outcome,
        )
        return True

    def get_risk_factors(self, service: str | None = None) -> list[dict[str, Any]]:
        targets = self._changes
        if service:
            targets = [c for c in targets if c.service == service]
        factor_counts: dict[str, int] = {}
        for c in targets:
            if c.has_db_migration:
                factor_counts["db_migration"] = factor_counts.get("db_migration", 0) + 1
            if c.has_config_change:
                factor_counts["config_change"] = factor_counts.get("config_change", 0) + 1
            if c.is_rollback:
                factor_counts["rollback"] = factor_counts.get("rollback", 0) + 1
            if c.files_changed > 20:
                factor_counts["large_diff"] = factor_counts.get("large_diff", 0) + 1
        return [
            {"factor": f, "count": c}
            for f, c in sorted(factor_counts.items(), key=lambda x: x[1], reverse=True)
        ]

    def get_success_correlation(self, service: str | None = None) -> dict[str, Any]:
        targets = self._changes
        if service:
            targets = [c for c in targets if c.service == service]
        known = [c for c in targets if c.outcome != ChangeOutcome.UNKNOWN]
        if not known:
            return {"total": 0, "success_rate": 0.0, "by_outcome": {}}
        outcome_counts: dict[str, int] = {}
        for c in known:
            outcome_counts[c.outcome] = outcome_counts.get(c.outcome, 0) + 1
        successes = outcome_counts.get(ChangeOutcome.SUCCESS, 0)
        return {
            "total": len(known),
            "success_rate": round(successes / len(known) * 100, 1),
            "by_outcome": outcome_counts,
        }

    def get_high_risk_changes(self, limit: int = 20) -> list[dict[str, Any]]:
        high_risk = [
            c
            for c in self._changes
            if c.risk_level in (ChangeRiskLevel.HIGH, ChangeRiskLevel.EXTREME)
        ]
        return [
            {
                "change_id": c.id,
                "service": c.service,
                "risk_level": c.risk_level.value,
                "outcome": c.outcome.value,
                "files_changed": c.files_changed,
            }
            for c in high_risk[-limit:]
        ]

    def get_stats(self) -> dict[str, Any]:
        outcome_counts: dict[str, int] = {}
        risk_counts: dict[str, int] = {}
        for c in self._changes:
            outcome_counts[c.outcome] = outcome_counts.get(c.outcome, 0) + 1
            risk_counts[c.risk_level] = risk_counts.get(c.risk_level, 0) + 1
        return {
            "total_changes": len(self._changes),
            "outcome_distribution": outcome_counts,
            "risk_distribution": risk_counts,
            "success_rate": self.get_success_correlation()["success_rate"],
        }
