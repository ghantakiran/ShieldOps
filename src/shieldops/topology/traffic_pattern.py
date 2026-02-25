"""Traffic Pattern Analyzer — track service traffic patterns, anomalies, hotspots."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrafficDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"
    EXTERNAL = "external"
    CROSS_REGION = "cross_region"


class TrafficAnomaly(StrEnum):
    SPIKE = "spike"
    DROP = "drop"
    LATENCY_INCREASE = "latency_increase"
    ERROR_BURST = "error_burst"
    PATTERN_SHIFT = "pattern_shift"


class TrafficHealth(StrEnum):
    HEALTHY = "healthy"
    ELEVATED = "elevated"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# --- Models ---


class TrafficRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    dest_service: str = ""
    direction: TrafficDirection = TrafficDirection.INTERNAL
    requests_per_second: float = 0.0
    error_rate_pct: float = 0.0
    p99_latency_ms: float = 0.0
    health: TrafficHealth = TrafficHealth.HEALTHY
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class TrafficAnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    dest_service: str = ""
    anomaly_type: TrafficAnomaly = TrafficAnomaly.SPIKE
    severity: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class TrafficPatternReport(BaseModel):
    total_traffic_records: int = 0
    total_anomalies: int = 0
    avg_error_rate_pct: float = 0.0
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    hotspot_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TrafficPatternAnalyzer:
    """Track service traffic patterns, anomalies, and hotspots."""

    def __init__(
        self,
        max_records: int = 200000,
        error_threshold_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._error_threshold_pct = error_threshold_pct
        self._records: list[TrafficRecord] = []
        self._anomalies: list[TrafficAnomalyRecord] = []
        logger.info(
            "traffic_pattern.initialized",
            max_records=max_records,
            error_threshold_pct=error_threshold_pct,
        )

    # -- record / get / list -------------------------------------------------

    def record_traffic(
        self,
        source_service: str,
        dest_service: str = "",
        direction: TrafficDirection = TrafficDirection.INTERNAL,
        requests_per_second: float = 0.0,
        error_rate_pct: float = 0.0,
        p99_latency_ms: float = 0.0,
        health: TrafficHealth = TrafficHealth.HEALTHY,
        details: str = "",
    ) -> TrafficRecord:
        record = TrafficRecord(
            source_service=source_service,
            dest_service=dest_service,
            direction=direction,
            requests_per_second=requests_per_second,
            error_rate_pct=error_rate_pct,
            p99_latency_ms=p99_latency_ms,
            health=health,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "traffic_pattern.traffic_recorded",
            record_id=record.id,
            source_service=source_service,
            dest_service=dest_service,
        )
        return record

    def get_traffic(self, record_id: str) -> TrafficRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_traffic(
        self,
        source_service: str | None = None,
        direction: TrafficDirection | None = None,
        limit: int = 50,
    ) -> list[TrafficRecord]:
        results = list(self._records)
        if source_service is not None:
            results = [r for r in results if r.source_service == source_service]
        if direction is not None:
            results = [r for r in results if r.direction == direction]
        return results[-limit:]

    def record_anomaly(
        self,
        source_service: str,
        dest_service: str = "",
        anomaly_type: TrafficAnomaly = TrafficAnomaly.SPIKE,
        severity: float = 0.0,
        details: str = "",
    ) -> TrafficAnomalyRecord:
        anomaly = TrafficAnomalyRecord(
            source_service=source_service,
            dest_service=dest_service,
            anomaly_type=anomaly_type,
            severity=severity,
            details=details,
        )
        self._anomalies.append(anomaly)
        if len(self._anomalies) > self._max_records:
            self._anomalies = self._anomalies[-self._max_records :]
        logger.info(
            "traffic_pattern.anomaly_recorded",
            source_service=source_service,
            anomaly_type=anomaly_type.value,
        )
        return anomaly

    # -- domain operations ---------------------------------------------------

    def analyze_service_pair(self, source_service: str, dest_service: str) -> dict[str, Any]:
        """Analyze traffic between a specific service pair."""
        records = [
            r
            for r in self._records
            if r.source_service == source_service and r.dest_service == dest_service
        ]
        if not records:
            return {
                "source_service": source_service,
                "dest_service": dest_service,
                "status": "no_data",
            }
        total = len(records)
        avg_rps = round(sum(r.requests_per_second for r in records) / total, 2)
        avg_err = round(sum(r.error_rate_pct for r in records) / total, 2)
        avg_lat = round(sum(r.p99_latency_ms for r in records) / total, 2)
        return {
            "source_service": source_service,
            "dest_service": dest_service,
            "total_records": total,
            "avg_requests_per_second": avg_rps,
            "avg_error_rate_pct": avg_err,
            "avg_p99_latency_ms": avg_lat,
        }

    def identify_hotspots(self) -> list[dict[str, Any]]:
        """Find traffic records with error rate above threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.error_rate_pct > self._error_threshold_pct:
                results.append(
                    {
                        "source_service": r.source_service,
                        "dest_service": r.dest_service,
                        "error_rate_pct": r.error_rate_pct,
                        "health": r.health.value,
                        "direction": r.direction.value,
                    }
                )
        results.sort(key=lambda x: x["error_rate_pct"], reverse=True)
        return results

    def detect_error_prone_routes(self) -> list[dict[str, Any]]:
        """Detect service pairs with high average error rates."""
        pair_errors: dict[str, list[float]] = {}
        for r in self._records:
            key = f"{r.source_service}->{r.dest_service}"
            pair_errors.setdefault(key, []).append(r.error_rate_pct)
        results: list[dict[str, Any]] = []
        for pair, errors in pair_errors.items():
            avg_err = round(sum(errors) / len(errors), 2)
            if avg_err > self._error_threshold_pct:
                parts = pair.split("->")
                results.append(
                    {
                        "source_service": parts[0],
                        "dest_service": parts[1],
                        "avg_error_rate_pct": avg_err,
                        "sample_count": len(errors),
                    }
                )
        results.sort(key=lambda x: x["avg_error_rate_pct"], reverse=True)
        return results

    def rank_by_latency(self) -> list[dict[str, Any]]:
        """Rank service pairs by average p99 latency."""
        pair_latencies: dict[str, list[float]] = {}
        for r in self._records:
            key = f"{r.source_service}->{r.dest_service}"
            pair_latencies.setdefault(key, []).append(r.p99_latency_ms)
        results: list[dict[str, Any]] = []
        for pair, lats in pair_latencies.items():
            parts = pair.split("->")
            results.append(
                {
                    "source_service": parts[0],
                    "dest_service": parts[1],
                    "avg_p99_latency_ms": round(sum(lats) / len(lats), 2),
                    "sample_count": len(lats),
                }
            )
        results.sort(key=lambda x: x["avg_p99_latency_ms"], reverse=True)
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> TrafficPatternReport:
        by_direction: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_direction[r.direction.value] = by_direction.get(r.direction.value, 0) + 1
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
        total = len(self._records)
        avg_err = round(sum(r.error_rate_pct for r in self._records) / total, 2) if total else 0.0
        hotspot_count = sum(
            1 for r in self._records if r.error_rate_pct > self._error_threshold_pct
        )
        recs: list[str] = []
        if hotspot_count > 0:
            recs.append(
                f"{hotspot_count} hotspot(s) exceed {self._error_threshold_pct}% error threshold"
            )
        if len(self._anomalies) > 0:
            recs.append(f"{len(self._anomalies)} traffic anomaly/anomalies detected")
        if not recs:
            recs.append("Traffic pattern health meets targets")
        return TrafficPatternReport(
            total_traffic_records=total,
            total_anomalies=len(self._anomalies),
            avg_error_rate_pct=avg_err,
            by_direction=by_direction,
            by_health=by_health,
            hotspot_count=hotspot_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._anomalies.clear()
        logger.info("traffic_pattern.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        direction_dist: dict[str, int] = {}
        for r in self._records:
            key = r.direction.value
            direction_dist[key] = direction_dist.get(key, 0) + 1
        return {
            "total_traffic_records": len(self._records),
            "total_anomalies": len(self._anomalies),
            "error_threshold_pct": self._error_threshold_pct,
            "direction_distribution": direction_dist,
            "unique_sources": len({r.source_service for r in self._records}),
        }
