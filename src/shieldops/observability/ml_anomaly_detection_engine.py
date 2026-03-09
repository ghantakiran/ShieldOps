"""ML Anomaly Detection Engine

Multi-variate anomaly detection, isolation forest scoring, seasonal
decomposition, and trend analysis for intelligent observability.
"""

from __future__ import annotations

import math
import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyType(StrEnum):
    POINT = "point"
    CONTEXTUAL = "contextual"
    COLLECTIVE = "collective"
    SEASONAL = "seasonal"
    TREND = "trend"


class DetectionMethod(StrEnum):
    ISOLATION_FOREST = "isolation_forest"
    Z_SCORE = "z_score"
    MAD = "mad"
    IQR = "iqr"
    DBSCAN = "dbscan"
    ENSEMBLE = "ensemble"


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrendDirection(StrEnum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    CYCLIC = "cyclic"
    UNKNOWN = "unknown"


# --- Models ---


class AnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    value: float = 0.0
    expected_value: float = 0.0
    anomaly_score: float = 0.0
    anomaly_type: AnomalyType = AnomalyType.POINT
    detection_method: DetectionMethod = DetectionMethod.Z_SCORE
    severity: AnomalySeverity = AnomalySeverity.LOW
    is_anomaly: bool = False
    dimension_values: dict[str, str] = Field(default_factory=dict)
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SeasonalDecomposition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    trend_direction: TrendDirection = TrendDirection.UNKNOWN
    seasonal_period: float = 0.0
    trend_slope: float = 0.0
    residual_std: float = 0.0
    seasonality_strength: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AnomalyDetectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_anomalies: int = 0
    anomaly_rate: float = 0.0
    avg_anomaly_score: float = 0.0
    by_anomaly_type: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_anomalous_metrics: list[str] = Field(default_factory=list)
    seasonal_insights: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MlAnomalyDetectionEngine:
    """ML Anomaly Detection Engine

    Multi-variate anomaly detection, isolation forest scoring, seasonal
    decomposition, and trend analysis.
    """

    def __init__(
        self,
        max_records: int = 200000,
        anomaly_score_threshold: float = 0.7,
        z_score_threshold: float = 3.0,
    ) -> None:
        self._max_records = max_records
        self._anomaly_score_threshold = anomaly_score_threshold
        self._z_score_threshold = z_score_threshold
        self._records: list[AnomalyRecord] = []
        self._decompositions: list[SeasonalDecomposition] = []
        logger.info(
            "ml_anomaly_detection_engine.initialized",
            max_records=max_records,
            anomaly_score_threshold=anomaly_score_threshold,
        )

    def add_record(
        self,
        metric_name: str,
        value: float,
        expected_value: float = 0.0,
        anomaly_type: AnomalyType = AnomalyType.POINT,
        detection_method: DetectionMethod = DetectionMethod.Z_SCORE,
        dimension_values: dict[str, str] | None = None,
        service: str = "",
        team: str = "",
    ) -> AnomalyRecord:
        deviation = abs(value - expected_value) if expected_value != 0 else 0.0
        anomaly_score = min(1.0, round(deviation / max(abs(expected_value), 1.0), 4))
        if detection_method == DetectionMethod.Z_SCORE:
            is_anomaly = anomaly_score >= (self._z_score_threshold / 10.0)
        else:
            is_anomaly = anomaly_score >= self._anomaly_score_threshold
        if anomaly_score >= 0.9:
            severity = AnomalySeverity.CRITICAL
        elif anomaly_score >= 0.7:
            severity = AnomalySeverity.HIGH
        elif anomaly_score >= 0.4:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW
        record = AnomalyRecord(
            metric_name=metric_name,
            value=value,
            expected_value=expected_value,
            anomaly_score=anomaly_score,
            anomaly_type=anomaly_type,
            detection_method=detection_method,
            severity=severity,
            is_anomaly=is_anomaly,
            dimension_values=dimension_values or {},
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ml_anomaly_detection_engine.record_added",
            record_id=record.id,
            metric_name=metric_name,
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
        )
        return record

    def get_record(self, record_id: str) -> AnomalyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        metric_name: str | None = None,
        severity: AnomalySeverity | None = None,
        anomalies_only: bool = False,
        limit: int = 50,
    ) -> list[AnomalyRecord]:
        results = list(self._records)
        if metric_name is not None:
            results = [r for r in results if r.metric_name == metric_name]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if anomalies_only:
            results = [r for r in results if r.is_anomaly]
        return results[-limit:]

    def compute_z_scores(self, metric_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if len(matching) < 3:
            return {"metric_name": metric_name, "status": "insufficient_data"}
        values = [r.value for r in matching]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 1.0
        z_scores = [round((v - mean) / std, 4) for v in values]
        outliers = sum(1 for z in z_scores if abs(z) > self._z_score_threshold)
        return {
            "metric_name": metric_name,
            "sample_count": len(values),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "outlier_count": outliers,
            "outlier_rate": round(outliers / len(values), 4),
            "max_z_score": round(max(abs(z) for z in z_scores), 4),
        }

    def compute_isolation_score(self, metric_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if len(matching) < 5:
            return {"metric_name": metric_name, "status": "insufficient_data"}
        values = sorted(r.value for r in matching)
        n = len(values)
        median = values[n // 2]
        mad = sorted(abs(v - median) for v in values)
        mad_val = mad[len(mad) // 2] if mad else 1.0
        isolation_scores: list[float] = []
        for v in values:
            score = min(1.0, abs(v - median) / (mad_val * 3)) if mad_val > 0 else 0.0
            isolation_scores.append(round(score, 4))
        anomaly_count = sum(1 for s in isolation_scores if s > self._anomaly_score_threshold)
        return {
            "metric_name": metric_name,
            "sample_count": n,
            "median": round(median, 4),
            "mad": round(mad_val, 4),
            "anomaly_count": anomaly_count,
            "avg_isolation_score": round(sum(isolation_scores) / n, 4),
            "max_isolation_score": max(isolation_scores),
        }

    def decompose_seasonal(self, metric_name: str) -> SeasonalDecomposition:
        matching = [r for r in self._records if r.metric_name == metric_name]
        values = [r.value for r in matching]
        n = len(values)
        if n < 4:
            decomp = SeasonalDecomposition(
                metric_name=metric_name,
                trend_direction=TrendDirection.UNKNOWN,
                description="Insufficient data for decomposition",
            )
            self._decompositions.append(decomp)
            return decomp
        mid = n // 2
        first_avg = sum(values[:mid]) / mid
        second_avg = sum(values[mid:]) / (n - mid)
        slope = round((second_avg - first_avg) / mid, 4)
        if abs(slope) < 0.01:
            direction = TrendDirection.STABLE
        elif slope > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING
        mean = sum(values) / n
        residuals = [v - mean for v in values]
        residual_std = round(math.sqrt(sum(r**2 for r in residuals) / n), 4)
        quarter = max(1, n // 4)
        q1_avg = sum(values[:quarter]) / quarter
        q3_avg = sum(values[2 * quarter : 3 * quarter]) / quarter if 3 * quarter <= n else q1_avg
        seasonality = round(abs(q1_avg - q3_avg) / max(abs(mean), 1.0), 4)
        decomp = SeasonalDecomposition(
            metric_name=metric_name,
            trend_direction=direction,
            trend_slope=slope,
            residual_std=residual_std,
            seasonality_strength=min(1.0, seasonality),
            description=f"Trend: {direction.value}, slope={slope}, seasonality={seasonality}",
        )
        self._decompositions.append(decomp)
        if len(self._decompositions) > self._max_records:
            self._decompositions = self._decompositions[-self._max_records :]
        return decomp

    def process(self, metric_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if not matching:
            return {"metric_name": metric_name, "status": "no_data"}
        anomalies = [r for r in matching if r.is_anomaly]
        scores = [r.anomaly_score for r in matching]
        return {
            "metric_name": metric_name,
            "total_points": len(matching),
            "anomaly_count": len(anomalies),
            "anomaly_rate": round(len(anomalies) / len(matching), 4),
            "avg_anomaly_score": round(sum(scores) / len(scores), 4),
            "max_anomaly_score": round(max(scores), 4),
            "critical_count": sum(1 for r in anomalies if r.severity == AnomalySeverity.CRITICAL),
        }

    def generate_report(self) -> AnomalyDetectionReport:
        by_type: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        for r in self._records:
            by_type[r.anomaly_type.value] = by_type.get(r.anomaly_type.value, 0) + 1
            by_method[r.detection_method.value] = by_method.get(r.detection_method.value, 0) + 1
            by_sev[r.severity.value] = by_sev.get(r.severity.value, 0) + 1
        anomalies = [r for r in self._records if r.is_anomaly]
        scores = [r.anomaly_score for r in anomalies]
        metric_anomaly_counts: dict[str, int] = {}
        for r in anomalies:
            metric_anomaly_counts[r.metric_name] = metric_anomaly_counts.get(r.metric_name, 0) + 1
        top_metrics = sorted(metric_anomaly_counts.items(), key=lambda x: x[1], reverse=True)
        seasonal_insights = [
            {
                "metric": d.metric_name,
                "trend": d.trend_direction.value,
                "slope": d.trend_slope,
                "seasonality": d.seasonality_strength,
            }
            for d in self._decompositions[-5:]
        ]
        recs: list[str] = []
        critical = by_sev.get("critical", 0)
        if critical > 0:
            recs.append(f"{critical} critical anomalies require immediate investigation")
        if anomalies:
            rate = len(anomalies) / len(self._records)
            if rate > 0.1:
                recs.append(f"Anomaly rate {rate:.1%} is elevated — review detection thresholds")
        if top_metrics:
            recs.append(
                f"Most anomalous metric: {top_metrics[0][0]} ({top_metrics[0][1]} anomalies)"
            )
        if not recs:
            recs.append("Anomaly detection is healthy — no significant anomalies")
        return AnomalyDetectionReport(
            total_records=len(self._records),
            total_anomalies=len(anomalies),
            anomaly_rate=round(len(anomalies) / max(1, len(self._records)), 4),
            avg_anomaly_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
            by_anomaly_type=by_type,
            by_detection_method=by_method,
            by_severity=by_sev,
            top_anomalous_metrics=[m[0] for m in top_metrics[:10]],
            seasonal_insights=seasonal_insights,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            type_dist[r.anomaly_type.value] = type_dist.get(r.anomaly_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_decompositions": len(self._decompositions),
            "anomaly_score_threshold": self._anomaly_score_threshold,
            "z_score_threshold": self._z_score_threshold,
            "anomaly_type_distribution": type_dist,
            "unique_metrics": len({r.metric_name for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._decompositions.clear()
        logger.info("ml_anomaly_detection_engine.cleared")
        return {"status": "cleared"}
