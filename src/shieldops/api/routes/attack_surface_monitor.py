"""Attack surface monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.attack_surface import (
    ExposureLevel,
    SurfaceRisk,
    SurfaceType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/attack-surface",
    tags=["Attack Surface"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Attack surface service unavailable")
    return _engine


class RecordSurfaceRequest(BaseModel):
    service_name: str
    surface_type: SurfaceType = SurfaceType.PUBLIC_API
    exposure: ExposureLevel = ExposureLevel.INTERNAL
    risk: SurfaceRisk = SurfaceRisk.LOW
    risk_score: float = 0.0
    details: str = ""


class AddExposureRequest(BaseModel):
    exposure_name: str
    surface_type: SurfaceType = SurfaceType.PUBLIC_API
    exposure: ExposureLevel = ExposureLevel.INTERNAL
    severity_score: float = 0.0
    description: str = ""


@router.post("/surfaces")
async def record_surface(
    body: RecordSurfaceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_surface(**body.model_dump())
    return result.model_dump()


@router.get("/surfaces")
async def list_surfaces(
    service_name: str | None = None,
    surface_type: SurfaceType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_surfaces(
            service_name=service_name, surface_type=surface_type, limit=limit
        )
    ]


@router.get("/surfaces/{record_id}")
async def get_surface(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_surface(record_id)
    if result is None:
        raise HTTPException(404, f"Surface '{record_id}' not found")
    return result.model_dump()


@router.post("/exposures")
async def add_exposure(
    body: AddExposureRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_exposure(**body.model_dump())
    return result.model_dump()


@router.get("/risk-analysis/{service_name}")
async def analyze_surface_risk(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_surface_risk(service_name)


@router.get("/critical-exposures")
async def identify_critical_exposures(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_exposures()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/expansion")
async def detect_surface_expansion(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_surface_expansion()


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


asm_route = router
