"""Service Health Predictor — predict service health degradation and failures."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    AT_RISK = "at_risk"
    FAILING = "failing"
    UNKNOWN = "unknown"


class PredictionBasis(StrEnum):
    LATENCY_TREND = "latency_trend"
    ERROR_TRAJECTORY = "error_trajectory"
    DEPENDENCY_SIGNAL = "dependency_signal"
    CAPACITY_PRESSURE = "capacity_pressure"
    ANOMALY_DETECTION = "anomaly_detection"


class PredictionHorizon(StrEnum):
    MINUTES_15 = "minutes_15"
    HOUR_1 = "hour_1"
    HOURS_4 = "hours_4"
    HOURS_24 = "hours_24"
    DAYS_7 = "days_7"


# --- Models ---


class PredictionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    health_state: HealthState = HealthState.HEALTHY
    prediction_basis: PredictionBasis = PredictionBasis.LATENCY_TREND
    prediction_horizon: PredictionHorizon = PredictionHorizon.MINUTES_15
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PredictionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    health_state: HealthState = HealthState.HEALTHY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_confidence_count: int = 0
    avg_confidence_score: float = 0.0
    by_state: dict[str, int] = Field(default_factory=dict)
    by_basis: dict[str, int] = Field(default_factory=dict)
    by_horizon: dict[str, int] = Field(default_factory=dict)
    top_at_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceHealthPredictor:
    """Predict service health, identify low-confidence predictions, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        prediction_confidence_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._prediction_confidence_threshold = prediction_confidence_threshold
        self._records: list[PredictionRecord] = []
        self._analyses: list[PredictionAnalysis] = []
        logger.info(
            "service_health_predictor.initialized",
            max_records=max_records,
            prediction_confidence_threshold=prediction_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_prediction(
        self,
        service_name: str,
        health_state: HealthState = HealthState.HEALTHY,
        prediction_basis: PredictionBasis = PredictionBasis.LATENCY_TREND,
        prediction_horizon: PredictionHorizon = PredictionHorizon.MINUTES_15,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PredictionRecord:
        record = PredictionRecord(
            service_name=service_name,
            health_state=health_state,
            prediction_basis=prediction_basis,
            prediction_horizon=prediction_horizon,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_health_predictor.prediction_recorded",
            record_id=record.id,
            service_name=service_name,
            health_state=health_state.value,
            prediction_basis=prediction_basis.value,
        )
        return record

    def get_prediction(self, record_id: str) -> PredictionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        health_state: HealthState | None = None,
        prediction_basis: PredictionBasis | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PredictionRecord]:
        results = list(self._records)
        if health_state is not None:
            results = [r for r in results if r.health_state == health_state]
        if prediction_basis is not None:
            results = [r for r in results if r.prediction_basis == prediction_basis]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        service_name: str,
        health_state: HealthState = HealthState.HEALTHY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PredictionAnalysis:
        analysis = PredictionAnalysis(
            service_name=service_name,
            health_state=health_state,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "service_health_predictor.analysis_added",
            service_name=service_name,
            health_state=health_state.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_prediction_distribution(self) -> dict[str, Any]:
        """Group by health_state; return count and avg score."""
        state_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.health_state.value
            state_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for state, scores in state_data.items():
            result[state] = {
                "count": len(scores),
                "avg_confidence_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_predictions(self) -> list[dict[str, Any]]:
        """Return predictions where confidence_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._prediction_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "health_state": r.health_state.value,
                        "prediction_basis": r.prediction_basis.value,
                        "confidence_score": r.confidence_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["confidence_score"], reverse=False)
        return results

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by service, avg confidence_score, sort asc (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_confidence_score": round(sum(scores) / len(scores), 2),
                    "prediction_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_confidence_score"], reverse=False)
        return results

    def detect_prediction_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.analysis_score for a in self._analyses]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> ServiceHealthReport:
        by_state: dict[str, int] = {}
        by_basis: dict[str, int] = {}
        by_horizon: dict[str, int] = {}
        for r in self._records:
            by_state[r.health_state.value] = by_state.get(r.health_state.value, 0) + 1
            by_basis[r.prediction_basis.value] = by_basis.get(r.prediction_basis.value, 0) + 1
            by_horizon[r.prediction_horizon.value] = (
                by_horizon.get(r.prediction_horizon.value, 0) + 1
            )
        low_confidence_count = sum(
            1 for r in self._records if r.confidence_score < self._prediction_confidence_threshold
        )
        avg_confidence = (
            round(
                sum(r.confidence_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low = self.identify_low_confidence_predictions()
        top_at_risk = [item["service_name"] for item in low]
        recs: list[str] = []
        if low:
            recs.append(
                f"{len(low)} low-confidence prediction(s) detected — review prediction models"
            )
        high_c = sum(
            1 for r in self._records if r.confidence_score >= self._prediction_confidence_threshold
        )
        if high_c > 0:
            recs.append(
                f"{high_c} prediction(s) above confidence threshold"
                f" ({self._prediction_confidence_threshold}%)"
            )
        if not recs:
            recs.append("Service health prediction levels are acceptable")
        return ServiceHealthReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_confidence_count=low_confidence_count,
            avg_confidence_score=avg_confidence,
            by_state=by_state,
            by_basis=by_basis,
            by_horizon=by_horizon,
            top_at_risk=top_at_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("service_health_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        state_dist: dict[str, int] = {}
        for r in self._records:
            key = r.health_state.value
            state_dist[key] = state_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "prediction_confidence_threshold": self._prediction_confidence_threshold,
            "state_distribution": state_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
