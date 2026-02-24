"""Database performance API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.db_performance import QueryCategory
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/db-performance",
    tags=["Database Performance"],
)

_instance: Any = None


def set_analyzer(instance: Any) -> None:
    global _instance
    _instance = instance


def _get_analyzer() -> Any:
    if _instance is None:
        raise HTTPException(503, "Database performance service unavailable")
    return _instance


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordQueryRequest(BaseModel):
    query_text: str
    category: str = "SELECT"
    database: str
    duration_ms: float
    rows_affected: int = 0


class PoolSnapshotRequest(BaseModel):
    database: str
    active_connections: int
    idle_connections: int
    max_connections: int
    wait_queue_size: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/queries")
async def record_query(
    body: RecordQueryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    category = QueryCategory(body.category.lower())
    result = analyzer.record_query(
        query_text=body.query_text,
        category=category,
        database=body.database,
        duration_ms=body.duration_ms,
        rows_affected=body.rows_affected,
    )
    return result.model_dump()


@router.get("/queries")
async def list_queries(
    database: str | None = None,
    category: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    cat = QueryCategory(category.lower()) if category is not None else None
    return [
        q.model_dump()
        for q in analyzer.list_queries(
            database=database,
            category=cat,
            limit=limit,
        )
    ]


@router.get("/queries/{query_id}")
async def get_query(
    query_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    result = analyzer.get_query(query_id)
    if result is None:
        raise HTTPException(404, f"Query '{query_id}' not found")
    return result.model_dump()


@router.get("/slow-queries")
async def detect_slow_queries(
    database: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        q.model_dump()
        for q in analyzer.detect_slow_queries(
            database=database,
            limit=limit,
        )
    ]


@router.post("/pool-snapshots")
async def record_pool_snapshot(
    body: PoolSnapshotRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    result = analyzer.record_pool_snapshot(
        database=body.database,
        active_connections=body.active_connections,
        idle_connections=body.idle_connections,
        max_connections=body.max_connections,
        wait_queue_size=body.wait_queue_size,
    )
    return result.model_dump()


@router.get("/pool-snapshots")
async def list_pool_snapshots(
    database: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        s.model_dump()
        for s in analyzer.list_pool_snapshots(
            database=database,
            limit=limit,
        )
    ]


@router.get("/query-patterns")
async def analyze_query_patterns(
    database: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.analyze_query_patterns(database=database)


@router.get("/health-report/{database}")
async def generate_health_report(
    database: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.generate_health_report(database).model_dump()


@router.get("/index-recommendations")
async def get_index_recommendations(
    database: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_index_recommendations(database=database)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
