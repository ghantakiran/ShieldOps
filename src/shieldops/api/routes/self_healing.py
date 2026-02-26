"""Self-healing orchestrator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.self_healing import (
    HealingAction,
    HealingOutcome,
    HealingTrigger,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/self-healing",
    tags=["Self Healing"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Self-healing service unavailable")
    return _engine


class RecordHealingRequest(BaseModel):
    service_name: str
    action: HealingAction = HealingAction.RESTART_SERVICE
    outcome: HealingOutcome = HealingOutcome.SUCCESS
    trigger: HealingTrigger = HealingTrigger.ALERT
    duration_seconds: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    action: HealingAction = HealingAction.RESTART_SERVICE
    trigger: HealingTrigger = HealingTrigger.ALERT
    max_retries: int = 3
    cooldown_seconds: float = 300.0


@router.post("/healings")
async def record_healing(
    body: RecordHealingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_healing(**body.model_dump())
    return result.model_dump()


@router.get("/healings")
async def list_healings(
    service_name: str | None = None,
    action: HealingAction | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_healings(service_name=service_name, action=action, limit=limit)
    ]


@router.get("/healings/{record_id}")
async def get_healing(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_healing(record_id)
    if result is None:
        raise HTTPException(404, f"Healing '{record_id}' not found")
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{service_name}")
async def analyze_healing_effectiveness(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_healing_effectiveness(service_name)


@router.get("/repeat-failures")
async def identify_repeat_failures(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_repeat_failures()


@router.get("/rankings")
async def rank_by_healing_frequency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_healing_frequency()


@router.get("/healing-loops")
async def detect_healing_loops(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_healing_loops()


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


slh_route = router
