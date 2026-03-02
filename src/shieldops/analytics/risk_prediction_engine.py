"""Risk Prediction Engine — ML-based risk forecasting."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PredictionModel(StrEnum):
    REGRESSION = "regression"
    CLASSIFICATION = "classification"
    TIME_SERIES = "time_series"
    ENSEMBLE = "ensemble"
    BAYESIAN = "bayesian"


class RiskHorizon(StrEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    STRATEGIC = "strategic"


class PredictionConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


# --- Models ---


class PredictionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_name: str = ""
    prediction_model: PredictionModel = PredictionModel.REGRESSION
    risk_horizon: RiskHorizon = RiskHorizon.IMMEDIATE
    prediction_confidence: PredictionConfidence = PredictionConfidence.VERY_HIGH
    risk_forecast: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PredictionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_name: str = ""
    prediction_model: PredictionModel = PredictionModel.REGRESSION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PredictionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_confidence_count: int = 0
    avg_risk_forecast: float = 0.0
    by_model: dict[str, int] = Field(default_factory=dict)
    by_horizon: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskPredictionEngine:
    """ML-based risk forecasting across multiple prediction models."""

    def __init__(
        self,
        max_records: int = 200000,
        forecast_confidence_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._forecast_confidence_threshold = forecast_confidence_threshold
        self._records: list[PredictionRecord] = []
        self._analyses: list[PredictionAnalysis] = []
        logger.info(
            "risk_prediction_engine.initialized",
            max_records=max_records,
            forecast_confidence_threshold=forecast_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_prediction(
        self,
        prediction_name: str,
        prediction_model: PredictionModel = PredictionModel.REGRESSION,
        risk_horizon: RiskHorizon = RiskHorizon.IMMEDIATE,
        prediction_confidence: PredictionConfidence = PredictionConfidence.VERY_HIGH,
        risk_forecast: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PredictionRecord:
        record = PredictionRecord(
            prediction_name=prediction_name,
            prediction_model=prediction_model,
            risk_horizon=risk_horizon,
            prediction_confidence=prediction_confidence,
            risk_forecast=risk_forecast,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_prediction_engine.prediction_recorded",
            record_id=record.id,
            prediction_name=prediction_name,
            prediction_model=prediction_model.value,
            risk_horizon=risk_horizon.value,
        )
        return record

    def get_prediction(self, record_id: str) -> PredictionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        prediction_model: PredictionModel | None = None,
        risk_horizon: RiskHorizon | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PredictionRecord]:
        results = list(self._records)
        if prediction_model is not None:
            results = [r for r in results if r.prediction_model == prediction_model]
        if risk_horizon is not None:
            results = [r for r in results if r.risk_horizon == risk_horizon]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        prediction_name: str,
        prediction_model: PredictionModel = PredictionModel.REGRESSION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PredictionAnalysis:
        analysis = PredictionAnalysis(
            prediction_name=prediction_name,
            prediction_model=prediction_model,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "risk_prediction_engine.analysis_added",
            prediction_name=prediction_name,
            prediction_model=prediction_model.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_model_distribution(self) -> dict[str, Any]:
        """Group by prediction_model; return count and avg risk_forecast."""
        model_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.prediction_model.value
            model_data.setdefault(key, []).append(r.risk_forecast)
        result: dict[str, Any] = {}
        for model, scores in model_data.items():
            result[model] = {
                "count": len(scores),
                "avg_risk_forecast": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_predictions(self) -> list[dict[str, Any]]:
        """Return records where risk_forecast < forecast_confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_forecast < self._forecast_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "prediction_name": r.prediction_name,
                        "prediction_model": r.prediction_model.value,
                        "risk_forecast": r.risk_forecast,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_forecast"])

    def rank_by_risk_forecast(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_forecast, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_forecast)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_forecast": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_forecast"])
        return results

    def detect_forecast_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> PredictionReport:
        by_model: dict[str, int] = {}
        by_horizon: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_model[r.prediction_model.value] = by_model.get(r.prediction_model.value, 0) + 1
            by_horizon[r.risk_horizon.value] = by_horizon.get(r.risk_horizon.value, 0) + 1
            by_confidence[r.prediction_confidence.value] = (
                by_confidence.get(r.prediction_confidence.value, 0) + 1
            )
        low_confidence_count = sum(
            1 for r in self._records if r.risk_forecast < self._forecast_confidence_threshold
        )
        scores = [r.risk_forecast for r in self._records]
        avg_risk_forecast = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_predictions()
        top_low_confidence = [o["prediction_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} prediction(s) below forecast confidence threshold "
                f"({self._forecast_confidence_threshold})"
            )
        if self._records and avg_risk_forecast < self._forecast_confidence_threshold:
            recs.append(
                f"Avg risk forecast {avg_risk_forecast} below threshold "
                f"({self._forecast_confidence_threshold})"
            )
        if not recs:
            recs.append("Risk prediction confidence is healthy")
        return PredictionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_confidence_count=low_confidence_count,
            avg_risk_forecast=avg_risk_forecast,
            by_model=by_model,
            by_horizon=by_horizon,
            by_confidence=by_confidence,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("risk_prediction_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        model_dist: dict[str, int] = {}
        for r in self._records:
            key = r.prediction_model.value
            model_dist[key] = model_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "forecast_confidence_threshold": self._forecast_confidence_threshold,
            "model_distribution": model_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
