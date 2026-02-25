"""Connection Pool Monitor — monitor database connection pool utilization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PoolStatus(StrEnum):
    HEALTHY = "healthy"
    ELEVATED = "elevated"
    SATURATED = "saturated"
    EXHAUSTED = "exhausted"
    LEAKING = "leaking"


class DatabaseType(StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"


class PoolAction(StrEnum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RECYCLE = "recycle"
    INVESTIGATE_LEAK = "investigate_leak"
    NO_ACTION = "no_action"


# --- Models ---


class PoolMetricRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pool_name: str = ""
    db_type: DatabaseType = DatabaseType.POSTGRESQL
    status: PoolStatus = PoolStatus.HEALTHY
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    wait_time_ms: float = 0.0
    utilization_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PoolRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pool_name: str = ""
    action: PoolAction = PoolAction.NO_ACTION
    reason: str = ""
    priority: int = 0
    created_at: float = Field(default_factory=time.time)


class ConnectionPoolReport(BaseModel):
    total_pools: int = 0
    total_recommendations: int = 0
    avg_utilization_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_db_type: dict[str, int] = Field(default_factory=dict)
    saturated_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConnectionPoolMonitor:
    """Monitor database connection pool utilization."""

    def __init__(
        self,
        max_records: int = 200000,
        saturation_threshold_pct: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._saturation_threshold_pct = saturation_threshold_pct
        self._records: list[PoolMetricRecord] = []
        self._recommendations: list[PoolRecommendation] = []
        logger.info(
            "connection_pool.initialized",
            max_records=max_records,
            saturation_threshold_pct=saturation_threshold_pct,
        )

    # -- record / get / list -------------------------------------------------

    def record_metrics(
        self,
        pool_name: str,
        db_type: DatabaseType = DatabaseType.POSTGRESQL,
        status: PoolStatus = PoolStatus.HEALTHY,
        total_connections: int = 0,
        active_connections: int = 0,
        idle_connections: int = 0,
        wait_time_ms: float = 0.0,
        utilization_pct: float = 0.0,
        details: str = "",
    ) -> PoolMetricRecord:
        record = PoolMetricRecord(
            pool_name=pool_name,
            db_type=db_type,
            status=status,
            total_connections=total_connections,
            active_connections=active_connections,
            idle_connections=idle_connections,
            wait_time_ms=wait_time_ms,
            utilization_pct=utilization_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "connection_pool.metrics_recorded",
            record_id=record.id,
            pool_name=pool_name,
            status=status.value,
        )
        return record

    def get_metrics(self, record_id: str) -> PoolMetricRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_metrics(
        self,
        pool_name: str | None = None,
        db_type: DatabaseType | None = None,
        limit: int = 50,
    ) -> list[PoolMetricRecord]:
        results = list(self._records)
        if pool_name is not None:
            results = [r for r in results if r.pool_name == pool_name]
        if db_type is not None:
            results = [r for r in results if r.db_type == db_type]
        return results[-limit:]

    def add_recommendation(
        self,
        pool_name: str,
        action: PoolAction = PoolAction.NO_ACTION,
        reason: str = "",
        priority: int = 0,
    ) -> PoolRecommendation:
        rec = PoolRecommendation(
            pool_name=pool_name,
            action=action,
            reason=reason,
            priority=priority,
        )
        self._recommendations.append(rec)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        logger.info(
            "connection_pool.recommendation_added",
            pool_name=pool_name,
            action=action.value,
        )
        return rec

    # -- domain operations ---------------------------------------------------

    def analyze_pool_health(self, pool_name: str) -> dict[str, Any]:
        """Analyze health for a specific connection pool."""
        records = [r for r in self._records if r.pool_name == pool_name]
        if not records:
            return {"pool_name": pool_name, "status": "no_data"}
        latest = records[-1]
        return {
            "pool_name": pool_name,
            "utilization_pct": latest.utilization_pct,
            "status": latest.status.value,
            "db_type": latest.db_type.value,
            "active_connections": latest.active_connections,
            "idle_connections": latest.idle_connections,
        }

    def identify_saturated_pools(self) -> list[dict[str, Any]]:
        """Find pools with utilization above saturation threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_pct >= self._saturation_threshold_pct:
                results.append(
                    {
                        "pool_name": r.pool_name,
                        "utilization_pct": r.utilization_pct,
                        "status": r.status.value,
                        "db_type": r.db_type.value,
                    }
                )
        results.sort(key=lambda x: x["utilization_pct"], reverse=True)
        return results

    def detect_potential_leaks(self) -> list[dict[str, Any]]:
        """Find pools with LEAKING status."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status == PoolStatus.LEAKING:
                results.append(
                    {
                        "pool_name": r.pool_name,
                        "utilization_pct": r.utilization_pct,
                        "active_connections": r.active_connections,
                        "idle_connections": r.idle_connections,
                        "db_type": r.db_type.value,
                    }
                )
        return results

    def rank_by_wait_time(self) -> list[dict[str, Any]]:
        """Rank all pools by wait time descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "pool_name": r.pool_name,
                    "wait_time_ms": r.wait_time_ms,
                    "utilization_pct": r.utilization_pct,
                    "status": r.status.value,
                }
            )
        results.sort(key=lambda x: x["wait_time_ms"], reverse=True)
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> ConnectionPoolReport:
        by_status: dict[str, int] = {}
        by_db_type: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_db_type[r.db_type.value] = by_db_type.get(r.db_type.value, 0) + 1
        total = len(self._records)
        avg_util = round(sum(r.utilization_pct for r in self._records) / total, 2) if total else 0.0
        saturated_count = sum(
            1 for r in self._records if r.utilization_pct >= self._saturation_threshold_pct
        )
        recs: list[str] = []
        if saturated_count > 0:
            recs.append(f"{saturated_count} pool(s) at or above saturation threshold")
        leaking = sum(1 for r in self._records if r.status == PoolStatus.LEAKING)
        if leaking > 0:
            recs.append(f"{leaking} pool(s) with potential connection leaks")
        if not recs:
            recs.append("Connection pool health meets targets")
        return ConnectionPoolReport(
            total_pools=total,
            total_recommendations=len(self._recommendations),
            avg_utilization_pct=avg_util,
            by_status=by_status,
            by_db_type=by_db_type,
            saturated_count=saturated_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._recommendations.clear()
        logger.info("connection_pool.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_pools": len(self._records),
            "total_recommendations": len(self._recommendations),
            "saturation_threshold_pct": self._saturation_threshold_pct,
            "status_distribution": status_dist,
            "unique_pools": len({r.pool_name for r in self._records}),
        }
