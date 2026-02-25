"""Deployment Confidence Scorer — composite pre-deployment confidence score."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConfidenceLevel(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class ConfidenceFactor(StrEnum):
    TEST_COVERAGE = "test_coverage"
    ROLLBACK_READINESS = "rollback_readiness"
    CHANGE_SIZE = "change_size"
    BLAST_RADIUS = "blast_radius"
    TEAM_EXPERIENCE = "team_experience"


class DeployDecision(StrEnum):
    PROCEED = "proceed"
    PROCEED_WITH_CAUTION = "proceed_with_caution"
    REQUIRE_APPROVAL = "require_approval"
    DELAY = "delay"
    BLOCK = "block"


# --- Models ---


class ConfidenceAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    service: str = ""
    score: float = 0.0
    level: ConfidenceLevel = ConfidenceLevel.MODERATE
    decision: DeployDecision = DeployDecision.REQUIRE_APPROVAL
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ConfidenceFactorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    factor: ConfidenceFactor = ConfidenceFactor.TEST_COVERAGE
    score: float = 0.0
    weight: float = 1.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentConfidenceReport(BaseModel):
    total_assessments: int = 0
    total_factors: int = 0
    avg_confidence: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_decision: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentConfidenceScorer:
    """Composite pre-deployment confidence score."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_score = min_confidence_score
        self._records: list[ConfidenceAssessment] = []
        self._factors: list[ConfidenceFactorRecord] = []
        logger.info(
            "deployment_confidence.initialized",
            max_records=max_records,
            min_confidence_score=min_confidence_score,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_level(self, score: float) -> ConfidenceLevel:
        if score >= 90:
            return ConfidenceLevel.VERY_HIGH
        if score >= 75:
            return ConfidenceLevel.HIGH
        if score >= 60:
            return ConfidenceLevel.MODERATE
        if score >= 40:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW

    def _level_to_decision(self, level: ConfidenceLevel) -> DeployDecision:
        return {
            ConfidenceLevel.VERY_HIGH: DeployDecision.PROCEED,
            ConfidenceLevel.HIGH: DeployDecision.PROCEED_WITH_CAUTION,
            ConfidenceLevel.MODERATE: DeployDecision.REQUIRE_APPROVAL,
            ConfidenceLevel.LOW: DeployDecision.DELAY,
            ConfidenceLevel.VERY_LOW: DeployDecision.BLOCK,
        }.get(level, DeployDecision.REQUIRE_APPROVAL)

    # -- record / get / list ---------------------------------------------

    def record_factor(
        self,
        deployment_id: str,
        factor: ConfidenceFactor = ConfidenceFactor.TEST_COVERAGE,
        score: float = 0.0,
        weight: float = 1.0,
        details: str = "",
    ) -> ConfidenceFactorRecord:
        record = ConfidenceFactorRecord(
            deployment_id=deployment_id,
            factor=factor,
            score=score,
            weight=weight,
            details=details,
        )
        self._factors.append(record)
        if len(self._factors) > self._max_records:
            self._factors = self._factors[-self._max_records :]
        logger.info(
            "deployment_confidence.factor_recorded",
            record_id=record.id,
            deployment_id=deployment_id,
            factor=factor.value,
            score=score,
        )
        return record

    def get_assessment(self, record_id: str) -> ConfidenceAssessment | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        service: str | None = None,
        level: ConfidenceLevel | None = None,
        limit: int = 50,
    ) -> list[ConfidenceAssessment]:
        results = list(self._records)
        if service is not None:
            results = [r for r in results if r.service == service]
        if level is not None:
            results = [r for r in results if r.level == level]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def assess_deployment(self, deployment_id: str, service: str = "") -> ConfidenceAssessment:
        """Calculate composite confidence score from recorded factors."""
        factors = [f for f in self._factors if f.deployment_id == deployment_id]
        if not factors:
            assessment = ConfidenceAssessment(
                deployment_id=deployment_id,
                service=service,
                score=0.0,
                level=ConfidenceLevel.VERY_LOW,
                decision=DeployDecision.BLOCK,
            )
        else:
            total_weight = sum(f.weight for f in factors)
            weighted_score = sum(f.score * f.weight for f in factors)
            score = round(weighted_score / max(total_weight, 1), 2)
            level = self._score_to_level(score)
            decision = self._level_to_decision(level)
            assessment = ConfidenceAssessment(
                deployment_id=deployment_id,
                service=service,
                score=score,
                level=level,
                decision=decision,
            )
        self._records.append(assessment)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deployment_confidence.assessed",
            deployment_id=deployment_id,
            score=assessment.score,
            decision=assessment.decision.value,
        )
        return assessment

    def identify_low_confidence_deployments(self) -> list[dict[str, Any]]:
        """Find deployments below confidence threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._min_confidence_score:
                results.append(
                    {
                        "deployment_id": r.deployment_id,
                        "service": r.service,
                        "score": r.score,
                        "level": r.level.value,
                        "decision": r.decision.value,
                    }
                )
        results.sort(key=lambda x: x["score"])
        return results

    def analyze_factor_trends(self) -> list[dict[str, Any]]:
        """Analyze trends per confidence factor."""
        factor_scores: dict[str, list[float]] = {}
        for f in self._factors:
            factor_scores.setdefault(f.factor.value, []).append(f.score)
        results: list[dict[str, Any]] = []
        for factor, scores in factor_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "factor": factor,
                    "avg_score": avg,
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "samples": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def compare_deployments(self, dep_id_a: str, dep_id_b: str) -> dict[str, Any]:
        """Compare confidence factors between two deployments."""
        factors_a = {f.factor.value: f.score for f in self._factors if f.deployment_id == dep_id_a}
        factors_b = {f.factor.value: f.score for f in self._factors if f.deployment_id == dep_id_b}
        return {
            "deployment_a": dep_id_a,
            "deployment_b": dep_id_b,
            "factors_a": factors_a,
            "factors_b": factors_b,
        }

    def calculate_service_confidence_trend(self, service: str) -> list[dict[str, Any]]:
        """Get confidence trend for a service over time."""
        svc_records = [r for r in self._records if r.service == service]
        return [
            {
                "deployment_id": r.deployment_id,
                "score": r.score,
                "level": r.level.value,
                "decision": r.decision.value,
                "created_at": r.created_at,
            }
            for r in svc_records
        ]

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DeploymentConfidenceReport:
        by_level: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        for r in self._records:
            by_level[r.level.value] = by_level.get(r.level.value, 0) + 1
            by_decision[r.decision.value] = by_decision.get(r.decision.value, 0) + 1
        avg_conf = (
            round(sum(r.score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        low_count = sum(1 for r in self._records if r.score < self._min_confidence_score)
        recs: list[str] = []
        if low_count > 0:
            recs.append(
                f"{low_count} deployment(s) below confidence threshold "
                f"of {self._min_confidence_score}"
            )
        blocked = sum(1 for r in self._records if r.decision == DeployDecision.BLOCK)
        if blocked > 0:
            recs.append(f"{blocked} deployment(s) blocked due to low confidence")
        if not recs:
            recs.append("Deployment confidence levels are healthy")
        return DeploymentConfidenceReport(
            total_assessments=len(self._records),
            total_factors=len(self._factors),
            avg_confidence=avg_conf,
            by_level=by_level,
            by_decision=by_decision,
            low_confidence_count=low_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._factors.clear()
        logger.info("deployment_confidence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_assessments": len(self._records),
            "total_factors": len(self._factors),
            "min_confidence_score": self._min_confidence_score,
            "level_distribution": level_dist,
            "unique_services": len({r.service for r in self._records}),
        }
