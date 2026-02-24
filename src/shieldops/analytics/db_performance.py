"""Database Performance Analyzer — query analysis, slow query detection, pool health."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QueryCategory(StrEnum):
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    DDL = "ddl"
    PROCEDURE = "procedure"


class PerformanceLevel(StrEnum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class PoolStatus(StrEnum):
    HEALTHY = "healthy"
    SATURATED = "saturated"
    EXHAUSTED = "exhausted"
    IDLE = "idle"


# --- Models ---


class QueryProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str = ""
    category: QueryCategory = QueryCategory.SELECT
    database: str = ""
    duration_ms: float = 0.0
    rows_affected: int = 0
    is_slow: bool = False
    created_at: float = Field(default_factory=time.time)


class ConnectionPoolSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    database: str = ""
    active_connections: int = 0
    idle_connections: int = 0
    max_connections: int = 100
    wait_queue_size: int = 0
    status: PoolStatus = PoolStatus.HEALTHY
    created_at: float = Field(default_factory=time.time)


class DatabaseHealthReport(BaseModel):
    database: str = ""
    total_queries: int = 0
    slow_query_count: int = 0
    avg_duration_ms: float = 0.0
    performance_level: PerformanceLevel = PerformanceLevel.OPTIMAL
    pool_status: PoolStatus = PoolStatus.HEALTHY
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DatabasePerformanceAnalyzer:
    """Query pattern analysis, slow query detection, and connection pool health monitoring."""

    def __init__(
        self,
        max_queries: int = 200000,
        slow_threshold_ms: float = 500.0,
    ) -> None:
        self._max_queries = max_queries
        self._slow_threshold_ms = slow_threshold_ms
        self._queries: list[QueryProfile] = []
        self._pool_snapshots: list[ConnectionPoolSnapshot] = []
        logger.info(
            "db_performance.initialized",
            max_queries=max_queries,
            slow_threshold_ms=slow_threshold_ms,
        )

    def record_query(
        self,
        query_text: str,
        category: QueryCategory,
        database: str,
        duration_ms: float,
        rows_affected: int = 0,
    ) -> QueryProfile:
        is_slow = duration_ms >= self._slow_threshold_ms
        profile = QueryProfile(
            query_text=query_text,
            category=category,
            database=database,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            is_slow=is_slow,
        )
        self._queries.append(profile)
        if len(self._queries) > self._max_queries:
            self._queries = self._queries[-self._max_queries :]
        logger.info(
            "db_performance.query_recorded",
            query_id=profile.id,
            database=database,
            category=category,
            duration_ms=duration_ms,
            is_slow=is_slow,
        )
        return profile

    def get_query(self, query_id: str) -> QueryProfile | None:
        for q in self._queries:
            if q.id == query_id:
                return q
        return None

    def list_queries(
        self,
        database: str | None = None,
        category: QueryCategory | None = None,
        limit: int = 100,
    ) -> list[QueryProfile]:
        results = list(self._queries)
        if database is not None:
            results = [q for q in results if q.database == database]
        if category is not None:
            results = [q for q in results if q.category == category]
        return results[-limit:]

    def detect_slow_queries(
        self,
        database: str | None = None,
        limit: int = 50,
    ) -> list[QueryProfile]:
        results = [q for q in self._queries if q.is_slow]
        if database is not None:
            results = [q for q in results if q.database == database]
        return results[-limit:]

    def record_pool_snapshot(
        self,
        database: str,
        active_connections: int,
        idle_connections: int,
        max_connections: int,
        wait_queue_size: int = 0,
    ) -> ConnectionPoolSnapshot:
        if active_connections >= max_connections:
            status = PoolStatus.EXHAUSTED
        elif max_connections > 0 and active_connections / max_connections > 0.8:
            status = PoolStatus.SATURATED
        elif active_connections == 0 and idle_connections > 0:
            status = PoolStatus.IDLE
        else:
            status = PoolStatus.HEALTHY
        snapshot = ConnectionPoolSnapshot(
            database=database,
            active_connections=active_connections,
            idle_connections=idle_connections,
            max_connections=max_connections,
            wait_queue_size=wait_queue_size,
            status=status,
        )
        self._pool_snapshots.append(snapshot)
        logger.info(
            "db_performance.pool_snapshot_recorded",
            snapshot_id=snapshot.id,
            database=database,
            status=status,
            active=active_connections,
            max=max_connections,
        )
        return snapshot

    def list_pool_snapshots(
        self,
        database: str | None = None,
        limit: int = 50,
    ) -> list[ConnectionPoolSnapshot]:
        results = list(self._pool_snapshots)
        if database is not None:
            results = [s for s in results if s.database == database]
        return results[-limit:]

    def analyze_query_patterns(
        self,
        database: str | None = None,
    ) -> dict[str, Any]:
        targets = list(self._queries)
        if database is not None:
            targets = [q for q in targets if q.database == database]
        category_stats: dict[str, dict[str, Any]] = {}
        for q in targets:
            cat = q.category.value
            if cat not in category_stats:
                category_stats[cat] = {"count": 0, "total_duration_ms": 0.0}
            category_stats[cat]["count"] += 1
            category_stats[cat]["total_duration_ms"] += q.duration_ms
        breakdown: dict[str, Any] = {}
        for cat, stats in category_stats.items():
            count = stats["count"]
            avg_dur = round(stats["total_duration_ms"] / count, 2) if count > 0 else 0.0
            breakdown[cat] = {"count": count, "avg_duration_ms": avg_dur}
        return {
            "database": database,
            "total_queries": len(targets),
            "category_breakdown": breakdown,
        }

    def generate_health_report(self, database: str) -> DatabaseHealthReport:
        db_queries = [q for q in self._queries if q.database == database]
        total = len(db_queries)
        slow_count = sum(1 for q in db_queries if q.is_slow)
        avg_dur = round(sum(q.duration_ms for q in db_queries) / total, 2) if total > 0 else 0.0
        # Determine performance level
        if total == 0:
            perf_level = PerformanceLevel.OPTIMAL
        elif slow_count / total > 0.3:
            perf_level = PerformanceLevel.CRITICAL
        elif slow_count / total > 0.15:
            perf_level = PerformanceLevel.DEGRADED
        elif slow_count / total > 0.05:
            perf_level = PerformanceLevel.ACCEPTABLE
        else:
            perf_level = PerformanceLevel.OPTIMAL
        # Latest pool status
        db_snapshots = [s for s in self._pool_snapshots if s.database == database]
        pool_st = db_snapshots[-1].status if db_snapshots else PoolStatus.HEALTHY
        # Recommendations
        recommendations: list[str] = []
        if perf_level in (PerformanceLevel.CRITICAL, PerformanceLevel.DEGRADED):
            recommendations.append("Investigate slow queries and add missing indexes")
        if pool_st == PoolStatus.EXHAUSTED:
            recommendations.append("Increase max_connections or optimize connection usage")
        elif pool_st == PoolStatus.SATURATED:
            recommendations.append("Connection pool nearing capacity — consider scaling")
        if slow_count > 0:
            recommendations.append(f"Found {slow_count} slow queries — review execution plans")
        logger.info(
            "db_performance.health_report_generated",
            database=database,
            total_queries=total,
            slow_count=slow_count,
            performance_level=perf_level,
        )
        return DatabaseHealthReport(
            database=database,
            total_queries=total,
            slow_query_count=slow_count,
            avg_duration_ms=avg_dur,
            performance_level=perf_level,
            pool_status=pool_st,
            recommendations=recommendations,
        )

    def get_index_recommendations(
        self,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        slow_selects = [
            q for q in self._queries if q.is_slow and q.category == QueryCategory.SELECT
        ]
        if database is not None:
            slow_selects = [q for q in slow_selects if q.database == database]
        recommendations: list[dict[str, Any]] = []
        seen_queries: set[str] = set()
        for q in slow_selects:
            normalized = q.query_text.strip().lower()
            if normalized in seen_queries:
                continue
            seen_queries.add(normalized)
            recommendations.append(
                {
                    "query_id": q.id,
                    "database": q.database,
                    "query_text": q.query_text,
                    "duration_ms": q.duration_ms,
                    "recommendation": "Consider adding an index to improve this slow SELECT query",
                }
            )
        return recommendations

    def clear_data(self) -> None:
        self._queries.clear()
        self._pool_snapshots.clear()
        logger.info("db_performance.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        databases = {q.database for q in self._queries}
        databases.update(s.database for s in self._pool_snapshots)
        return {
            "total_queries": len(self._queries),
            "total_snapshots": len(self._pool_snapshots),
            "slow_query_count": sum(1 for q in self._queries if q.is_slow),
            "databases": sorted(databases),
        }
