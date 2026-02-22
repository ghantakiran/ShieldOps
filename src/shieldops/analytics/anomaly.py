"""Anomaly Detection Engine for ShieldOps metrics.

Provides statistical anomaly detection using multiple algorithms:
- Z-score: detects values deviating significantly from the mean
- IQR (Interquartile Range): robust outlier detection
- EMA (Exponential Moving Average): trend-aware spike detection
- Seasonal decomposition: detects anomalies after removing periodic patterns

All algorithms are implemented in pure Python (no numpy/scipy dependency).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Pure-Python Math Helpers ─────────────────────────────────────────


def _mean(values: list[float]) -> float:
    """Compute the arithmetic mean of a list of floats."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std_dev(values: list[float]) -> float:
    """Compute the population standard deviation."""
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _median(values: list[float]) -> float:
    """Compute the median of a list of floats."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def _percentile(values: list[float], p: float) -> float:
    """Compute the p-th percentile (0-100) using linear interpolation."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    # Linear interpolation between closest ranks
    k = (p / 100) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


# ── Pydantic Models ──────────────────────────────────────────────────


class MetricPoint(BaseModel):
    """A single metric data point."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    value: float
    labels: dict[str, str] = Field(default_factory=dict)


class AnomalyResult(BaseModel):
    """Result of anomaly detection for a single data point."""

    metric_name: str
    point: MetricPoint
    score: float
    threshold: float
    is_anomaly: bool
    algorithm: str
    details: dict[str, Any] = Field(default_factory=dict)


class Baseline(BaseModel):
    """Statistical baseline for a metric."""

    metric_name: str
    mean: float
    std_dev: float
    min_val: float
    max_val: float
    count: int
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    percentiles: dict[str, float] = Field(default_factory=dict)


class DetectionRequest(BaseModel):
    """Request payload for anomaly detection."""

    metric_name: str
    values: list[float]
    timestamps: list[str] | None = None
    algorithm: str = "zscore"
    sensitivity: float = 2.0
    window_size: int = 30


class DetectionResponse(BaseModel):
    """Response payload for anomaly detection."""

    metric_name: str
    anomalies: list[AnomalyResult]
    total_points: int
    anomaly_count: int
    algorithm: str


# ── Anomaly Detector ─────────────────────────────────────────────────


class AnomalyDetector:
    """Statistical anomaly detection engine.

    Supports multiple algorithms and maintains per-metric baselines
    for auto-threshold calibration.
    """

    def __init__(self, default_sensitivity: float = 2.0) -> None:
        self.default_sensitivity = default_sensitivity
        self._baselines: dict[str, Baseline] = {}
        self._history: dict[str, list[float]] = {}

    # ── Z-Score Detection ────────────────────────────────────────

    def detect_zscore(
        self,
        values: list[float],
        sensitivity: float = 2.0,
    ) -> list[tuple[int, float, bool]]:
        """Detect anomalies using Z-score method.

        A point is anomalous when abs(z-score) > sensitivity threshold.

        Returns:
            List of (index, z_score, is_anomaly) tuples for each value.
        """
        if len(values) < 2:
            return [(i, 0.0, False) for i in range(len(values))]

        avg = _mean(values)
        sd = _std_dev(values)

        if sd == 0.0:
            return [(i, 0.0, False) for i in range(len(values))]

        results: list[tuple[int, float, bool]] = []
        for i, v in enumerate(values):
            z = (v - avg) / sd
            results.append((i, z, abs(z) > sensitivity))
        return results

    # ── IQR Detection ────────────────────────────────────────────

    def detect_iqr(
        self,
        values: list[float],
        multiplier: float = 1.5,
    ) -> list[tuple[int, float, bool]]:
        """Detect anomalies using the Interquartile Range method.

        A point is anomalous when it falls outside [Q1 - m*IQR, Q3 + m*IQR].

        Returns:
            List of (index, iqr_distance, is_anomaly) tuples for each value.
        """
        if len(values) < 4:
            return [(i, 0.0, False) for i in range(len(values))]

        q1 = _percentile(values, 25)
        q3 = _percentile(values, 75)
        iqr = q3 - q1

        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        results: list[tuple[int, float, bool]] = []
        for i, v in enumerate(values):
            if iqr == 0.0:
                results.append((i, 0.0, False))
            elif v < lower:
                distance = (lower - v) / iqr
                results.append((i, -distance, True))
            elif v > upper:
                distance = (v - upper) / iqr
                results.append((i, distance, True))
            else:
                # Normalized distance from median within IQR band
                mid = (q1 + q3) / 2
                distance = (v - mid) / iqr if iqr else 0.0
                results.append((i, distance, False))
        return results

    # ── Exponential Moving Average Detection ─────────────────────

    def detect_ema(
        self,
        values: list[float],
        span: int = 10,
        sensitivity: float = 2.0,
    ) -> list[tuple[int, float, bool]]:
        """Detect anomalies using Exponential Moving Average.

        A point is anomalous when its deviation from the EMA exceeds
        sensitivity * standard deviation of residuals.

        Returns:
            List of (index, deviation_score, is_anomaly) tuples.
        """
        if len(values) < 2:
            return [(i, 0.0, False) for i in range(len(values))]

        alpha = 2.0 / (span + 1)

        # Compute EMA
        ema: list[float] = [values[0]]
        for i in range(1, len(values)):
            ema.append(alpha * values[i] + (1 - alpha) * ema[-1])

        # Compute residuals
        residuals = [values[i] - ema[i] for i in range(len(values))]
        residual_std = _std_dev(residuals)

        if residual_std == 0.0:
            return [(i, 0.0, False) for i in range(len(values))]

        results: list[tuple[int, float, bool]] = []
        for i, r in enumerate(residuals):
            score = r / residual_std
            results.append((i, score, abs(score) > sensitivity))
        return results

    # ── Seasonal Decomposition Detection ─────────────────────────

    def detect_seasonal(
        self,
        values: list[float],
        period: int = 24,
        sensitivity: float = 2.0,
    ) -> list[tuple[int, float, bool]]:
        """Detect anomalies using seasonal decomposition.

        Removes the periodic component by averaging values at each
        position within the cycle, then detects anomalies in the residuals.

        Returns:
            List of (index, residual_score, is_anomaly) tuples.
        """
        n = len(values)
        if n < period:
            # Not enough data for a full cycle; fall back to z-score
            return self.detect_zscore(values, sensitivity)

        # Compute seasonal component: average value at each position in the cycle
        seasonal: list[float] = []
        for pos in range(period):
            cycle_values = [values[i] for i in range(pos, n, period)]
            seasonal.append(_mean(cycle_values))

        # Remove seasonal component to get residuals
        residuals: list[float] = []
        for i in range(n):
            residuals.append(values[i] - seasonal[i % period])

        residual_std = _std_dev(residuals)

        if residual_std == 0.0:
            return [(i, 0.0, False) for i in range(n)]

        residual_mean = _mean(residuals)
        results: list[tuple[int, float, bool]] = []
        for i, r in enumerate(residuals):
            score = (r - residual_mean) / residual_std
            results.append((i, score, abs(score) > sensitivity))
        return results

    # ── Baseline Management ──────────────────────────────────────

    def update_baseline(self, metric_name: str, values: list[float]) -> Baseline:
        """Calculate or update the baseline statistics for a metric.

        Merges new values into the history for the metric and
        recomputes all statistics including percentiles.

        Returns:
            The updated Baseline object.
        """
        if metric_name not in self._history:
            self._history[metric_name] = []
        self._history[metric_name].extend(values)

        all_values = self._history[metric_name]

        baseline = Baseline(
            metric_name=metric_name,
            mean=_mean(all_values),
            std_dev=_std_dev(all_values),
            min_val=min(all_values) if all_values else 0.0,
            max_val=max(all_values) if all_values else 0.0,
            count=len(all_values),
            updated_at=datetime.now(UTC),
            percentiles={
                "p50": _percentile(all_values, 50),
                "p95": _percentile(all_values, 95),
                "p99": _percentile(all_values, 99),
            },
        )
        self._baselines[metric_name] = baseline
        logger.info(
            "baseline_updated",
            metric=metric_name,
            count=baseline.count,
            mean=round(baseline.mean, 4),
        )
        return baseline

    def get_baseline(self, metric_name: str) -> Baseline | None:
        """Retrieve the current baseline for a metric, or None if absent."""
        return self._baselines.get(metric_name)

    def list_baselines(self) -> list[Baseline]:
        """Return all stored baselines."""
        return list(self._baselines.values())

    # ── Unified Detection Entry Point ────────────────────────────

    def detect(self, request: DetectionRequest) -> DetectionResponse:
        """Run anomaly detection using the algorithm specified in the request.

        Routes to the appropriate detection method and builds a full
        DetectionResponse with AnomalyResult objects for each anomalous point.

        Raises:
            ValueError: If the algorithm name is not recognized.
        """
        algorithm = request.algorithm.lower()
        sensitivity = request.sensitivity

        if algorithm == "zscore":
            raw = self.detect_zscore(request.values, sensitivity)
        elif algorithm == "iqr":
            raw = self.detect_iqr(request.values, multiplier=sensitivity)
        elif algorithm == "ema":
            raw = self.detect_ema(
                request.values,
                span=request.window_size,
                sensitivity=sensitivity,
            )
        elif algorithm == "seasonal":
            raw = self.detect_seasonal(
                request.values,
                period=request.window_size,
                sensitivity=sensitivity,
            )
        else:
            raise ValueError(
                f"Unknown algorithm '{algorithm}'. Supported: zscore, iqr, ema, seasonal"
            )

        # Build timestamps
        now = datetime.now(UTC)
        anomalies: list[AnomalyResult] = []
        for idx, score, is_anomaly in raw:
            if is_anomaly:
                ts = now  # default
                if request.timestamps and idx < len(request.timestamps):
                    try:
                        ts = datetime.fromisoformat(request.timestamps[idx])
                    except (ValueError, TypeError):
                        ts = now

                point = MetricPoint(timestamp=ts, value=request.values[idx])
                anomalies.append(
                    AnomalyResult(
                        metric_name=request.metric_name,
                        point=point,
                        score=round(score, 4),
                        threshold=sensitivity,
                        is_anomaly=True,
                        algorithm=algorithm,
                        details={
                            "index": idx,
                            "raw_value": request.values[idx],
                        },
                    )
                )

        # Auto-update baseline from the provided values
        self.update_baseline(request.metric_name, request.values)

        return DetectionResponse(
            metric_name=request.metric_name,
            anomalies=anomalies,
            total_points=len(request.values),
            anomaly_count=len(anomalies),
            algorithm=algorithm,
        )
