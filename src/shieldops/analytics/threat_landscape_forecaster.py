"""Threat Landscape Forecaster — forecast emerging threats and landscape evolution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastHorizon(StrEnum):
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    STRATEGIC = "strategic"
    TACTICAL = "tactical"


class ForecastConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"
    UNCERTAIN = "uncertain"


class ThreatTrend(StrEnum):
    ESCALATING = "escalating"
    STABLE = "stable"
    DECLINING = "declining"
    EMERGING = "emerging"
    CYCLICAL = "cyclical"


# --- Models ---


class ForecastRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_name: str = ""
    forecast_horizon: ForecastHorizon = ForecastHorizon.SHORT_TERM
    forecast_confidence: ForecastConfidence = ForecastConfidence.MEDIUM
    threat_trend: ThreatTrend = ThreatTrend.STABLE
    forecast_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_name: str = ""
    forecast_horizon: ForecastHorizon = ForecastHorizon.SHORT_TERM
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_forecast_score: float = 0.0
    by_horizon: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatLandscapeForecaster:
    """Forecast emerging threats and landscape evolution across horizons."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[ForecastRecord] = []
        self._analyses: list[ForecastAnalysis] = []
        logger.info(
            "threat_landscape_forecaster.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_forecast(
        self,
        forecast_name: str,
        forecast_horizon: ForecastHorizon = ForecastHorizon.SHORT_TERM,
        forecast_confidence: ForecastConfidence = ForecastConfidence.MEDIUM,
        threat_trend: ThreatTrend = ThreatTrend.STABLE,
        forecast_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ForecastRecord:
        record = ForecastRecord(
            forecast_name=forecast_name,
            forecast_horizon=forecast_horizon,
            forecast_confidence=forecast_confidence,
            threat_trend=threat_trend,
            forecast_score=forecast_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_landscape_forecaster.recorded",
            record_id=record.id,
            forecast_name=forecast_name,
            forecast_horizon=forecast_horizon.value,
        )
        return record

    def get_record(self, record_id: str) -> ForecastRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        forecast_horizon: ForecastHorizon | None = None,
        forecast_confidence: ForecastConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ForecastRecord]:
        results = list(self._records)
        if forecast_horizon is not None:
            results = [r for r in results if r.forecast_horizon == forecast_horizon]
        if forecast_confidence is not None:
            results = [r for r in results if r.forecast_confidence == forecast_confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        forecast_name: str,
        forecast_horizon: ForecastHorizon = ForecastHorizon.SHORT_TERM,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ForecastAnalysis:
        analysis = ForecastAnalysis(
            forecast_name=forecast_name,
            forecast_horizon=forecast_horizon,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "threat_landscape_forecaster.analysis_added",
            forecast_name=forecast_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_horizon_distribution(self) -> dict[str, Any]:
        horizon_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.forecast_horizon.value
            horizon_data.setdefault(key, []).append(r.forecast_score)
        result: dict[str, Any] = {}
        for horizon, scores in horizon_data.items():
            result[horizon] = {
                "count": len(scores),
                "avg_forecast_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.forecast_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "forecast_name": r.forecast_name,
                        "forecast_horizon": r.forecast_horizon.value,
                        "forecast_score": r.forecast_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["forecast_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.forecast_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_forecast_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_forecast_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ForecastReport:
        by_horizon: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_horizon[r.forecast_horizon.value] = by_horizon.get(r.forecast_horizon.value, 0) + 1
            by_confidence[r.forecast_confidence.value] = (
                by_confidence.get(r.forecast_confidence.value, 0) + 1
            )
            by_trend[r.threat_trend.value] = by_trend.get(r.threat_trend.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.forecast_score < self._quality_threshold)
        scores = [r.forecast_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["forecast_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} forecast(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg forecast score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Threat landscape forecasting is healthy")
        return ForecastReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_forecast_score=avg_score,
            by_horizon=by_horizon,
            by_confidence=by_confidence,
            by_trend=by_trend,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_landscape_forecaster.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        horizon_dist: dict[str, int] = {}
        for r in self._records:
            key = r.forecast_horizon.value
            horizon_dist[key] = horizon_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "horizon_distribution": horizon_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
