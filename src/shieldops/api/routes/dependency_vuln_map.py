"""Dependency vulnerability mapping API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/dependency-vuln-map", tags=["Dependency Vulnerability Map"])

_mapper: Any = None


def set_mapper(mapper: Any) -> None:
    global _mapper
    _mapper = mapper


def _get_mapper() -> Any:
    if _mapper is None:
        raise HTTPException(503, "Dependency vulnerability mapping service unavailable")
    return _mapper


class DependencyInput(BaseModel):
    package_name: str
    version: str = ""
    depth: str = "direct"


class RegisterServiceRequest(BaseModel):
    service: str
    dependencies: list[DependencyInput]


class MapCveRequest(BaseModel):
    cve_id: str
    package_name: str
    affected_versions: list[str] = Field(default_factory=list)
    impact_level: str = "medium"
    description: str = ""


@router.post("/services")
async def register_service(
    body: RegisterServiceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mapper = _get_mapper()
    nodes = mapper.register_service_dependencies(
        body.service, [d.model_dump() for d in body.dependencies]
    )
    return [n.model_dump() for n in nodes]


@router.post("/map-cve")
async def map_cve(
    body: MapCveRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    mapping = mapper.map_cve_impact(**body.model_dump())
    return mapping.model_dump()


@router.get("/affected/{cve_id}")
async def get_affected(
    cve_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[str]:
    mapper = _get_mapper()
    return mapper.get_affected_services(cve_id)


@router.get("/services/{service}/vulnerabilities")
async def get_service_vulns(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mapper = _get_mapper()
    return [v.model_dump() for v in mapper.get_service_vulnerabilities(service)]


@router.get("/tree/{service}")
async def get_tree(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.build_dependency_tree(service)


@router.get("/mappings")
async def list_mappings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mapper = _get_mapper()
    return [m.model_dump() for m in mapper.list_mappings()]


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    assessment = mapper.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(404, f"Assessment '{assessment_id}' not found")
    return assessment.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mapper = _get_mapper()
    return mapper.get_stats()
