"""Service mesh intelligence API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.service_mesh_intel import (
    MeshAntiPattern,
    MeshHealth,
    MeshPattern,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/service-mesh",
    tags=["Service Mesh"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Service mesh service unavailable",
        )
    return _engine


class RecordObservationRequest(BaseModel):
    service_name: str
    pattern: MeshPattern = MeshPattern.DIRECT_CALL
    health: MeshHealth = MeshHealth.OPTIMAL
    anti_pattern: MeshAntiPattern = MeshAntiPattern.UNNECESSARY_HOP
    latency_ms: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    pattern: MeshPattern = MeshPattern.DIRECT_CALL
    health: MeshHealth = MeshHealth.OPTIMAL
    max_latency_ms: float = 500.0
    auto_optimize: bool = False


@router.post("/observations")
async def record_observation(
    body: RecordObservationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_observation(**body.model_dump())
    return result.model_dump()


@router.get("/observations")
async def list_observations(
    service_name: str | None = None,
    pattern: MeshPattern | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_observations(
            service_name=service_name,
            pattern=pattern,
            limit=limit,
        )
    ]


@router.get("/observations/{record_id}")
async def get_observation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_observation(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Observation '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/health/{service_name}")
async def analyze_mesh_health(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_mesh_health(service_name)


@router.get("/anti-patterns")
async def identify_anti_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_anti_patterns()


@router.get("/rankings")
async def rank_by_latency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_latency()


@router.get("/mesh-issues")
async def detect_mesh_issues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_mesh_issues()


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


smi_route = router
