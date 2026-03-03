"""Spot Instance Manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.spot_instance_manager import (
    InstanceFamily,
    InterruptionBehavior,
    SpotStrategy,
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


class RecordSpotInstanceRequest(BaseModel):
    spot_strategy: SpotStrategy = SpotStrategy.CAPACITY_OPTIMIZED
    instance_family: InstanceFamily = InstanceFamily.GENERAL
    interruption_behavior: InterruptionBehavior = InterruptionBehavior.TERMINATE
    savings_pct: float = 0.0
    on_demand_price: float = 0.0
    spot_price: float = 0.0
    service: str = ""
    team: str = ""


@sim_route.post("/instances")
async def record_spot_instance(
    body: RecordSpotInstanceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    record = manager.record_spot_instance(**body.model_dump())
    return record.model_dump()  # type: ignore[no-any-return]


@sim_route.get("/instances")
async def list_spot_instances(
    spot_strategy: SpotStrategy | None = None,
    instance_family: InstanceFamily | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return [  # type: ignore[no-any-return]
        r.model_dump()
        for r in manager.list_spot_instances(
            spot_strategy=spot_strategy,
            instance_family=instance_family,
            team=team,
            limit=limit,
        )
    ]


@sim_route.get("/instances/{record_id}")
async def get_spot_instance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    record = manager.get_spot_instance(record_id)
    if record is None:
        raise HTTPException(404, f"Spot instance record '{record_id}' not found")
    return record.model_dump()  # type: ignore[no-any-return]


@sim_route.get("/high-savings")
async def identify_high_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return manager.identify_high_savings_spots()  # type: ignore[no-any-return]


@sim_route.get("/rank")
async def rank_by_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return manager.rank_by_savings()  # type: ignore[no-any-return]


@sim_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.generate_report().model_dump()  # type: ignore[no-any-return]


@sim_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    manager = _get_manager()
    return manager.clear_data()  # type: ignore[no-any-return]


@sim_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_stats()  # type: ignore[no-any-return]
