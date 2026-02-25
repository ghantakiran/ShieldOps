"""Deployment Health Scorer — real-time composite health
score (0-100) for active/recent deployments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeployHealthGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    FAILING = "failing"


class HealthDimension(StrEnum):
    ERROR_RATE_DELTA = "error_rate_delta"
    LATENCY_DELTA = "latency_delta"
    CANARY_PASS_RATE = "canary_pass_rate"  # noqa: S105
    ROLLBACK_FREQUENCY = "rollback_frequency"
    CUSTOMER_REPORTS = "customer_reports"


class DeployPhase(StrEnum):
    CANARY = "canary"
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    BAKING = "baking"
    COMPLETE = "complete"


# --- Models ---


class HealthDimensionReading(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    dimension: HealthDimension = HealthDimension.ERROR_RATE_DELTA
    value: float = 0.0
    weight: float = 1.0
    created_at: float = Field(default_factory=time.time)


class DeployHealthScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    service_name: str = ""
    version: str = ""
    composite_score: float = 100.0
    grade: DeployHealthGrade = DeployHealthGrade.EXCELLENT
    phase: DeployPhase = DeployPhase.CANARY
    reading_count: int = 0
    created_at: float = Field(default_factory=time.time)


class DeployHealthReport(BaseModel):
    total_scores: int = 0
    total_readings: int = 0
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    avg_score: float = 0.0
    failing_deployments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentHealthScorer:
    """Real-time composite health score (0-100) for active/recent deployments."""

    def __init__(
        self,
        max_records: int = 200000,
        failing_threshold: float = 40.0,
    ) -> None:
        self._max_records = max_records
        self._failing_threshold = failing_threshold
        self._scores: list[DeployHealthScore] = []
        self._readings: list[HealthDimensionReading] = []
        logger.info(
            "deploy_health_scorer.initialized",
            max_records=max_records,
            failing_threshold=failing_threshold,
        )

    # -- score / get / list ------------------------------------------

    def score_deployment(
        self,
        deployment_id: str,
        service_name: str = "",
        version: str = "",
        composite_score: float = 100.0,
        phase: DeployPhase = DeployPhase.CANARY,
        **kw: Any,
    ) -> DeployHealthScore:
        grade = self._score_to_grade(composite_score)
        score = DeployHealthScore(
            deployment_id=deployment_id,
            service_name=service_name,
            version=version,
            composite_score=composite_score,
            grade=grade,
            phase=phase,
            **kw,
        )
        self._scores.append(score)
        if len(self._scores) > self._max_records:
            self._scores = self._scores[-self._max_records :]
        logger.info(
            "deploy_health_scorer.scored",
            score_id=score.id,
            deployment_id=deployment_id,
            composite_score=composite_score,
        )
        return score

    def get_score(self, score_id: str) -> DeployHealthScore | None:
        for s in self._scores:
            if s.id == score_id:
                return s
        return None

    def list_scores(
        self,
        service_name: str | None = None,
        grade: DeployHealthGrade | None = None,
        limit: int = 50,
    ) -> list[DeployHealthScore]:
        results = list(self._scores)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if grade is not None:
            results = [r for r in results if r.grade == grade]
        return results[-limit:]

    # -- dimension readings ------------------------------------------

    def record_dimension_reading(
        self,
        deployment_id: str,
        dimension: HealthDimension = HealthDimension.ERROR_RATE_DELTA,
        value: float = 0.0,
        weight: float = 1.0,
        **kw: Any,
    ) -> HealthDimensionReading:
        reading = HealthDimensionReading(
            deployment_id=deployment_id,
            dimension=dimension,
            value=value,
            weight=weight,
            **kw,
        )
        self._readings.append(reading)
        if len(self._readings) > self._max_records:
            self._readings = self._readings[-self._max_records :]
        logger.info(
            "deploy_health_scorer.reading_recorded",
            reading_id=reading.id,
            deployment_id=deployment_id,
        )
        return reading

    def list_dimension_readings(
        self,
        deployment_id: str | None = None,
        dimension: HealthDimension | None = None,
        limit: int = 50,
    ) -> list[HealthDimensionReading]:
        results = list(self._readings)
        if deployment_id is not None:
            results = [r for r in results if r.deployment_id == deployment_id]
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def compute_composite_score(
        self,
        deployment_id: str,
    ) -> DeployHealthScore:
        """Compute composite score from dimension readings."""
        readings = [r for r in self._readings if r.deployment_id == deployment_id]
        if not readings:
            return self.score_deployment(
                deployment_id=deployment_id,
                composite_score=100.0,
            )
        total_weight = sum(r.weight for r in readings)
        if total_weight == 0:
            composite = 100.0
        else:
            weighted_sum = sum(r.value * r.weight for r in readings)
            composite = round(max(0, min(100, weighted_sum / total_weight)), 2)
        # Find service_name from existing scores
        svc = ""
        for s in self._scores:
            if s.deployment_id == deployment_id:
                svc = s.service_name
                break
        score = self.score_deployment(
            deployment_id=deployment_id,
            service_name=svc,
            composite_score=composite,
        )
        score.reading_count = len(readings)
        return score

    def compare_deployments(
        self,
        deployment_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Compare health scores across multiple deployments."""
        results: list[dict[str, Any]] = []
        for did in deployment_ids:
            scores = [s for s in self._scores if s.deployment_id == did]
            if scores:
                latest = scores[-1]
                results.append(
                    {
                        "deployment_id": did,
                        "service_name": latest.service_name,
                        "composite_score": latest.composite_score,
                        "grade": latest.grade.value,
                        "phase": latest.phase.value,
                    }
                )
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results

    def detect_degradation(
        self,
        deployment_id: str,
    ) -> dict[str, Any]:
        """Detect if a deployment is degrading over time."""
        scores = [s for s in self._scores if s.deployment_id == deployment_id]
        if len(scores) < 2:
            return {
                "deployment_id": deployment_id,
                "degrading": False,
                "reason": "Insufficient data",
            }
        mid = len(scores) // 2
        first_avg = sum(s.composite_score for s in scores[:mid]) / mid
        second_avg = sum(s.composite_score for s in scores[mid:]) / (len(scores) - mid)
        degrading = second_avg < first_avg * 0.85
        return {
            "deployment_id": deployment_id,
            "degrading": degrading,
            "first_period_avg": round(first_avg, 2),
            "second_period_avg": round(second_avg, 2),
            "reason": "Score declining" if degrading else "Score stable",
        }

    # -- report / stats ----------------------------------------------

    def generate_health_report(self) -> DeployHealthReport:
        by_grade: dict[str, int] = {}
        for s in self._scores:
            key = s.grade.value
            by_grade[key] = by_grade.get(key, 0) + 1
        by_phase: dict[str, int] = {}
        for s in self._scores:
            key = s.phase.value
            by_phase[key] = by_phase.get(key, 0) + 1
        scores_vals = [s.composite_score for s in self._scores]
        avg_score = round(sum(scores_vals) / len(scores_vals), 2) if scores_vals else 0.0
        failing = [
            s.deployment_id for s in self._scores if s.composite_score < self._failing_threshold
        ]
        recs: list[str] = []
        if failing:
            recs.append(f"{len(failing)} deployment(s) below failing threshold")
        if not recs:
            recs.append("All deployments within healthy range")
        return DeployHealthReport(
            total_scores=len(self._scores),
            total_readings=len(self._readings),
            by_grade=by_grade,
            by_phase=by_phase,
            avg_score=avg_score,
            failing_deployments=list(set(failing)),
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._scores)
        self._scores.clear()
        self._readings.clear()
        logger.info("deploy_health_scorer.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        grade_dist: dict[str, int] = {}
        for s in self._scores:
            key = s.grade.value
            grade_dist[key] = grade_dist.get(key, 0) + 1
        return {
            "total_scores": len(self._scores),
            "total_readings": len(self._readings),
            "failing_threshold": self._failing_threshold,
            "grade_distribution": grade_dist,
        }

    # -- internal helpers --------------------------------------------

    def _score_to_grade(self, score: float) -> DeployHealthGrade:
        if score >= 90:
            return DeployHealthGrade.EXCELLENT
        if score >= 75:
            return DeployHealthGrade.GOOD
        if score >= 60:
            return DeployHealthGrade.FAIR
        if score >= 40:
            return DeployHealthGrade.POOR
        return DeployHealthGrade.FAILING
