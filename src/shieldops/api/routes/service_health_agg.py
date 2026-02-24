"""Service health aggregation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/service-health-agg",
    tags=["Service Health Aggregation"],
)

_aggregator: Any = None


def set_aggregator(aggregator: Any) -> None:
    global _aggregator
    _aggregator = aggregator


def _get_aggregator() -> Any:
    if _aggregator is None:
        raise HTTPException(
            503,
            "Service health aggregation unavailable",
        )
    return _aggregator


# -- Request models -------------------------------------------------


class ReportSignalRequest(BaseModel):
    service_name: str
    source: str = "metrics"
    status: str = "unknown"
    score: float = 100.0
    details: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# -- Routes ---------------------------------------------------------


@router.post("/signals")
async def report_signal(
    body: ReportSignalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    signal = agg.report_signal(**body.model_dump())
    return signal.model_dump()


@router.get("/signals/{signal_id}")
async def get_signal(
    signal_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    signal = agg.get_signal(signal_id)
    if signal is None:
        raise HTTPException(
            404,
            f"Signal '{signal_id}' not found",
        )
    return signal.model_dump()


@router.get("/signals")
async def list_signals(
    service_name: str | None = None,
    source: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    agg = _get_aggregator()
    items = agg.list_signals(
        service_name=service_name,
        source=source,
        limit=limit,
    )
    return [s.model_dump() for s in items]


@router.get("/score/{service_name}")
async def calculate_health_score(
    service_name: str,
    strategy: str = "weighted_average",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    score = agg.calculate_health_score(
        service_name,
        strategy=strategy,
    )
    return score.model_dump()


@router.get("/degradation/{service_name}")
async def detect_degradation(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    agg = _get_aggregator()
    signals = agg.detect_health_degradation(service_name)
    return [s.model_dump() for s in signals]


@router.get("/ranking")
async def rank_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    agg = _get_aggregator()
    return [s.model_dump() for s in agg.rank_services_by_health()]


@router.get("/flapping")
async def identify_flapping(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    agg = _get_aggregator()
    return agg.identify_flapping_services()


@router.get("/availability/{service_name}")
async def get_availability(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    pct = agg.calculate_availability_pct(service_name)
    return {
        "service_name": service_name,
        "availability_pct": pct,
    }


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    return agg.generate_health_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    return agg.get_stats()
