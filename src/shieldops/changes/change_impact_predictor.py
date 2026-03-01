"""Change Impact Predictor — predict change impact before deployment, estimate blast radius."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactCategory(StrEnum):
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    SECURITY = "security"
    DATA_INTEGRITY = "data_integrity"
    USER_EXPERIENCE = "user_experience"


class PredictionConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNCERTAIN = "uncertain"


class BlastRadius(StrEnum):
    ISOLATED = "isolated"
    SERVICE = "service"
    CLUSTER = "cluster"
    REGION = "region"
    GLOBAL = "global"


# --- Models ---


class ImpactPredictionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_id: str = ""
    impact_category: ImpactCategory = ImpactCategory.PERFORMANCE
    prediction_confidence: PredictionConfidence = PredictionConfidence.UNCERTAIN
    blast_radius: BlastRadius = BlastRadius.ISOLATED
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PredictionAccuracy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_id: str = ""
    impact_category: ImpactCategory = ImpactCategory.PERFORMANCE
    accuracy_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_accuracy_checks: int = 0
    high_impact_count: int = 0
    avg_impact_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_radius: dict[str, int] = Field(default_factory=dict)
    top_high_impact: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeImpactPredictor:
    """Predict change impact before deployment, estimate blast radius."""

    def __init__(
        self,
        max_records: int = 200000,
        max_high_impact_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_high_impact_pct = max_high_impact_pct
        self._records: list[ImpactPredictionRecord] = []
        self._accuracy_checks: list[PredictionAccuracy] = []
        logger.info(
            "change_impact_predictor.initialized",
            max_records=max_records,
            max_high_impact_pct=max_high_impact_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_prediction(
        self,
        prediction_id: str,
        impact_category: ImpactCategory = ImpactCategory.PERFORMANCE,
        prediction_confidence: PredictionConfidence = PredictionConfidence.UNCERTAIN,
        blast_radius: BlastRadius = BlastRadius.ISOLATED,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ImpactPredictionRecord:
        record = ImpactPredictionRecord(
            prediction_id=prediction_id,
            impact_category=impact_category,
            prediction_confidence=prediction_confidence,
            blast_radius=blast_radius,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_impact_predictor.prediction_recorded",
            record_id=record.id,
            prediction_id=prediction_id,
            impact_category=impact_category.value,
            blast_radius=blast_radius.value,
        )
        return record

    def get_prediction(self, record_id: str) -> ImpactPredictionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        category: ImpactCategory | None = None,
        confidence: PredictionConfidence | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ImpactPredictionRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.impact_category == category]
        if confidence is not None:
            results = [r for r in results if r.prediction_confidence == confidence]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_accuracy(
        self,
        prediction_id: str,
        impact_category: ImpactCategory = ImpactCategory.PERFORMANCE,
        accuracy_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PredictionAccuracy:
        accuracy = PredictionAccuracy(
            prediction_id=prediction_id,
            impact_category=impact_category,
            accuracy_score=accuracy_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._accuracy_checks.append(accuracy)
        if len(self._accuracy_checks) > self._max_records:
            self._accuracy_checks = self._accuracy_checks[-self._max_records :]
        logger.info(
            "change_impact_predictor.accuracy_added",
            prediction_id=prediction_id,
            impact_category=impact_category.value,
            accuracy_score=accuracy_score,
        )
        return accuracy

    # -- domain operations --------------------------------------------------

    def analyze_impact_distribution(self) -> dict[str, Any]:
        """Group by impact_category; return count and avg impact_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.impact_category.value
            cat_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact(self) -> list[dict[str, Any]]:
        """Return records where blast_radius is REGION or GLOBAL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.blast_radius in (BlastRadius.REGION, BlastRadius.GLOBAL):
                results.append(
                    {
                        "record_id": r.id,
                        "prediction_id": r.prediction_id,
                        "blast_radius": r.blast_radius.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        """Group by service, avg impact_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_prediction_trends(self) -> dict[str, Any]:
        """Split-half comparison on accuracy_score; delta threshold 5.0."""
        if len(self._accuracy_checks) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.accuracy_score for a in self._accuracy_checks]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
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

    def generate_report(self) -> ChangeImpactReport:
        by_category: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_radius: dict[str, int] = {}
        for r in self._records:
            by_category[r.impact_category.value] = by_category.get(r.impact_category.value, 0) + 1
            by_confidence[r.prediction_confidence.value] = (
                by_confidence.get(r.prediction_confidence.value, 0) + 1
            )
            by_radius[r.blast_radius.value] = by_radius.get(r.blast_radius.value, 0) + 1
        high_impact_count = sum(
            1 for r in self._records if r.blast_radius in (BlastRadius.REGION, BlastRadius.GLOBAL)
        )
        scores = [r.impact_score for r in self._records]
        avg_impact_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_impact()
        top_high_impact = [h["prediction_id"] for h in high_list[:5]]
        recs: list[str] = []
        high_pct = round(high_impact_count / len(self._records) * 100, 2) if self._records else 0.0
        if self._records and high_pct > self._max_high_impact_pct:
            recs.append(
                f"High-impact changes at {high_pct}% exceed threshold "
                f"({self._max_high_impact_pct}%)"
            )
        if high_impact_count > 0:
            recs.append(f"{high_impact_count} high-impact prediction(s) — review blast radius")
        if not recs:
            recs.append("Change impact levels are acceptable")
        return ChangeImpactReport(
            total_records=len(self._records),
            total_accuracy_checks=len(self._accuracy_checks),
            high_impact_count=high_impact_count,
            avg_impact_score=avg_impact_score,
            by_category=by_category,
            by_confidence=by_confidence,
            by_radius=by_radius,
            top_high_impact=top_high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._accuracy_checks.clear()
        logger.info("change_impact_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.impact_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_accuracy_checks": len(self._accuracy_checks),
            "max_high_impact_pct": self._max_high_impact_pct,
            "impact_category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
