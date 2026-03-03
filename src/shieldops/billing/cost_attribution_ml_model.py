"""Cost Attribution ML Model — ML-powered cost attribution across teams and services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttributionMethod(StrEnum):
    RULE_BASED = "rule_based"
    ML_CLASSIFICATION = "ml_classification"
    PROPORTIONAL = "proportional"
    TAG_BASED = "tag_based"
    HYBRID = "hybrid"


class CostDimension(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    PROJECT = "project"
    ENVIRONMENT = "environment"
    CUSTOMER = "customer"


class ModelAccuracy(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TRAINING = "training"
    UNVALIDATED = "unvalidated"


# --- Models ---


class AttributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attribution_method: AttributionMethod = AttributionMethod.HYBRID
    cost_dimension: CostDimension = CostDimension.TEAM
    model_accuracy: ModelAccuracy = ModelAccuracy.UNVALIDATED
    attributed_cost: float = 0.0
    accuracy_score: float = 0.0
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AttributionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attribution_method: AttributionMethod = AttributionMethod.HYBRID
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAttributionMLReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_accuracy_count: int = 0
    avg_accuracy_score: float = 0.0
    by_attribution_method: dict[str, int] = Field(default_factory=dict)
    by_cost_dimension: dict[str, int] = Field(default_factory=dict)
    by_model_accuracy: dict[str, int] = Field(default_factory=dict)
    top_attributions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostAttributionMLModel:
    """ML-powered cost attribution across teams, services, and cost dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        accuracy_threshold: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._accuracy_threshold = accuracy_threshold
        self._records: list[AttributionRecord] = []
        self._analyses: list[AttributionAnalysis] = []
        logger.info(
            "cost_attribution_ml_model.initialized",
            max_records=max_records,
            accuracy_threshold=accuracy_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_attribution(
        self,
        attribution_method: AttributionMethod = AttributionMethod.HYBRID,
        cost_dimension: CostDimension = CostDimension.TEAM,
        model_accuracy: ModelAccuracy = ModelAccuracy.UNVALIDATED,
        attributed_cost: float = 0.0,
        accuracy_score: float = 0.0,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AttributionRecord:
        record = AttributionRecord(
            attribution_method=attribution_method,
            cost_dimension=cost_dimension,
            model_accuracy=model_accuracy,
            attributed_cost=attributed_cost,
            accuracy_score=accuracy_score,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_attribution_ml_model.attribution_recorded",
            record_id=record.id,
            attribution_method=attribution_method.value,
            accuracy_score=accuracy_score,
        )
        return record

    def get_attribution(self, record_id: str) -> AttributionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_attributions(
        self,
        attribution_method: AttributionMethod | None = None,
        cost_dimension: CostDimension | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AttributionRecord]:
        results = list(self._records)
        if attribution_method is not None:
            results = [r for r in results if r.attribution_method == attribution_method]
        if cost_dimension is not None:
            results = [r for r in results if r.cost_dimension == cost_dimension]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        attribution_method: AttributionMethod = AttributionMethod.HYBRID,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AttributionAnalysis:
        analysis = AttributionAnalysis(
            attribution_method=attribution_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cost_attribution_ml_model.analysis_added",
            attribution_method=attribution_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_method_distribution(self) -> dict[str, Any]:
        """Group by attribution_method; return count and avg accuracy_score."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.attribution_method.value
            method_data.setdefault(key, []).append(r.accuracy_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_accuracy_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_accuracy_attributions(self) -> list[dict[str, Any]]:
        """Return records where accuracy_score >= accuracy_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.accuracy_score >= self._accuracy_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "attribution_method": r.attribution_method.value,
                        "accuracy_score": r.accuracy_score,
                        "attributed_cost": r.attributed_cost,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["accuracy_score"], reverse=True)

    def rank_by_attributed_cost(self) -> list[dict[str, Any]]:
        """Group by team, total attributed_cost, sort descending."""
        team_costs: dict[str, float] = {}
        for r in self._records:
            team_costs[r.team] = team_costs.get(r.team, 0.0) + r.attributed_cost
        results: list[dict[str, Any]] = [
            {"team": team, "total_attributed_cost": round(cost, 2)}
            for team, cost in team_costs.items()
        ]
        results.sort(key=lambda x: x["total_attributed_cost"], reverse=True)
        return results

    def detect_accuracy_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CostAttributionMLReport:
        by_method: dict[str, int] = {}
        by_dimension: dict[str, int] = {}
        by_accuracy: dict[str, int] = {}
        for r in self._records:
            by_method[r.attribution_method.value] = by_method.get(r.attribution_method.value, 0) + 1
            by_dimension[r.cost_dimension.value] = by_dimension.get(r.cost_dimension.value, 0) + 1
            by_accuracy[r.model_accuracy.value] = by_accuracy.get(r.model_accuracy.value, 0) + 1
        high_accuracy_count = sum(
            1 for r in self._records if r.accuracy_score >= self._accuracy_threshold
        )
        scores = [r.accuracy_score for r in self._records]
        avg_accuracy_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        top_list = self.identify_high_accuracy_attributions()
        top_attributions = [o["record_id"] for o in top_list[:5]]
        recs: list[str] = []
        if high_accuracy_count > 0:
            recs.append(f"{high_accuracy_count} high-accuracy attribution(s) above threshold")
        if avg_accuracy_score < self._accuracy_threshold and self._records:
            recs.append(
                f"Avg accuracy {avg_accuracy_score}% below target ({self._accuracy_threshold}%)"
            )
        if not recs:
            recs.append("Cost attribution ML model is performing well")
        return CostAttributionMLReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_accuracy_count=high_accuracy_count,
            avg_accuracy_score=avg_accuracy_score,
            by_attribution_method=by_method,
            by_cost_dimension=by_dimension,
            by_model_accuracy=by_accuracy,
            top_attributions=top_attributions,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cost_attribution_ml_model.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attribution_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "accuracy_threshold": self._accuracy_threshold,
            "attribution_method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
