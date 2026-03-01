"""SLO Dependency Mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_dep_mapper import (
    DependencyType,
    MappingStatus,
    RiskLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-dep-mapper",
    tags=["SLO Dep Mapper"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO dep mapper service unavailable")
    return _engine


class RecordMappingRequest(BaseModel):
    service: str
    dependency_service: str = ""
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    dependency_type: DependencyType = DependencyType.HARD
    risk_level: RiskLevel = RiskLevel.NONE
    slo_target_pct: float = 0.0
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    service_pattern: str
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    dependency_type: DependencyType = DependencyType.HARD
    min_slo_pct: float = 0.0
    reason: str = ""
    model_config = {"extra": "forbid"}


@router.post("/mappings")
async def record_mapping(
    body: RecordMappingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_mapping(**body.model_dump())
    return result.model_dump()


@router.get("/mappings")
async def list_mappings(
    mapping_status: MappingStatus | None = None,
    dependency_type: DependencyType | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_mappings(
            mapping_status=mapping_status,
            dependency_type=dependency_type,
            team=team,
            limit=limit,
        )
    ]


@router.get("/mappings/{record_id}")
async def get_mapping(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_mapping(record_id)
    if result is None:
        raise HTTPException(404, f"Mapping '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/coverage")
async def analyze_mapping_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_mapping_coverage()


@router.get("/unmapped")
async def identify_unmapped_deps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unmapped_deps()


@router.get("/cascade-risk-rankings")
async def rank_by_cascade_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cascade_risk()


@router.get("/trends")
async def detect_mapping_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_mapping_trends()


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


sdm_route = router
