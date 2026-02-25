"""Dependency Lag Monitor — monitor runtime latency lag between services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LagSeverity(StrEnum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    DEGRADED = "degraded"
    SEVERE = "severe"
    CRITICAL = "critical"


class PropagationDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    LATERAL = "lateral"
    BIDIRECTIONAL = "bidirectional"
    ISOLATED = "isolated"


class LagCause(StrEnum):
    NETWORK_CONGESTION = "network_congestion"
    SERVICE_OVERLOAD = "service_overload"
    DATABASE_CONTENTION = "database_contention"
    QUEUE_BACKLOG = "queue_backlog"
    EXTERNAL_API = "external_api"


# --- Models ---


class DependencyLagRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    target_service: str = ""
    latency_ms: float = 0.0
    baseline_ms: float = 0.0
    lag_pct: float = 0.0
    severity: LagSeverity = LagSeverity.NORMAL
    direction: PropagationDirection = PropagationDirection.DOWNSTREAM
    cause: LagCause = LagCause.NETWORK_CONGESTION
    created_at: float = Field(default_factory=time.time)


class LagBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    target_service: str = ""
    baseline_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class DependencyLagReport(BaseModel):
    total_records: int = 0
    total_baselines: int = 0
    degraded_count: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_cause: dict[str, int] = Field(default_factory=dict)
    top_bottlenecks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyLagMonitor:
    """Monitor runtime latency lag between services in the dependency graph."""

    def __init__(
        self,
        max_records: int = 200000,
        degradation_threshold_pct: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._degradation_threshold_pct = degradation_threshold_pct
        self._records: list[DependencyLagRecord] = []
        self._baselines: dict[str, LagBaseline] = {}
        logger.info(
            "dependency_lag.initialized",
            max_records=max_records,
            degradation_threshold_pct=degradation_threshold_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _lag_to_severity(self, lag_pct: float) -> LagSeverity:
        if lag_pct < 20:
            return LagSeverity.NORMAL
        if lag_pct < 50:
            return LagSeverity.ELEVATED
        if lag_pct < 100:
            return LagSeverity.DEGRADED
        if lag_pct < 200:
            return LagSeverity.SEVERE
        return LagSeverity.CRITICAL

    def _pair_key(self, source: str, target: str) -> str:
        return f"{source}->{target}"

    # -- record / get / list ---------------------------------------------

    def record_lag(
        self,
        source_service: str,
        target_service: str,
        latency_ms: float,
        baseline_ms: float = 0.0,
        direction: PropagationDirection = PropagationDirection.DOWNSTREAM,
        cause: LagCause = LagCause.NETWORK_CONGESTION,
    ) -> DependencyLagRecord:
        # Use stored baseline if available and none provided
        pair_key = self._pair_key(source_service, target_service)
        if baseline_ms <= 0 and pair_key in self._baselines:
            baseline_ms = self._baselines[pair_key].baseline_ms
        lag_pct = 0.0
        if baseline_ms > 0:
            lag_pct = round((latency_ms - baseline_ms) / baseline_ms * 100, 2)
        severity = self._lag_to_severity(max(0, lag_pct))
        record = DependencyLagRecord(
            source_service=source_service,
            target_service=target_service,
            latency_ms=latency_ms,
            baseline_ms=baseline_ms,
            lag_pct=lag_pct,
            severity=severity,
            direction=direction,
            cause=cause,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_lag.lag_recorded",
            record_id=record.id,
            source=source_service,
            target=target_service,
            lag_pct=lag_pct,
            severity=severity.value,
        )
        return record

    def get_lag_record(self, record_id: str) -> DependencyLagRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lag_records(
        self,
        source_service: str | None = None,
        target_service: str | None = None,
        limit: int = 50,
    ) -> list[DependencyLagRecord]:
        results = list(self._records)
        if source_service is not None:
            results = [r for r in results if r.source_service == source_service]
        if target_service is not None:
            results = [r for r in results if r.target_service == target_service]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def set_baseline(
        self,
        source_service: str,
        target_service: str,
        baseline_ms: float,
        p50_ms: float = 0.0,
        p95_ms: float = 0.0,
        p99_ms: float = 0.0,
    ) -> LagBaseline:
        pair_key = self._pair_key(source_service, target_service)
        baseline = LagBaseline(
            source_service=source_service,
            target_service=target_service,
            baseline_ms=baseline_ms,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
        )
        self._baselines[pair_key] = baseline
        logger.info(
            "dependency_lag.baseline_set",
            source=source_service,
            target=target_service,
            baseline_ms=baseline_ms,
        )
        return baseline

    def detect_degradation(
        self,
        source_service: str,
        target_service: str,
    ) -> dict[str, Any]:
        """Detect if a service pair has degraded latency."""
        pair_key = self._pair_key(source_service, target_service)
        pair_records = [
            r
            for r in self._records
            if r.source_service == source_service and r.target_service == target_service
        ]
        if not pair_records:
            return {
                "source_service": source_service,
                "target_service": target_service,
                "degraded": False,
                "reason": "no records",
            }
        latest = pair_records[-1]
        degraded = latest.lag_pct >= self._degradation_threshold_pct
        return {
            "source_service": source_service,
            "target_service": target_service,
            "degraded": degraded,
            "lag_pct": latest.lag_pct,
            "latency_ms": latest.latency_ms,
            "baseline_ms": latest.baseline_ms,
            "severity": latest.severity.value,
            "has_baseline": pair_key in self._baselines,
        }

    def trace_propagation_chain(self, service: str) -> list[dict[str, Any]]:
        """Trace lag propagation from a service to its dependents."""
        chain: list[dict[str, Any]] = []
        visited: set[str] = set()
        queue = [service]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            downstream = [r for r in self._records if r.source_service == current and r.lag_pct > 0]
            for r in downstream:
                chain.append(
                    {
                        "source": r.source_service,
                        "target": r.target_service,
                        "lag_pct": r.lag_pct,
                        "severity": r.severity.value,
                    }
                )
                if r.target_service not in visited:
                    queue.append(r.target_service)
        return chain

    def identify_bottleneck_services(self) -> list[dict[str, Any]]:
        """Find services that are bottlenecks (frequently appearing as targets with high lag)."""
        target_lags: dict[str, list[float]] = {}
        for r in self._records:
            if r.lag_pct > 0:
                target_lags.setdefault(r.target_service, []).append(r.lag_pct)
        results: list[dict[str, Any]] = []
        for svc, lags in target_lags.items():
            avg_lag = round(sum(lags) / len(lags), 2)
            if avg_lag >= self._degradation_threshold_pct:
                results.append(
                    {
                        "service": svc,
                        "avg_lag_pct": avg_lag,
                        "max_lag_pct": round(max(lags), 2),
                        "occurrence_count": len(lags),
                    }
                )
        results.sort(key=lambda x: x["avg_lag_pct"], reverse=True)
        return results

    def compare_to_baseline(
        self,
        source_service: str,
        target_service: str,
    ) -> dict[str, Any]:
        """Compare current latency to baseline for a pair."""
        pair_key = self._pair_key(source_service, target_service)
        baseline = self._baselines.get(pair_key)
        if baseline is None:
            return {
                "source_service": source_service,
                "target_service": target_service,
                "has_baseline": False,
            }
        pair_records = [
            r
            for r in self._records
            if r.source_service == source_service and r.target_service == target_service
        ]
        if not pair_records:
            return {
                "source_service": source_service,
                "target_service": target_service,
                "has_baseline": True,
                "baseline_ms": baseline.baseline_ms,
                "current_ms": 0.0,
                "deviation_pct": 0.0,
            }
        latest = pair_records[-1]
        deviation = 0.0
        if baseline.baseline_ms > 0:
            deviation = round(
                (latest.latency_ms - baseline.baseline_ms) / baseline.baseline_ms * 100, 2
            )
        return {
            "source_service": source_service,
            "target_service": target_service,
            "has_baseline": True,
            "baseline_ms": baseline.baseline_ms,
            "current_ms": latest.latency_ms,
            "deviation_pct": deviation,
            "severity": latest.severity.value,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DependencyLagReport:
        by_severity: dict[str, int] = {}
        by_cause: dict[str, int] = {}
        for r in self._records:
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_cause[r.cause.value] = by_cause.get(r.cause.value, 0) + 1
        degraded_count = sum(
            1
            for r in self._records
            if r.severity in (LagSeverity.DEGRADED, LagSeverity.SEVERE, LagSeverity.CRITICAL)
        )
        bottlenecks = self.identify_bottleneck_services()
        top_bn = [b["service"] for b in bottlenecks[:5]]
        recs: list[str] = []
        if degraded_count > 0:
            recs.append(f"{degraded_count} dependency link(s) degraded")
        if bottlenecks:
            recs.append(f"{len(bottlenecks)} bottleneck service(s) identified")
        critical = by_severity.get(LagSeverity.CRITICAL.value, 0)
        if critical > 0:
            recs.append(f"{critical} critical lag event(s) detected")
        if not recs:
            recs.append("All dependency latencies within normal range")
        return DependencyLagReport(
            total_records=len(self._records),
            total_baselines=len(self._baselines),
            degraded_count=degraded_count,
            by_severity=by_severity,
            by_cause=by_cause,
            top_bottlenecks=top_bn,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._baselines.clear()
        logger.info("dependency_lag.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_baselines": len(self._baselines),
            "degradation_threshold_pct": self._degradation_threshold_pct,
            "severity_distribution": severity_dist,
            "unique_pairs": len({(r.source_service, r.target_service) for r in self._records}),
        }
