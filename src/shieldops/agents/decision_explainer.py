"""Agent decision explainability for audit trails and transparency.

Records the full reasoning chain behind every agent decision, including
intermediate steps, alternatives considered, confidence levels, and final
outcomes. Designed for compliance audits and operational debugging.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class DecisionOutcome(enum.StrEnum):
    EXECUTED = "executed"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    ESCALATED = "escalated"


class ConfidenceLevel(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# -- Models --------------------------------------------------------------------


class DecisionStep(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str
    reasoning: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    timestamp: float = Field(default_factory=time.time)


class AlternativeConsidered(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str
    reason_rejected: str = ""
    estimated_impact: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class DecisionRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str
    agent_type: str = ""
    action: str
    outcome: DecisionOutcome = DecisionOutcome.DEFERRED
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    steps: list[DecisionStep] = Field(default_factory=list)
    alternatives: list[AlternativeConsidered] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    finalized: bool = False
    created_at: float = Field(default_factory=time.time)
    finalized_at: float | None = None


# -- Engine --------------------------------------------------------------------


class AgentDecisionExplainer:
    """Record and explain agent decision-making for audits.

    Parameters
    ----------
    max_records:
        Maximum decision records to store.
    retention_days:
        Number of days to retain records.
    """

    def __init__(
        self,
        max_records: int = 50000,
        retention_days: int = 90,
    ) -> None:
        self._decisions: dict[str, DecisionRecord] = {}
        self._max_records = max_records
        self._retention_days = retention_days

    def record_decision(
        self,
        agent_id: str,
        action: str,
        agent_type: str = "",
        context: dict[str, Any] | None = None,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    ) -> DecisionRecord:
        if len(self._decisions) >= self._max_records:
            raise ValueError(f"Maximum decision records limit reached: {self._max_records}")
        record = DecisionRecord(
            agent_id=agent_id,
            action=action,
            agent_type=agent_type,
            context=context or {},
            confidence=confidence,
        )
        self._decisions[record.id] = record
        logger.info(
            "decision_recorded",
            decision_id=record.id,
            agent_id=agent_id,
            action=action,
        )
        return record

    def add_step(
        self,
        decision_id: str,
        description: str,
        reasoning: str = "",
        inputs: dict[str, Any] | None = None,
        output: str = "",
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    ) -> DecisionStep | None:
        decision = self._decisions.get(decision_id)
        if decision is None:
            raise ValueError(f"Decision not found: {decision_id}")
        if decision.finalized:
            raise ValueError(f"Decision already finalized: {decision_id}")
        step = DecisionStep(
            description=description,
            reasoning=reasoning,
            inputs=inputs or {},
            output=output,
            confidence=confidence,
        )
        decision.steps.append(step)
        logger.info(
            "decision_step_added",
            decision_id=decision_id,
            step_id=step.id,
        )
        return step

    def add_alternative(
        self,
        decision_id: str,
        description: str,
        reason_rejected: str = "",
        estimated_impact: str = "",
        confidence: ConfidenceLevel = ConfidenceLevel.LOW,
    ) -> AlternativeConsidered | None:
        decision = self._decisions.get(decision_id)
        if decision is None:
            return None
        alt = AlternativeConsidered(
            description=description,
            reason_rejected=reason_rejected,
            estimated_impact=estimated_impact,
            confidence=confidence,
        )
        decision.alternatives.append(alt)
        logger.info(
            "decision_alternative_added",
            decision_id=decision_id,
            alternative_id=alt.id,
        )
        return alt

    def finalize_decision(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        summary: str = "",
    ) -> DecisionRecord | None:
        decision = self._decisions.get(decision_id)
        if decision is None:
            return None
        decision.outcome = outcome
        decision.summary = summary
        decision.finalized = True
        decision.finalized_at = time.time()
        logger.info(
            "decision_finalized",
            decision_id=decision_id,
            outcome=outcome,
        )
        return decision

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        return self._decisions.get(decision_id)

    def list_decisions(
        self,
        agent_id: str | None = None,
        outcome: DecisionOutcome | None = None,
    ) -> list[DecisionRecord]:
        decisions = list(self._decisions.values())
        if agent_id:
            decisions = [d for d in decisions if d.agent_id == agent_id]
        if outcome:
            decisions = [d for d in decisions if d.outcome == outcome]
        return decisions

    def get_by_agent(self, agent_id: str) -> list[DecisionRecord]:
        return [d for d in self._decisions.values() if d.agent_id == agent_id]

    def get_explanation(self, decision_id: str) -> dict[str, Any] | None:
        decision = self._decisions.get(decision_id)
        if decision is None:
            return None
        return {
            "decision_id": decision.id,
            "action": decision.action,
            "outcome": decision.outcome.value,
            "confidence": decision.confidence.value,
            "steps": [
                {
                    "description": s.description,
                    "reasoning": s.reasoning,
                    "output": s.output,
                    "confidence": s.confidence.value,
                }
                for s in decision.steps
            ],
            "alternatives": [
                {
                    "description": a.description,
                    "reason_rejected": a.reason_rejected,
                    "estimated_impact": a.estimated_impact,
                }
                for a in decision.alternatives
            ],
            "summary": decision.summary,
            "agent_id": decision.agent_id,
            "agent_type": decision.agent_type,
            "finalized": decision.finalized,
        }

    def get_stats(self) -> dict[str, Any]:
        finalized = sum(1 for d in self._decisions.values() if d.finalized)
        outcome_counts: dict[str, int] = {}
        for d in self._decisions.values():
            key = d.outcome.value
            outcome_counts[key] = outcome_counts.get(key, 0) + 1
        unique_agents = len({d.agent_id for d in self._decisions.values()})
        return {
            "total_decisions": len(self._decisions),
            "finalized_decisions": finalized,
            "pending_decisions": len(self._decisions) - finalized,
            "outcome_breakdown": outcome_counts,
            "unique_agents": unique_agents,
            "max_records": self._max_records,
            "retention_days": self._retention_days,
        }
