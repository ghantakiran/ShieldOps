"""Distributed trace analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/trace-analyzer",
    tags=["Trace Analyzer"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Trace analyzer service unavailable")
    return _analyzer


class IngestTraceRequest(BaseModel):
    trace_id: str
    service: str
    operation: str = ""
    segment_type: str = "http"
    duration_ms: float = 0.0
    parent_span_id: str | None = None
    status_code: int = 200
    error: bool = False
    tags: dict[str, str] | None = None


@router.post("/traces")
async def ingest_trace(
    body: IngestTraceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    record = analyzer.ingest_trace(
        trace_id=body.trace_id,
        service=body.service,
        operation=body.operation,
        segment_type=body.segment_type,
        duration_ms=body.duration_ms,
        parent_span_id=body.parent_span_id,
        status_code=body.status_code,
        error=body.error,
        tags=body.tags,
    )
    return record.model_dump()


@router.get("/traces")
async def list_traces(
    service: str | None = None,
    segment_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    traces = analyzer.list_traces(service=service, segment_type=segment_type, limit=limit)
    return [t.model_dump() for t in traces]


@router.get("/traces/{record_id}")
async def get_trace(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    record = analyzer.get_trace(record_id)
    if record is None:
        raise HTTPException(404, f"Trace '{record_id}' not found")
    return record.model_dump()


@router.post("/bottlenecks")
async def detect_bottlenecks(
    service: str | None = None,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    reports = analyzer.detect_bottlenecks(service=service)
    return [r.model_dump() for r in reports]


@router.get("/attribution/{trace_id}")
async def compute_latency_attribution(
    trace_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    attrs = analyzer.compute_latency_attribution(trace_id)
    return [a.model_dump() for a in attrs]


@router.get("/slow-endpoints")
async def get_slow_endpoints(
    threshold_ms: float = 1000.0,
    limit: int = 20,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_slow_endpoints(threshold_ms=threshold_ms, limit=limit)


@router.post("/baseline-compare")
async def compare_baseline(
    service: str,
    operation: str,
    baseline_avg_ms: float,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.compare_baseline(service, operation, baseline_avg_ms)


@router.get("/flow/{trace_id}")
async def get_service_flow(
    trace_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_service_flow(trace_id)


@router.delete("/traces")
async def clear_traces(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    count = analyzer.clear_traces()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
