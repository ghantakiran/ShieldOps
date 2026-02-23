"""Service Latency Profiler — per-endpoint percentile tracking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PercentileBucket(StrEnum):
    P50 = "p50"
    P75 = "p75"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"


class RegressionSeverity(StrEnum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ProfileWindow(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# --- Models ---


class LatencySample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    endpoint: str
    latency_ms: float
    timestamp: float = Field(default_factory=time.time)


class LatencyProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    endpoint: str
    window: ProfileWindow = ProfileWindow.DAILY
    p50: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    sample_count: int = 0
    computed_at: float = Field(default_factory=time.time)


class RegressionAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    endpoint: str
    percentile: PercentileBucket
    baseline_ms: float
    current_ms: float
    severity: RegressionSeverity = RegressionSeverity.NONE
    regression_pct: float = 0.0
    detected_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceLatencyProfiler:
    """Per-endpoint p50/p75/p90/p95/p99 tracking, baseline comparison, regression detection."""

    def __init__(
        self,
        max_samples: int = 500000,
        regression_threshold: float = 0.1,
    ) -> None:
        self._max_samples = max_samples
        self._regression_threshold = regression_threshold
        self._samples: list[LatencySample] = []
        self._profiles: dict[str, LatencyProfile] = {}
        self._baselines: dict[str, LatencyProfile] = {}
        logger.info(
            "latency_profiler.initialized",
            max_samples=max_samples,
            regression_threshold=regression_threshold,
        )

    def record_sample(
        self,
        service: str,
        endpoint: str,
        latency_ms: float,
    ) -> LatencySample:
        sample = LatencySample(service=service, endpoint=endpoint, latency_ms=latency_ms)
        self._samples.append(sample)
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples :]
        logger.debug(
            "latency_profiler.sample_recorded",
            service=service,
            endpoint=endpoint,
            latency_ms=latency_ms,
        )
        return sample

    def compute_profile(
        self,
        service: str,
        endpoint: str,
        window: ProfileWindow = ProfileWindow.DAILY,
    ) -> LatencyProfile:
        matching = [s for s in self._samples if s.service == service and s.endpoint == endpoint]
        latencies = sorted(s.latency_ms for s in matching)
        n = len(latencies)
        if n == 0:
            profile = LatencyProfile(service=service, endpoint=endpoint, window=window)
        else:
            profile = LatencyProfile(
                service=service,
                endpoint=endpoint,
                window=window,
                p50=latencies[int(n * 0.5)] if n > 0 else 0.0,
                p75=latencies[int(n * 0.75)] if n > 0 else 0.0,
                p90=latencies[min(int(n * 0.9), n - 1)] if n > 0 else 0.0,
                p95=latencies[min(int(n * 0.95), n - 1)] if n > 0 else 0.0,
                p99=latencies[min(int(n * 0.99), n - 1)] if n > 0 else 0.0,
                sample_count=n,
            )
        key = f"{service}:{endpoint}"
        self._profiles[key] = profile
        logger.info(
            "latency_profiler.profile_computed",
            service=service,
            endpoint=endpoint,
            sample_count=n,
        )
        return profile

    def set_baseline(self, service: str, endpoint: str) -> LatencyProfile | None:
        key = f"{service}:{endpoint}"
        profile = self._profiles.get(key)
        if profile is None:
            return None
        self._baselines[key] = profile
        logger.info("latency_profiler.baseline_set", service=service, endpoint=endpoint)
        return profile

    def get_baseline(self, service: str, endpoint: str) -> LatencyProfile | None:
        return self._baselines.get(f"{service}:{endpoint}")

    def detect_regressions(
        self,
        service: str,
        endpoint: str,
    ) -> list[RegressionAlert]:
        key = f"{service}:{endpoint}"
        baseline = self._baselines.get(key)
        current = self._profiles.get(key)
        if baseline is None or current is None:
            return []
        alerts: list[RegressionAlert] = []
        for bucket in PercentileBucket:
            baseline_val = getattr(baseline, bucket.value, 0.0)
            current_val = getattr(current, bucket.value, 0.0)
            if baseline_val <= 0:
                continue
            pct_change = (current_val - baseline_val) / baseline_val
            if pct_change <= self._regression_threshold:
                continue
            if pct_change > 1.0:
                severity = RegressionSeverity.CRITICAL
            elif pct_change > 0.5:
                severity = RegressionSeverity.MAJOR
            elif pct_change > 0.25:
                severity = RegressionSeverity.MODERATE
            else:
                severity = RegressionSeverity.MINOR
            alerts.append(
                RegressionAlert(
                    service=service,
                    endpoint=endpoint,
                    percentile=bucket,
                    baseline_ms=baseline_val,
                    current_ms=current_val,
                    severity=severity,
                    regression_pct=round(pct_change * 100, 1),
                )
            )
        return alerts

    def list_profiles(
        self,
        service: str | None = None,
    ) -> list[LatencyProfile]:
        profiles = list(self._profiles.values())
        if service is not None:
            profiles = [p for p in profiles if p.service == service]
        return profiles

    def get_endpoint_ranking(self, service: str) -> list[dict[str, Any]]:
        profiles = [p for p in self._profiles.values() if p.service == service]
        ranked = sorted(profiles, key=lambda p: p.p99, reverse=True)
        return [
            {
                "endpoint": p.endpoint,
                "p50": p.p50,
                "p75": p.p75,
                "p90": p.p90,
                "p95": p.p95,
                "p99": p.p99,
                "sample_count": p.sample_count,
            }
            for p in ranked
        ]

    def list_samples(
        self,
        service: str | None = None,
        endpoint: str | None = None,
        limit: int = 100,
    ) -> list[LatencySample]:
        results = list(self._samples)
        if service is not None:
            results = [s for s in results if s.service == service]
        if endpoint is not None:
            results = [s for s in results if s.endpoint == endpoint]
        return results[-limit:]

    def clear_samples(self) -> int:
        count = len(self._samples)
        self._samples.clear()
        logger.info("latency_profiler.samples_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_samples": len(self._samples),
            "total_profiles": len(self._profiles),
            "total_baselines": len(self._baselines),
            "unique_services": len({s.service for s in self._samples}),
            "unique_endpoints": len({f"{s.service}:{s.endpoint}" for s in self._samples}),
        }
