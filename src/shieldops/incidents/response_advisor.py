"""Incident Response Advisor — recommend ranked response strategies for active incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResponseStrategy(StrEnum):
    ESCALATE = "escalate"
    MITIGATE = "mitigate"
    FAILOVER = "failover"
    ROLLBACK = "rollback"
    OBSERVE = "observe"


class Urgency(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    DEFERRED = "deferred"


class ConfidenceBand(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class IncidentContext(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    service: str = ""
    severity: str = "medium"
    blast_radius: int = 1
    error_budget_remaining_pct: float = 100.0
    active_users_affected: int = 0
    created_at: float = Field(default_factory=time.time)


class ResponseRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    strategy: ResponseStrategy = ResponseStrategy.OBSERVE
    urgency: Urgency = Urgency.MODERATE
    confidence: ConfidenceBand = ConfidenceBand.MEDIUM
    confidence_score: float = 0.5
    estimated_resolution_minutes: float = 60.0
    rationale: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseAdvisorReport(BaseModel):
    total_contexts: int = 0
    total_recommendations: int = 0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    avg_confidence_score: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentResponseAdvisor:
    """Recommend ranked response strategies for active incidents."""

    def __init__(
        self,
        max_records: int = 200000,
        confidence_threshold: float = 0.6,
    ) -> None:
        self._max_records = max_records
        self._confidence_threshold = confidence_threshold
        self._contexts: list[IncidentContext] = []
        self._recommendations: list[ResponseRecommendation] = []
        logger.info(
            "response_advisor.initialized",
            max_records=max_records,
            confidence_threshold=confidence_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_confidence(self, score: float) -> ConfidenceBand:
        if score >= 0.9:
            return ConfidenceBand.VERY_HIGH
        if score >= 0.75:
            return ConfidenceBand.HIGH
        if score >= 0.5:
            return ConfidenceBand.MEDIUM
        if score >= 0.3:
            return ConfidenceBand.LOW
        return ConfidenceBand.INSUFFICIENT_DATA

    def _severity_to_urgency(self, severity: str, blast_radius: int) -> Urgency:
        if severity == "critical" or blast_radius > 100:
            return Urgency.IMMEDIATE
        if severity == "high" or blast_radius > 50:
            return Urgency.HIGH
        if severity == "medium" or blast_radius > 10:
            return Urgency.MODERATE
        if severity == "low":
            return Urgency.LOW
        return Urgency.DEFERRED

    # -- record / get / list ---------------------------------------------

    def record_context(
        self,
        incident_id: str,
        service: str = "",
        severity: str = "medium",
        blast_radius: int = 1,
        error_budget_remaining_pct: float = 100.0,
        active_users_affected: int = 0,
    ) -> IncidentContext:
        ctx = IncidentContext(
            incident_id=incident_id,
            service=service,
            severity=severity,
            blast_radius=blast_radius,
            error_budget_remaining_pct=error_budget_remaining_pct,
            active_users_affected=active_users_affected,
        )
        self._contexts.append(ctx)
        if len(self._contexts) > self._max_records:
            self._contexts = self._contexts[-self._max_records :]
        logger.info(
            "response_advisor.context_recorded",
            context_id=ctx.id,
            incident_id=incident_id,
            severity=severity,
        )
        return ctx

    def get_context(self, context_id: str) -> IncidentContext | None:
        for c in self._contexts:
            if c.id == context_id:
                return c
        return None

    def list_contexts(
        self,
        incident_id: str | None = None,
        limit: int = 50,
    ) -> list[IncidentContext]:
        results = list(self._contexts)
        if incident_id is not None:
            results = [c for c in results if c.incident_id == incident_id]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def generate_recommendation(
        self,
        incident_id: str,
    ) -> ResponseRecommendation:
        """Generate a response recommendation based on incident context."""
        # Find the most recent context for this incident
        contexts = [c for c in self._contexts if c.incident_id == incident_id]
        if not contexts:
            rec = ResponseRecommendation(
                incident_id=incident_id,
                strategy=ResponseStrategy.OBSERVE,
                urgency=Urgency.LOW,
                confidence=ConfidenceBand.INSUFFICIENT_DATA,
                confidence_score=0.2,
                rationale="No context available — defaulting to observe",
            )
            self._recommendations.append(rec)
            return rec

        ctx = contexts[-1]
        urgency = self._severity_to_urgency(ctx.severity, ctx.blast_radius)

        # Determine strategy based on context
        if ctx.error_budget_remaining_pct < 10:
            strategy = ResponseStrategy.ROLLBACK
            confidence_score = 0.85
        elif ctx.blast_radius > 50:
            strategy = ResponseStrategy.FAILOVER
            confidence_score = 0.8
        elif ctx.severity in ("critical", "high"):
            strategy = ResponseStrategy.MITIGATE
            confidence_score = 0.75
        elif ctx.active_users_affected > 1000:
            strategy = ResponseStrategy.ESCALATE
            confidence_score = 0.7
        else:
            strategy = ResponseStrategy.OBSERVE
            confidence_score = 0.6

        confidence = self._score_to_confidence(confidence_score)
        estimated_minutes = {
            ResponseStrategy.ROLLBACK: 15.0,
            ResponseStrategy.FAILOVER: 30.0,
            ResponseStrategy.MITIGATE: 45.0,
            ResponseStrategy.ESCALATE: 60.0,
            ResponseStrategy.OBSERVE: 120.0,
        }.get(strategy, 60.0)

        rationale = (
            f"Severity={ctx.severity}, blast_radius={ctx.blast_radius}, "
            f"error_budget={ctx.error_budget_remaining_pct}%"
        )

        rec = ResponseRecommendation(
            incident_id=incident_id,
            strategy=strategy,
            urgency=urgency,
            confidence=confidence,
            confidence_score=confidence_score,
            estimated_resolution_minutes=estimated_minutes,
            rationale=rationale,
        )
        self._recommendations.append(rec)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        logger.info(
            "response_advisor.recommendation_generated",
            rec_id=rec.id,
            incident_id=incident_id,
            strategy=strategy.value,
            urgency=urgency.value,
        )
        return rec

    def rank_strategies(self, incident_id: str) -> list[dict[str, Any]]:
        """Rank all possible strategies for an incident."""
        contexts = [c for c in self._contexts if c.incident_id == incident_id]
        if not contexts:
            return []
        ctx = contexts[-1]
        rankings: list[dict[str, Any]] = []
        for strategy in ResponseStrategy:
            if strategy == ResponseStrategy.ROLLBACK:
                score = 0.9 if ctx.error_budget_remaining_pct < 10 else 0.3
            elif strategy == ResponseStrategy.FAILOVER:
                score = 0.85 if ctx.blast_radius > 50 else 0.25
            elif strategy == ResponseStrategy.MITIGATE:
                score = 0.75 if ctx.severity in ("critical", "high") else 0.4
            elif strategy == ResponseStrategy.ESCALATE:
                score = 0.7 if ctx.active_users_affected > 1000 else 0.35
            else:
                score = 0.5
            rankings.append(
                {
                    "strategy": strategy.value,
                    "score": round(score, 4),
                    "confidence": self._score_to_confidence(score).value,
                }
            )
        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings

    def assess_escalation_need(self, incident_id: str) -> dict[str, Any]:
        """Check if an incident needs escalation."""
        contexts = [c for c in self._contexts if c.incident_id == incident_id]
        if not contexts:
            return {"incident_id": incident_id, "needs_escalation": False, "reason": "no context"}
        ctx = contexts[-1]
        needs = (
            ctx.severity == "critical"
            or ctx.blast_radius > 100
            or ctx.error_budget_remaining_pct < 5
            or ctx.active_users_affected > 5000
        )
        reasons: list[str] = []
        if ctx.severity == "critical":
            reasons.append("critical severity")
        if ctx.blast_radius > 100:
            reasons.append(f"blast radius {ctx.blast_radius}")
        if ctx.error_budget_remaining_pct < 5:
            reasons.append(f"error budget {ctx.error_budget_remaining_pct}%")
        if ctx.active_users_affected > 5000:
            reasons.append(f"{ctx.active_users_affected} users affected")
        return {
            "incident_id": incident_id,
            "needs_escalation": needs,
            "reason": "; ".join(reasons) if reasons else "within normal parameters",
        }

    def estimate_resolution_time(self, incident_id: str) -> dict[str, Any]:
        """Estimate time to resolution based on context."""
        contexts = [c for c in self._contexts if c.incident_id == incident_id]
        if not contexts:
            return {
                "incident_id": incident_id,
                "estimated_minutes": 0,
                "confidence": "insufficient_data",
            }
        ctx = contexts[-1]
        base_minutes = {"critical": 30.0, "high": 60.0, "medium": 120.0, "low": 240.0}.get(
            ctx.severity, 120.0
        )
        # Adjust for blast radius
        multiplier = 1.0 + (ctx.blast_radius / 100)
        estimated = round(base_minutes * multiplier, 1)
        confidence_score = 0.7 if len(contexts) > 1 else 0.5
        return {
            "incident_id": incident_id,
            "estimated_minutes": estimated,
            "confidence": self._score_to_confidence(confidence_score).value,
            "confidence_score": confidence_score,
        }

    def list_recommendations(
        self,
        incident_id: str | None = None,
        limit: int = 50,
    ) -> list[ResponseRecommendation]:
        results = list(self._recommendations)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        return results[-limit:]

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ResponseAdvisorReport:
        by_strategy: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        total_conf = 0.0
        for r in self._recommendations:
            by_strategy[r.strategy.value] = by_strategy.get(r.strategy.value, 0) + 1
            by_urgency[r.urgency.value] = by_urgency.get(r.urgency.value, 0) + 1
            total_conf += r.confidence_score
        avg_conf = (
            round(total_conf / len(self._recommendations), 4) if self._recommendations else 0.0
        )
        recs: list[str] = []
        immediate_count = by_urgency.get(Urgency.IMMEDIATE.value, 0)
        if immediate_count > 0:
            recs.append(f"{immediate_count} incident(s) require immediate action")
        rollback_count = by_strategy.get(ResponseStrategy.ROLLBACK.value, 0)
        if rollback_count > 0:
            recs.append(f"{rollback_count} rollback(s) recommended")
        if avg_conf < self._confidence_threshold:
            recs.append("Average confidence below threshold — review context data")
        if not recs:
            recs.append("All incidents within normal parameters")
        return ResponseAdvisorReport(
            total_contexts=len(self._contexts),
            total_recommendations=len(self._recommendations),
            by_strategy=by_strategy,
            by_urgency=by_urgency,
            avg_confidence_score=avg_conf,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._contexts.clear()
        self._recommendations.clear()
        logger.info("response_advisor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._recommendations:
            key = r.strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_contexts": len(self._contexts),
            "total_recommendations": len(self._recommendations),
            "confidence_threshold": self._confidence_threshold,
            "strategy_distribution": strategy_dist,
            "unique_incidents": len({c.incident_id for c in self._contexts}),
        }
