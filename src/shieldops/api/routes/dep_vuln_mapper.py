"""Dependency vulnerability mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dep_vuln_mapper import (
    DependencyType,
    RemediationStatus,
    VulnSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dep-vuln-mapper",
    tags=["Dep Vuln Mapper"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dep vuln mapper service unavailable")
    return _engine


class RecordMappingRequest(BaseModel):
    dependency_name: str
    vuln_id: str = ""
    severity: VulnSeverity = VulnSeverity.MEDIUM
    dependency_type: DependencyType = DependencyType.DIRECT
    remediation_status: RemediationStatus = RemediationStatus.PENDING
    risk_score: float = 0.0
    details: str = ""


class AddDependencyDetailRequest(BaseModel):
    dependency_name: str
    vuln_id: str = ""
    affected_version: str = ""
    fixed_version: str = ""
    description: str = ""


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
    dependency_name: str | None = None,
    severity: VulnSeverity | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_mappings(
            dependency_name=dependency_name,
            severity=severity,
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


@router.post("/details")
async def add_dependency_detail(
    body: AddDependencyDetailRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_dependency_detail(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/severity/{severity}")
async def analyze_vuln_by_severity(
    severity: VulnSeverity,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_vuln_by_severity(severity)


@router.get("/critical-dependencies")
async def identify_critical_dependencies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_dependencies()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_vuln_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_vuln_trends()


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


dvm_route = router
