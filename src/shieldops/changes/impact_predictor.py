"""Deployment Impact Predictor — predict and analyze deployment impact across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactScope(StrEnum):
    GLOBAL = "global"
    REGIONAL = "regional"
    SERVICE_LEVEL = "service_level"
    COMPONENT = "component"
    MINIMAL = "minimal"


class ImpactCategory(StrEnum):
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    SECURITY = "security"
    DATA_INTEGRITY = "data_integrity"
    USER_EXPERIENCE = "user_experience"


class PredictionBasis(StrEnum):
    HISTORICAL_DATA = "historical_data"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    CODE_ANALYSIS = "code_analysis"
    ML_MODEL = "ml_model"
    EXPERT_JUDGMENT = "expert_judgment"


# --- Models ---


class ImpactPredictionRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    deployment_name: str = ""
    scope: ImpactScope = ImpactScope.MINIMAL
    category: ImpactCategory = ImpactCategory.PERFORMANCE
    basis: PredictionBasis = PredictionBasis.HISTORICAL_DATA
    impact_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactDetail(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    detail_name: str = ""
    scope: ImpactScope = ImpactScope.MINIMAL
    category: ImpactCategory = ImpactCategory.PERFORMANCE
    impact_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactPredictorReport(BaseModel):
    total_predictions: int = 0
    total_details: int = 0
    avg_impact_score_pct: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    high_impact_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentImpactPredictor:
    """Predict deployment impact, detect high-impact deploys, and analyze accuracy trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_impact_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._max_impact_score = max_impact_score
        self._records: list[ImpactPredictionRecord] = []
        self._details: list[ImpactDetail] = []
        logger.info(
            "impact_predictor.initialized",
            max_records=max_records,
            max_impact_score=max_impact_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_prediction(
        self,
        deployment_name: str,
        scope: ImpactScope = ImpactScope.MINIMAL,
        category: ImpactCategory = ImpactCategory.PERFORMANCE,
        basis: PredictionBasis = PredictionBasis.HISTORICAL_DATA,
        impact_score: float = 0.0,
        details: str = "",
    ) -> ImpactPredictionRecord:
        record = ImpactPredictionRecord(
            deployment_name=deployment_name,
            scope=scope,
            category=category,
            basis=basis,
            impact_score=impact_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "impact_predictor.recorded",
            record_id=record.id,
            deployment_name=deployment_name,
            scope=scope.value,
            category=category.value,
        )
        return record

    def get_prediction(self, record_id: str) -> ImpactPredictionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        scope: ImpactScope | None = None,
        category: ImpactCategory | None = None,
        limit: int = 50,
    ) -> list[ImpactPredictionRecord]:
        results = list(self._records)
        if scope is not None:
            results = [r for r in results if r.scope == scope]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_detail(
        self,
        detail_name: str,
        scope: ImpactScope = ImpactScope.MINIMAL,
        category: ImpactCategory = ImpactCategory.PERFORMANCE,
        impact_score: float = 0.0,
        description: str = "",
    ) -> ImpactDetail:
        detail = ImpactDetail(
            detail_name=detail_name,
            scope=scope,
            category=category,
            impact_score=impact_score,
            description=description,
        )
        self._details.append(detail)
        if len(self._details) > self._max_records:
            self._details = self._details[-self._max_records :]
        logger.info(
            "impact_predictor.detail_added",
            detail_name=detail_name,
            scope=scope.value,
            category=category.value,
        )
        return detail

    # -- domain operations -----------------------------------------------

    def analyze_prediction_accuracy(self, deployment_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.deployment_name == deployment_name]
        if not records:
            return {"deployment_name": deployment_name, "status": "no_data"}
        avg_score = round(sum(r.impact_score for r in records) / len(records), 2)
        high_impact = sum(
            1 for r in records if r.scope in (ImpactScope.GLOBAL, ImpactScope.REGIONAL)
        )
        return {
            "deployment_name": deployment_name,
            "total_records": len(records),
            "avg_impact_score": avg_score,
            "high_impact_count": high_impact,
            "exceeds_threshold": avg_score >= self._max_impact_score,
        }

    def identify_high_impact_deploys(self) -> list[dict[str, Any]]:
        high_impact_counts: dict[str, int] = {}
        for r in self._records:
            if r.scope in (ImpactScope.GLOBAL, ImpactScope.REGIONAL):
                high_impact_counts[r.deployment_name] = (
                    high_impact_counts.get(r.deployment_name, 0) + 1
                )
        results: list[dict[str, Any]] = []
        for deploy, count in high_impact_counts.items():
            if count > 1:
                results.append({"deployment_name": deploy, "high_impact_count": count})
        results.sort(key=lambda x: x["high_impact_count"], reverse=True)
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        deploy_scores: dict[str, list[float]] = {}
        for r in self._records:
            deploy_scores.setdefault(r.deployment_name, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for deploy, scores in deploy_scores.items():
            results.append(
                {
                    "deployment_name": deploy,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_impact_patterns(self) -> list[dict[str, Any]]:
        deploy_counts: dict[str, int] = {}
        for r in self._records:
            deploy_counts[r.deployment_name] = deploy_counts.get(r.deployment_name, 0) + 1
        results: list[dict[str, Any]] = []
        for deploy, count in deploy_counts.items():
            if count > 3:
                results.append(
                    {
                        "deployment_name": deploy,
                        "prediction_count": count,
                        "pattern_detected": True,
                    }
                )
        results.sort(key=lambda x: x["prediction_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ImpactPredictorReport:
        by_scope: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_scope[r.scope.value] = by_scope.get(r.scope.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        avg_score = (
            round(sum(r.impact_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        high_impact = sum(
            1 for r in self._records if r.scope in (ImpactScope.GLOBAL, ImpactScope.REGIONAL)
        )
        recs: list[str] = []
        if avg_score >= self._max_impact_score:
            recs.append(
                f"Average impact score {avg_score}% exceeds {self._max_impact_score}% threshold"
            )
        patterns = len(self.detect_impact_patterns())
        if patterns > 0:
            recs.append(f"{patterns} deployment(s) with recurring high-impact patterns")
        if not recs:
            recs.append("Deployment impact scores are within acceptable risk thresholds")
        return ImpactPredictorReport(
            total_predictions=len(self._records),
            total_details=len(self._details),
            avg_impact_score_pct=avg_score,
            by_scope=by_scope,
            by_category=by_category,
            high_impact_count=high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._details.clear()
        logger.info("impact_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_predictions": len(self._records),
            "total_details": len(self._details),
            "max_impact_score": self._max_impact_score,
            "scope_distribution": scope_dist,
            "unique_deployments": len({r.deployment_name for r in self._records}),
        }
