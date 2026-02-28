"""Decision Audit Logger — agent decision audit trail."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DecisionType(StrEnum):
    REMEDIATION = "remediation"
    ESCALATION = "escalation"
    SCALING = "scaling"
    ROLLBACK = "rollback"
    ALERT_SUPPRESSION = "alert_suppression"


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    PENDING = "pending"


class ConfidenceLevel(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNCERTAIN = "uncertain"


# --- Models ---


class DecisionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    decision_type: DecisionType = DecisionType.REMEDIATION
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    confidence_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DecisionRationale(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rationale_name: str = ""
    decision_type: DecisionType = DecisionType.REMEDIATION
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    weight: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DecisionAuditReport(BaseModel):
    total_decisions: int = 0
    total_rationales: int = 0
    avg_confidence_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DecisionAuditLogger:
    """Audit trail for autonomous agent decisions with reasoning transparency."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[DecisionRecord] = []
        self._rationales: list[DecisionRationale] = []
        logger.info(
            "decision_audit.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_decision(
        self,
        agent_name: str,
        decision_type: DecisionType = DecisionType.REMEDIATION,
        outcome: DecisionOutcome = DecisionOutcome.PENDING,
        confidence: ConfidenceLevel = ConfidenceLevel.MODERATE,
        confidence_score: float = 0.0,
        details: str = "",
    ) -> DecisionRecord:
        record = DecisionRecord(
            agent_name=agent_name,
            decision_type=decision_type,
            outcome=outcome,
            confidence=confidence,
            confidence_score=confidence_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "decision_audit.recorded",
            record_id=record.id,
            agent_name=agent_name,
            decision_type=decision_type.value,
            outcome=outcome.value,
        )
        return record

    def get_decision(self, record_id: str) -> DecisionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_decisions(
        self,
        agent_name: str | None = None,
        decision_type: DecisionType | None = None,
        limit: int = 50,
    ) -> list[DecisionRecord]:
        results = list(self._records)
        if agent_name is not None:
            results = [r for r in results if r.agent_name == agent_name]
        if decision_type is not None:
            results = [r for r in results if r.decision_type == decision_type]
        return results[-limit:]

    def add_rationale(
        self,
        rationale_name: str,
        decision_type: DecisionType = DecisionType.REMEDIATION,
        confidence: ConfidenceLevel = ConfidenceLevel.MODERATE,
        weight: float = 0.0,
        description: str = "",
    ) -> DecisionRationale:
        rationale = DecisionRationale(
            rationale_name=rationale_name,
            decision_type=decision_type,
            confidence=confidence,
            weight=weight,
            description=description,
        )
        self._rationales.append(rationale)
        if len(self._rationales) > self._max_records:
            self._rationales = self._rationales[-self._max_records :]
        logger.info(
            "decision_audit.rationale_added",
            rationale_name=rationale_name,
            decision_type=decision_type.value,
            confidence=confidence.value,
        )
        return rationale

    # -- domain operations -----------------------------------------------

    def analyze_agent_decisions(self, agent_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.agent_name == agent_name]
        if not records:
            return {"agent_name": agent_name, "status": "no_data"}
        avg_confidence = round(sum(r.confidence_score for r in records) / len(records), 2)
        low_conf = sum(
            1 for r in records if r.confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)
        )
        return {
            "agent_name": agent_name,
            "total_records": len(records),
            "avg_confidence": avg_confidence,
            "low_confidence_count": low_conf,
            "meets_threshold": avg_confidence >= self._min_confidence_pct,
        }

    def identify_low_confidence_decisions(self) -> list[dict[str, Any]]:
        low_counts: dict[str, int] = {}
        for r in self._records:
            if r.confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN):
                low_counts[r.agent_name] = low_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in low_counts.items():
            if count > 1:
                results.append({"agent_name": agent, "low_confidence_count": count})
        results.sort(key=lambda x: x["low_confidence_count"], reverse=True)
        return results

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        agent_scores: dict[str, list[float]] = {}
        for r in self._records:
            agent_scores.setdefault(r.agent_name, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for agent, scores in agent_scores.items():
            results.append(
                {
                    "agent_name": agent,
                    "avg_confidence": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_confidence"], reverse=True)
        return results

    def detect_decision_patterns(self) -> list[dict[str, Any]]:
        agent_counts: dict[str, int] = {}
        for r in self._records:
            agent_counts[r.agent_name] = agent_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_counts.items():
            if count > 3:
                results.append(
                    {
                        "agent_name": agent,
                        "decision_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["decision_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DecisionAuditReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_type[r.decision_type.value] = by_type.get(r.decision_type.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        avg_confidence = (
            round(
                sum(r.confidence_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low_conf = sum(
            1
            for r in self._records
            if r.confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)
        )
        recs: list[str] = []
        if avg_confidence < self._min_confidence_pct:
            recs.append(
                f"Avg confidence {avg_confidence}% below {self._min_confidence_pct}% threshold"
            )
        recurring = len(self.detect_decision_patterns())
        if recurring > 0:
            recs.append(f"{recurring} agent(s) with recurring decision patterns")
        if not recs:
            recs.append("Decision audit analysis meets targets")
        return DecisionAuditReport(
            total_decisions=len(self._records),
            total_rationales=len(self._rationales),
            avg_confidence_pct=avg_confidence,
            by_type=by_type,
            by_outcome=by_outcome,
            low_confidence_count=low_conf,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rationales.clear()
        logger.info("decision_audit.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.decision_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_decisions": len(self._records),
            "total_rationales": len(self._rationales),
            "min_confidence_pct": self._min_confidence_pct,
            "type_distribution": type_dist,
            "unique_agents": len({r.agent_name for r in self._records}),
        }
