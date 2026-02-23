"""Webhook replay API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/webhook-replay", tags=["Webhook Replay"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Webhook replay service unavailable")
    return _engine


class ReplayBatchRequest(BaseModel):
    delivery_ids: list[str]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.get("/failed")
async def get_failed_deliveries(
    subscription_id: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        d.model_dump()
        for d in engine.get_failed_deliveries(subscription_id=subscription_id, limit=limit)
    ]


@router.get("/deliveries")
async def list_deliveries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.get("/deliveries/{delivery_id}")
async def get_delivery(
    delivery_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    delivery = engine.get_delivery(delivery_id)
    if delivery is None:
        raise HTTPException(404, f"Delivery '{delivery_id}' not found")
    return delivery.model_dump()


@router.post("/replay/{delivery_id}")
async def replay_delivery(
    delivery_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    delivery = engine.replay_delivery(delivery_id)
    if delivery is None:
        raise HTTPException(404, f"Delivery '{delivery_id}' not found")
    return delivery.model_dump()


@router.post("/replay-batch")
async def replay_batch(
    body: ReplayBatchRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.replay_batch(body.delivery_ids)
    return result.model_dump()
