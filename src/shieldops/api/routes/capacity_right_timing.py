"""Capacity right-timing API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
crt_route = APIRouter(
    prefix="/capacity-right-timing",
    tags=["Capacity Right-Timing"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Capacity right-timing service unavailable",
        )
    return _instance


# -- Request models --


class CreateRecommendationRequest(BaseModel):
    service_name: str
    direction: str = "no_change"
    recommended_at_hour: int = 0
    confidence: str = "very_low"
    traffic_pattern: str = "diurnal"
    cost_saving_pct: float = 0.0
    reason: str = ""


class RegisterWindowRequest(BaseModel):
    service_name: str
    start_hour: int = 0
    end_hour: int = 23
    expected_load_pct: float = 0.0
    pattern: str = "diurnal"
    day_of_week: int = 0


class FindOptimalRequest(BaseModel):
    service_name: str
    direction: str = "scale_up"


# -- Routes --


@crt_route.post("/recommendations")
async def create_recommendation(
    body: CreateRecommendationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rec = engine.create_recommendation(**body.model_dump())
    return rec.model_dump()


@crt_route.get("/recommendations")
async def list_recommendations(
    service_name: str | None = None,
    direction: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_recommendations(
            service_name=service_name,
            direction=direction,
            limit=limit,
        )
    ]


@crt_route.get("/recommendations/{rec_id}")
async def get_recommendation(
    rec_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rec = engine.get_recommendation(rec_id)
    if rec is None:
        raise HTTPException(404, f"Recommendation '{rec_id}' not found")
    return rec.model_dump()


@crt_route.post("/windows")
async def register_window(
    body: RegisterWindowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    window = engine.register_traffic_window(**body.model_dump())
    return window.model_dump()


@crt_route.get("/windows")
async def list_windows(
    service_name: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        w.model_dump()
        for w in engine.list_traffic_windows(
            service_name=service_name,
            limit=limit,
        )
    ]


@crt_route.post("/optimal-time")
async def find_optimal_time(
    body: FindOptimalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rec = engine.find_optimal_scale_time(
        body.service_name,
        body.direction,
    )
    return rec.model_dump()


@crt_route.get("/evaluate/{rec_id}")
async def evaluate_timing(
    rec_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.evaluate_timing(rec_id)


@crt_route.post("/cancel/{rec_id}")
async def cancel_recommendation(
    rec_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.cancel_recommendation(rec_id)
    if not result:
        raise HTTPException(404, f"Recommendation '{rec_id}' not found")
    return {"cancelled": True, "rec_id": rec_id}


@crt_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_timing_report().model_dump()


@crt_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
