"""Event correlation engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/event-correlation",
    tags=["Event Correlation"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Event correlation service unavailable")
    return _engine


class SubmitEventRequest(BaseModel):
    source: str = "metrics"
    service: str = ""
    event_type: str = ""
    description: str = ""
    severity: str = "info"
    tags: dict[str, str] | None = None
    occurred_at: float | None = None


class CorrelateWindowRequest(BaseModel):
    window_start: float | None = None
    window_end: float | None = None
    strategy: str = "temporal"


class BuildChainRequest(BaseModel):
    event_ids: list[str]


@router.post("/events")
async def submit_event(
    body: SubmitEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    event = engine.submit_event(
        source=body.source,
        service=body.service,
        event_type=body.event_type,
        description=body.description,
        severity=body.severity,
        tags=body.tags,
        occurred_at=body.occurred_at,
    )
    return event.model_dump()


@router.get("/events")
async def list_events(
    source: str | None = None,
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    events = engine.list_events(source=source, service=service, limit=limit)
    return [e.model_dump() for e in events]


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    event = engine.get_event(event_id)
    if event is None:
        raise HTTPException(404, f"Event '{event_id}' not found")
    return event.model_dump()


@router.post("/correlate")
async def correlate_window(
    body: CorrelateWindowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.correlate_window(
        window_start=body.window_start,
        window_end=body.window_end,
        strategy=body.strategy,
    )
    return report.model_dump()


@router.post("/causal-chain")
async def build_causal_chain(
    body: BuildChainRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    chain = engine.build_causal_chain(body.event_ids)
    return chain.model_dump()


@router.get("/root-causes")
async def rank_root_causes(
    report_id: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_root_causes(report_id=report_id)


@router.get("/timeline")
async def get_timeline(
    service: str | None = None,
    window_minutes: int | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.get_timeline(service=service, window_minutes=window_minutes)


@router.get("/reports")
async def list_reports(
    limit: int = 20,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    reports = engine.list_reports(limit=limit)
    return [r.model_dump() for r in reports]


@router.delete("/events")
async def clear_events(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    count = engine.clear_events()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
