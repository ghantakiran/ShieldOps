"""Network Latency Mapper — map and monitor network latency across paths."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LatencyCategory(StrEnum):
    INTRA_AZ = "intra_az"
    CROSS_AZ = "cross_az"
    CROSS_REGION = "cross_region"
    CROSS_CLOUD = "cross_cloud"
    EXTERNAL = "external"


class LatencyHealth(StrEnum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    POOR = "poor"
    CRITICAL = "critical"


class PathType(StrEnum):
    DIRECT = "direct"
    LOAD_BALANCED = "load_balanced"
    PROXIED = "proxied"
    MESH = "mesh"
    VPN = "vpn"


# --- Models ---


class LatencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path_name: str = ""
    category: LatencyCategory = LatencyCategory.INTRA_AZ
    health: LatencyHealth = LatencyHealth.OPTIMAL
    path_type: PathType = PathType.DIRECT
    latency_ms: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LatencyPath(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path_name: str = ""
    category: LatencyCategory = LatencyCategory.INTRA_AZ
    health: LatencyHealth = LatencyHealth.OPTIMAL
    source_service: str = ""
    target_service: str = ""
    created_at: float = Field(default_factory=time.time)


class NetworkLatencyReport(BaseModel):
    total_measurements: int = 0
    total_paths: int = 0
    healthy_rate_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class NetworkLatencyMapper:
    """Map and monitor network latency across paths."""

    def __init__(
        self,
        max_records: int = 200000,
        max_acceptable_ms: float = 100.0,
    ) -> None:
        self._max_records = max_records
        self._max_acceptable_ms = max_acceptable_ms
        self._records: list[LatencyRecord] = []
        self._paths: list[LatencyPath] = []
        logger.info(
            "network_latency.initialized",
            max_records=max_records,
            max_acceptable_ms=max_acceptable_ms,
        )

    # -- record / get / list ---------------------------------------------

    def record_latency(
        self,
        path_name: str,
        category: LatencyCategory = LatencyCategory.INTRA_AZ,
        health: LatencyHealth = LatencyHealth.OPTIMAL,
        path_type: PathType = PathType.DIRECT,
        latency_ms: float = 0.0,
        details: str = "",
    ) -> LatencyRecord:
        record = LatencyRecord(
            path_name=path_name,
            category=category,
            health=health,
            path_type=path_type,
            latency_ms=latency_ms,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "network_latency.latency_recorded",
            record_id=record.id,
            path_name=path_name,
            category=category.value,
            health=health.value,
        )
        return record

    def get_latency(self, record_id: str) -> LatencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_latencies(
        self,
        path_name: str | None = None,
        category: LatencyCategory | None = None,
        limit: int = 50,
    ) -> list[LatencyRecord]:
        results = list(self._records)
        if path_name is not None:
            results = [r for r in results if r.path_name == path_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_path(
        self,
        path_name: str,
        category: LatencyCategory = LatencyCategory.INTRA_AZ,
        health: LatencyHealth = LatencyHealth.OPTIMAL,
        source_service: str = "",
        target_service: str = "",
    ) -> LatencyPath:
        path = LatencyPath(
            path_name=path_name,
            category=category,
            health=health,
            source_service=source_service,
            target_service=target_service,
        )
        self._paths.append(path)
        if len(self._paths) > self._max_records:
            self._paths = self._paths[-self._max_records :]
        logger.info(
            "network_latency.path_added",
            path_name=path_name,
            category=category.value,
            health=health.value,
        )
        return path

    # -- domain operations -----------------------------------------------

    def analyze_network_health(self, path_name: str) -> dict[str, Any]:
        """Analyze network health for a specific path."""
        records = [r for r in self._records if r.path_name == path_name]
        if not records:
            return {"path_name": path_name, "status": "no_data"}
        avg_latency = round(sum(r.latency_ms for r in records) / len(records), 2)
        return {
            "path_name": path_name,
            "avg_latency": avg_latency,
            "record_count": len(records),
            "meets_threshold": avg_latency <= self._max_acceptable_ms,
        }

    def identify_high_latency_paths(self) -> list[dict[str, Any]]:
        """Find paths with >1 POOR or CRITICAL health."""
        high_counts: dict[str, int] = {}
        for r in self._records:
            if r.health in (LatencyHealth.POOR, LatencyHealth.CRITICAL):
                high_counts[r.path_name] = high_counts.get(r.path_name, 0) + 1
        results: list[dict[str, Any]] = []
        for path, count in high_counts.items():
            if count > 1:
                results.append(
                    {
                        "path_name": path,
                        "high_latency_count": count,
                    }
                )
        results.sort(key=lambda x: x["high_latency_count"], reverse=True)
        return results

    def rank_by_latency(self) -> list[dict[str, Any]]:
        """Rank paths by avg latency_ms descending."""
        latencies: dict[str, list[float]] = {}
        for r in self._records:
            latencies.setdefault(r.path_name, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for path, vals in latencies.items():
            results.append(
                {
                    "path_name": path,
                    "avg_latency_ms": round(sum(vals) / len(vals), 2),
                }
            )
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        return results

    def detect_latency_anomalies(self) -> list[dict[str, Any]]:
        """Detect paths with >3 degraded records."""
        counts: dict[str, int] = {}
        for r in self._records:
            if r.health in (
                LatencyHealth.DEGRADED,
                LatencyHealth.POOR,
                LatencyHealth.CRITICAL,
            ):
                counts[r.path_name] = counts.get(r.path_name, 0) + 1
        results: list[dict[str, Any]] = []
        for path, count in counts.items():
            if count > 3:
                results.append(
                    {
                        "path_name": path,
                        "degraded_count": count,
                        "anomaly_detected": True,
                    }
                )
        results.sort(key=lambda x: x["degraded_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> NetworkLatencyReport:
        by_category: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
        healthy = sum(
            1
            for r in self._records
            if r.health in (LatencyHealth.OPTIMAL, LatencyHealth.ACCEPTABLE)
        )
        healthy_rate = round(healthy / len(self._records) * 100, 2) if self._records else 0.0
        critical_count = sum(1 for d in self.identify_high_latency_paths())
        recs: list[str] = []
        if self._records and healthy_rate < 80.0:
            recs.append(f"Healthy rate {healthy_rate}% is below 80.0% threshold")
        if critical_count > 0:
            recs.append(f"{critical_count} path(s) with high latency")
        anomalies = len(self.detect_latency_anomalies())
        if anomalies > 0:
            recs.append(f"{anomalies} path(s) with latency anomalies detected")
        if not recs:
            recs.append("Network latency meets targets")
        return NetworkLatencyReport(
            total_measurements=len(self._records),
            total_paths=len(self._paths),
            healthy_rate_pct=healthy_rate,
            by_category=by_category,
            by_health=by_health,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._paths.clear()
        logger.info("network_latency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_measurements": len(self._records),
            "total_paths": len(self._paths),
            "max_acceptable_ms": self._max_acceptable_ms,
            "category_distribution": category_dist,
            "unique_paths": len({r.path_name for r in self._records}),
        }
