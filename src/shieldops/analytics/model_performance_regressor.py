"""Model Performance Regressor — track ML model performance regression over time."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PerformanceMetric(StrEnum):
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    AUC_ROC = "auc_roc"


class RegressionType(StrEnum):
    GRADUAL = "gradual"
    SUDDEN = "sudden"
    SEASONAL = "seasonal"
    PERIODIC = "periodic"
    UNKNOWN = "unknown"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT = "insufficient"


# --- Models ---


class PerformanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    performance_metric: PerformanceMetric = PerformanceMetric.ACCURACY
    regression_type: RegressionType = RegressionType.UNKNOWN
    trend_direction: TrendDirection = TrendDirection.STABLE
    metric_value: float = 0.0
    baseline_value: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PerformanceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    performance_metric: PerformanceMetric = PerformanceMetric.ACCURACY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerformanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    regressed_count: int = 0
    avg_metric_value: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_regression: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    top_regressed: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ModelPerformanceRegressor:
    """Track ML model performance regression over time."""

    def __init__(
        self,
        max_records: int = 200000,
        regression_threshold: float = 0.05,
    ) -> None:
        self._max_records = max_records
        self._regression_threshold = regression_threshold
        self._records: list[PerformanceRecord] = []
        self._analyses: list[PerformanceAnalysis] = []
        logger.info(
            "model_performance_regressor.initialized",
            max_records=max_records,
            regression_threshold=regression_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_performance(
        self,
        model_id: str,
        performance_metric: PerformanceMetric = PerformanceMetric.ACCURACY,
        regression_type: RegressionType = RegressionType.UNKNOWN,
        trend_direction: TrendDirection = TrendDirection.STABLE,
        metric_value: float = 0.0,
        baseline_value: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PerformanceRecord:
        record = PerformanceRecord(
            model_id=model_id,
            performance_metric=performance_metric,
            regression_type=regression_type,
            trend_direction=trend_direction,
            metric_value=metric_value,
            baseline_value=baseline_value,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "model_performance_regressor.performance_recorded",
            record_id=record.id,
            model_id=model_id,
            performance_metric=performance_metric.value,
        )
        return record

    def get_performance(self, record_id: str) -> PerformanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_performances(
        self,
        performance_metric: PerformanceMetric | None = None,
        trend_direction: TrendDirection | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PerformanceRecord]:
        results = list(self._records)
        if performance_metric is not None:
            results = [r for r in results if r.performance_metric == performance_metric]
        if trend_direction is not None:
            results = [r for r in results if r.trend_direction == trend_direction]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        performance_metric: PerformanceMetric = PerformanceMetric.ACCURACY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PerformanceAnalysis:
        analysis = PerformanceAnalysis(
            model_id=model_id,
            performance_metric=performance_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "model_performance_regressor.analysis_added",
            model_id=model_id,
            performance_metric=performance_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by performance_metric; return count and avg metric_value."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.performance_metric.value
            metric_data.setdefault(key, []).append(r.metric_value)
        result: dict[str, Any] = {}
        for metric, values in metric_data.items():
            result[metric] = {
                "count": len(values),
                "avg_metric_value": round(sum(values) / len(values), 4),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records with performance regression > regression_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            regression = r.baseline_value - r.metric_value
            if regression > self._regression_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "performance_metric": r.performance_metric.value,
                        "metric_value": r.metric_value,
                        "baseline_value": r.baseline_value,
                        "regression": round(regression, 4),
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["regression"], reverse=True)

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg metric_value, sort ascending (lowest first)."""
        model_values: dict[str, list[float]] = {}
        for r in self._records:
            model_values.setdefault(r.model_id, []).append(r.metric_value)
        results: list[dict[str, Any]] = []
        for model_id, values in model_values.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_metric_value": round(sum(values) / len(values), 4),
                }
            )
        results.sort(key=lambda x: x["avg_metric_value"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> PerformanceReport:
        by_metric: dict[str, int] = {}
        by_regression: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_metric[r.performance_metric.value] = by_metric.get(r.performance_metric.value, 0) + 1
            by_regression[r.regression_type.value] = (
                by_regression.get(r.regression_type.value, 0) + 1
            )
            by_trend[r.trend_direction.value] = by_trend.get(r.trend_direction.value, 0) + 1
        regressed_count = len(self.identify_severe_drifts())
        values = [r.metric_value for r in self._records]
        avg_metric_value = round(sum(values) / len(values), 4) if values else 0.0
        regressed_list = self.identify_severe_drifts()
        top_regressed = [o["model_id"] for o in regressed_list[:5]]
        recs: list[str] = []
        if self._records and regressed_count > 0:
            recs.append(
                f"{regressed_count} model(s) showing performance regression "
                f"(>{self._regression_threshold})"
            )
        if not recs:
            recs.append("Model performance is stable")
        return PerformanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            regressed_count=regressed_count,
            avg_metric_value=avg_metric_value,
            by_metric=by_metric,
            by_regression=by_regression,
            by_trend=by_trend,
            top_regressed=top_regressed,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("model_performance_regressor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.performance_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "regression_threshold": self._regression_threshold,
            "metric_distribution": metric_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
