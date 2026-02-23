"""Agent performance benchmarker.

Benchmarks agent executions against historical baselines, detects performance
regressions in duration, success rate, confidence, and token usage.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class BenchmarkMetric(enum.StrEnum):
    DURATION = "duration"
    SUCCESS_RATE = "success_rate"
    CONFIDENCE = "confidence"
    TOKEN_USAGE = "token_usage"  # noqa: S105


class RegressionSeverity(enum.StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"


# ── Models ───────────────────────────────────────────────────────────


class BenchmarkResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_type: str
    duration_seconds: float = 0.0
    success: bool = True
    confidence: float = 0.0
    token_usage: int = 0
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkBaseline(BaseModel):
    agent_type: str
    avg_duration: float = 0.0
    avg_confidence: float = 0.0
    avg_token_usage: float = 0.0
    success_rate: float = 0.0
    sample_count: int = 0
    computed_at: float = Field(default_factory=time.time)


class PerformanceRegression(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_type: str
    metric: BenchmarkMetric
    baseline_value: float
    current_value: float
    deviation: float = 0.0
    severity: RegressionSeverity = RegressionSeverity.MINOR
    detected_at: float = Field(default_factory=time.time)
    description: str = ""


# ── Benchmarker ──────────────────────────────────────────────────────


class AgentPerformanceBenchmarker:
    """Benchmark agent performance and detect regressions.

    Parameters
    ----------
    baseline_days:
        Days of data to use for baseline computation.
    regression_threshold:
        Fractional deviation threshold for regression detection.
    """

    def __init__(
        self,
        baseline_days: int = 30,
        regression_threshold: float = 0.2,
    ) -> None:
        self._results: dict[str, list[BenchmarkResult]] = {}
        self._baselines: dict[str, BenchmarkBaseline] = {}
        self._baseline_seconds = baseline_days * 86400
        self._threshold = regression_threshold

    def record_execution(
        self,
        agent_type: str,
        duration_seconds: float = 0.0,
        success: bool = True,
        confidence: float = 0.0,
        token_usage: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        result = BenchmarkResult(
            agent_type=agent_type,
            duration_seconds=duration_seconds,
            success=success,
            confidence=confidence,
            token_usage=token_usage,
            metadata=metadata or {},
        )
        if agent_type not in self._results:
            self._results[agent_type] = []
        self._results[agent_type].append(result)
        return result

    def compute_baseline(self, agent_type: str) -> BenchmarkBaseline:
        cutoff = time.time() - self._baseline_seconds
        results = [r for r in self._results.get(agent_type, []) if r.timestamp >= cutoff]
        if not results:
            baseline = BenchmarkBaseline(agent_type=agent_type)
            self._baselines[agent_type] = baseline
            return baseline

        n = len(results)
        avg_dur = sum(r.duration_seconds for r in results) / n
        avg_conf = sum(r.confidence for r in results) / n
        avg_tokens = sum(r.token_usage for r in results) / n
        success_rate = sum(1 for r in results if r.success) / n

        baseline = BenchmarkBaseline(
            agent_type=agent_type,
            avg_duration=round(avg_dur, 4),
            avg_confidence=round(avg_conf, 4),
            avg_token_usage=round(avg_tokens, 2),
            success_rate=round(success_rate, 4),
            sample_count=n,
        )
        self._baselines[agent_type] = baseline
        logger.info("benchmark_baseline_computed", agent_type=agent_type, samples=n)
        return baseline

    def detect_regressions(
        self,
        agent_type: str,
        window_size: int = 10,
    ) -> list[PerformanceRegression]:
        baseline = self._baselines.get(agent_type)
        if baseline is None or baseline.sample_count == 0:
            return []

        recent = self._results.get(agent_type, [])[-window_size:]
        if not recent:
            return []

        n = len(recent)
        cur_duration = sum(r.duration_seconds for r in recent) / n
        cur_confidence = sum(r.confidence for r in recent) / n
        cur_tokens = sum(r.token_usage for r in recent) / n
        cur_success = sum(1 for r in recent if r.success) / n

        regressions: list[PerformanceRegression] = []

        # Duration regression (higher is worse)
        if baseline.avg_duration > 0:
            dev = (cur_duration - baseline.avg_duration) / baseline.avg_duration
            if dev > self._threshold:
                regressions.append(
                    PerformanceRegression(
                        agent_type=agent_type,
                        metric=BenchmarkMetric.DURATION,
                        baseline_value=baseline.avg_duration,
                        current_value=round(cur_duration, 4),
                        deviation=round(dev, 4),
                        severity=self._classify_regression(dev),
                        description=f"Duration increased by {dev:.0%}",
                    )
                )

        # Success rate regression (lower is worse)
        if baseline.success_rate > 0:
            dev = (baseline.success_rate - cur_success) / baseline.success_rate
            if dev > self._threshold:
                regressions.append(
                    PerformanceRegression(
                        agent_type=agent_type,
                        metric=BenchmarkMetric.SUCCESS_RATE,
                        baseline_value=baseline.success_rate,
                        current_value=round(cur_success, 4),
                        deviation=round(dev, 4),
                        severity=self._classify_regression(dev),
                        description=f"Success rate decreased by {dev:.0%}",
                    )
                )

        # Confidence regression (lower is worse)
        if baseline.avg_confidence > 0:
            dev = (baseline.avg_confidence - cur_confidence) / baseline.avg_confidence
            if dev > self._threshold:
                regressions.append(
                    PerformanceRegression(
                        agent_type=agent_type,
                        metric=BenchmarkMetric.CONFIDENCE,
                        baseline_value=baseline.avg_confidence,
                        current_value=round(cur_confidence, 4),
                        deviation=round(dev, 4),
                        severity=self._classify_regression(dev),
                        description=f"Confidence decreased by {dev:.0%}",
                    )
                )

        # Token usage regression (higher is worse)
        if baseline.avg_token_usage > 0:
            dev = (cur_tokens - baseline.avg_token_usage) / baseline.avg_token_usage
            if dev > self._threshold:
                regressions.append(
                    PerformanceRegression(
                        agent_type=agent_type,
                        metric=BenchmarkMetric.TOKEN_USAGE,
                        baseline_value=baseline.avg_token_usage,
                        current_value=round(cur_tokens, 2),
                        deviation=round(dev, 4),
                        severity=self._classify_regression(dev),
                        description=f"Token usage increased by {dev:.0%}",
                    )
                )

        return regressions

    def _classify_regression(self, deviation: float) -> RegressionSeverity:
        if deviation >= 0.5:
            return RegressionSeverity.MAJOR
        if deviation >= 0.3:
            return RegressionSeverity.MODERATE
        return RegressionSeverity.MINOR

    def get_benchmark(self, agent_type: str) -> dict[str, Any]:
        baseline = self._baselines.get(agent_type)
        results = self._results.get(agent_type, [])
        return {
            "agent_type": agent_type,
            "total_executions": len(results),
            "baseline": baseline.model_dump() if baseline else None,
        }

    def list_benchmarks(self) -> list[dict[str, Any]]:
        return [self.get_benchmark(at) for at in self._results]

    def get_stats(self) -> dict[str, Any]:
        total_executions = sum(len(v) for v in self._results.values())
        return {
            "tracked_agent_types": len(self._results),
            "total_executions": total_executions,
            "baselines_computed": len(self._baselines),
        }
