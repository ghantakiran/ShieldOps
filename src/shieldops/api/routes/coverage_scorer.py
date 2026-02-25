"""Observability coverage scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.coverage_scorer import (
    GapPriority,
    ObservabilityPillar,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/observability-coverage",
    tags=["Observability Coverage"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Observability coverage service unavailable",
        )
    return _engine


class RecordCoverageRequest(BaseModel):
    service: str
    pillar: ObservabilityPillar
    coverage_pct: float = 0.0
    details: str = ""


class RecordGapRequest(BaseModel):
    service: str
    pillar: ObservabilityPillar
    priority: GapPriority = GapPriority.MEDIUM
    description: str = ""
    remediation: str = ""


@router.post("/coverage")
async def record_coverage(
    body: RecordCoverageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_coverage(**body.model_dump())
    return result.model_dump()


@router.get("/coverage")
async def list_coverage(
    service: str | None = None,
    pillar: ObservabilityPillar | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_coverage(service=service, pillar=pillar, limit=limit)
    ]


@router.get("/coverage/{record_id}")
async def get_coverage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_coverage(record_id)
    if result is None:
        raise HTTPException(404, f"Coverage record '{record_id}' not found")
    return result.model_dump()


@router.post("/gaps")
async def record_gap(
    body: RecordGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_gap(**body.model_dump())
    return result.model_dump()


@router.get("/score/{service}")
async def calculate_service_score(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_service_score(service)


@router.get("/instrumentation-gaps")
async def identify_instrumentation_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_instrumentation_gaps()


@router.get("/rankings")
async def rank_services_by_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_services_by_coverage()


@router.get("/pillar-breakdown")
async def get_pillar_breakdown(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_pillar_breakdown()


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


ocs_route = router
