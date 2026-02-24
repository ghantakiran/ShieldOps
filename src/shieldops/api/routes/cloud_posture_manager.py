"""Cloud security posture manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cloud-posture-manager", tags=["Cloud Posture Manager"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Cloud posture manager service unavailable")
    return _manager


class RegisterResourceRequest(BaseModel):
    resource_id: str
    resource_type: str = ""
    cloud_provider: str = ""
    region: str = ""
    account_id: str = ""
    compliance_benchmarks: list[str] | None = None


class RecordFindingRequest(BaseModel):
    resource_id: str
    finding_type: str = "PUBLIC_ACCESS"
    benchmark: str = "CIS_AWS"
    priority: str = "MEDIUM"
    description: str = ""


@router.post("/resources")
async def register_resource(
    body: RegisterResourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    resource = manager.register_resource(**body.model_dump())
    return resource.model_dump()


@router.get("/resources")
async def list_resources(
    cloud_provider: str | None = None,
    resource_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return [
        r.model_dump()
        for r in manager.list_resources(
            cloud_provider=cloud_provider, resource_type=resource_type, limit=limit
        )
    ]


@router.get("/resources/{resource_id}")
async def get_resource(
    resource_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    resource = manager.get_resource(resource_id)
    if resource is None:
        raise HTTPException(404, f"Resource '{resource_id}' not found")
    return resource.model_dump()


@router.post("/findings")
async def record_finding(
    body: RecordFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    finding = manager.record_finding(**body.model_dump())
    return finding.model_dump()


@router.get("/evaluate/{resource_id}")
async def evaluate_resource(
    resource_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return [f.model_dump() for f in manager.evaluate_resource(resource_id)]


@router.get("/compliance-score")
async def calculate_compliance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.calculate_compliance_score()


@router.get("/high-risk")
async def detect_high_risk_resources(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return manager.detect_high_risk_resources()


@router.put("/findings/{finding_id}/resolve")
async def resolve_finding(
    finding_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    resolved = manager.resolve_finding(finding_id)
    if not resolved:
        raise HTTPException(404, f"Finding '{finding_id}' not found")
    return {"resolved": True, "finding_id": finding_id}


@router.get("/report")
async def generate_posture_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.generate_posture_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_stats()
