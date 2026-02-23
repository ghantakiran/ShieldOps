"""Workload Fingerprinting Engine — behavioral fingerprints for anomaly detection."""

from __future__ import annotations

import math
import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkloadType(StrEnum):
    WEB_SERVER = "web_server"
    BATCH_JOB = "batch_job"
    STREAM_PROCESSOR = "stream_processor"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE_WORKER = "queue_worker"


class FingerprintStatus(StrEnum):
    LEARNING = "learning"
    STABLE = "stable"
    DRIFTED = "drifted"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class WorkloadSample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    cpu_pct: float = Field(default=0.0)
    memory_pct: float = Field(default=0.0)
    request_rate: float = Field(default=0.0)
    error_rate: float = Field(default=0.0)
    latency_p99_ms: float = Field(default=0.0)
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkloadFingerprint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    workload_type: WorkloadType = Field(default=WorkloadType.WEB_SERVER)
    status: FingerprintStatus = Field(default=FingerprintStatus.LEARNING)
    sample_count: int = Field(default=0)
    cpu_mean: float = Field(default=0.0)
    cpu_stddev: float = Field(default=0.0)
    memory_mean: float = Field(default=0.0)
    memory_stddev: float = Field(default=0.0)
    request_rate_mean: float = Field(default=0.0)
    request_rate_stddev: float = Field(default=0.0)
    error_rate_mean: float = Field(default=0.0)
    latency_mean: float = Field(default=0.0)
    last_updated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class DriftAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    metric: str
    expected_value: float
    observed_value: float
    deviation_pct: float
    message: str = Field(default="")
    detected_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Internal accumulators for running mean/variance (Welford's algorithm)
# ---------------------------------------------------------------------------


class _RunningStats:
    """Welford's online algorithm for mean and std-dev."""

    __slots__ = ("n", "mean", "m2")

    def __init__(self) -> None:
        self.n: int = 0
        self.mean: float = 0.0
        self.m2: float = 0.0

    def update(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def stddev(self) -> float:
        if self.n < 2:
            return 0.0
        return math.sqrt(self.m2 / self.n)

    def reset(self) -> None:
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class WorkloadFingerprintEngine:
    """Creates behavioral fingerprints of workloads for anomaly detection."""

    def __init__(
        self,
        max_samples: int = 100000,
        min_samples_for_stable: int = 20,
        drift_threshold_pct: float = 50.0,
    ) -> None:
        self.max_samples = max_samples
        self.min_samples_for_stable = min_samples_for_stable
        self.drift_threshold_pct = drift_threshold_pct

        self._samples: list[WorkloadSample] = []
        self._fingerprints: dict[str, WorkloadFingerprint] = {}
        # per-service running stats keyed by metric name
        self._stats: dict[str, dict[str, _RunningStats]] = {}
        self._drift_alerts: list[DriftAlert] = []

        logger.info(
            "workload_fingerprint_engine.initialized",
            max_samples=max_samples,
            min_samples_for_stable=min_samples_for_stable,
            drift_threshold_pct=drift_threshold_pct,
        )

    # -- helpers -------------------------------------------------------------

    _METRICS = ("cpu_pct", "memory_pct", "request_rate", "error_rate", "latency_p99_ms")

    def _ensure_stats(self, service: str) -> dict[str, _RunningStats]:
        if service not in self._stats:
            self._stats[service] = {m: _RunningStats() for m in self._METRICS}
        return self._stats[service]

    def _sync_fingerprint(self, service: str) -> WorkloadFingerprint:
        stats = self._ensure_stats(service)
        now = time.time()

        if service not in self._fingerprints:
            self._fingerprints[service] = WorkloadFingerprint(
                service=service,
                created_at=now,
                last_updated_at=now,
            )

        fp = self._fingerprints[service]
        fp.sample_count = stats["cpu_pct"].n
        fp.cpu_mean = round(stats["cpu_pct"].mean, 4)
        fp.cpu_stddev = round(stats["cpu_pct"].stddev, 4)
        fp.memory_mean = round(stats["memory_pct"].mean, 4)
        fp.memory_stddev = round(stats["memory_pct"].stddev, 4)
        fp.request_rate_mean = round(stats["request_rate"].mean, 4)
        fp.request_rate_stddev = round(stats["request_rate"].stddev, 4)
        fp.error_rate_mean = round(stats["error_rate"].mean, 4)
        fp.latency_mean = round(stats["latency_p99_ms"].mean, 4)
        fp.last_updated_at = now

        is_learning = fp.status == FingerprintStatus.LEARNING
        if fp.sample_count >= self.min_samples_for_stable and is_learning:
            fp.status = FingerprintStatus.STABLE

        return fp

    # -- public API ----------------------------------------------------------

    def record_sample(self, service: str, **kw: Any) -> WorkloadSample:
        """Record a workload sample and update fingerprint statistics."""
        sample = WorkloadSample(service=service, **kw)
        self._samples.append(sample)
        if len(self._samples) > self.max_samples:
            self._samples = self._samples[-self.max_samples :]

        stats = self._ensure_stats(service)
        stats["cpu_pct"].update(sample.cpu_pct)
        stats["memory_pct"].update(sample.memory_pct)
        stats["request_rate"].update(sample.request_rate)
        stats["error_rate"].update(sample.error_rate)
        stats["latency_p99_ms"].update(sample.latency_p99_ms)

        self._sync_fingerprint(service)

        logger.info(
            "workload_fingerprint.sample_recorded",
            sample_id=sample.id,
            service=service,
        )
        return sample

    def get_fingerprint(self, service: str) -> WorkloadFingerprint | None:
        """Return the current fingerprint for a service."""
        return self._fingerprints.get(service)

    def list_fingerprints(
        self,
        status: FingerprintStatus | None = None,
        workload_type: WorkloadType | None = None,
    ) -> list[WorkloadFingerprint]:
        """List fingerprints, optionally filtered."""
        result = list(self._fingerprints.values())
        if status is not None:
            result = [f for f in result if f.status == status]
        if workload_type is not None:
            result = [f for f in result if f.workload_type == workload_type]
        return result

    def check_drift(self, service: str) -> list[DriftAlert]:
        """Compare latest sample against fingerprint and generate drift alerts."""
        fp = self._fingerprints.get(service)
        if fp is None or fp.sample_count < 2:
            return []

        # Find latest sample for this service
        latest: WorkloadSample | None = None
        for s in reversed(self._samples):
            if s.service == service:
                latest = s
                break
        if latest is None:
            return []

        alerts: list[DriftAlert] = []
        metric_map = {
            "cpu_pct": (fp.cpu_mean, latest.cpu_pct),
            "memory_pct": (fp.memory_mean, latest.memory_pct),
            "request_rate": (fp.request_rate_mean, latest.request_rate),
            "error_rate": (fp.error_rate_mean, latest.error_rate),
            "latency_p99_ms": (fp.latency_mean, latest.latency_p99_ms),
        }

        for metric_name, (expected, observed) in metric_map.items():
            if expected == 0:
                if observed == 0:
                    continue
                deviation_pct = 100.0
            else:
                deviation_pct = abs(observed - expected) / abs(expected) * 100

            if deviation_pct > self.drift_threshold_pct:
                alert = DriftAlert(
                    service=service,
                    metric=metric_name,
                    expected_value=round(expected, 4),
                    observed_value=round(observed, 4),
                    deviation_pct=round(deviation_pct, 2),
                    message=(
                        f"{metric_name} drifted {deviation_pct:.1f}% from mean "
                        f"(expected={expected:.4f}, observed={observed:.4f})"
                    ),
                )
                alerts.append(alert)
                self._drift_alerts.append(alert)

        if alerts:
            fp.status = FingerprintStatus.DRIFTED
            logger.warning(
                "workload_fingerprint.drift_detected",
                service=service,
                alert_count=len(alerts),
            )

        return alerts

    def set_workload_type(
        self, service: str, workload_type: WorkloadType
    ) -> WorkloadFingerprint | None:
        """Update the workload type for a service fingerprint."""
        fp = self._fingerprints.get(service)
        if fp is None:
            return None
        fp.workload_type = workload_type
        logger.info(
            "workload_fingerprint.type_set",
            service=service,
            workload_type=workload_type,
        )
        return fp

    def get_samples(self, service: str, limit: int = 100) -> list[WorkloadSample]:
        """Return samples for a service, newest first."""
        result = [s for s in self._samples if s.service == service]
        result.reverse()
        return result[:limit]

    def clear_samples(self, service: str | None = None) -> int:
        """Clear samples (all or per-service). Reset fingerprint if clearing."""
        if service is None:
            count = len(self._samples)
            self._samples.clear()
            self._fingerprints.clear()
            self._stats.clear()
            logger.info("workload_fingerprint.all_samples_cleared", count=count)
            return count

        before = len(self._samples)
        self._samples = [s for s in self._samples if s.service != service]
        cleared = before - len(self._samples)

        if service in self._fingerprints:
            del self._fingerprints[service]
        if service in self._stats:
            del self._stats[service]

        logger.info(
            "workload_fingerprint.samples_cleared",
            service=service,
            count=cleared,
        )
        return cleared

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        fps = list(self._fingerprints.values())
        stable = sum(1 for f in fps if f.status == FingerprintStatus.STABLE)
        drifted = sum(1 for f in fps if f.status == FingerprintStatus.DRIFTED)
        learning = sum(1 for f in fps if f.status == FingerprintStatus.LEARNING)

        avg_cpu = 0.0
        avg_memory = 0.0
        if fps:
            avg_cpu = round(sum(f.cpu_mean for f in fps) / len(fps), 4)
            avg_memory = round(sum(f.memory_mean for f in fps) / len(fps), 4)

        return {
            "total_samples": len(self._samples),
            "total_fingerprints": len(fps),
            "stable_count": stable,
            "drifted_count": drifted,
            "learning_count": learning,
            "avg_cpu": avg_cpu,
            "avg_memory": avg_memory,
        }
