"""Change velocity throttle API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.velocity_throttle import (
    ChangeScope,
    VelocityZone,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/velocity-throttle",
    tags=["Velocity Throttle"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Velocity throttle service unavailable",
        )
    return _engine


class RegisterPolicyRequest(BaseModel):
    name: str
    scope: ChangeScope = ChangeScope.SERVICE
    max_changes_per_hour: int = 10
    warn_at: int = 6
    delay_at: int = 8
    block_at: int = 12


class EvaluateChangeRequest(BaseModel):
    service: str
    team: str = ""
    environment: str = "production"
    change_type: str = ""


@router.post("/policies")
async def register_policy(
    body: RegisterPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.register_policy(**body.model_dump())
    return result.model_dump()


@router.get("/policies")
async def list_policies(
    scope: ChangeScope | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_policies(scope=scope, limit=limit)]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_policy(policy_id)
    if result is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return result.model_dump()


@router.post("/evaluate")
async def evaluate_change(
    body: EvaluateChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.evaluate_change(**body.model_dump())
    return result.model_dump()


@router.get("/velocity/{service}")
async def get_current_velocity(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_current_velocity(service)


@router.get("/zone/{service}")
async def get_current_zone(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_current_zone(service)


@router.get("/records")
async def list_records(
    service: str | None = None,
    zone: VelocityZone | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_records(service=service, zone=zone, limit=limit)]


@router.get("/spikes")
async def identify_velocity_spikes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_velocity_spikes()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


vt_route = router
