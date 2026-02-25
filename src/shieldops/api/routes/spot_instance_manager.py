"""Spot Instance Manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.spot_instance_manager import (
    FallbackStrategy,
    InstanceStatus,
    SpotMarket,
)

logger = structlog.get_logger()
sim_route = APIRouter(
    prefix="/spot-instance-manager",
    tags=["Spot Instance Manager"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Spot instance manager unavailable")
    return _manager


class RegisterInstanceRequest(BaseModel):
    instance_id: str
    instance_type: str
    market: SpotMarket = SpotMarket.AWS_SPOT
    hourly_rate: float = 0.0
    on_demand_rate: float = 0.0
    fallback_strategy: FallbackStrategy = FallbackStrategy.ON_DEMAND


class RecordInterruptionRequest(BaseModel):
    reason: str
    warning_seconds: int = 0


class ExecuteFallbackRequest(BaseModel):
    strategy: FallbackStrategy


@sim_route.post("/instances")
async def register_instance(
    body: RegisterInstanceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    instance = manager.register_instance(**body.model_dump())
    return instance.model_dump()  # type: ignore[no-any-return]


@sim_route.get("/instances")
async def list_instances(
    market: SpotMarket | None = None,
    status: InstanceStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return [  # type: ignore[no-any-return]
        i.model_dump()
        for i in manager.list_instances(
            market=market,
            status=status,
            limit=limit,
        )
    ]


@sim_route.get("/instances/{spot_id}")
async def get_instance(
    spot_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    instance = manager.get_instance(spot_id)
    if instance is None:
        raise HTTPException(404, f"Instance '{spot_id}' not found")
    return instance.model_dump()  # type: ignore[no-any-return]


@sim_route.post("/instances/{spot_id}/interruption")
async def record_interruption(
    spot_id: str,
    body: RecordInterruptionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    event = manager.record_interruption(
        spot_id,
        body.reason,
        body.warning_seconds,
    )
    if event is None:
        raise HTTPException(404, f"Instance '{spot_id}' not found")
    return event.model_dump()  # type: ignore[no-any-return]


@sim_route.post("/instances/{spot_id}/fallback")
async def execute_fallback(
    spot_id: str,
    body: ExecuteFallbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    instance = manager.execute_fallback(
        spot_id,
        body.strategy,
    )
    if instance is None:
        raise HTTPException(404, f"Instance '{spot_id}' not found")
    return instance.model_dump()  # type: ignore[no-any-return]


@sim_route.get("/savings")
async def get_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.calculate_savings()  # type: ignore[no-any-return]


@sim_route.get("/risk/{instance_type}")
async def get_risk(
    instance_type: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.predict_interruption_risk(  # type: ignore[no-any-return]
        instance_type,
    )


@sim_route.get("/optimal-markets")
async def get_optimal_markets(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return manager.identify_optimal_markets()  # type: ignore[no-any-return]


@sim_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.generate_spot_report().model_dump()  # type: ignore[no-any-return]


@sim_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    manager = _get_manager()
    manager.clear_data()
    return {"status": "cleared"}


@sim_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_stats()  # type: ignore[no-any-return]
