"""Response Time Predictor — predict incident response times using historical and ML models."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IncidentComplexity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TRIVIAL = "trivial"


class PredictionModel(StrEnum):
    HISTORICAL = "historical"
    ML_REGRESSION = "ml_regression"
    BAYESIAN = "bayesian"
    ENSEMBLE = "ensemble"
    RULE_BASED = "rule_based"


class PredictionAccuracy(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNRELIABLE = "unreliable"


# --- Models ---


class ResponseTimePrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_id: str = ""
    incident_complexity: IncidentComplexity = IncidentComplexity.MEDIUM
    prediction_model: PredictionModel = PredictionModel.HISTORICAL
    prediction_accuracy: PredictionAccuracy = PredictionAccuracy.GOOD
    prediction_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseTimePredictionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_id: str = ""
    incident_complexity: IncidentComplexity = IncidentComplexity.MEDIUM
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseTimePredictionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_prediction_score: float = 0.0
    by_complexity: dict[str, int] = Field(default_factory=dict)
    by_model: dict[str, int] = Field(default_factory=dict)
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResponseTimePredictor:
    """Predict incident response times using historical data and ML models."""

    def __init__(
        self,
        max_records: int = 200000,
        prediction_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._prediction_threshold = prediction_threshold
        self._records: list[ResponseTimePrediction] = []
        self._analyses: list[ResponseTimePredictionAnalysis] = []
        logger.info(
            "response_time_predictor.initialized",
            max_records=max_records,
            prediction_threshold=prediction_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_prediction(
        self,
        prediction_id: str,
        incident_complexity: IncidentComplexity = IncidentComplexity.MEDIUM,
        prediction_model: PredictionModel = PredictionModel.HISTORICAL,
        prediction_accuracy: PredictionAccuracy = PredictionAccuracy.GOOD,
        prediction_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ResponseTimePrediction:
        record = ResponseTimePrediction(
            prediction_id=prediction_id,
            incident_complexity=incident_complexity,
            prediction_model=prediction_model,
            prediction_accuracy=prediction_accuracy,
            prediction_score=prediction_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_time_predictor.prediction_recorded",
            record_id=record.id,
            prediction_id=prediction_id,
            incident_complexity=incident_complexity.value,
            prediction_model=prediction_model.value,
        )
        return record

    def get_prediction(self, record_id: str) -> ResponseTimePrediction | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        incident_complexity: IncidentComplexity | None = None,
        prediction_model: PredictionModel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ResponseTimePrediction]:
        results = list(self._records)
        if incident_complexity is not None:
            results = [r for r in results if r.incident_complexity == incident_complexity]
        if prediction_model is not None:
            results = [r for r in results if r.prediction_model == prediction_model]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        prediction_id: str,
        incident_complexity: IncidentComplexity = IncidentComplexity.MEDIUM,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ResponseTimePredictionAnalysis:
        analysis = ResponseTimePredictionAnalysis(
            prediction_id=prediction_id,
            incident_complexity=incident_complexity,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "response_time_predictor.analysis_added",
            prediction_id=prediction_id,
            incident_complexity=incident_complexity.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_complexity_distribution(self) -> dict[str, Any]:
        complexity_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.incident_complexity.value
            complexity_data.setdefault(key, []).append(r.prediction_score)
        result: dict[str, Any] = {}
        for complexity, scores in complexity_data.items():
            result[complexity] = {
                "count": len(scores),
                "avg_prediction_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_prediction_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.prediction_score < self._prediction_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "prediction_id": r.prediction_id,
                        "incident_complexity": r.incident_complexity.value,
                        "prediction_score": r.prediction_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["prediction_score"])

    def rank_by_prediction(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.prediction_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_prediction_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_prediction_score"])
        return results

    def detect_prediction_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> ResponseTimePredictionReport:
        by_complexity: dict[str, int] = {}
        by_model: dict[str, int] = {}
        by_accuracy: dict[str, int] = {}
        for r in self._records:
            by_complexity[r.incident_complexity.value] = (
                by_complexity.get(r.incident_complexity.value, 0) + 1
            )
            by_model[r.prediction_model.value] = by_model.get(r.prediction_model.value, 0) + 1
            by_accuracy[r.prediction_accuracy.value] = (
                by_accuracy.get(r.prediction_accuracy.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.prediction_score < self._prediction_threshold)
        scores = [r.prediction_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_prediction_gaps()
        top_gaps = [o["prediction_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} prediction(s) below threshold ({self._prediction_threshold})")
        if self._records and avg_score < self._prediction_threshold:
            recs.append(
                f"Avg prediction score {avg_score} below threshold ({self._prediction_threshold})"
            )
        if not recs:
            recs.append("Response time prediction is healthy")
        return ResponseTimePredictionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_prediction_score=avg_score,
            by_complexity=by_complexity,
            by_model=by_model,
            by_accuracy=by_accuracy,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("response_time_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        complexity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.incident_complexity.value
            complexity_dist[key] = complexity_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "prediction_threshold": self._prediction_threshold,
            "complexity_distribution": complexity_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
